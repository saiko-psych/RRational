# Inspector Workflows

Six end-to-end recipes for the most common Inspector tasks. Each
workflow lists the exact menu items and keyboard shortcuts to use, so
you can follow it without prior tool familiarity.

For the underlying feature reference see
[Inspector features](inspector-features.md). For the Streamlit web app
side, see [Workflow](workflow.md).

---

## 1. Quick review of a single recording

You just received one `.rrational` file and want to eyeball the data
quality before kicking off any analysis.

1. `File → Open project…` and pick the project root (or skip if you
   are working without a project).
2. Drop the file into `data/processed/` if it isn't already there.
3. Double-click the file in the workspace tree or use
   `File → Open recent file…`.
4. Press `R` to reset the zoom to the full recording.
5. Press `Z` to enter Zen mode (HUD + crosshair off) for a clean look.
6. Skim the tachogram. Press `1` to drill into the last 1 min if
   something looks suspicious, then `3` to zoom back out.
7. If you spot a bad stretch, press `E` and drag-select the range —
   the warm-gray stripe records the exclusion automatically.

**Time budget:** 2–3 minutes per recording.

---

## 2. Multi-participant survey

You have a folder of recordings and need to know which ones are
high quality and which need rework.

1. Open the project — every detected file shows in the **Data** tab.
2. `Tools → Run preprocessing on all loaded recordings…` to detect
   artifacts across the whole batch.
3. When the batch finishes, the **Quality triage** dashboard opens.
   Sort by artifact percentage to find the worst recordings.
4. Switch to the **Participants** tab — the participant grid shows
   thumbnails of every recording.
5. Click a thumbnail to load that recording into the main view. Do a
   30-second visual sanity check, then move to the next.
6. Mark any unrecoverable recordings as excluded via the Data tab's
   per-row context menu.

**Time budget:** 1 minute per recording in the grid.

---

## 3. Group comparison

You want to visually compare two experimental groups before running
formal statistics.

1. Make sure every recording is tagged with its group (Setup tab →
   Groups pane → assign participants to a group).
2. Open `Tools → Compare HRV curves…`.
3. In the dialog:
   - Check the recordings for **Group A**.
   - Check the recordings for **Group B**.
   - Leave **Confidence level** at 95% unless your protocol differs.
4. Click **Plot**. The overlay opens in a new window with mean curves
   plus bootstrap CI bands.
5. Look for non-overlapping bands as a visual cue, then confirm any
   differences formally in the **Analysis** tab.

The Compare-curves overlay is a visual sanity check, not a hypothesis
test — always run the Analysis tab's between-group test before
reporting any difference.

---

## 4. Detailed review of one participant

A specific recording needs careful, beat-by-beat inspection.

1. Load the recording in the **Participant** tab.
2. On the right, the **Preprocessing** panel runs the Lipponen 2019
   detector when you click **Detect**. Orange X markers are flagged
   beats.
3. Press `H` to bring up the HUD readout — hover the cursor over a
   flagged beat to read off its `t / RR / HR` instantly.
4. Switch the panel to **Manual mark mode** to click individual beats
   that the detector missed.
5. Press `A` and drag a range over any region where you want to leave
   a written note — the magenta annotation stripe is saved per-recording.
6. Tick **Use corrected RR values** to switch the plot to the
   interpolated series.
7. Click **Save as .rrational** to write a v2 export with the
   corrections baked in.

---

## 5. Presentation mode

Building a slide deck or recording a video walkthrough.

1. Press `F11` to enter fullscreen.
2. Press `Z` for Zen mode — no HUD, no crosshair, just data.
3. Set the zoom to whatever window you want to show (`1 / 2 / 3` or
   manual scroll).
4. Use the OS screenshot tool, or for video, your screen-recording
   app of choice. The Inspector is single-window so there are no
   floating palettes in the recording.
5. Press `Z` again to bring the HUD back when you need to read off
   exact values during the recording.

Tip: switch to the **light** color scheme under
`Edit → Preferences → Color Scheme` for projector visibility.

---

## 6. Exploratory analysis

You want to poke around without committing to a hypothesis yet.

1. Open the project and a recording.
2. Use the **Overview bar** to scrub freely — drag the viewport
   rectangle, zoom by dragging its edges.
3. Try every visualization in the `Tools → Visualisation` submenu:
   Tachogram, Poincare plot, PSD plot, HR distribution. Each opens
   in its own window so you can have several up at once.
4. If something looks interesting, annotate it (`A` + drag) for
   future reference.
5. Use `Tools → Annotations…` to open the cross-recording table; sort
   and filter to surface patterns across your dataset.

---

## Inspector vs. Streamlit — best-practice cheat sheet

| Task | Inspector | Streamlit |
|------|-----------|-----------|
| Visual review of one recording | Best | OK |
| Per-beat artifact correction | Best | Limited |
| Compare HRV curves visually | Best | OK |
| Compute HRV metrics for one file | Good | Good |
| Group statistics (Friedman, RM-ANOVA) | Good | Best |
| Publication-ready HTML report | Good | Best |
| Quality triage across a folder | Best | OK |
| Reproducible CI/CD pipeline | Limited | Best |

Both apps share the same `project/config/` folder, so you can switch
between them without conversion.

---

## See also

- [Inspector features](inspector-features.md)
- [Inspector keyboard shortcuts](inspector-keyboard-shortcuts.md)
- [Inspector menu reference](../reference/inspector-menu-reference.md)
- [Streamlit workflow](workflow.md)
