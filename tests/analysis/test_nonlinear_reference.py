"""Reference-value tests for sample_entropy / approximate_entropy.

``test_nonlinear.py`` already covers the NaN-guard contract and the
relative ordering SampEn < ApEn on simple periodic input. These tests
add coverage against well-known reference series so a future refactor
of the embedding / Chebyshev-distance code cannot silently change the
numerical output without one of these assertions tripping.

The logistic-map fixture uses ``r = 4`` (fully chaotic regime) which
Richman & Moorman 2000 and follow-up work cite as a canonical input
for entropy benchmarks. The exact SampEn value reported in the
literature varies (different m, r, N, seed) so we assert membership in
a broad plausibility band rather than equality.
"""

from __future__ import annotations

import math

import numpy as np

from rrational.analysis.nonlinear import (
    approximate_entropy,
    sample_entropy,
)


def _logistic_map(n: int, r: float = 4.0, seed: int = 42) -> np.ndarray:
    """Iterate the logistic map ``x_{n+1} = r * x_n * (1 - x_n)``.

    The seed picks the initial condition deterministically so two
    runs produce identical series; this matters for the reference-band
    assertion below, which would otherwise be flaky.
    """
    rng = np.random.default_rng(seed)
    x = float(rng.uniform(0.1, 0.9))
    out = np.empty(n, dtype=float)
    for i in range(n):
        x = r * x * (1.0 - x)
        out[i] = x
    return out


def test_sample_entropy_logistic_map_r4_matches_published_band() -> None:
    """Fully-chaotic logistic map (r=4, N=500) should land in the
    published SampEn band. Literature reports values around 0.5 -- 0.8
    for similar m/r choices; we use atol=0.2 around 0.6 to cover the
    span without false positives.
    """
    series = _logistic_map(n=500, r=4.0, seed=42)
    sampen = sample_entropy(series, m=2, r=0.2)
    assert math.isfinite(sampen), "SampEn must be finite on a chaotic series"
    # Generous band -- the exact published value depends on m, r, N,
    # and the embedding convention. 0.4 -- 0.8 covers every reference
    # we found while still rejecting clearly-broken implementations.
    assert 0.4 <= sampen <= 0.8, f"SampEn {sampen} out of band for r=4 logistic map"


def test_apen_geq_sampen_on_chaotic_input() -> None:
    """ApEn includes self-matches; SampEn excludes them. The known
    consequence is that ApEn is biased upward relative to SampEn on
    short-to-medium series, so ApEn >= SampEn holds for typical inputs.
    Asserting this on the logistic map locks in the bias direction.
    """
    series = _logistic_map(n=500, r=4.0, seed=42)
    apen = approximate_entropy(series, m=2, r=0.2)
    sampen = sample_entropy(series, m=2, r=0.2)
    assert math.isfinite(apen) and math.isfinite(sampen)
    # Allow a tiny float-comparison slack -- this is not the place to
    # debate whether ApEn == SampEn for one specific seed.
    assert apen >= sampen - 1e-9


def test_sample_entropy_extreme_r_returns_finite_or_nan() -> None:
    """When ``r`` is so large that every pair matches, sample_entropy
    will see sum_a == sum_b and the log argument becomes 1 (entropy 0),
    or it may fall back to the NaN guard if the count overflows. Either
    way the call must not raise.
    """
    series = _logistic_map(n=200, r=4.0, seed=1)
    out = sample_entropy(series, m=2, r=10.0)
    # The contract is just "no exception, scalar float". Both math.nan
    # and a finite zero are acceptable outcomes.
    assert isinstance(out, float)
    assert math.isnan(out) or math.isfinite(out)


def test_sample_entropy_short_series_returns_nan() -> None:
    """The NaN guard in the source fires when ``len(rr) < m + 2``.
    Five samples with default m=2 is the smallest input we still
    consider 'real-looking' rather than degenerate empty input.
    """
    out = sample_entropy(np.array([800.0, 810.0, 820.0, 805.0, 815.0]), m=2, r=0.2)
    # m+2 == 4, so 5 samples should NOT trigger the short-series
    # guard. The genuinely-short case is 3 samples with m=2.
    short = sample_entropy(np.array([800.0, 810.0, 820.0]), m=2, r=0.2)
    assert math.isnan(short), "3-sample input must hit the NaN guard"
    # And the 5-sample case must be either finite or a NaN coming from
    # a downstream branch (sum_a/sum_b == 0) -- never an exception.
    assert isinstance(out, float)


def test_apen_and_sampen_agree_on_constant_series_being_nan() -> None:
    """Both functions guard against zero std. The constant-input case
    is mirrored across the two implementations -- a regression where
    only one guard fires would mean the other quietly returns -inf or
    raises. Pin both behaviours together so the symmetry is enforced.
    """
    constant = np.full(100, 800.0)
    assert math.isnan(approximate_entropy(constant))
    assert math.isnan(sample_entropy(constant))
