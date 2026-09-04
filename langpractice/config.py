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

# 难缠程度旋钮（模块 2.5 配套，见 SPEC"难缠客户练习与配置分层"）：只有这四档，
# 前端下拉框和场景生成都从这个常量取值，不额外做成 .env 可配置——档位是产品设计，
# 不是运维参数。红线（满级也不能突破的底线）是写死在 persona_template.md 里的固定文字，
# 不受这个常量影响。
HOSTILITY_LEVELS = ("温和", "中等", "难缠", "极难缠")
DEFAULT_HOSTILITY_LEVEL = "中等"

# 口语侧诱导（induction.py）配额，见 SPEC"配置项"：INDUCTION_MAX_TARGETS 是一次诱导
# 注入的目标总数上限（生词+病句+专业话术混合池，原来就是这个值，只是之前硬编码在
# retrieve_induction_targets 的默认参数里）；INDUCTION_MIN_PHRASES 是其中保底来自
# pro_phrases 的条数——防止话术被生词/病句挤掉（专业话术是使用者最想练的）。
INDUCTION_MAX_TARGETS = int(os.getenv("INDUCTION_MAX_TARGETS", "2"))
INDUCTION_MIN_PHRASES = int(os.getenv("INDUCTION_MIN_PHRASES", "1"))

# collocation（模块 4 精听提炼产出）的常规配比保底——默认 0（不像 INDUCTION_MIN_PHRASES
# 默认 1），因为 INDUCTION_MAX_TARGETS 默认只有 2，两个保底加起来会直接吃满预算、
# 挤掉生词/病句的常规诱导。默认让 collocation 走跟生词/病句一样的混合池排序竞争；
# 真攒了数据觉得被淹没了，在 .env 里调高——这跟其它诱导配额一致的"先跑通、按真实数据调"
# 惯例。注意：当天新学的 collocation 走「今日通道」（见 retrieve_today_collocations），
# 不占这个配额，这里只影响往期 collocation 的常规采样。
INDUCTION_MIN_COLLOCATIONS = int(os.getenv("INDUCTION_MIN_COLLOCATIONS", "0"))

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
