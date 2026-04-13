# Recommended Analysis Workflow

A step-by-step guide for rigorous HRV analysis, based on current scientific guidelines and expert recommendations for psychophysiological research.

## When to Use This Workflow

This segmented analysis approach is recommended for studies with **recordings longer than 5 minutes** where experimental conditions change over time. Typical use cases:

| Use Case | Example Protocol | Why segmentation helps |
|----------|-----------------|----------------------|
| **Music & emotion research** | Rest → Music A → Pause → Music B → Rest | Track autonomic changes across conditions; identify non-stationary phases (Bernardi et al., 2006; Koelsch & Jancke, 2015) |
| **Stress & relaxation studies** | Baseline → Stressor → Recovery | Compare HRV between phases with per-segment quality control |
| **Clinical monitoring** | Pre → Intervention → Post | Ensure artifact-free segments before/after treatment (Sammito et al., 2024) |
| **Intervention studies** | Multiple conditions with rest periods | Aggregated metrics across validated segments improve reliability (Buchheit, 2014) |
| **Student research projects** | Any within-subject repeated-measures design | Transparent, reproducible pipeline with quality reporting (Quintana et al., 2016) |

!!! note "Not needed for single 5-minute resting recordings"
    If your protocol is a single, short (≤5 min) resting measurement, segmentation is unnecessary — analyze the full recording as one segment.

## Why This Workflow?

HRV analysis requires careful attention to data quality. The core problem: **long recordings are not stationary** — heart rate drifts over minutes and hours due to fatigue, temperature, posture changes, and circadian effects (Li et al., 2019). Analyzing a 90-minute recording as one block produces unreliable frequency-domain metrics and inflated SDNN (Task Force, 1996; Shaffer & Ginsberg, 2017).

The solution is **segmentation**: divide recordings into short, quasi-stationary windows, assess quality per segment, exclude bad segments, and aggregate the validated results (Berntson et al., 1997; Quigley et al., 2024).

## The 7-Step Workflow

``` mermaid
flowchart TD
    A[1. Import & Inspect] --> B[2. Define Sections]
    B --> C[3. Segment into Windows]
    C --> D[4. Detect Artifacts per Segment]
    D --> E[5. Assess & Exclude]
    E --> F[6. Correct & Analyze]
    F --> G[7. Aggregate & Report]

    style A fill:#2E86AB,color:#fff
    style D fill:#ee6c4d,color:#fff
    style E fill:#ffc107,color:#000
    style G fill:#28a745,color:#fff
```

---

### Step 1: Import & Visual Inspection

**What:** Load RR interval data and visually inspect the tachogram.

**Why:** Visual inspection catches problems that algorithms miss — sensor disconnects, participant movement, recording errors, or mislabeled events.

**In RRational:**

1. **Data tab** → set raw data path → **Analyze Folder**
2. **Participants tab** → select participant → examine tachogram
3. Check for: obvious gaps, extreme outliers, flat-line sections, correct event placement

!!! tip
    Enable **Show time gaps** in Plot Options to highlight recording interruptions (gray regions).

---

### Step 2: Define Protocol Sections

**What:** Mark the boundaries of each experimental condition using events.

**Why:** Each condition (rest, measurement, pause) must be analyzed separately. Mixing conditions invalidates the analysis — resting HRV is fundamentally different from task HRV.

**Example study protocol:**

```
rest_pre        measurement_1         pause        measurement_2         rest_post
|── 5 min ──|────── 90 min ──────|── 10 min ──|────── 90 min ──────|── 5 min ──|
```

**In RRational:**

1. **Setup tab → Events** → verify event names and synonyms
2. **Setup tab → Sections** → define each section with start/end events
3. Verify section durations match your protocol

---

### Step 3: Segment into Time-Based Windows

**What:** Divide each section into fixed-length windows (typically 5 minutes).

**Why:**

- **Stationarity**: Spectral HRV analysis (FFT) assumes the signal is stationary within the analysis window (Berntson et al., 1997). A 5-minute window is short enough to approximate stationarity, but long enough for reliable frequency-domain analysis — the Task Force (1996) established this as the standard short-term recording duration.
- **Comparability**: SDNN reflects total variability and scales directly with recording duration — comparing SDNN from different durations is invalid (Task Force, 1996; Sacha, 2013). Fixed 5-minute windows ensure comparability across conditions, participants, and studies.
- **Detrending becomes unnecessary**: With 5-minute windows, slow drifts are negligible. The segmentation itself acts as an implicit high-pass filter (Tarvainen et al., 2002 describe the detrending problem, which windowing avoids more transparently). See [Why Not Detrend?](#why-not-detrend) below.
- **Granular quality control**: A single noisy minute in a 90-minute recording only affects one segment, not the entire analysis. Per-segment quality indices are the current standard (Vest et al., 2018).
- **Metric reliability**: RMSSD and HF are reliable in 5-minute segments (ICC 0.83–0.93; Shaffer & Ginsberg, 2017). Aggregating across multiple validated segments further improves reliability (Buchheit, 2014).

**Window parameters:**

| Parameter | Recommended | Why |
|-----------|-------------|-----|
| **Duration** | 5 minutes | Standard short-term window (Task Force 1996) |
| **Overlap** | 0% or 50% | 0% for independent segments; 50% for smoother estimates |

**Resulting segments per section (no overlap):**

| Section | Duration | Segments |
|---------|----------|----------|
| rest_pre | 5 min | 1 |
| measurement_1 | 90 min | 18 |
| pause | 10 min | 2 |
| measurement_2 | 90 min | 18 |
| rest_post | 5 min | 1 |
| **Total** | **200 min** | **40 segments** |

**In RRational:**

- Analysis tab → **Window Analysis Settings** → set duration to 5.0 min

!!! warning "Time-based, not beat-based"
    Always use **time-based** windows (minutes), not beat-based windows. A 300-beat window is ~5 minutes at 60 bpm but only ~3 minutes at 100 bpm — this makes segments incomparable across participants with different heart rates.

---

### Step 4: Detect Artifacts Per Segment

**What:** Run artifact detection on each segment independently, using the **exact same segments** that will be used for analysis.

**Why:**

- **Same segments for detection and analysis**: If you detect artifacts on the full recording but analyze 5-minute windows, the artifact rate per window is unknown. A segment might have 0% artifacts overall but 25% concentrated in one window.
- **Per-segment quality grades**: Each segment gets its own quality assessment (Grade A/B/C/D). This enables informed decisions about which segments to include.

**In RRational:**

1. **Participants tab** → Artifact Detection section
2. Set detection scope to **All validated sections**
3. Set window duration to **match your analysis window** (5 min)
4. Click **Run Detection**
5. Review the **Segment Assessment Table**

``` mermaid
flowchart TD
    A[Artifact rate per segment] --> B{< 2%?}
    B -->|Yes| C[Grade A — use as-is]
    B -->|No| D{< 5%?}
    D -->|Yes| E[Grade B — correct, then analyze]
    D -->|No| F{< 10%?}
    F -->|Yes| G[Grade C — correct, time-domain only]
    F -->|No| H[Grade D — EXCLUDE]

    style C fill:#28a745,color:#fff
    style E fill:#2E86AB,color:#fff
    style G fill:#ffc107,color:#000
    style H fill:#dc3545,color:#fff
```

---

### Step 5: Assess Quality & Exclude Bad Segments

**What:** Review each segment individually. Exclude segments with unacceptable artifact rates (> 10%).

**Why:**

- **Over-correction is worse than exclusion**: Correcting (interpolating) more than 10% of beats fundamentally changes the signal. Frequency-domain metrics are especially sensitive — LF power tolerates only ~2% beat removal before significant distortion (Sheridan et al., 2020). Time-domain metrics are more robust but still degrade above 10% (Peltola, 2012).
- **Transparency**: Reporting how many segments were excluded (and why) is required by current guidelines (GRAPH; Quintana et al., 2016). Quigley et al. (2024) recommend combining automated detection with visual inspection.
- **Automated + manual**: Automated artifact detection alone is insufficient (Laborde et al., 2017). RRational supports both: algorithm-based detection per segment, plus manual marking of individual beats in Signal Inspection mode.

**Both approaches are valid:**

| Approach | When to use | In RRational |
|----------|-------------|--------------|
| **Individual assessment** | Checking each segment manually | Segment Assessment Table with include/exclude checkboxes |
| **Automatic threshold** | Large datasets, reproducibility | Segments with Grade D are auto-excluded |

**In RRational:**

- The Segment Assessment Table shows quality grades, beat count, and artifact rate for each segment
- Uncheck segments you want to exclude
- Excluded segments are skipped in the analysis

---

### Step 6: Correct Artifacts & Compute HRV

**What:** Apply artifact correction to included segments (Grade B/C), then compute HRV metrics per segment.

**Why:**

- **Correction, not deletion**: Ectopic beats are replaced by interpolated values (cubic spline), preserving the time structure. Simply deleting ectopic beats would shift all subsequent timestamps.
- **Per-segment metrics**: Computing metrics per segment enables both individual reporting and later aggregation.

**In RRational:**

1. **Analysis tab** → select participant and sections
2. Choose **Per-segment (individual results)** for detailed segment-by-segment output
3. Or choose **Aggregated (mean across windows)** for the summary

**Metrics computed per segment:**

| Domain | Metrics | Minimum |
|--------|---------|---------|
| Time | RMSSD, SDNN, pNN50, Mean HR | 100 beats |
| Frequency | LF, HF, LF/HF, Total Power | 300 beats, 5 min |
| Nonlinear | SD1, SD2, SD1/SD2 | 100 beats |

---

### Step 7: Aggregate & Report

**What:** Average validated metrics across included segments per condition. Report both the aggregate and the quality information.

**Why:**

- **Aggregation reduces noise**: Single 5-minute segments have within-session ICCs of 0.60–0.93 depending on the metric (parasympathetic metrics like RMSSD show higher reliability: ICC 0.83–0.93). Averaging across multiple segments yields more robust estimates (Shaffer & Ginsberg, 2017; Buchheit, 2014).
- **Report quality**: Reviewers need to assess data quality. The GRAPH checklist (Quintana et al., 2016) requires reporting artifact correction methods, exclusion criteria, and data quality per condition. Quigley et al. (2024) formalize this further.

**What to report (per condition):**

| Information | Example |
|-------------|---------|
| Number of segments analyzed | 16 of 18 (2 excluded) |
| Mean artifact rate | 2.3% ± 1.1% |
| Mean RMSSD | 42.5 ± 8.3 ms |
| Mean SDNN | 51.2 ± 12.1 ms |
| Mean HF Power | 845 ± 312 ms² |
| Window duration | 5 min, no overlap |
| Correction method | Kubios (NeuroKit2), Grade D excluded |

**In RRational:**

- **Aggregated mode**: Automatically computes mean ± SD across included windows
- **Export**: Download as CSV for statistical analysis, or generate an HTML report

---

## Why Not Detrend?

A common question is whether **detrending** (removing slow trends) is needed before frequency-domain analysis.

**With 5-minute segmentation: no.** Here's why:

| Concern | Without segmentation | With 5-min segments |
|---------|---------------------|---------------------|
| Baseline drift | Inflates VLF/LF power | Negligible within 5 min |
| Non-stationarity | Violates FFT assumptions | Each segment is quasi-stationary |
| SDNN inflation | Yes, for long recordings | Controlled by fixed window length |

Detrending is only relevant when analyzing **long continuous recordings** (>10 min) as a single block. The segmentation approach solves the same problem more transparently — you can see and assess each segment individually, rather than relying on a mathematical transformation that may itself introduce artifacts.

!!! note "Kubios comparison"
    When comparing RRational results with Kubios HRV, set **Detrending = OFF** in Kubios. With identical segmentation and no detrending, time-domain metrics should match within <1%.

---

## Summary

| Step | Purpose | Key setting |
|------|---------|-------------|
| 1. Import & Inspect | Catch obvious problems | Visual tachogram |
| 2. Define Sections | Separate experimental conditions | Events + Sections |
| 3. Segment | Ensure stationarity + comparability | 5 min, time-based |
| 4. Detect Artifacts | Per-segment quality assessment | Same segments as analysis |
| 5. Assess & Exclude | Remove unreliable data | >10% artifacts = exclude |
| 6. Correct & Analyze | Compute HRV per valid segment | Interpolation for 2-10% |
| 7. Aggregate & Report | Robust estimates + transparency | Mean ± SD + quality info |

## References

- Bernardi, L., Porta, C., & Sleight, P. (2006). Cardiovascular, cerebrovascular, and respiratory changes induced by different types of music. *Heart*, 92(4), 445–452.
- Berntson, G.G., et al. (1997). Heart rate variability: Origins, methods, and interpretive caveats. *Psychophysiology*, 34(6), 623–648.
- Buchheit, M. (2014). Monitoring training status with HR measures: Do all roads lead to Rome? *Frontiers in Physiology*, 5, 73.
- Koelsch, S. & Jancke, L. (2015). Music and the heart. *European Heart Journal*, 36(44), 3043–3049.
- Laborde, S., Mosley, E., & Thayer, J.F. (2017). Heart rate variability and cardiac vagal tone in psychophysiological research. *Frontiers in Psychology*, 8, 213.
- Li, K., Rudiger, H., & Ziemssen, T. (2019). Spectral analysis of heart rate variability: Time window matters. *Frontiers in Neurology*, 10, 545.
- Lipponen, J.A., & Tarvainen, M.P. (2019). A robust algorithm for heart rate variability time series artefact correction. *Journal of Medical Engineering & Technology*, 43(3), 173–181.
- Peltola, M.A. (2012). Role of editing of R-R intervals in the analysis of heart rate variability. *Frontiers in Physiology*, 3, 148.
- Quigley, K.S., et al. (2024). Publication guidelines for human heart rate and heart rate variability studies in psychophysiology. *Psychophysiology*, 61(7), e14604.
- Quintana, D.S., Alvares, G.A., & Heathers, J.A. (2016). Guidelines for Reporting Articles on Psychiatry and Heart rate variability (GRAPH). *Translational Psychiatry*, 6, e803.
- Sacha, J. (2013). Why should one normalize heart rate variability with respect to average heart rate. *Frontiers in Physiology*, 4, 306.
- Sammito, S., et al. (2024). Guideline for the application of heart rate and heart rate variability in occupational medicine. *Journal of Occupational Medicine and Toxicology*, 19, 22.
- Shaffer, F. & Ginsberg, J.P. (2017). An overview of heart rate variability metrics and norms. *Frontiers in Public Health*, 5, 258.
- Sheridan, D.C., et al. (2020). Heart rate variability analysis: How much artifact can we remove? *Psychiatry Investigation*, 17(9), 960–966.
- Tarvainen, M.P., Ranta-Aho, P.O., & Karjalainen, P.A. (2002). An advanced detrending method with application to HRV analysis. *IEEE Transactions on Biomedical Engineering*, 49(2), 172–175.
- Task Force of ESC and NASPE (1996). Heart rate variability: Standards of measurement. *Circulation*, 93(5), 1043–1065.
- Vest, A.N., et al. (2018). An open source benchmarked toolbox for cardiovascular waveform and interval analysis. *Physiological Measurement*, 39(10), 105004.
