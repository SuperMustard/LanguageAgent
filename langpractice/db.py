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
    conn.executemany(
        """
        INSERT INTO expressions (language, zh, en_wrong, en_correct, error_note, pattern, mastery, last_practiced)
        VALUES (:language, :zh, :en_wrong, :en_correct, :error_note, :pattern, :mastery, :last_practiced)
        """,
        [
            {
                "language": e.language,
                "zh": e.zh,
                "en_wrong": e.en_wrong,
                "en_correct": e.en_correct,
                "error_note": e.error_note,
                "pattern": e.pattern,
                "mastery": e.mastery,
                "last_practiced": e.last_practiced,
            }
            for e in expressions
        ],
    )
    conn.commit()


def insert_words(conn: sqlite3.Connection, words: list[Word]) -> None:
    conn.executemany(
        """
        INSERT INTO words (language, word, meaning, mastery, last_practiced)
        VALUES (:language, :word, :meaning, :mastery, :last_practiced)
        """,
        [
            {
                "language": w.language,
                "word": w.word,
                "meaning": w.meaning,
                "mastery": w.mastery,
                "last_practiced": w.last_practiced,
            }
            for w in words
        ],
    )
    conn.commit()


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
