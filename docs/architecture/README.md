# DUOMI Architecture

## Cognitive loop

```
Perception        感知      hearing.py · vision_system.py
      ↓
Interpretation    理解      action_planner.py · vision_system.py (LLM)
      ↓
Memory Retrieval  记忆检索  memory_manager.py
      ↓
State             内部状态  emotion_system.py
      ↓
Self Model        自我模型  learning_system.py · reflection_system.py
      ↓
Belief            信念      — (no dedicated module)
      ↓
Goal              目标      — (no dedicated module)
      ↓
Prediction        预测      imagination_system.py
      ↓
Planning          规划      action_planner.py
      ↓
Decision          决策      main.py
      ↓
Action            行动      motor_controller.py · tts_plus.py
      ↓
Observation       观察      vision_memory.py · vision_compare.py
      ↓
Experience        经验      memory_manager.py · learning_system.py
      ↓
Growth            成长      learning_system.py · reflection_system.py
```

Two stages — **Belief** and **Goal** — have no dedicated module. Their logic currently
lives inside `action_planner.py` and `imagination_system.py`. This is recorded honestly
rather than papered over with a placeholder.

## Six subsystems

| Subsystem | Modules | Status |
|-----------|---------|--------|
| Brain | `action_planner.py` + DeepSeek via OpenAI-compatible SDK | implemented |
| Memory | `memory_manager.py` | implemented, retrieval quality in progress |
| Self | `learning_system.py`, `reflection_system.py`, `imagination_system.py` | early form |
| Agency | `imagination_trigger.py`, `main.py` | implemented (trigger-based) |
| Relationship | `emotion_system.py` | implemented as internal state dimensions |
| Body | `motor_controller.py`, `hearing.py`, `tts*.py`, `vision_system.py` | implemented, minimal (differential base only) |

## Module map

| File | Lines of responsibility |
|------|-------------------------|
| `main.py` | entry point; wires hearing → planner → TTS → motor; SIGINT handling |
| `hearing.py` | streaming ASR via sherpa-onnx, `arecord` at 16 kHz |
| `tts.py` / `tts_plus.py` | local Piper / Piper-Plus synthesis, played with `aplay` |
| `pronunciation.py` | pronunciation dictionary applied before synthesis (needs `pronunciation.json`) |
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

## What is deliberately absent

- **No ROS 2.** The body layer drives GPIO directly. ROS 2 is planned, not started.
- **No simulation.** There is no Gazebo / Isaac / MuJoCo model in this project.
- **No vector database.** Retrieval in `memory_manager.py` is string-similarity based
  (`difflib` + hashing), not embeddings.
