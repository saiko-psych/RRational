"""Regression tests for the Round 30 "warn but compute" quality signals.

Two methodological guards the user opted into (flag, never gate):

- G3: time-domain metrics on a window below ``MIN_BEATS_TIME_DOMAIN`` (100
  beats, Quigley 2024) still compute but emit one aggregated warning.
- G1: a Kubios PSD segment too short to fit >= 2 Welch averaging windows
  still computes but emits a reproducibility warning.

The values must always be returned — the warning is advisory only. Pure
logic, no Qt.
"""

from __future__ import annotations

import logging

import numpy as np

from rrational.analysis.hrv_compute import (
    FREQ_METHOD_KUBIOS,
    calculate_hrv_metrics,
)

_LOGGER = "rrational.analysis.hrv_compute"


def _rr(n: int, seed: int, mean: float = 800.0, sd: float = 25.0) -> list[float]:
    return (mean + sd * np.random.default_rng(seed).standard_normal(n)).tolist()


# ---------------------------------------------------------------------
# G3 — time-domain minimum-beats warning
# ---------------------------------------------------------------------
def test_short_time_domain_window_warns_but_computes(caplog):
    rr = _rr(40, seed=0)  # 40 < 100
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        metrics, _, _ = calculate_hrv_metrics(
            rr, use_windows=False, selected_metrics=["RMSSD", "SDNN"]
        )
    # Value still returned.
    assert metrics.get("RMSSD") is not None
    # Exactly one aggregated warning mentioning the 100-beat floor.
    msgs = [r.message for r in caplog.records if r.name == _LOGGER]
    assert any("100-beat" in m or "minimum" in m for m in msgs)


def test_adequate_time_domain_window_does_not_warn(caplog):
    rr = _rr(200, seed=2)  # 200 >= 100
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        metrics, _, _ = calculate_hrv_metrics(
            rr, use_windows=False, selected_metrics=["RMSSD"]
        )
    assert metrics.get("RMSSD") is not None
    td_warnings = [
        r for r in caplog.records if r.name == _LOGGER and "beat minimum" in r.message
    ]
    assert not td_warnings


# ---------------------------------------------------------------------
# G1 — short-segment PSD reproducibility warning
# ---------------------------------------------------------------------
def test_short_kubios_psd_warns_but_computes(caplog):
    # ~4 min at 800 ms -> passes the 300-beat frequency gate but is short
    # enough that Welch yields a single averaging window.
    rr = _rr(320, seed=1, sd=30.0)
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        metrics, _, _ = calculate_hrv_metrics(
            rr,
            use_windows=False,
            selected_metrics=["LF", "HF"],
            freq_method=FREQ_METHOD_KUBIOS,
        )
    assert metrics.get("LF") is not None  # value still computed
    msgs = [r.message for r in caplog.records if r.name == _LOGGER]
    assert any("Welch averaging window" in m for m in msgs)


def test_long_kubios_psd_does_not_warn(caplog):
    rr = _rr(1200, seed=3, sd=30.0)  # ~16 min -> multiple Welch windows
    with caplog.at_level(logging.WARNING, logger=_LOGGER):
        metrics, _, _ = calculate_hrv_metrics(
            rr,
            use_windows=False,
            selected_metrics=["LF", "HF"],
            freq_method=FREQ_METHOD_KUBIOS,
        )
    assert metrics.get("LF") is not None
    psd_warnings = [
        r
        for r in caplog.records
        if r.name == _LOGGER and "Welch averaging" in r.message
    ]
    assert not psd_warnings
