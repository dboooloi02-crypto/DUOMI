# DUOMI Hardware

All values below are taken from the source, not invented.

## Compute

- Raspberry Pi (the environment this was developed on runs Python 3.13)
- USB camera on `/dev/video0`
- USB or HAT audio device at ALSA `plughw:1,0`

## Motor wiring (`motor_controller.py`)

Two DC gear motors driven through an H-bridge, exposed as `gpiozero.DigitalOutputDevice`:

| Wheel | Enable | IN1 | IN2 |
|-------|:------:|:---:|:---:|
| Left  | GPIO23 | GPIO17 | GPIO18 |
| Right | GPIO24 | GPIO27 | GPIO22 |

Behaviour:

- `forward()` / `backward()` / `left_turn()` / `right_turn()` / `stop()`
- `execute(action, duration)` clamps duration to `0 … MAX_ACTION_DURATION` (3.0 s)
  and **always stops in a `finally` block**

> The 3-second clamp and the guaranteed stop exist so a stuck command cannot drive
> the robot indefinitely. Keep them if you modify this file.

## Audio

| Item | Value |
|------|-------|
| Capture device | `plughw:1,0` |
| Sample rate | 16000 Hz |
| Chunk | 1600 samples (3200 bytes) |
| Capture command | `arecord -D plughw:1,0 -t raw -f S16_LE -r 16000 -c 1 -` |
| Playback command | `aplay <file>` |

## Camera

Capture command used by `vision_system.py`:

```bash
v4l2-ctl -d /dev/video0 --stream-mmap --stream-count=1 --stream-to=<output>.jpg
```

Frames default to `vision_frames/frame_<timestamp>.jpg`.

## Model files (NOT in this repository)

These are large binaries. Download them yourself and place them next to the code:

| Path used by code | Purpose |
|-------------------|---------|
| `sherpa-onnx-streaming-zipformer-small-ctc-zh-int8-2025-04-01/` | Chinese streaming ASR (model.int8.onnx + tokens.txt) |
| `voices/*.onnx` | Piper voice models (`tts.py`, e.g. `zh_CN-xiao_ya-medium.onnx`) |
| `piper-plus-model/tsukuyomi-chan-6lang-fp16.onnx` + `config.json` | Piper-Plus voice (`tts_plus.py`) |
| `.venv_piper_plus/bin/piper` | Piper-Plus binary |
| `bert-base-chinese/`, `g2pW/` | Chinese grapheme-to-phoneme resources |

## System packages (not installable via pip)

```bash
sudo apt install v4l-utils alsa-utils   # v4l2-ctl, arecord, aplay
```

## Running the body standalone

```bash
cd src/duomi
python motor_controller.py
```

W = forward, S = backward, A = left, D = right, Space = stop, Q = quit.
Each movement lasts 0.3 s.
