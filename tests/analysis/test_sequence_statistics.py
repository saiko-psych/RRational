"""Tests for sequence_statistics — repeated-measures over section chains."""

from __future__ import annotations

import math

import numpy as np
import pytest

from rrational.analysis.sequence_statistics import (
    MIN_SUBJECTS,
    RM_ANOVA_MIN_SUBJECTS,
    PostHocPair,
    SequenceComparisonResult,
    _build_complete_matrix,
    _holm_correct,
    analyze_sequence,
)


# ---------------------------------------------------------------------
# _holm_correct
# ---------------------------------------------------------------------
def test_holm_correct_empty():
    assert _holm_correct([]) == []


def test_holm_correct_single_pvalue_unchanged():
    assert _holm_correct([0.04]) == [0.04]


def test_holm_correct_three_pvalues_match_textbook():
    """Holm: sorted [0.01, 0.04, 0.03] -> ranks [1,3,2]
    Adj: [0.01*3, 0.04*1, 0.03*2] = [0.03, 0.04, 0.06]
    Monotonised, mapped back to input order.
    """
    out = _holm_correct([0.01, 0.04, 0.03])
    assert out[0] == pytest.approx(0.03)
    assert out[1] == pytest.approx(0.06)
    assert out[2] == pytest.approx(0.06)


def test_holm_correct_clamps_to_one():
    assert _holm_correct([0.9, 0.9])[0] == 1.0


def test_holm_correct_monotone():
    """Adjusted p must be non-decreasing when sorted by raw p."""
    raw = [0.001, 0.05, 0.03, 0.04, 0.2]
    out = _holm_correct(raw)
    # Re-sort by raw p
    paired = sorted(zip(raw, out))
    sorted_adj = [a for _, a in paired]
    assert all(a <= b for a, b in zip(sorted_adj, sorted_adj[1:]))


# ---------------------------------------------------------------------
# _build_complete_matrix
# ---------------------------------------------------------------------
def test_build_complete_matrix_balanced():
    data = {"s1": [1.0, 2.0, 3.0], "s2": [10.0, 20.0, 30.0]}
    m, excl = _build_complete_matrix(data, ["s1", "s2"])
    assert m.shape == (3, 2)
    assert excl == 0
    np.testing.assert_array_equal(m[:, 0], [1.0, 2.0, 3.0])


def test_build_complete_matrix_drops_incomplete_subjects():
    # Subject 1 has no s2 value -> dropped
    data = {"s1": [1.0, 2.0, 3.0], "s2": [10.0, float("nan"), 30.0]}
    m, excl = _build_complete_matrix(data, ["s1", "s2"])
    assert m.shape == (2, 2)
    assert excl == 1


def test_build_complete_matrix_short_list_is_treated_as_missing():
    """If a section's list is shorter, the missing subjects are excluded."""
    data = {"s1": [1.0, 2.0, 3.0], "s2": [10.0]}
    m, excl = _build_complete_matrix(data, ["s1", "s2"])
    assert m.shape == (1, 2)
    assert excl == 2


def test_build_complete_matrix_preserves_section_order():
    data = {"a": [1.0, 2.0], "b": [10.0, 20.0], "c": [100.0, 200.0]}
    m, _ = _build_complete_matrix(data, ["c", "a", "b"])
    # Column 0 must be c
    np.testing.assert_array_equal(m[:, 0], [100.0, 200.0])
    np.testing.assert_array_equal(m[:, 1], [1.0, 2.0])


# ---------------------------------------------------------------------
# analyze_sequence — refusal cases
# ---------------------------------------------------------------------
def test_analyze_sequence_rejects_single_section():
    with pytest.raises(ValueError, match="at least 2 sections"):
        analyze_sequence({"s1": [1, 2, 3]}, "seq", "RMSSD", ["s1"])


def test_analyze_sequence_handles_insufficient_subjects():
    """Below MIN_SUBJECTS the result has a note and NaN stats, not an exception."""
    data = {"s1": [1.0, 2.0], "s2": [3.0, 4.0]}
    result = analyze_sequence(data, "seq", "RMSSD", ["s1", "s2"])
    assert result.n_complete_subjects == 2
    assert math.isnan(result.p_value)
    assert "insufficient" in result.test_name.lower()
    assert result.note is not None
    assert str(MIN_SUBJECTS) in result.note


# ---------------------------------------------------------------------
# analyze_sequence — Friedman (default)
# ---------------------------------------------------------------------
def test_analyze_sequence_friedman_runs_on_three_sections():
    """A clear monotone trend across 3 sections, 6 subjects → significant Friedman."""
    rng = np.random.default_rng(0)
    # subject baselines
    base = 50 + 10 * rng.standard_normal(6)
    data = {
        "rest": list(base),
        "music": list(base + 20),  # systematic +20
        "recover": list(base + 40),  # systematic +40
    }
    result = analyze_sequence(data, "demo", "RMSSD", ["rest", "music", "recover"])
    assert result.test_name == "Friedman"
    assert result.effect_size_name == "Kendall's W"
    assert result.is_parametric is False
    # Strong systematic difference → p should be very small
    assert result.p_value < 0.05
    # Kendall's W is in [0, 1]
    assert 0.0 <= result.effect_size <= 1.0


def test_analyze_sequence_post_hoc_has_correct_pair_count():
    """3 sections → C(3,2) = 3 pairs in post-hoc."""
    rng = np.random.default_rng(1)
    base = 50 + 5 * rng.standard_normal(5)
    data = {"a": list(base), "b": list(base + 5), "c": list(base + 10)}
    result = analyze_sequence(data, "seq", "RMSSD", ["a", "b", "c"])
    assert len(result.post_hoc) == 3
    pair_keys = {(p.section_a, p.section_b) for p in result.post_hoc}
    assert pair_keys == {("a", "b"), ("a", "c"), ("b", "c")}


def test_analyze_sequence_post_hoc_holm_adjusted_p_is_at_least_raw():
    """Holm-adjusted p is >= raw p (correction never makes things look more significant)."""
    rng = np.random.default_rng(2)
    base = 50 + 5 * rng.standard_normal(7)
    data = {
        "a": list(base),
        "b": list(base + 2),
        "c": list(base + 4),
        "d": list(base + 6),
    }
    result = analyze_sequence(data, "seq", "RMSSD", ["a", "b", "c", "d"])
    for pair in result.post_hoc:
        assert pair.p_value_corrected >= pair.p_value_raw - 1e-12


def test_analyze_sequence_descriptives_use_complete_cases_only():
    """Means/SDs match what numpy reports on the post-exclusion matrix."""
    data = {
        "a": [10.0, 20.0, 30.0],
        "b": [11.0, float("nan"), 33.0],  # subject 1 dropped
    }
    result = analyze_sequence(data, "seq", "RMSSD", ["a", "b"])
    # Subjects 0 and 2 only -> a: mean(10,30)=20, b: mean(11,33)=22
    assert result.n_complete_subjects == 2
    assert result.n_excluded_subjects == 1
    assert result.means["a"] == pytest.approx(20.0)
    assert result.means["b"] == pytest.approx(22.0)


# ---------------------------------------------------------------------
# analyze_sequence — RM-ANOVA opt-in
# ---------------------------------------------------------------------
def test_rm_anova_used_when_normal_and_n_large_and_prefer_parametric():
    rng = np.random.default_rng(42)
    n_subjects = RM_ANOVA_MIN_SUBJECTS + 5
    base = 50 + 5 * rng.standard_normal(n_subjects)
    data = {
        "a": list(base + 0.1 * rng.standard_normal(n_subjects)),
        "b": list(base + 5 + 0.1 * rng.standard_normal(n_subjects)),
        "c": list(base + 10 + 0.1 * rng.standard_normal(n_subjects)),
    }
    result = analyze_sequence(
        data, "seq", "RMSSD", ["a", "b", "c"], prefer_parametric=True
    )
    assert result.test_name == "RM-ANOVA"
    assert result.is_parametric is True
    assert result.effect_size_name == "partial eta-squared"
    # Strong systematic trend → significant
    assert result.p_value < 0.001
    # df is (k-1, (n-1)*(k-1)) tuple for ANOVA
    assert isinstance(result.df, tuple)
    assert result.df[0] == 2
    assert result.df[1] == (n_subjects - 1) * 2


def test_friedman_used_when_below_n_threshold_even_if_normal():
    rng = np.random.default_rng(7)
    # Just above MIN_SUBJECTS but below RM_ANOVA_MIN_SUBJECTS
    n = MIN_SUBJECTS + 1
    assert n < RM_ANOVA_MIN_SUBJECTS
    base = 50 + 5 * rng.standard_normal(n)
    data = {"a": list(base), "b": list(base + 5), "c": list(base + 10)}
    result = analyze_sequence(
        data, "seq", "RMSSD", ["a", "b", "c"], prefer_parametric=True
    )
    assert result.test_name == "Friedman"
    assert result.note is not None
    assert "power" in result.note.lower()


def test_friedman_used_when_normality_fails_even_if_prefer_parametric():
    rng = np.random.default_rng(9)
    n = RM_ANOVA_MIN_SUBJECTS + 5
    # Heavily right-skewed (exponential ** 3) — reliably fails Shapiro
    base = (rng.exponential(scale=1.0, size=n) ** 3) * 50
    data = {"a": list(base), "b": list(base + 3), "c": list(base + 6)}
    result = analyze_sequence(
        data, "seq", "RMSSD", ["a", "b", "c"], prefer_parametric=True
    )
    assert result.test_name == "Friedman"


# ---------------------------------------------------------------------
# Result dataclass surface
# ---------------------------------------------------------------------
def test_result_significance_stars():
    res = SequenceComparisonResult(
        sequence_name="x",
        metric="RMSSD",
        sections=["a", "b"],
        n_complete_subjects=5,
        n_excluded_subjects=0,
        means={"a": 1, "b": 2},
        sds={"a": 0.5, "b": 0.5},
        normality_p={"a": 0.5, "b": 0.5},
        test_name="Friedman",
        statistic=10.0,
        p_value=0.0005,
        df=1,
        effect_size=0.6,
        effect_size_name="Kendall's W",
        is_parametric=False,
    )
    assert res.significance == "***"


def test_post_hoc_pair_is_dataclass():
    p = PostHocPair(
        section_a="a",
        section_b="b",
        test_name="Wilcoxon signed-rank",
        statistic=2.0,
        p_value_raw=0.04,
        p_value_corrected=0.08,
        n_pairs=5,
    )
    assert p.section_a == "a"
    assert p.n_pairs == 5
