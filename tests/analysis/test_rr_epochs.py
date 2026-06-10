"""Tests for the MNE-style ``RREpochs`` container (Cluster C1)."""

from __future__ import annotations

import numpy as np
import pytest

from rrational.analysis.rr_epochs import RREpochs


@pytest.fixture
def synthetic_tachogram():
    """One-hour RR sampled at 1 Hz with a slow sinusoid."""
    t = np.arange(0, 3600, dtype=float)  # seconds
    rr = 800 + 30 * np.sin(2 * np.pi * t / 600.0)
    return t, rr


@pytest.fixture
def events_every_minute():
    """One event every minute from 60s to 1800s -> 30 events."""
    return np.arange(60.0, 1800.0, 60.0)


def test_construct_with_events_keeps_all(synthetic_tachogram, events_every_minute):
    t, rr = synthetic_tachogram
    ep = RREpochs(t=t, rr=rr, events=events_every_minute, tmin=-10, tmax=20)
    assert len(ep) == len(events_every_minute)


def test_tmin_must_be_less_than_tmax(synthetic_tachogram):
    t, rr = synthetic_tachogram
    with pytest.raises(ValueError, match="tmin"):
        RREpochs(t=t, rr=rr, events=np.array([100.0]), tmin=5, tmax=5)


def test_average_returns_times_and_mean(synthetic_tachogram, events_every_minute):
    t, rr = synthetic_tachogram
    ep = RREpochs(t=t, rr=rr, events=events_every_minute, tmin=-10, tmax=20)
    times, mean = ep.average()
    assert times.shape == mean.shape
    assert times[0] == pytest.approx(-10.0)
    assert times[-1] == pytest.approx(20.0)
    assert np.all(np.isfinite(mean))


def test_apply_baseline_subtracts_window_mean(synthetic_tachogram, events_every_minute):
    t, rr = synthetic_tachogram
    ep = RREpochs(t=t, rr=rr, events=events_every_minute, tmin=-10, tmax=20)
    ep.apply_baseline((-10.0, 0.0))
    # After subtraction the baseline-window mean should be ~0 per epoch.
    data = ep.get_data()
    times = ep.times
    mask = (times >= -10.0) & (times <= 0.0)
    baselines = np.nanmean(data[:, mask], axis=1)
    assert np.allclose(baselines, 0.0, atol=1e-6)
    assert ep.baseline == (-10.0, 0.0)


def test_apply_baseline_validates_window(synthetic_tachogram, events_every_minute):
    t, rr = synthetic_tachogram
    ep = RREpochs(t=t, rr=rr, events=events_every_minute, tmin=-10, tmax=20)
    with pytest.raises(ValueError, match="baseline tmin"):
        ep.apply_baseline((5.0, 5.0))
    with pytest.raises(ValueError, match="outside epoch range"):
        ep.apply_baseline((100.0, 200.0))


def test_drop_bad_removes_high_ptp_epochs(synthetic_tachogram, events_every_minute):
    t, rr = (
        synthetic_tachogram.copy()
        if hasattr(synthetic_tachogram, "copy")
        else (synthetic_tachogram[0], synthetic_tachogram[1].copy())
    )
    # Inject a spike in the second epoch's window.
    rr[120:130] = 2000.0
    ep = RREpochs(t=t, rr=rr, events=events_every_minute, tmin=-10, tmax=20)
    before = len(ep)
    ep.drop_bad(reject={"rr": 500.0})
    assert len(ep) < before
    assert any(reason.startswith("PTP>") for _, reason in ep.drop_log)


def test_drop_bad_noop_without_threshold(synthetic_tachogram, events_every_minute):
    t, rr = synthetic_tachogram
    ep = RREpochs(t=t, rr=rr, events=events_every_minute, tmin=-10, tmax=20)
    before = len(ep)
    ep.drop_bad()
    ep.drop_bad(reject={})
    assert len(ep) == before


def test_out_of_bounds_events_are_dropped(synthetic_tachogram):
    t, rr = synthetic_tachogram
    # Events beyond the data range -> all dropped with OUT_OF_BOUNDS.
    ep = RREpochs(t=t, rr=rr, events=np.array([10000.0]), tmin=-10, tmax=20)
    assert len(ep) == 0
    assert ep.drop_log[0][1] == "OUT_OF_BOUNDS"


def test_to_data_frame_yields_long_format(synthetic_tachogram, events_every_minute):
    t, rr = synthetic_tachogram
    ep = RREpochs(t=t, rr=rr, events=events_every_minute[:3], tmin=-5, tmax=5)
    df = ep.to_data_frame()
    assert {"epoch", "event_idx", "time", "rr_ms"}.issubset(df.columns)
    # 3 epochs * (5 - (-5)) * 4Hz + 1 sample per epoch = 3 * 41 rows
    assert len(df) == 3 * 41


def test_integer_index_returns_single_epoch(synthetic_tachogram, events_every_minute):
    t, rr = synthetic_tachogram
    ep = RREpochs(t=t, rr=rr, events=events_every_minute, tmin=-10, tmax=20)
    single = ep[2]
    assert len(single) == 1


def test_slice_subset_works(synthetic_tachogram, events_every_minute):
    t, rr = synthetic_tachogram
    ep = RREpochs(t=t, rr=rr, events=events_every_minute, tmin=-10, tmax=20)
    sub = ep[0:5]
    assert len(sub) == 5


def test_query_subset_uses_metadata(synthetic_tachogram, events_every_minute):
    import pandas as pd

    t, rr = synthetic_tachogram
    md = pd.DataFrame(
        {"cond": ["rest"] * 15 + ["stress"] * (len(events_every_minute) - 15)}
    )
    ep = RREpochs(
        t=t, rr=rr, events=events_every_minute, tmin=-10, tmax=20, metadata=md
    )
    sub = ep["cond == 'rest'"]
    assert len(sub) == 15
