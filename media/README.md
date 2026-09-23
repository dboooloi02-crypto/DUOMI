# media

This directory is currently empty.

## Why it exists

DUOMI is a physical robot. A repository that claims a body should eventually show one.
When a first real photo or demo clip is ready, it belongs here and can be referenced
from the README.

## Git note

`.gitignore` excludes `*.jpg` / `*.jpeg` / `*.png` / `*.wav` globally, so camera frames,
test captures and private recordings never end up in the repository by accident.

This directory is an **exception**:

```gitignore
!media/**/
!media/**/*.jpg
!media/**/*.jpeg
!media/**/*.png
```

So images inside `media/` **are** committable, while identical files elsewhere stay
ignored. Verified with `git status` — a file at `media/x.jpg` shows up as untracked,
while a file at `x.jpg` does not.

## Suggested contents

```text
media/
├── duomi-v0.1.jpg        # the robot itself — the most important one
├── hardware-v0.1.jpg     # wiring, motors, Raspberry Pi, camera, mic
└── demos/
```

## Rule

Only publish media that:

- shows hardware or behaviour you are willing to make public, and
- is actually referenced from the README or docs.

Camera observations of private spaces — and anything containing people who have not
agreed to be published — stay out. A media file that nothing links to is exposure
without purpose.
