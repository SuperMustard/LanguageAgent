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
class DebriefResult:
    sentences: list[Expression] = field(default_factory=list)
    words: list[Word] = field(default_factory=list)
