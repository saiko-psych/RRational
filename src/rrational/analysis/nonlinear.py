"""Non-linear HRV metrics: sample-entropy and approximate-entropy.

Cluster B7 — implements the textbook ``ApEn`` (Pincus 1991) and
``SampEn`` (Richman & Moorman 2000) families used as complexity
measures in HRV research. Implementation strategy follows the public
reference in MNE-features
(``github.com/mne-tools/mne-features``, BSD-3-Clause) — chunked
distance scan rather than building the full template-distance matrix,
so memory stays O(n) for n-beat series.

Both metrics share the embedding-and-counting backbone:

1. Embed the 1-D series into m-dimensional templates X[i] = rr[i : i+m].
2. For each template, count templates X[j] with Chebyshev-distance
   ``<= r * std(rr)``.
3. ApEn(m, r) = phi(m) - phi(m+1), where phi(k) is the mean log of
   per-template self-inclusive match counts.
4. SampEn(m, r) = -ln(A / B), where A = matches at length m+1 and
   B = matches at length m, both excluding self-matches.

The ``r`` tolerance is supplied as a fraction of the series standard
deviation, which is the convention every HRV reference uses (Pincus
1991, Richman 2000, Lippman 1994).
"""

from __future__ import annotations

import numpy as np

# Default embedding dimension + tolerance. m=2 and r=0.2*sigma are the
# textbook HRV defaults (Pincus 1991, Lake et al. 2002). Exposed as
# constants so unit tests can pin them without re-reading the paper.
DEFAULT_M = 2
DEFAULT_R = 0.2


def _embed(x: np.ndarray, m: int) -> np.ndarray:
    """Return the (n-m+1, m) sliding-window template matrix.

    ``np.lib.stride_tricks.sliding_window_view`` is the most memory-
    efficient way to do this — no copy, the returned view shares
    storage with ``x``. Caller must not mutate the view.
    """
    if x.ndim != 1:
        raise ValueError("embedding requires a 1-D array")
    if m < 1:
        raise ValueError("m must be >= 1")
    if x.size < m:
        return np.empty((0, m), dtype=x.dtype)
    return np.lib.stride_tricks.sliding_window_view(x, m)


def _chebyshev_match_counts(
    templates: np.ndarray, tol: float, exclude_self: bool
) -> np.ndarray:
    """For each template return the count of templates within Chebyshev tol.

    Uses a chunked O(n) inner loop instead of materialising the full
    (n, n) distance matrix — important for long RR series (10k+ beats)
    where a dense matrix would blow past 1 GB.
    """
    n = templates.shape[0]
    counts = np.empty(n, dtype=np.int64)
    # Process row-by-row; numpy broadcasts each template against all
    # others, then we collapse along the embedding axis with max.
    for i in range(n):
        diffs = np.max(np.abs(templates - templates[i]), axis=1)
        matches = int(np.sum(diffs <= tol))
        if exclude_self:
            matches -= 1  # discount the template's match against itself
        counts[i] = matches
    return counts


def _phi(rr: np.ndarray, m: int, r_abs: float) -> float:
    """ApEn helper: mean log of self-inclusive match probability."""
    templates = _embed(rr, m)
    n = templates.shape[0]
    if n == 0:
        return float("nan")
    counts = _chebyshev_match_counts(templates, r_abs, exclude_self=False)
    # Pincus 1991 normalises by N - m + 1. Log of 0 cannot happen here
    # because every template at least matches itself (self-inclusive).
    probabilities = counts / n
    return float(np.mean(np.log(probabilities)))


def approximate_entropy(
    rr: np.ndarray | list[float], m: int = DEFAULT_M, r: float = DEFAULT_R
) -> float:
    """Approximate entropy ApEn(m, r) of an RR series.

    Parameters
    ----------
    rr
        1-D RR series. Units do not matter — the tolerance is rescaled
        by the empirical standard deviation.
    m
        Embedding dimension. Default 2 (textbook HRV choice).
    r
        Tolerance as a fraction of ``std(rr)``. Default 0.2.

    Returns
    -------
    float
        ApEn(m, r). ``NaN`` if the series is too short (``len(rr) < m + 1``)
        or its standard deviation is zero (constant series).
    """
    rr = np.asarray(rr, dtype=float).ravel()
    if rr.size < m + 1:
        return float("nan")
    sigma = float(np.std(rr, ddof=0))
    if sigma == 0.0:
        return float("nan")
    r_abs = r * sigma
    return _phi(rr, m, r_abs) - _phi(rr, m + 1, r_abs)


def sample_entropy(
    rr: np.ndarray | list[float], m: int = DEFAULT_M, r: float = DEFAULT_R
) -> float:
    """Sample entropy SampEn(m, r) of an RR series.

    Unlike ApEn, SampEn excludes self-matches and conditions on
    length-m matches when computing length-(m+1) matches. Both
    properties make it less biased for short series.

    Parameters
    ----------
    rr
        1-D RR series.
    m
        Embedding dimension. Default 2.
    r
        Tolerance as a fraction of ``std(rr)``. Default 0.2.

    Returns
    -------
    float
        SampEn(m, r). ``NaN`` if the series is too short, its standard
        deviation is zero, or no length-(m+1) matches occur (the log
        would diverge — Richman & Moorman 2000 §IV recommends raising
        ``r`` or shortening ``m`` in that case).
    """
    rr = np.asarray(rr, dtype=float).ravel()
    if rr.size < m + 2:
        return float("nan")
    sigma = float(np.std(rr, ddof=0))
    if sigma == 0.0:
        return float("nan")
    r_abs = r * sigma

    # Count length-m and length-(m+1) matches, both excluding self.
    tm = _embed(rr, m)
    tm1 = _embed(rr, m + 1)
    # Both template arrays must have the same number of rows for the
    # SampEn ratio to be conditional on length-m matches. Truncate the
    # length-m table to match length-(m+1) row count.
    n_pairs = tm1.shape[0]
    tm = tm[:n_pairs]

    b_counts = _chebyshev_match_counts(tm, r_abs, exclude_self=True)
    a_counts = _chebyshev_match_counts(tm1, r_abs, exclude_self=True)
    # Aggregate sums (per Richman & Moorman): SampEn = -ln(sum(A) / sum(B)).
    sum_b = int(np.sum(b_counts))
    sum_a = int(np.sum(a_counts))
    if sum_b == 0 or sum_a == 0:
        return float("nan")
    return float(-np.log(sum_a / sum_b))
