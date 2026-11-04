"""Tests for rrational.cleaning.quality (gap, artifact and quality checks)."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from rrational.cleaning.quality import detect_time_gaps

T0 = dt.datetime(2024, 3, 1, 10, 0, 0)


def _beats(rr_ms, gap_after=None, gap_s=0.0, t0=T0):
    """Per-beat timestamps for ``rr_ms`` with an optional recording gap.

    The timestamp of beat i is the end of interval i. A gap of ``gap_s``
    seconds of *missing time* is inserted after beat ``gap_after``.
    """
    ts, t = [], t0
    for i, r in enumerate(rr_ms):
        t = t + dt.timedelta(milliseconds=float(r))
        if gap_after is not None and i == gap_after + 1:
            t = t + dt.timedelta(seconds=gap_s)
        ts.append(t)
    return ts


# ---------------------------------------------------------------------------
# detect_time_gaps
# ---------------------------------------------------------------------------


class TestDetectTimeGaps:
    def test_rr_values_as_numpy_array_detects_gap(self):
        """Regression: a numpy ``rr_values`` used to make the function
        silently report *no gaps* (``if rr_values`` raised "truth value of
        an array is ambiguous", which the broad except swallowed)."""
        # Whole-second RR so this test is independent of sub-second
        # timestamp handling (covered separately below).
        rr = [1000] * 20
        ts = _beats(rr, gap_after=9, gap_s=10.0)

        as_list = detect_time_gaps(ts, rr_values=rr)
        as_array = detect_time_gaps(ts, rr_values=np.array(rr))

        assert as_list["total_gaps"] == 1
        assert as_array["total_gaps"] == as_list["total_gaps"]
        assert as_array["gaps"][0]["duration_s"] == pytest.approx(10.0)
        assert as_array["total_gap_duration_s"] == pytest.approx(10.0)
