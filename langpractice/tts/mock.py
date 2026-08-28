"""离线占位 TTS：还没申请 Azure Speech key 时用，生成一段短促的提示音而不是空音频，
方便肉眼/耳朵确认"确实有音频传回来了"，跟 llm/mock.py 是同一个思路（见 CLAUDE.md 决定记录）。
接上 Azure key 后 app.py 会自动切到 AzureTTSClient，调用方代码不用改。
"""

import io
import math
import struct
import wave

_SAMPLE_RATE = 16000
_DURATION_SECONDS = 0.3
_FREQUENCY_HZ = 440.0  # A4，一声"哔"


def _beep_wav() -> bytes:
    n_samples = int(_SAMPLE_RATE * _DURATION_SECONDS)
    frames = bytearray()
    for i in range(n_samples):
        t = i / _SAMPLE_RATE
        amplitude = 0.3 * math.sin(2 * math.pi * _FREQUENCY_HZ * t)
        frames += struct.pack("<h", int(amplitude * 32767))

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(_SAMPLE_RATE)
        wav_file.writeframes(bytes(frames))
    return buffer.getvalue()


_BEEP = _beep_wav()


class MockTTSClient:
    def synthesize(self, text: str, language: str) -> bytes:
        return _BEEP
