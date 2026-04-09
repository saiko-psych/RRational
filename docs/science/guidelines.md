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
| **A** | < 2% | All (time, frequency, nonlinear) | Use as-is |
| **B** | 2–5% | All | Correct artifacts, then analyze |
| **C** | 5–10% | Time-domain only | Correct, but avoid frequency metrics |
| **D** | > 10% | None reliably | **Exclude from analysis** |

### Minimum Data Requirements

| Analysis | Minimum | Recommended | Why |
|----------|---------|-------------|-----|
| Time-domain (RMSSD, SDNN) | 100 beats | 300+ beats | Statistical reliability |
| Frequency-domain (LF, HF) | 300 beats | 500+ beats | Spectral estimation needs sufficient data |
| Recording duration for frequency | 2 minutes | 5 minutes | Standard short-term window (Task Force 1996) |

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

- Quigley, K.S., et al. (2024). Guidelines for heart rate variability measurement and reporting. *Psychophysiology*.
- Task Force of ESC and NASPE (1996). Heart rate variability: Standards of measurement. *Circulation*, 93(5), 1043–1065.
- Quintana, D.S., et al. (2016). Guidelines for Reporting Articles on Psychiatry and Heart rate variability (GRAPH). *Translational Psychiatry*, 6(5), e803.
- Lipponen, J.A., & Tarvainen, M.P. (2019). A robust algorithm for heart rate variability time series artefact correction. *Journal of Medical Engineering & Technology*, 43(3), 173–181.
- Makowski, D., et al. (2021). NeuroKit2: A Python toolbox for neurophysiological signal processing. *Behavior Research Methods*.
- Billman, G.E. (2013). The LF/HF ratio does not accurately measure cardiac sympatho-vagal balance. *Frontiers in Physiology*, 4, 26.
