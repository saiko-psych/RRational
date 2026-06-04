"""Tests for ``PoincarePlot`` (RR[n] vs RR[n+1] with SD1/SD2 ellipse)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


def _synthetic_rr(n: int = 600, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = 850 + 30 * np.sin(np.linspace(0, 4 * np.pi, n))
    noise = rng.normal(0, 10, size=n)
    return base + noise


def _expected_sd1_sd2(rr: np.ndarray) -> tuple[float, float]:
    """Mirror the formulas used by ``create_poincare_plot``."""
    rr_n = rr[:-1]
    rr_n1 = rr[1:]
    sd1 = float(np.std(rr_n1 - rr_n) / np.sqrt(2))
    sd2 = float(np.std(rr_n1 + rr_n) / np.sqrt(2))
    return sd1, sd2


def test_poincare_constructs_with_synthetic_rr(qtbot):
    from rrational.inspector.plots.poincare import PoincarePlot

    rr = _synthetic_rr(600)
    w = PoincarePlot(rr, section_label="music")
    qtbot.addWidget(w)

    assert w.plot_widget is not None
    assert w.stats["N pairs"] == 599
    assert "SD1 (short-term)" in w.stats
    assert "SD2 (long-term)" in w.stats
    assert "SD1/SD2" in w.stats


def test_poincare_sd1_sd2_match_reference_formula(qtbot):
    """Widget's SD1/SD2 must match the canonical formulas used by the
    Streamlit ``create_poincare_plot`` helper."""
    from rrational.inspector.plots.poincare import PoincarePlot

    rr = _synthetic_rr(800, seed=42)
    expected_sd1, expected_sd2 = _expected_sd1_sd2(rr)

    w = PoincarePlot(rr)
    qtbot.addWidget(w)

    assert w.sd1 == pytest.approx(expected_sd1, rel=1e-9)
    assert w.sd2 == pytest.approx(expected_sd2, rel=1e-9)


def test_poincare_handles_short_input(qtbot):
    """Fewer than 2 beats -> empty stats but no crash."""
    from rrational.inspector.plots.poincare import PoincarePlot

    w = PoincarePlot([850.0])
    qtbot.addWidget(w)

    assert w.stats["N pairs"] == 0
    assert w.sd1 == 0.0
    assert w.sd2 == 0.0
