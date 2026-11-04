"""Artifact detection + R-peak correction wrapper for the inspector.

Thin facade over ``rrational.cleaning.quality.correct_artifacts_lipponen``
(NeuroKit2's Kubios detector + Lipponen & Tarvainen 2019 correction). The cleaning module already does the
science; this layer just packages the result into something the
inspector's UI can consume — most importantly, the **time-domain
indices** of each artifact (so the plot can drop an ``ArtifactMarker``
at the right X position) and a per-grade quality summary.

The 2024 Quigley HRV-analysis guidelines dictate which metrics stay
valid at which artifact rates:
- < 2%   : excellent — all metrics
- 2–5%   : good — time + frequency domain
- 5–10%  : moderate — time domain only
- > 10%  : poor — recommend exclusion
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class PreprocessingResult:
    """Output of ``detect_artifacts``: indices, rate, corrected values, grade."""

    indices: np.ndarray  # int64, positions in the original t/v arrays
    by_type: dict[str, int] = field(default_factory=dict)  # "ectopic", "missed", ...
    total: int = 0
    rate: float = 0.0  # 0.0–1.0, fraction of beats that are artifacts
    # Lipponen & Tarvainen (2019) correction: missed beats are split and
    # extra beats merged, so the corrected series can be longer/shorter than
    # the input. It carries its own time axis (seconds, same basis as
    # ``data.t``; None if no times were given) and per-beat change flags.
    # NaN gap markers of the input are preserved at their original time.
    corrected_v: np.ndarray | None = None  # ms
    corrected_t: np.ndarray | None = None  # s, aligned 1:1 with corrected_v
    corrected_flags: np.ndarray | None = None  # bool, aligned with corrected_v
    n_inserted: int = 0
    n_removed: int = 0
    grade: str = "unknown"  # excellent / good / moderate / poor
    recommendation: str = ""


# Quality grade per artifact rate. The BOUNDARIES come from the shared
# rrational.gui.segmentation.quality_grade_from_rate (also used by the
# Streamlit app, should_exclude_segment and the .rrational export), so both
# GUIs grade a recording identically; this module only adds the messages.
# A private ``<`` table here once disagreed with it at exactly 2/5/10 %.
_GRADE_MESSAGES = {
    "excellent": "All HRV metrics are valid.",
    "good": "Time- and frequency-domain metrics valid.",
    "moderate": "Time-domain only; frequency-domain metrics are unreliable.",
    "poor": "Consider excluding this recording from analysis.",
}


def _grade_for_rate(rate: float) -> tuple[str, str]:
    from rrational.gui.segmentation import quality_grade_from_rate

    grade = quality_grade_from_rate(rate)
    return grade, _GRADE_MESSAGES[grade]


# A/B/C/D letter grade — same Quigley 2024 thresholds, just renamed for
# the cross-recording triage dashboard where the long-form names are too
# wide to fit alongside numeric columns.
_LETTER_GRADE_MAP = {
    "excellent": "A",
    "good": "B",
    "moderate": "C",
    "poor": "D",
    "unknown": "?",
}


def _grade_letter_for_rate(rate: float) -> str:
    """Return the A/B/C/D letter for ``rate`` (or '?' if non-finite)."""
    import math

    if not math.isfinite(rate):
        return "?"
    grade, _msg = _grade_for_rate(rate)
    return _LETTER_GRADE_MAP.get(grade, "?")


def detect_artifacts(v: np.ndarray, t: np.ndarray | None = None) -> PreprocessingResult:
    """Detect and correct artifacts in the RR-ms array ``v`` (L&T 2019).

    Detection is NK2's Kubios detector over all finite beats (indices are
    positions in ``v``). Correction is Lipponen & Tarvainen: missed beats
    split, extra beats merged, ectopic peaks moved, so the corrected series
    may differ in length. Pass the beat times ``t`` (seconds) to get
    ``corrected_t``. NaN samples (inter-section gaps) are never filled:
    each gap marker is re-inserted at the corrected position between the
    same two beats, with its original time.

    Returns a ``PreprocessingResult`` even on failure: if NeuroKit2 isn't
    installed or the array is too short (< 10 beats), the result has zero
    artifacts, the input as "corrected" series and grade "unknown".
    """
    from rrational.cleaning.quality import correct_artifacts_lipponen

    v = np.asarray(v, dtype=np.float64)
    t_arr = np.asarray(t, dtype=np.float64) if t is not None else None
    if t_arr is not None and len(t_arr) != len(v):
        t_arr = None
    finite_mask = np.isfinite(v)
    finite_v = v[finite_mask]

    if len(finite_v) < 10:
        return PreprocessingResult(
            indices=np.array([], dtype=np.int64),
            total=0,
            rate=0.0,
            corrected_v=v.copy(),
            corrected_t=t_arr.copy() if t_arr is not None else None,
            corrected_flags=np.zeros(len(v), dtype=bool),
            grade="unknown",
            recommendation="Recording too short for artifact detection (<10 beats).",
        )

    finite_t = t_arr[finite_mask] if t_arr is not None else None
    result = correct_artifacts_lipponen(
        [int(round(x)) for x in finite_v.tolist()],
        timestamps=finite_t.tolist() if finite_t is not None else None,
    )

    # Artifact indices: positions in the finite-only sub-array -> FULL array.
    finite_positions = np.nonzero(finite_mask)[0]
    artifact_finite_indices = np.asarray(
        result.get("artifact_indices", []), dtype=np.int64
    )
    if artifact_finite_indices.size > 0:
        full_artifact_indices = finite_positions[artifact_finite_indices]
    else:
        full_artifact_indices = np.array([], dtype=np.int64)

    # Re-insert NaN gap markers. A NaN at full position p lies between the
    # finite beats k-1 and k (k = finite beats before p); in the corrected
    # series that boundary is raw_to_corrected[k].
    corrected_finite = np.asarray(result["corrected_rr"], dtype=np.float64)
    flags_finite = np.asarray(result["corrected_flags"], dtype=bool)
    nan_positions = np.nonzero(~finite_mask)[0]
    bmap = np.asarray(result["raw_to_corrected"], dtype=np.int64)
    finite_before = np.cumsum(finite_mask)[nan_positions] if nan_positions.size else []
    insert_at = bmap[np.asarray(finite_before, dtype=np.int64)] if nan_positions.size else []
    corrected_full = np.insert(corrected_finite, insert_at, np.nan)
    flags_full = np.insert(flags_finite, insert_at, False)
    corrected_t = None
    cts = result.get("corrected_timestamps")
    if t_arr is not None and cts is not None and len(cts) == len(corrected_finite):
        corrected_t = np.insert(
            np.asarray(cts, dtype=np.float64), insert_at, t_arr[nan_positions]
        )

    rate = float(result["artifact_ratio"])
    grade, msg = _grade_for_rate(rate)

    return PreprocessingResult(
        indices=full_artifact_indices.astype(np.int64),
        by_type=dict(result.get("artifacts", {})),
        total=int(result["total_artifacts"]),
        rate=rate,
        corrected_v=corrected_full,
        corrected_t=corrected_t,
        corrected_flags=flags_full,
        n_inserted=int(result["n_inserted"]),
        n_removed=int(result["n_removed"]),
        grade=grade,
        recommendation=msg,
    )
