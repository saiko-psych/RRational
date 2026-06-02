# PyQtGraph Signal Inspector — Plan

**Status**: planning (2026-06-02)
**Goal**: A standalone PyQt-based desktop signal inspector for RR data, modeled after MNE-LAB's smooth signal browser. Lives alongside the existing Streamlit app; both share the same backend code (`analysis/`, `cleaning/`, `io/`, `segments/`).

## Why a second GUI?

Streamlit's web-roundtrip model is fundamentally unsuited for sub-second interactive signal browsing (each keystroke = 1–2 s server reload, plot serialization). MNE-Python solved the same problem for EEG/MEG by adding a Qt-based browser ([`mne-qt-browser`](https://github.com/mne-tools/mne-qt-browser)) on top of [PyQtGraph](https://www.pyqtgraph.org/), which delivers 60 FPS scrolling over millions of samples on the GPU.

Streamlit stays the right tool for Group Analysis, statistics, multi-user web deployments, and export. The new inspector is explicitly **single-user desktop, designed for fluid per-beat review and artifact editing**.

## Architecture

```
src/rrational/
├── analysis/, cleaning/, io/, segments/   ← unchanged, both GUIs reuse
├── gui/                                   ← Streamlit (Group / Stats / Export)
└── inspector/                             ← NEW: PyQt desktop inspector
    ├── __main__.py
    ├── main_window.py
    ├── plot_widget.py
    ├── overlays.py        (sections, events, artifacts via mne-qt-browser items)
    ├── controllers/
    └── persistence_bridge.py    (read/write project YAMLs)
```

CLI:

- `rrational gui` — launches Streamlit (existing)
- `rrational inspect <project>` — launches PyQt inspector (new)

## Tech stack

- **PySide6** (LGPL — commercial-friendly with dynamic linking) via `qtpy` abstraction
- **PyQtGraph ≥ 0.13** for `PlotWidget`, `ViewBox`, `PlotDataItem`
- **mne-qt-browser ≥ 0.6** as an *optional* dependency — import `_graphic_items.AnnotRegion`, `VLine`, `EventLine`, `Crosshair`, `ScaleBar` to skip ~70% of the visual-polish work. Fallback to plain `pyqtgraph.InfiniteLine` if not installed.
- **pytest-qt** for headless GUI tests in CI

## License compatibility check (verified)

| Component | License | Note |
|-----------|---------|------|
| RRational | Apache-2.0 | — |
| MNE-Python | BSD-3 | Compatible with Apache-2.0 |
| mne-qt-browser | BSD-3 | Compatible with Apache-2.0 |
| MNELAB (reference) | BSD-3 | Compatible with Apache-2.0 |
| PyQtGraph | MIT | Compatible |
| PySide6 | LGPL | Compatible via dynamic linking (standard for PyQt apps) |

LGPL requires shipping the license notice in the bundle — that's already standard PyInstaller behavior.

## Performance budget

PyQtGraph with `setClipToView(True) + setDownsampling(auto=True, method='peak')` handles **1–10 million samples** at interactive frame rates ([SciPy 2023 paper](https://proceedings.scipy.org/articles/gerudo-f2bc6f59-00e)). RR tachograms are 1D with ~5k–50k beats per session — **trivially under the limit**. No need for OpenGL.

## MVP feature list

Phase-1 MVP (~21 working days estimate):

1. **Scrolling RR tachogram** — pan / zoom via Qt-native drag, scroll-zoom, keyboard (←/→/PgUp/PgDn/Home/End/Space)
2. **Section overlay** — show validated section ranges as colored `AnnotRegion`s
3. **Event markers** — vertical `EventLine` for every event in the project
4. **Artifact marking** — click a beat to flag as bad, drag-select range to flag bulk
5. **Persist to project YAML** — write back to `bad_beats.yml` and `section_validations.yml`
6. **Project loader** — file menu → "Open Project" reuses `rrational.io` parsers
7. **Theme** — read `color_scheme.py` so inspector matches Streamlit-side colors

Phase-2 (post-MVP):

- Multi-pane view (RR + HR + Poincaré in sync)
- Live spectrum (PSD updates while panning, like MNE-LAB's spectrogram pane)
- Annotation tool for music sections / experimental phases
- Comparative view (overlay two participants)

## Effort estimate (single developer)

| Phase | Work | Days |
|-------|------|------|
| 1 | Spike: PySide6 install, PlotWidget loading RR, scroll/zoom | 2 |
| 2 | Skeleton: `MainWindow`, file menu, color theme | 2 |
| 3 | Performance: `setClipToView`, downsampling, keyboard nav | 2 |
| 4 | Overlays: section regions, event lines | 3 |
| 5 | Artifact edit: click-to-mark, range-select, undo, persistence | 4 |
| 6 | CLI: `rrational inspect`, PyInstaller spec, CI matrix | 3 |
| 7 | Tests: `pytest-qt`, polish, docs | 3 |
| 8 | Buffer: macOS Qt signing, Linux Xvfb, Windows DPI | 2 |
| **Total** | | **~21 days** |

## Reference projects

- **[MNELAB](https://github.com/cbrnr/mnelab)** — solo-dev EEG analysis app, BSD-3, PySide6, PyInstaller-distributed, cross-platform. Architecture template for our inspector.
- **[mne-qt-browser](https://github.com/mne-tools/mne-qt-browser)** — Specifically [`_graphic_items.py`](https://github.com/mne-tools/mne-qt-browser/blob/main/src/mne_qt_browser/_graphic_items.py) for AnnotRegion / VLine / EventLine / Crosshair / ScaleBar.
- **[PyQtGraph docs — PlotDataItem](https://pyqtgraph.readthedocs.io/en/latest/api_reference/graphicsItems/plotdataitem.html)** for downsampling / clip-to-view API.

## Why NOT use mne-qt-browser as a drop-in

mne-qt-browser expects an `mne.io.Raw` object with `info['ch_names']`, `info['sfreq']`, regular sampling matrix `(n_channels, n_samples)`. RR intervals are irregularly sampled (cumulative time / beat index). Wrapping RR as fake Raw would either:

- (a) resample to 4 Hz uniform — loses beat-level editing precision, or
- (b) hack an irregular-time Raw — fights the framework

Our approach: **build a small custom PlotWidget for RR, but import `_graphic_items` classes** for the visual primitives. Saves ~70% of polish work without inheriting Raw's coupling.

## Open questions

1. **macOS notarization for Qt bundle** — currently bypassed for x86_64; needs revisit when shipping Qt
2. **Bundle-size impact** — Qt adds ~40–60 MB per platform. With current NeuroKit2+SciPy bundle this is noise but worth measuring
3. **Should `inspect` open a project, or accept a single `.rrational` file directly?** Project-first matches the Streamlit flow

## Decision needed before kick-off

- [ ] Confirm 4-week budget vs other priorities
- [ ] Decide: PySide6 or PyQt6 (both work; PySide6 has LGPL-only friendly licensing, PyQt6 is GPL/commercial dual)
- [ ] Confirm bundle-size hit is acceptable for the standalone build
