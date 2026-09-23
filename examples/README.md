# DUOMI Examples

Scripts here drive one subsystem at a time. They are the fastest way to check that
a piece of hardware or a module works before running the full loop in `main.py`.

Run them from `src/duomi/` so flat imports resolve:

```bash
cd ../src/duomi
python ../examples/<script>.py
```

| Script | What it exercises |
|--------|-------------------|
| `motor_test.py` | DC motor wiring and direction |
| `hearing_test.py` | streaming ASR loop |
| `hearing_once_test.py` | a single ASR utterance |
| `asr_test.py` | ASR model loading |
| `action_planner_test.py` | planner output without the full loop |
| `web_tool_call_test.py` | web tool dispatch |

Requirements before running:

- `DEEPSEEK_API_KEY` exported (for planner / web agent scripts)
- microphones, speakers and GPIO wired per `docs/hardware/`
- ASR model directory present next to the code
