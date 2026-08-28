from dataclasses import dataclass
from pathlib import Path

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "persona_template.md"


@dataclass
class PersonaCard:
    key: str
    language: str  # 内部语言码，"en" | "fr"（对齐 SUPPORTED_LANGUAGES）
    target_language: str  # 模板里展示给 LLM 的语言名，如 "French" / "English"
    role_identity: str
    emotional_state: str
    speaking_style: str
    hidden_motivation: str
    scenario_description: str
    difficulty_level: str


# 加新场景 = 在这里加一条 PersonaCard，不用碰其它逻辑。
# 未来"场景卡自动生成"功能（见 CLAUDE.md「已推迟的增量想法」）：LLM 按同样字段填充产出
# PersonaCard，再塞进这个 dict（或换成持久化存储）即可接上，不需要改 render_persona_prompt。
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


def render_persona_prompt(card: PersonaCard) -> str:
    body = _load_template_body()
    replacements = {
        "target_language": card.target_language,
        "role_identity": card.role_identity,
        "emotional_state": card.emotional_state,
        "speaking_style": card.speaking_style,
        "hidden_motivation": card.hidden_motivation,
        "scenario_description": card.scenario_description,
        "difficulty_level": card.difficulty_level,
        "induction_block": "",  # 二期才填，一期留空（见 SPEC）
    }
    for key, value in replacements.items():
        body = body.replace("{{" + key + "}}", value)
    return body
