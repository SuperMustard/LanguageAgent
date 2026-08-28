"""场景卡自动生成：给一段自由中文描述 + 目标语言，LLM 按 persona_template.md 的字段
结构填充生成一张新的 PersonaCard。落库（scenarios 表）是调用方的事——这个模块只管
"描述 -> PersonaCard" 这一步，方便单独测试。
"""

import json
import uuid
from pathlib import Path

from .llm.base import LLMClient, Message
from .models import PersonaCard

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "scenario_generation_prompt.md"

_TARGET_LANGUAGE_NAME = {"en": "English", "fr": "French"}

_REQUIRED_FIELDS = (
    "role_identity",
    "emotional_state",
    "speaking_style",
    "hidden_motivation",
    "scenario_description",
    "difficulty_level",
)


def _load_template_body() -> str:
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.split("## 模板", 1)[1].split("```", 2)[1].strip()


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[len("json"):]
    return text.strip()


def render_scenario_generation_prompt(description: str, target_language: str) -> str:
    return (
        _load_template_body()
        .replace("{{target_language}}", target_language)
        .replace("{{description}}", description)
    )


def generate_persona_card(llm: LLMClient, description: str, language: str) -> PersonaCard:
    """description 是用户输入的自由中文场景想法，language 是 "en"/"fr"。
    key 自动生成、带 custom_ 前缀，跟内置场景（clinic_fr 等）不会冲突。"""
    target_language = _TARGET_LANGUAGE_NAME.get(language, "English")
    prompt = render_scenario_generation_prompt(description, target_language)

    raw = llm.chat([Message(role="system", content=prompt)])
    payload = json.loads(_strip_json_fence(raw))

    missing = [f for f in _REQUIRED_FIELDS if not payload.get(f)]
    if missing:
        raise ValueError(f"场景生成结果缺字段: {missing}")

    return PersonaCard(
        key=f"custom_{uuid.uuid4().hex[:8]}",
        language=language,
        target_language=target_language,
        role_identity=payload["role_identity"],
        emotional_state=payload["emotional_state"],
        speaking_style=payload["speaking_style"],
        hidden_motivation=payload["hidden_motivation"],
        scenario_description=payload["scenario_description"],
        difficulty_level=payload["difficulty_level"],
    )
