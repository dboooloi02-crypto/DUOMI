import wave
import numpy as np
import sherpa_onnx


MODEL_DIR = (
    "sherpa-onnx-streaming-zipformer-small-ctc-zh-int8-2025-04-01"
)

MODEL_PATH = f"{MODEL_DIR}/model.int8.onnx"
TOKENS_PATH = f"{MODEL_DIR}/tokens.txt"
AUDIO_PATH = "mic_test.wav"


def read_wav(filename):
    with wave.open(filename, "rb") as f:
        sample_rate = f.getframerate()
        num_channels = f.getnchannels()
        sample_width = f.getsampwidth()
        num_frames = f.getnframes()

        if num_channels != 1:
            raise ValueError(f"需要单声道 WAV，当前是 {num_channels} 声道")

        if sample_width != 2:
            raise ValueError(
                f"需要 16-bit PCM，当前 sample_width={sample_width}"
            )

        data = f.readframes(num_frames)

    samples = np.frombuffer(data, dtype=np.int16).astype(np.float32)
    samples /= 32768.0

    return samples, sample_rate


def main():
    print("正在加载中文语音识别模型...")

    recognizer = sherpa_onnx.OnlineRecognizer.from_zipformer2_ctc(
        tokens=TOKENS_PATH,
        model=MODEL_PATH,
        num_threads=2,
        sample_rate=16000,
        feature_dim=80,
        enable_endpoint_detection=True,
        provider="cpu",
    )

    print("模型加载完成")

    samples, sample_rate = read_wav(AUDIO_PATH)

    print(f"音频采样率: {sample_rate} Hz")
    print(f"音频时长: {len(samples) / sample_rate:.2f} 秒")
    print("开始识别...")

    stream = recognizer.create_stream()

    stream.accept_waveform(sample_rate, samples)

    # 在音频末尾补一点静音，帮助流式模型完成最后一句
    tail = np.zeros(int(0.5 * sample_rate), dtype=np.float32)
    stream.accept_waveform(sample_rate, tail)

    stream.input_finished()

    while recognizer.is_ready(stream):
        recognizer.decode_stream(stream)

    result = recognizer.get_result_all(stream)

    print()
    print("=" * 40)
    print("识别结果：")
    print(result.text)
    print("=" * 40)


if __name__ == "__main__":
    main()
