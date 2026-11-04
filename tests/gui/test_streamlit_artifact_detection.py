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
each segment.
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


@pytest.mark.parametrize("method", ["kubios", "lipponen2019"])
def test_single_pass_flags_the_artifact_not_the_next_beat(detect, method):
    rr = _rr_with_artifacts()
    res = _run(detect, rr, method)

    flagged = set(res["artifact_indices"])
    assert {100, 700} <= flagged
    # The planted artifact is corrected; its healthy successor is untouched.
    assert 700 < res["corrected_rr"][100] < 900
    assert res["corrected_rr"][101] == rr[101]
    assert 700 < res["corrected_rr"][700] < 900
    assert res["corrected_rr"][701] == rr[701]


def test_single_pass_matches_core_detector_exactly(detect):
    from rrational.cleaning.quality import detect_artifacts_fixpeaks

    rr = _rr_with_artifacts(seed=3)
    res = _run(detect, rr, "kubios")
    core = detect_artifacts_fixpeaks(rr)

    assert res["artifact_indices"] == core["artifact_indices"]
    assert res["corrected_rr"] == pytest.approx(core["corrected_rr"])
    # Per-type indices are in RR space too (used for the plot overlay).
    for indices in res["indices_by_type"].values():
        assert set(indices) <= set(core["artifact_indices"])
    assert res["artifact_timestamps"] == res["artifact_indices"]  # ts = range(n)


def test_segmented_matches_core_detector_per_segment(detect):
    from rrational.cleaning.quality import detect_artifacts_fixpeaks

    rr = _rr_with_artifacts(seed=4)
    res = _run(detect, rr, "lipponen2019_segmented", window_s=300.0)

    expected = set()
    for seg in res["segments"]:
        seg_rr = rr[seg.beat_start : seg.beat_end]
        if len(seg_rr) < 10:
            continue
        local = detect_artifacts_fixpeaks(seg_rr)["artifact_indices"]
        expected.update(seg.beat_start + i for i in local)

    assert res["artifact_indices"] == sorted(expected)
    assert {100, 700} <= set(res["artifact_indices"])
    assert res["corrected_rr"][101] == rr[101]
    assert res["corrected_rr"][701] == rr[701]


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
