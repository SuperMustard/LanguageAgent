"""Pipecat 全双工语音 bot server —— 跟 langpractice 的主 FastAPI app（app.py，端口 8000）
是两个独立进程：这里只管语音 pipeline（Groq STT/LLM + Azure TTS，VAD 自动断句、可打断）。
场景卡、Debrief、存库这些跟 transport 无关的逻辑，原样复用 langpractice 的其它模块。

跑法：python -m langpractice.voice_bot   （默认端口 7860，见 pipecat.runner.run.main）
"""

import sqlite3
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.azure.tts import AzureTTSService
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.groq.stt import GroqSTTService
from pipecat.transcriptions.language import Language
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.workers.runner import WorkerRunner

from . import db, debrief
from .config import (
    AZURE_SPEECH_KEY,
    AZURE_SPEECH_REGION,
    GROQ_API_KEY,
    GROQ_MODEL,
    GROQ_WHISPER_MODEL,
    VAD_CONFIDENCE,
    VAD_MIN_VOLUME,
    VAD_START_SECS,
    VAD_STOP_SECS,
)
from .induction import (
    apply_mastery_updates,
    format_induction_targets,
    retrieve_induction_targets,
    retrieve_today_collocations,
    review_induction_usage,
)
from .llm.groq_client import GroqLLMClient
from .models import PersonaCard
from .personas import get_scenario, render_persona_prompt

load_dotenv(override=True)

_VOICE_BY_LANGUAGE = {"en": "en-US-JennyNeural", "fr": "fr-FR-DeniseNeural"}
_STT_LANGUAGE_BY_CODE = {"en": Language.EN, "fr": Language.FR}

# 调参走 .env（VAD_STOP_SECS 等，见 config.py），改完重启 voice_bot 就生效，不用改代码。
_VAD_PARAMS = VADParams(
    confidence=VAD_CONFIDENCE,
    start_secs=VAD_START_SECS,
    stop_secs=VAD_STOP_SECS,
    min_volume=VAD_MIN_VOLUME,
)

# Pipecat 的 TTS 是流式拼接 LLM 输出念出来的，不像旧 REST 版能在发去 TTS 前用
# tts_text.strip_for_speech() 整句过滤星号舞台指示。改成直接在 system prompt 里说清楚。
_VOICE_ONLY_SUFFIX = (
    "\n\n注意：你的话会被语音合成朗读出来，绝不要用 *叹气* *微笑* 这类只适合书面阅读的舞台"
    "指示或任何星号标记——情绪和停顿感直接体现在措辞、语气词（Hmm...、Bon...）里。"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _resolve_scenario(conn: sqlite3.Connection, runner_args: RunnerArguments) -> PersonaCard:
    body = runner_args.body or {}
    scenario_key = body.get("scenario", "clinic_fr")
    card = get_scenario(conn, scenario_key)
    if card is None:
        raise ValueError(f"unknown scenario: {scenario_key}")
    return card


def _resolve_hostility_level(card: PersonaCard, runner_args: RunnerArguments) -> str:
    """临场覆盖优先；前端没选（body 里没带这个键，或者带了空字符串）就落回场景默认值
    （card.hostility_level，来自 scenarios 表）。不校验是不是 HOSTILITY_LEVELS 里的
    四档之一——渲染进 prompt 的是自由文本，就算传了个奇怪的值，最坏情况只是提示词
    有点怪，不会破坏铁律（红线是模板里写死的，不受这个值影响）。"""
    body = runner_args.body or {}
    return body.get("hostility_level") or card.hostility_level


def _build_transcript(context: LLMContext) -> str:
    speaker_names = {"assistant": "AI", "user": "学习者"}
    lines = [
        f"{speaker_names[m['role']]}：{m['content']}"
        for m in context.get_messages()
        if m.get("role") in speaker_names and m.get("content")
    ]
    return "\n".join(lines)


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments) -> None:
    # 场景解析 + 诱导检索都是开场前的一次性读库，共用一个连接。
    startup_conn = db.connect()
    try:
        card = _resolve_scenario(startup_conn, runner_args)
        hostility_level = _resolve_hostility_level(card, runner_args)
        # 口语侧诱导（二期）：不限定场景，按语言检索旧表达，注入隐藏目标。没有历史记录时
        # targets 是空列表，render_persona_prompt 自然退化成一期行为（induction_block 留空）。
        # 今日通道（模块 4）额外拼接在后面——当天精听提炼刚进库、mastery=0 的 collocation
        # 高优先级注入当天这场对话，不占 retrieve_induction_targets 的常规配额。
        induction_targets = retrieve_induction_targets(
            startup_conn, card.language
        ) + retrieve_today_collocations(startup_conn, card.language)
    finally:
        startup_conn.close()

    logger.info(f"Starting voice bot, scenario={card.key}, hostility_level={hostility_level}")
    if induction_targets:
        logger.info(f"Induction targets for this session: {induction_targets}")

    # 不传 language 时 Whisper 有时会"翻译"成英文而不是"转写"原文——尤其是短句、法语这种
    # 场景，必须显式给语言提示，不能让它自己猜（见 CLAUDE.md 实现踩坑记录）。
    stt = GroqSTTService(
        api_key=GROQ_API_KEY,
        model=GROQ_WHISPER_MODEL,
        language=_STT_LANGUAGE_BY_CODE.get(card.language, Language.EN),
    )
    tts = AzureTTSService(
        api_key=AZURE_SPEECH_KEY,
        region=AZURE_SPEECH_REGION,
        settings=AzureTTSService.Settings(
            voice=_VOICE_BY_LANGUAGE.get(card.language, _VOICE_BY_LANGUAGE["en"]),
        ),
    )
    llm = GroqLLMService(
        api_key=GROQ_API_KEY,
        settings=GroqLLMService.Settings(
            model=GROQ_MODEL,
            system_instruction=render_persona_prompt(
                card,
                induction_targets=format_induction_targets(induction_targets),
                hostility_level=hostility_level,
            )
            + _VOICE_ONLY_SUFFIX,
        ),
    )

    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(params=_VAD_PARAMS)
        ),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )

    worker = PipelineWorker(pipeline, params=PipelineParams(enable_metrics=True))
    debrief_llm = GroqLLMClient(api_key=GROQ_API_KEY, model=GROQ_MODEL)

    @worker.rtvi.event_handler("on_client_ready")
    async def on_client_ready(rtvi):
        await rtvi.set_bot_ready()
        context.add_message({"role": "developer", "content": "开始，按角色设定说第一句话。"})
        await worker.queue_frames([LLMRunFrame()])

    @worker.rtvi.event_handler("on_client_message")
    async def on_client_message(rtvi, message):
        if message.type != "end_session":
            return

        now_iso = _now_iso()
        transcript = _build_transcript(context)

        conn = db.connect()
        try:
            # 话术去重（SPEC 模块 2.5）：产出前把这门语言已在库的话术传进 prompt，
            # 让 LLM 语义上避开推荐过的说法，数据库层面不用另写判重逻辑。
            existing_phrases = [p.phrase for p in db.fetch_pro_phrases(conn, card.language)]
            result = debrief.run_debrief(
                debrief_llm,
                target_language=card.target_language,
                language_code=card.language,
                transcript=transcript,
                now_iso=now_iso,
                scenario_type=card.key,
                existing_phrases=existing_phrases,
            )

            if result.sentences:
                db.insert_expressions(conn, result.sentences)
            if result.words:
                db.insert_words(conn, result.words)
            if result.pro_phrases:
                db.insert_pro_phrases(conn, result.pro_phrases)

            # 口语侧诱导复盘：这场开场前注入的隐藏目标有没有被用上，更新掌握度。
            # 独立于 Debrief 的另一次非流式调用，跟角色扮演/纠错分离铁律无关——这两次
            # 都发生在演练结束之后。
            if induction_targets:
                outcomes = review_induction_usage(
                    debrief_llm, card.target_language, transcript, induction_targets
                )
                # outcomes 是 {列表位置: outcome}，不是 db id（见 induction.py 的注释——
                # 三张表的 id 各自从 1 自增，混用 db id 当 key 会撞号），这里按位置配上
                # 具体是哪个 target 方便看日志。
                logger.info(
                    "Induction review outcomes: "
                    f"{[(t.kind, t.id, outcomes.get(i)) for i, t in enumerate(induction_targets)]}"
                )
                apply_mastery_updates(conn, induction_targets, outcomes, now_iso)
        finally:
            conn.close()

        payload: dict[str, Any] = {
            "sentences": [
                {
                    "id": e.id,
                    "zh": e.zh,
                    "en_wrong": e.en_wrong,
                    "en_correct": e.en_correct,
                    "error_note": e.error_note,
                    "pattern": e.pattern,
                }
                for e in result.sentences
            ],
            "words": [{"id": w.id, "word": w.word, "meaning": w.meaning} for w in result.words],
            "pro_phrases": [
                {
                    "id": p.id,
                    "phrase": p.phrase,
                    "meaning": p.meaning,
                    "dimension": p.dimension,
                    "usage_note": p.usage_note,
                }
                for p in result.pro_phrases
            ],
        }
        await rtvi.send_server_response(message, payload)

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        await worker.cancel()

    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)
    await runner.run()


async def bot(runner_args: RunnerArguments):
    """Pipecat runner 入口：在calling module 里找这个函数。"""
    transport_params = {
        "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    }
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
