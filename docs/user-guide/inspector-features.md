# Inspector Feature Reference

This page is a feature-by-feature reference for the **RRational
Inspector** desktop app. For a high-level orientation, start with
[Inspector standalone app](../getting-started/inspector.md). For the
end-to-end walkthrough, open `Help → Workflow walkthrough` from inside
the app.

The features below match the in-app menus, dialogs, and side panels as
of the v0.9 release (Cluster A–D + R15–R16 feature waves).

---

## Visual features

### HUD (Heads-Up Display)

A compact panel anchored in the **top-right corner** of the tachogram.
It tracks the cursor and shows three live values:

| Field | Meaning |
|-------|---------|
| `t` | Time at the cursor (mm:ss) |
| `RR` | RR interval at the cursor (ms) |
| `HR` | Instantaneous heart rate (60 / RR) (bpm) |

**Toggle:** keyboard `H`, or `View → Show HUD readout`. The state
persists in QSettings across sessions.

### Crosshair

A vertical reference line that follows the cursor. Useful for aligning
event markers and reading off precise time-stamps.

**Toggle:** keyboard `C`, or `View → Show crosshair`.

### Zen mode

A one-stroke "hide everything that isn't the data" toggle — turns off
the HUD and Crosshair together. Built for screenshots, presentations,
and screen recordings where on-screen overlays are distracting.

**Toggle:** keyboard `Z`. There is no equivalent menu item because the
shortcut is the design — the action is intentionally fast.

### Color schemes

RRational ships three palettes:

| Palette | Use case |
|---------|----------|
| **Okabe-Ito** (default) | Colorblind-safe, Nature-recommended |
| **Viridis** | Continuous, perceptually uniform |
| **Custom** | User-defined hex codes |

Switch via `Edit → Preferences → Color Scheme`. Changes apply
immediately to every plot in the inspector — no restart needed.

For publication, keep Okabe-Ito unless your journal mandates otherwise.
It is distinguishable for the roughly 8% of readers with red-green
colorblindness (deuteranopia / protanopia).

---

## Navigation

### Overview bar

A reduced-scale strip below the main tachogram showing the **whole
recording** at a glance. A light rectangle marks the current viewport.

- **Pan:** drag the rectangle left or right.
- **Zoom:** drag the edges of the rectangle.
- **Stripes:** mirror the main plot — warm gray for exclusion zones,
  magenta for annotations.

**Toggle:** `View → Show overview bar`.

### Zoom presets

Three numeric jumps for common review windows:

| Key | Action |
|-----|--------|
| `1` | Last 1 minute |
| `2` | Last 10 minutes |
| `3` | Full recording |

Plus `R` to reset zoom to the full recording, `Home` to jump to the
first 60 s, `End` to jump to the last 60 s.

### Keyboard panning + zooming

| Key | Action |
|-----|--------|
| `←` / `→` | Pan 25% of the visible window |
| `↑` / `↓` | Zoom out / zoom in |

All keys work with focus on the plot.

---

## Content features

### Compare HRV curves

Overlay RR curves from multiple `.rrational` files side by side with
bootstrap confidence intervals. Open via `Tools → Compare HRV curves…`.

The dialog has:

- **Group A / Group B** dataset checklists (Group B is optional).
- **Confidence level** spinbox — default 95%.
- **Plot** button — renders the overlay in a new window.

The shaded band around each mean curve is the **bootstrap 95% CI** —
wider bands indicate more between-participant variability; non-
overlapping bands suggest a group difference worth testing formally
in the Analysis tab.

### Annotation stripes

When you enable **Annotation mode** (`A`) and drag a time range, the
range is recorded as a `(t_start, t_end, text)` annotation. Annotated
ranges show as **magenta stripes** in both the main plot and the
overview bar. Open the cross-recording annotation table from
`Tools → Annotations…`.

### Exclusion stripes

Same drag pattern but with **Exclusion mode** (`E`). Excluded ranges
are shown as **warm-gray stripes** and are skipped by every downstream
analysis. The exclusions are saved into the project's per-recording
metadata so they survive close/reopen.

---

## UI components

### Info dock

A right-side dock with metadata for the currently active dataset:
participant ID, group, sequence, beats count, duration, duplicates.
Toggle via `View → Show Info panel`.

### Participant grid

Multi-recording overview for batch review. Each tile shows a
mini-tachogram + key metrics; clicking a tile loads the recording into
the main view. Available in the **Participants** tab.

### Empty state widget

When no dataset is loaded, the central plot area shows a friendly
empty state with links to `File → Open project…` and `File → Import
from`. This replaces the previous "blank plot" UX.

### Workspace tree badges

In the left sidebar's workspace tree, each loaded dataset shows two
small badges:

- **Artifact count** — number of detected artifacts after correction.
- **Annotation count** — number of saved annotations.

Hover any row for the full file path tooltip.

---

## Status bar context

The bottom status bar carries three persistent indicators plus
context hints:

| Slot | Content |
|------|---------|
| Left | Project badge — click to switch projects |
| Center | Tab-specific hint (e.g. "Choose a metric preset to begin") |
| Right | Active dataset name + section count |

Context hints change on every tab switch via the internal
`_on_tab_changed_hint` handler.

---

## Full keyboard shortcuts reference

For the complete shortcut table see
[Inspector keyboard shortcuts](inspector-keyboard-shortcuts.md).
The most-used keys at a glance:

| Key | Action |
|-----|--------|
| `R` | Reset zoom to full recording |
| `1` / `2` / `3` | Jump to last 1 min / 10 min / full |
| `←` / `→` | Pan 25% of visible window |
| `↑` / `↓` | Zoom out / zoom in |
| `Home` / `End` | First / last 60 s |
| `A` | Toggle annotation mode |
| `E` | Toggle exclusion mode |
| `H` | Toggle HUD readout |
| `C` | Toggle crosshair |
| `Z` | Zen mode (HUD + crosshair off) |
| `F1` | Open keyboard shortcut reference |

---

## Where to next

- [Inspector workflows](inspector-workflows.md) — six end-to-end use
  cases (quick review, group comparison, presentation mode, …).
- [Inspector menu reference](../reference/inspector-menu-reference.md)
  — every menu item, dialog, and side-panel control documented.
- [Inspector keyboard shortcuts](inspector-keyboard-shortcuts.md) —
  printable cheat sheet.
