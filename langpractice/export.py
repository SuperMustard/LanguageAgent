import json
from pathlib import Path

from .config import EXPORT_DIR
from .models import Expression, Word

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


def write_export_files(
    language: str,
    expressions: list[Expression],
    words: list[Word],
    out_dir: Path = EXPORT_DIR,
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    sentences_path = out_dir / f"{language}_sentences.json"
    words_path = out_dir / f"{language}_words.txt"
    sentences_path.write_text(expressions_to_json(expressions), encoding="utf-8")
    words_path.write_text(words_to_txt(words), encoding="utf-8")
    return sentences_path, words_path
