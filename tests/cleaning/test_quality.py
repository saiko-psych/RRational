"""Tests for rrational.cleaning.quality (gap, artifact and quality checks)."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from rrational.cleaning import quality
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

    def test_gap_duration_is_timestamp_delta_minus_explaining_rr(self):
        rr = [1000] * 10
        ts = _beats(rr, gap_after=4, gap_s=5.0)
        res = detect_time_gaps(ts, rr_values=rr)
        (gap,) = res["gaps"]
        assert gap["start_idx"] == 4 and gap["end_idx"] == 5
        assert gap["timestamp_diff_s"] == pytest.approx(6.0)
        assert gap["duration_s"] == pytest.approx(5.0)  # 6 s - 1 s of RR
        total = (ts[-1] - ts[0]).total_seconds()
        assert res["gap_ratio"] == pytest.approx(5.0 / total)

    def test_without_rr_uses_raw_timestamp_delta(self):
        rr = [1000] * 10
        ts = _beats(rr, gap_after=4, gap_s=5.0)
        (gap,) = detect_time_gaps(ts)["gaps"]
        assert gap["duration_s"] == pytest.approx(6.0)

    def test_rr_length_mismatch_falls_back_to_raw_delta(self):
        rr = [1000] * 10
        ts = _beats(rr, gap_after=4, gap_s=5.0)
        (gap,) = detect_time_gaps(ts, rr_values=rr[:-1])["gaps"]
        assert gap["duration_s"] == pytest.approx(6.0)

    def test_threshold_is_strict(self):
        rr = [1000] * 6
        ts = _beats(rr, gap_after=2, gap_s=2.0)  # unexplained exactly 2.0 s
        assert detect_time_gaps(ts, rr, gap_threshold_s=2.0)["total_gaps"] == 0
        assert detect_time_gaps(ts, rr, gap_threshold_s=1.99)["total_gaps"] == 1

    def test_continuous_recording_has_no_gaps(self):
        rr = [812, 790, 845, 801, 777, 830, 795]
        res = detect_time_gaps(_beats(rr), rr_values=rr)
        assert res == {"gaps": [], "total_gaps": 0, "total_gap_duration_s": 0.0, "gap_ratio": 0.0}

    @pytest.mark.parametrize("ts", [[], [T0], [None, None, None]])
    def test_degenerate_inputs_return_empty(self, ts):
        assert detect_time_gaps(ts)["total_gaps"] == 0

    def test_none_timestamp_inside_series_is_tolerated(self):
        rr = [1000] * 6
        ts = _beats(rr, gap_after=3, gap_s=8.0)
        ts[1] = None
        res = detect_time_gaps(ts, rr_values=rr)
        assert res["total_gaps"] == 1
        assert res["gaps"][0]["duration_s"] == pytest.approx(8.0)

    def test_malformed_timestamps_return_empty_and_log(self, caplog):
        with caplog.at_level("WARNING", logger="rrational.cleaning.quality"):
            res = detect_time_gaps(["not a datetime", "nope"])
        assert res["total_gaps"] == 0
        assert "recovered from" in caplog.text


# ---------------------------------------------------------------------------
# get_quality_badge
# ---------------------------------------------------------------------------


class TestQualityBadge:
    @pytest.mark.parametrize(
        "score,ratio,badge",
        [
            (100, 0.0, "[OK]"),
            (100, 0.25, "[OK]"),  # combined = (100 + 50) / 2 = 75 -> boundary
            (100, 0.26, "[!]"),
            (100, 0.50, "[!]"),  # combined = 50 -> boundary
            (100, 0.51, "[!]"),  # artifact score clamps at 0 -> combined 50
            (40, 0.51, "[X]"),  # (40 + 0) / 2 = 20
            (50, 0.0, "[OK]"),  # (50 + 100) / 2 = 75
            (0, 0.0, "[!]"),  # (0 + 100) / 2 = 50
            (0, 1.0, "[X]"),
        ],
    )
    def test_thresholds(self, score, ratio, badge):
        assert quality.get_quality_badge(score, ratio) == badge

    def test_x_badge_unreachable_when_quality_score_is_100(self):
        """Documents current behaviour, not an endorsement: both production
        callers (prep/participant_table.py, gui/tabs/data.py) pass a fixed
        quality_score of 100, so the combined score is always >= 50 and a
        recording is never shown as "[X]" (even at 100 % artifacts), and
        up to 25 % artifacts shows "[OK]" although Quigley et al. (2024)
        recommend excluding segments with > 10 % artifacts
        (docs/science/validation.md). If the thresholds are changed on
        purpose, update this test."""
        assert quality.get_quality_badge(100, 1.0) == "[!]"
        assert quality.get_quality_badge(100, 0.25) == "[OK]"

    def test_artifact_score_is_clamped(self):
        # ratio > 0.5 must not push the artifact score below 0
        assert quality.get_quality_badge(100, 5.0) == quality.get_quality_badge(100, 0.75)


# ---------------------------------------------------------------------------
# detect_quality_changepoints
# ---------------------------------------------------------------------------


class _FakeNK:
    """Minimal stand-in for neurokit2 returning canned results."""

    def __init__(self, changepoints=None, fixpeaks_info=None, raise_exc=False):
        self._cp = changepoints
        self._info = fixpeaks_info
        self._raise = raise_exc

    def signal_changepoints(self, *a, **k):
        if self._raise:
            raise RuntimeError("boom")
        return self._cp

    def signal_fixpeaks(self, *a, **k):
        if self._raise:
            raise RuntimeError("boom")
        return self._info, None


class TestQualityChangepoints:
    def test_short_input_returns_neutral_result(self):
        res = quality.detect_quality_changepoints([800] * 9)
        assert res == {
            "changepoint_indices": [],
            "n_segments": 1,
            "segment_stats": [],
            "quality_score": 100,
        }

    def test_neurokit_unavailable_returns_neutral_result(self, monkeypatch):
        monkeypatch.setattr(quality, "_get_neurokit", lambda: (None, False))
        assert quality.detect_quality_changepoints([800] * 50)["quality_score"] == 100

    def test_real_variance_change_is_detected_and_segments_partition_signal(self):
        rng = np.random.default_rng(42)
        rr = np.concatenate([800 + rng.normal(0, 5, 150), 800 + rng.normal(0, 80, 150)])
        res = quality.detect_quality_changepoints(rr.tolist(), change_type="var")

        assert res["changepoint_indices"], "a 16x variance jump must be detected"
        stats = res["segment_stats"]
        assert res["n_segments"] == len(stats)
        # Segments tile the signal without gaps/overlaps.
        assert stats[0]["start_idx"] == 0 and stats[-1]["end_idx"] == len(rr)
        for a, b in zip(stats, stats[1:]):
            assert a["end_idx"] == b["start_idx"]
        assert sum(s["n_beats"] for s in stats) == len(rr)
        # Per-segment statistics equal numpy on the same slice.
        for s in stats:
            seg = rr[s["start_idx"] : s["end_idx"]]
            assert s["mean_rr"] == pytest.approx(seg.mean())
            assert s["std_rr"] == pytest.approx(seg.std())
            assert s["cv"] == pytest.approx(seg.std() / seg.mean())

    @pytest.mark.parametrize(
        "n_cp,score", [(0, 100), (1, 80), (2, 80), (3, 60), (5, 60), (6, 40), (8, 20), (20, 20)]
    )
    def test_quality_score_mapping(self, monkeypatch, n_cp, score):
        cps = list(range(5, 5 + 3 * n_cp, 3))
        monkeypatch.setattr(quality, "_get_neurokit", lambda: (_FakeNK(cps), True))
        res = quality.detect_quality_changepoints([800.0] * 100)
        assert res["quality_score"] == score
        assert res["n_segments"] == n_cp + 1

    def test_neurokit_error_returns_neutral_result(self, monkeypatch):
        monkeypatch.setattr(
            quality, "_get_neurokit", lambda: (_FakeNK(raise_exc=True), True)
        )
        assert quality.detect_quality_changepoints([800] * 50)["quality_score"] == 100


# ---------------------------------------------------------------------------
# detect_artifacts_fixpeaks
# ---------------------------------------------------------------------------


def _fake_fixpeaks(monkeypatch, info):
    monkeypatch.setattr(
        quality, "_get_neurokit", lambda: (_FakeNK(fixpeaks_info=info), True)
    )


class TestArtifactsFixpeaks:
    def test_short_input_is_passed_through(self):
        rr = [800] * 9
        res = quality.detect_artifacts_fixpeaks(rr)
        assert res["corrected_rr"] is rr
        assert res["total_artifacts"] == 0 and res["correction_applied"] is False

    def test_clean_signal_has_no_artifacts_and_is_unchanged(self):
        rng = np.random.default_rng(7)
        rr = np.round(850 + 25 * np.sin(np.arange(400) / 5) + rng.normal(0, 3, 400))
        res = quality.detect_artifacts_fixpeaks(rr.astype(int).tolist())
        assert res["total_artifacts"] == 0
        assert res["artifact_ratio"] == 0.0
        assert res["corrected_rr"] == pytest.approx(rr.tolist())

    def test_real_artifacts_are_flagged_and_length_preserved(self):
        rng = np.random.default_rng(0)
        rr = np.round(800 + rng.normal(0, 15, 500)).astype(int).tolist()
        rr[200] = 400  # extra/ectopic-like short beat
        rr[350] = 1600  # missed beat
        res = quality.detect_artifacts_fixpeaks(rr)

        assert len(res["corrected_rr"]) == len(rr)
        assert {200, 350} <= set(res["artifact_indices"])
        assert res["artifact_ratio"] == pytest.approx(res["total_artifacts"] / len(rr))
        assert res["total_artifacts"] == sum(res["artifacts"].values())
        # Corrected values are back in the physiological range.
        assert 700 < res["corrected_rr"][200] < 900
        assert 700 < res["corrected_rr"][350] < 900

    def test_interpolation_rules_including_edges(self, monkeypatch):
        """Peaks-space k maps to RR index k-1; first/last beats copy their
        single neighbour, interior beats take the mean of both neighbours,
        and peaks index 0 (NK2's synthetic first interval) is ignored."""
        rr = [800, 810, 820, 830, 840, 850, 860, 870, 880, 890, 900, 910]
        n = len(rr)
        info = {
            "ectopic": np.array([1, 5]),  # rr idx 0 and 4
            "missed": [n],  # rr idx n-1 (last)
            "extra": [0],  # synthetic -> ignored for indices
            "longshort": "garbage",  # non list/array -> treated as empty
        }
        _fake_fixpeaks(monkeypatch, info)
        res = quality.detect_artifacts_fixpeaks(rr)

        assert res["artifacts"] == {"ectopic": 2, "missed": 1, "extra": 1, "longshort": 0}
        assert res["artifact_indices"] == [0, 4, n - 1]
        c = res["corrected_rr"]
        assert c[0] == 810  # copies right neighbour
        assert c[4] == (830 + 850) / 2
        assert c[-1] == 900  # copies left neighbour
        assert c[1:4] == rr[1:4] and c[5:-1] == rr[5:-1]
        assert res["correction_applied"] is True

    def test_non_integer_indices_are_skipped(self, monkeypatch):
        _fake_fixpeaks(monkeypatch, {"ectopic": ["x", None, 3]})
        res = quality.detect_artifacts_fixpeaks([800] * 12)
        assert res["artifact_indices"] == [2]

    def test_neurokit_error_returns_uncorrected(self, monkeypatch):
        monkeypatch.setattr(
            quality, "_get_neurokit", lambda: (_FakeNK(raise_exc=True), True)
        )
        rr = [800] * 20
        res = quality.detect_artifacts_fixpeaks(rr)
        assert res["corrected_rr"] is rr and res["correction_applied"] is False


# ---------------------------------------------------------------------------
# filter_exclusion_zones
# ---------------------------------------------------------------------------


class _RR:
    def __init__(self, timestamp, rr_ms):
        self.timestamp = timestamp
        self.rr_ms = rr_ms


class TestFilterExclusionZones:
    def _series(self):
        return [_RR(T0 + dt.timedelta(seconds=i), 1000) for i in range(10)]

    def test_no_zones_returns_input_unchanged(self):
        rr = self._series()
        out, stats = quality.filter_exclusion_zones(rr, [])
        assert out is rr
        assert stats == {
            "n_original": 10,
            "n_excluded": 0,
            "n_remaining": 10,
            "excluded_duration_ms": 0,
            "zones_applied": 0,
        }

    def test_empty_rr_list(self):
        out, stats = quality.filter_exclusion_zones([], [{"start": T0, "end": T0}])
        assert out == [] and stats["n_original"] == 0

    def test_zone_bounds_are_inclusive_and_stats_add_up(self):
        rr = self._series()
        zone = {"start": T0 + dt.timedelta(seconds=2), "end": T0 + dt.timedelta(seconds=4)}
        out, stats = quality.filter_exclusion_zones(rr, [zone])
        kept = [(r.timestamp - T0).seconds for r in out]
        assert kept == [0, 1, 5, 6, 7, 8, 9]
        assert stats["n_excluded"] == 3 and stats["excluded_duration_ms"] == 3000
        assert stats["n_remaining"] + stats["n_excluded"] == stats["n_original"]

    def test_string_zones_are_parsed(self):
        rr = self._series()
        zone = {"start": "2024-03-01 10:00:07", "end": "2024-03-01 10:00:08"}
        out, stats = quality.filter_exclusion_zones(rr, [zone])
        assert stats["n_excluded"] == 2 and stats["zones_applied"] == 1

    def test_invalid_zones_are_ignored(self):
        rr = self._series()
        zones = [{"start": "not-a-date", "end": "x"}, {"start": None, "end": T0}]
        out, stats = quality.filter_exclusion_zones(rr, zones)
        assert out is rr and stats["zones_applied"] == 0

    def test_beats_without_timestamp_are_kept(self):
        rr = self._series() + [_RR(None, 900)]
        zone = {"start": T0, "end": T0 + dt.timedelta(seconds=100)}
        out, stats = quality.filter_exclusion_zones(rr, [zone])
        assert [r.rr_ms for r in out] == [900]
        assert stats["n_excluded"] == 10
