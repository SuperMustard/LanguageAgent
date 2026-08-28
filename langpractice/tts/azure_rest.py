"""Azure Speech TTS，走 REST API（不用 azure-cognitiveservices-speech 那个原生 SDK，
省一个平台相关的重依赖，httpx 已经在项目里）。
"""

from xml.sax.saxutils import escape

import httpx

_VOICE_BY_LANGUAGE = {
    "en": ("en-US", "en-US-JennyNeural"),
    "fr": ("fr-FR", "fr-FR-DeniseNeural"),
}


class AzureTTSClient:
    def __init__(self, api_key: str, region: str) -> None:
        if not api_key or not region:
            raise RuntimeError(
                "AZURE_SPEECH_KEY / AZURE_SPEECH_REGION 未设置：在 .env 里填入（见 .env.example）"
            )
        self._api_key = api_key
        self._endpoint = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"

    def synthesize(self, text: str, language: str) -> bytes:
        locale, voice = _VOICE_BY_LANGUAGE.get(language, _VOICE_BY_LANGUAGE["en"])
        ssml = (
            f"<speak version='1.0' xml:lang='{locale}'>"
            f"<voice xml:lang='{locale}' name='{voice}'>{escape(text)}</voice>"
            f"</speak>"
        )
        response = httpx.post(
            self._endpoint,
            content=ssml.encode("utf-8"),
            headers={
                "Ocp-Apim-Subscription-Key": self._api_key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "riff-16khz-16bit-mono-pcm",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.content
