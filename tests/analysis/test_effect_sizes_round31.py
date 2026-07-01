"""Round 31 regression tests for statistical effect-size + correction fixes.

Three confirmed defects in the stats layer:

- S1: Mann-Whitney U reported Cohen's d (a parametric pooled-SD measure)
  instead of the rank-biserial correlation appropriate for a rank test.
- S5: Kruskal-Wallis reported SS-based eta-squared instead of the rank-based
  epsilon-squared (Tomczak & Tomczak 2014).
- S4: a NaN p-value (from a test on constant data, which returns NaN without
  raising) poisoned the Holm correction for the whole family of comparisons.

Pure logic, no Qt.
"""

from __future__ import annotations

import math
import warnings

import numpy as np

from rrational.analysis.group_statistics import (
    _epsilon_squared_kruskal,
    _rank_biserial_from_u,
    adjust_pvalues,
    compare_groups,
)
from rrational.analysis.sequence_statistics import _holm_correct


# ---------------------------------------------------------------------
# S1 — rank-biserial for Mann-Whitney U
# ---------------------------------------------------------------------
def test_mann_whitney_reports_rank_biserial_not_cohens_d():
    rng = np.random.default_rng(0)
    g1 = rng.exponential(1.0, 50).tolist()  # skewed -> non-parametric path
    g2 = (rng.exponential(1.0, 50) + 2.0).tolist()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        r = compare_groups({"A": g1, "B": g2})
    assert r.test_name == "Mann-Whitney U"
    assert r.effect_size_name == "Rank-biserial r"
    # Bounded in [-1, 1], and clearly non-zero for these shifted samples.
    assert -1.0 <= r.effect_size <= 1.0
    assert abs(r.effect_size) > 0.3


def test_rank_biserial_formula_bounds_and_sign():
    # U = 0 -> maximal positive effect (r = 1); U = n1*n2 -> r = -1.
    assert _rank_biserial_from_u(0.0, 10, 10) == 1.0
    assert _rank_biserial_from_u(100.0, 10, 10) == -1.0
    assert _rank_biserial_from_u(50.0, 10, 10) == 0.0
    assert math.isnan(_rank_biserial_from_u(5.0, 0, 10))


def test_parametric_two_group_still_reports_cohens_d():
    rng = np.random.default_rng(1)
    g1 = rng.normal(50, 5, 40).tolist()
    g2 = rng.normal(55, 5, 40).tolist()
    r = compare_groups({"A": g1, "B": g2})
    assert r.test_name == "Welch's t-test"
    assert r.effect_size_name == "Cohen's d"


# ---------------------------------------------------------------------
# S5 — epsilon-squared for Kruskal-Wallis
# ---------------------------------------------------------------------
def test_kruskal_reports_epsilon_squared_not_eta():
    rng = np.random.default_rng(0)
    r = compare_groups(
        {
            "A": rng.exponential(20, 25).tolist(),
            "B": rng.exponential(40, 25).tolist(),
            "C": rng.exponential(60, 25).tolist(),
        }
    )
    assert r.test_name == "Kruskal-Wallis"
    assert r.effect_size_name == "ε²"  # epsilon-squared
    assert 0.0 <= r.effect_size <= 1.0


def test_epsilon_squared_formula():
    # (H - k + 1) / (n - k)
    groups = [np.zeros(25), np.zeros(25), np.zeros(25)]
    assert _epsilon_squared_kruskal(22.4, groups) == (22.4 - 3 + 1) / (75 - 3)
    # Degenerate n <= k -> NaN.
    assert math.isnan(_epsilon_squared_kruskal(1.0, [np.zeros(1), np.zeros(1)]))


# ---------------------------------------------------------------------
# S4 — NaN p-value must not poison the Holm family
# ---------------------------------------------------------------------
def test_holm_correct_sanitizes_nan_to_one():
    nan_result = _holm_correct([0.01, float("nan"), 0.04])
    clean_result = _holm_correct([0.01, 1.0, 0.04])
    # A NaN entry must be treated as p=1.0, giving the SAME adjusted values
    # as if the caller had passed 1.0 — and must not corrupt the other pairs.
    assert nan_result == clean_result
    assert all(math.isfinite(p) for p in nan_result)


def test_adjust_pvalues_sanitizes_nan_raw_p():
    # Build two results, one carrying a NaN p (as a constant-data test would).
    rng = np.random.default_rng(2)
    r_ok = compare_groups(
        {"A": rng.normal(50, 5, 20).tolist(), "B": rng.normal(56, 5, 20).tolist()}
    )
    r_nan = compare_groups(
        {"A": rng.normal(50, 5, 20).tolist(), "B": rng.normal(52, 5, 20).tolist()}
    )
    object.__setattr__(r_nan, "p_value", float("nan"))
    out = adjust_pvalues([r_ok, r_nan], method="holm")
    for r in out:
        assert math.isfinite(r.p_value)
        assert 0.0 <= r.p_value <= 1.0
