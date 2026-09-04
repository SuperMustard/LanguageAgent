import json
import os
import threading
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, export, mining, personas, scenario_gen
from .config import GROQ_API_KEY, GROQ_MODEL, SUPPORTED_LANGUAGES
from .llm.groq_client import GroqLLMClient
from .models import Collocation, MiningSentence, PhoneticNote, Word

# 语音演练本身（角色扮演 + Debrief + 存库）现在全在 langpractice/voice_bot.py 里，
# 走 Pipecat 全双工 pipeline，是独立进程（默认端口 7860）。这个 app（端口 8000）只管
# 页面、场景列表（含自动生成）、导出、退出——不再自己跑语音，但场景生成是一次性文字
# LLM 调用，跟语音 pipeline 无关，就近放在这个进程里。

app = FastAPI(title="LanguageAgent — 口语演练 Agent（页面 + 场景 + 导出）")


def _build_scenario_llm():
    # 没配 GROQ_API_KEY 时留空——只有 /scenarios/generate 会用到它，不阻塞其它功能。
    if not GROQ_API_KEY:
        return None
    return GroqLLMClient(api_key=GROQ_API_KEY, model=GROQ_MODEL)


_scenario_llm = _build_scenario_llm()

_WEB_DIR = Path(__file__).resolve().parent.parent / "web"
_INDEX_HTML_PATH = _WEB_DIR / "index.html"
_HISTORY_HTML_PATH = _WEB_DIR / "history.html"
_SCENARIO_MANAGER_HTML_PATH = _WEB_DIR / "scenario-manager.html"
_MINING_HTML_PATH = _WEB_DIR / "mining.html"

app.mount("/pipecat", StaticFiles(directory=_WEB_DIR / "pipecat"), name="pipecat-client")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _INDEX_HTML_PATH.read_text(encoding="utf-8")


@app.get("/history", response_class=HTMLResponse)
def history_page() -> str:
    return _HISTORY_HTML_PATH.read_text(encoding="utf-8")


@app.get("/scenario-manager", response_class=HTMLResponse)
def scenario_manager_page() -> str:
    return _SCENARIO_MANAGER_HTML_PATH.read_text(encoding="utf-8")


@app.get("/mining", response_class=HTMLResponse)
def mining_page() -> str:
    return _MINING_HTML_PATH.read_text(encoding="utf-8")


def _delayed_exit() -> None:
    # 留点时间让这次请求的响应先发出去，再终止进程——本地单人开发工具，不用优雅关闭。
    time.sleep(0.3)
    os._exit(0)


@app.post("/shutdown")
def shutdown() -> dict:
    threading.Thread(target=_delayed_exit, daemon=True).start()
    return {"status": "shutting down"}


class GenerateScenarioRequest(BaseModel):
    description: str
    language: str


class TriageSentenceRequest(BaseModel):
    choice: str  # "phonetic" | "language" | "skip"
    word_or_span: str | None = None


class ProcessMiningRequest(BaseModel):
    language: str


@app.get("/scenarios")
def list_scenarios() -> dict[str, str]:
    conn = db.connect()
    try:
        return personas.list_all_scenario_descriptions(conn)
    finally:
        conn.close()


@app.get("/scenarios/full")
def list_scenarios_full() -> list[dict]:
    """给场景管理页用——跟 /scenarios 那个 {key: 描述} 不同，这里是完整字段，
    种子场景和自动生成的场景一视同仁，没有区分标记。"""
    conn = db.connect()
    try:
        cards = db.fetch_all_scenarios(conn)
    finally:
        conn.close()
    return [
        {
            "key": c.key,
            "language": c.language,
            "target_language": c.target_language,
            "role_identity": c.role_identity,
            "emotional_state": c.emotional_state,
            "speaking_style": c.speaking_style,
            "hidden_motivation": c.hidden_motivation,
            "scenario_description": c.scenario_description,
            "difficulty_level": c.difficulty_level,
            "hostility_level": c.hostility_level,
        }
        for c in cards
    ]


@app.delete("/scenarios/{key}")
def delete_scenario(key: str) -> dict:
    conn = db.connect()
    try:
        deleted = db.delete_scenario(conn, key)
    finally:
        conn.close()
    if not deleted:
        raise HTTPException(404, f"scenario {key} not found")
    return {"status": "deleted"}


@app.post("/scenarios/generate")
def generate_scenario(req: GenerateScenarioRequest) -> dict:
    if _scenario_llm is None:
        raise HTTPException(503, "GROQ_API_KEY 未设置，场景生成不可用")
    if req.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, f"unsupported language: {req.language}")
    if not req.description.strip():
        raise HTTPException(400, "场景描述不能为空")

    try:
        card = scenario_gen.generate_persona_card(_scenario_llm, req.description, req.language)
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        raise HTTPException(502, f"场景生成失败：{e}") from e

    conn = db.connect()
    try:
        db.insert_scenario(conn, card)
    finally:
        conn.close()

    return {"key": card.key, "description": card.scenario_description}


@app.delete("/expressions/{expression_id}")
def delete_expression(expression_id: int) -> dict:
    """删一条病句诊断——常见场景是语音识别错了，诊断其实是针对错误转写文本的假病句。"""
    conn = db.connect()
    try:
        deleted = db.delete_expression(conn, expression_id)
    finally:
        conn.close()
    if not deleted:
        raise HTTPException(404, f"expression {expression_id} not found")
    return {"status": "deleted"}


@app.delete("/words/{word_id}")
def delete_word(word_id: int) -> dict:
    conn = db.connect()
    try:
        deleted = db.delete_word(conn, word_id)
    finally:
        conn.close()
    if not deleted:
        raise HTTPException(404, f"word {word_id} not found")
    return {"status": "deleted"}


@app.delete("/pro_phrases/{phrase_id}")
def delete_pro_phrase(phrase_id: int) -> dict:
    conn = db.connect()
    try:
        deleted = db.delete_pro_phrase(conn, phrase_id)
    finally:
        conn.close()
    if not deleted:
        raise HTTPException(404, f"pro_phrase {phrase_id} not found")
    return {"status": "deleted"}


@app.delete("/collocations/{collocation_id}")
def delete_collocation(collocation_id: int) -> dict:
    conn = db.connect()
    try:
        deleted = db.delete_collocation(conn, collocation_id)
    finally:
        conn.close()
    if not deleted:
        raise HTTPException(404, f"collocation {collocation_id} not found")
    return {"status": "deleted"}


@app.delete("/phonetic_notes/{note_id}")
def delete_phonetic_note(note_id: int) -> dict:
    conn = db.connect()
    try:
        deleted = db.delete_phonetic_note(conn, note_id)
    finally:
        conn.close()
    if not deleted:
        raise HTTPException(404, f"phonetic_note {note_id} not found")
    return {"status": "deleted"}


@app.post("/mining/words/import")
async def import_mining_words(
    language: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    """模块 4 切片 A：Trancy 词表 CSV（Word/Phonetic/Translation/Date）极简入口——
    点词收藏本身已经是"我不认识这个词"的判断，不经 Groq，清洗后直接进 words 表。"""
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, f"unsupported language: {language}")

    content = await file.read()
    try:
        rows = mining.parse_vocabulary_csv(content)
    except UnicodeDecodeError as e:
        raise HTTPException(400, f"CSV 解码失败：{e}") from e

    conn = db.connect()
    try:
        existing = {w.word.strip().lower() for w in db.fetch_words(conn, language)}
        seen_in_batch: set[str] = set()
        to_insert: list[Word] = []
        skipped_duplicate = 0
        for row in rows:
            key = row["word"].strip().lower()
            if key in existing or key in seen_in_batch:
                skipped_duplicate += 1
                continue
            seen_in_batch.add(key)
            to_insert.append(
                Word(
                    word=row["word"],
                    meaning=row["meaning"],
                    language=language,
                    phonetic=row["phonetic"],
                )
            )
        db.insert_words(conn, to_insert)
    finally:
        conn.close()

    return {
        "total_rows": len(rows),
        "imported": len(to_insert),
        "skipped_duplicate": skipped_duplicate,
    }


@app.post("/mining/sentences/import")
async def import_mining_sentences(
    language: str = Form(...),
    file: UploadFile = File(...),
) -> dict:
    """模块 4 切片 B 第 0 步：Trancy 句表 CSV（Sentence/Translation/URL/Date）导入去重池
    （mining_sentences 表），等人工三选一（/mining/sentences/{id}/triage）。"""
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, f"unsupported language: {language}")

    content = await file.read()
    try:
        rows = mining.parse_sentence_csv(content)
    except UnicodeDecodeError as e:
        raise HTTPException(400, f"CSV 解码失败：{e}") from e

    conn = db.connect()
    try:
        seen_in_batch: set[str] = set()
        to_insert: list[MiningSentence] = []
        skipped_duplicate = 0
        for row in rows:
            sentence = row["sentence"]
            if sentence in seen_in_batch or db.mining_sentence_exists(conn, language, sentence):
                skipped_duplicate += 1
                continue
            seen_in_batch.add(sentence)
            to_insert.append(
                MiningSentence(
                    sentence=sentence,
                    translation=row["translation"],
                    url=row["url"],
                    csv_date=row["csv_date"],
                    language=language,
                )
            )
        db.insert_mining_sentences(conn, to_insert)
    finally:
        conn.close()

    return {
        "total_rows": len(rows),
        "imported": len(to_insert),
        "skipped_duplicate": skipped_duplicate,
    }


@app.get("/mining/sentences")
def list_mining_sentences(language: str, status: str | None = None) -> list[dict]:
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, f"unsupported language: {language}")
    conn = db.connect()
    try:
        rows = db.fetch_mining_sentences(conn, language, status)
    finally:
        conn.close()
    return [
        {
            "id": r.id,
            "sentence": r.sentence,
            "translation": r.translation,
            "url": r.url,
            "csv_date": r.csv_date,
            "status": r.status,
        }
        for r in rows
    ]


@app.post("/mining/sentences/{sentence_id}/triage")
def triage_mining_sentence(sentence_id: int, req: TriageSentenceRequest) -> dict:
    """人工三选一：语音（不进 Groq，直接写 phonetic_notes）/ 语言（排进 Groq 批量队列）
    / 跳过（标记已处理，不入任何表）。"""
    conn = db.connect()
    try:
        row = db.fetch_mining_sentence_by_id(conn, sentence_id)
        if row is None:
            raise HTTPException(404, f"mining sentence {sentence_id} not found")

        if req.choice == "skip":
            db.update_mining_sentence_status(conn, sentence_id, "skipped")
        elif req.choice == "phonetic":
            if not req.word_or_span or not req.word_or_span.strip():
                raise HTTPException(400, "选“语音”必须填 word_or_span（哪里没听清）")
            db.insert_phonetic_notes(
                conn,
                [
                    PhoneticNote(
                        sentence=row.sentence,
                        word_or_span=req.word_or_span.strip(),
                        source=row.url,
                        date=row.csv_date,
                        language=row.language,
                    )
                ],
            )
            db.update_mining_sentence_status(conn, sentence_id, "done")
        elif req.choice == "language":
            db.update_mining_sentence_status(conn, sentence_id, "queued")
        else:
            raise HTTPException(400, f"unknown choice: {req.choice}")
    finally:
        conn.close()
    return {"status": "ok"}


@app.post("/mining/process")
def process_mining_queue(req: ProcessMiningRequest) -> dict:
    """模块 4 切片 B 第 2/3 步：批量处理所有 status='queued' 的句子——一次 Groq 调用
    分诊+提炼，产出的生词/语块去重后分流进 words/collocations，处理成功的行置 done，
    解析失败的行留在 queued（可下次重新提交重试）。"""
    if req.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, f"unsupported language: {req.language}")
    if _scenario_llm is None:
        raise HTTPException(503, "GROQ_API_KEY 未设置，精听提炼不可用")

    conn = db.connect()
    try:
        queued = db.fetch_mining_sentences(conn, req.language, "queued")
        if not queued:
            return {"processed": 0, "words_added": 0, "collocations_added": 0, "failed_ids": []}

        results = mining.run_mining_triage(
            _scenario_llm, [r.sentence for r in queued], req.language
        )

        existing_words = {w.word.strip().lower() for w in db.fetch_words(conn, req.language)}
        existing_collocations = {
            c.phrase.strip().lower() for c in db.fetch_collocations(conn, req.language)
        }

        words_to_insert: list[Word] = []
        collocations_to_insert: list[Collocation] = []
        processed = 0
        failed_ids: list[int] = []

        for position, row in enumerate(queued, start=1):
            result = results.get(position)
            if result is None:
                failed_ids.append(row.id)
                continue

            for w in result["words"]:
                word_text = (w.get("word") or "").strip()
                key = word_text.lower()
                if not word_text or key in existing_words:
                    continue
                existing_words.add(key)
                words_to_insert.append(
                    Word(word=word_text, meaning=w.get("meaning", "") or "", language=req.language)
                )

            for c in result["collocations"]:
                phrase_text = (c.get("phrase") or "").strip()
                key = phrase_text.lower()
                if not phrase_text or key in existing_collocations:
                    continue
                existing_collocations.add(key)
                collocations_to_insert.append(
                    Collocation(
                        phrase=phrase_text,
                        meaning=c.get("meaning", "") or "",
                        note=c.get("note", "") or "",
                        language=req.language,
                    )
                )

            db.update_mining_sentence_status(conn, row.id, "done")
            processed += 1

        db.insert_words(conn, words_to_insert)
        db.insert_collocations(conn, collocations_to_insert)
    finally:
        conn.close()

    return {
        "processed": processed,
        "words_added": len(words_to_insert),
        "collocations_added": len(collocations_to_insert),
        "failed_ids": failed_ids,
    }


@app.get("/records/{language}")
def list_records(language: str) -> dict:
    """给历史记录管理页用——跟 /export 不同，这里带 id/mastery/last_practiced，
    因为要能单条删除、看掌握度，不是给 langhelper 吃的干净格式。"""
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, f"unsupported language: {language}")

    conn = db.connect()
    try:
        expressions = db.fetch_expressions(conn, language)
        words = db.fetch_words(conn, language)
        pro_phrases = db.fetch_pro_phrases(conn, language)
        collocations = db.fetch_collocations(conn, language)
        phonetic_notes = db.fetch_phonetic_notes(conn, language)
    finally:
        conn.close()

    return {
        "expressions": [
            {
                "id": e.id,
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
        "words": [
            {
                "id": w.id,
                "word": w.word,
                "meaning": w.meaning,
                "phonetic": w.phonetic,
                "mastery": w.mastery,
                "last_practiced": w.last_practiced,
            }
            for w in words
        ],
        "pro_phrases": [
            {
                "id": p.id,
                "scenario_type": p.scenario_type,
                "phrase": p.phrase,
                "meaning": p.meaning,
                "dimension": p.dimension,
                "usage_note": p.usage_note,
                "mastery": p.mastery,
                "last_practiced": p.last_practiced,
            }
            for p in pro_phrases
        ],
        "collocations": [
            {
                "id": c.id,
                "phrase": c.phrase,
                "meaning": c.meaning,
                "note": c.note,
                "mastery": c.mastery,
                "last_practiced": c.last_practiced,
            }
            for c in collocations
        ],
        "phonetic_notes": [
            {
                "id": n.id,
                "sentence": n.sentence,
                "word_or_span": n.word_or_span,
                "source": n.source,
                "date": n.date,
            }
            for n in phonetic_notes
        ],
    }


@app.get("/export/{language}")
def export_language(language: str) -> dict:
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, f"unsupported language: {language}")

    conn = db.connect()
    try:
        expressions = db.fetch_expressions(conn, language)
        words = db.fetch_words(conn, language)
        pro_phrases = db.fetch_pro_phrases(conn, language)
        collocations = db.fetch_collocations(conn, language)
    finally:
        conn.close()

    sentences_path, words_path, phrases_path = export.write_export_files(
        language, expressions, words, pro_phrases, collocations
    )
    return {
        "sentences_file": str(sentences_path),
        "words_file": str(words_path),
        "phrases_file": str(phrases_path),
        "sentences_json": export.expressions_to_json(expressions),
        "words_txt": export.words_to_txt(words),
        "phrases_json": export.merge_phrase_cards(pro_phrases, collocations),
    }
