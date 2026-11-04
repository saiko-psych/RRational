"""Time-based windows must have equal length (Task Force 1996 comparability)."""

from __future__ import annotations

import logging

import numpy as np
import pytest

from rrational.analysis.hrv_compute import calculate_hrv_metrics
from rrational.gui.segmentation import generate_segments

pytestmark = pytest.mark.filterwarnings("ignore")


def _nn(seconds, seed=0):
    rng = np.random.default_rng(seed)
    rr, t = [], 0.0
    while t < seconds:
        v = float(np.round(800 + rng.normal(0, 30)))
        rr.append(v)
        t += v / 1000.0
    return rr


def _rmssd(x):
    d = np.diff(np.asarray(x, dtype=float))
    return float(np.sqrt(np.mean(d**2)))


def test_partial_trailing_window_is_not_averaged(caplog):
    """12 min with 5-min windows, no overlap: generate_segments yields
    300 + 300 + ~120 s. SDNN/RMSSD from a 2-min window are not comparable
    with 5-min ones (recommended-workflow.md), so only the two full windows
    may enter the mean."""
    nn = _nn(720)
    segs = generate_segments(np.asarray(nn), window_s=300, overlap_pct=0)
    durations = [s.duration_s for s in segs]
    assert len(segs) == 3 and durations[-1] < 200  # premise: one partial window

    with caplog.at_level(logging.INFO, logger="rrational.analysis.hrv_compute"):
        mean, _, n_win = calculate_hrv_metrics(
            nn, selected_metrics=["RMSSD"], window_s=300, overlap_pct=0
        )
    full = [s for s in segs if s.duration_s >= 0.9 * 300]
    assert n_win == len(full) == 2
    expected = np.mean([_rmssd(nn[s.beat_start : s.beat_end]) for s in full])
    assert mean["RMSSD"] == pytest.approx(expected, rel=1e-10)
    assert "partial window" in caplog.text


def test_section_shorter_than_one_window_falls_back_to_whole_section():
    nn = _nn(200)  # 3.3 min < 5-min window
    mean, sd, n_win = calculate_hrv_metrics(
        nn, selected_metrics=["RMSSD"], window_s=300
    )
    assert (n_win, sd) == (1, None)
    assert mean["RMSSD"] == pytest.approx(_rmssd(nn), rel=1e-10)
