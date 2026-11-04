"""Tests for persistence.build_nn_data (NN-file records from a correction)."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from rrational.cleaning.quality import correct_artifacts_lipponen
from rrational.gui.persistence import build_nn_data

pytestmark = pytest.mark.filterwarnings("ignore")

T0 = dt.datetime(2024, 3, 1, 10, 0, 0)


def _realistic(n=600, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    rr = 800 + 40 * np.sin(t / 5) + 24 * np.sin(t / 23 + 1) + rng.normal(0, 15, n)
    return np.round(rr).astype(int).tolist()


def _ts(rr):
    out, t = [], T0
    for r in rr:
        t = t + dt.timedelta(milliseconds=int(r))
        out.append(t)
    return out


def test_in_place_correction_keeps_legacy_semantics():
    raw = [800, 810, 400, 805, 790]
    corrected = [800, 810, 807.5, 805, 790]
    nn = build_nn_data(raw, corrected, _ts(raw))
    assert nn["final_nn_count"] == 5 and nn["original_beat_count"] == 5
    assert [r[2] for r in nn["intervals"]] == [False, False, True, False, False]
    assert nn["corrections"] == [
        {"nn_idx": 2, "raw_idx": 2, "original_rr_ms": 400, "corrected_nn_ms": 807.5}
    ]
    assert [r[0] for r in nn["intervals"]] == [0, 810, 1210, 2015, 2805]


def test_lipponen_missed_beat_adds_an_interval():
    raw = _realistic()
    raw[300] = 2 * raw[300]
    ts = _ts(raw)
    lt = correct_artifacts_lipponen(raw, timestamps=ts)
    nn = build_nn_data(
        raw,
        lt["corrected_rr"],
        lt["corrected_timestamps"],
        raw_to_corrected=lt["raw_to_corrected"],
        corrected_flags=lt["corrected_flags"],
        raw_start=250,
        raw_end=350,
    )
    assert nn["original_beat_count"] == 100
    assert nn["final_nn_count"] == 101
    assert sum(r[1] for r in nn["intervals"]) == pytest.approx(sum(raw[250:350]), abs=2)
    split = [c for c in nn["corrections"] if c["raw_idx"] == 300]
    assert len(split) == 2 and all(c["original_rr_ms"] == raw[300] for c in split)
    # Timestamps are relative to the first beat of the range and increasing.
    ts_ms = [r[0] for r in nn["intervals"]]
    assert ts_ms[0] == 0 and all(a < b for a, b in zip(ts_ms, ts_ms[1:]))


def test_excluded_raw_beats_are_not_marked_corrected():
    raw = [800, 810, 400, 805, 790]
    corrected = [800, 810, 807.5, 805, 790]
    nn = build_nn_data(raw, corrected, _ts(raw), excluded_raw={2})
    assert not any(r[2] for r in nn["intervals"]) and nn["corrections"] == []


def test_length_mismatch_without_map_is_rejected():
    with pytest.raises(ValueError, match="raw_to_corrected"):
        build_nn_data([800] * 5, [800] * 6, None)


def test_missing_timestamps_fall_back_to_cumulative_nn():
    raw = [800, 810, 790]
    nn = build_nn_data(raw, raw, [None, None, None])
    assert [r[0] for r in nn["intervals"]] == [0, 810, 1600]


def test_nn_export_rows_one_row_per_nn_beat_with_raw_reference():
    from rrational.gui.persistence import nn_export_rows

    raw = _realistic()
    raw[300] = 2 * raw[300]
    ts = _ts(raw)
    lt = correct_artifacts_lipponen(raw, timestamps=ts)
    rows = nn_export_rows(
        raw,
        lt["corrected_rr"],
        lt["corrected_timestamps"],
        raw_to_corrected=lt["raw_to_corrected"],
        corrected_flags=lt["corrected_flags"],
    )
    assert len(rows) == len(lt["corrected_rr"]) == len(raw) + 1
    split = [r for r in rows if r["raw_idx"] == 300]
    assert len(split) == 2
    assert all(r["rr_ms"] == raw[300] and r["was_corrected"] for r in split)
    assert [r["nn_idx"] for r in rows] == list(range(len(rows)))


def test_nn_export_rows_in_place_is_one_to_one():
    from rrational.gui.persistence import nn_export_rows

    raw = [800, 810, 400, 805]
    rows = nn_export_rows(raw, [800, 810, 807.5, 805], _ts(raw))
    assert [r["raw_idx"] for r in rows] == [0, 1, 2, 3]
    assert [r["was_corrected"] for r in rows] == [False, False, True, False]
