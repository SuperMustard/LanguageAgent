"""SPEC 指定的 STT：Groq Whisper。复用同一个 GROQ_API_KEY，不需要额外申请。"""

from groq import Groq


class GroqWhisperSTT:
    def __init__(self, api_key: str, model: str = "whisper-large-v3") -> None:
        if not api_key:
            raise RuntimeError("GROQ_API_KEY 未设置，无法使用 Groq Whisper STT")
        self._client = Groq(api_key=api_key)
        self._model = model

    def transcribe(self, audio_bytes: bytes, filename: str, language: str) -> str:
        result = self._client.audio.transcriptions.create(
            model=self._model,
            file=(filename, audio_bytes),
            language=language,
            response_format="text",
        )
        # response_format="text" 时 SDK 直接返回字符串；保险起见两种都处理
        return result if isinstance(result, str) else result.text
