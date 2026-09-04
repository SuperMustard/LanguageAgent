import json
from pathlib import Path

from .config import EXPORT_DIR
from .models import Collocation, Expression, ProPhrase, Word

SENTENCE_FIELDS = ("zh", "en_wrong", "en_correct", "error_note", "pattern")


def expressions_to_json(expressions: list[Expression]) -> str:
    """按 langhelper 病句卡契约：只含五个字段，不带 language/mastery/last_practiced。"""
    data = [{field: getattr(e, field) for field in SENTENCE_FIELDS} for e in expressions]
    return json.dumps(data, ensure_ascii=False, indent=2)


def words_to_txt(words: list[Word]) -> str:
    """按 langhelper 生词卡契约：纯文本，每行 `词|义`（义可省略），大小写不敏感去重。"""
    seen: set[str] = set()
    lines: list[str] = []
    for w in words:
        key = w.word.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"{w.word}|{w.meaning}" if w.meaning else w.word)
    return "\n".join(lines) + ("\n" if lines else "")


def pro_phrases_to_json(phrases: list[ProPhrase]) -> str:
    """按 langhelper 表达块卡契约：只含 phrase/meaning/note 三个字段（SPEC"导出格式契约 →
    表达块卡"）。`usage_note` 降级进 `note`；`dimension`/`scenario_type`/language/mastery/
    last_practiced 等 agent 内部字段一律剥离——它们只在诱导循环里有意义。按 phrase
    大小写不敏感去重，保留第一次出现的写法（跟 words_to_txt 的去重规则一致）。"""
    seen: set[str] = set()
    data = []
    for p in phrases:
        key = p.phrase.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        data.append({"phrase": p.phrase, "meaning": p.meaning, "note": p.usage_note})
    return json.dumps(data, ensure_ascii=False, indent=2)


def collocations_to_json(collocations: list[Collocation]) -> str:
    """按 langhelper 表达块卡契约：只含 phrase/meaning/note 三个字段——跟 pro_phrases_to_json
    同构（collocation.note 本来就叫 note，不用像 pro_phrases 那样从 usage_note 降级）。
    source/language/mastery/last_practiced 等 agent 内部字段一律剥离。按 phrase 大小写
    不敏感去重，保留第一次出现的写法。"""
    seen: set[str] = set()
    data = []
    for c in collocations:
        key = c.phrase.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        data.append({"phrase": c.phrase, "meaning": c.meaning, "note": c.note})
    return json.dumps(data, ensure_ascii=False, indent=2)


def merge_phrase_cards(pro_phrases: list[ProPhrase], collocations: list[Collocation]) -> str:
    """pro_phrases 和 collocations 共用「表达块卡」导出格式，写进同一个 {lang}_phrases.json——
    SPEC「导出格式契约」明确两者若产出同一 phrase 要字面去重，避免同块表达出两张卡。
    pro_phrases 先拼、collocations 后拼，同 phrase 时 pro_phrases 那条赢（专业话术是
    使用者最想练的能力，SPEC 排序上把它放在 collocation 前面）。"""
    seen: set[str] = set()
    data = []
    for phrase, meaning, note in [(p.phrase, p.meaning, p.usage_note) for p in pro_phrases] + [
        (c.phrase, c.meaning, c.note) for c in collocations
    ]:
        key = phrase.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        data.append({"phrase": phrase, "meaning": meaning, "note": note})
    return json.dumps(data, ensure_ascii=False, indent=2)


def write_export_files(
    language: str,
    expressions: list[Expression],
    words: list[Word],
    pro_phrases: list[ProPhrase],
    collocations: list[Collocation] | None = None,
    out_dir: Path = EXPORT_DIR,
) -> tuple[Path, Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    sentences_path = out_dir / f"{language}_sentences.json"
    words_path = out_dir / f"{language}_words.txt"
    phrases_path = out_dir / f"{language}_phrases.json"
    sentences_path.write_text(expressions_to_json(expressions), encoding="utf-8")
    words_path.write_text(words_to_txt(words), encoding="utf-8")
    phrases_path.write_text(merge_phrase_cards(pro_phrases, collocations or []), encoding="utf-8")
    return sentences_path, words_path, phrases_path
