import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DB_PATH = Path(os.getenv(
    "LANGPRACTICE_DB",
    Path.home() / ".local/share/languageagent/agent.db",
))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

EXPORT_DIR = Path(os.getenv(
    "LANGPRACTICE_EXPORT_DIR",
    DB_PATH.parent / "exports",
))

SUPPORTED_LANGUAGES = ("en", "fr")

# 没配 GROQ_API_KEY 时 app.py 会自动退回 MockLLMClient，不报错、不阻塞开发。
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip() or None
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3")

# 没配 AZURE_SPEECH_KEY 时 app.py 会自动退回 MockTTSClient（占位提示音）。
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "").strip() or None
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "").strip() or None
