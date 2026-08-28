"""口语侧诱导（二期）：新场景开始前，从自己的 SQLite 检索旧表达/生词，
格式化成 persona_template.md 的 induction_block 要的目标列表文本。

检索条件按 SPEC 是"语言 + 掌握度 + 最后练习时间"，不限定场景。掌握度更新算法还没做
（见 CLAUDE.md 已推迟的增量），mastery 现在对同语言的记录全是 0，排序上等于没有区分度——
先纯按 last_practiced 挑最久没碰的，等掌握度更新上线后再把它加进排序键。
"""

import sqlite3


def retrieve_induction_targets(
    conn: sqlite3.Connection, language: str, limit: int = 2
) -> list[str]:
    """返回最多 limit 条候选标签（生词 + 病句地道说法混在一起挑），
    按 (mastery, last_practiced) 升序——最久没练/掌握度最低的排前面。"""
    candidates: list[tuple[int, str, str]] = []

    for row in conn.execute(
        "SELECT word, meaning, mastery, last_practiced FROM words WHERE language = ?",
        (language,),
    ):
        label = f"生词「{row['word']}」" + (f"（{row['meaning']}）" if row["meaning"] else "")
        candidates.append((row["mastery"], row["last_practiced"], label))

    for row in conn.execute(
        "SELECT en_correct, mastery, last_practiced FROM expressions WHERE language = ?",
        (language,),
    ):
        label = f'地道说法「{row["en_correct"]}」（之前用错过，找机会让学习者自然说出这个版本）'
        candidates.append((row["mastery"], row["last_practiced"], label))

    candidates.sort(key=lambda c: (c[0], c[1]))
    return [label for _, _, label in candidates[:limit]]


def format_induction_targets(targets: list[str]) -> str:
    if not targets:
        return ""
    return "\n".join(f"- {t}" for t in targets)
