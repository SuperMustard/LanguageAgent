import sqlite3
from pathlib import Path

from . import db
from .models import PersonaCard

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "persona_template.md"


# 加新内置场景 = 在这里加一条 PersonaCard，不用碰其它逻辑。
# 场景卡自动生成的场景（见 scenario_gen.py）存在 SQLite 的 scenarios 表，不在这个 dict
# 里——get_scenario()/list_all_scenario_descriptions() 会把两边合并起来用。
BUILTIN_SCENARIOS: dict[str, PersonaCard] = {
    "clinic_fr": PersonaCard(
        key="clinic_fr",
        language="fr",
        target_language="French",
        role_identity="一位来做按摩治疗的客人，今天诸事不顺",
        emotional_state="烦躁、有点不耐烦，但不至于无理取闹",
        speaking_style="简短、带情绪，偶尔叹气",
        hidden_motivation="其实想放松，但嘴上不饶人；被真诚对待后会慢慢软化",
        scenario_description="客人刚进诊所，迟到了又找不到车位，一肚子气。你（学习者）是治疗师，要安抚并顺利开始 treatment。",
        difficulty_level="中级，语速正常，用日常口语",
    ),
    "interview_en": PersonaCard(
        key="interview_en",
        language="en",
        target_language="English",
        role_identity="一位招聘经理",
        emotional_state="专业、友好但有评估性",
        speaking_style="清晰、结构化，会追问细节",
        hidden_motivation="想判断候选人是否真的合适，会礼貌地深挖",
        scenario_description="一场30分钟的岗位面试，你（学习者）是候选人。",
        difficulty_level="中级偏上，会用一些职场惯用表达",
    ),
}


def _load_template_body() -> str:
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.split("## 模板", 1)[1].split("```", 2)[1].strip()


def _load_induction_block_template() -> str:
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    section = template.split("## induction_block", 1)[1]
    return section.split("```", 2)[1].strip()


def render_persona_prompt(card: PersonaCard, induction_targets: str = "") -> str:
    """induction_targets 非空时才注入隐藏引导目标（二期口语侧诱导，见 SPEC）；
    默认空字符串，行为跟一期完全一样——没有旧表达可诱导时（比如这门语言第一次练）
    自然退化成空，不用调用方特判。"""
    body = _load_template_body()
    induction_block = ""
    if induction_targets:
        induction_block = _load_induction_block_template().replace(
            "{{induction_targets}}", induction_targets
        )
    replacements = {
        "target_language": card.target_language,
        "role_identity": card.role_identity,
        "emotional_state": card.emotional_state,
        "speaking_style": card.speaking_style,
        "hidden_motivation": card.hidden_motivation,
        "scenario_description": card.scenario_description,
        "difficulty_level": card.difficulty_level,
        "induction_block": induction_block,
    }
    for key, value in replacements.items():
        body = body.replace("{{" + key + "}}", value)
    return body


def get_scenario(conn: sqlite3.Connection, key: str) -> PersonaCard | None:
    """内置场景优先查内存 dict，查不到再查 scenarios 表（自动生成的场景）。"""
    card = BUILTIN_SCENARIOS.get(key)
    if card is not None:
        return card
    return db.fetch_scenario(conn, key)


def list_all_scenario_descriptions(conn: sqlite3.Connection) -> dict[str, str]:
    """给场景下拉框用：内置 + 自动生成的场景合并成一个 {key: 场景描述}。"""
    result = {key: card.scenario_description for key, card in BUILTIN_SCENARIOS.items()}
    for card in db.fetch_all_scenarios(conn):
        result[card.key] = card.scenario_description
    return result
