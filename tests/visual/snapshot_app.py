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
from qtpy.QtCore import QEventLoop, QTimer
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
    app = QApplication.instance() or QApplication(sys.argv)

    win = MainWindow()
    win.test_mode = True
    # Keep resolution under 2000px so the Read tool can display the PNGs
    # without rejecting them as too large.
    win.resize(1280, 800)
    win.show()
    app.processEvents()

    # Load a synthetic dataset so the participant view has content.
    win.add_dataset(_make_synthetic_dataset("0012MEBE.csv"))
    win.set_active_dataset(0)
    app.processEvents()
    _let_layout_settle(app)

    written: list[Path] = []
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
        pix = win.grab()
        # Force max-1600-wide so the Read tool can display the result.
        if pix.width() > 1600:
            from qtpy.QtCore import Qt as _Qt

            pix = pix.scaledToWidth(1600, mode=_Qt.SmoothTransformation)
        pix.save(str(path), "PNG")
        written.append(path)
        print(f"wrote {path}")

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
        pix = win.grab()
        if pix.width() > 1600:
            from qtpy.QtCore import Qt as _Qt

            pix = pix.scaledToWidth(1600, mode=_Qt.SmoothTransformation)
        pix.save(str(path), "PNG")
        written.append(path)
        print(f"wrote {path}")

    win.close()
    return written


if __name__ == "__main__":
    paths = snapshot_all_tabs()
    print(f"\nWrote {len(paths)} screenshots to {_OUT_DIR}")
