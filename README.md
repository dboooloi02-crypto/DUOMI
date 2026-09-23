# DUOMI

**A Robot That Grows With You.**

[English](#english) · [中文](#%E4%B8%AD%E6%96%87)

> DUOMI is an embodied AI personal robot built from scratch.
> The goal is not to answer questions, but to hold a continuous identity,
> long-term memory, internal state, relationships, autonomous action,
> and eventually a real physical body.
>
> **This is a live project, not a finished product.** Every claim below is
> backed by code in this repository. Nothing is claimed that is not built.

---

## 中文

### DUOMI 是什么

DUOMI 是我从零开始构建的 embodied AI 个人机器人。

目标不是"做一个会答话的模型"，而是让 AI 拥有：

- 持续的身份（不会因为会话结束而重置）
- 长期记忆（跨天、跨会话地积累）
- 内部状态（情绪、能量、信任、亲近度等可演化的量）
- 关系（对人、对事件的持续态度）
- 自主行动（不只是被调用，而是能自己发起观察、想象、反思）
- 最终的实体身体（能感知、能移动、能说话的硬件）

### 状态：Implemented / In Progress / Planned

#### ✅ Implemented

以下每一项都对应仓库里真实存在的代码：

| 能力 | 对应模块 |
|------|----------|
| Raspberry Pi robot body | `src/duomi/motor_controller.py` |
| Motor control | `src/duomi/motor_controller.py`（双轮差速，DC 减速电机） |
| Camera input | `src/duomi/vision_system.py`（USB 相机，v4l2-ctl 抓帧） |
| Microphone input | `src/duomi/hearing.py`（arecord + 流式 ASR） |
| Local Chinese speech synthesis | `src/duomi/tts.py`、`tts_plus.py`、`pronunciation.py`（Piper / Piper-Plus，本地推理） |
| Chinese streaming ASR | `src/duomi/hearing.py`（sherpa-onnx zipformer CTC） |
| Action planning | `src/duomi/action_planner.py` |
| Memory management | `src/duomi/memory_manager.py` |
| Emotion / internal state mechanisms | `src/duomi/emotion_system.py` |
| Learning / reflection | `src/duomi/learning_system.py`、`reflection_system.py` |
| Imagination | `src/duomi/imagination_system.py`、`imagination_trigger.py` |
| Vision observation and memory | `src/duomi/vision_system.py`、`vision_memory.py`、`vision_compare.py` |
| Web tools | `src/duomi/web_tools.py`、`web_search*.py`、`web_open.py`、`web_news.py`、`web_agent.py` |

#### 🚧 In Progress

- 长期记忆的检索质量与冲突合并（现有实现可用，仍在迭代）
- 视觉观察的连续性与对比可靠性（`vision_compare.py` 已含可靠性评估，阈值仍在调）
- 情绪状态与行为之间的耦合强度
- 想象系统对记忆的写入策略

#### 📋 Planned

- **ROS 2 接入**：当前项目**没有任何 ROS 2 代码** —— 没有 `rclpy`、没有 `package.xml`、没有 colcon 构建。
  身体层目前是 `gpiozero` 直接控制 GPIO。迁移到 ROS 2 是计划中的方向，尚未开始。
- 更完整的实体身体（现有运动能力只有差速底盘，无机械臂）
- 多模态长期记忆的统一索引
- 主动行为调度（目前自主性体现在 imagination / reflection 的触发上）

> 上面 Planned 里的每一项都是**尚未实现**的。仓库里搜不到对应代码。

### 认知循环

```
Perception        感知       hearing.py · vision_system.py
      ↓
Interpretation    理解       action_planner.py · vision_system.py (LLM)
      ↓
Memory Retrieval  记忆检索   memory_manager.py
      ↓
State             内部状态   emotion_system.py
      ↓
Self Model        自我模型   learning_system.py · reflection_system.py
      ↓
Belief            信念
      ↓
Goal              目标
      ↓
Prediction        预测       imagination_system.py
      ↓
Planning          规划       action_planner.py
      ↓
Decision          决策       main.py
      ↓
Action            行动       motor_controller.py · tts_plus.py
      ↓
Observation       观察       vision_memory.py · vision_compare.py
      ↓
Experience        经验       memory_manager.py · learning_system.py
      ↓
Growth            成长       learning_system.py · reflection_system.py
```

说明：Belief / Goal 两个阶段目前**没有独立的模块**，它们的逻辑分散在
`action_planner.py` 与 `imagination_system.py` 中。这是当前的真实状态，不是设计目标。

### 六个长期架构

| 子系统 | 现在由什么承担 | 说明 |
|--------|----------------|------|
| **Brain** | `action_planner.py` + DeepSeek LLM | 理解、推理、规划。LLM 走 OpenAI 兼容接口 |
| **Memory** | `memory_manager.py` | 对话记忆、重要记忆、联想检索 |
| **Self** | `learning_system.py` + `reflection_system.py` + `imagination_system.py` | 自我观察、反思、想象，共同构成自我模型的雏形 |
| **Agency** | `imagination_trigger.py` + `main.py` | 自主发起想象与反思，不只在被调用时工作 |
| **Relationship** | `emotion_system.py` | 内部状态含 trust / closeness 等关系维度 |
| **Body** | `motor_controller.py` + `hearing.py` + `tts*.py` + `vision_system.py` | 差速底盘、麦克风、扬声器、USB 相机 |

### 目录结构

```
duomi/
├── README.md
├── .gitignore
├── requirements.txt
├── src/duomi/        22 个当前源码模块 + pronunciation.json
├── docs/
│   ├── architecture/ 认知循环与六个子系统
│   ├── hardware/     GPIO 接线、音频、相机、模型文件清单
│   └── build-log/    版本演进记录（历史文件本体留在本地备份）
├── examples/         子系统驱动脚本
└── media/            （空）README 未引用媒体，故不公开上传
```

### 运行

```bash
cd src/duomi
export DEEPSEEK_API_KEY="..."
python main.py
```

> 模块间是平铺 import（`from memory_manager import ...`），因此**要在 `src/duomi/` 目录内运行**，
> 让该目录位于 `sys.path[0]`。没有做包化重构 —— 为了避免破坏已经在跑的代码。

### 隐私

- 所有 API Key 从环境变量读取（`DEEPSEEK_API_KEY`），源码内**没有任何硬编码密钥**。
- 记忆、情绪、学习、视觉观察等**运行期数据文件不在此仓库**，已在 `.gitignore` 中排除。
- 摄像头观察记录（`self_observation_memory.jsonl`、`vision_observation_log.jsonl` 等）
  含真实场景与人物，属于私人数据，不公开。

---

## English

### What DUOMI is

DUOMI is an embodied AI personal robot built from scratch.

The goal is not "a model that answers questions" but an AI that holds:

- a continuous identity (not reset per session)
- long-term memory (accumulating across days and sessions)
- internal state (emotion, energy, trust, closeness as evolving quantities)
- relationships (persistent attitudes toward people and events)
- autonomous action (initiating observation, imagination and reflection on its own)
- eventually a real physical body (sensing, moving, speaking hardware)

### Status: Implemented / In Progress / Planned

#### ✅ Implemented

Each item maps to code that exists in this repository:

| Capability | Module |
|------------|--------|
| Raspberry Pi robot body | `src/duomi/motor_controller.py` |
| Motor control | `src/duomi/motor_controller.py` (differential drive, DC gear motors) |
| Camera input | `src/duomi/vision_system.py` (USB camera via `v4l2-ctl`) |
| Microphone input | `src/duomi/hearing.py` (`arecord` + streaming ASR) |
| Local Chinese speech synthesis | `src/duomi/tts.py`, `tts_plus.py`, `pronunciation.py` (Piper / Piper-Plus, fully local) |
| Chinese streaming ASR | `src/duomi/hearing.py` (sherpa-onnx zipformer CTC) |
| Action planning | `src/duomi/action_planner.py` |
| Memory management | `src/duomi/memory_manager.py` |
| Emotion / internal state mechanisms | `src/duomi/emotion_system.py` |
| Learning / reflection | `src/duomi/learning_system.py`, `reflection_system.py` |
| Imagination | `src/duomi/imagination_system.py`, `imagination_trigger.py` |
| Vision observation and memory | `src/duomi/vision_system.py`, `vision_memory.py`, `vision_compare.py` |
| Web tools | `src/duomi/web_tools.py`, `web_search*.py`, `web_open.py`, `web_news.py`, `web_agent.py` |

#### 🚧 In Progress

- Retrieval quality and conflict merging for long-term memory
- Continuity and comparison reliability of vision observations
- Coupling strength between emotional state and behavior
- How the imagination system writes back into memory

#### 📋 Planned

- **ROS 2 integration**: this project contains **no ROS 2 code at all** — no `rclpy`,
  no `package.xml`, no colcon build. The body layer drives GPIO directly through `gpiozero`.
  Moving to ROS 2 is the intended direction and has not started.
- A more complete physical body (motion today is a differential base only, no arm)
- A unified index over multimodal long-term memory
- Proactive behavior scheduling (today autonomy shows up as imagination / reflection triggers)

> Everything under Planned is **not implemented**. There is no corresponding code in this repo.

### Cognitive loop

```
Perception      →  hearing.py · vision_system.py
Interpretation  →  action_planner.py · vision_system.py (LLM)
Memory Retrieval→  memory_manager.py
State           →  emotion_system.py
Self Model      →  learning_system.py · reflection_system.py
Belief          →  (no dedicated module yet)
Goal            →  (no dedicated module yet)
Prediction      →  imagination_system.py
Planning        →  action_planner.py
Decision        →  main.py
Action          →  motor_controller.py · tts_plus.py
Observation     →  vision_memory.py · vision_compare.py
Experience      →  memory_manager.py · learning_system.py
Growth          →  learning_system.py · reflection_system.py
```

Note: **Belief** and **Goal** have no dedicated modules today; their logic lives inside
`action_planner.py` and `imagination_system.py`. This is the current state, not the target design.

### Six long-term subsystems

| Subsystem | Currently carried by | Note |
|-----------|----------------------|------|
| **Brain** | `action_planner.py` + DeepSeek LLM | understanding, reasoning, planning via an OpenAI-compatible SDK |
| **Memory** | `memory_manager.py` | conversation memory, important memory, associative retrieval |
| **Self** | `learning_system.py` + `reflection_system.py` + `imagination_system.py` | self-observation, reflection and imagination together form an early self-model |
| **Agency** | `imagination_trigger.py` + `main.py` | initiates imagination and reflection instead of only responding |
| **Relationship** | `emotion_system.py` | internal state includes relational dimensions such as trust and closeness |
| **Body** | `motor_controller.py` + `hearing.py` + `tts*.py` + `vision_system.py` | differential base, microphone, speaker, USB camera |

### Layout

```
duomi/
├── README.md
├── .gitignore
├── requirements.txt
├── src/duomi/        22 current modules + pronunciation.json
├── docs/
│   ├── architecture/ cognitive loop and the six subsystems
│   ├── hardware/     GPIO wiring, audio, camera, required model files
│   └── build-log/    version timeline (the historical files stay in a local backup)
├── examples/         subsystem driver scripts
└── media/            (empty) no media is referenced by the README, so none is published
```

### Run

```bash
cd src/duomi
export DEEPSEEK_API_KEY="..."
python main.py
```

Modules import each other flat (`from memory_manager import ...`), so **run from inside
`src/duomi/`** so that directory is `sys.path[0]`. No package refactor was done —
the priority was not breaking code that already runs.

### Privacy

- All API keys come from the environment (`DEEPSEEK_API_KEY`). **No key is hardcoded.**
- Runtime data (memory, emotion, learning, vision observations) is **not in this repo**
  and is excluded by `.gitignore`.
- Camera observation logs contain real scenes and people and are private.

---

## License

No license file has been chosen yet. Until one is added, the default GitHub terms apply
(all rights reserved). See the note in this README's issue tracker discussion if you want to reuse code.
