import json
from pathlib import Path

from .llm.base import LLMClient, Message
from .models import DebriefResult, Expression, Word

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "debrief_prompt.md"


def _load_template_body() -> str:
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.split("## 模板", 1)[1].split("```", 2)[1].strip()


def render_debrief_prompt(target_language: str, transcript: str) -> str:
    body = _load_template_body()
    body = body.replace("{{target_language}}", target_language)
    body = body.replace("{{transcript}}", transcript)
    return body


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[len("json"):]
    return text.strip()


def parse_debrief_payload(payload: dict, language_code: str, now_iso: str) -> DebriefResult:
    """纯逻辑：把 debrief LLM 输出的 dict 转成落库用的 Expression/Word，补上 language/mastery/last_practiced。"""
    sentences = [
        Expression(
            zh=s["zh"],
            en_wrong=s["en_wrong"],
            en_correct=s["en_correct"],
            error_note=s["error_note"],
            pattern=s["pattern"],
            language=language_code,
            mastery=0,
            last_practiced=now_iso,
        )
        for s in payload.get("sentences", [])
    ]
    words = [
        Word(
            word=w["word"],
            meaning=w.get("meaning", "") or "",
            language=language_code,
            mastery=0,
            last_practiced=now_iso,
        )
        for w in payload.get("words", [])
    ]
    return DebriefResult(sentences=sentences, words=words)


def run_debrief(
    llm: LLMClient,
    target_language: str,
    language_code: str,
    transcript: str,
    now_iso: str,
) -> DebriefResult:
    prompt = render_debrief_prompt(target_language, transcript)
    raw = llm.chat([Message(role="system", content=prompt)])
    payload = json.loads(_strip_json_fence(raw))
    return parse_debrief_payload(payload, language_code, now_iso)
