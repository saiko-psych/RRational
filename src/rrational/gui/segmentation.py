"""Unified time-based segmentation for artifact detection and HRV analysis.

Both artifact detection and analysis must operate on identical segment boundaries.
Segments are always time-based (not beat-based) for scientific correctness:
a 5-minute window is exactly 5 minutes regardless of heart rate.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Quigley 2024 artifact-rate thresholds (fraction of beats, 0-1)
_RATE_EXCELLENT = 0.02  # <= 2%  -> excellent
_RATE_GOOD = 0.05  # <= 5%  -> good
_RATE_MODERATE = 0.10  # <= 10% -> moderate; > 10% -> poor
_EXCLUDE_RATE_PCT = 10.0  # artifact % above which a segment is excluded
_MIN_BEATS = 50  # absolute minimum beats for any analysis


@dataclass(slots=True)
class Segment:
    """A time-based analysis segment used by both artifact detection and HRV analysis."""

    idx: int
    start_ms: float  # cumulative ms from recording start
    end_ms: float
    beat_start: int  # index into RR array (inclusive)
    beat_end: int  # index into RR array (exclusive, slice-compatible)
    n_beats: int
    duration_s: float
    # populated after artifact detection
    artifact_count: int = 0
    artifact_pct: float = 0.0
    quality_grade: str = ""
    included: bool = True


def generate_segments(
    rr_ms: np.ndarray,
    window_s: float = 300.0,
    overlap_pct: float = 0.0,
) -> list[Segment]:
    """Generate time-based segments from RR intervals.

    Uses numpy vectorization: cumsum for elapsed time, searchsorted for
    O(n log n) window boundary lookup.

    Args:
        rr_ms: RR intervals in milliseconds (1-D array or list).
        window_s: Window duration in seconds (default 300 = 5 min).
        overlap_pct: Overlap percentage (0 for artifact detection, e.g. 50 for analysis).

    Returns:
        List of Segment objects with time and beat-index boundaries.
    """
    rr = np.asarray(rr_ms, dtype=np.float64)
    if rr.size == 0:
        return []

    window_ms = window_s * 1000.0
    step_ms = window_ms * (1.0 - overlap_pct / 100.0)
    if step_ms <= 0:
        return []

    # cumulative elapsed time at beat start (beat i starts at cumsum[i])
    elapsed = np.empty(rr.size, dtype=np.float64)
    elapsed[0] = 0.0
    np.cumsum(rr[:-1], out=elapsed[1:])

    total_ms = elapsed[-1] + rr[-1]

    # window start positions (include trailing partial segment)
    n_full = max(1, int(np.floor((total_ms - window_ms) / step_ms)) + 1)
    starts = np.arange(n_full, dtype=np.float64) * step_ms
    ends = starts + window_ms

    # add trailing partial segment if it has uncovered beats
    last_end = ends[-1] if len(ends) > 0 else 0.0
    if last_end < total_ms:
        trail_start = starts[-1] + step_ms if len(starts) > 0 else 0.0
        if trail_start < total_ms:
            starts = np.append(starts, trail_start)
            ends = np.append(ends, total_ms)

    # clip to total duration
    ends = np.minimum(ends, total_ms)

    # vectorized boundary lookup
    # Round 29 — verified that side="left" on BOTH starts and ends is
    # the intended convention: adjacent windows share the same beat
    # index (segs[0].beat_end == segs[1].beat_start) so a 300 s / 800 ms
    # window produces 375 beats, not 376. The agent's "off-by-one"
    # claim was a misread of the dataclass docstring. See
    # tests/segments/test_segmentation.py for the encoded invariant.
    beat_starts = np.searchsorted(elapsed, starts, side="left")
    beat_ends = np.searchsorted(elapsed, ends, side="left")

    segments = []
    for i in range(len(starts)):
        bs, be = int(beat_starts[i]), int(beat_ends[i])
        n = be - bs
        if n < 1:
            continue
        dur_s = float(ends[i] - starts[i]) / 1000.0
        segments.append(
            Segment(
                idx=len(segments),
                start_ms=float(starts[i]),
                end_ms=float(ends[i]),
                beat_start=bs,
                beat_end=be,
                n_beats=n,
                duration_s=dur_s,
            )
        )

    return segments


def quality_grade_from_rate(artifact_rate: float) -> str:
    """Map an artifact rate (fraction of beats, 0-1) to a quality grade.

    Quigley 2024 thresholds. Returns one of: "excellent", "good", "moderate",
    "poor". This is the single source of truth for quality grades across the
    artifact-detection panel, the analysis tab and the .rrational export.

    Boundaries are INCLUSIVE on the upper side (``<=``): a rate of exactly
    2% is "excellent", exactly 5% is "good", exactly 10% is "moderate".
    Quigley 2024 Table 2 is reportedly slightly different (``<10%`` for
    moderate, ``>=10%`` for poor) — kept inclusive here for backward
    compatibility with the rest of the pipeline; revisit if Quigley
    compliance is required for publication.
    """
    if artifact_rate <= _RATE_EXCELLENT:
        return "excellent"
    if artifact_rate <= _RATE_GOOD:
        return "good"
    if artifact_rate <= _RATE_MODERATE:
        return "moderate"
    return "poor"


def assess_segment_quality(seg: Segment) -> str:
    """Quality grade for a segment, per Quigley 2024.

    Returns "excellent", "good", "moderate" or "poor". Whether a segment must
    be *excluded* from analysis is a separate decision — see
    should_exclude_segment().
    """
    return quality_grade_from_rate(seg.artifact_pct / 100.0)


def should_exclude_segment(seg: Segment) -> bool:
    """Whether a segment must be excluded from analysis (Quigley 2024).

    A segment is excluded when its artifact rate exceeds 10% or it has fewer
    than 50 beats (too short for any reliable HRV metric).
    """
    return seg.artifact_pct > _EXCLUDE_RATE_PCT or seg.n_beats < _MIN_BEATS


def format_ms_as_time(ms: float) -> str:
    """Format cumulative milliseconds as MM:SS."""
    total_s = int(ms / 1000)
    return f"{total_s // 60}:{total_s % 60:02d}"


def windows_from_detection_segments(
    det_segments, inclusion: dict, nn_values, artifact_data: dict, min_beats: int = 30
):
    """HRV windows from artifact-detection segments, or None if they don't apply.

    Detection segments hold RAW beat indices of the array the detection ran
    on. They may only be used on ``nn_values`` if that is exactly the
    detection's own corrected series (``artifact_data["corrected_rr"]``);
    the raw bounds are then translated with the raw->corrected map (L&T
    correction can split/merge beats). For any other NN array (another
    section, a cleaned subset, NN loaded from a file) the raw indices would
    point at unrelated beats, so None is returned and the caller should use
    fresh time-based segments.

    Returns a list of ``(segment_idx, start_ms, nn_slice)`` for included
    segments with at least ``min_beats`` beats. ``inclusion`` overrides
    ``seg.included`` per segment index.
    """
    import numpy as _np

    corrected = artifact_data.get("corrected_rr") if artifact_data else None
    if not det_segments or corrected is None:
        return None
    nn = _np.asarray(nn_values, dtype=_np.float64)
    corr = _np.asarray(corrected, dtype=_np.float64)
    if nn.shape != corr.shape or not _np.allclose(nn, corr):
        return None

    bmap = artifact_data.get("raw_to_corrected")
    if not bmap:
        original = artifact_data.get("original_rr")
        if original is not None and len(original) != len(corr):
            return None
        bmap = list(range(len(corr) + 1))
    n_raw = len(bmap) - 1

    windows = []
    for seg in det_segments:
        if not inclusion.get(seg.idx, seg.included):
            continue
        s = min(max(int(seg.beat_start), 0), n_raw)
        e = min(max(int(seg.beat_end), s), n_raw)
        sliced = nn[int(bmap[s]) : int(bmap[e])].tolist()
        if len(sliced) >= min_beats:
            windows.append((seg.idx, seg.start_ms, sliced))
    return windows
