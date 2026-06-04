"""Tests for ``HRDistributionPlot`` (HR histogram + KDE overlay)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


def _synthetic_rr(n: int = 500, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return 800 + rng.normal(0, 30, size=n)


def test_hr_distribution_constructs_with_synthetic_rr(qtbot):
    from rrational.inspector.plots.hr_distribution import HRDistributionPlot

    w = HRDistributionPlot(_synthetic_rr(500), section_label="rest")
    qtbot.addWidget(w)

    assert w.plot_widget is not None
    assert "Mean HR" in w.stats
    assert "SD" in w.stats


def test_hr_distribution_handles_empty_input(qtbot):
    """Empty RR -> stats reports N beats = 0 and widget does not crash."""
    from rrational.inspector.plots.hr_distribution import HRDistributionPlot

    w = HRDistributionPlot([])
    qtbot.addWidget(w)

    assert w.stats == {"N beats": 0}


def test_hr_distribution_filters_zero_rr(qtbot):
    """Zero (or negative) RR values must be silently dropped (no /0)."""
    from rrational.inspector.plots.hr_distribution import HRDistributionPlot

    rr = list(_synthetic_rr(200)) + [0.0, 0.0]
    w = HRDistributionPlot(rr)
    qtbot.addWidget(w)

    # If filtering failed, mean HR would be NaN/inf.
    mean_hr_str = w.stats["Mean HR"]
    assert "nan" not in mean_hr_str.lower()
    assert "inf" not in mean_hr_str.lower()


def test_hr_distribution_custom_bins(qtbot):
    """Custom ``bins`` must be accepted without error."""
    from rrational.inspector.plots.hr_distribution import HRDistributionPlot

    w = HRDistributionPlot(_synthetic_rr(400), bins=50)
    qtbot.addWidget(w)
    assert "Mean HR" in w.stats
