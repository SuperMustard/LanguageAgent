import sqlite3
from pathlib import Path

from .config import DB_PATH
from .models import Expression, Word

SCHEMA = """
CREATE TABLE IF NOT EXISTS expressions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    language       TEXT NOT NULL CHECK(language IN ('en','fr')),
    zh             TEXT NOT NULL,
    en_wrong       TEXT NOT NULL,
    en_correct     TEXT NOT NULL,
    error_note     TEXT NOT NULL,
    pattern        TEXT NOT NULL,
    mastery        INTEGER NOT NULL DEFAULT 0,
    last_practiced TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS words (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    language       TEXT NOT NULL CHECK(language IN ('en','fr')),
    word           TEXT NOT NULL,
    meaning        TEXT,
    mastery        INTEGER NOT NULL DEFAULT 0,
    last_practiced TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def insert_expressions(conn: sqlite3.Connection, expressions: list[Expression]) -> None:
    """插入后把每条记录的 id 写回对象本身（sqlite3 的 executemany 拿不到每行的
    lastrowid，只能逐条 execute），方便调用方（比如 voice_bot.py）马上把 id
    传给前端，用于之后的删除操作（识别错误导致的假病句，需要能单条撤销）。"""
    for e in expressions:
        cursor = conn.execute(
            """
            INSERT INTO expressions (language, zh, en_wrong, en_correct, error_note, pattern, mastery, last_practiced)
            VALUES (:language, :zh, :en_wrong, :en_correct, :error_note, :pattern, :mastery, :last_practiced)
            """,
            {
                "language": e.language,
                "zh": e.zh,
                "en_wrong": e.en_wrong,
                "en_correct": e.en_correct,
                "error_note": e.error_note,
                "pattern": e.pattern,
                "mastery": e.mastery,
                "last_practiced": e.last_practiced,
            },
        )
        e.id = cursor.lastrowid
    conn.commit()


def insert_words(conn: sqlite3.Connection, words: list[Word]) -> None:
    """同 insert_expressions：逐条插入把 id 写回对象，供前端删除用。"""
    for w in words:
        cursor = conn.execute(
            """
            INSERT INTO words (language, word, meaning, mastery, last_practiced)
            VALUES (:language, :word, :meaning, :mastery, :last_practiced)
            """,
            {
                "language": w.language,
                "word": w.word,
                "meaning": w.meaning,
                "mastery": w.mastery,
                "last_practiced": w.last_practiced,
            },
        )
        w.id = cursor.lastrowid
    conn.commit()


def delete_expression(conn: sqlite3.Connection, expression_id: int) -> bool:
    """删一条病句记录（比如识别错误导致的假诊断）。返回是否真的删到了东西。"""
    cursor = conn.execute("DELETE FROM expressions WHERE id = ?", (expression_id,))
    conn.commit()
    return cursor.rowcount > 0


def delete_word(conn: sqlite3.Connection, word_id: int) -> bool:
    cursor = conn.execute("DELETE FROM words WHERE id = ?", (word_id,))
    conn.commit()
    return cursor.rowcount > 0


def fetch_expressions(conn: sqlite3.Connection, language: str) -> list[Expression]:
    rows = conn.execute(
        "SELECT * FROM expressions WHERE language = ? ORDER BY id", (language,)
    ).fetchall()
    return [
        Expression(
            id=r["id"],
            language=r["language"],
            zh=r["zh"],
            en_wrong=r["en_wrong"],
            en_correct=r["en_correct"],
            error_note=r["error_note"],
            pattern=r["pattern"],
            mastery=r["mastery"],
            last_practiced=r["last_practiced"],
        )
        for r in rows
    ]


def fetch_words(conn: sqlite3.Connection, language: str) -> list[Word]:
    rows = conn.execute(
        "SELECT * FROM words WHERE language = ? ORDER BY id", (language,)
    ).fetchall()
    return [
        Word(
            id=r["id"],
            language=r["language"],
            word=r["word"],
            meaning=r["meaning"] or "",
            mastery=r["mastery"],
            last_practiced=r["last_practiced"],
        )
        for r in rows
    ]
