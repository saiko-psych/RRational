"""Radical/edge-case E2E — pathological data + dramatic interactions.

Hunts the bugs visual inspection of "normal" workflows would never
catch: empty workspaces, 1-beat datasets, all-NaN values, 100-dataset
stress, identical-RR (zero variance), rapid tab smashing, Holter-scale
recordings, malformed CSV, dramatic resize churn.

Output: tests/visual/e2e_snapshots/rad_NN_<scenario>.png
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import numpy as np
from qtpy.QtCore import QEventLoop, Qt, QTimer
from qtpy.QtWidgets import QApplication

from rrational.inspector.app import set_plot_theme  # noqa: E402
from rrational.inspector.data_loader import (  # noqa: E402
    Dataset,
    EventMeta,
    InspectorData,
    SectionMeta,
)
from rrational.inspector.main_window import MainWindow  # noqa: E402
from rrational.inspector.style import apply_app_theme  # noqa: E402

_OUT = Path(__file__).parent / "e2e_snapshots"
_OUT.mkdir(exist_ok=True)


def _settle(app, ms=400):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    app.processEvents()


def _snap(widget, name, note=""):
    path = _OUT / f"rad_{name}.png"
    pix = widget.grab()
    if pix.width() > 1200 or pix.height() > 900:
        pix = pix.scaled(1200, 900, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    pix.save(str(path), "PNG")
    suffix = f" -- {note}" if note else ""
    print(f"[snap] {path.name} {pix.width()}x{pix.height()}{suffix}")


def _try(label, fn):
    try:
        return fn()
    except Exception as exc:
        print(f"[FAIL] {label}: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------
# Pathological dataset factories
# ---------------------------------------------------------------------


def _one_beat_dataset() -> Dataset:
    """Single RR interval — every windowed metric should degenerate.

    Round 28 — fixture had mismatched shapes (t=2, v=1) which now
    correctly fails the Round 24 InspectorData validation guard. Use
    matching one-element arrays so we still exercise the n=1 edge case
    without tripping the dimension check.
    """
    t = np.array([0.0])
    v = np.array([800.0])
    return Dataset(name="degenerate_1_beat.csv", data=InspectorData(t=t, v=v))


def _all_nan_dataset() -> Dataset:
    """All values are NaN — should NOT crash mean/std/HRV/HR computations."""
    t = np.linspace(0, 100, 200)
    v = np.full(200, np.nan)
    return Dataset(name="all_nan.csv", data=InspectorData(t=t, v=v))


def _identical_rr_dataset() -> Dataset:
    """Zero-variance RR (perfect metronome) — RMSSD=0, SDNN=0."""
    rr = np.full(500, 850.0)
    t = np.cumsum(np.concatenate(([0], rr[:-1] / 1000.0)))
    return Dataset(name="identical_rr.csv", data=InspectorData(t=t, v=rr))


def _holter_dataset() -> Dataset:
    """24h-Holter-scale: ~86k beats, 60 sections, 200 events."""
    rng = np.random.default_rng(seed=999)
    n_beats = 86_400
    rr = 800 + 80 * rng.standard_normal(n_beats)
    t = np.cumsum(rr) / 1000.0
    sections = []
    step = n_beats // 60
    for i in range(60):
        a = i * step
        b = (i + 1) * step - 1
        sections.append(
            SectionMeta(
                name=f"hour_{i // 5:02d}_seg_{i % 5}",
                t_start=float(t[a]),
                t_end=float(t[b]),
                beat_count=b - a + 1,
            )
        )
    events = [EventMeta(label=f"evt_{i:03d}", t=float(t[i * 432])) for i in range(200)]
    return Dataset(
        name="holter_24h_simulated.csv",
        data=InspectorData(t=t, v=rr, sections=sections, events=events),
    )


def _extreme_outlier_dataset() -> Dataset:
    """Mostly normal RR with 5 wild outliers (sensor dropouts)."""
    rng = np.random.default_rng(seed=42)
    rr = 800 + 30 * rng.standard_normal(2000)
    # Inject extreme outliers — 50ms (>1000 BPM) and 5000ms (12 BPM).
    rr[100] = 50.0
    rr[500] = 5000.0
    rr[1000] = 30.0
    rr[1500] = 4500.0
    rr[1900] = 25.0
    t = np.cumsum(rr) / 1000.0
    return Dataset(name="extreme_outliers.csv", data=InspectorData(t=t, v=rr))


def _negative_rr_dataset() -> Dataset:
    """Negative RR values — physically impossible. Should be rejected or
    flagged, not silently rendered as upside-down tachogram."""
    rng = np.random.default_rng(seed=7)
    rr = 800 + 30 * rng.standard_normal(300)
    # Flip 10% of the values negative.
    flip_idx = rng.choice(300, size=30, replace=False)
    rr[flip_idx] *= -1
    t = np.cumsum(np.abs(rr)) / 1000.0
    return Dataset(name="negative_rr.csv", data=InspectorData(t=t, v=rr))


def _zero_length_dataset() -> Dataset:
    """Empty arrays — boundary case for layout code that expects a range."""
    return Dataset(name="empty.csv", data=InspectorData(t=np.array([]), v=np.array([])))


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    apply_app_theme(app, mode="dark")
    set_plot_theme("dark")

    print("[boot] Radical/edge-case E2E starting")
    win = MainWindow()
    win.resize(1600, 1000)
    win.show()
    _settle(app, 400)
    _snap(win, "01_empty_workspace", "no datasets, no project")

    # ----- Scenario 1: One-beat dataset --------------------------------
    print("\n[1] one-beat dataset")
    ds = _one_beat_dataset()
    _try("add 1-beat", lambda: win.add_dataset(ds))
    _try("activate 1-beat", lambda: win.set_active_dataset(0))
    _settle(app, 400)
    _snap(win, "02_one_beat", "single RR interval")

    # ----- Scenario 2: All-NaN dataset ---------------------------------
    print("\n[2] all-NaN dataset")
    ds = _all_nan_dataset()
    _try("add all-nan", lambda: win.add_dataset(ds))
    _try("activate all-nan", lambda: win.set_active_dataset(len(win._datasets) - 1))
    _settle(app, 400)
    _snap(win, "03_all_nan", "every RR is NaN")

    # ----- Scenario 3: Identical RR (zero variance) --------------------
    print("\n[3] zero-variance dataset")
    ds = _identical_rr_dataset()
    _try("add identical", lambda: win.add_dataset(ds))
    _try("activate identical", lambda: win.set_active_dataset(len(win._datasets) - 1))
    _settle(app, 400)
    _snap(win, "04_zero_variance", "perfect metronome — SDNN=0")

    # ----- Scenario 4: Extreme outliers --------------------------------
    print("\n[4] extreme outliers dataset")
    ds = _extreme_outlier_dataset()
    _try("add outliers", lambda: win.add_dataset(ds))
    _try("activate outliers", lambda: win.set_active_dataset(len(win._datasets) - 1))
    _settle(app, 400)
    _snap(win, "05_extreme_outliers", "1000+ BPM and 12 BPM spikes")

    # ----- Scenario 5: Negative RR values ------------------------------
    print("\n[5] negative-RR dataset")
    ds = _negative_rr_dataset()
    _try("add negative", lambda: win.add_dataset(ds))
    _try("activate negative", lambda: win.set_active_dataset(len(win._datasets) - 1))
    _settle(app, 400)
    _snap(win, "06_negative_rr", "10% of values are negative")

    # ----- Scenario 6: Zero-length dataset -----------------------------
    # Many components assume at least one beat. Loading an empty array
    # should NOT crash the plot or info dock.
    print("\n[6] zero-length dataset")
    try:
        ds = _zero_length_dataset()
        win.add_dataset(ds)
        win.set_active_dataset(len(win._datasets) - 1)
    except Exception as exc:
        print(f"[FAIL] zero-length add: {type(exc).__name__}: {exc}")
    _settle(app, 400)
    _snap(win, "07_zero_length", "empty t/v arrays")

    # ----- Scenario 7: Rapid tab smashing ------------------------------
    # Real users panic-click. Each tab switch fires re-renders. Walk all
    # visible tabs forward AND backward to catch teardown / re-init bugs.
    print("\n[7] rapid tab smashing")
    tabs = win._tabs_widget
    visible_tabs = [i for i in range(tabs.count()) if tabs.isTabVisible(i)]
    for round_idx in range(3):
        sequence = visible_tabs if round_idx % 2 == 0 else list(reversed(visible_tabs))
        for i in sequence:
            tabs.setCurrentIndex(i)
            app.processEvents()
    _settle(app, 600)
    _snap(win, "08_after_tab_smash", "3 rounds of fwd+rev tab cycling")

    # ----- Scenario 8: Dramatic resize churn ---------------------------
    print("\n[8] dramatic resize churn")
    for w, h in [(640, 480), (1920, 1080), (320, 240), (2560, 1440), (1024, 768)]:
        win.resize(w, h)
        app.processEvents()
    _settle(app, 500)
    _snap(win, "09_after_resize_churn", "5 dramatic resizes back-to-back")

    # ----- Scenario 9: 100-dataset stress test -------------------------
    print("\n[9] 100-dataset stress test")
    rng = np.random.default_rng(seed=1234)
    for i in range(100):
        n = 300
        rr = 800 + 30 * rng.standard_normal(n)
        t = np.cumsum(rr) / 1000.0
        ds = Dataset(
            name=f"stress_{i:03d}.csv",
            data=InspectorData(t=t, v=rr),
        )
        win.add_dataset(ds)
        if i % 20 == 0:
            app.processEvents()
    _settle(app, 800)
    print(f"  loaded total = {len(win._datasets)} datasets")
    _snap(win, "10_100_dataset_stress", f"{len(win._datasets)} datasets in workspace")

    # ----- Scenario 10: Holter-scale recording -------------------------
    print("\n[10] Holter-scale single recording (86k beats)")
    ds = _holter_dataset()
    _try("add holter", lambda: win.add_dataset(ds))
    _try("activate holter", lambda: win.set_active_dataset(len(win._datasets) - 1))
    _settle(app, 1200)
    _snap(win, "11_holter_86k_beats", "24h Holter sim with 60 sections")

    # ----- Scenario 11: Navigate Participants tab with 100+ datasets ---
    print("\n[11] Participants tab with massive workspace")
    participants_idx = -1
    for i in range(tabs.count()):
        if tabs.isTabVisible(i) and "articipant" in tabs.tabText(i):
            participants_idx = i
            break
    if participants_idx >= 0:
        tabs.setCurrentIndex(participants_idx)
        _settle(app, 1500)
        _snap(win, "12_participants_with_100+", "grid with 100+ recordings")

    # ----- Scenario 12: Browse tab back with active dataset switch ------
    print("\n[12] Switch back to Browse, activate Holter")
    browse_idx = tabs.indexOf(win._browse_tab)
    if browse_idx >= 0:
        tabs.setCurrentIndex(browse_idx)
        _settle(app, 500)
        # Activate the Holter (last) dataset
        win.set_active_dataset(len(win._datasets) - 1)
        _settle(app, 800)
        _snap(win, "13_browse_holter_active", "Holter rendered in Browse")

    # ----- Scenario 13: Section overlay extremes ------------------------
    # The Holter has 60 sections. With section colour-coding cycling
    # through the palette, do any sections collide or look identical?
    print("\n[13] Holter section overlay density")
    # No additional action needed — last snap shows the overlay density.

    # ----- Scenario 14: Active dataset stress switching -----------------
    print("\n[14] rapid active-dataset cycling")
    for i in range(0, len(win._datasets), 20):
        win.set_active_dataset(i)
        app.processEvents()
    _settle(app, 500)
    _snap(win, "14_after_active_cycling", "cycled active across 100+ datasets")

    print("\n[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
