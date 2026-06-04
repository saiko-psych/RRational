"""Tests for ``TachogramPlot`` (pyqtgraph-backed RR-vs-beat plot)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


def _synthetic_rr(n: int = 500, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    base = 800 + 40 * np.sin(np.linspace(0, 6 * np.pi, n))
    noise = rng.normal(0, 15, size=n)
    return base + noise


def test_tachogram_constructs_with_synthetic_rr(qtbot):
    from rrational.inspector.plots.tachogram import TachogramPlot

    rr = _synthetic_rr(500)
    w = TachogramPlot(rr, section_label="rest")
    qtbot.addWidget(w)

    assert w.plot_widget is not None
    assert w.stats["N beats"] == 500
    assert "Mean RR" in w.stats
    assert "SD" in w.stats
    assert "Mean HR" in w.stats


def test_tachogram_artifact_marker_count_matches_input(qtbot):
    from rrational.inspector.plots.tachogram import TachogramPlot

    rr = _synthetic_rr(500)
    artifacts = [10, 50, 120, 300, 499]
    w = TachogramPlot(rr, artifact_indices=artifacts)
    qtbot.addWidget(w)

    assert w.artifact_marker_count() == len(artifacts)
    assert w.stats["Artifacts"] == len(artifacts)


def test_tachogram_zero_artifacts_when_none_given(qtbot):
    from rrational.inspector.plots.tachogram import TachogramPlot

    w = TachogramPlot(_synthetic_rr(300))
    qtbot.addWidget(w)

    assert w.artifact_marker_count() == 0
    assert "Artifacts" not in w.stats


def test_tachogram_filters_out_of_bounds_artifact_indices(qtbot):
    """Indices outside [0, len(rr)) should be silently dropped."""
    from rrational.inspector.plots.tachogram import TachogramPlot

    rr = _synthetic_rr(100)
    artifacts = [-1, 5, 99, 100, 5000]  # only 5 and 99 are valid
    w = TachogramPlot(rr, artifact_indices=artifacts)
    qtbot.addWidget(w)

    assert w.artifact_marker_count() == 2


def test_tachogram_empty_rr_does_not_crash(qtbot):
    from rrational.inspector.plots.tachogram import TachogramPlot

    w = TachogramPlot([])
    qtbot.addWidget(w)

    assert w.stats["N beats"] == 0
    assert w.artifact_marker_count() == 0
