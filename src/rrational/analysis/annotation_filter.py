"""Annotation-aware filtering for RR series (Cluster B9).

MNE's ``raw.get_data(reject_by_annotation='omit')`` strips samples
covered by any BAD_*-prefixed annotation before downstream analysis.
We expose the same contract for RR-interval series: feed in a
``(t, rr)`` pair plus a list of :class:`~rrational.inspector.annotations.Annotation`,
get back the subset with BAD_* regions excised.

The filter is deliberately stateless and free of inspector/UI imports
— it lives in the analysis package so the HRV pipeline can call it
without dragging Qt into the import graph.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np

# Per MNE convention, only annotations whose description starts with
# the case-insensitive ``BAD`` prefix are treated as rejection masks.
_BAD_PREFIX = "bad"


def _is_bad(text: str) -> bool:
    """Return True for annotations that should reject samples."""
    return bool(text) and text.lower().startswith(_BAD_PREFIX)


def reject_by_annotation(
    t: np.ndarray,
    rr: np.ndarray,
    annotations: Iterable,
    *,
    enabled: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Drop samples whose timestamps fall inside any BAD_* annotation.

    Parameters
    ----------
    t
        Per-beat timestamps (seconds-since-epoch). Same length as ``rr``.
    rr
        RR intervals (ms).
    annotations
        Iterable of objects exposing ``t`` (onset, seconds-since-epoch)
        and ``t_end`` (onset + duration). The inspector's
        ``Annotation`` dataclass already matches this shape; tests can
        pass tuples wrapped in a lightweight namespace.
    enabled
        When False, returns the inputs unchanged. Lets callers thread
        a single ``reject_by_annotation: bool = True`` flag through
        their pipeline without a conditional at every call site.

    Returns
    -------
    (t_kept, rr_kept)
        Same shape as the input arrays minus the rejected samples.
        Order is preserved; no sorting / deduplication is applied.
    """
    t = np.asarray(t, dtype=float)
    rr = np.asarray(rr, dtype=float)
    if t.shape != rr.shape:
        raise ValueError(f"t and rr must share shape; got {t.shape} vs {rr.shape}")
    if not enabled:
        return t, rr

    keep = np.ones(t.shape, dtype=bool)
    for ann in annotations:
        if not _is_bad(getattr(ann, "text", "")):
            continue
        # Range annotations: drop everything inside [t, t_end].
        # Point annotations have duration 0 → no rejection (point
        # markers are notes, not rejection regions; matches MNE
        # convention where ``BAD_*`` point markers are also ignored).
        a_start = float(getattr(ann, "t", 0.0))
        a_end = float(getattr(ann, "t_end", a_start))
        if a_end <= a_start:
            continue
        keep &= ~((t >= a_start) & (t <= a_end))
    return t[keep], rr[keep]
