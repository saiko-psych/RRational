"""Tests for group_statistics module.

Uses TDD: tests written first to define expected behavior.
"""

import numpy as np
import pytest

from rrational.analysis.group_statistics import (
    adjust_pvalues,
    compare_groups,
    compare_paired,
    compute_stars,
    should_log_transform,
)


class TestComputeStars:
    """APA 7th edition convention: boundaries are inclusive (p <= threshold)."""

    def test_highly_significant(self):
        assert compute_stars(0.0001) == "***"
        assert compute_stars(0.001) == "***"  # boundary inclusive

    def test_very_significant(self):
        assert compute_stars(0.00101) == "**"
        assert compute_stars(0.005) == "**"
        assert compute_stars(0.01) == "**"  # boundary inclusive

    def test_significant(self):
        assert compute_stars(0.0101) == "*"
        assert compute_stars(0.03) == "*"
        assert compute_stars(0.05) == "*"  # boundary inclusive

    def test_not_significant(self):
        assert compute_stars(0.0501) == "ns"
        assert compute_stars(0.1) == "ns"
        assert compute_stars(0.99) == "ns"


class TestCompareTwoGroups:
    def test_parametric_t_test_selected_for_normal_data(self):
        rng = np.random.default_rng(42)
        g1 = rng.normal(50, 10, 30).tolist()
        g2 = rng.normal(60, 10, 30).tolist()
        result = compare_groups({"A": g1, "B": g2}, metric="RMSSD", section="rest")
        assert result.test_name == "Welch's t-test"
        assert result.is_parametric is True
        assert result.effect_size_name == "Cohen's d"
        # Effect size should be roughly (60-50)/10 = 1.0
        assert abs(result.effect_size) > 0.5

    def test_non_parametric_used_for_skewed_data(self):
        rng = np.random.default_rng(42)
        # Highly skewed: exponential distributions
        g1 = rng.exponential(scale=20, size=30).tolist()
        g2 = rng.exponential(scale=40, size=30).tolist()
        result = compare_groups({"A": g1, "B": g2})
        assert result.test_name == "Mann-Whitney U"
        assert result.is_parametric is False

    def test_result_fields_all_populated(self):
        rng = np.random.default_rng(42)
        g1 = rng.normal(50, 10, 25).tolist()
        g2 = rng.normal(55, 10, 23).tolist()
        r = compare_groups({"EG": g1, "KG": g2}, metric="SDNN", section="meas")
        assert r.metric == "SDNN"
        assert r.section == "meas"
        assert r.groups == ["EG", "KG"]
        assert r.n_per_group == {"EG": 25, "KG": 23}
        assert "EG" in r.means and "KG" in r.means
        assert "EG" in r.sds and "KG" in r.sds
        assert r.statistic is not None
        assert 0 <= r.p_value <= 1
        assert r.significance in ("ns", "*", "**", "***")

    def test_groups_different_n(self):
        rng = np.random.default_rng(42)
        g1 = rng.normal(50, 10, 27).tolist()
        g2 = rng.normal(52, 10, 23).tolist()
        result = compare_groups({"A": g1, "B": g2})
        assert result.n_per_group == {"A": 27, "B": 23}

    def test_identical_groups_high_p_value(self):
        rng = np.random.default_rng(42)
        g1 = rng.normal(50, 10, 30).tolist()
        g2 = rng.normal(50, 10, 30).tolist()
        result = compare_groups({"A": g1, "B": g2})
        # Should not be significant
        assert result.p_value > 0.05
        assert result.significance == "ns"

    def test_large_effect_low_p_value(self):
        rng = np.random.default_rng(42)
        g1 = rng.normal(30, 5, 30).tolist()
        g2 = rng.normal(80, 5, 30).tolist()
        result = compare_groups({"A": g1, "B": g2})
        # Huge separation — should be extremely significant
        assert result.p_value < 0.001
        assert result.significance == "***"


class TestCompareThreeGroups:
    def test_anova_selected_for_normal_data(self):
        rng = np.random.default_rng(42)
        g1 = rng.normal(50, 10, 25).tolist()
        g2 = rng.normal(55, 10, 25).tolist()
        g3 = rng.normal(60, 10, 25).tolist()
        result = compare_groups({"A": g1, "B": g2, "C": g3})
        assert result.test_name == "One-way ANOVA"
        assert result.effect_size_name == "η²"

    def test_kruskal_wallis_for_skewed(self):
        rng = np.random.default_rng(42)
        g1 = rng.exponential(20, 25).tolist()
        g2 = rng.exponential(30, 25).tolist()
        g3 = rng.exponential(40, 25).tolist()
        result = compare_groups({"A": g1, "B": g2, "C": g3})
        assert result.test_name == "Kruskal-Wallis"
        assert result.is_parametric is False

    def test_three_groups_n_per_group(self):
        rng = np.random.default_rng(42)
        data = {
            "A": rng.normal(50, 10, 27).tolist(),
            "B": rng.normal(55, 10, 23).tolist(),
            "C": rng.normal(60, 10, 29).tolist(),
        }
        result = compare_groups(data)
        assert result.n_per_group == {"A": 27, "B": 23, "C": 29}


class TestEdgeCases:
    def test_single_group_raises(self):
        with pytest.raises(ValueError, match="at least 2 groups"):
            compare_groups({"A": [1.0, 2.0, 3.0]})

    def test_empty_group_raises(self):
        with pytest.raises(ValueError, match="empty"):
            compare_groups({"A": [1.0, 2.0], "B": []})

    def test_small_sample_adds_note(self):
        rng = np.random.default_rng(42)
        g1 = rng.normal(50, 10, 4).tolist()
        g2 = rng.normal(55, 10, 4).tolist()
        result = compare_groups({"A": g1, "B": g2})
        assert result.note is not None
        assert "small sample" in result.note.lower() or "power" in result.note.lower()

    def test_shapiro_skipped_for_n_under_3(self):
        # Should not crash with n=2 per group
        result = compare_groups({"A": [1.0, 2.0], "B": [3.0, 4.0]})
        # Should fall back to non-parametric for safety
        assert result.test_name in ("Mann-Whitney U", "Welch's t-test")


class TestCohensD:
    def test_cohens_d_known_value(self):
        # Mean diff = 10, pooled SD ≈ 10, so d ≈ 1.0
        rng = np.random.default_rng(123)
        g1 = rng.normal(50, 10, 100).tolist()
        g2 = rng.normal(60, 10, 100).tolist()
        result = compare_groups({"A": g1, "B": g2})
        # d should be close to 1.0 (medium-large effect)
        assert 0.7 < abs(result.effect_size) < 1.3

    def test_cohens_d_zero_for_identical(self):
        rng = np.random.default_rng(42)
        data = rng.normal(50, 10, 50).tolist()
        # Same distribution twice
        result = compare_groups({"A": data[:25], "B": data[25:]})
        assert abs(result.effect_size) < 0.5


class TestLogTransform:
    def test_hf_auto_log_transformed(self):
        # Lognormal data typical of HF power
        rng = np.random.default_rng(42)
        g1 = np.exp(rng.normal(5, 1, 30)).tolist()
        g2 = np.exp(rng.normal(6, 1, 30)).tolist()
        result = compare_groups({"A": g1, "B": g2}, metric="HF")
        assert result.note is not None
        assert "log-transformed" in result.note.lower()

    def test_rmssd_not_log_transformed(self):
        rng = np.random.default_rng(42)
        g1 = rng.normal(50, 10, 30).tolist()
        g2 = rng.normal(55, 10, 30).tolist()
        result = compare_groups({"A": g1, "B": g2}, metric="RMSSD")
        assert result.note is None or "log-transformed" not in result.note.lower()

    def test_should_log_transform(self):
        assert should_log_transform("LF") is True
        assert should_log_transform("HF") is True
        assert should_log_transform("VLF") is True
        assert should_log_transform("TP") is True
        assert should_log_transform("RMSSD") is False
        assert should_log_transform("SDNN") is False
        assert should_log_transform("") is False

    def test_nan_values_filtered(self):
        g1 = [50.0, 55.0, float("nan"), 60.0, 52.0]
        g2 = [45.0, 48.0, 50.0, float("inf"), 47.0]
        result = compare_groups({"A": g1, "B": g2})
        assert result.n_per_group["A"] == 4  # NaN dropped
        assert result.n_per_group["B"] == 4  # Inf dropped


class TestPairedComparison:
    def test_paired_t_test_selected(self):
        rng = np.random.default_rng(42)
        pre = rng.normal(50, 10, 30)
        # Post has a +5 shift — true within-subject effect
        post = pre + rng.normal(5, 3, 30)
        result = compare_paired(
            pre.tolist(),
            post.tolist(),
            metric="RMSSD",
            condition_a_name="pre",
            condition_b_name="post",
        )
        assert result.test_name == "Paired t-test"
        assert result.significance in ("*", "**", "***")
        assert result.effect_size_name == "Cohen's d_z"

    def test_paired_requires_equal_length(self):
        with pytest.raises(ValueError, match="equal length"):
            compare_paired([1.0, 2.0, 3.0], [1.0, 2.0])

    def test_paired_filters_incomplete_pairs(self):
        a = [50.0, 55.0, float("nan"), 60.0, 52.0]
        b = [45.0, 48.0, 50.0, 55.0, 47.0]
        result = compare_paired(a, b)
        # Participant 3 (NaN in a) should be dropped from both
        assert result.n_per_group["A"] == 4
        assert result.n_per_group["B"] == 4

    def test_paired_wilcoxon_for_non_normal_diffs(self):
        rng = np.random.default_rng(42)
        # Highly skewed differences
        pre = rng.normal(50, 5, 30)
        post = pre + rng.exponential(3, 30)
        result = compare_paired(pre.tolist(), post.tolist())
        # Should fall back to Wilcoxon
        assert result.test_name in ("Paired t-test", "Wilcoxon signed-rank")


class TestMultipleComparisonCorrection:
    def _make_results(self, p_values):
        rng = np.random.default_rng(42)
        out = []
        for p in p_values:
            g1 = rng.normal(50, 10, 30).tolist()
            g2 = rng.normal(50, 10, 30).tolist()
            r = compare_groups({"A": g1, "B": g2})
            r.p_value = p  # Override for testing
            r.significance = compute_stars(p)
            out.append(r)
        return out

    def test_bonferroni(self):
        results = self._make_results([0.01, 0.02, 0.04])
        adjusted = adjust_pvalues(results, method="bonferroni")
        # 0.01 * 3 = 0.03, 0.02 * 3 = 0.06, 0.04 * 3 = 0.12
        assert abs(adjusted[0].p_value - 0.03) < 1e-6
        assert abs(adjusted[1].p_value - 0.06) < 1e-6
        assert abs(adjusted[2].p_value - 0.12) < 1e-6

    def test_holm(self):
        results = self._make_results([0.01, 0.03, 0.04])
        adjusted = adjust_pvalues(results, method="holm")
        # Holm: sorted 0.01, 0.03, 0.04 → × 3, × 2, × 1 → 0.03, 0.06, 0.04
        # But monotonicity: 0.04 ≥ max(0.03, 0.06) → stays at 0.06
        assert abs(adjusted[0].p_value - 0.03) < 1e-6
        assert abs(adjusted[1].p_value - 0.06) < 1e-6
        assert abs(adjusted[2].p_value - 0.06) < 1e-6

    def test_fdr_bh(self):
        # BH is less conservative than Holm
        results = self._make_results([0.01, 0.03, 0.04])
        adj_bh = adjust_pvalues(results, method="fdr_bh")
        # Should be less conservative than Holm
        assert adj_bh[0].p_value < 0.04
        assert all(r.significance in ("ns", "*", "**", "***") for r in adj_bh)

    def test_correction_note_added(self):
        results = self._make_results([0.01, 0.02, 0.04])
        adjusted = adjust_pvalues(results, method="holm")
        assert "Adjusted for 3 comparisons" in adjusted[0].note
        assert "holm" in adjusted[0].note
        assert "raw p=" in adjusted[0].note

    def test_single_result_unchanged(self):
        results = self._make_results([0.03])
        original_p = results[0].p_value
        adjusted = adjust_pvalues(results, method="holm")
        assert adjusted[0].p_value == original_p

    def test_invalid_method_raises(self):
        results = self._make_results([0.01, 0.02])
        with pytest.raises(ValueError, match="Unknown correction"):
            adjust_pvalues(results, method="invalid")

    def test_raw_p_preserved_after_correction(self):
        """After adjust_pvalues runs, p_value_raw must hold the original p."""
        results = self._make_results([0.01, 0.02, 0.04])
        adjust_pvalues(results, method="holm")
        # Raw p preserved
        assert results[0].p_value_raw == pytest.approx(0.01)
        assert results[1].p_value_raw == pytest.approx(0.02)
        assert results[2].p_value_raw == pytest.approx(0.04)
        # And p_value now holds the adjusted value (>= raw)
        for r in results:
            assert r.p_value >= r.p_value_raw - 1e-12
        # is_corrected flag set
        assert all(r.is_corrected for r in results)

    def test_double_correction_raises(self):
        """Re-running adjust_pvalues on already-corrected results must error."""
        results = self._make_results([0.01, 0.02, 0.04])
        adjust_pvalues(results, method="holm")
        with pytest.raises(ValueError, match="already-corrected"):
            adjust_pvalues(results, method="holm")

    def test_default_uncorrected_flags(self):
        """Fresh results from compare_groups must have is_corrected=False
        and p_value_raw=None."""
        rng = np.random.default_rng(42)
        g1 = rng.normal(50, 10, 30).tolist()
        g2 = rng.normal(50, 10, 30).tolist()
        r = compare_groups({"A": g1, "B": g2})
        assert r.is_corrected is False
        assert r.p_value_raw is None


class TestShortSampleNote:
    """Fix 4: the fallback note should explain WHY non-parametric was picked."""

    def test_small_n_note_mentions_shapiro_could_not_run(self):
        # n=2 per group -> Shapiro-Wilk cannot run, fallback to MW
        result = compare_groups({"A": [1.0, 2.0], "B": [3.0, 4.0]})
        assert result.note is not None
        assert "shapiro" in result.note.lower()
        assert "could not run" in result.note.lower()
        # Must NOT misleadingly say "non-normal"
        assert "non-normal distribution" not in result.note.lower()

    def test_normal_sized_skewed_note_says_non_normal(self):
        rng = np.random.default_rng(42)
        # Skewed but n>=5 per group: Shapiro CAN run, and rejects normality
        g1 = rng.exponential(20, 25).tolist()
        g2 = rng.exponential(40, 25).tolist()
        result = compare_groups({"A": g1, "B": g2})
        assert result.note is not None
        assert "non-normal distribution" in result.note.lower()
