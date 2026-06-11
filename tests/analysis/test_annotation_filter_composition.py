"""Composition tests for ``crop`` + ``reject_by_annotation`` + ``chunk``.

Each operator has unit tests of its own; this file pins their joint
behaviour. The composition is what the inspector pipeline actually
runs (load -> crop to window -> reject BAD regions -> chunk long
spans) and the easy bug to introduce is one where each unit still
passes but the order or boundary handling silently changes the
samples that survive into HRV.

We use synthetic 1 Hz-spaced RR samples so the index math is easy to
reason about: timestamp 50 == sample index 50, the BAD window for a
[50, 100] annotation rejects 51 samples (inclusive on both ends, per
the source).
"""

from __future__ import annotations

import numpy as np

from rrational.analysis.annotation_filter import reject_by_annotation
from rrational.inspector.annotations import (
    Annotation,
    chunk_annotations,
    crop,
)


def _make_series(n: int = 150):
    """Per-second RR samples; timestamp == index for easy bookkeeping."""
    t = np.arange(n, dtype=float)
    rr = np.full(n, 800.0)
    return t, rr


def test_crop_then_reject_preserves_correct_indices() -> None:
    """Crop [0, 150] (no-op on the data) then reject BAD [50, 100]
    must leave indices outside [50, 100]. Inclusive endpoint matches
    the reject_by_annotation source.
    """
    t, rr = _make_series(n=150)
    bad = Annotation.create(t=50.0, text="BAD_motion", duration=50.0)
    # Crop the annotation list to [0, 150]; the BAD window survives intact.
    cropped_anns = crop([bad], tmin=0.0, tmax=150.0)
    t_kept, _ = reject_by_annotation(t, rr, cropped_anns)
    # Surviving indices: 0..49 and 101..149.
    expected_kept = np.concatenate([np.arange(0, 50), np.arange(101, 150)])
    np.testing.assert_array_equal(t_kept, expected_kept.astype(float))


def test_reject_then_crop_equivalent_to_crop_then_reject() -> None:
    """The two orderings should give the same kept-sample set when the
    crop window contains the annotation. ``reject`` operates on RR
    samples, ``crop`` operates on the annotation list -- their effects
    commute as long as crop does not chop part of the BAD region.
    """
    t, rr = _make_series(n=150)
    bad = Annotation.create(t=50.0, text="BAD_motion", duration=50.0)

    # Path A: crop annotations first, then reject.
    cropped = crop([bad], tmin=0.0, tmax=150.0)
    t_a, _ = reject_by_annotation(t, rr, cropped)

    # Path B: reject on the raw annotation, then crop the RR series
    # to the same window (no-op here since the window covers everything).
    t_rej, _ = reject_by_annotation(t, rr, [bad])
    # "Crop the RR series" is just a boolean mask on t.
    mask = (t_rej >= 0.0) & (t_rej <= 150.0)
    t_b = t_rej[mask]

    np.testing.assert_array_equal(t_a, t_b)


def test_chained_chunk_then_filter() -> None:
    """A long BAD span chunked into 10 s pieces should still reject the
    same RR samples as the original single annotation -- chunking is a
    bookkeeping operation, not a semantic one.
    """
    t, rr = _make_series(n=150)
    long_bad = Annotation.create(t=50.0, text="BAD_segment", duration=50.0)

    chunks = chunk_annotations(long_bad, chunk_duration_s=10.0)
    # Sanity: chunking must produce 5 pieces (50 s / 10 s) -- if the
    # algorithm changes we want the failure to surface here, not in a
    # downstream assertion on the kept-sample count.
    assert len(chunks) == 5

    t_chunked, _ = reject_by_annotation(t, rr, chunks)
    t_single, _ = reject_by_annotation(t, rr, [long_bad])
    np.testing.assert_array_equal(t_chunked, t_single)


def test_overlapping_BAD_regions_act_as_union() -> None:
    """Two overlapping BAD windows must reject the UNION, not the
    intersection. The reject_by_annotation source uses ``keep &= ~mask``
    inside its loop, so this is the natural behaviour -- pin it.
    """
    t, rr = _make_series(n=150)
    bad_a = Annotation.create(t=20.0, text="BAD_a", duration=30.0)  # [20, 50]
    bad_b = Annotation.create(t=40.0, text="BAD_b", duration=30.0)  # [40, 70]

    t_kept, _ = reject_by_annotation(t, rr, [bad_a, bad_b])
    # Union [20, 70] inclusive -> rejects indices 20..70 (51 samples).
    expected_kept = np.concatenate([np.arange(0, 20), np.arange(71, 150)])
    np.testing.assert_array_equal(t_kept, expected_kept.astype(float))


def test_crop_clips_annotation_then_reject_uses_clipped_range() -> None:
    """When the crop window slices a BAD annotation, only the clipped
    portion should drive rejection. Without this contract, a user
    cropping out the bad region in the UI would still see those
    samples drop in the analysis.
    """
    t, rr = _make_series(n=150)
    bad = Annotation.create(t=50.0, text="BAD_motion", duration=50.0)  # [50, 100]

    # Crop window stops at 70 -> annotation should clip to [50, 70].
    clipped = crop([bad], tmin=0.0, tmax=70.0)
    assert len(clipped) == 1
    assert clipped[0].t == 50.0
    assert clipped[0].duration == 20.0

    t_kept, _ = reject_by_annotation(t, rr, clipped)
    # Now only indices 50..70 (inclusive, 21 samples) drop.
    expected_kept = np.concatenate([np.arange(0, 50), np.arange(71, 150)])
    np.testing.assert_array_equal(t_kept, expected_kept.astype(float))
