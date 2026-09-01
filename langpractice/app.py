import json
import os
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, export, personas, scenario_gen
from .config import GROQ_API_KEY, GROQ_MODEL, SUPPORTED_LANGUAGES
from .llm.groq_client import GroqLLMClient

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
    finally:
        conn.close()

    sentences_path, words_path, phrases_path = export.write_export_files(
        language, expressions, words, pro_phrases
    )
    return {
        "sentences_file": str(sentences_path),
        "words_file": str(words_path),
        "phrases_file": str(phrases_path),
        "sentences_json": export.expressions_to_json(expressions),
        "words_txt": export.words_to_txt(words),
        "phrases_json": export.pro_phrases_to_json(pro_phrases),
    }
