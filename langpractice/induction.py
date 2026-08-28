"""口语侧诱导（二期）：新场景开始前，从自己的 SQLite 检索旧表达/生词，注入隐藏目标；
演练结束后复盘有没有用上，更新掌握度。

检索条件按 SPEC 是"语言 + 掌握度 + 最后练习时间"，不限定场景。
"""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from . import db
from .llm.base import LLMClient, Message

_REVIEW_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "induction_review_prompt.md"

_VALID_OUTCOMES = {"used_correctly", "used_incorrectly", "not_used"}


@dataclass
class InductionTarget:
    id: int
    kind: str  # "word" | "expression" —— 决定复盘后调哪张表的 mastery
    label: str  # 注入 persona 提示词、也给复盘 prompt 用的展示文本


def retrieve_induction_targets(
    conn: sqlite3.Connection, language: str, limit: int = 2
) -> list[InductionTarget]:
    """返回最多 limit 条候选（生词 + 病句地道说法混在一起挑），
    按 (mastery, last_practiced) 升序——最久没练/掌握度最低的排前面。"""
    candidates: list[tuple[int, str, InductionTarget]] = []

    for row in conn.execute(
        "SELECT id, word, meaning, mastery, last_practiced FROM words WHERE language = ?",
        (language,),
    ):
        label = f"生词「{row['word']}」" + (f"（{row['meaning']}）" if row["meaning"] else "")
        candidates.append((row["mastery"], row["last_practiced"], InductionTarget(row["id"], "word", label)))

    for row in conn.execute(
        "SELECT id, en_correct, mastery, last_practiced FROM expressions WHERE language = ?",
        (language,),
    ):
        label = f'地道说法「{row["en_correct"]}」（之前用错过，找机会让学习者自然说出这个版本）'
        candidates.append(
            (row["mastery"], row["last_practiced"], InductionTarget(row["id"], "expression", label))
        )

    candidates.sort(key=lambda c: (c[0], c[1]))
    return [target for _, _, target in candidates[:limit]]


def format_induction_targets(targets: list[InductionTarget]) -> str:
    if not targets:
        return ""
    return "\n".join(f"- {t.label}" for t in targets)


def _load_review_template() -> str:
    template = _REVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.split("## 模板", 1)[1].split("```", 2)[1].strip()


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[len("json"):]
    return text.strip()


def review_induction_usage(
    llm: LLMClient, target_language: str, transcript: str, targets: list[InductionTarget]
) -> dict[int, str]:
    """判断这场演练里，每个诱导目标有没有被用上、用得对不对。返回 {target_id: outcome}，
    outcome 是 used_correctly / used_incorrectly / not_used。没有目标、解析失败都返回
    空字典——调用方按"没判断出来就不动 mastery"处理，不强行猜。"""
    if not targets:
        return {}

    target_list_text = "\n".join(f"- id={t.id}: {t.label}" for t in targets)
    prompt = (
        _load_review_template()
        .replace("{{target_language}}", target_language)
        .replace("{{transcript}}", transcript)
        .replace("{{targets}}", target_list_text)
    )

    raw = llm.chat([Message(role="system", content=prompt)])
    try:
        payload = json.loads(_strip_json_fence(raw))
    except (json.JSONDecodeError, ValueError):
        return {}

    outcomes: dict[int, str] = {}
    if isinstance(payload, list):
        for item in payload:
            target_id = item.get("id")
            outcome = item.get("outcome")
            if target_id is not None and outcome in _VALID_OUTCOMES:
                outcomes[int(target_id)] = outcome
    return outcomes


def apply_mastery_updates(
    conn: sqlite3.Connection,
    targets: list[InductionTarget],
    outcomes: dict[int, str],
    now_iso: str,
) -> None:
    """讲对了 mastery+1，讲错了 mastery-1（下限 0，db.py 里的 SQL 卡住），
    没用上/没判断出来就不动——保持"最久没碰"排前面，下次继续诱导。"""
    for target in targets:
        outcome = outcomes.get(target.id)
        if outcome == "used_correctly":
            delta = 1
        elif outcome == "used_incorrectly":
            delta = -1
        else:
            continue

        if target.kind == "word":
            db.adjust_word_mastery(conn, target.id, delta, now_iso)
        else:
            db.adjust_expression_mastery(conn, target.id, delta, now_iso)
