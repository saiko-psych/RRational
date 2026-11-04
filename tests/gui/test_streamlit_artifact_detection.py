"""Regression tests for the Streamlit app's Kubios/Lipponen artifact detection.

``gui/app.py:cached_artifact_detection`` ran ``nk.signal_fixpeaks`` inline
instead of using the core ``cleaning.quality`` detector, and never received
the core's Round 30 fix: NK2 reports an artifact at ``rr[k-1]`` as peaks
index ``k``. The app stored ``k`` directly, so it flagged (and "corrected")
the healthy beat *after* each artifact while the artifact itself stayed in
the NN series used for HRV.

The core detector (``detect_artifacts_fixpeaks``, already regression-tested
in tests/cleaning/test_fixpeaks_index_alignment.py) is the independent
reference: the single-pass app path runs the same NK2 call
(``iterative=False``) and the same in-place interpolation, so its output must
match the core exactly; the segmented path must match the core applied to
each segment. Correction is Lipponen & Tarvainen (2019): the corrected series
can differ in length, so values are compared through the raw->corrected map.
"""

from __future__ import annotations

import sys

import numpy as np
import pytest

pytestmark = pytest.mark.filterwarnings("ignore")


@pytest.fixture(scope="module")
def detect():
    """The undecorated ``cached_artifact_detection`` (bypass st.cache_data)."""
    argv = sys.argv
    sys.argv = ["app.py"]  # app.py reads sys.argv at import time
    try:
        import rrational.gui.app as app
    finally:
        sys.argv = argv
    fn = app.cached_artifact_detection
    return getattr(fn, "__wrapped__", fn)


def _rr_with_artifacts(n=1200, seed=0):
    rng = np.random.default_rng(seed)
    rr = np.round(800 + rng.normal(0, 15, n)).astype(int).tolist()
    rr[100] = 450  # premature (ectopic/short) beat
    rr[700] = 1500  # missed beat
    return rr


def _run(detect, rr, method, **kw):
    return detect(tuple(rr), tuple(range(len(rr))), method=method, **kw)


def _corrected_window(res, start, end):
    from rrational.gui.app import corrected_slice_bounds

    cs, ce = corrected_slice_bounds(res, start, end)
    return res["corrected_rr"][cs:ce]


@pytest.mark.parametrize("method", ["kubios", "lipponen2019"])
def test_single_pass_flags_and_corrects_the_artifact(detect, method):
    rr = _rr_with_artifacts()
    res = _run(detect, rr, method)

    flagged = set(res["artifact_indices"])
    assert {100, 700} <= flagged
    assert 101 not in flagged or 100 in flagged  # never the successor alone
    # The planted artifacts are gone from the corrected series and the
    # corrected region keeps its duration (L&T moves/inserts peaks).
    for s, e in [(95, 106), (695, 706)]:
        window = _corrected_window(res, s, e)
        assert all(600 < x < 1000 for x in window), window
        assert sum(window) == pytest.approx(sum(rr[s:e]), abs=2)
    assert len(res["corrected_timestamps"]) == len(res["corrected_rr"])


def test_single_pass_matches_core_exactly(detect):
    from rrational.cleaning.quality import (
        correct_artifacts_lipponen,
        detect_artifacts_fixpeaks,
    )

    rr = _rr_with_artifacts(seed=3)
    ts = list(range(len(rr)))
    res = _run(detect, rr, "kubios")
    core_detect = detect_artifacts_fixpeaks(rr)
    core_lt = correct_artifacts_lipponen(rr, timestamps=ts)

    assert res["artifact_indices"] == core_detect["artifact_indices"]
    assert res["corrected_rr"] == pytest.approx(core_lt["corrected_rr"])
    assert res["raw_to_corrected"] == core_lt["raw_to_corrected"]
    assert res["corrected_timestamps"] == pytest.approx(core_lt["corrected_timestamps"])
    # Per-type indices are in raw RR space (used for the plot overlay).
    for indices in res["indices_by_type"].values():
        assert set(indices) <= set(core_detect["artifact_indices"])
    assert res["artifact_timestamps"] == res["artifact_indices"]  # ts = range(n)


def test_segmented_matches_core_per_segment(detect):
    from rrational.cleaning.quality import (
        correct_artifacts_lipponen_segmented,
        detect_artifacts_fixpeaks,
    )

    rr = _rr_with_artifacts(seed=4)
    res = _run(detect, rr, "lipponen2019_segmented", window_s=300.0)

    expected = set()
    bounds = []
    for seg in res["segments"]:
        bounds.append((seg.beat_start, seg.beat_end))
        seg_rr = rr[seg.beat_start : seg.beat_end]
        if len(seg_rr) < 10:
            continue
        local = detect_artifacts_fixpeaks(seg_rr)["artifact_indices"]
        expected.update(seg.beat_start + i for i in local)

    assert res["artifact_indices"] == sorted(expected)
    assert {100, 700} <= set(res["artifact_indices"])
    lt = correct_artifacts_lipponen_segmented(rr, list(range(len(rr))), bounds)
    assert res["corrected_rr"] == pytest.approx(lt["corrected_rr"])
    assert res["raw_to_corrected"] == lt["raw_to_corrected"]
    for s, e in [(95, 106), (695, 706)]:
        assert all(600 < x < 1000 for x in _corrected_window(res, s, e))


def test_threshold_method_has_identity_map(detect):
    rr = _rr_with_artifacts()
    res = _run(detect, rr, "threshold")
    assert len(res["corrected_rr"]) == len(rr)
    assert res["raw_to_corrected"] == list(range(len(rr) + 1))


def test_segment_artifact_count_is_distinct_flagged_beats(detect):
    """Regression: the per-segment count used ``range(len(indices))`` per
    artifact type, i.e. the length of the LONGEST type list instead of the
    number of distinct flagged beats. Here 64 beats (10.7 %) are flagged
    (48 longshort + 16 missed) but the segment reported 48 (8.0 %), graded
    "moderate" and stayed included, although > 10 % must be excluded
    (Quigley 2024, docs/science/validation.md)."""
    rng = np.random.default_rng(1)
    rr = np.round(800 + rng.normal(0, 15, 600)).astype(int).tolist()
    for k in range(20, 580, 12):
        rr[k] = 450  # premature beats
    for k in range(26, 580, 36):
        rr[k] = 1550  # missed beats

    res = _run(detect, rr, "lipponen2019_segmented", window_s=600.0)
    flagged = res["artifact_indices"]
    assert res["segments"], "expected at least one segment"
    for seg in res["segments"]:
        distinct = [i for i in flagged if seg.beat_start <= i < seg.beat_end]
        assert seg.artifact_count == len(distinct)
        assert seg.artifact_pct == pytest.approx(len(distinct) / seg.n_beats * 100, abs=0.01)
        stats = res["segment_stats"][seg.idx]
        assert stats["n_artifacts"] == len(distinct)

    (seg,) = res["segments"]
    assert seg.artifact_pct > 10
    assert seg.quality_grade == "poor"
    assert seg.included is False


def _realistic_rr(n, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    rr = 800 + 40 * np.sin(t / 5) + 24 * np.sin(t / 23 + 1) + rng.normal(0, 15, n)
    return np.round(rr).astype(int).tolist()


def test_gap_segmented_detection_stitches_length_changing_corrections():
    """Each gap segment is corrected independently; a missed beat (split)
    and an extra beat (merged) change segment lengths, so the merge must
    stitch them with a global map instead of splicing into a raw-length
    array (which silently dropped any length-changed segment)."""
    argv = sys.argv
    sys.argv = ["app.py"]
    try:
        import rrational.gui.app as app
    finally:
        sys.argv = argv
    from rrational.cleaning.quality import map_raw_range

    rr = _realistic_rr(1000)
    rr[200] = 2 * rr[200]  # missed, gap segment 0
    first = int(rr[700] * 0.4)
    rr[700:701] = [first, rr[700] - first]  # extra, gap segment 1 -> n = 1001
    ts = list(range(len(rr)))
    res = app.run_segmented_artifact_detection_at_gaps(
        rr, ts, gap_adjacent_indices={500}, method="lipponen2019"
    )
    m = res["raw_to_corrected"]
    assert len(m) == len(rr) + 1 and m[-1] == len(res["corrected_rr"])
    assert len(res["corrected_timestamps"]) == len(res["corrected_rr"])
    assert sum(res["corrected_rr"]) == pytest.approx(sum(rr), abs=4)
    cs, ce = map_raw_range(m, 200, 201)
    assert ce - cs == 2  # missed beat split
    cs, ce = map_raw_range(m, 700, 702)
    assert ce - cs == 1  # extra beat merged
