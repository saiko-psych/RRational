"""Tests for ``PSDPlot`` (Welch PSD with VLF/LF/HF band shadings)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


def _synthetic_rr(n: int = 1000, seed: int = 3) -> np.ndarray:
    """RR series long enough (>= ~3 min) for a meaningful Welch PSD."""
    rng = np.random.default_rng(seed)
    base = 800 + 25 * np.sin(np.linspace(0, 40 * np.pi, n))  # ~LF/HF mix
    noise = rng.normal(0, 12, size=n)
    return base + noise


def test_psd_constructs_with_synthetic_rr(qtbot):
    from rrational.inspector.plots.psd import PSDPlot

    w = PSDPlot(_synthetic_rr(1000), section_label="rest")
    qtbot.addWidget(w)

    assert w.plot_widget is not None
    # Long-enough input should produce band integrals.
    assert "LF Power" in w.stats
    assert "HF Power" in w.stats
    assert "VLF Power" in w.stats


def test_psd_has_three_band_shadings(qtbot):
    """The widget must add exactly 3 band-shading regions (VLF, LF, HF)."""
    from rrational.inspector.plots.psd import PSDPlot

    w = PSDPlot(_synthetic_rr(1000))
    qtbot.addWidget(w)

    assert w.band_shading_count() == 3


def test_psd_short_input_renders_empty_but_does_not_crash(qtbot):
    """With < 16 beats we render axes only — no stats, no band shadings."""
    from rrational.inspector.plots.psd import PSDPlot

    w = PSDPlot([800.0] * 5)
    qtbot.addWidget(w)

    assert w.stats == {}
    assert w.band_shading_count() == 0
