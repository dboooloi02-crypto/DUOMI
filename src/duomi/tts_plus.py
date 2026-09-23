import os
import subprocess


PIPER_BIN = os.path.expanduser(
    "~/duomi/.venv_piper_plus/bin/piper"
)

VOICE_MODEL = os.path.expanduser(
    "~/duomi/piper-plus-model/tsukuyomi-chan-6lang-fp16.onnx"
)

CONFIG_FILE = os.path.expanduser(
    "~/duomi/piper-plus-model/config.json"
)

OUTPUT_FILE = os.path.expanduser(
    "~/duomi/piper-plus-model/duomi_plus_speech.wav"
)


def speak_plus(text):
    if not text:
        return

    command = [
        PIPER_BIN,
        "-m",
        VOICE_MODEL,
        "-c",
        CONFIG_FILE,
        "-f",
        OUTPUT_FILE,
        "--length-scale",
        "1.7",
        "--noise-scale",
        "0.5",
        "--noise-w",
        "0.4",
        "--",
        text,
    ]

    try:
        # 隐藏 Piper 的普通运行日志和底层警告
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # 真正失败时才显示错误
        if result.returncode != 0:
            print("Piper Plus 语音合成失败：")
            print(result.stderr.strip())
            return

        # 隐藏 aplay 的播放信息
        play_result = subprocess.run(
            ["aplay", OUTPUT_FILE],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # 播放真正失败时显示错误
        if play_result.returncode != 0:
            print("音频播放失败：")
            print(play_result.stderr.strip())

    except Exception as e:
        print(f"TTS 系统错误：{e}")
