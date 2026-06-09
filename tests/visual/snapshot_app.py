"""Visual snapshot harness — opens MainWindow off-screen and saves
PNG screenshots of every tab so the developer can eyeball-verify the
layout without running the app interactively.

Run:
    uv run python tests/visual/snapshot_app.py

Outputs go to ``tests/visual/snapshots/<tab>.png``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from qtpy.QtCore import QEventLoop, Qt, QTimer
from qtpy.QtWidgets import QApplication

# Import early so the inspector lazy-imports inside MainWindow find them
from rrational.inspector.data_loader import (  # noqa: E402  (deliberate ordering)
    Dataset,
    EventMeta,
    InspectorData,
    SectionMeta,
)
from rrational.inspector.main_window import MainWindow  # noqa: E402


_OUT_DIR = Path(__file__).parent / "snapshots"
_OUT_DIR.mkdir(exist_ok=True)

_MAX_WIDTH = 1600


def _let_layout_settle(app: QApplication, ms: int = 200) -> None:
    """Bug B4: actually wait for the dock layout + pyqtgraph plot to
    finish laying out.

    A handful of ``processEvents()`` calls is not enough on Windows when
    a tab containing a nested ``QMainWindow`` + ``QDockWidget``s + a
    pyqtgraph widget is shown for the first time — the dock area can
    still be mid-resize when ``QWidget.grab()`` runs, producing a
    captured frame where the central plot pane is rendered at a sliver
    of its final width. A real event-loop timer guarantees Qt has
    finished its deferred layout passes before we grab.
    """
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    app.processEvents()


def _save_grab(win: MainWindow, path: Path) -> None:
    """Grab the window, downscale to <=1600px wide, save PNG."""
    pix = win.grab()
    if pix.width() > _MAX_WIDTH:
        pix = pix.scaledToWidth(_MAX_WIDTH, mode=Qt.SmoothTransformation)
    pix.save(str(path), "PNG")
    print(f"wrote {path}")


def _make_synthetic_dataset(name: str) -> Dataset:
    """Build a realistic-ish dataset so the participant view actually renders."""
    n = 600
    rng = np.random.default_rng(seed=42)
    rr_ms = 800 + 30 * rng.standard_normal(n)
    base = 1_700_000_000
    t = base + np.cumsum(rr_ms) / 1000.0
    sections = [
        SectionMeta(
            name="rest_pre",
            t_start=float(t[0]),
            t_end=float(t[199]),
            beat_count=200,
        ),
        SectionMeta(
            name="music",
            t_start=float(t[200]),
            t_end=float(t[399]),
            beat_count=200,
        ),
        SectionMeta(
            name="rest_post",
            t_start=float(t[400]),
            t_end=float(t[-1]),
            beat_count=200,
        ),
    ]
    events = [
        EventMeta(label="rest_pre_start", t=float(t[0])),
        EventMeta(label="music_start", t=float(t[200])),
        EventMeta(label="music_end", t=float(t[399])),
    ]
    data = InspectorData(t=t, v=rr_ms, sections=sections, events=events)
    return Dataset(name=name, data=data)


def snapshot_all_tabs() -> list[Path]:
    # Wipe stale PNGs so removed snapshots don't linger and confuse
    # eyeball-verification. Cheap because the dir only has a few dozen
    # files at most.
    for old in _OUT_DIR.glob("*.png"):
        try:
            old.unlink()
        except OSError:
            pass

    app = QApplication.instance() or QApplication(sys.argv)
    # Mirror app.run(): the Refined Laboratory QSS theme must be applied
    # BEFORE the first widget renders, otherwise the snapshot captures
    # the unstyled Qt default look instead of the production theme.
    from rrational.inspector.style import apply_app_theme

    apply_app_theme(app, mode="dark")

    win = MainWindow()
    win.test_mode = True
    # Keep resolution under 2000px so the Read tool can display the PNGs
    # without rejecting them as too large.
    win.resize(1280, 800)
    win.show()
    app.processEvents()

    written: list[Path] = []

    # Pass A — Welcome state: MainWindow shows BrowseTab with the
    # WelcomeWidget (incl. "Try with sample data" button) when no
    # datasets are loaded. Captured BEFORE add_dataset(), otherwise the
    # welcome panel is hidden and replaced by the plot.
    _let_layout_settle(app, 200)
    welcome_path = _OUT_DIR / "welcome_00_no_dataset.png"
    _save_grab(win, welcome_path)
    written.append(welcome_path)

    # Load a synthetic dataset so the participant view has content.
    win.add_dataset(_make_synthetic_dataset("0012MEBE.csv"))
    win.set_active_dataset(0)
    app.processEvents()
    _let_layout_settle(app)

    tabs = win._tabs_widget
    for i in range(tabs.count()):
        if not tabs.isTabVisible(i):
            continue
        tabs.setCurrentIndex(i)
        app.processEvents()
        # Let layout settle — dock area + pyqtgraph need a real timer,
        # not just a burst of processEvents (Bug B4).
        _let_layout_settle(app)
        widget_name = type(tabs.widget(i)).__name__
        path = _OUT_DIR / f"tab_{i:02d}_{widget_name}.png"
        _save_grab(win, path)
        written.append(path)

    # Pass C — Single-pane Compute (F6): trigger a real compute on the
    # AnalysisTab's single-participant pane and snap each plot tab so
    # the populated Tachogram / Poincare / PSD / HR-distribution views
    # are visually verifiable. Wrapped in try/except because synthetic
    # data shape changes or settings-bar drift would otherwise crash
    # the whole harness.
    ana_tab = getattr(win, "_analysis_tab", None)
    single_pane = (
        getattr(ana_tab, "_single_pane", None) if ana_tab is not None else None
    )
    if single_pane is not None:
        try:
            # Make sure the AnalysisTab is the current tab so the grab
            # captures the populated plot panel.
            ana_idx = tabs.indexOf(ana_tab)
            if ana_idx >= 0 and tabs.isTabVisible(ana_idx):
                tabs.setCurrentIndex(ana_idx)
                _let_layout_settle(app, 200)
            ds_combo = getattr(single_pane, "_dataset_combo", None)
            sec_combo = getattr(single_pane, "_section_combo", None)
            if ds_combo is not None and ds_combo.count() > 0:
                ds_combo.setCurrentIndex(0)
            if sec_combo is not None and sec_combo.count() > 0:
                sec_combo.setCurrentIndex(0)
            app.processEvents()
            single_pane._on_compute()
            _let_layout_settle(app, 500)

            plot_tabs = getattr(single_pane, "_plot_tabs", None)
            if plot_tabs is not None:
                for i in range(plot_tabs.count()):
                    plot_tabs.setCurrentIndex(i)
                    _let_layout_settle(app, 200)
                    name = plot_tabs.tabText(i).replace(" ", "_")
                    path = _OUT_DIR / f"analysis_compute_plot_{name}.png"
                    _save_grab(win, path)
                    written.append(path)
        except Exception as exc:  # noqa: BLE001 — harness must not crash
            print(f"skipped F6 plot capture: {exc!r}")

    # MNE-LAB mode for comparison
    win.set_ui_layout("mnelab")
    app.processEvents()
    _let_layout_settle(app)
    for i in range(tabs.count()):
        if not tabs.isTabVisible(i):
            continue
        tabs.setCurrentIndex(i)
        app.processEvents()
        # See note above (Bug B4): real timer beats processEvents bursts.
        _let_layout_settle(app)
        widget_name = type(tabs.widget(i)).__name__
        path = _OUT_DIR / f"mnelab_{i:02d}_{widget_name}.png"
        _save_grab(win, path)
        written.append(path)

    # Pass B — Streamlit-mode DataTab: in Streamlit layout DataTab is
    # the default first tab, but it can be skipped by the visible-tab
    # iteration above (e.g. if hidden by future layout tweaks). Capture
    # it explicitly so V1 is always represented in the snapshot set.
    win.set_ui_layout("streamlit")
    app.processEvents()
    _let_layout_settle(app, 300)
    for i in range(tabs.count()):
        if not tabs.isTabVisible(i):
            continue
        tabs.setCurrentIndex(i)
        app.processEvents()
        _let_layout_settle(app)
        widget_name = type(tabs.widget(i)).__name__
        path = _OUT_DIR / f"streamlit_{i:02d}_{widget_name}.png"
        _save_grab(win, path)
        written.append(path)

    data_tab = getattr(win, "_data_tab", None)
    if data_tab is not None:
        try:
            data_idx = tabs.indexOf(data_tab)
            if data_idx >= 0:
                # Force-visible just for this snapshot if the layout
                # decided to hide DataTab — otherwise setCurrentIndex
                # silently no-ops on an invisible tab.
                was_visible = tabs.isTabVisible(data_idx)
                if not was_visible:
                    tabs.setTabVisible(data_idx, True)
                tabs.setCurrentIndex(data_idx)
                _let_layout_settle(app, 300)
                path = _OUT_DIR / "streamlit_data_tab_explicit.png"
                _save_grab(win, path)
                written.append(path)
                if not was_visible:
                    tabs.setTabVisible(data_idx, False)
        except Exception as exc:  # noqa: BLE001
            print(f"skipped explicit DataTab capture: {exc!r}")

    # Pass D — Round-8 MNE-inspired dialogs. Each one is opened
    # programmatically against the synthetic dataset that's already in
    # the workspace so we can grab the chrome (table contents, summary
    # line, sort indicators) without needing a real project on disk.
    # Wrapped per-dialog so a single failure doesn't sink the rest.

    # Quality triage with a hand-built sample BatchResult set covering
    # all four grades + an unknown row.
    try:
        from rrational.inspector.quality_triage_dialog import (
            BatchResult,
            QualityTriageDialog,
        )

        sample_results = [
            BatchResult("0001CTRL.csv", 5210, 87, 0.0167, "A", "data/0001.rrational"),
            BatchResult("0002EXPR.csv", 4980, 162, 0.0325, "B", "data/0002.rrational"),
            BatchResult("0003CTRL.csv", 5620, 412, 0.0733, "C", None),
            BatchResult("0004CTRL.csv", 3105, 401, 0.1291, "D", None),
            BatchResult("0005EXPR.csv", 280, 0, 0.0, "?", None),
        ]
        qt_dlg = QualityTriageDialog(sample_results, parent=win)
        qt_dlg.resize(900, 480)
        qt_dlg.show()
        _let_layout_settle(app, 250)
        path = _OUT_DIR / "round8_quality_triage_dialog.png"
        _save_grab(qt_dlg, path)
        written.append(path)
        qt_dlg.close()
    except Exception as exc:  # noqa: BLE001
        print(f"skipped quality triage capture: {exc!r}")

    # Annotation table opened against the loaded dataset(s). Empty by
    # design — the synthetic dataset has no on-disk annotations — but
    # captures the toolbar, the "Show:" filter, the column headers, and
    # the empty-state body.
    try:
        from rrational.inspector.annotation_table_dialog import (
            AnnotationTableDialog,
        )

        at_dlg = AnnotationTableDialog(win, parent=win)
        at_dlg.resize(900, 480)
        at_dlg.show()
        _let_layout_settle(app, 250)
        path = _OUT_DIR / "round8_annotation_table_dialog.png"
        _save_grab(at_dlg, path)
        written.append(path)
        at_dlg.close()
    except Exception as exc:  # noqa: BLE001
        print(f"skipped annotation table capture: {exc!r}")

    win.close()
    return written


if __name__ == "__main__":
    paths = snapshot_all_tabs()
    print(f"\nWrote {len(paths)} screenshots to {_OUT_DIR}")
