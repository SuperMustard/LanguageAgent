import json
from pathlib import Path

from .llm.base import LLMClient, Message
from .models import DebriefResult, Expression, ProPhrase, Word

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "debrief_prompt.md"


def _load_template_body() -> str:
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.split("## 模板", 1)[1].split("```", 2)[1].strip()


def _format_existing_phrases(existing_phrases: list[str]) -> str:
    if not existing_phrases:
        return "（无，这是第一次产出）"
    return "\n".join(f"- {p}" for p in existing_phrases)


def render_debrief_prompt(
    target_language: str, transcript: str, existing_phrases: list[str] | None = None
) -> str:
    body = _load_template_body()
    body = body.replace("{{target_language}}", target_language)
    body = body.replace("{{transcript}}", transcript)
    body = body.replace("{{existing_phrases}}", _format_existing_phrases(existing_phrases or []))
    return body


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[len("json"):]
    return text.strip()


def parse_debrief_payload(
    payload: dict, language_code: str, now_iso: str, scenario_type: str = ""
) -> DebriefResult:
    """纯逻辑：把 debrief LLM 输出的 dict 转成落库用的 Expression/Word/ProPhrase，
    补上 language/mastery/last_practiced（ProPhrase 还要补 scenario_type）。"""
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
    pro_phrases = [
        ProPhrase(
            phrase=p["phrase"],
            meaning=p.get("meaning", "") or "",
            dimension=p["dimension"],
            usage_note=p.get("usage_note", "") or "",
            language=language_code,
            scenario_type=scenario_type,
            mastery=0,
            last_practiced=now_iso,
        )
        for p in payload.get("pro_phrases", [])
    ]
    return DebriefResult(sentences=sentences, words=words, pro_phrases=pro_phrases)


def run_debrief(
    llm: LLMClient,
    target_language: str,
    language_code: str,
    transcript: str,
    now_iso: str,
    scenario_type: str = "",
    existing_phrases: list[str] | None = None,
) -> DebriefResult:
    prompt = render_debrief_prompt(target_language, transcript, existing_phrases)
    raw = llm.chat([Message(role="system", content=prompt)])
    payload = json.loads(_strip_json_fence(raw))
    return parse_debrief_payload(payload, language_code, now_iso, scenario_type)
