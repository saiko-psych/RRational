"""Minimal repro for the 'plot stays empty after loading a real RR file' bug.

Loads ONE real HRV Logger _RRIntervals.csv and snapshots the BrowseTab plot
at every step so we can pin down whether the data ever reaches the plot
widget, whether it renders, and whether a fresh paint cycle ever fires.
"""

from __future__ import annotations

import sys
from pathlib import Path

from qtpy.QtCore import QEventLoop, QTimer
from qtpy.QtWidgets import QApplication

from rrational.inspector.app import set_plot_theme  # noqa: E402
from rrational.inspector.data_loader import Dataset  # noqa: E402
from rrational.inspector.main_window import MainWindow  # noqa: E402
from rrational.inspector.style import apply_app_theme  # noqa: E402

_OUT = Path(__file__).parent / "e2e_snapshots"
_OUT.mkdir(exist_ok=True)

RR_FILE = Path(
    "C:/Users/David/Nextcloud2/Documents/Uni Graz/Praxis Master/test_project"
    "/data/raw/hrv_logger/0405SAAD_170325_MEL_0.00-0.40_RRIntervals.csv"
)


def _settle(app, ms=600):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    app.processEvents()


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    apply_app_theme(app, mode="dark")
    set_plot_theme("dark")

    print(f"[boot] RR_FILE.exists = {RR_FILE.exists()}")
    if not RR_FILE.exists():
        return 1

    # First, parse the file to InspectorData and inspect its shape
    print("\n[parse] Dataset.from_path(RR_FILE)")
    ds = Dataset.from_path(RR_FILE)
    data = ds.data
    print(f"  name = {ds.name}")
    print(f"  len(t) = {len(data.t)}")
    print(f"  t[:3] = {list(data.t[:3])}")
    print(f"  t[-3:] = {list(data.t[-3:])}")
    print(f"  v[:3] = {list(data.v[:3])}")
    print(f"  v[-3:] = {list(data.v[-3:])}")
    print(f"  v.min/max = {data.v.min():.1f} / {data.v.max():.1f}")
    print(f"  sections = {len(data.sections)}")
    print(f"  events = {len(data.events)}")
    print(f"  t_start={data.t_start}  t_end={data.t_end}")

    win = MainWindow()
    win.resize(1600, 1000)
    win.show()
    win.setGeometry(20, 20, 1600, 1000)
    _settle(app, 800)
    win.grab().save(str(_OUT / "repro_01_boot.png"), "PNG")
    print("\n[snap] repro_01_boot.png")

    # Force a BrowseTab focus before loading so the nested QMainWindow
    # in the tab gets a real paint pass that sizes the central plot pane.
    tabs = win._tabs_widget
    browse_idx = tabs.indexOf(win._browse_tab)
    print(f"[layout] browse tab index = {browse_idx}")
    if browse_idx >= 0:
        tabs.setCurrentIndex(browse_idx)
    _settle(app, 600)
    win.grab().save(str(_OUT / "repro_02_browse_focused.png"), "PNG")
    print("[snap] repro_02_browse_focused.png")

    print("\n[load] win.open_path(RR_FILE)")
    idx = win.open_path(RR_FILE)
    print(f"  returned idx = {idx}")
    print(f"  active_idx = {win._active_idx}")
    print(f"  dataset count = {len(win._datasets)}")
    print(f"  browse._plot.isVisible = {win._browse_tab._plot.isVisible()}")
    print(f"  browse._plot._times is None = {win._browse_tab._plot._times is None}")
    if win._browse_tab._plot._times is not None:
        t_arr = win._browse_tab._plot._times
        print(f"  browse._plot._times.shape = {t_arr.shape}")
        print(
            f"  browse._plot.viewRange = "
            f"{win._browse_tab._plot.getViewBox().viewRange()}"
        )
        plot = win._browse_tab._plot
        print(f"  plot.size() = {plot.size().width()}x{plot.size().height()}")
        print(f"  plot.isVisible = {plot.isVisible()}")
        print(f"  plot.parent = {plot.parent()}")
        print(
            f"  plot.parentWidget.size = "
            f"{plot.parentWidget().size().width() if plot.parentWidget() else 'None'}"
        )
        vb = plot.getViewBox()
        print(f"  viewbox.boundingRect = {vb.boundingRect()}")
        # Maybe the welcome widget keeps its size policy reserving space
        welcome = win._browse_tab._welcome_widget
        print(
            f"  welcome.isVisible={welcome.isVisible()} size="
            f"{welcome.size().width()}x{welcome.size().height()}"
        )
        # Force layout invalidation
        mid_pane = plot.parentWidget()
        if mid_pane is not None:
            mid_pane.updateGeometry()
            mid_pane.layout().invalidate() if mid_pane.layout() else None
        # Force window-wide relayout
        win.adjustSize()
        win.resize(1600, 1000)
        _settle(app, 500)
        print(
            f"  AFTER relayout plot.size = {plot.size().width()}x{plot.size().height()}"
        )

    _settle(app, 800)
    win.grab().save(str(_OUT / "repro_03_after_load.png"), "PNG")
    print("[snap] repro_03_after_load.png")

    # Force a re-render explicitly in case set_active_dataset didn't fire
    print("\n[force] _browse_tab._render_dataset() explicitly")
    if win._datasets:
        try:
            win._browse_tab._render_dataset(win._datasets[0])
        except Exception as e:
            print(f"  [FAIL] {type(e).__name__}: {e}")
    _settle(app, 800)
    win.grab().save(str(_OUT / "repro_04_force_render.png"), "PNG")
    print("[snap] repro_04_force_render.png")

    # Manual viewport reset
    print("\n[reset] viewport autoRange")
    try:
        win._browse_tab._plot.getViewBox().autoRange()
    except Exception as e:
        print(f"  [FAIL] {type(e).__name__}: {e}")
    _settle(app, 600)
    win.grab().save(str(_OUT / "repro_05_after_autoRange.png"), "PNG")
    print("[snap] repro_05_after_autoRange.png")

    print("\n[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
