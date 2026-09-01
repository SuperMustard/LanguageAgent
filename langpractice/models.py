from dataclasses import dataclass, field


@dataclass
class Expression:
    """一条病句记录。language/mastery/last_practiced 是 agent 内部字段，导出时剥离。"""

    zh: str
    en_wrong: str
    en_correct: str
    error_note: str
    pattern: str
    language: str
    mastery: int = 0
    last_practiced: str = ""
    id: int | None = None


@dataclass
class Word:
    """一条生词记录。meaning 可为空字符串。"""

    word: str
    meaning: str
    language: str
    mastery: int = 0
    last_practiced: str = ""
    id: int | None = None


@dataclass
class ProPhrase:
    """一条专业应对话术记录（模块 2.5）。除了进 agent 自己的诱导循环，phrase/meaning/
    usage_note 还会导出成「表达块卡」（export.pro_phrases_to_json）；dimension/
    scenario_type/mastery/last_practiced 是 agent 内部字段，导出时剥离。"""

    phrase: str
    meaning: str
    dimension: str  # 同理承接/设立边界/降级冲突/重定向解决/vouvoiement
    usage_note: str
    language: str
    scenario_type: str
    mastery: int = 0
    last_practiced: str = ""
    id: int | None = None


@dataclass
class DebriefResult:
    sentences: list[Expression] = field(default_factory=list)
    words: list[Word] = field(default_factory=list)
    pro_phrases: list[ProPhrase] = field(default_factory=list)


@dataclass
class PersonaCard:
    """角色卡——一个场景的完整设定。全部存在 SQLite 的 scenarios 表里（db.py），
    种子场景（seed_scenarios.py）和 AI 自动生成的场景没有区别，都是普通行，能改能删。
    放在 models.py 而不是 personas.py，是因为 db.py 要能返回 PersonaCard，
    放 personas.py 会跟 db.py 互相 import 成环。"""

    key: str
    language: str  # 内部语言码，"en" | "fr"（对齐 SUPPORTED_LANGUAGES）
    target_language: str  # 模板里展示给 LLM 的语言名，如 "French" / "English"
    role_identity: str
    emotional_state: str
    speaking_style: str
    hidden_motivation: str
    scenario_description: str
    difficulty_level: str
    # 场景默认"难缠程度"（模块 2.5 配套）——跟 difficulty_level（语言难度）是正交维度，
    # 只影响角色的对抗/挑剔态度。每场演练前端可临场覆盖（见 config.HOSTILITY_LEVELS），
    # 不选就用这个默认值。满级也不能突破的红线写死在 persona_template.md 里，不是这个字段管的。
    hostility_level: str = "中等"
