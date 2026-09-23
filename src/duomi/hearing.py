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

CHUNK_SAMPLES = 1600
CHUNK_BYTES = CHUNK_SAMPLES * 2


class Hearing:
    """DUOMI Hearing V0.1"""

    def __init__(self):
        print("正在加载 DUOMI 听觉系统...")

        self.recognizer = (
            sherpa_onnx.OnlineRecognizer.from_zipformer2_ctc(
                tokens=TOKENS_PATH,
                model=MODEL_PATH,
                num_threads=2,
                sample_rate=SAMPLE_RATE,
                feature_dim=80,
                enable_endpoint_detection=True,
                provider="cpu",
            )
        )

        print("DUOMI 听觉系统已加载")

    def listen_once(self):
        """
        监听一次用户发言。
        每次重新启动 arecord，避免上一轮音频残留。
        """

        stream = self.recognizer.create_stream()

        process = subprocess.Popen(
            [
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
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )

        started = False

        try:
            while True:
                data = process.stdout.read(CHUNK_BYTES)

                if not data:
                    return ""

                samples = (
                    np.frombuffer(
                        data,
                        dtype=np.int16,
                    )
                    .astype(np.float32)
                    / 32768.0
                )

                stream.accept_waveform(
                    SAMPLE_RATE,
                    samples,
                )

                while self.recognizer.is_ready(stream):
                    self.recognizer.decode_stream(stream)

                text = (
                    self.recognizer
                    .get_result_all(stream)
                    .text
                    .strip()
                )

                if text:
                    started = True

                if started and self.recognizer.is_endpoint(stream):
                    final_text = (
                        self.recognizer
                        .get_result_all(stream)
                        .text
                        .strip()
                    )

                    return final_text

        finally:
            process.terminate()

            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()

    def close(self):
        print("DUOMI 听觉系统已关闭")
