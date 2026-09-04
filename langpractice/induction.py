"""口语侧诱导（二期）：新场景开始前，从自己的 SQLite 检索旧表达/生词/专业应对话术，
注入隐藏目标；演练结束后复盘有没有用上，更新掌握度。

检索条件按 SPEC 是"语言 + 掌握度 + 最后练习时间"，不限定场景。三个来源用
"保底 + 上限"配比（INDUCTION_MAX_TARGETS/INDUCTION_MIN_PHRASES，见 config.py），
避免专业话术被生词/病句挤掉。
"""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from . import db
from .config import INDUCTION_MAX_TARGETS, INDUCTION_MIN_COLLOCATIONS, INDUCTION_MIN_PHRASES
from .llm.base import LLMClient, Message

_REVIEW_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "prompts" / "induction_review_prompt.md"

_VALID_OUTCOMES = {"used_correctly", "used_incorrectly", "not_used"}

_Candidate = tuple[int, str, "InductionTarget"]


@dataclass
class InductionTarget:
    id: int
    kind: str  # "word" | "expression" | "pro_phrase" | "collocation" —— 决定复盘后调哪张表的 mastery
    label: str  # 注入 persona 提示词、也给复盘 prompt 用的展示文本


def _word_candidates(conn: sqlite3.Connection, language: str) -> list[_Candidate]:
    candidates = []
    for row in conn.execute(
        "SELECT id, word, meaning, mastery, last_practiced FROM words WHERE language = ?",
        (language,),
    ):
        label = f"生词「{row['word']}」" + (f"（{row['meaning']}）" if row["meaning"] else "")
        candidates.append((row["mastery"], row["last_practiced"], InductionTarget(row["id"], "word", label)))
    return candidates


def _expression_candidates(conn: sqlite3.Connection, language: str) -> list[_Candidate]:
    candidates = []
    for row in conn.execute(
        "SELECT id, en_correct, mastery, last_practiced FROM expressions WHERE language = ?",
        (language,),
    ):
        label = f'地道说法「{row["en_correct"]}」（之前用错过，找机会让学习者自然说出这个版本）'
        candidates.append(
            (row["mastery"], row["last_practiced"], InductionTarget(row["id"], "expression", label))
        )
    return candidates


def _pro_phrase_candidates(conn: sqlite3.Connection, language: str) -> list[_Candidate]:
    candidates = []
    for phrase in db.fetch_pro_phrases(conn, language):
        label = (
            f"专业应对话术「{phrase.phrase}」"
            + (f"（{phrase.meaning}）" if phrase.meaning else "")
            + f"，属于「{phrase.dimension}」应对维度，设计一个类似情境让学习者有机会自己说出接近的说法"
        )
        candidates.append((phrase.mastery, phrase.last_practiced, InductionTarget(phrase.id, "pro_phrase", label)))
    return candidates


def _collocation_candidates(conn: sqlite3.Connection, language: str) -> list[_Candidate]:
    """常规（历史）通道候选池——排除"今日通道"会覆盖的那批（今天刚精听提炼进库、还没被
    诱导过的 mastery=0 collocation，见 retrieve_today_collocations），避免同一条被两条
    通道重复选中、重复消耗名额。"""
    candidates = []
    for row in conn.execute(
        """
        SELECT id, phrase, meaning, mastery, last_practiced FROM collocations
        WHERE language = ?
          AND NOT (mastery = 0 AND last_practiced = '' AND date(created_at) = date('now'))
        """,
        (language,),
    ):
        label = (
            f"语块「{row['phrase']}」"
            + (f"（{row['meaning']}）" if row["meaning"] else "")
            + "，设计语境让学习者有机会自然用出这个搭配"
        )
        candidates.append(
            (row["mastery"], row["last_practiced"], InductionTarget(row["id"], "collocation", label))
        )
    return candidates


def retrieve_today_collocations(conn: sqlite3.Connection, language: str) -> list[InductionTarget]:
    """今日通道（SPEC 模块 3）：当天精听提炼（模块 4）刚进库、mastery=0 的 collocation，
    作为高优先级隐藏目标额外注入当天那场对话——不占 retrieve_induction_targets 的常规
    配额，调用方（voice_bot.py）直接把这个函数的结果拼接在 retrieve_induction_targets
    的返回值之后。"""
    targets = []
    for row in conn.execute(
        """
        SELECT id, phrase, meaning FROM collocations
        WHERE language = ? AND mastery = 0 AND last_practiced = '' AND date(created_at) = date('now')
        ORDER BY id
        """,
        (language,),
    ):
        label = (
            f"语块「{row['phrase']}」"
            + (f"（{row['meaning']}）" if row["meaning"] else "")
            + "，今天刚精听提炼出来，设计语境让学习者有机会自然用出这个搭配"
        )
        targets.append(InductionTarget(row["id"], "collocation", label))
    return targets


def retrieve_induction_targets(
    conn: sqlite3.Connection,
    language: str,
    limit: int = INDUCTION_MAX_TARGETS,
    min_phrases: int = INDUCTION_MIN_PHRASES,
    min_collocations: int = INDUCTION_MIN_COLLOCATIONS,
) -> list[InductionTarget]:
    """返回最多 limit 条候选（生词 + 病句地道说法 + 专业应对话术 + 精听语块混在一起挑），
    按 (mastery, last_practiced) 升序——最久没练/掌握度最低的排前面。

    四个来源用"保底 + 上限"配比（SPEC 模块 2.5/4）：先从 pro_phrases 池保底选出最多
    min_phrases 条，再从 collocation 池（今日通道那批已被 _collocation_candidates 排除）
    保底选出最多 min_collocations 条（池子不够就有多少选多少，绝不因为凑数选已掌握的），
    pro_phrases 保底优先于 collocation（专业话术是使用者最想练的能力）。剩下的名额从四个
    来源的全部候选（含未被保底选中的话术/语块）混合竞争，避免专业话术/语块被生词/病句挤掉，
    同时不让保底把名额浪费在"根本没货可推"的语言上。"""
    word_pool = _word_candidates(conn, language)
    expression_pool = _expression_candidates(conn, language)
    phrase_pool = sorted(_pro_phrase_candidates(conn, language), key=lambda c: (c[0], c[1]))
    collocation_pool = sorted(_collocation_candidates(conn, language), key=lambda c: (c[0], c[1]))

    guaranteed_phrases_count = min(min_phrases, limit, len(phrase_pool))
    guaranteed_phrases = phrase_pool[:guaranteed_phrases_count]

    remaining_after_phrases = limit - guaranteed_phrases_count
    guaranteed_collocations_count = min(min_collocations, remaining_after_phrases, len(collocation_pool))
    guaranteed_collocations = collocation_pool[:guaranteed_collocations_count]

    remaining_slots = remaining_after_phrases - guaranteed_collocations_count
    remaining_pool = (
        word_pool
        + expression_pool
        + phrase_pool[guaranteed_phrases_count:]
        + collocation_pool[guaranteed_collocations_count:]
    )
    remaining_pool.sort(key=lambda c: (c[0], c[1]))
    fill = remaining_pool[:remaining_slots]

    return [target for _, _, target in guaranteed_phrases + guaranteed_collocations + fill]


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
    """判断这场演练里，每个诱导目标有没有被用上、用得对不对。返回 {index: outcome}，
    index 是 targets 列表里的位置，**不是数据库 id**——生词/病句/专业话术分别存在三张表，
    各自的 id 都是从 1 自增的，混在一起传给 LLM 时完全可能撞号（比如 words 表和
    pro_phrases 表都有 id=1），如果用 db id 当 outcomes 的 key，撞号的两个目标会互相
    覆盖/错配彼此的判断结果。用列表位置当 key 彻底避开这个坑——位置在一次调用内必然唯一。
    outcome 是 used_correctly / used_incorrectly / not_used。没有目标、解析失败都返回
    空字典——调用方按"没判断出来就不动 mastery"处理，不强行猜。"""
    if not targets:
        return {}

    target_list_text = "\n".join(f"- id={i}: {t.label}" for i, t in enumerate(targets))
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
            index = item.get("id")
            outcome = item.get("outcome")
            if index is not None and outcome in _VALID_OUTCOMES:
                outcomes[int(index)] = outcome
    return outcomes


def apply_mastery_updates(
    conn: sqlite3.Connection,
    targets: list[InductionTarget],
    outcomes: dict[int, str],
    now_iso: str,
) -> None:
    """讲对了 mastery+1，讲错了 mastery-1（下限 0，db.py 里的 SQL 卡住），
    没用上/没判断出来就不动——保持"最久没碰"排前面，下次继续诱导。

    outcomes 是 review_induction_usage() 返回的 {列表位置: outcome}（见那边的注释——
    key 是位置不是 db id，避免三张表 id 各自从 1 自增导致的撞号），所以这里必须用
    enumerate 按位置对齐，不能再用 target.id 去查。"""
    for index, target in enumerate(targets):
        outcome = outcomes.get(index)
        if outcome == "used_correctly":
            delta = 1
        elif outcome == "used_incorrectly":
            delta = -1
        else:
            continue

        if target.kind == "word":
            db.adjust_word_mastery(conn, target.id, delta, now_iso)
        elif target.kind == "pro_phrase":
            db.adjust_pro_phrase_mastery(conn, target.id, delta, now_iso)
        elif target.kind == "collocation":
            db.adjust_collocation_mastery(conn, target.id, delta, now_iso)
        else:
            db.adjust_expression_mastery(conn, target.id, delta, now_iso)
