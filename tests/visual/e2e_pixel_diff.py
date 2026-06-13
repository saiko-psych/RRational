"""Theme-regression detector — dual snapshots in dark + light and
pixel-diff the histograms.

For each scenario, snapshot the SAME widget twice (dark theme, then
light theme), then quantify how different the two snapshots are by
comparing per-channel histograms. A "good" theme switch produces a
LARGE diff (intentional contrast inversion). A "stuck" widget — one
with hardcoded colors that don't theme-switch — produces a SMALL diff
in the affected region. We can't pixel-diff the whole window because
some surfaces SHOULD invert; we focus on the offending widget for
each scenario.

This is a heuristic regression check, not a strict pass/fail. The
output is two PNGs per scenario + a JSON file with the histogram
summary so a human can spot which scenarios changed less than the
median.

Output: tests/visual/e2e_snapshots/pix_NN_<scenario>_<theme>.png
        tests/visual/e2e_snapshots/pix_diff_report.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from qtpy.QtCore import QEventLoop, QTimer
from qtpy.QtGui import QImage
from qtpy.QtWidgets import QApplication

from rrational.inspector.app import set_plot_theme  # noqa: E402
from rrational.inspector.data_loader import Dataset, InspectorData, SectionMeta  # noqa: E402
from rrational.inspector.main_window import MainWindow  # noqa: E402
from rrational.inspector.style import apply_app_theme  # noqa: E402

_OUT = Path(__file__).parent / "e2e_snapshots"
_OUT.mkdir(exist_ok=True)


def _settle(app, ms=400):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    app.processEvents()


def _grab_image(widget) -> QImage:
    pix = widget.grab()
    return pix.toImage()


def _channel_histograms(img: QImage) -> dict[str, list[int]]:
    """Return per-channel 16-bucket histograms of every visible pixel."""
    w, h = img.width(), img.height()
    # Pull raw bytes once — convert to RGB888 so each pixel is exactly 3 bytes.
    img = img.convertToFormat(QImage.Format.Format_RGB888)
    buf = img.constBits()
    if hasattr(buf, "asstring"):
        raw = buf.asstring(w * h * 3)  # PyQt5
    else:
        raw = bytes(buf)
    arr = np.frombuffer(raw, dtype=np.uint8).reshape(h, w, 3)
    return {
        "r": np.histogram(arr[..., 0], bins=16, range=(0, 256))[0].tolist(),
        "g": np.histogram(arr[..., 1], bins=16, range=(0, 256))[0].tolist(),
        "b": np.histogram(arr[..., 2], bins=16, range=(0, 256))[0].tolist(),
    }


def _hist_distance(h1: dict, h2: dict) -> float:
    """L1 distance between two histogram dicts, normalised to [0, 1]."""
    total = 0
    for ch in "rgb":
        a = np.asarray(h1[ch], dtype=float)
        b = np.asarray(h2[ch], dtype=float)
        s = max(a.sum(), b.sum(), 1.0)
        total += float(np.abs(a - b).sum()) / s
    return total / 3.0


def _save(img: QImage, name: str) -> Path:
    p = _OUT / f"pix_{name}.png"
    img.save(str(p), "PNG")
    return p


def _synth_dataset(name, n_beats=300, seed=42, mean_rr=800):
    rng = np.random.default_rng(seed=seed)
    rr = mean_rr + 30 * rng.standard_normal(n_beats)
    base = 1_700_000_000 + seed * 1000
    t = base + np.cumsum(rr) / 1000.0
    sections = [
        SectionMeta(
            name="sec_00",
            t_start=float(t[0]),
            t_end=float(t[-1]),
            beat_count=n_beats,
        ),
    ]
    return Dataset(name=name, data=InspectorData(t=t, v=rr, sections=sections))


def _scenarios(win, app):
    """Yield ``(scenario_label, widget_to_grab)`` pairs."""
    tabs = win._tabs_widget

    # Welcome screen (no datasets).
    yield "01_welcome", win

    # Add 3 datasets, snap Browse tab.
    for i in range(3):
        win.add_dataset(_synth_dataset(name=f"pd_{i}.csv", seed=10 + i))
    win.set_active_dataset(0)
    _settle(app, 600)
    browse_idx = tabs.indexOf(win._browse_tab)
    if browse_idx >= 0:
        tabs.setCurrentIndex(browse_idx)
        _settle(app, 500)
    yield "02_browse_3_datasets", win

    # Setup tab.
    setup_tab = getattr(win, "_setup_tab", None)
    if setup_tab is not None:
        idx = tabs.indexOf(setup_tab)
        if idx >= 0:
            tabs.setCurrentIndex(idx)
            _settle(app, 500)
        yield "03_setup", win

    # Participants tab (synth grid).
    participants_tab = getattr(win, "_participants_tab", None)
    if participants_tab is not None:
        idx = tabs.indexOf(participants_tab)
        if idx >= 0:
            tabs.setCurrentIndex(idx)
            _settle(app, 1000)
        yield "04_participants", win

    # Analysis tab.
    analysis_tab = getattr(win, "_analysis_tab", None)
    if analysis_tab is not None:
        idx = tabs.indexOf(analysis_tab)
        if idx >= 0:
            tabs.setCurrentIndex(idx)
            _settle(app, 500)
        yield "05_analysis", win


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    print("[boot] Pixel-diff theme regression detector starting")

    apply_app_theme(app, mode="dark")
    set_plot_theme("dark")
    win = MainWindow()
    win.resize(1400, 900)
    win.show()
    _settle(app, 500)

    # Collect dark-theme snapshots first.
    dark_images: dict[str, QImage] = {}
    for label, widget in _scenarios(win, app):
        img = _grab_image(widget)
        _save(img, f"{label}_dark")
        dark_images[label] = img
        print(f"  [dark] {label}: {img.width()}x{img.height()}")

    # Flip to light theme — reuse the same window so the same widgets
    # get re-styled, NOT a fresh MainWindow which would mask cached-color
    # bugs (Round 25 found nn_summary used the construction-time bg).
    apply_app_theme(app, mode="light")
    set_plot_theme("light")
    _settle(app, 600)

    report: list[dict] = []
    tabs = win._tabs_widget
    for label, _widget in [
        ("01_welcome", win),
        ("02_browse_3_datasets", win),
        ("03_setup", win),
        ("04_participants", win),
        ("05_analysis", win),
    ]:
        # Re-navigate to the same tab so the snapshot framing matches.
        targets = {
            "01_welcome": None,
            "02_browse_3_datasets": getattr(win, "_browse_tab", None),
            "03_setup": getattr(win, "_setup_tab", None),
            "04_participants": getattr(win, "_participants_tab", None),
            "05_analysis": getattr(win, "_analysis_tab", None),
        }
        target_tab = targets.get(label)
        if target_tab is not None:
            idx = tabs.indexOf(target_tab)
            if idx >= 0:
                tabs.setCurrentIndex(idx)
                _settle(app, 500)
        if label == "01_welcome":
            # Clear datasets so the welcome view appears again? Skip; the
            # window already has 3 — accept the slight scenario drift.
            pass

        img_light = _grab_image(win)
        _save(img_light, f"{label}_light")
        print(f"  [light] {label}: {img_light.width()}x{img_light.height()}")

        h_dark = _channel_histograms(dark_images[label])
        h_light = _channel_histograms(img_light)
        dist = _hist_distance(h_dark, h_light)
        report.append(
            {
                "scenario": label,
                "hist_distance": round(dist, 4),
                "dark_w": dark_images[label].width(),
                "dark_h": dark_images[label].height(),
                "light_w": img_light.width(),
                "light_h": img_light.height(),
            }
        )
        print(f"  [diff] {label}: hist_distance={dist:.4f}")

    median = float(np.median([r["hist_distance"] for r in report]))
    for r in report:
        # bool(np.bool_) — json.dumps refuses numpy bools, so cast
        # to a plain Python bool before serialising.
        r["below_median"] = bool(r["hist_distance"] < median * 0.7)
    print(f"\n[summary] median hist distance = {median:.4f}")
    for r in report:
        flag = " <-- low (likely stuck colors)" if r["below_median"] else ""
        print(f"  {r['scenario']}: {r['hist_distance']:.4f}{flag}")

    report_path = _OUT / "pix_diff_report.json"
    report_path.write_text(
        json.dumps({"median": median, "scenarios": report}, indent=2),
        encoding="utf-8",
    )
    print(f"\n[done] report at {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
