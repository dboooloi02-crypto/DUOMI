import os
import subprocess

from pronunciation import apply_pronunciation

VOICE_MODEL = os.path.expanduser(
    "~/duomi/voices/zh_CN-xiao_ya-medium.onnx"
)

OUTPUT_FILE = os.path.expanduser(
    "~/duomi/voices/duomi_speech.wav"
)


def speak(text):
    if not text:
        return

    # TTS 发音词典
    speech_text = apply_pronunciation(text)

    command = [
        "python",
        "-m",
        "piper",
        "-m",
        VOICE_MODEL,
        "-f",
        OUTPUT_FILE,
        "--length_scale",
        "1.0",
        "--noise_w",
        "0.4",
        "--sentence_silence",
        "0.08",
        "--",
        speech_text
    ]

    try:
        subprocess.run(
            command,
            check=True
        )

        subprocess.run(
            ["aplay", OUTPUT_FILE],
            check=True
        )

    except subprocess.CalledProcessError as e:
        print(f"TTS播放失败：{e}")
