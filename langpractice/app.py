import os
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import db, export
from .config import SUPPORTED_LANGUAGES
from .personas import BUILTIN_SCENARIOS

# 语音演练本身（角色扮演 + Debrief + 存库）现在全在 langpractice/voice_bot.py 里，
# 走 Pipecat 全双工 pipeline，是独立进程（默认端口 7860）。这个 app（端口 8000）只管
# 页面、场景列表、导出、退出——不再自己跑 LLM/STT/TTS。

app = FastAPI(title="LanguageAgent — 口语演练 Agent（页面 + 场景 + 导出）")

_WEB_DIR = Path(__file__).resolve().parent.parent / "web"
_INDEX_HTML_PATH = _WEB_DIR / "index.html"
_HISTORY_HTML_PATH = _WEB_DIR / "history.html"

app.mount("/pipecat", StaticFiles(directory=_WEB_DIR / "pipecat"), name="pipecat-client")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return _INDEX_HTML_PATH.read_text(encoding="utf-8")


@app.get("/history", response_class=HTMLResponse)
def history_page() -> str:
    return _HISTORY_HTML_PATH.read_text(encoding="utf-8")


def _delayed_exit() -> None:
    # 留点时间让这次请求的响应先发出去，再终止进程——本地单人开发工具，不用优雅关闭。
    time.sleep(0.3)
    os._exit(0)


@app.post("/shutdown")
def shutdown() -> dict:
    threading.Thread(target=_delayed_exit, daemon=True).start()
    return {"status": "shutting down"}


@app.get("/scenarios")
def list_scenarios() -> dict[str, str]:
    return {key: card.scenario_description for key, card in BUILTIN_SCENARIOS.items()}


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
    }


@app.get("/export/{language}")
def export_language(language: str) -> dict:
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(400, f"unsupported language: {language}")

    conn = db.connect()
    try:
        expressions = db.fetch_expressions(conn, language)
        words = db.fetch_words(conn, language)
    finally:
        conn.close()

    sentences_path, words_path = export.write_export_files(language, expressions, words)
    return {
        "sentences_file": str(sentences_path),
        "words_file": str(words_path),
        "sentences_json": export.expressions_to_json(expressions),
        "words_txt": export.words_to_txt(words),
    }
