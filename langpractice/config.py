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

# voice_bot.py（Pipecat 语音 pipeline）必需，没配就连不上。
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip() or None
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3")

AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "").strip() or None
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "").strip() or None

# VAD（voice_bot.py 的断句/打断判断）调参，改 .env 不用改代码。含义见 Pipecat 的
# VADParams：confidence 语音置信度阈值，start_secs 判定"开始说话"要等多久，
# stop_secs 判定"说完了"要等多久静音（觉得被切太快就调大这个），min_volume 音量阈值。
VAD_CONFIDENCE = float(os.getenv("VAD_CONFIDENCE", "0.7"))
VAD_START_SECS = float(os.getenv("VAD_START_SECS", "0.2"))
VAD_STOP_SECS = float(os.getenv("VAD_STOP_SECS", "0.8"))
VAD_MIN_VOLUME = float(os.getenv("VAD_MIN_VOLUME", "0.6"))
