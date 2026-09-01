import sqlite3
from pathlib import Path

from .config import DB_PATH, DEFAULT_HOSTILITY_LEVEL
from .models import Expression, PersonaCard, ProPhrase, Word
from .seed_scenarios import SEED_SCENARIOS

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

CREATE TABLE IF NOT EXISTS pro_phrases (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    language       TEXT NOT NULL CHECK(language IN ('en','fr')),
    scenario_type  TEXT NOT NULL,
    phrase         TEXT NOT NULL,
    meaning        TEXT,
    dimension      TEXT NOT NULL,
    usage_note     TEXT,
    mastery        INTEGER NOT NULL DEFAULT 0,
    last_practiced TEXT NOT NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scenarios (
    key                   TEXT PRIMARY KEY,
    language              TEXT NOT NULL CHECK(language IN ('en','fr')),
    target_language       TEXT NOT NULL,
    role_identity         TEXT NOT NULL,
    emotional_state       TEXT NOT NULL,
    speaking_style        TEXT NOT NULL,
    hidden_motivation     TEXT NOT NULL,
    scenario_description  TEXT NOT NULL,
    difficulty_level      TEXT NOT NULL,
    hostility_level       TEXT NOT NULL DEFAULT '""" + DEFAULT_HOSTILITY_LEVEL + """',
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate_scenarios_add_hostility_level(conn)
    _seed_scenarios_if_empty(conn)
    return conn


def _migrate_scenarios_add_hostility_level(conn: sqlite3.Connection) -> None:
    """老数据库（本次改动之前建的）的 scenarios 表没有 hostility_level 列——
    `CREATE TABLE IF NOT EXISTS` 对已存在的表不会补列，得手动 ALTER TABLE 一次。
    新建的库走上面 SCHEMA 里的 DEFAULT，这里天然是 no-op（列已存在）。"""
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(scenarios)")}
    if "hostility_level" not in columns:
        conn.execute(
            f"ALTER TABLE scenarios ADD COLUMN hostility_level TEXT NOT NULL DEFAULT '{DEFAULT_HOSTILITY_LEVEL}'"
        )
        conn.commit()


def _seed_scenarios_if_empty(conn: sqlite3.Connection) -> None:
    """scenarios 表首次为空（全新数据库，或者用户把种子场景也删光了）时塞两条默认场景，
    插完就是普通行，跟场景管理页里删/查其它场景没有区别。不用 INSERT OR IGNORE 常驻做，
    不然用户删掉种子场景后，下次 connect() 又会把它复活——只在"整张表空"时播种一次。"""
    (count,) = conn.execute("SELECT COUNT(*) FROM scenarios").fetchone()
    if count == 0:
        for card in SEED_SCENARIOS:
            insert_scenario(conn, card)


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


def insert_pro_phrases(conn: sqlite3.Connection, phrases: list[ProPhrase]) -> None:
    """同 insert_expressions/insert_words：逐条插入把 id 写回对象，供前端删除用。"""
    for p in phrases:
        cursor = conn.execute(
            """
            INSERT INTO pro_phrases (language, scenario_type, phrase, meaning, dimension, usage_note, mastery, last_practiced)
            VALUES (:language, :scenario_type, :phrase, :meaning, :dimension, :usage_note, :mastery, :last_practiced)
            """,
            {
                "language": p.language,
                "scenario_type": p.scenario_type,
                "phrase": p.phrase,
                "meaning": p.meaning,
                "dimension": p.dimension,
                "usage_note": p.usage_note,
                "mastery": p.mastery,
                "last_practiced": p.last_practiced,
            },
        )
        p.id = cursor.lastrowid
    conn.commit()


def fetch_pro_phrases(conn: sqlite3.Connection, language: str) -> list[ProPhrase]:
    rows = conn.execute(
        "SELECT * FROM pro_phrases WHERE language = ? ORDER BY id", (language,)
    ).fetchall()
    return [
        ProPhrase(
            id=r["id"],
            language=r["language"],
            scenario_type=r["scenario_type"],
            phrase=r["phrase"],
            meaning=r["meaning"] or "",
            dimension=r["dimension"],
            usage_note=r["usage_note"] or "",
            mastery=r["mastery"],
            last_practiced=r["last_practiced"],
        )
        for r in rows
    ]


def delete_pro_phrase(conn: sqlite3.Connection, phrase_id: int) -> bool:
    cursor = conn.execute("DELETE FROM pro_phrases WHERE id = ?", (phrase_id,))
    conn.commit()
    return cursor.rowcount > 0


def delete_expression(conn: sqlite3.Connection, expression_id: int) -> bool:
    """删一条病句记录（比如识别错误导致的假诊断）。返回是否真的删到了东西。"""
    cursor = conn.execute("DELETE FROM expressions WHERE id = ?", (expression_id,))
    conn.commit()
    return cursor.rowcount > 0


def delete_word(conn: sqlite3.Connection, word_id: int) -> bool:
    cursor = conn.execute("DELETE FROM words WHERE id = ?", (word_id,))
    conn.commit()
    return cursor.rowcount > 0


def adjust_expression_mastery(
    conn: sqlite3.Connection, expression_id: int, delta: int, now_iso: str
) -> None:
    """口语侧诱导复盘用：讲对了 delta=+1，讲错了 delta=-1（下限 0 靠 SQL 的 MAX 卡住，
    不会变负数）。同时把 last_practiced 刷新成这次复盘的时间，不然同一条会一直被判定
    "最久没碰"，永远排在诱导检索的最前面。"""
    conn.execute(
        "UPDATE expressions SET mastery = MAX(0, mastery + ?), last_practiced = ? WHERE id = ?",
        (delta, now_iso, expression_id),
    )
    conn.commit()


def adjust_word_mastery(conn: sqlite3.Connection, word_id: int, delta: int, now_iso: str) -> None:
    conn.execute(
        "UPDATE words SET mastery = MAX(0, mastery + ?), last_practiced = ? WHERE id = ?",
        (delta, now_iso, word_id),
    )
    conn.commit()


def adjust_pro_phrase_mastery(
    conn: sqlite3.Connection, phrase_id: int, delta: int, now_iso: str
) -> None:
    """同 adjust_expression_mastery/adjust_word_mastery：口语侧诱导复盘用，
    进了诱导循环的话术用同一套掌握度更新规则（下限 0，同时刷新 last_practiced）。"""
    conn.execute(
        "UPDATE pro_phrases SET mastery = MAX(0, mastery + ?), last_practiced = ? WHERE id = ?",
        (delta, now_iso, phrase_id),
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


def _row_to_persona_card(row: sqlite3.Row) -> PersonaCard:
    return PersonaCard(
        key=row["key"],
        language=row["language"],
        target_language=row["target_language"],
        role_identity=row["role_identity"],
        emotional_state=row["emotional_state"],
        speaking_style=row["speaking_style"],
        hidden_motivation=row["hidden_motivation"],
        scenario_description=row["scenario_description"],
        difficulty_level=row["difficulty_level"],
        hostility_level=row["hostility_level"],
    )


def insert_scenario(conn: sqlite3.Connection, card: PersonaCard) -> None:
    """存一张场景卡自动生成（scenario_gen.py）产出的 PersonaCard。key 由调用方生成，
    要保证唯一——内置场景的 key（clinic_fr 等）不会跟这里冲突，因为自动生成的 key
    统一带 custom_ 前缀（见 scenario_gen.py）。"""
    conn.execute(
        """
        INSERT INTO scenarios (key, language, target_language, role_identity, emotional_state,
                                speaking_style, hidden_motivation, scenario_description, difficulty_level,
                                hostility_level)
        VALUES (:key, :language, :target_language, :role_identity, :emotional_state,
                :speaking_style, :hidden_motivation, :scenario_description, :difficulty_level,
                :hostility_level)
        """,
        {
            "key": card.key,
            "language": card.language,
            "target_language": card.target_language,
            "role_identity": card.role_identity,
            "emotional_state": card.emotional_state,
            "speaking_style": card.speaking_style,
            "hidden_motivation": card.hidden_motivation,
            "scenario_description": card.scenario_description,
            "difficulty_level": card.difficulty_level,
            "hostility_level": card.hostility_level,
        },
    )
    conn.commit()


def fetch_scenario(conn: sqlite3.Connection, key: str) -> PersonaCard | None:
    row = conn.execute("SELECT * FROM scenarios WHERE key = ?", (key,)).fetchone()
    return _row_to_persona_card(row) if row is not None else None


def fetch_all_scenarios(conn: sqlite3.Connection) -> list[PersonaCard]:
    rows = conn.execute("SELECT * FROM scenarios ORDER BY created_at").fetchall()
    return [_row_to_persona_card(r) for r in rows]


def delete_scenario(conn: sqlite3.Connection, key: str) -> bool:
    cursor = conn.execute("DELETE FROM scenarios WHERE key = ?", (key,))
    conn.commit()
    return cursor.rowcount > 0
