"""Artifact detection + R-peak correction wrapper for the inspector.

Thin facade over ``rrational.cleaning.quality.detect_artifacts_fixpeaks``
(NeuroKit2's Kubios algorithm). The cleaning module already does the
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
    corrected_v: np.ndarray | None = None  # ms, same length as input
    grade: str = "unknown"  # excellent / good / moderate / poor
    recommendation: str = ""


# Quality grade boundaries — Quigley 2024 + NeuroKit2 conventions.
_GRADE_THRESHOLDS = [
    (0.02, "excellent", "All HRV metrics are valid."),
    (0.05, "good", "Time- and frequency-domain metrics valid."),
    (0.10, "moderate", "Time-domain only; frequency-domain metrics are unreliable."),
    (float("inf"), "poor", "Consider excluding this recording from analysis."),
]


def _grade_for_rate(rate: float) -> tuple[str, str]:
    for threshold, grade, msg in _GRADE_THRESHOLDS:
        if rate < threshold:
            return grade, msg
    return "poor", "Consider excluding this recording from analysis."


def detect_artifacts(v: np.ndarray) -> PreprocessingResult:
    """Run NK2's Kubios fixpeaks on the RR-ms array ``v``.

    NaN samples (inter-section gaps) are passed through unchanged in
    the corrected output — we never invent data for a missing region.

    Returns a ``PreprocessingResult`` even on failure: if NeuroKit2
    isn't installed or the array is too short (< 10 beats), the result
    has zero artifacts and quality grade "unknown".
    """
    from rrational.cleaning.quality import detect_artifacts_fixpeaks

    # detect_artifacts_fixpeaks operates on a Python list of ints; NaN
    # samples are gap-markers we should strip before sending to NK2,
    # then re-inject at the right indices in the output.
    finite_mask = np.isfinite(v)
    finite_v = v[finite_mask]

    if len(finite_v) < 10:
        return PreprocessingResult(
            indices=np.array([], dtype=np.int64),
            total=0,
            rate=0.0,
            corrected_v=v.copy(),
            grade="unknown",
            recommendation="Recording too short for artifact detection (<10 beats).",
        )

    result = detect_artifacts_fixpeaks(
        rr_values=[int(round(x)) for x in finite_v.tolist()],
    )

    # Map artifact indices (positions in the finite-only sub-array) back to
    # indices in the FULL array. ``detect_artifacts_fixpeaks`` now returns
    # the merged set from NK2's info dict directly, so we no longer have to
    # reconstruct it by diffing corrected vs original (which silently lost
    # artifacts that happened to interpolate to the same value).
    finite_positions = np.nonzero(finite_mask)[0]
    artifact_finite_indices = np.asarray(
        result.get("artifact_indices", []), dtype=np.int64
    )
    if artifact_finite_indices.size > 0:
        full_artifact_indices = finite_positions[artifact_finite_indices]
    else:
        full_artifact_indices = np.array([], dtype=np.int64)

    # Rebuild corrected array at full length (NaNs preserved at gaps).
    corrected_finite = np.array(result["corrected_rr"], dtype=np.float64)
    corrected_full = v.copy()
    corrected_full[finite_positions] = corrected_finite

    rate = float(result["artifact_ratio"])
    grade, msg = _grade_for_rate(rate)

    return PreprocessingResult(
        indices=full_artifact_indices.astype(np.int64),
        by_type=dict(result.get("artifacts", {})),
        total=int(result["total_artifacts"]),
        rate=rate,
        corrected_v=corrected_full,
        grade=grade,
        recommendation=msg,
    )
