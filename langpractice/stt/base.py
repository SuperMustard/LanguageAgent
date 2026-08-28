from typing import Protocol


class STTClient(Protocol):
    """语音转文字接口。传入音频字节和语言码（"en"/"fr"），返回识别出的文字。"""

    def transcribe(self, audio_bytes: bytes, filename: str, language: str) -> str:
        ...
