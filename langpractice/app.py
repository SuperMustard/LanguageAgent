from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from pydantic import BaseModel

from . import db, debrief, export
from .config import (
    AZURE_SPEECH_KEY,
    AZURE_SPEECH_REGION,
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_WHISPER_MODEL,
    SUPPORTED_LANGUAGES,
)
from .llm.base import LLMClient
from .llm.groq_client import GroqLLMClient
from .llm.mock import MockLLMClient
from .personas import BUILTIN_SCENARIOS
from .session import PracticeSession
from .stt.base import STTClient
from .stt.groq_whisper import GroqWhisperSTT
from .tts.azure_rest import AzureTTSClient
from .tts.base import TTSClient
from .tts.mock import MockTTSClient
from .tts_text import strip_for_speech

app = FastAPI(title="LanguageAgent — 口语演练 Agent (slice 1+2, 文字+语音)")


def _build_llm() -> LLMClient:
    # .env 填了 GROQ_API_KEY 就自动用 Groq，没填就退回 Mock —— 不用改代码切换。
    if GROQ_API_KEY:
        return GroqLLMClient(api_key=GROQ_API_KEY, model=GROQ_MODEL)
    return MockLLMClient()


def _build_stt() -> STTClient | None:
    # 没配 GROQ_API_KEY 时留空——语音端点调用时才报错，不阻塞纯文字模式启动。
    if not GROQ_API_KEY:
        return None
    return GroqWhisperSTT(api_key=GROQ_API_KEY, model=GROQ_WHISPER_MODEL)


def _build_tts() -> TTSClient:
    # .env 填了 AZURE_SPEECH_KEY 就自动用 Azure，没填就退回 Mock（占位提示音）。
    if AZURE_SPEECH_KEY and AZURE_SPEECH_REGION:
        return AzureTTSClient(api_key=AZURE_SPEECH_KEY, region=AZURE_SPEECH_REGION)
    return MockTTSClient()


# slice 1：session 状态放进程内存，不落库（见 CLAUDE.md 决定记录）。
_llm = _build_llm()
_stt = _build_stt()
_tts = _build_tts()
_sessions: dict[str, PracticeSession] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class StartRequest(BaseModel):
    scenario: str


class StartResponse(BaseModel):
    session_id: str
    opening_line: str


class MessageRequest(BaseModel):
    text: str


class MessageResponse(BaseModel):
    reply: str


class ExpressionOut(BaseModel):
    zh: str
    en_wrong: str
    en_correct: str
    error_note: str
    pattern: str


class WordOut(BaseModel):
    word: str
    meaning: str


class EndResponse(BaseModel):
    sentences: list[ExpressionOut]
    words: list[WordOut]


@app.get("/scenarios")
def list_scenarios() -> dict[str, str]:
    return {key: card.scenario_description for key, card in BUILTIN_SCENARIOS.items()}


@app.post("/sessions", response_model=StartResponse)
def start_session(req: StartRequest) -> StartResponse:
    card = BUILTIN_SCENARIOS.get(req.scenario)
    if card is None:
        raise HTTPException(404, f"unknown scenario: {req.scenario}")
    session = PracticeSession.start(card, _llm)
    _sessions[session.id] = session
    return StartResponse(session_id=session.id, opening_line=session.opening_line)


@app.post("/sessions/{session_id}/messages", response_model=MessageResponse)
def send_message(session_id: str, req: MessageRequest) -> MessageResponse:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(404, "unknown session")
    return MessageResponse(reply=session.turn(req.text))


@app.get("/sessions/{session_id}/opening-audio")
def opening_audio(session_id: str) -> Response:
    """开场白的语音版——语音演练开始时先放这个，再进入 /voice-messages 回合。"""
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(404, "unknown session")
    audio = _tts.synthesize(strip_for_speech(session.opening_line), session.card.language)
    return Response(
        content=audio,
        media_type="audio/wav",
        headers={"X-Reply-Text": quote(session.opening_line, safe="")},
    )


@app.post("/sessions/{session_id}/voice-messages")
async def voice_message(session_id: str, audio: UploadFile = File(...)) -> Response:
    """语音回合：录音 -> Groq Whisper 转文字 -> 复用现有角色扮演逻辑 -> TTS 念出回复。
    演练/纠错分离的铁律在 session.turn() 里已经保证，这里只是把文字输入输出包了一层语音。
    """
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(404, "unknown session")
    if _stt is None:
        raise HTTPException(503, "GROQ_API_KEY 未设置，STT 不可用")

    audio_bytes = await audio.read()
    transcribed_text = _stt.transcribe(
        audio_bytes, filename=audio.filename or "audio.wav", language=session.card.language
    )
    reply_text = session.turn(transcribed_text)
    reply_audio = _tts.synthesize(strip_for_speech(reply_text), session.card.language)

    return Response(
        content=reply_audio,
        media_type="audio/wav",
        headers={
            "X-Transcribed-Text": quote(transcribed_text, safe=""),
            "X-Reply-Text": quote(reply_text, safe=""),
        },
    )


@app.post("/sessions/{session_id}/end", response_model=EndResponse)
def end_session(session_id: str) -> EndResponse:
    session = _sessions.pop(session_id, None)
    if session is None:
        raise HTTPException(404, "unknown session")

    result = debrief.run_debrief(
        _llm,
        target_language=session.card.target_language,
        language_code=session.card.language,
        transcript=session.transcript_text(),
        now_iso=_now_iso(),
    )

    conn = db.connect()
    try:
        if result.sentences:
            db.insert_expressions(conn, result.sentences)
        if result.words:
            db.insert_words(conn, result.words)
    finally:
        conn.close()

    return EndResponse(
        sentences=[
            ExpressionOut(
                zh=e.zh,
                en_wrong=e.en_wrong,
                en_correct=e.en_correct,
                error_note=e.error_note,
                pattern=e.pattern,
            )
            for e in result.sentences
        ],
        words=[WordOut(word=w.word, meaning=w.meaning) for w in result.words],
    )


@app.get("/export/{language}")
def export_language(language: str) -> dict:
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, f"unsupported language: {language}")

    conn = db.connect()
    try:
        expressions = db.fetch_expressions(conn, language)
        words = db.fetch_words(conn, language)
    finally:
        conn.close()

    sentences_path, words_path = export.write_export_files(language, expressions, words)
    return {
        "sentences_file": str(sentences_path),
        "words_file": str(words_path),
        "sentences_json": export.expressions_to_json(expressions),
        "words_txt": export.words_to_txt(words),
    }
