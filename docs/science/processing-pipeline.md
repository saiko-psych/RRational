# Processing Pipeline

How RRational processes RR interval data from import to analysis results.

## Pipeline Overview

``` mermaid
flowchart LR
  A[Import] --> B[Clean]
  B --> C[Inspect]
  C --> D[Detect\nArtifacts]
  D --> E[Correct]
  E --> F[Validate\nSections]
  F --> G[Analyze]
  G --> H[Export]

  style A fill:#2E86AB,color:#fff
  style D fill:#ee6c4d,color:#fff
  style G fill:#1e3a5f,color:#fff
  style H fill:#28a745,color:#fff
```

| Stage | What happens | Where in the app |
|-------|-------------|------------------|
| **1. Import** | Load RR intervals + events from CSV/TXT | Data tab |
| **2. Clean** | Remove out-of-range values (200–2000 ms) | Automatic on import |
| **3. Inspect** | Visual tachogram, PSD, gap detection | Participants tab |
| **4. Detect Artifacts** | Lipponen-Tarvainen algorithm per segment | Participants tab |
| **5. Correct** | Interpolate artifact beats (Kubios method) | Analysis tab |
| **6. Validate Sections** | Define start/end events, check boundaries | Participants tab |
| **7. Analyze** | Compute HRV metrics per section/window | Analysis tab |
| **8. Export** | CSV, HTML report, .rrational file | Analysis tab |

## Stage 1: Data Import

RRational accepts 8 input formats: HRV Logger, VNS Analyse, Polar Sensor Logger, Polar Flow, Empatica E4, Elite HRV, Kubios HRV, and plain-text RR files. See [Data Formats](../user-guide/data-formats.md) for details.

On import, RRational:

1. Discovers all recording files matching the participant ID pattern
2. Merges multiple files per participant chronologically
3. Detects and reports time gaps between files
4. Extracts event markers from Events CSV files
5. Maps raw event labels to canonical names (e.g., "Messung Start" → `measurement_start`)

## Stage 2: Cleaning

Basic physiological filtering removes impossible values:

| Parameter | Default | Purpose |
|-----------|---------|---------|
| Minimum RR | 200 ms | Removes impossibly fast beats (> 300 BPM) |
| Maximum RR | 2000 ms | Removes impossibly slow beats (< 30 BPM) |
| Sudden change | 100% | Removes a beat that is more than **twice** the previous RR (e.g. a missed beat) before artifact detection runs; such beats are not counted as artifacts afterwards |

!!! warning "Known asymmetry of the sudden-change rule"
    The rule is `|RR - previous RR| / previous RR > threshold`. With the default 100% it can never fire for a *shorter* beat, so a premature beat (e.g. 399 ms after 800 ms) is **kept** and the normal beat that follows it is **removed** instead (800 / 399 > 2). Smaller beat-to-beat changes are left to the NeuroKit2 artifact detection.

!!! note
    For VNS Analyse data, no cleaning is applied during import. Artifact detection is handled separately at analysis time, since VNS timestamps are cumulative and removing beats would distort the time axis.

## Stage 3: Visual Inspection

The tachogram shows RR intervals over time with:

- **Event markers** — vertical lines at protocol events
- **Gap markers** — shaded regions where recording was interrupted
- **Condition sections** — colored bands for repeating conditions
- **Power Spectrum (PSD)** — expandable frequency-domain view

Three interaction modes:

- **Add Events** — click to place event markers
- **Add Exclusions** — define time ranges to exclude from analysis
- **Signal Inspection** — click individual beats to mark/unmark manual artifacts

## Stage 4: Artifact Detection

RRational uses **time-based segmentation** (Quigley 2024): the recording is divided into fixed-length windows (default: 5 minutes), and artifact detection runs on each segment independently.

**Algorithm**: Lipponen & Tarvainen (2019), implemented via NeuroKit2's `signal_fixpeaks`:

1. Compute successive RR differences (dRR) and deviation from local median (mRR)
2. Apply time-varying thresholds based on dRR and mRR distributions
3. Classify each beat: normal, ectopic, long, short, missed, or extra
4. Assign quality grade per segment (Excellent/Good/Moderate/Poor based on artifact rate)

**Detection scope options**:

| Scope | What it analyzes |
|-------|-----------------|
| All validated sections | Only beats within validated section boundaries |
| Full recording | Entire recording from first to last beat |
| Custom range | User-defined time window |

## Stage 5: Artifact Correction

Detected artifacts are corrected with the algorithm of **Lipponen & Tarvainen (2019)** (NeuroKit2 `signal_fixpeaks(method="Kubios", iterative=True)`). The correction works on R-peak positions, not on RR values:

| Artifact type | Correction | Effect on the NN series |
|---|---|---|
| Missed beat (one RR ≈ two beats) | A peak is inserted at the midpoint | The long interval is **split** into two (+1 beat) |
| Extra beat (spurious peak) | The peak is removed | Two short intervals are **merged** (−1 beat) |
| Ectopic / long-short beat | The peak is moved to the midpoint of its neighbours | Two adjacent intervals become equal; beat count unchanged |

Total recording time is preserved in every case. Because the number of NN intervals can differ from the number of raw RR intervals, the corrected series carries its own timestamps, and sections, segments and exports are mapped onto it (RRational keeps a raw → corrected beat map).

!!! note "Known limitations"
    - **Ectopic pairs**: NeuroKit2 moves two adjacent misaligned peaks using each other's *uncorrected* positions, so a premature/compensatory pair is improved but not fully equalised (example: 550 / 1050 / 785 ms → 733 / 734 / 918 ms; total time unchanged).
    - **Very low variability**: the missed/extra criteria use thresholds adapted to the local spread of RR differences. In recordings with very little beat-to-beat variability these thresholds become strict, and a true missed beat may be classified as long/short and have a peak moved instead of being split.

Earlier versions replaced each flagged RR value with the mean of its neighbours. That changed the recording duration (a missed 1600 ms beat became ~800 ms, losing 0.8 s) and kept phantom beats for extra detections.

!!! warning
    Segments with > 10% artifacts should be **excluded**, not corrected. Over-correction distorts HRV metrics.

## Stage 6: Section Validation

Sections are defined by event boundaries (e.g., `measurement_start` → `pause_start`). Validation checks:

- Start event occurs before end event
- Section duration matches expected protocol (within tolerance)
- Beat count meets minimum requirements (100 for time-domain, 300 for frequency)
- No excessive gaps within the section

## Stage 7: HRV Analysis

RRational computes metrics using **time-based windows** for reliability:

1. Divide section into fixed-length windows (default: 5 minutes, time-based)
2. Compute HRV metrics per window via NeuroKit2
3. Choose: per-segment results or aggregated mean across windows (with SD)

See [Recommended Workflow](recommended-workflow.md) for the full rationale behind this approach.

**Available metrics:**

| Domain | Metrics |
|--------|---------|
| Time (basic) | RMSSD, SDNN, MeanNN, MeanHR, pNN50 |
| Time (extended) | pNN20, SDSD, CVNN, CVSD, MedianNN, MadNN, MCVNN, IQRNN, TINN, HTI |
| Frequency | VLF, LF, HF, LF/HF, LFn, HFn, Total Power |
| Nonlinear | SD1, SD2, SD1/SD2, ApEn, SampEn, DFA α1, DFA α2 |

### Frequency-Domain Pipeline (`freq_method`)

Since v0.9.3, RRational supports two frequency-domain pipelines, selectable in
the Analysis tab under "Frequency-domain pipeline":

| Pipeline | Detrending | Interpolation | Welch window | PSD output | Bands |
|----------|-----------|---------------|--------------|------------|-------|
| **`neurokit`** (default) | Mean subtraction | NeuroKit2 default | NeuroKit2 default | Normalized | NK2 default (incl. ULF/VHF) |
| **`kubios`** | Smoothness Priors λ=500 | 4 Hz (Cubic Spline) | 180 s Hann, 50% overlap | Absolute ms² | VLF 0–0.04 / LF 0.04–0.15 / HF 0.15–0.40 Hz |

**When to use Kubios mode**: Direct cross-validation against Kubios HRV Scientific,
publishing in journals that reference Kubios values, or when reviewers request
absolute ms² units. See [Validation](validation.md) for the cross-validation report
(<10% agreement on frequency-domain metrics — RMSSD and HF within ±5%, LF within ±9% — with proper segment matching).

**Time-domain metrics are identical** in both modes — they always follow Task Force
1996 on raw NN intervals after artifact correction. Only the frequency-domain pipeline
is switched.

## Stage 8: Export

| Format | Content | Use case |
|--------|---------|----------|
| **CSV** | Metric tables | Statistical analysis in R/SPSS/jamovi |
| **HTML Report** | Formatted report with summary cards | Sharing with supervisors, supplementary material |
| **Markdown** | Text report with tables | Research documentation |
| **.rrational** | Full analysis state (NN intervals, metadata, audit trail) | Reproducibility, re-import |

## References

- Lipponen, J.A., & Tarvainen, M.P. (2019). A robust algorithm for heart rate variability time series artefact correction. *Journal of Medical Engineering & Technology*, 43(3), 173–181. [doi:10.1080/03091902.2019.1640306](https://doi.org/10.1080/03091902.2019.1640306)
- Quigley, K.S., et al. (2024). Publication guidelines for human heart rate and heart rate variability studies in psychophysiology. *Psychophysiology*, 61(9), e14604. [doi:10.1111/psyp.14604](https://doi.org/10.1111/psyp.14604)
- Makowski, D., et al. (2021). NeuroKit2: A Python toolbox for neurophysiological signal processing. *Behavior Research Methods*, 53, 1689–1696. [doi:10.3758/s13428-020-01516-y](https://doi.org/10.3758/s13428-020-01516-y)
