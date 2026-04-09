# Processing Pipeline

How RRational processes RR interval data from import to analysis results.

## Pipeline Overview

```
Import → Clean → Detect Artifacts → Validate Sections → Analyze → Export
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

RRational accepts two input formats:

- **HRV Logger** (iOS/Android): CSV files with real timestamps per beat
- **VNS Analyse** (clinical): TXT files with cumulative RR intervals

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
| Sudden change | 100% | Flags beats that change > 100% from predecessor |

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
4. Assign quality grade per segment (A/B/C/D based on artifact rate)

**Detection scope options**:

| Scope | What it analyzes |
|-------|-----------------|
| All validated sections | Only beats within validated section boundaries |
| Full recording | Entire recording from first to last beat |
| Custom range | User-defined time window |

## Stage 5: Artifact Correction

For segments with 2–10% artifacts, RRational applies **cubic interpolation** to replace detected artifacts with estimated values:

- Short artifacts (ectopic): replaced by mean of neighbors
- Long artifacts (missed beats): interpolated from surrounding beats

!!! warning
    Segments with > 10% artifacts should be **excluded**, not corrected. Over-correction distorts HRV metrics.

## Stage 6: Section Validation

Sections are defined by event boundaries (e.g., `measurement_start` → `pause_start`). Validation checks:

- Start event occurs before end event
- Section duration matches expected protocol (within tolerance)
- Beat count meets minimum requirements (100 for time-domain, 300 for frequency)
- No excessive gaps within the section

## Stage 7: HRV Analysis

RRational computes metrics using **overlapping windows** for reliability:

1. Divide section into windows (default: 300 beats, 75% overlap)
2. Compute HRV metrics per window via NeuroKit2
3. Aggregate: report mean across windows (with SD for within-participant variability)

**Available metrics:**

| Domain | Metrics |
|--------|---------|
| Time (basic) | RMSSD, SDNN, MeanNN, MeanHR, pNN50 |
| Time (extended) | SDSD, CVNN, CVSD, MedianNN, MadNN, MCVNN, IQRNN, TINN, HTI |
| Frequency | VLF, LF, HF, LF/HF, LFn, HFn, Total Power |
| Nonlinear | SD1, SD2, SD1/SD2, ApEn, SampEn |

## Stage 8: Export

| Format | Content | Use case |
|--------|---------|----------|
| **CSV** | Metric tables | Statistical analysis in R/SPSS/jamovi |
| **HTML Report** | Formatted report with summary cards | Sharing with supervisors, supplementary material |
| **Markdown** | Text report with tables | Research documentation |
| **.rrational** | Full analysis state (NN intervals, metadata, audit trail) | Reproducibility, re-import |

## References

- Lipponen, J.A., & Tarvainen, M.P. (2019). A robust algorithm for heart rate variability time series artefact correction. *Journal of Medical Engineering & Technology*, 43(3), 173–181.
- Quigley, K.S., et al. (2024). Guidelines for heart rate variability measurement and reporting. *Psychophysiology*.
- Makowski, D., et al. (2021). NeuroKit2: A Python toolbox for neurophysiological signal processing. *Behavior Research Methods*.
