"""Tests for the Cluster B1 compare-HRV-curves overlay + dialog."""

from __future__ import annotations

import numpy as np
import pytest
import pyqtgraph as pg

from rrational.inspector.plots.compare_curves import (
    _bootstrap_ci,
    _pad_to_common_length,
    compare_hrv_curves,
)


def test_pad_to_common_length_handles_unequal_curves():
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([10.0, 20.0])
    out = _pad_to_common_length([a, b])
    assert out.shape == (2, 3)
    assert np.array_equal(out[0], np.array([1.0, 2.0, 3.0]))
    assert np.isnan(out[1, 2])
    assert out[1, 0] == 10.0


def test_pad_to_common_length_empty_input():
    assert _pad_to_common_length([]).shape == (0, 0)


def test_bootstrap_ci_returns_band_in_order():
    rng = np.random.default_rng(42)
    # 20 curves of length 50, mean ~800ms +- 30
    matrix = 800 + 30 * rng.standard_normal((20, 50))
    mean, lower, upper = _bootstrap_ci(matrix, ci=0.95, n_boot=200, rng=rng)
    assert mean.shape == (50,)
    assert np.all(lower <= mean + 1e-9)
    assert np.all(upper >= mean - 1e-9)
    # CI band should be narrower than +- 1 SD across subjects.
    assert np.mean(upper - lower) < 60.0


def test_bootstrap_ci_single_curve_returns_degenerate_band():
    rng = np.random.default_rng(0)
    matrix = np.array([[1.0, 2.0, 3.0]])
    mean, lower, upper = _bootstrap_ci(matrix, ci=0.95, n_boot=100, rng=rng)
    assert np.array_equal(mean, lower)
    assert np.array_equal(mean, upper)


def test_compare_hrv_curves_validates_ci(qtbot):
    with pytest.raises(ValueError, match="ci must be in"):
        compare_hrv_curves({"a": [np.array([1.0])]}, ci=1.5)


def test_compare_hrv_curves_validates_n_boot(qtbot):
    with pytest.raises(ValueError, match="n_boot"):
        compare_hrv_curves({"a": [np.array([1.0])]}, n_boot=0)


def test_compare_hrv_curves_returns_plot_widget(qtbot):
    rng = np.random.default_rng(0)
    groups = {
        "baseline": [800 + 10 * rng.standard_normal(50) for _ in range(5)],
        "stress": [700 + 15 * rng.standard_normal(50) for _ in range(5)],
    }
    w = compare_hrv_curves(groups, ci=0.95, n_boot=100, seed=1)
    qtbot.addWidget(w)
    assert isinstance(w, pg.PlotWidget)
    # Two groups -> at least two PlotDataItems for means (plus fill helpers).
    items = w.getPlotItem().listDataItems()
    assert len(items) >= 2


def test_compare_hrv_curves_skips_empty_group(qtbot):
    rng = np.random.default_rng(0)
    groups = {
        "ok": [800 + 10 * rng.standard_normal(30) for _ in range(3)],
        "empty": [],
    }
    w = compare_hrv_curves(groups, ci=0.95, n_boot=100, seed=2)
    qtbot.addWidget(w)
    # Should not crash; the empty group simply contributes no items.
    items = w.getPlotItem().listDataItems()
    assert len(items) >= 1


def test_compare_curves_dialog_runs_without_groups(qtbot):
    from rrational.inspector.compare_curves_dialog import CompareCurvesDialog

    dialog = CompareCurvesDialog(datasets=[])
    qtbot.addWidget(dialog)
    # No datasets, no exception on construction.
    assert dialog.windowTitle() == "Compare HRV curves"


def test_compare_curves_dialog_plots_with_dataset(qtbot, synthetic_inspector_data):
    from rrational.inspector.compare_curves_dialog import CompareCurvesDialog
    from rrational.inspector.data_loader import Dataset

    ds = Dataset(name="synth", data=synthetic_inspector_data, path=None)
    dialog = CompareCurvesDialog(datasets=[ds])
    qtbot.addWidget(dialog)
    # Select the single dataset in group A.
    listw = dialog._group_a["list"]
    listw.item(0).setSelected(True)
    dialog._on_plot_clicked()
    assert dialog._plot_widget is not None
