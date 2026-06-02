# Inspector Research Notes

Reference material from the architecture-research phase, compiled to guide the PyQtGraph inspector implementation. Each section is a TL;DR — link out for full source code.

## MNELAB architecture (primary template)

[MNELAB](https://github.com/cbrnr/mnelab) is a PySide6 wrapper around MNE-Python — structurally the closest match to what we're building. We borrow:

- **`@data_changed` decorator pattern** ([`mainwindow.py`](https://github.com/cbrnr/mnelab/blob/main/src/mnelab/mainwindow.py)): mutating methods wrap with `@data_changed` which calls `view.data_changed()` and sets the wait-cursor. Less boilerplate than manual Qt-Signal emission.
- **Dictionary-dispatch readers** ([`io/readers.py`](https://github.com/cbrnr/mnelab/blob/main/src/mnelab/io/readers.py)): `supported = {".edf": mne.io.read_raw_edf, ...}`. No factory classes, no plugin magic. We already do this in `rrational/io/generic_rr.py`.
- **`QSettings` + `_DEFAULTS` dict**: macOS plist / Windows registry / Linux INI via `QStandardPaths.AppConfigLocation`. JSON for complex values like annotation colors.
- **Recent-files menu with existence check**: purge dead entries on every refresh.
- **`standalone/` layout**: platform-specific PyInstaller specs + Inno Setup on Windows.
- **`dialogs/<operation>.py` convention**: one file per modal, exposes `get_values()`.
- **CI: `xvfb-run` for headless Linux**, not `QT_QPA_PLATFORM=offscreen` (more robust for plot tests).

## EDFbrowser keyboard model

[EDFbrowser](https://gitlab.com/Teuniz/EDFbrowser) is the gold standard for keyboard-driven multi-channel browsing. Our shortcut scheme follows its conventions:

| Key | Action |
|-----|--------|
| Left / Right | Scroll 1/10 of pagetime |
| Ctrl+Wheel | Time zoom |
| Ctrl++ / Ctrl+- | Change timescale |
| Ctrl+Home / Ctrl+End | Beginning / end of recording |
| F1–F12 | Switch montage / view |
| 1–8 | Quick-annotation (user-configurable) |
| Right-click | Hide/unhide annotation |

Source: [EDFbrowser manual](https://www.teuniz.net/edfbrowser/EDFbrowser%20manual.html).

## PyQtGraph anti-patterns to avoid

1. **`useOpenGL=True` is SLOWER on Windows**. [Issue #2227](https://github.com/pyqtgraph/pyqtgraph/issues/2227): GPU pipeline halved FPS (65 → 44). Default to `useOpenGL=False`, use `setDownsampling(auto=True, method='peak')` + `setClipToView(True)` instead. That's what mne-qt-browser does.
2. **Memory leaks on PlotItem add/remove**. [Issue #2665](https://github.com/pyqtgraph/pyqtgraph/issues/2665), [#2672](https://github.com/pyqtgraph/pyqtgraph/issues/2672). Solution: keep ONE persistent `PlotWidget` and call `setData()` to swap content — never destroy and recreate plot items.
3. **GUI freezes on file load**. Mitigation: `QThread` + `QObject` worker pattern. Worker emits `Signal(np.ndarray)`, main thread calls `setData()`. NEVER touch GUI widgets from worker thread.
4. **`autoRange` recalcs on every update**. [Issue #2328](https://github.com/pyqtgraph/pyqtgraph/issues/2328). Solution: `viewBox.disableAutoRange()` + explicit `setXRange(t0, t1, padding=0)` on scroll. Recalc Y only on explicit user trigger ("Fit Y" button).
5. **HiDPI font blur** on Windows 4K / mixed-DPI Linux. Solution: `pg.mkQApp()` sets recommended flags. For robustness, also `QGuiApplication.setHighDpiScaleFactorRoundingPolicy(PassThrough)`.

## Other OSS tools surveyed

- **[mne-qt-browser](https://github.com/mne-tools/mne-qt-browser)**: PyQtGraph-backend for MNE plotting. [Issue #161](https://github.com/mne-tools/mne-qt-browser/issues/161) — they tested "only visible annotations" vs "all annotations" and chose **all annotations** because faster for typical loads (<1000). Lesson: don't prematurely optimize annotation virtualization.
- **[SigViewer](https://github.com/cbrnr/sigviewer)**: Qt/C++ from same author as MNELAB. Confirms his architectural decision to split heavy C++ viewer from Python-GUI orchestrator. We stay Python-only.
- **[PhysioZoo](https://github.com/physiozoo/physiozoo)**: HRV-specific (MATLAB+Python). Strength: explicit per-species config (dog, rabbit, mouse). We can mirror: per-device config (Polar / Empatica / VNS).
- **[gHRV](https://github.com/milegroup/ghrv)**: wxPython, older. Module naming worth borrowing: separate `EditEpisodes.py` (event/section markup) from `EditNIHR.py` (R-peak correction). Clean separation of "what happened when" vs "fix the signal".
- **[pyHRV](https://github.com/PGomes92/pyhrv)**: no GUI — useful only for formula reference, not plot code (matplotlib, too slow).
- **[NeuroDSP](https://github.com/neurodsp-tools/neurodsp)**: functional-modular layout (`filt/`, `spectral/`, `timefrequency/`, `burst/`, `rhythm/`, `sim/`, `plts/`) — submodule template.
- **[Brainstorm](https://github.com/brainstorm-tools/brainstorm3)** (MATLAB): protocol → subject → recording hierarchy moved from struct files to **SQLite** in v4. Lesson: if we grow past ~100 recordings per project, consider SQLite over YAML.

## PyQtGraph examples to crib from

From `pyqtgraph/examples/`:

- **`PlotSpeedTest.py`** — benchmark reference for our decimation. Shows `setDownsampling(auto=True, method='peak'|'mean'|'subsample')` impact.
- **`crosshair.py`** — direct code for X/Y readout at cursor (standard feature).
- **`InfiniteLine.py`** — `pg.InfiniteLine` movable → ideal for event markers / cursors.
- **`customGraphicsItem.py`** — template for custom annotations if `LinearRegionItem` isn't enough.
- **`ImageView.py`** — basis if we want a spectrogram pane in Phase 2.

## Inspector file layout (planned)

Adapted from MNELAB's structure:

```
rrational/inspector/
├── __main__.py                  # python -m rrational.inspector entry
├── app.py                       # QApplication + run()
├── main_window.py               # QMainWindow, menus, splitter
├── model.py                     # @data_changed decorator + Model
├── settings.py                  # QSettings + _DEFAULTS
├── plot_widget.py               # PyQtGraph PlotWidget (CORE)
├── widgets/
│   ├── sidebar.py               # tree of recordings/sections
│   ├── info.py                  # metadata panel
│   ├── overview_bar.py          # mini-map (like mne-qt-browser)
│   └── annot_region.py          # LinearRegionItem subclass
├── dialogs/
│   ├── edit_peaks.py            # R-peak correction (à la gHRV EditNIHR)
│   ├── edit_episodes.py         # episode/event markup (à la gHRV)
│   └── settings.py
├── workers/
│   ├── file_loader.py           # QThread file I/O
│   └── hrv_compute.py
└── standalone/
    ├── inspector-macos.spec
    ├── inspector-windows.iss
    └── create-standalone-*.sh
```

## Sources

Full bibliography at the bottom of [docs/development/inspector-plan.md](./inspector-plan.md).
