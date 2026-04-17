"""Statistical tests for group comparisons of HRV metrics.

Provides hypothesis testing with automatic test selection based on normality:
- 2 groups, normal: Welch's t-test + Cohen's d
- 2 groups, non-normal: Mann-Whitney U + Cohen's d
- 3+ groups, normal: one-way ANOVA + eta-squared
- 3+ groups, non-normal: Kruskal-Wallis + eta-squared

References:
- Welch, B.L. (1947). The generalization of 'Student's' problem.
  *Biometrika*, 34(1/2), 28-35. [doi:10.1093/biomet/34.1-2.28](https://doi.org/10.1093/biomet/34.1-2.28)
- Shapiro, S.S., & Wilk, M.B. (1965). *Biometrika*, 52(3/4), 591-611.
  [doi:10.1093/biomet/52.3-4.591](https://doi.org/10.1093/biomet/52.3-4.591)
- Cohen, J. (1988). Statistical Power Analysis for the Behavioral Sciences.
  [doi:10.4324/9780203771587](https://doi.org/10.4324/9780203771587)
- Lakens, D. (2013). Calculating and reporting effect sizes to facilitate
  cumulative science. *Frontiers in Psychology*, 4, 863.
  [doi:10.3389/fpsyg.2013.00863](https://doi.org/10.3389/fpsyg.2013.00863)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy import stats


@dataclass
class GroupComparisonResult:
    """Result of comparing a metric across groups."""

    metric: str
    section: str
    groups: list[str]
    n_per_group: dict[str, int]
    means: dict[str, float]
    sds: dict[str, float]
    test_name: str
    statistic: float
    p_value: float
    effect_size: float | None
    effect_size_name: str
    normality_p: dict[str, float] = field(default_factory=dict)
    is_parametric: bool = True
    significance: str = "ns"
    note: str | None = None


def compute_stars(p_value: float) -> str:
    """Convert p-value to significance stars (APA 7th edition convention, inclusive).

    - p <= 0.001: "***"
    - p <= 0.01:  "**"
    - p <= 0.05:  "*"
    - else:       "ns"
    """
    if p_value <= 0.001:
        return "***"
    if p_value <= 0.01:
        return "**"
    if p_value <= 0.05:
        return "*"
    return "ns"


# HRV frequency-domain metrics that are typically log-normally distributed.
# Task Force (1996) and Quigley et al. (2024) recommend log-transformation
# before parametric analysis. Names match upper-case metric codes used in
# stats_df (see calculate_group_stats).
LOG_NORMAL_METRICS = frozenset(
    {"LF", "HF", "VLF", "LF_HF", "TP", "TOTAL_POWER", "LFN", "HFN"}
)


def should_log_transform(metric: str) -> bool:
    """Check if a metric is typically log-normally distributed in HRV studies."""
    return metric.upper() in LOG_NORMAL_METRICS


def _cohens_d(x: np.ndarray, y: np.ndarray) -> float:
    """Cohen's d with pooled standard deviation.

    d = (mean_x - mean_y) / pooled_sd
    where pooled_sd = sqrt(((n1-1)*sd1² + (n2-1)*sd2²) / (n1+n2-2))
    """
    n1, n2 = len(x), len(y)
    if n1 < 2 or n2 < 2:
        return 0.0
    s1_sq = x.var(ddof=1)
    s2_sq = y.var(ddof=1)
    pooled_sd = math.sqrt(((n1 - 1) * s1_sq + (n2 - 1) * s2_sq) / (n1 + n2 - 2))
    if pooled_sd == 0:
        return 0.0
    return (x.mean() - y.mean()) / pooled_sd


def _eta_squared_oneway(groups_data: list[np.ndarray]) -> float:
    """Eta-squared (η²) effect size for one-way ANOVA.

    η² = SS_between / SS_total

    Interpretation (Cohen 1988):
    - 0.01: small effect
    - 0.06: medium effect
    - 0.14: large effect
    """
    all_values = np.concatenate(groups_data)
    grand_mean = all_values.mean()
    ss_total = ((all_values - grand_mean) ** 2).sum()
    if ss_total == 0:
        return 0.0
    ss_between = sum(len(g) * (g.mean() - grand_mean) ** 2 for g in groups_data)
    return ss_between / ss_total


def _is_normal(values: np.ndarray, alpha: float = 0.05) -> tuple[bool, float]:
    """Shapiro-Wilk normality test. Returns (is_normal, p_value).

    Skipped (returns (True, 1.0)) for n < 3 since Shapiro-Wilk requires n >= 3.
    """
    if len(values) < 3:
        return True, 1.0
    try:
        _, p = stats.shapiro(values)
        return p >= alpha, float(p)
    except Exception:
        return True, 1.0


def compare_groups(
    values_per_group: dict[str, list[float]],
    metric: str = "",
    section: str = "",
    alpha: float = 0.05,
    log_transform: bool | None = None,
) -> GroupComparisonResult:
    """Compare a metric across 2+ groups with auto-selected tests.

    Args:
        values_per_group: {"group_name": [v1, v2, ...], ...}
        metric: Optional metric label (e.g., "RMSSD")
        section: Optional section label (e.g., "rest_pre")
        alpha: Significance level for normality test (default 0.05)
        log_transform: If True, apply log before testing. If None (auto),
            applies log for frequency-domain metrics (LF, HF, VLF, etc.)
            which are typically log-normal (Task Force 1996, Quigley 2024).

    Returns:
        GroupComparisonResult with test results and effect size

    Raises:
        ValueError: If fewer than 2 groups or any group is empty (after NaN filter)

    Test selection:
        - 2 groups, both normal: Welch's t-test + Cohen's d
        - 2 groups, any non-normal OR n<3: Mann-Whitney U + Cohen's d
        - 3+ groups, all normal: one-way ANOVA + η²
        - 3+ groups, any non-normal: Kruskal-Wallis + η²
    """
    if len(values_per_group) < 2:
        raise ValueError("Need at least 2 groups for comparison")

    # Auto-detect log-transform for known log-normal metrics
    if log_transform is None:
        log_transform = should_log_transform(metric)

    group_names = list(values_per_group.keys())

    # Filter NaN/Inf and apply log-transform if requested
    arrays: dict[str, np.ndarray] = {}
    for name, vals in values_per_group.items():
        if not vals:
            raise ValueError(f"Group '{name}' is empty")
        arr = np.asarray(vals, dtype=float)
        arr = arr[np.isfinite(arr)]
        if log_transform:
            # Only log positive values; drop zeros/negatives
            arr = arr[arr > 0]
            arr = np.log(arr)
        if len(arr) == 0:
            raise ValueError(
                f"Group '{name}' has no valid values after filtering NaN/Inf"
                + (
                    " and non-positive values for log-transform"
                    if log_transform
                    else ""
                )
            )
        arrays[name] = arr

    n_per_group = {name: len(arr) for name, arr in arrays.items()}
    means = {name: float(arr.mean()) for name, arr in arrays.items()}
    sds = {
        name: float(arr.std(ddof=1)) if len(arr) > 1 else 0.0
        for name, arr in arrays.items()
    }

    # Normality check per group
    normality_p = {}
    any_non_normal = False
    any_too_small = False
    for name, arr in arrays.items():
        is_norm, p = _is_normal(arr, alpha=alpha)
        normality_p[name] = p
        if not is_norm:
            any_non_normal = True
        if len(arr) < 3:
            any_too_small = True

    # Force non-parametric if sample too small to verify normality
    is_parametric = not any_non_normal and not any_too_small

    group_arrays = list(arrays.values())

    if len(group_names) == 2:
        g1, g2 = group_arrays[0], group_arrays[1]
        if is_parametric:
            stat, p_val = stats.ttest_ind(g1, g2, equal_var=False)
            test_name = "Welch's t-test"
        else:
            stat, p_val = stats.mannwhitneyu(g1, g2, alternative="two-sided")
            test_name = "Mann-Whitney U"
        effect = _cohens_d(g1, g2)
        effect_name = "Cohen's d"
    else:
        if is_parametric:
            stat, p_val = stats.f_oneway(*group_arrays)
            test_name = "One-way ANOVA"
        else:
            stat, p_val = stats.kruskal(*group_arrays)
            test_name = "Kruskal-Wallis"
        effect = _eta_squared_oneway(group_arrays)
        effect_name = "η²"

    # Build note combining all relevant warnings
    notes = []
    min_n = min(n_per_group.values())
    if min_n < 5:
        notes.append(f"Small sample (min n={min_n}): statistical power limited")
    if not is_parametric and not any_too_small:
        notes.append("Non-parametric test used due to non-normal distribution")
    if log_transform:
        notes.append(
            f"Values log-transformed before testing ({metric} is typically log-normal)"
        )
    note = "; ".join(notes) if notes else None

    return GroupComparisonResult(
        metric=metric,
        section=section,
        groups=group_names,
        n_per_group=n_per_group,
        means=means,
        sds=sds,
        test_name=test_name,
        statistic=float(stat),
        p_value=float(p_val),
        effect_size=float(effect),
        effect_size_name=effect_name,
        normality_p=normality_p,
        is_parametric=is_parametric,
        significance=compute_stars(float(p_val)),
        note=note,
    )


def compare_paired(
    condition_a: list[float],
    condition_b: list[float],
    metric: str = "",
    condition_a_name: str = "A",
    condition_b_name: str = "B",
    alpha: float = 0.05,
    log_transform: bool | None = None,
) -> GroupComparisonResult:
    """Compare paired (within-subject) measurements.

    Use this for pre/post, or music/rest comparisons on the SAME participants.
    The two arrays must have identical length and be aligned by participant.

    Test selection:
        - Paired t-test if differences are normal
        - Wilcoxon signed-rank if not

    Effect size: Cohen's d_z = mean(diff) / SD(diff)
    """
    if len(condition_a) != len(condition_b):
        raise ValueError(
            f"Paired comparison requires equal length arrays "
            f"(got {len(condition_a)} vs {len(condition_b)})"
        )
    if not condition_a:
        raise ValueError("Empty input arrays")

    if log_transform is None:
        log_transform = should_log_transform(metric)

    a = np.asarray(condition_a, dtype=float)
    b = np.asarray(condition_b, dtype=float)

    # Keep only pairs where both values are finite
    mask = np.isfinite(a) & np.isfinite(b)
    if log_transform:
        mask = mask & (a > 0) & (b > 0)
    a, b = a[mask], b[mask]

    if len(a) < 2:
        raise ValueError("Need at least 2 valid pairs after filtering")

    if log_transform:
        a = np.log(a)
        b = np.log(b)

    diff = a - b
    is_norm, norm_p = _is_normal(diff, alpha=alpha)
    too_small = len(diff) < 3
    is_parametric = is_norm and not too_small

    if is_parametric:
        stat, p_val = stats.ttest_rel(a, b)
        test_name = "Paired t-test"
    else:
        stat, p_val = stats.wilcoxon(a, b)
        test_name = "Wilcoxon signed-rank"

    # Cohen's d_z: mean difference / SD of difference
    d_sd = float(diff.std(ddof=1))
    effect = float(diff.mean() / d_sd) if d_sd > 0 else 0.0

    notes = []
    if len(diff) < 5:
        notes.append(f"Small sample (n={len(diff)}): statistical power limited")
    if not is_parametric and not too_small:
        notes.append(
            "Non-parametric test used due to non-normal distribution of differences"
        )
    if log_transform:
        notes.append(
            f"Values log-transformed before testing ({metric} is typically log-normal)"
        )

    return GroupComparisonResult(
        metric=metric,
        section="",
        groups=[condition_a_name, condition_b_name],
        n_per_group={condition_a_name: len(a), condition_b_name: len(b)},
        means={condition_a_name: float(a.mean()), condition_b_name: float(b.mean())},
        sds={
            condition_a_name: float(a.std(ddof=1)),
            condition_b_name: float(b.std(ddof=1)),
        },
        test_name=test_name,
        statistic=float(stat),
        p_value=float(p_val),
        effect_size=effect,
        effect_size_name="Cohen's d_z",
        normality_p={"difference": norm_p},
        is_parametric=is_parametric,
        significance=compute_stars(float(p_val)),
        note="; ".join(notes) if notes else None,
    )


def adjust_pvalues(
    results: list[GroupComparisonResult],
    method: str = "holm",
) -> list[GroupComparisonResult]:
    """Apply multiple-comparison correction across a batch of results.

    When running many tests (e.g., 5 metrics × 3 sections = 15 tests),
    family-wise error rate inflates dramatically. This function adjusts
    p-values in place and updates significance stars.

    Args:
        results: List of GroupComparisonResult from compare_groups/compare_paired
        method: "holm" (Holm-Bonferroni, default), "bonferroni", or "fdr_bh"
            (Benjamini-Hochberg false discovery rate)

    Returns:
        Same list with updated p_values (stored as note) and significance.
        Original raw p-value preserved in the statistic field note.

    References:
        - Holm, S. (1979). A simple sequentially rejective multiple test
          procedure. Scandinavian Journal of Statistics, 6, 65-70.
        - Benjamini, Y., & Hochberg, Y. (1995). Controlling the false
          discovery rate. Journal of the Royal Statistical Society B, 57(1),
          289-300. [doi:10.1111/j.2517-6161.1995.tb02031.x](https://doi.org/10.1111/j.2517-6161.1995.tb02031.x)
    """
    if not results:
        return results
    n = len(results)
    if n == 1:
        return results

    raw_p = np.array([r.p_value for r in results])

    if method == "bonferroni":
        adj_p = np.minimum(raw_p * n, 1.0)
    elif method == "holm":
        # Holm-Bonferroni: sort ascending, multiply by (n - rank)
        order = np.argsort(raw_p)
        adj = np.empty_like(raw_p)
        running_max = 0.0
        for i, idx in enumerate(order):
            val = raw_p[idx] * (n - i)
            running_max = max(running_max, val)
            adj[idx] = min(running_max, 1.0)
        adj_p = adj
    elif method == "fdr_bh":
        # Benjamini-Hochberg
        order = np.argsort(raw_p)
        adj = np.empty_like(raw_p)
        running_min = 1.0
        for i in range(n - 1, -1, -1):
            idx = order[i]
            val = raw_p[idx] * n / (i + 1)
            running_min = min(running_min, val)
            adj[idx] = min(running_min, 1.0)
        adj_p = adj
    else:
        raise ValueError(
            f"Unknown correction method: {method}. Use 'holm', 'bonferroni', or 'fdr_bh'."
        )

    for result, new_p in zip(results, adj_p):
        raw = result.p_value
        result.p_value = float(new_p)
        result.significance = compute_stars(float(new_p))
        correction_note = f"Adjusted for {n} comparisons ({method}); raw p={raw:.4g}"
        result.note = (
            f"{result.note}; {correction_note}" if result.note else correction_note
        )

    return results
