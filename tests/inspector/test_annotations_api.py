"""Tests for the MNE-style annotation helpers (Cluster B3 / B4).

The helpers operate on plain ``list[Annotation]`` containers — no Qt
fixtures needed. We pin the contract on the same six operations
``mne.Annotations`` exposes: crop, rename, count, set_durations,
chunk_annotations (the inspector adds the last as a convenience).
"""

from __future__ import annotations

import math

import pytest

from rrational.inspector.annotations import (
    Annotation,
    chunk_annotations,
    count,
    crop,
    rename,
    set_durations,
)


def _make(t: float, text: str, duration: float = 0.0) -> Annotation:
    return Annotation(
        t=t, text=text, created_at="2026-01-01T00:00:00", duration=duration
    )


# ---------------------------------------------------------------------
# crop
# ---------------------------------------------------------------------
def test_crop_keeps_annotations_inside_window() -> None:
    anns = [_make(10, "early"), _make(50, "mid"), _make(95, "late")]
    out = crop(anns, tmin=20, tmax=80)
    assert [a.text for a in out] == ["mid"]


def test_crop_clips_overlapping_range_annotations() -> None:
    # 20-second range from t=40 to t=60. Window 50..70 → clipped to 50..60.
    anns = [_make(40, "long", duration=20)]
    out = crop(anns, tmin=50, tmax=70)
    assert len(out) == 1
    assert out[0].t == pytest.approx(50)
    assert out[0].duration == pytest.approx(10)


def test_crop_drops_annotations_entirely_outside_window() -> None:
    anns = [_make(5, "before"), _make(95, "after")]
    out = crop(anns, tmin=20, tmax=80)
    assert out == []


def test_crop_rejects_inverted_window() -> None:
    with pytest.raises(ValueError):
        crop([], tmin=10, tmax=5)


# ---------------------------------------------------------------------
# rename
# ---------------------------------------------------------------------
def test_rename_substitutes_matching_labels_only() -> None:
    anns = [_make(0, "baseline"), _make(10, "stress"), _make(20, "baseline")]
    out = rename(anns, {"baseline": "rest"})
    assert [a.text for a in out] == ["rest", "stress", "rest"]


def test_rename_with_empty_mapping_is_identity() -> None:
    anns = [_make(0, "a"), _make(1, "b")]
    out = rename(anns, {})
    assert [a.text for a in out] == ["a", "b"]


# ---------------------------------------------------------------------
# count
# ---------------------------------------------------------------------
def test_count_returns_label_histogram() -> None:
    anns = [_make(0, "x"), _make(1, "y"), _make(2, "x"), _make(3, "x")]
    histogram = count(anns)
    assert histogram == {"x": 3, "y": 1}


def test_count_handles_empty_input() -> None:
    assert count([]) == {}


# ---------------------------------------------------------------------
# set_durations
# ---------------------------------------------------------------------
def test_set_durations_overwrites_by_label() -> None:
    anns = [_make(0, "trial"), _make(10, "rest"), _make(20, "trial")]
    out = set_durations(anns, {"trial": 5.0})
    assert [a.duration for a in out] == [5.0, 0.0, 5.0]


def test_set_durations_negative_clamps_to_zero() -> None:
    anns = [_make(0, "a")]
    out = set_durations(anns, {"a": -3.0})
    assert out[0].duration == 0.0


# ---------------------------------------------------------------------
# chunk_annotations
# ---------------------------------------------------------------------
def test_chunk_annotations_splits_long_range() -> None:
    ann = _make(0, "BAD_movement", duration=90)
    chunks = chunk_annotations(ann, chunk_duration_s=30)
    assert len(chunks) == 3
    assert [c.t for c in chunks] == [0, 30, 60]
    assert all(c.duration == pytest.approx(30) for c in chunks)
    assert all(c.text == "BAD_movement" for c in chunks)


def test_chunk_annotations_honours_overlap() -> None:
    ann = _make(0, "ep", duration=100)
    chunks = chunk_annotations(ann, chunk_duration_s=40, overlap_s=10)
    # step = 30; chunks start at 0, 30, 60, 90 — last one fits because
    # 90 < 100 and chunk_end clamps to t_end.
    starts = [c.t for c in chunks]
    assert starts == [0, 30, 60, 90]
    # Final chunk gets clipped to t_end (100), so duration 10 not 40.
    assert chunks[-1].duration == pytest.approx(10)


def test_chunk_annotations_point_annotation_passthrough() -> None:
    ann = _make(5, "point")
    chunks = chunk_annotations(ann, chunk_duration_s=10)
    assert chunks == [ann]


def test_chunk_annotations_rejects_bad_inputs() -> None:
    ann = _make(0, "x", duration=10)
    with pytest.raises(ValueError):
        chunk_annotations(ann, chunk_duration_s=0)
    with pytest.raises(ValueError):
        chunk_annotations(ann, chunk_duration_s=5, overlap_s=5)
    with pytest.raises(ValueError):
        chunk_annotations(ann, chunk_duration_s=5, overlap_s=-1)


def test_chunk_drops_sub_millisecond_trailing_fragment() -> None:
    # 30 s duration, 10-second chunks → exactly 3 full chunks, no
    # spurious fourth from floating-point drift.
    ann = _make(0, "x", duration=30.0)
    chunks = chunk_annotations(ann, chunk_duration_s=10.0)
    assert len(chunks) == 3
    assert not math.isclose(chunks[-1].duration, 0.0)
