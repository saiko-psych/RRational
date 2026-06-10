"""Tests for reject_by_annotation (Cluster B9)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from rrational.analysis.annotation_filter import reject_by_annotation


@dataclass
class _Ann:
    """Minimal Annotation-compatible stand-in (no Qt / inspector dep)."""

    t: float
    duration: float
    text: str

    @property
    def t_end(self) -> float:
        return self.t + self.duration


def _make_rr(n: int = 10) -> tuple[np.ndarray, np.ndarray]:
    t = np.linspace(0, 90, n)
    rr = np.full(n, 800.0)
    return t, rr


def test_returns_unchanged_when_disabled() -> None:
    t, rr = _make_rr()
    anns = [_Ann(t=10, duration=20, text="BAD_movement")]
    out_t, out_rr = reject_by_annotation(t, rr, anns, enabled=False)
    assert np.array_equal(out_t, t)
    assert np.array_equal(out_rr, rr)


def test_drops_samples_inside_bad_range() -> None:
    t, rr = _make_rr(n=10)  # timestamps 0, 10, 20, ..., 90
    anns = [_Ann(t=25, duration=20, text="BAD_movement")]
    out_t, out_rr = reject_by_annotation(t, rr, anns)
    # Samples at t=30 and t=40 fall inside [25, 45] and should drop.
    assert 30.0 not in out_t
    assert 40.0 not in out_t
    assert 20.0 in out_t  # boundary just outside
    assert 50.0 in out_t


def test_ignores_non_bad_annotations() -> None:
    t, rr = _make_rr(n=10)
    anns = [_Ann(t=25, duration=20, text="rest")]
    out_t, _ = reject_by_annotation(t, rr, anns)
    assert len(out_t) == len(t)


def test_ignores_point_annotations() -> None:
    t, rr = _make_rr()
    anns = [_Ann(t=30, duration=0.0, text="BAD_blip")]
    out_t, _ = reject_by_annotation(t, rr, anns)
    # Point annotation has zero duration → no sample drops.
    assert len(out_t) == len(t)


def test_bad_prefix_is_case_insensitive() -> None:
    t, rr = _make_rr()
    anns = [_Ann(t=10, duration=20, text="bad_motion")]
    out_t, _ = reject_by_annotation(t, rr, anns)
    assert len(out_t) < len(t)


def test_multiple_bad_regions_union() -> None:
    t, rr = _make_rr(n=10)  # 0, 10, ..., 90
    anns = [
        _Ann(t=5, duration=10, text="BAD_one"),
        _Ann(t=55, duration=10, text="BAD_two"),
    ]
    out_t, _ = reject_by_annotation(t, rr, anns)
    # Drops samples at t=10 and t=60.
    assert 10.0 not in out_t
    assert 60.0 not in out_t


def test_raises_on_shape_mismatch() -> None:
    import pytest

    with pytest.raises(ValueError):
        reject_by_annotation(np.array([1, 2, 3]), np.array([1, 2]), [])
