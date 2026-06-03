# HRV Analysis Guidelines

Practical guidelines for using RRational in line with current scientific standards.

## Which guidelines does RRational follow?

RRational implements recommendations from:

- **Quigley et al. (2024)** — Current consensus on HRV measurement and reporting in psychophysiology
- **Task Force (1996)** — Foundational standards for HRV measurement
- **Quintana et al. (2016)** — GRAPH checklist for reporting HRV studies
- **Lipponen & Tarvainen (2019)** — State-of-the-art artifact detection algorithm

## Data Quality

### Artifact Detection

RRational uses the **Lipponen-Tarvainen algorithm** (via NeuroKit2's Kubios implementation) which classifies beats into six categories: ectopic, long, short, missed, extra, and normal.

``` mermaid
flowchart TD
  A[Run artifact detection] --> B{Artifact rate?}
  B -->|≤ 2%| C[Excellent\nUse as-is]
  B -->|2-5%| D[Good\nCorrect + analyze]
  B -->|5-10%| E[Moderate\nCorrect, time-domain only]
  B -->|> 10%| F[Poor\nExclude segment]

  style C fill:#28a745,color:#fff
  style D fill:#2E86AB,color:#fff
  style E fill:#ffc107,color:#000
  style F fill:#dc3545,color:#fff
```

!!! tip "Recommended Workflow"
    1. Run artifact detection on **all validated sections** (same segments)
    2. Review per-segment quality grades
    3. Exclude segments with > 10% artifacts
    4. Correct segments with 2–10% artifacts
    5. Report artifact rates in your publication

### Quality Grades

RRational assigns quality grades following Quigley et al. (2024):

| Grade | Artifact Rate | Valid Metrics | Action |
|-------|---------------|---------------|--------|
| **Excellent** | ≤ 2% | All (time, frequency, nonlinear) | Use as-is |
| **Good** | 2–5% | All | Correct artifacts, then analyze |
| **Moderate** | 5–10% | Time-domain only | Correct, but avoid frequency metrics |
| **Poor** | > 10% | None reliably | **Exclude from analysis** |

Segments with fewer than 50 beats are excluded automatically regardless of artifact rate (too short for any reliable HRV metric).

### Minimum Data Requirements

| Analysis | Minimum | Recommended | Why |
|----------|---------|-------------|-----|
| Time-domain (RMSSD, SDNN) | 100 beats | 300+ beats | Statistical reliability |
| Frequency-domain (LF, HF) | 300 beats | 500+ beats | Spectral estimation needs sufficient data |
| Recording duration for frequency | 2 minutes | 5 minutes | 5 min is the Task Force (1996) short-term window; the 2 min minimum is RRational's practical floor |

## Metric Interpretation

### Recommended Metrics

| Metric | What it reflects | Recommendation |
|--------|-----------------|----------------|
| **RMSSD** | Parasympathetic (vagal) activity | Primary metric for short-term studies |
| **SDNN** | Total autonomic variability | Use with consistent segment durations |
| **HF Power** | Parasympathetic activity (0.15–0.4 Hz) | Corroborates RMSSD |
| **SD1** | Short-term variability (Poincare) | Mathematically related to RMSSD |

### Metrics to Use with Caution

!!! warning "LF/HF Ratio"
    The LF/HF ratio should **not** be interpreted as "sympathovagal balance." This interpretation is rejected by current consensus (Quigley et al., 2024; Billman, 2013). The LF band reflects both sympathetic and parasympathetic activity plus baroreflex function. RRational includes LF/HF for legacy compatibility, but we recommend against using it as your primary outcome.

!!! warning "SDNN Across Different Durations"
    SDNN scales with recording duration. **Never compare SDNN values from segments of different lengths.** Use consistent window sizes (e.g., always 5 minutes) within a study.

## Statistical Testing (Group & Sequence Comparison)

When you compare groups or conditions, RRational selects an appropriate test automatically and reports an effect size alongside each p-value.

**Test selection** is driven by the number of groups and a normality check (Shapiro-Wilk) on each metric:

| Comparison | Distribution | Test | Effect size |
|------------|--------------|------|-------------|
| 2 groups | normal | Welch's t-test (unequal variances) | Cohen's d |
| 2 groups | non-normal | Mann-Whitney U | — |
| 3+ groups | normal | one-way ANOVA | η² (eta-squared) |
| 3+ groups | non-normal | Kruskal-Wallis | η² |

**Why effect sizes?** A p-value indicates whether a difference is unlikely under the null hypothesis; it does not say how *large* the difference is. Always report an effect size (Cohen's d or η²) so readers can judge practical significance — current reporting guidelines (Quigley et al., 2024) require this.

**Multiple comparisons.** Testing many metrics at once inflates the false-positive rate. RRational adjusts p-values across the metrics in a comparison using **Holm** (default), **Bonferroni**, or **Benjamini-Hochberg FDR**. State which correction you used.

**Log-normal metrics.** Frequency-domain powers (LF, HF, VLF, Total Power) are right-skewed and approximately log-normal. RRational log-transforms them before parametric testing so the normality assumption holds, in line with common HRV practice.

!!! warning "Normality on small samples"
    The Shapiro-Wilk test has low power with very small groups, so a "normal" verdict on a handful of participants is weak evidence. With small or clearly skewed samples, prefer the non-parametric option and interpret parametric results cautiously.

## Reporting Checklist

Following the GRAPH guidelines (Quintana et al., 2016), your publication should report:

- [ ] Recording device and sampling rate
- [ ] Recording duration per condition
- [ ] Artifact detection method and parameters
- [ ] Mean artifact rate per condition (with SD)
- [ ] Artifact correction algorithm
- [ ] Number of excluded segments and criteria
- [ ] HRV metrics computed, with window duration
- [ ] Beat count per analyzed segment
- [ ] Software and version used

!!! tip "RRational makes this easy"
    The **Analysis Documentation** panel (in Single Participant analysis) auto-generates a report with all these details. Export as HTML or Markdown and include in your supplementary materials.

## Common Pitfalls

| Pitfall | Why it's a problem | What to do instead |
|---------|--------------------|--------------------|
| Comparing SDNN across different durations | SDNN scales with recording length | Use identical segment lengths |
| Interpreting LF as "sympathetic" | Not supported by evidence | Report LF but don't over-interpret |
| Using LF/HF as sympathovagal balance | Rejected by current consensus | Focus on RMSSD and HF |
| Over-correcting artifacts (> 10%) | Distorts the signal | Exclude the segment instead |
| Frequency metrics on < 2 min segments | Insufficient spectral resolution | Use time-domain only |
| Ignoring respiratory confounds | Breathing rate affects HF | Note if breathing was uncontrolled |
| Not reporting artifact rates | Reviewers can't assess data quality | Always report per condition |

## Key References

- Quigley, K.S., et al. (2024). Publication guidelines for human heart rate and heart rate variability studies in psychophysiology. *Psychophysiology*, 61(9), e14604. [doi:10.1111/psyp.14604](https://doi.org/10.1111/psyp.14604)
- Task Force of ESC and NASPE (1996). Heart rate variability: Standards of measurement. *Circulation*, 93(5), 1043–1065. [doi:10.1161/01.CIR.93.5.1043](https://doi.org/10.1161/01.CIR.93.5.1043)
- Quintana, D.S., et al. (2016). Guidelines for Reporting Articles on Psychiatry and Heart rate variability (GRAPH). *Translational Psychiatry*, 6(5), e803. [doi:10.1038/tp.2016.73](https://doi.org/10.1038/tp.2016.73)
- Lipponen, J.A., & Tarvainen, M.P. (2019). A robust algorithm for heart rate variability time series artefact correction. *Journal of Medical Engineering & Technology*, 43(3), 173–181. [doi:10.1080/03091902.2019.1640306](https://doi.org/10.1080/03091902.2019.1640306)
- Makowski, D., et al. (2021). NeuroKit2: A Python toolbox for neurophysiological signal processing. *Behavior Research Methods*, 53, 1689–1696. [doi:10.3758/s13428-020-01516-y](https://doi.org/10.3758/s13428-020-01516-y)
- Billman, G.E. (2013). The LF/HF ratio does not accurately measure cardiac sympatho-vagal balance. *Frontiers in Physiology*, 4, 26. [doi:10.3389/fphys.2013.00026](https://doi.org/10.3389/fphys.2013.00026)
