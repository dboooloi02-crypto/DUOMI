# DUOMI Architecture

> This document describes **DUOMI's architecture as it exists today**.
> For the planned evolution — V0.2 through V1.x and the long-term vision — see
> [`README.md` → Development Roadmap](../../README.md#development-roadmap).

## Cognitive loop

```
Perception              感知       hearing.py · vision_system.py
      ↓
Interpretation          理解       action_planner.py · vision_system.py (LLM)
      ↓
Memory Retrieval        记忆检索   memory_manager.py (retrieve_memories)
      ↓
Internal State          内部状态   emotion_system.py
      ↓
Self Model              自我模型   — partial (self-observation · reflection · identity memory)
      ↓
Belief                  信念       — not implemented
      ↓
Goal                    目标       — not implemented
      ↓
Prediction              预测       imagination_system.py
      ↓
Planning                规划       action_planner.py
      ↓
Safety / Epistemic Check安全检查   — partial (motor duration clamp; explicit uncertainty in vision)
      ↓
Decision                决策       main.py
      ↓
Action                  行动       motor_controller.py · tts_plus.py
      ↓
Observation             观察       vision_memory.py · vision_compare.py
      ↓
Experience              经验       memory_manager.py
      ↓
Learning / Growth       学习与成长 learning_system.py · reflection_system.py
```

Four stages are honest gaps today:

| Stage | State | Where the logic lives now |
|-------|-------|---------------------------|
| Self Model | partial | `learning_system.py`, `reflection_system.py`, `imagination_system.py` |
| Belief | **not implemented** | scattered in `action_planner.py` / `imagination_system.py` |
| Goal | **not implemented** | scattered in `action_planner.py` / `imagination_system.py` |
| Safety / Epistemic Check | partial | `MAX_ACTION_DURATION` clamp in `motor_controller.py`; `uncertainties` / `cannot_determine` / `reliability` in the vision modules |

These are recorded as gaps rather than papered over with placeholder modules.

## Six subsystems

| Subsystem | Modules | Status | Roadmap version |
|-----------|---------|--------|-----------------|
| Brain | `action_planner.py` + DeepSeek via OpenAI-compatible SDK | implemented | V0.1 ✅ |
| Memory | `memory_manager.py` | implemented; retrieval quality in progress | V0.2 🟡 |
| Self | `learning_system.py`, `reflection_system.py`, `imagination_system.py` | early form, no standalone module | V0.3 🟡 |
| Agency | `imagination_trigger.py`, `main.py` | implemented (trigger-based only) | V0.6 🔵 |
| Relationship | `emotion_system.py` | implemented as internal state dimensions, no standalone model | V0.4 🟡 |
| Body | `motor_controller.py`, `hearing.py`, `tts*.py`, `vision_system.py` | implemented, minimal (differential base only) | V0.1 ✅ / V0.7 🔵 |

## Module map

| File | Responsibility |
|------|-------------------------|
| `main.py` | entry point; wires hearing → planner → TTS → motor; SIGINT handling |
| `hearing.py` | streaming ASR via sherpa-onnx, `arecord` at 16 kHz |
| `tts.py` / `tts_plus.py` | local Piper / Piper-Plus synthesis, played with `aplay` |
| `pronunciation.py` | pronunciation dictionary applied before synthesis (reads `pronunciation.json`) |
| `motor_controller.py` | GPIO differential drive, `MAX_ACTION_DURATION = 3.0 s` safety clamp |
| `action_planner.py` | LLM-driven intent and action planning |
| `memory_manager.py` | conversation memory, important memory, associative retrieval |
| `emotion_system.py` | internal state: mood, valence, arousal, trust, closeness, energy … |
| `learning_system.py` | extracts lessons from experience |
| `reflection_system.py` | reflection over learning history |
| `imagination_system.py` | prediction / imagination over memory |
| `imagination_trigger.py` | decides when to trigger imagination |
| `vision_system.py` | USB camera capture + vision LLM interpretation |
| `vision_memory.py` | persists observations |
| `vision_compare.py` | compares observations across time, with reliability estimates |
| `web_agent.py` / `web_tools.py` | tool dispatch layer |
| `web_search.py` / `web_search_baidu.py` | multi-source search |
| `web_open.py` / `web_news.py` | page fetching (gzip handled) and news extraction |

## Roadmap alignment

Which version is expected to introduce which architectural piece:

| Version | Architectural change |
|---------|---------------------|
| **V0.2** | Memory gains structure: working / episodic / semantic / autobiographical memory, provenance, confidence, temporal relations, conflict resolution, consolidation |
| **V0.3** | `self_model.py` — Self Model becomes a real module: identity, capabilities, limitations, preferences, values, beliefs, current state, current goals, autobiography |
| **V0.4** | `relationship_model.py` — Relationship becomes a real module: familiarity, trust, respect, closeness, conflict, shared history, beliefs about people |
| **V0.5** | `belief_system.py` + `goal_system.py` — Belief and Goal become real modules, forming `Observation → Belief → Goal → Priority → Plan` |
| **V0.6** | `scheduler.py` — Agency moves from trigger-based to goal-driven: internal triggers, autonomous goal selection, planning, safety checks, execution, observation, evaluation, recovery |
| **V0.7** | Body gains feedback: wheel encoders, IMU, distance sensors, battery monitoring, odometry |
| **V0.8** | ROS 2 interface, then `cmd_vel`, odometry, sensor topics, localization, SLAM, path planning, obstacle avoidance, navigation |
| **V0.9** | Unified multimodal memory: text, audio, image, video, action, emotion, environment, time → retrievable episodic experiences |
| **V1.0** | Physical manipulation: arm, gripper, tactile sensing — `See → Understand → Plan → Reach → Grasp → Manipulate → Observe → Learn` |
| **V1.x** | Self-directed growth: identify problems, generate hypotheses, create goals, run experiments, evaluate, update knowledge, acquire skills |

Dependencies worth remembering:

- V0.3 and V0.4 both depend on V0.2 — a self model and a relationship model are compiled
  from memory, so an unstructured memory layer would weaken both.
- V0.5 depends on V0.3 — goal generation must respect capabilities and limitations.
- V0.6 depends on V0.5 + V0.2 — autonomy needs goals to choose from and memory to
  evaluate outcomes against.
- V0.7 is independent of the cognition stages, but **required by V0.8** — navigation is
  meaningless without odometry and distance feedback.
- V0.9 depends on V0.2 + V0.7. V1.0 depends on V0.5/V0.6 + V0.9. V1.x depends on V0.6 + V0.9.

## What is deliberately absent

- **No ROS 2.** The body layer drives GPIO directly. ROS 2 is planned for **V0.8**, not started.
- **No simulation.** There is no Gazebo / Isaac / MuJoCo model in this project.
- **No vector database.** Retrieval in `memory_manager.py` is string-similarity based
  (`difflib` + hashing), not embeddings. A retrieval overhaul is part of **V0.2**.
- **No standalone Self / Relationship / Belief / Goal modules.** These are tracked under
  V0.3, V0.4 and V0.5 respectively.
