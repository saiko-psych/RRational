"""Quality-gated frequency domain: Moderate (5-10 % artifacts) = time domain only.

docs/science/guidelines.md: "Moderate | 5-10% | Time-domain only | Correct,
but avoid frequency metrics"; Poor (> 10 %) = exclude. Frequency-domain
power is far more sensitive to corrected beats than time-domain indices
(LF tolerates only ~2 % beat removal, Sheridan et al. 2020, cited in
recommended-workflow.md). These tests pin that calculate_hrv_metrics
withholds frequency metrics when the artifact rate exceeds 5 %, per call
and per window.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from rrational.analysis.hrv_compute import (
    FREQ_GATE_ARTIFACT_RATE,
    calculate_hrv_metrics,
)

pytestmark = pytest.mark.filterwarnings("ignore")

METRICS = ["RMSSD", "SDNN", "LF", "HF", "LF_HF"]


def _nn(n=900, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    return (
        800 + 40 * np.sin(t / 5) + 24 * np.sin(t / 23 + 1) + rng.normal(0, 15, n)
    ).tolist()


def test_threshold_matches_documented_good_moderate_boundary():
    assert FREQ_GATE_ARTIFACT_RATE == 0.05


@pytest.mark.parametrize("rate", [None, 0.0, 0.02, 0.05])
def test_frequency_computed_up_to_good_grade(rate):
    m, _, _ = calculate_hrv_metrics(
        _nn(), use_windows=False, selected_metrics=METRICS, artifact_rate=rate
    )
    assert m["LF"] is not None and m["HF"] is not None


@pytest.mark.parametrize("rate", [0.0501, 0.08, 0.10, 0.3])
def test_frequency_withheld_above_five_percent(rate, caplog):
    with caplog.at_level("WARNING", logger="rrational.analysis.hrv_compute"):
        m, _, _ = calculate_hrv_metrics(
            _nn(), use_windows=False, selected_metrics=METRICS, artifact_rate=rate
        )
    assert m["LF"] is None and m["HF"] is None and m["LF_HF"] is None
    # Time domain is still reported.
    assert m["RMSSD"] is not None and m["SDNN"] is not None
    assert "frequency-domain metrics withheld" in caplog.text


def test_per_segment_rates_gate_each_window():
    nn = _nn(n=1200)
    segs = [
        SimpleNamespace(beat_start=0, beat_end=400, included=True, artifact_pct=1.0),
        SimpleNamespace(beat_start=400, beat_end=800, included=True, artifact_pct=7.0),
        SimpleNamespace(beat_start=800, beat_end=1200, included=True, artifact_pct=2.0),
    ]
    mean, _, n_win = calculate_hrv_metrics(nn, selected_metrics=METRICS, segments=segs)
    only_good = [segs[0], segs[2]]
    mean_good, _, _ = calculate_hrv_metrics(
        nn, selected_metrics=METRICS, segments=only_good
    )
    assert n_win == 3
    # Frequency averaged over the two good windows only ...
    assert mean["LF"] == pytest.approx(mean_good["LF"])
    # ... time domain over all three.
    mean_all_time, _, _ = calculate_hrv_metrics(
        nn, selected_metrics=["RMSSD"], segments=segs
    )
    assert mean["RMSSD"] == pytest.approx(mean_all_time["RMSSD"])
    assert mean["RMSSD"] != pytest.approx(mean_good["RMSSD"])
