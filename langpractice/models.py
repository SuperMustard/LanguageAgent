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
    """一条生词记录。meaning 可为空字符串。phonetic（音标）来自 Trancy 词表导入
    （模块 4），备用字段，不参与导出（生词卡格式只有 词|义）。"""

    word: str
    meaning: str
    language: str
    phonetic: str = ""
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
class Collocation:
    """一条语块/地道搭配记录（模块 4 精听提炼产出）。跟 pro_phrases 共用「表达块卡」
    导出格式（phrase/meaning/note），但是独立的表——collocation 没有 dimension/
    scenario_type，不按专业维度组织。source 固定 "mining"，导出时剥离（连同 language/
    mastery/last_practiced），只是内部标记，跟 pro_phrases 区分来源。"""

    phrase: str
    meaning: str
    note: str
    language: str
    source: str = "mining"
    mastery: int = 0
    last_practiced: str = ""
    id: int | None = None


@dataclass
class PhoneticNote:
    """一条语音现象留痕（模块 4 精听提炼产出）。只存不导——不进任何导出文件，不进
    induction.py。病根是听觉解码能力，不是记忆缺口，所以没有 mastery/last_practiced。
    word_or_span 是"哪里没听清"（用户能可靠判断的部分）；现象类型（连读/弱读/吞音）
    不记，留给未来模型看 sentence+word_or_span 事后推断。"""

    sentence: str
    word_or_span: str
    source: str  # 句表 CSV 的 URL，回溯重听用
    date: str
    language: str
    id: int | None = None


@dataclass
class MiningSentence:
    """句表 CSV 导入后的暂存池行（模块 4 精听提炼）。status 流转：
    pending（刚导入）-> phonetic/skipped（人工三选一，终态）-> queued（选"语言"，
    等批量 Groq 处理）-> done（Groq 处理完，产出已分流进 words/collocations）。
    解析失败的行保持 queued，可重新批量提交重试。"""

    sentence: str
    translation: str
    url: str
    csv_date: str
    language: str
    status: str = "pending"
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
