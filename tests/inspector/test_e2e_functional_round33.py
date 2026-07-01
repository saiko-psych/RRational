"""End-to-end FUNCTIONAL tests — drive the real MainWindow through real
button clicks and assert the buttons do what they should, with a focus on
the Round 30-33 fixes (corrected-RR flow, cross-dataset exclusion isolation,
annotation dedup, dataset-switch state reset).

These construct the actual MainWindow + tabs (not a mocked slice) and use
``QPushButton.click()`` / ``QCheckBox.setChecked(...)`` so the wired slots
fire exactly as they would for a user. Auto-marked ``slow`` (qtbot).
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pytestqt")


def _synthetic_dataset(name: str, n: int = 200, seed: int = 42):
    from rrational.inspector.data_loader import (
        Dataset,
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    rng = np.random.default_rng(seed)
    base = 1_700_000_000
    t = base + np.cumsum(np.full(n, 0.8))
    v = 800 + 20 * rng.standard_normal(n)
    for idx in (n // 4, n // 2):
        v[idx] = 200.0  # clear artifacts
    data = InspectorData(
        t=t,
        v=v,
        sections=[
            SectionMeta(
                name="full", t_start=float(t[0]), t_end=float(t[-1]), beat_count=n
            )
        ],
        events=[EventMeta(label="start", t=float(t[0]))],
    )
    return Dataset(name=name, data=data, path=None)


@pytest.fixture
def win(qtbot, tmp_path):
    from rrational.inspector import settings
    from rrational.inspector.main_window import MainWindow

    settings.enable_test_mode(tmp_path)
    w = MainWindow()
    w.test_mode = True
    w.set_ui_layout("mnelab")
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    return w


def _panel(win):
    return win._browse_tab._preprocessing_panel


# ---------------------------------------------------------------------
# 1. Detect-artifacts button actually detects + enables the toggles
# ---------------------------------------------------------------------
def test_detect_button_click_populates_result(win):
    win.add_dataset(_synthetic_dataset("P01.csv"))
    win.set_active_dataset(0)
    panel = _panel(win)
    assert panel._detect_btn.isEnabled()
    panel._detect_btn.click()  # real button click -> _on_detect_clicked
    assert panel._last_result is not None
    assert panel._last_result.total > 0  # it found the injected spikes
    # "Use corrected RR values" becomes enabled once a correction exists.
    assert panel._toggle_use_corrected.isEnabled()


# ---------------------------------------------------------------------
# 2. PP1 — the "Use corrected" toggle makes Compute use corrected values
# ---------------------------------------------------------------------
def test_use_corrected_toggle_propagates_to_dataset_and_analysis(win):
    win.add_dataset(_synthetic_dataset("P01.csv"))
    win.set_active_dataset(0)
    panel = _panel(win)
    panel._detect_btn.click()
    ds = win._datasets[0]
    assert not ds.use_corrected

    panel._toggle_use_corrected.setChecked(True)  # fires _on_toggle_use_corrected
    assert ds.use_corrected is True
    assert ds.corrected_v is not None

    # The analysis slice must now differ from the raw slice at the artifact.
    from rrational.inspector.tabs.analysis_tab import _corrected_for, _slice_section

    raw = _slice_section(ds.data, "full")
    corr = _slice_section(ds.data, "full", corrected_v=_corrected_for(ds))
    assert corr is not None and raw is not None
    # The 200 ms spike is corrected away -> min of corrected slice is higher.
    assert float(np.min(corr)) > float(np.min(raw))

    # Toggling back off restores raw analysis.
    panel._toggle_use_corrected.setChecked(False)
    assert ds.use_corrected is False


# ---------------------------------------------------------------------
# 3. E1 — cross-dataset exclusion isolation (A's zones don't filter B)
# ---------------------------------------------------------------------
def test_cross_dataset_exclusion_isolation(win):
    from rrational.inspector.exclusion_persistence import ExclusionZone
    from rrational.inspector.tabs.analysis_tab import _exclusion_zones_for_dataset

    a = _synthetic_dataset("A.csv", seed=1)
    b = _synthetic_dataset("B.csv", seed=2)
    win.add_dataset(a)
    win.add_dataset(b)
    win.set_active_dataset(0)  # A is displayed

    # Put a live zone on the shared plot (belongs to A, the active dataset).
    plot = win._browse_tab._plot
    plot._exclusion_zones = [ExclusionZone(start_t=a.data.t[10], end_t=a.data.t[20])]

    za = _exclusion_zones_for_dataset(win, win._datasets[0])
    zb = _exclusion_zones_for_dataset(win, win._datasets[1])
    assert len(za) == 1  # active dataset uses the live zone
    assert len(zb) == 0  # B does NOT inherit A's live zone


# ---------------------------------------------------------------------
# 4. A2 — annotation dedup: a duplicate at the same t is refused
# ---------------------------------------------------------------------
def test_annotation_duplicate_refused(win):
    win.add_dataset(_synthetic_dataset("P01.csv"))
    win.set_active_dataset(0)
    panel = _panel(win)
    panel._toggle_annotation_mode.setChecked(True)
    t = float(win._datasets[0].data.t[30])
    panel._on_plot_clicked(t)
    n_after_first = len(panel._annotations)
    assert n_after_first == 1
    panel._on_plot_clicked(t)  # same timestamp -> refused
    assert len(panel._annotations) == 1  # not doubled


# ---------------------------------------------------------------------
# 5. E3 — switching datasets resets exclusion mode OFF
# ---------------------------------------------------------------------
def test_dataset_switch_resets_exclusion_mode(win):
    win.add_dataset(_synthetic_dataset("A.csv", seed=1))
    win.add_dataset(_synthetic_dataset("B.csv", seed=2))
    win.set_active_dataset(0)
    panel = _panel(win)
    panel._toggle_exclusion_mode.setChecked(True)
    assert panel._toggle_exclusion_mode.isChecked()
    win.set_active_dataset(1)  # switch -> on_active_dataset_changed
    assert not panel._toggle_exclusion_mode.isChecked()


# ---------------------------------------------------------------------
# 6. Analysis Compute button produces a results row
# ---------------------------------------------------------------------
def test_analysis_compute_button_creates_result(win):
    win.add_dataset(_synthetic_dataset("P01.csv"))
    win.set_active_dataset(0)
    ana = win._analysis_tab
    single = ana._single_pane
    # Pick the dataset + section, then click Compute.
    if single._dataset_combo.count() > 0:
        single._dataset_combo.setCurrentIndex(0)
    if single._section_combo.count() > 0:
        single._section_combo.setCurrentIndex(0)
    n_before = len(win._results_store.metric_rows)
    single._compute_btn.click()
    assert len(win._results_store.metric_rows) > n_before


# ---------------------------------------------------------------------
# 7. Every tab switches without raising
# ---------------------------------------------------------------------
def test_all_tabs_switch_cleanly(win):
    win.add_dataset(_synthetic_dataset("P01.csv"))
    win.set_active_dataset(0)
    tabs = win._tabs_widget
    for i in range(tabs.count()):
        if tabs.isTabVisible(i):
            tabs.setCurrentIndex(i)
    assert True  # no exception across the full sweep
