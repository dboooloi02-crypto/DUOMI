# DUOMI Build Log

## Scope

This directory records **how DUOMI evolved**. The historical files themselves are
deliberately **not uploaded** — they stay in the local backup.

The original directory contains **83 Python files**, of which:

| Category | Count |
|----------|:-----:|
| 当前源码 / current sources | 22 |
| 历史与测试版本 / historical & test versions | 61 |

Uploading all of them would bury the current code under dozens of snapshots, so the
public repository keeps only the 22 current modules.

## Version timeline (reconstructed from snapshot filenames)

- `2026-09-19 22:49` `imagination_system.py` — `v031`
- `2026-09-19 22:54` `imagination_system.py` — `v032_listdedupe`

## How to restore a historical version

Historical files live in the local backup, e.g.:

```
D:\DUOMI_BACKUP\wincn\duomi\
```

Filenames follow `<module>.py.<tag>.<YYYYMMDD_HHMMSS>`, for example:

```
imagination_system.py.v040.clientglobal.20260920_085806
imagination_trigger.py.v041.visionstart.20260920_221931
```

To inspect one, copy it into `src/duomi/` under a temporary name. Do not commit it.

## Future work

If a particular snapshot turns out to matter for understanding the design, it can be
promoted into `docs/build-log/` as a short write-up (what changed and why) — the file
itself still does not need to be published.
