# DUOMI

**A Robot That Grows With You.**

[English](#english) · [中文](#%E4%B8%AD%E6%96%87)

---

## What DUOMI is

DUOMI is an embodied AI personal robot built from scratch.

The goal is not to make AI answer questions, but to let it gradually have:

- a continuous identity
- long-term memory
- internal state
- a relationship model
- autonomous action
- a physical body

### About the LLM

**The LLM is one of DUOMI's cognitive engines, not DUOMI's identity.**

DUOMI currently uses an LLM (DeepSeek, through an OpenAI-compatible SDK) for
interpretation, planning, reflection and vision reasoning. The system is designed so
that the LLM can be replaced — the robot's identity, memory and internal state live in
DUOMI's own modules, not inside any model.

---

## Implemented

Everything below exists as working code in this repository.

### Body

- Raspberry Pi
- Two-wheel differential drive
- L298N motor driver
- GPIO motor control
- Forward
- Backward
- Left
- Right
- Stop

> Implemented in `src/duomi/motor_controller.py`. Every movement is clamped to
> `MAX_ACTION_DURATION` (3.0 s) and always stops in a `finally` block, so a stuck
> command cannot drive the robot indefinitely.

### Hearing

- USB microphone
- ALSA audio capture
- 16 kHz mono audio
- sherpa-onnx streaming Chinese ASR
- Endpoint detection

> `src/duomi/hearing.py` — `arecord -D plughw:1,0 -t raw -f S16_LE -r 16000 -c 1 -`,
> streamed into a sherpa-onnx zipformer CTC recogniser with endpoint detection enabled.

### Speech / TTS

- Local Chinese speech synthesis
- Piper / Piper-Plus integration

> `src/duomi/tts.py` (Piper), `tts_plus.py` (Piper-Plus), `pronunciation.py`
> (pronunciation dictionary applied before synthesis). Playback via `aplay`.
> Synthesis runs locally — no cloud TTS.

### Vision

- Camera input
- V4L2 camera capture
- Vision reasoning
- Visual observation records
- Visual comparison
- Explicit uncertainty handling

> `src/duomi/vision_system.py` captures a frame with **`v4l2-ctl`**
> (`v4l2-ctl -d /dev/video0 --stream-mmap --stream-count=1 --stream-to=...`), then sends
> it to a vision model. Observed scenes and objects carry explicit uncertainty fields;
> `vision_compare.py` records `cannot_determine` cases and a comparison reliability score
> rather than guessing.

### Agent

- Action Planner
- Memory Manager
- Emotion / internal state mechanisms
- Learning
- Reflection
- Imagination
- Web tools
- Limited autonomous internal processes

> The autonomous part is deliberately described as **limited**: DUOMI can trigger some
> internal processes (imagination, reflection) on its own, but it does not yet execute
> goal-driven tasks by itself.

### Memory

- Memory IDs
- Importance
- Status
- Related memories
- Retrieval
- Updating
- Archiving
- Association / linking mechanisms

> `src/duomi/memory_manager.py` exposes `make_memory_id`, `add_memory`,
> `update_memory`, `archive_memory`, `link_memories`, `get_related_memories` and
> `retrieve_memories`. Association is expressed through a `related_to` list of memory IDs
> and is filled in by the memory-organisation step in `main.py`, which is instructed to
> link only on clear relationships.

---

## In Progress

- Long-term memory consolidation
- Better memory retrieval
- Multimodal memory integration
- Self Model
- Belief System
- Goal System
- More reliable autonomous behavior
- Emotion / state → behavior coupling
- Imagination → memory integration
- More robust planning

### Self Model — early prototype / partially implemented

What exists today:

- self-observation (camera observations written to `self_observation_memory`)
- reflection (`reflection_system.py`)
- autobiographical / identity-related memory mechanisms (important memory, learning history)

What does **not** exist: a complete, standalone Self Model.

### Relationship — relationship-related state / early prototype

What exists today:

- `trust`
- `closeness`
- relationship-related emotional state

What does **not** exist: a complete, standalone Relationship Model.

### Agency — limited autonomy / early prototype

What exists today:

- DUOMI can autonomously trigger some internal processes such as imagination and reflection

What does **not** exist: real goal-driven autonomous task execution.

---

## Planned

- Belief System
- Goal System
- Scheduler
- Goal-driven autonomy
- Wheel encoders
- IMU
- Odometry
- Battery monitoring
- Obstacle avoidance
- Navigation
- SLAM
- ROS 2 integration
- Unified multimodal memory
- Robotic arm
- Gripper
- Tactile sensing
- Physical manipulation
- More autonomous learning
- Future humanoid body

> **ROS 2 is not implemented.** There is no ROS 2 code in this repository — no `rclpy`,
> no `package.xml`, no colcon build. The body layer drives GPIO directly.
> Do not read "ROS 2 integration" above as current support.

---

## Architecture

```
Perception            hearing.py · vision_system.py
      ↓
Interpretation        action_planner.py · vision_system.py (LLM)
      ↓
Memory Retrieval      memory_manager.py (retrieve_memories)
      ↓
Internal State        emotion_system.py
      ↓
Self Model            — partial (self-observation · reflection · identity memory)
      ↓
Belief                — not implemented
      ↓
Goal                  — not implemented
      ↓
Prediction            imagination_system.py
      ↓
Planning              action_planner.py
      ↓
Safety / Epistemic Check   — partial (motor duration clamp; explicit uncertainty in vision)
      ↓
Decision              main.py
      ↓
Action                motor_controller.py · tts_plus.py
      ↓
Observation           vision_memory.py · vision_compare.py
      ↓
Experience            memory_manager.py
      ↓
Learning / Growth     learning_system.py · reflection_system.py
```

**Several stages in this pipeline are still under development.** The two stages marked
*not implemented* (Belief, Goal) and the two marked *partial* (Self Model,
Safety / Epistemic Check) are honest gaps, not documentation shortcuts.

---

## Repository layout

```
duomi/
├── README.md
├── .gitignore
├── .env.example          # copy to .env and fill in (never commit .env)
├── requirements.txt
├── src/duomi/            # core modules
├── docs/
│   ├── architecture/     # cognitive loop and subsystem mapping
│   ├── hardware/         # GPIO wiring, audio, camera, required model files
│   └── build-log/        # version timeline
├── examples/             # subsystem driver scripts
└── media/                # intentionally empty
```

---

## Quick Start

```bash
cd src/duomi
export DEEPSEEK_API_KEY="..."
python main.py
```

Or copy `.env.example` to `.env` and fill in the key (`.env` is git-ignored):

```bash
cp .env.example .env
```

DUOMI is at an early engineering stage and some modules use **local flat imports**
(`from memory_manager import ...`). That is why you run it from inside `src/duomi` —
that directory needs to be `sys.path[0]`. No package refactor has been done, because not
breaking working code matters more than a conventional layout.

See `docs/hardware/` for GPIO wiring, audio device and camera setup, and for the list of
model files that must be downloaded separately.

---

## Privacy and secrets

- All API keys are read from the environment (`DEEPSEEK_API_KEY`). **No key is hardcoded.**
- Runtime data — memory, emotion, learning and vision observation logs — is **not in this
  repository** and is excluded by `.gitignore`. Camera observations contain real scenes
  and people and are private.
- Large third-party models (ONNX, voice models, ASR models) are **not** distributed here.

---

## License

No open-source license has been added yet.
All rights reserved.

---

## Development Status

DUOMI is an active experimental embodied AI project.

The repository intentionally distinguishes between:

- Implemented
- In Progress
- Planned

The goal is to document real development progress rather than present future research
ideas as completed capabilities.

---
---

## 中文

### DUOMI 是什么

DUOMI 是一个从零开始构建的 embodied AI personal robot。

目标不是让 AI 回答问题，而是让它逐步拥有：

- 持续身份
- 长期记忆
- 内部状态
- 关系模型
- 自主行动
- 实体身体

### 关于 LLM

**LLM 是 DUOMI 的认知引擎之一，而不是 DUOMI 本身的身份。**

DUOMI 目前使用一个 LLM（DeepSeek，经 OpenAI 兼容 SDK）来完成理解、规划、反思与视觉推理。
系统设计上允许未来替换不同的 LLM —— DUOMI 的身份、记忆与内部状态存在于它自己的模块里，
不在任何模型内部。

### Implemented（已完成）

以下每一项都是仓库里真实可运行的代码。

**Body** — Raspberry Pi / 两轮差速 / L298N 驱动 / GPIO 电机控制 / 前进 / 后退 / 左转 / 右转 / 停止

**Hearing** — USB 麦克风 / ALSA 采集 / 16 kHz 单声道 / sherpa-onnx 中文流式 ASR / 端点检测

**Speech / TTS** — 本地中文语音合成 / Piper 与 Piper-Plus 集成

**Vision** — 摄像头输入 / V4L2 抓帧 / 视觉推理 / 视觉观察记录 / 视觉对比 / 显式不确定性处理
（抓帧实际使用 **`v4l2-ctl`**，不是 `libcamera-still`）

**Agent** — Action Planner / Memory Manager / 情绪与内部状态机制 / Learning / Reflection /
Imagination / Web tools / 有限的自主内部进程

**Memory** — 记忆 ID / 重要性 / 状态 / 关联记忆 / 检索 / 更新 / 归档 / 关联与链接机制

### In Progress（进行中）

长期记忆整合、更好的记忆检索、多模态记忆整合、Self Model、Belief System、Goal System、
更可靠的自主行为、情绪/状态到行为的耦合、想象到记忆的整合、更稳健的规划。

- **Self Model**：早期原型 / 部分实现。现有 self-observation、reflection、
  自传式与身份相关记忆机制；但没有完整独立的 Self Model。
- **Relationship**：关系相关状态 / 早期原型。现有 trust、closeness 与关系相关的情绪状态；
  但没有完整独立的 Relationship Model。
- **Agency**：有限自主 / 早期原型。能够自主触发部分内部进程（如想象、反思）；
  但真正的目标驱动的自主任务执行尚未完成。

### Planned（计划中）

Belief System、Goal System、Scheduler、目标驱动的自主性、轮式编码器、IMU、里程计、
电量监测、避障、导航、SLAM、ROS 2 集成、统一多模态记忆、机械臂、夹爪、触觉、
物理操作、更强的自主学习、未来的人形身体。

**ROS 2 当前没有实际代码** —— 没有 `rclpy`、没有 `package.xml`、没有 colcon 构建。
身体层直接驱动 GPIO。请不要把上面的「ROS 2 integration」理解为当前已支持。

### 架构

见上方 Architecture 一节。其中 Belief、Goal 尚未实现；Self Model 与
Safety / Epistemic Check 仅部分实现。

### 快速开始

```bash
cd src/duomi
export DEEPSEEK_API_KEY="..."
python main.py
```

项目仍处于早期工程阶段，部分模块使用本地 flat imports，因此从 `src/duomi` 目录运行。

### 隐私与密钥

- API Key 全部从环境变量读取（`DEEPSEEK_API_KEY`），源码无任何硬编码密钥。
- 记忆、情绪、学习、视觉观察等运行时数据**不在本仓库**，已被 `.gitignore` 排除。
- 大型第三方模型（ONNX、音色、ASR 模型）不随仓库分发。

### License

尚未添加开源许可证。保留所有权利。

### 开发状态

DUOMI 是一个活跃的实验性 embodied AI 项目。

本仓库有意区分 Implemented / In Progress / Planned，目的是记录真实的开发进展，
而不是把未来的研究设想包装成已完成的能力。
