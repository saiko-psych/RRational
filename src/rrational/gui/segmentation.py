"""Unified time-based segmentation for artifact detection and HRV analysis.

Both artifact detection and analysis must operate on identical segment boundaries.
Segments are always time-based (not beat-based) for scientific correctness:
a 5-minute window is exactly 5 minutes regardless of heart rate.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Quigley 2024 thresholds
_ARTIFACT_EXCLUDE = 10.0  # % -> exclude segment
_ARTIFACT_POOR = 5.0      # % -> poor quality
_ARTIFACT_FAIR = 2.0      # % -> fair quality
_MIN_BEATS = 50           # absolute minimum for any analysis


@dataclass(slots=True)
class Segment:
    """A time-based analysis segment used by both artifact detection and HRV analysis."""
    idx: int
    start_ms: float       # cumulative ms from recording start
    end_ms: float
    beat_start: int       # index into RR array (inclusive)
    beat_end: int          # index into RR array (exclusive, slice-compatible)
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
    beat_starts = np.searchsorted(elapsed, starts, side="left")
    beat_ends = np.searchsorted(elapsed, ends, side="left")

    segments = []
    for i in range(len(starts)):
        bs, be = int(beat_starts[i]), int(beat_ends[i])
        n = be - bs
        if n < 1:
            continue
        dur_s = float(ends[i] - starts[i]) / 1000.0
        segments.append(Segment(
            idx=len(segments),
            start_ms=float(starts[i]),
            end_ms=float(ends[i]),
            beat_start=bs,
            beat_end=be,
            n_beats=n,
            duration_s=dur_s,
        ))

    return segments


def assess_segment_quality(seg: Segment) -> str:
    """Assign quality grade based on Quigley 2024 guidelines.

    Returns one of: "good", "fair", "poor", "exclude".
    """
    if seg.artifact_pct > _ARTIFACT_EXCLUDE or seg.n_beats < _MIN_BEATS:
        return "exclude"
    if seg.artifact_pct > _ARTIFACT_POOR:
        return "poor"
    if seg.artifact_pct > _ARTIFACT_FAIR:
        return "fair"
    return "good"


def format_ms_as_time(ms: float) -> str:
    """Format cumulative milliseconds as MM:SS."""
    total_s = int(ms / 1000)
    return f"{total_s // 60}:{total_s % 60:02d}"
