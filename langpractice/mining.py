"""模块 4：精听提炼（Intensive-Listening Mining）。

吃 Trancy 导出的两种 CSV（词表 / 句表），词表极简直入 words 表（本文件负责的部分），
句表走完整流水线（导入去重 -> 人工三选一 -> Groq 分诊提炼 -> 入库分流，见 app.py 的
/mining/sentences/* 路由和本文件后续补充的函数）。
"""

import csv
import io
import json
import re
from pathlib import Path

from .llm.base import LLMClient, Message

_TRIAGE_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent / "prompts" / "mining_triage_prompt.md"
)

_LANGUAGE_LABELS = {"en": "英语", "fr": "法语"}


def clean_meaning(raw: str) -> str:
    """清洗 Trancy 词表 CSV 的 Translation 字段（SPEC.md「词表清洗规则」参考实现原样搬）。

    原始字段形如 `n. 独处 独居; web. 孤独 寂寞 孤寂`——按 `;` 分段，每段
    `词性. 释义1 释义2 …`，末尾常带 web. 段（网络释义，质量最差，含剧名等噪声）。
    """
    segs = [s.strip() for s in raw.split(";") if s.strip()]
    segs = [s for s in segs if not s.lower().startswith("web.")]  # 丢 web 段
    parts = []
    for seg in segs:
        m = re.match(r"^([a-z]+\.)\s*(.+)$", seg)  # 分出词性前缀与释义
        if m:
            pos, defs = m.group(1), m.group(2).split()
            parts.append((pos, defs[:2]))  # 每词性取前 2 个主释义
        else:
            parts.append(("", seg.split()[:2]))
    if not parts:
        return ""
    if len(parts) == 1:  # 单词性省前缀
        return " ".join(parts[0][1])
    return "; ".join((f"{pos} " if pos else "") + " ".join(defs) for pos, defs in parts)


def parse_vocabulary_csv(content: bytes) -> list[dict]:
    """解析 Trancy 词表 CSV（列：Word / Phonetic / Translation / Date）。

    返回 [{"word", "phonetic", "meaning"}]，meaning 已跑过 clean_meaning 清洗。
    Date 字段本身不落库（words 表没有这一列，last_practiced 由调用方在插入时另行赋值）。
    """
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    results = []
    for row in reader:
        word = (row.get("Word") or "").strip()
        if not word:
            continue
        phonetic = (row.get("Phonetic") or "").strip()
        raw_translation = row.get("Translation") or ""
        meaning = clean_meaning(raw_translation)
        results.append({"word": word, "phonetic": phonetic, "meaning": meaning})
    return results


def parse_sentence_csv(content: bytes) -> list[dict]:
    """解析 Trancy 句表 CSV（列：Sentence / Translation / URL / Date）。

    返回 [{"sentence", "translation", "url", "csv_date"}]，不做去重/清洗——句表原文本身
    就是提炼输入，去重在 db 层按 sentence 字面比对（导入时调用方负责）。
    """
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    results = []
    for row in reader:
        sentence = (row.get("Sentence") or "").strip()
        if not sentence:
            continue
        results.append(
            {
                "sentence": sentence,
                "translation": (row.get("Translation") or "").strip(),
                "url": (row.get("URL") or "").strip(),
                "csv_date": (row.get("Date") or "").strip(),
            }
        )
    return results


def _load_triage_template_body() -> str:
    template = _TRIAGE_TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.split("## 模板", 1)[1].split("```", 2)[1].strip()


def render_mining_prompt(sentences: list[str], language: str) -> str:
    """渲染精听分诊+提炼 prompt。language_label 按 language（en/fr）换成中文语言名——
    SPEC 验证时 prompt 里硬编码"英语"，这里泛化成参数，好支持法语句子。"""
    language_label = _LANGUAGE_LABELS.get(language, language)
    numbered = "\n".join(f"{i}. {s}" for i, s in enumerate(sentences, start=1))
    body = _load_triage_template_body()
    body = body.replace("{{language_label}}", language_label)
    body = body.replace("{{sentences}}", numbered)
    return body


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[len("json"):]
    return text.strip()


def run_mining_triage(
    llm: LLMClient, sentences: list[str], language: str
) -> dict[int, dict]:
    """调一次 Groq，把句子按 1-based index 分诊+提炼成 {"words": [...], "collocations": [...]}。

    返回 {index: result}，只包含格式合法的 index——单条结果畸形不拖累整批（调用方按
    index 映射回 mining_sentences 行，缺失的 index 保持 status='queued' 可重试）。
    """
    if not sentences:
        return {}
    prompt = render_mining_prompt(sentences, language)
    raw = llm.chat([Message(role="system", content=prompt)])
    payload = json.loads(_strip_json_fence(raw))

    results: dict[int, dict] = {}
    for item in payload.get("results", []):
        index = item.get("index")
        if not isinstance(index, int) or not (1 <= index <= len(sentences)):
            continue
        words = item.get("words", [])
        collocations = item.get("collocations", [])
        if not isinstance(words, list) or not isinstance(collocations, list):
            continue
        results[index] = {"words": words, "collocations": collocations}
    return results
