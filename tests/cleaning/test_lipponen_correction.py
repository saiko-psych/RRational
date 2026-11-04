"""Tests for the Lipponen & Tarvainen (2019) artifact correction.

L&T correct in PEAK space (NeuroKit2 ``signal_fixpeaks(method="Kubios",
iterative=True)``): an extra beat's peak is deleted (two short intervals
merge), a missed beat gets a peak inserted at the midpoint (a long interval
splits), and ectopic/long-short beats have their peak moved to the midpoint
of its neighbours. Total recording time is therefore preserved, while the
number of intervals can change. These tests pin those properties and the
raw->corrected boundary map that consumers use to slice the corrected
series with raw beat positions.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from rrational.cleaning.quality import (
    correct_artifacts_lipponen,
    detect_artifacts_fixpeaks,
    map_raw_range,
)

pytestmark = pytest.mark.filterwarnings("ignore")


def _base(n=600, seed=2):
    """Smooth physiological variation that NK2 flags nowhere (verified by
    test_clean_signal_is_unchanged), so every change is due to the planted
    artifact."""
    rng = np.random.default_rng(seed)
    rr = 800 + 25 * np.sin(np.arange(n) / 5) + rng.normal(0, 3, n)
    return np.round(rr).astype(int).tolist()


def _realistic(n=600, seed=0):
    """Physiological spread (RMSSD ~ 20 ms). L&T's missed/extra criteria
    use thresholds adapted to the local spread of RR differences; on the
    near-noise-free ``_base`` they become so strict that NK2 labels a 2x
    beat "longshort" (peak moved, not split). That is the published
    algorithm's behaviour, so missed/extra cases use realistic variability.
    iid noise also triggers a few spurious "ectopic" peak moves elsewhere;
    those never change the beat count."""
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    rr = 800 + 40 * np.sin(t / 5) + 24 * np.sin(t / 23 + 1) + rng.normal(0, 15, n)
    return np.round(rr).astype(int).tolist()


def _missed():
    rr = _realistic()
    rr[300] = 2 * rr[300]
    return rr


def _extra():
    rr = _realistic()
    first = int(rr[300] * 0.4)
    rr[300:301] = [first, rr[300] - first]  # one interval split by a spurious peak
    return rr


def _ectopic():
    rr = _base()
    rr[300], rr[301] = 550, 1050
    return rr


def _check_map(res, rr):
    m = res["raw_to_corrected"]
    assert len(m) == len(rr) + 1
    assert m[0] == 0 and m[-1] == len(res["corrected_rr"])
    assert all(a <= b for a, b in zip(m, m[1:]))


class TestCorrectionSemantics:
    def test_missed_beat_is_split_and_time_preserved(self):
        rr = _missed()
        res = correct_artifacts_lipponen(rr)
        c = res["corrected_rr"]
        assert len(c) == len(rr) + 1
        assert res["n_inserted"] == 1 and res["n_removed"] == 0
        assert sum(c) == pytest.approx(sum(rr), abs=1)
        cs, ce = map_raw_range(res["raw_to_corrected"], 300, 301)
        assert ce - cs == 2  # the 1600 ms interval became two
        assert all(700 < x < 900 for x in c[cs:ce])
        assert 300 in res["artifact_indices"]
        _check_map(res, rr)

    def test_extra_beat_is_merged_and_time_preserved(self):
        rr = _extra()
        res = correct_artifacts_lipponen(rr)
        c = res["corrected_rr"]
        assert len(c) == len(rr) - 1
        assert res["n_removed"] == 1 and res["n_inserted"] == 0
        assert sum(c) == pytest.approx(sum(rr), abs=1)
        cs, ce = map_raw_range(res["raw_to_corrected"], 300, 302)
        assert ce - cs == 1  # 300 + 500 merged into one interval
        assert 700 < c[cs] < 900
        _check_map(res, rr)

    def test_ectopic_peak_is_moved_length_and_time_preserved(self):
        rr = _ectopic()
        res = correct_artifacts_lipponen(rr)
        c = res["corrected_rr"]
        assert len(c) == len(rr)
        assert sum(c) == pytest.approx(sum(rr), abs=1)
        # Deviation from the clean signal over the affected beats shrinks.
        # NK2 moves adjacent misaligned peaks using each other's
        # uncorrected positions, so the pair is improved, not equalised
        # (e.g. 550/1050/785 -> 733/734/918; documented limitation).
        clean = _base()
        raw_dev = sum(abs(rr[i] - clean[i]) for i in (300, 301, 302))
        cor_dev = sum(abs(c[i] - clean[i]) for i in (300, 301, 302))
        assert cor_dev < raw_dev
        assert res["raw_to_corrected"] == list(range(len(rr) + 1))

    def test_clean_signal_is_unchanged(self):
        rng = np.random.default_rng(7)
        rr = np.round(850 + 25 * np.sin(np.arange(400) / 5) + rng.normal(0, 3, 400))
        rr = rr.astype(int).tolist()
        res = correct_artifacts_lipponen(rr)
        assert res["corrected_rr"] == pytest.approx(rr)
        assert res["artifact_indices"] == []
        assert res["correction_applied"] is False
        assert not any(res["corrected_flags"])

    def test_detection_indices_match_core_detector(self):
        for rr in (_missed(), _extra(), _ectopic()):
            res = correct_artifacts_lipponen(rr)
            core = detect_artifacts_fixpeaks(rr)
            assert res["artifact_indices"] == core["artifact_indices"]

    def test_unchanged_regions_are_identical_via_map(self):
        rr = _ectopic()  # clean base: only the planted beats are flagged
        res = correct_artifacts_lipponen(rr)
        assert set(res["artifact_indices"]) <= {299, 300, 301, 302}
        m, c = res["raw_to_corrected"], res["corrected_rr"]
        for s, e in [(0, 290), (310, 600)]:
            cs, ce = map_raw_range(m, s, e)
            assert c[cs:ce] == pytest.approx(rr[s:e])

    def test_raw_slices_keep_their_duration(self):
        for rr in (_missed(), _extra()):
            res = correct_artifacts_lipponen(rr)
            m, c = res["raw_to_corrected"], res["corrected_rr"]
            for s, e in [(0, 200), (250, 350), (280, 320), (400, len(rr))]:
                cs, ce = map_raw_range(m, s, e)
                assert sum(c[cs:ce]) == pytest.approx(sum(rr[s:e]), abs=2)

    def test_corrected_flags_mark_only_changed_beats(self):
        rr = _missed()
        res = correct_artifacts_lipponen(rr)
        flags = res["corrected_flags"]
        assert len(flags) == len(res["corrected_rr"])
        cs, ce = map_raw_range(res["raw_to_corrected"], 300, 301)
        assert all(flags[cs:ce])
        # Each flagged raw beat changes itself and at most its neighbour.
        assert sum(flags) <= 2 * len(res["artifact_indices"]) + 2
        # Every flag corresponds to a value that really differs or moved.
        c = res["corrected_rr"]
        unchanged = [j for j, f in enumerate(flags) if not f]
        raw_vals = set(rr)
        assert all(c[j] in raw_vals for j in unchanged)


class TestTimestamps:
    def _ts(self, rr, t0=dt.datetime(2024, 3, 1, 10, 0, 0)):
        out, t = [], t0
        for r in rr:
            t = t + dt.timedelta(milliseconds=int(r))
            out.append(t)
        return out

    def test_datetime_timestamps_follow_corrected_beats(self):
        rr = _missed()
        ts = self._ts(rr)
        res = correct_artifacts_lipponen(rr, timestamps=ts)
        cts = res["corrected_timestamps"]
        assert len(cts) == len(res["corrected_rr"])
        assert all(a < b for a, b in zip(cts, cts[1:]))
        m = res["raw_to_corrected"]
        # Unchanged beats keep their original timestamps exactly.
        for j, f in enumerate(res["corrected_flags"][:250]):
            if not f:
                assert cts[j] in ts
        # The inserted beat lies between its neighbours.
        cs, ce = map_raw_range(m, 300, 301)
        assert ts[299] < cts[cs] < ts[300] and cts[ce - 1] == ts[300]

    def test_numeric_timestamps_are_interpolated(self):
        rr = _extra()
        ts = list(range(len(rr)))
        res = correct_artifacts_lipponen(rr, timestamps=ts)
        assert len(res["corrected_timestamps"]) == len(res["corrected_rr"])

    def test_no_timestamps_gives_none(self):
        assert correct_artifacts_lipponen(_missed())["corrected_timestamps"] is None


class TestEdgeCases:
    def test_short_input_passthrough(self):
        rr = [800] * 9
        res = correct_artifacts_lipponen(rr, timestamps=list(range(9)))
        assert res["corrected_rr"] == rr
        assert res["corrected_timestamps"] == list(range(9))
        assert res["raw_to_corrected"] == list(range(10))

    def test_map_raw_range_bounds(self):
        m = [0, 1, 3, 4]
        assert map_raw_range(m, 0, 3) == (0, 4)
        assert map_raw_range(m, 1, 2) == (1, 3)
        assert map_raw_range(m, 2, 2) == (3, 3)


class TestSegmented:
    def test_concatenates_per_segment_corrections_with_global_map(self):
        from rrational.cleaning.quality import correct_artifacts_lipponen_segmented

        rr = _realistic(n=900)
        rr[150] = 2 * rr[150]  # missed in segment 0
        first = int(rr[450] * 0.4)
        rr[450:451] = [first, rr[450] - first]  # extra in segment 1 (n -> 901)
        rr[800], rr[801] = int(rr[800] * 0.65), int(rr[801] * 1.35)  # ectopic, seg 2
        ts = list(range(len(rr)))
        bounds = [(0, 300), (300, 600), (600, len(rr))]

        res = correct_artifacts_lipponen_segmented(rr, ts, bounds)
        m = res["raw_to_corrected"]
        _check_map(res, rr)
        assert len(res["corrected_timestamps"]) == len(res["corrected_rr"])
        for s, e in bounds:
            local = correct_artifacts_lipponen(rr[s:e], timestamps=ts[s:e])
            cs, ce = map_raw_range(m, s, e)
            assert res["corrected_rr"][cs:ce] == pytest.approx(local["corrected_rr"])
        assert res["n_inserted"] == 1 and res["n_removed"] == 1
        assert {150, 450, 800} <= set(res["artifact_indices"])
        assert sum(res["corrected_rr"]) == pytest.approx(sum(rr), abs=3)

    def test_uncovered_and_tiny_segments_pass_through(self):
        from rrational.cleaning.quality import correct_artifacts_lipponen_segmented

        rr = _base(n=400)
        res = correct_artifacts_lipponen_segmented(rr, None, [(0, 5), (100, 400)])
        m = res["raw_to_corrected"]
        cs, ce = map_raw_range(m, 0, 100)
        assert res["corrected_rr"][cs:ce] == pytest.approx(rr[0:100])
        assert res["corrected_timestamps"] is None
        _check_map(res, rr)
