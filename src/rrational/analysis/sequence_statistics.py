"""Repeated-measures statistics for ordered sequences of sections.

A "sequence" here is an ordered chain of named sections (e.g.
``["rest_pre", "music_block_1", "pause", "music_block_2", "rest_post"]``)
that every participant in a study went through in the SAME order.
We ask: does the HRV metric (RMSSD, LF/HF, …) change across the chain?

This is the classic repeated-measures problem: each participant
contributes one value per section, and we compare the within-subject
trajectories rather than treating sections as independent groups.

Test selection (auto):

- Default: **Friedman test** (non-parametric, no distributional
  assumption, robust for small n). Effect size: **Kendall's W**.
- If every section's values are normally distributed (Shapiro-Wilk
  p > 0.05) AND we have at least 10 complete-case subjects, the
  caller may opt into **one-way repeated-measures ANOVA**. Effect
  size: **partial eta-squared**.

Both tests are followed by **all-pairwise post-hoc** comparisons
(Wilcoxon signed-rank for Friedman, paired t-test for RM-ANOVA),
**Holm-Bonferroni corrected**.

Only **complete cases** are analysed — a subject who is missing one
section's value is dropped from the omnibus test (RM designs require
balanced data). The result reports how many cases were excluded.

References:

- Friedman, M. (1937). The use of ranks to avoid the assumption of
  normality implicit in the analysis of variance.
  *Journal of the American Statistical Association*, 32(200), 675-701.
  [doi:10.1080/01621459.1937.10503522](https://doi.org/10.1080/01621459.1937.10503522)
- Kendall, M.G., & Babington Smith, B. (1939). The problem of m rankings.
  *The Annals of Mathematical Statistics*, 10(3), 275-287.
  [doi:10.1214/aoms/1177732186](https://doi.org/10.1214/aoms/1177732186)
- Wilcoxon, F. (1945). Individual comparisons by ranking methods.
  *Biometrics Bulletin*, 1(6), 80-83.
  [doi:10.2307/3001968](https://doi.org/10.2307/3001968)
- Holm, S. (1979). A simple sequentially rejective multiple test procedure.
  *Scandinavian Journal of Statistics*, 6(2), 65-70.
  [JSTOR:4615733](https://www.jstor.org/stable/4615733)
- Lakens, D. (2013). Calculating and reporting effect sizes to facilitate
  cumulative science. *Frontiers in Psychology*, 4, 863.
  [doi:10.3389/fpsyg.2013.00863](https://doi.org/10.3389/fpsyg.2013.00863)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from itertools import combinations

import numpy as np
from scipy import stats

# Reuse the canonical log-normal HRV metric set defined for group analysis,
# so both pipelines agree on which metrics get log-transformed before
# parametric testing (Task Force 1996 / Quigley 2024).
from rrational.analysis.group_statistics import (
    LOG_NORMAL_METRICS,  # re-exported for callers
    should_log_transform,
)

__all__ = [
    "LOG_NORMAL_METRICS",
    "MIN_SUBJECTS",
    "RM_ANOVA_MIN_SUBJECTS",
    "PostHocPair",
    "SequenceComparisonResult",
    "analyze_sequence",
    "compute_stars",
    "should_log_transform",
]

# Minimum complete cases below which the omnibus test refuses to run.
# Friedman with n=2 subjects collapses; n=3 is the smallest practical case.
MIN_SUBJECTS = 3

# Minimum subjects to even consider RM-ANOVA. Below this we always pick
# Friedman regardless of normality.
RM_ANOVA_MIN_SUBJECTS = 10


@dataclass
class PostHocPair:
    """A single pairwise comparison from the post-hoc battery."""

    section_a: str
    section_b: str
    test_name: str  # "Wilcoxon signed-rank" or "Paired t-test"
    statistic: float
    p_value_raw: float
    p_value_corrected: float
    n_pairs: int


@dataclass
class SequenceComparisonResult:
    """Result of running a repeated-measures test over a section sequence."""

    sequence_name: str
    metric: str
    sections: list[str]  # ordered
    n_complete_subjects: int
    n_excluded_subjects: int

    # Per-section descriptives (only over the complete-case subjects)
    means: dict[str, float]
    sds: dict[str, float]
    normality_p: dict[str, float]

    # Omnibus
    test_name: str  # "Friedman" or "RM-ANOVA"
    statistic: float
    p_value: float
    df: tuple[float, float] | float  # (df1, df2) for ANOVA, just int for Friedman
    effect_size: float
    effect_size_name: str  # "Kendall's W" or "partial eta-squared"
    is_parametric: bool

    # Post-hoc pairwise comparisons (Holm-corrected)
    post_hoc: list[PostHocPair] = field(default_factory=list)

    # Free-text caveat (e.g. "n=5, statistical power limited").
    note: str | None = None

    @property
    def significance(self) -> str:
        return compute_stars(self.p_value)


def compute_stars(p_value: float) -> str:
    """APA-style significance stars (inclusive thresholds)."""
    if p_value <= 0.001:
        return "***"
    if p_value <= 0.01:
        return "**"
    if p_value <= 0.05:
        return "*"
    return "ns"


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _holm_correct(p_values: list[float]) -> list[float]:
    """Holm-Bonferroni step-down correction.

    Returns a new list of adjusted p-values in the same order as input.
    Adjusted p is clamped to [0, 1].
    """
    n = len(p_values)
    if n == 0:
        return []
    # Sort indices by raw p ascending
    order = sorted(range(n), key=lambda i: p_values[i])
    adjusted = [0.0] * n
    running_max = 0.0
    for rank, idx in enumerate(order):
        # Holm: multiply by (n - rank)
        adj = p_values[idx] * (n - rank)
        adj = min(adj, 1.0)
        # Enforce monotonicity: adjusted p never decreases as raw p increases
        running_max = max(running_max, adj)
        adjusted[idx] = running_max
    return adjusted


def _shapiro_safe(values: list[float]) -> float:
    """Run Shapiro-Wilk; return p-value, or NaN if the test can't run.

    Shapiro requires n >= 3 and that all values aren't identical.
    """
    if len(values) < 3:
        return float("nan")
    if len(set(values)) <= 1:
        return float("nan")
    try:
        return float(stats.shapiro(values).pvalue)
    except Exception:
        return float("nan")


def _build_complete_matrix(
    values_per_section: dict[str, list[float]],
    sections: list[str],
) -> tuple[np.ndarray, int]:
    """Build an (n_subjects, n_sections) matrix of complete-case values.

    ``values_per_section`` is indexed by section name; each list holds
    one value per subject, in subject order (subject i = position i in
    every list). Subjects with NaN or missing values for any section in
    the requested order are dropped.

    Returns (matrix, n_excluded).
    """
    # Find the maximum subject index across sections (lists may differ
    # in length if some sections were skipped for some subjects).
    n_subjects = max((len(values_per_section.get(s, [])) for s in sections), default=0)
    if n_subjects == 0:
        return np.zeros((0, len(sections))), 0

    rows = []
    excluded = 0
    for i in range(n_subjects):
        row = []
        complete = True
        for s in sections:
            vals = values_per_section.get(s, [])
            if i >= len(vals):
                complete = False
                break
            v = vals[i]
            if v is None or (isinstance(v, float) and math.isnan(v)):
                complete = False
                break
            row.append(float(v))
        if complete:
            rows.append(row)
        else:
            excluded += 1
    if not rows:
        return np.zeros((0, len(sections))), excluded
    return np.asarray(rows, dtype=float), excluded


# ---------------------------------------------------------------------
# Omnibus tests
# ---------------------------------------------------------------------
def _friedman(matrix: np.ndarray) -> tuple[float, float, float]:
    """Friedman chi-square + Kendall's W effect size.

    Returns (chi2, p_value, kendalls_w).
    """
    n_subjects, k = matrix.shape
    # Pass columns as separate args
    chi2, p = stats.friedmanchisquare(*[matrix[:, j] for j in range(k)])
    # Kendall's W = chi² / (n * (k - 1))
    w = float(chi2) / (n_subjects * (k - 1)) if (k > 1 and n_subjects > 0) else 0.0
    return float(chi2), float(p), float(w)


def _greenhouse_geisser_epsilon(matrix: np.ndarray) -> float:
    """Greenhouse-Geisser epsilon for RM-ANOVA sphericity correction.

    Sphericity = equal variances of all pairwise differences between
    repeated-measures levels. When violated, the F-statistic's null
    distribution has fewer effective degrees of freedom and the uncorrected
    p-value is anti-conservative.

    GG epsilon is computed from the covariance matrix S of the k repeated
    measures (Box 1954; Greenhouse & Geisser 1959):

        S* = S - row_means - col_means + grand_mean    (double-centered)
        eps = (trace(S*))^2 / ((k - 1) * sum(S*_ij^2))

    eps in (1/(k-1), 1]. eps = 1 means perfect sphericity (no correction).
    Returns 1.0 when the matrix is too small or degenerate to estimate.
    """
    n, k = matrix.shape
    if n < 2 or k < 3:
        # Sphericity is trivially satisfied for k=2 (only one pairwise diff).
        return 1.0
    # Sample covariance of the k columns across subjects (ddof=1, k x k).
    s = np.cov(matrix, rowvar=False, ddof=1)
    if s.shape != (k, k):
        return 1.0
    # Double-centering: subtract row means, column means, add grand mean.
    row_means = s.mean(axis=1, keepdims=True)
    col_means = s.mean(axis=0, keepdims=True)
    grand = float(s.mean())
    s_centered = s - row_means - col_means + grand
    trace = float(np.trace(s_centered))
    sum_sq = float((s_centered**2).sum())
    if sum_sq <= 0:
        return 1.0
    eps = (trace**2) / ((k - 1) * sum_sq)
    # Clamp into the theoretical range [1/(k-1), 1].
    return float(max(1.0 / (k - 1), min(1.0, eps)))


def _rm_anova(
    matrix: np.ndarray,
) -> tuple[float, float, tuple[float, float], float, float]:
    """One-way repeated-measures ANOVA with Greenhouse-Geisser correction.

    Standard partition of variance:

      SS_total      = sum_{ij} (y_ij - grand_mean)^2
      SS_subjects   = k * sum_i (subject_mean_i - grand_mean)^2
      SS_treatments = n * sum_j (treatment_mean_j - grand_mean)^2
      SS_error      = SS_total - SS_subjects - SS_treatments

      df_treatments = k - 1
      df_error      = (n - 1) * (k - 1)

    Sphericity assumption
    ---------------------
    Classical RM-ANOVA assumes sphericity (equal variance of all pairwise
    level-differences). When violated, F is anti-conservative. We compute
    the Greenhouse-Geisser epsilon and apply it to df_treat and df_error
    BEFORE evaluating p (Greenhouse & Geisser 1959). For k=2 levels
    sphericity is satisfied by construction (eps=1).

    Effect size (partial eta-squared) is unaffected by GG correction;
    only the inferential df / p change.

    References
    ----------
    - Box, G.E.P. (1954). Some theorems on quadratic forms applied in the
      study of analysis of variance problems, II. *Annals of Mathematical
      Statistics*, 25(3), 484-498. doi:10.1214/aoms/1177728717
    - Greenhouse, S.W., & Geisser, S. (1959). On methods in the analysis
      of profile data. *Psychometrika*, 24(2), 95-112. doi:10.1007/BF02289823

    Returns
    -------
    (F, p_value, (df_treatments, df_error), partial_eta_squared, gg_epsilon)
        The df reported are the GG-corrected (fractional) values used to
        compute p. gg_epsilon == 1.0 when no correction was applied.
    """
    n, k = matrix.shape
    grand_mean = matrix.mean()
    subject_means = matrix.mean(axis=1)  # (n,)
    treatment_means = matrix.mean(axis=0)  # (k,)

    ss_total = float(((matrix - grand_mean) ** 2).sum())
    ss_subjects = float(k * ((subject_means - grand_mean) ** 2).sum())
    ss_treatments = float(n * ((treatment_means - grand_mean) ** 2).sum())
    ss_error = ss_total - ss_subjects - ss_treatments
    if ss_error <= 0:
        # Degenerate (no within-subject variance after removing subject + treatment)
        return 0.0, 1.0, (k - 1, (n - 1) * (k - 1)), 0.0, 1.0

    df_treat = k - 1
    df_error = (n - 1) * (k - 1)
    ms_treat = ss_treatments / df_treat
    ms_error = ss_error / df_error
    f_stat = ms_treat / ms_error

    eps = _greenhouse_geisser_epsilon(matrix)
    df_treat_corr = df_treat * eps
    df_error_corr = df_error * eps
    p_val = float(stats.f.sf(f_stat, df_treat_corr, df_error_corr))
    eta_p_sq = ss_treatments / (ss_treatments + ss_error)
    return (
        float(f_stat),
        p_val,
        (float(df_treat_corr), float(df_error_corr)),
        float(eta_p_sq),
        float(eps),
    )


# ---------------------------------------------------------------------
# Post-hoc
# ---------------------------------------------------------------------
def _post_hoc(
    matrix: np.ndarray,
    sections: list[str],
    is_parametric: bool,
) -> list[PostHocPair]:
    """All-pairwise post-hoc with Holm correction."""
    pairs = list(combinations(range(len(sections)), 2))
    raw_results = []
    for i, j in pairs:
        a = matrix[:, i]
        b = matrix[:, j]
        if is_parametric:
            try:
                stat, p = stats.ttest_rel(a, b)
            except Exception:
                stat, p = float("nan"), 1.0
            test_name = "Paired t-test"
        else:
            try:
                stat, p = stats.wilcoxon(a, b)
            except Exception:
                stat, p = float("nan"), 1.0
            test_name = "Wilcoxon signed-rank"
        raw_results.append((i, j, test_name, float(stat), float(p), len(a)))

    raw_ps = [r[4] for r in raw_results]
    adj_ps = _holm_correct(raw_ps)

    out = []
    for (i, j, name, stat, p_raw, n_pairs), p_adj in zip(raw_results, adj_ps):
        out.append(
            PostHocPair(
                section_a=sections[i],
                section_b=sections[j],
                test_name=name,
                statistic=stat,
                p_value_raw=p_raw,
                p_value_corrected=p_adj,
                n_pairs=n_pairs,
            )
        )
    return out


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------
def analyze_sequence(
    values_per_section: dict[str, list[float]],
    sequence_name: str,
    metric: str,
    sections: list[str],
    prefer_parametric: bool = False,
) -> SequenceComparisonResult:
    """Run a repeated-measures comparison across an ordered section sequence.

    Parameters
    ----------
    values_per_section
        One list of per-subject values per section. The i-th element of
        every list is subject ``i`` (so the lists must be aligned).
    sequence_name, metric
        Free-text labels carried through to the result.
    sections
        The ordered list of section names that defines the sequence.
        Must have at least 2 entries.
    prefer_parametric
        If True AND every section's normality p > 0.05 AND
        n_complete >= :data:`RM_ANOVA_MIN_SUBJECTS`, run RM-ANOVA.
        Otherwise default to Friedman. Default False (always Friedman).
    """
    if len(sections) < 2:
        raise ValueError("Need at least 2 sections to compare a sequence.")

    matrix, excluded = _build_complete_matrix(values_per_section, sections)
    n_complete = matrix.shape[0]

    # Per-section descriptives + normality (computed from the complete
    # cases so they match what the omnibus test actually sees).
    means: dict[str, float] = {}
    sds: dict[str, float] = {}
    normality_p: dict[str, float] = {}
    if n_complete > 0:
        for j, s in enumerate(sections):
            col = matrix[:, j]
            means[s] = float(col.mean())
            sds[s] = float(col.std(ddof=1)) if n_complete >= 2 else 0.0
            normality_p[s] = _shapiro_safe(col.tolist())
    else:
        for s in sections:
            means[s] = float("nan")
            sds[s] = float("nan")
            normality_p[s] = float("nan")

    if n_complete < MIN_SUBJECTS:
        return SequenceComparisonResult(
            sequence_name=sequence_name,
            metric=metric,
            sections=list(sections),
            n_complete_subjects=n_complete,
            n_excluded_subjects=excluded,
            means=means,
            sds=sds,
            normality_p=normality_p,
            test_name="(insufficient data)",
            statistic=float("nan"),
            p_value=float("nan"),
            df=0,
            effect_size=float("nan"),
            effect_size_name="—",
            is_parametric=False,
            post_hoc=[],
            note=(
                f"Need >= {MIN_SUBJECTS} complete-case subjects to run any "
                f"repeated-measures test. Got {n_complete}."
            ),
        )

    # Choose the test
    all_normal = all(not math.isnan(p) and p > 0.05 for p in normality_p.values())
    use_rm_anova = (
        prefer_parametric and all_normal and n_complete >= RM_ANOVA_MIN_SUBJECTS
    )

    # Per Task Force (1996), frequency-domain HRV metrics (LF/HF/VLF/TP/LF_HF)
    # are log-normally distributed; parametric tests on the raw scale lose
    # power and bias effect sizes. When the parametric path will run, work on
    # the log-transformed matrix throughout (omnibus + post-hoc paired t).
    # We do NOT log-transform for Friedman: it's rank-based and the
    # transformation is monotonic, so ranks (and hence the chi-square) are
    # unchanged. For the post-hoc Wilcoxon (also rank-based) the result is
    # likewise invariant to a monotonic transform.
    log_transformed = False
    omnibus_matrix = matrix
    if use_rm_anova and should_log_transform(metric):
        # Only positive values can be log-transformed. If any non-positive
        # values slipped through (zeros from clipped frequency powers, etc.)
        # we silently skip the transform rather than mutate the analysis.
        if np.all(matrix > 0):
            omnibus_matrix = np.log(matrix)
            log_transformed = True

    gg_epsilon = 1.0
    if use_rm_anova:
        f_stat, p_val, dfs, eta_p_sq, gg_epsilon = _rm_anova(omnibus_matrix)
        test_name = "RM-ANOVA"
        statistic = f_stat
        effect_size = eta_p_sq
        effect_size_name = "partial eta-squared"
        is_parametric = True
        df_out: tuple[float, float] | float = dfs
    else:
        chi2, p_val, w = _friedman(matrix)
        test_name = "Friedman"
        statistic = chi2
        effect_size = w
        effect_size_name = "Kendall's W"
        is_parametric = False
        df_out = float(len(sections) - 1)

    # Post-hoc operates on the same scale as the omnibus, so paired t-tests
    # on log-normal metrics also use the log-transformed matrix.
    post_hoc_matrix = omnibus_matrix if (use_rm_anova and log_transformed) else matrix
    post_hoc = _post_hoc(post_hoc_matrix, sections, is_parametric)

    note_bits: list[str] = []
    if n_complete < RM_ANOVA_MIN_SUBJECTS:
        note_bits.append(
            f"n={n_complete} complete subjects — statistical power limited. "
            f"Friedman used (RM-ANOVA requires n >= {RM_ANOVA_MIN_SUBJECTS})."
        )
    elif prefer_parametric and not all_normal:
        note_bits.append(
            "Friedman used: at least one section failed the Shapiro-Wilk "
            "normality test (p <= 0.05)."
        )
    if log_transformed:
        note_bits.append(
            f"Values log-transformed before RM-ANOVA and paired t-tests "
            f"({metric} is typically log-normal, Task Force 1996)."
        )
    if use_rm_anova:
        if gg_epsilon < 1.0 - 1e-9:
            note_bits.append(
                f"RM-ANOVA: Greenhouse-Geisser sphericity correction applied "
                f"(epsilon={gg_epsilon:.3f})."
            )
        else:
            note_bits.append(
                "RM-ANOVA: sphericity assumed (Greenhouse-Geisser epsilon=1.000)."
            )
    note = " ".join(note_bits) if note_bits else None

    return SequenceComparisonResult(
        sequence_name=sequence_name,
        metric=metric,
        sections=list(sections),
        n_complete_subjects=n_complete,
        n_excluded_subjects=excluded,
        means=means,
        sds=sds,
        normality_p=normality_p,
        test_name=test_name,
        statistic=statistic,
        p_value=p_val,
        df=df_out,
        effect_size=effect_size,
        effect_size_name=effect_size_name,
        is_parametric=is_parametric,
        post_hoc=post_hoc,
        note=note,
    )
