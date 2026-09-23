import subprocess
import numpy as np
import sherpa_onnx


MODEL_DIR = (
    "sherpa-onnx-streaming-zipformer-small-ctc-zh-int8-2025-04-01"
)

MODEL_PATH = f"{MODEL_DIR}/model.int8.onnx"
TOKENS_PATH = f"{MODEL_DIR}/tokens.txt"

AUDIO_DEVICE = "plughw:1,0"
SAMPLE_RATE = 16000

# 每次从麦克风读取约 100ms 音频
CHUNK_SAMPLES = 1600
CHUNK_BYTES = CHUNK_SAMPLES * 2  # S16_LE = 2 bytes/sample


def main():
    print("正在加载中文语音识别模型...")

    recognizer = sherpa_onnx.OnlineRecognizer.from_zipformer2_ctc(
        tokens=TOKENS_PATH,
        model=MODEL_PATH,
        num_threads=2,
        sample_rate=SAMPLE_RATE,
        feature_dim=80,
        enable_endpoint_detection=True,
        provider="cpu",
    )

    stream = recognizer.create_stream()

    print("模型加载完成")
    print(f"麦克风设备：{AUDIO_DEVICE}")
    print()
    print("================================")
    print(" DUOMI Hearing V0.1")
    print("================================")
    print("现在可以直接对 DUOMI 说话。")
    print("按 Ctrl+C 退出。")
    print()

    command = [
        "arecord",
        "-D",
        AUDIO_DEVICE,
        "-t",
        "raw",
        "-f",
        "S16_LE",
        "-r",
        str(SAMPLE_RATE),
        "-c",
        "1",
        "-",
    ]

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )

    last_text = ""

    try:
        while True:
            data = process.stdout.read(CHUNK_BYTES)

            if not data:
                print("麦克风没有返回数据")
                break

            samples = (
                np.frombuffer(data, dtype=np.int16)
                .astype(np.float32)
                / 32768.0
            )

            stream.accept_waveform(SAMPLE_RATE, samples)

            while recognizer.is_ready(stream):
                recognizer.decode_stream(stream)

            result = recognizer.get_result_all(stream)
            text = result.text.strip()

            if text and text != last_text:
                print(f"\r听到：{text}", end="", flush=True)
                last_text = text

            if recognizer.is_endpoint(stream):
                final_text = recognizer.get_result_all(stream).text.strip()

                if final_text:
                    print()
                    print(f"识别完成：{final_text}")
                    print()

                recognizer.reset(stream)
                last_text = ""

    except KeyboardInterrupt:
        print("\n")
        print("停止 Hearing V0.1")

    finally:
        process.terminate()
        process.wait()
        print("麦克风已关闭")


if __name__ == "__main__":
    main()
