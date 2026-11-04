"""Frequency-domain power is absolute (ms^2) in both freq_methods.

NeuroKit2's hrv_frequency defaults to normalize=True, which divides each
recording's PSD by its OWN maximum. Band powers then lose all amplitude
information: two recordings whose true LF power differs 4x got identical
LF (0.0050) - yet they were labelled ms^2 and compared between groups.
"""

from __future__ import annotations

import numpy as np
import pytest

from rrational.analysis.hrv_compute import calculate_hrv_metrics

pytestmark = pytest.mark.filterwarnings("ignore")


def _sine_rr(freqs, amps, duration_s=600.0, base=800.0):
    rr, t = [], 0.0
    while t < duration_s:
        v = base + sum(a * np.sin(2 * np.pi * f * t) for f, a in zip(freqs, amps))
        rr.append(v)
        t += v / 1000.0
    return rr


@pytest.mark.parametrize("freq_method", ["neurokit", "kubios"])
def test_band_power_is_absolute_ms2(freq_method):
    m, _, _ = calculate_hrv_metrics(
        _sine_rr([0.10, 0.25], [20.0, 10.0]),
        use_windows=False,
        selected_metrics=["LF", "HF", "LF_HF"],
        freq_method=freq_method,
    )
    assert m["LF"] == pytest.approx(200.0, rel=0.05)  # A^2 / 2
    assert m["HF"] == pytest.approx(50.0, rel=0.05)
    assert m["LF_HF"] == pytest.approx(4.0, rel=0.05)


def test_neurokit_power_scales_with_amplitude_squared():
    def lf(amp):
        m, _, _ = calculate_hrv_metrics(
            _sine_rr([0.10], [amp]), use_windows=False, selected_metrics=["LF"]
        )
        return m["LF"]

    assert lf(20.0) / lf(10.0) == pytest.approx(4.0, rel=0.02)
