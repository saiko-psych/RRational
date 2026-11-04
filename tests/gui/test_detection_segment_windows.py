"""Tests for segmentation.windows_from_detection_segments."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from rrational.cleaning.quality import correct_artifacts_lipponen
from rrational.gui.segmentation import windows_from_detection_segments

pytestmark = pytest.mark.filterwarnings("ignore")


def _realistic(n=900, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    rr = 800 + 40 * np.sin(t / 5) + 24 * np.sin(t / 23 + 1) + rng.normal(0, 15, n)
    return np.round(rr).astype(int).tolist()


def _segs(bounds, included=None):
    included = included or [True] * len(bounds)
    return [
        SimpleNamespace(idx=i, beat_start=s, beat_end=e, start_ms=float(s * 800), included=inc)
        for i, ((s, e), inc) in enumerate(zip(bounds, included))
    ]


def test_slices_corrected_series_through_the_map():
    raw = _realistic()
    raw[150] = 2 * raw[150]  # missed beat in segment 0 -> corrected is 1 longer
    lt = correct_artifacts_lipponen(raw)
    data = {"original_rr": raw, **lt}
    segs = _segs([(0, 300), (300, 600), (600, 900)])
    windows = windows_from_detection_segments(segs, {}, lt["corrected_rr"], data)
    assert [w[0] for w in windows] == [0, 1, 2]
    assert len(windows[0][2]) == 301  # split beat lands in segment 0
    assert len(windows[1][2]) == 300
    assert sum(windows[0][2]) == pytest.approx(sum(raw[0:300]), abs=2)


def test_respects_inclusion_overrides_and_min_beats():
    raw = _realistic()
    lt = correct_artifacts_lipponen(raw)
    data = {"original_rr": raw, **lt}
    segs = _segs([(0, 20), (20, 450), (450, 900)], included=[True, True, False])
    windows = windows_from_detection_segments(segs, {1: False, 2: True}, lt["corrected_rr"], data)
    assert [w[0] for w in windows] == [2]  # seg 0 < 30 beats, seg 1 excluded by user


def test_returns_none_when_nn_is_not_the_detection_series():
    raw = _realistic()
    lt = correct_artifacts_lipponen(raw)
    data = {"original_rr": raw, **lt}
    other_nn = lt["corrected_rr"][100:]  # e.g. one section of the recording
    assert windows_from_detection_segments(_segs([(0, 300)]), {}, other_nn, data) is None


def test_in_place_results_without_map_use_identity():
    raw = [800.0] * 400
    data = {"original_rr": raw, "corrected_rr": list(raw)}
    windows = windows_from_detection_segments(_segs([(0, 200), (200, 400)]), {}, raw, data)
    assert [len(w[2]) for w in windows] == [200, 200]
