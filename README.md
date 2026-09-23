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

## How DUOMI Runs Today

DUOMI currently runs on a Raspberry Pi. **`main.py` is the system entry point.**

### 1. Startup

```text
main.py
  ↓
create DeepSeek / OpenAI-compatible LLM client   (key from env DEEPSEEK_API_KEY)
  ↓
load Hearing                                     (sherpa-onnx streaming Chinese ASR)
  ↓
load Action Planner
  ↓
load Robot Controller                            (GPIO motors)
  ↓
load User Profile                                (user_profile.json)
  ↓
load Important Memory                            (important_memory.json)
  ↓
build system prompt (identity + user profile), append conversation history (memory.json)
  ↓
register SIGINT handler — Ctrl+C stops the body and exits
  ↓
enter the interaction loop
```

### 2. Interaction loop

Each turn is **voice-driven and blocking** — DUOMI waits for one utterance, then acts:

```text
listen once (ASR) → no speech detected → listen again
      ↓
exit command? ("quit" / "退出" / "退出系统") → save memory, stop body, exit
      ↓
Action Planner — does this utterance map to a movement?
      │
      ├── YES → Robot Controller executes (forward / backward / left / right / stop)
      │         → speak a short confirmation → save memory → next turn
      │         (on failure: stop the body, then next turn)
      │
      └── NO  → conversation path:
                1. infer an emotion event from the utterance; if one is detected,
                   apply it to the internal state
                2. retrieve related long-term memories
                3. assemble context: memory + internal state + learned rules
                4. ask the LLM (web tools are used only when needed)
                5. speak the answer FIRST, before any autonomous processing
                6. if an emotion event was detected: reflect on this turn and record
                   the lesson (falls back to a conservative template if reflection fails)
                7. save conversation memory, then organise long-term memory
                   (add / update / ignore, plus bidirectional linking of related memories)
```

### 3. What this means in practice

- **Turn-based, not scheduled.** There is no background scheduler. DUOMI reacts to one
  spoken utterance at a time.
- **Movement and conversation are alternative branches, not a combined pipeline.** If the
  planner returns a movement, DUOMI moves and answers with a fixed short confirmation
  rather than generating a conversational reply.
- **Emotion and learning are event-gated.** Internal state is only updated when
  `infer_event` detects an explicit event; ordinary chat does not force an emotion change.
  Reflection and learning run only on turns where such an event was detected.
- **Speech output comes first.** `speak_plus` runs before reflection and memory
  organisation, so autonomous processing never adds to the user's waiting time.
- **Everything persists to local files**: conversation history → `memory.json`,
  long-term memory → `important_memory.json`, user profile → `user_profile.json`.
- **Safety**: Ctrl+C stops the motors and exits; every motor command is clamped by
  `MAX_ACTION_DURATION` and always stops in a `finally` block.

This section describes **what the code does today**, not the target design.

---

## Current Architecture

```text
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
> `pronunciation.py` reads `pronunciation.json` from the same directory — that file is
> part of the code, not runtime data, and is committed. Synthesis runs locally — no cloud TTS.

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

## Near-term Roadmap

The next development steps, in order. Each one depends on what comes before it.
The full V0.1 → V1.x sequence is in [Development Roadmap](#development-roadmap).

| Version | Focus | Status |
|---------|-------|:------:|
| **V0.2** | Memory Foundation — working / episodic / semantic / autobiographical memory, provenance, confidence, temporal relations, retrieval quality, conflict resolution, consolidation | 🟡 |
| **V0.3** | Self Model — `self_model.py`: identity, capabilities, limitations, preferences, values, beliefs, current state, current goals, autobiography | 🟡 |
| **V0.4** | Relationship Model — `relationship_model.py`: familiarity, trust, respect, closeness, conflict, shared history, beliefs about people | 🟡 |
| **V0.5** | Belief + Goal System — `belief_system.py`, `goal_system.py`: belief update, goal generation, priority, lifecycle, constraints | 🔵 |
| **V0.6** | Agency / Autonomy — `scheduler.py`: internal triggers, autonomous goal selection, planning, safety checks, execution, observation, evaluation, recovery | 🔵 |

None of these are implemented yet.

---

## Development Roadmap

This is the **recommended development order**, not a claim that these capabilities exist.
Only **V0.1** is done. Everything from V0.2 onward is future work.

Legend: ✅ done · 🟡 started / next · 🔵 planned · 🔴 long-term

### V0.1 — Foundation ✅

Already working:

- Raspberry Pi body
- Differential drive
- Motor control
- Camera
- Microphone
- Local TTS
- Streaming ASR
- Action planner
- Memory manager
- Emotion / internal state
- Learning
- Reflection
- Imagination
- Vision observation / memory
- Web tools

### V0.2 — Memory Foundation 🟡

Goal: turn "a memory list" into a memory system with structure and provenance.

- Working Memory
- Episodic Memory
- Semantic Memory
- Autobiographical Memory
- Provenance
- Confidence
- Temporal relationships
- Retrieval quality
- Conflict resolution
- Consolidation

*Why first:* every later stage reads from memory. A Self Model, Belief System or Goal
System built on an unstructured memory list would inherit that weakness.

### V0.3 — Self Model 🟡

New module `self_model.py`:

- Identity
- Capabilities
- Limitations
- Preferences
- Values
- Beliefs
- Current state
- Current goals
- Autobiography

*Depends on V0.2.* A self model is largely compiled from autobiographical memory —
it needs a memory layer that can answer "what happened to me, and when".

### V0.4 — Relationship Model 🟡

New module `relationship_model.py`:

- Familiarity
- Trust
- Respect
- Closeness
- Conflict
- Shared history
- Beliefs about people

*Depends on V0.2 + V0.3.* Relationships are modelled against a self: "closer to me than
before" needs both a memory of past interactions and a stable self to compare against.

### V0.5 — Belief + Goal System 🔵

New modules `belief_system.py`, `goal_system.py`:

- Belief update
- Goal generation
- Goal priority
- Goal lifecycle
- Constraints

Forming the chain:

```text
Observation → Belief → Goal → Priority → Plan
```

*Depends on V0.3.* Goal generation must respect capabilities and limitations — which is
exactly what the Self Model provides. Without it, DUOMI would generate goals it cannot
evaluate or refuse.

### V0.6 — Agency / Autonomy 🔵

New module `scheduler.py`:

- Internal triggers
- Autonomous goal selection
- Planning
- Safety checks
- Action execution
- Observation
- Evaluation
- Recovery

Goal: move DUOMI from **"can be called"** toward **"can act with purpose on its own"**.

*Depends on V0.5 + V0.2.* Autonomy needs goals to select from (V0.5) and memory to
evaluate outcomes against (V0.2). Safety checks are part of this stage, not an afterthought.

### V0.7 — Physical Feedback 🔵

Hardware upgrades:

- Wheel encoders
- IMU
- Distance sensors
- Battery monitoring
- Odometry

Goal: DUOMI should no longer only know *"I sent a movement command"* — it should know
**what its body actually did**.

*Independent of the cognition stages, but required by V0.8.* Navigation is meaningless
without odometry and distance feedback.

### V0.8 — Navigation + ROS 2 🔵

Build the ROS 2 interface first, then move into:

- `cmd_vel`
- Odometry
- Sensor topics
- Localization
- Mapping / SLAM
- Path planning
- Obstacle avoidance
- Navigation

> **There is currently no ROS 2 code in this repository.** This stage is future work.

### V0.9 — Unified Multimodal Memory 🔵

Unify into retrievable episodic experiences:

- Text
- Audio
- Image
- Video
- Action
- Emotion
- Environment
- Time

Goal: DUOMI should form real **experiences**, not separate, unconnected logs.

*Depends on V0.2 + V0.7.* It needs the memory structure to index into, and body feedback
to bind actions and outcomes to episodes.

### V1.0 — Physical Manipulation 🔵

- Robotic arm
- Gripper
- Tactile sensing
- Object manipulation

Forming the chain:

```text
See → Understand → Plan → Reach → Grasp → Manipulate → Observe → Learn
```

*Depends on V0.5 / V0.6 + V0.9.* Manipulation needs goal-directed planning and
experience-level memory to learn from failed grasps.

### V1.x — Self-directed Growth 🔴

DUOMI should be able to:

- Identify problems
- Generate hypotheses
- Create goals
- Run experiments
- Evaluate results
- Update knowledge
- Acquire new skills

The goal is **not** "self-training a model". It is capability growth through continuous
experience and action.

*Depends on V0.6 + V0.9.* Self-directed growth is autonomy plus experience — it is the
stage where the loop closes.

### Future — Humanoid Body 🔴

Long-term direction:

- Multi-joint body
- Manipulation
- Richer sensing
- Whole-body interaction
- Human-scale embodied intelligence

---

## Long-Term Vision

DUOMI is ultimately meant to form this loop:

```text
Perception
   → Interpretation
   → Memory
   → Internal State
   → Self
   → Belief
   → Goal
   → Planning
   → Action
   → Observation
   → Reflection
   → Learning
   → Growth
```

and to close it.

Growth feeds back into memory and into the self model, so each loop makes the next one
slightly better informed. That closed loop — not any single capability — is the actual
goal of this project.

> **Development Roadmap is the recommended order of work.**
> It is not a statement that these future capabilities have been implemented.

---

## Hardware

DUOMI currently runs on:

- Raspberry Pi
- Two-wheel differential drive with an L298N driver (GPIO: left `ENA 23 / IN1 17 / IN2 18`,
  right `ENB 24 / IN3 27 / IN4 22`)
- USB microphone on ALSA `plughw:1,0` (16 kHz mono)
- USB camera on `/dev/video0`, captured with `v4l2-ctl`
- Speaker via `aplay`
- Local Piper / Piper-Plus TTS

Full wiring, audio and camera commands, and the list of model files that must be
downloaded separately: **[`docs/hardware/`](docs/hardware/README.md)**.

---

## Installation / Run

### Repository layout

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

### Run

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

---

## Privacy

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

**LLM 是 DUOMI 的认知引擎之一，而不是 DUOMI 本身的身份。** 当前使用 DeepSeek
（经 OpenAI 兼容 SDK），系统设计上允许未来替换不同的 LLM —— DUOMI 的身份、记忆与
内部状态存在于它自己的模块里，不在任何模型内部。

### DUOMI 当前如何运行

DUOMI 当前运行在 Raspberry Pi 上，**`main.py` 是系统入口**。

启动顺序见上方「How DUOMI Runs Today」第 1 节。启动后进入**语音驱动、阻塞式**的交互循环：
DUOMI 等待一句语音，然后行动。

几个容易误解的点，按代码实际情况说明：

- **一轮一轮来，不是后台调度。** 没有后台调度器，DUOMI 一次只对一句语音做出反应。
- **移动与对话是二选一分支，不是串联流水线。** planner 若返回动作，DUOMI 执行动作并用一句固定确认回复，
  不再生成对话式回答；只有 planner 没返回动作时才走对话分支。
- **情绪与学习由事件触发。** 只有 `infer_event` 检测到明确事件时才更新内部状态，普通闲聊不会强行改变情绪；
  反思与学习同样只在检测到事件的轮次执行（反思失败时退回保守模板学习）。
- **语音输出优先。** `speak_plus` 在反思与记忆整理之前执行，自主处理不会增加用户等待时间。
- **全部落本地文件**：对话历史 → `memory.json`，长期记忆 → `important_memory.json`，档案 → `user_profile.json`。
- **安全**：Ctrl+C 停止电机并退出；每条电机指令受 `MAX_ACTION_DURATION` 限制，并在 `finally` 中保证停止。
- **退出方式**：说「退出系统」/「退出」/「quit」正常保存并退出；Ctrl+C 为紧急停止。

这一节描述的是**代码当前实际做的事**，不是目标架构。

### Implemented（已完成）

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

### 近期路线（Near-term Roadmap）

| 版本 | 重点 | 状态 |
|------|------|:----:|
| **V0.2** | Memory Foundation — 工作/情景/语义/自传记忆、来源、置信度、时序关系、检索质量、冲突消解、整合 | 🟡 |
| **V0.3** | Self Model — `self_model.py`：身份、能力、局限、偏好、价值、信念、当前状态、当前目标、自传 | 🟡 |
| **V0.4** | Relationship Model — `relationship_model.py`：熟悉度、信任、尊重、亲近、冲突、共同经历、对人的信念 | 🟡 |
| **V0.5** | Belief + Goal System — `belief_system.py` / `goal_system.py`：信念更新、目标生成、优先级、生命周期、约束 | 🔵 |
| **V0.6** | Agency / Autonomy — `scheduler.py`：内部触发、自主选目标、规划、安全检查、执行、观察、评估、恢复 | 🔵 |

以上均**尚未实现**。完整 V0.1 → V1.x 路线见下方。

### 研发路线（Development Roadmap）

这是**推荐的研发顺序**，不是已实现声明。只有 **V0.1** 已完成。

图例：✅ 已完成 · 🟡 已启动/下一步 · 🔵 计划中 · 🔴 长期

- **V0.1 — Foundation ✅**：Raspberry Pi 身体 / 差速底盘 / 电机控制 / 摄像头 / 麦克风 /
  本地 TTS / 流式 ASR / action planner / memory manager / 情绪与内部状态 / learning /
  reflection / imagination / 视觉观察与记忆 / web tools
- **V0.2 — Memory Foundation 🟡**：Working / Episodic / Semantic / Autobiographical Memory、
  provenance、confidence、时序关系、检索质量、冲突消解、整合。
  *为什么最先做*：后面每一层都要读记忆，建在松散记忆列表上的 Self / Belief / Goal 会继承这个缺陷。
- **V0.3 — Self Model 🟡**：新增 `self_model.py`。*依赖 V0.2* —— 自我模型主要由自传式记忆编译而来。
- **V0.4 — Relationship Model 🟡**：新增 `relationship_model.py`。*依赖 V0.2 + V0.3* ——
  「比之前更亲近」既需要过往互动的记忆，也需要一个稳定的自我作参照。
- **V0.5 — Belief + Goal System 🔵**：新增 `belief_system.py` / `goal_system.py`，
  形成 `Observation → Belief → Goal → Priority → Plan`。*依赖 V0.3* —— 目标生成必须尊重能力与局限。
- **V0.6 — Agency / Autonomy 🔵**：新增 `scheduler.py`。
  目标：让 DUOMI 从**「能被调用」**逐步变成**「能主动进行有目标的行为」**。*依赖 V0.5 + V0.2*。
- **V0.7 — Physical Feedback 🔵**：轮式编码器 / IMU / 距离传感器 / 电量监测 / 里程计。
  目标：不再只知道「我发出了移动指令」，而是知道**我的身体实际发生了什么**。*为 V0.8 所必需*。
- **V0.8 — Navigation + ROS 2 🔵**：先建 ROS 2 interface，再进入 cmd_vel / 里程计 / 传感器 topic /
  定位 / SLAM / 路径规划 / 避障 / 导航。**当前没有 ROS 2 代码，此阶段为未来计划。**
- **V0.9 — Unified Multimodal Memory 🔵**：把文本、音频、图像、视频、动作、情绪、环境、时间
  统一成可检索的情景经历。目标：让 DUOMI 真正形成**经历**，而不是互相分离的日志。*依赖 V0.2 + V0.7*。
- **V1.0 — Physical Manipulation 🔵**：机械臂 / 夹爪 / 触觉 / 物体操作，
  形成 `See → Understand → Plan → Reach → Grasp → Manipulate → Observe → Learn`。*依赖 V0.5/V0.6 + V0.9*。
- **V1.x — Self-directed Growth 🔴**：发现问题 / 生成假设 / 创建目标 / 做实验 / 评估结果 /
  更新知识 / 获得新技能。目标不是「自我训练模型」，而是通过持续经历与行动形成能力增长。*依赖 V0.6 + V0.9*。
- **Future — Humanoid Body 🔴**：多关节身体 / 操作 / 更丰富感知 / 全身交互 / 人形尺度的具身智能。

### 长期愿景（Long-Term Vision）

DUOMI 最终希望形成：

```
Perception → Interpretation → Memory → Internal State → Self → Belief → Goal
→ Planning → Action → Observation → Reflection → Learning → Growth
```

并且**形成闭环** —— 成长会回过头写入记忆与自我模型，让下一轮循环比上一轮更有依据。
这个闭环本身（而不是某个单独功能）才是这个项目的真正目标。

**研发路线是推荐的研发顺序，不代表这些未来功能已经实现。**

### 硬件

Raspberry Pi / 两轮差速 + L298N（左 `ENA 23 / IN1 17 / IN2 18`，右 `ENB 24 / IN3 27 / IN4 22`）、
USB 麦克风（ALSA `plughw:1,0`，16 kHz 单声道）、USB 相机（`/dev/video0`，`v4l2-ctl` 抓帧）、
扬声器（`aplay`）、本地 Piper / Piper-Plus TTS。详见 [`docs/hardware/`](docs/hardware/README.md)。

### 安装与运行

```bash
cd src/duomi
export DEEPSEEK_API_KEY="..."
python main.py
```

项目仍处于早期工程阶段，部分模块使用本地 flat imports，因此从 `src/duomi` 目录运行。

### 隐私

- API Key 全部从环境变量读取（`DEEPSEEK_API_KEY`），源码无任何硬编码密钥。
- 记忆、情绪、学习、视觉观察等运行时数据**不在本仓库**，已被 `.gitignore` 排除。
- 大型第三方模型（ONNX、音色、ASR 模型）不随仓库分发。

### License

尚未添加开源许可证。保留所有权利。

### 开发状态

DUOMI 是一个活跃的实验性 embodied AI 项目。

本仓库有意区分 Implemented / In Progress / Planned，目的是记录真实的开发进展，
而不是把未来的研究设想包装成已完成的能力。
