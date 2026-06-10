# Inspector Keyboard Shortcuts

A printable, single-page reference for every keyboard shortcut in the
RRational Inspector. Press `F1` from inside the app to open this list
inline.

For prose explanations of each shortcut see
[Inspector features](inspector-features.md) and the in-app
`Help → Workflow walkthrough`.

---

## Navigation

| Key | Action |
|-----|--------|
| `R` | Reset zoom to full recording |
| `1` | Jump to last 1 minute |
| `2` | Jump to last 10 minutes |
| `3` | Jump to full recording |
| `Home` | Jump to first 60 seconds |
| `End` | Jump to last 60 seconds |
| `←` | Pan left 25% of visible window |
| `→` | Pan right 25% of visible window |
| `↑` | Zoom out |
| `↓` | Zoom in |
| `Page Up` / `Page Down` | Step through participants |

---

## Modes

Drag-select modes let you mark a time range with a single mouse drag.
Press the key once to enter the mode; press again (or `Esc`) to exit.

| Key | Mode |
|-----|------|
| `A` | Annotation mode (drag to create a labeled range) |
| `E` | Exclusion mode (drag to mark a bad time range) |
| `M` | Manual artifact mark mode (click individual beats) |

---

## Display toggles

| Key | Action |
|-----|--------|
| `H` | Toggle HUD readout (t / RR / HR) |
| `C` | Toggle crosshair |
| `Z` | Zen mode — hide HUD and crosshair |
| `G` | Toggle grid |
| `S` | Toggle section bands |
| `V` | Toggle event markers |

---

## File and project

| Key | Action |
|-----|--------|
| `Ctrl+N` | New project |
| `Ctrl+O` | Open project |
| `Ctrl+S` | Save current dataset as `.rrational` v2 |
| `Ctrl+Shift+S` | Save as… (new file) |
| `Ctrl+Q` | Quit |

---

## Edit

| Key | Action |
|-----|--------|
| `Ctrl+Z` | Undo manual artifact mark |
| `Ctrl+Y` (Win/Linux), `Cmd+Shift+Z` (macOS) | Redo manual mark |
| `Ctrl+,` | Open Preferences |

---

## Global

| Key | Action |
|-----|--------|
| `F1` | Open keyboard shortcut reference |
| `F11` | Toggle fullscreen |
| `Esc` | Exit current mode (annotation / exclusion / manual mark) |

---

## Tips and tricks

### Z for demos

Pressing `Z` once gives you a clean view for screenshots, lecture
slides, or screen recordings — no HUD overlay in the corner, no
crosshair following the cursor. Press `Z` again to bring everything
back.

### Crosshair for event alignment

Turn on the crosshair (`C`) when checking that an event marker lines up
with a feature in the tachogram — the vertical line snaps to the cursor
so you can read off precise times.

### 1 / 2 / 3 for triage

When skimming a long recording, the `3 → 2 → 1` cascade lets you start
zoomed out (full recording), then drill down to the last 10 minutes,
then to the last 1 minute, without touching the mouse.

### Home / End for split-end review

For protocols where the interesting parts are bookends (e.g. baseline
+ recovery), `Home` and `End` jump straight to the first / last 60 s.

### Arrow keys for precision panning

`←` and `→` pan exactly 25% of the visible window — predictable enough
that you can press `→` four times to scroll one window-width forward.

---

## Cross-references

- [Inspector features](inspector-features.md) — full feature reference
  with prose explanations.
- [Inspector workflows](inspector-workflows.md) — six end-to-end use
  cases putting the shortcuts in context.
- `Help → Workflow walkthrough` in the app — interactive tour.
