"""语音演练手动测试脚本 —— 用麦克风跟角色对话，验证 STT -> turn() -> TTS 的语音回合闭环。
不是自动化测试，是给你自己跑的交互式工具，需要真人声音，pytest 覆盖不到。

依赖（跟主项目分开，只有跑这个脚本才需要装）：
    pip install sounddevice numpy httpx

跑法（先确保 uvicorn 已经在跑，见 README）：
    python scripts/voice_test.py --scenario clinic_fr
"""

import argparse
import io
import json
import wave
from urllib.parse import unquote

import httpx
import numpy as np
import sounddevice as sd

SAMPLE_RATE = 16000
CHANNELS = 1


def record_until_enter() -> bytes:
    print("按回车开始录音...")
    input()
    print("录音中，说完按回车结束...")
    frames: list[np.ndarray] = []

    def callback(indata, frame_count, time_info, status):
        frames.append(indata.copy())

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16", callback=callback):
        input()

    if not frames:
        return b""
    audio = np.concatenate(frames, axis=0)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(audio.tobytes())
    return buffer.getvalue()


def play_wav_bytes(data: bytes) -> None:
    if not data:
        return
    with wave.open(io.BytesIO(data), "rb") as wav_file:
        frames = wav_file.readframes(wav_file.getnframes())
        samplerate = wav_file.getframerate()
    audio = np.frombuffer(frames, dtype="int16")
    sd.play(audio, samplerate)
    sd.wait()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--scenario", default="clinic_fr", choices=["clinic_fr", "interview_en"])
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url, timeout=60.0)

    r = client.post("/sessions", json={"scenario": args.scenario})
    r.raise_for_status()
    body = r.json()
    session_id = body["session_id"]
    print(f"\n[场景] {args.scenario}  [session] {session_id}")
    print(f"[AI 开场] {body['opening_line']}")

    r = client.get(f"/sessions/{session_id}/opening-audio")
    r.raise_for_status()
    play_wav_bytes(r.content)

    print("\n每轮：回车开始录音，再回车结束发送。输入 q 回车 结束演练进入 Debrief。\n")
    while True:
        cmd = input("[回车=开始新一轮 / q=结束演练] ")
        if cmd.strip().lower() == "q":
            break

        audio_bytes = record_until_enter()
        if not audio_bytes:
            print("没录到东西，重来。")
            continue

        files = {"audio": ("turn.wav", audio_bytes, "audio/wav")}
        r = client.post(f"/sessions/{session_id}/voice-messages", files=files)
        r.raise_for_status()
        transcribed = unquote(r.headers.get("X-Transcribed-Text", ""))
        reply_text = unquote(r.headers.get("X-Reply-Text", ""))
        print(f"[你说] {transcribed}")
        print(f"[AI回复] {reply_text}")
        play_wav_bytes(r.content)

    print("\n结束演练，触发 Debrief...")
    r = client.post(f"/sessions/{session_id}/end")
    r.raise_for_status()
    print(json.dumps(r.json(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
