from typing import Protocol


class TTSClient(Protocol):
    """文字转语音接口。传入文字和语言码（"en"/"fr"），返回 wav 音频字节。"""

    def synthesize(self, text: str, language: str) -> bytes:
        ...
