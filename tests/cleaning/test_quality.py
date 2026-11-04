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

    @pytest.mark.parametrize("start_us", [0, 250_000, 500_000, 900_000])
    def test_naive_and_aware_timestamps_give_same_gap_duration(self, start_us):
        """Regression: naive datetimes went through
        ``calendar.timegm(t.timetuple())``, and ``timetuple()`` has no
        sub-second field, so every naive timestamp was truncated to whole
        seconds. The same instants as tz-aware UTC kept their fractions,
        so gap durations differed by up to 1 s depending only on tzinfo."""
        rr = [800] * 20
        naive = _beats(rr, gap_after=9, gap_s=10.0, t0=T0.replace(microsecond=start_us))
        aware = [t.replace(tzinfo=dt.timezone.utc) for t in naive]

        g_naive = detect_time_gaps(naive, rr_values=rr)
        g_aware = detect_time_gaps(aware, rr_values=rr)

        assert g_naive["total_gaps"] == g_aware["total_gaps"] == 1
        assert g_naive["gaps"][0]["duration_s"] == pytest.approx(10.0, abs=1e-6)
        assert g_aware["gaps"][0]["duration_s"] == pytest.approx(10.0, abs=1e-6)
        assert g_naive["gap_ratio"] == pytest.approx(g_aware["gap_ratio"], abs=1e-9)

    def test_sub_threshold_gap_not_inflated_by_subsecond_phase(self):
        """A 1.5 s unexplained interval is below the 2 s threshold and must
        not be flagged. With whole-second truncation, a beat at hh:mm:00.9
        followed by one at hh:mm:03.2 looked like 3 s - 0.8 s = 2.2 s."""
        a = T0.replace(microsecond=900_000)
        ts = [a - dt.timedelta(milliseconds=800), a, a + dt.timedelta(milliseconds=2300)]
        rr = [800, 800, 800]

        result = detect_time_gaps(ts, rr_values=rr, gap_threshold_s=2.0)

        assert result["total_gaps"] == 0
