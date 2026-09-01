import sqlite3
from pathlib import Path

from . import db
from .models import PersonaCard

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "persona_template.md"

# 场景（内置的两个种子场景 + 自动生成的场景）统一存在 SQLite 的 scenarios 表，没有
# "内置 vs 自定义"的区分——种子场景只是 db.py 在表首次为空时插的两条普通行
# （见 seed_scenarios.py），之后就是普通数据，能改能删，跟场景管理页里的其它场景一样。


def _load_template_body() -> str:
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.split("## 模板", 1)[1].split("```", 2)[1].strip()


def _load_induction_block_template() -> str:
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    section = template.split("## induction_block", 1)[1]
    return section.split("```", 2)[1].strip()


def render_persona_prompt(
    card: PersonaCard, induction_targets: str = "", hostility_level: str | None = None
) -> str:
    """induction_targets 非空时才注入隐藏引导目标（二期口语侧诱导，见 SPEC）；
    默认空字符串，行为跟一期完全一样——没有旧表达可诱导时（比如这门语言第一次练）
    自然退化成空，不用调用方特判。

    hostility_level 为 None 时用场景卡自己的默认值（card.hostility_level）——
    "前端不选就用场景默认"这条規则由调用方（voice_bot.py）决定要不要传临场覆盖值，
    这里只管兜底。难缠满级也不能突破的红线是模板里写死的固定文字，不受这个参数影响。"""
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
        "hostility_level": hostility_level or card.hostility_level,
        "induction_block": induction_block,
    }
    for key, value in replacements.items():
        body = body.replace("{{" + key + "}}", value)
    return body


def get_scenario(conn: sqlite3.Connection, key: str) -> PersonaCard | None:
    return db.fetch_scenario(conn, key)


def list_all_scenario_descriptions(conn: sqlite3.Connection) -> dict[str, str]:
    """给场景下拉框用：{key: 场景描述}。"""
    return {card.key: card.scenario_description for card in db.fetch_all_scenarios(conn)}
