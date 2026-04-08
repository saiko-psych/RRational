# Scientific HRV Processing Pipeline for RR Interval Data

A methodological guide for processing heart rate variability from Polar H10 RR intervals in psychological research.

## Overview

This pipeline assumes you are starting with **RR intervals** (interbeat intervals) directly from a Polar H10 chest strap, bypassing raw ECG signal processing and R-peak detection. The Polar H10 is considered the reference standard for wearable HRV research, with validation studies confirming its accuracy against medical-grade ECG.

**Your recording context:**
- Device: Polar H10 (validated research-grade)
- Total duration: ~3 hours per participant
- Segments: Variable (5 min to 90+ min)
- Design: Pre/post baselines + extended task with break

---

## Stage 1: Data Import & Initial Validation

### 1.1 Load RR Intervals

Depending on your recording app, data arrives in one of two formats:

**Format A: TXT with embedded events**
- RR intervals only (ms)
- Events marked at specific intervals
- Simpler event alignment but less temporal precision

**Format B: CSV with timestamps**
- RR intervals with recording timestamps
- Events in separate CSV with timestamps
- More precise but requires alignment (note: Bluetooth introduces ~10-50 ms timing uncertainty)

### 1.2 Initial Sanity Checks

Before any processing, validate raw data:

| Check | Expected Range | Flag if |
|-------|---------------|---------|
| RR interval range | 300–2000 ms | Values outside range |
| Corresponding HR | 30–200 bpm | Implausible values |
| Recording gaps | Continuous | Missing segments >2 sec |
| Total beat count | ~3600 beats/hour | Major deviations |

### 1.3 Bluetooth Dropout Detection

Polar H10 transmits via Bluetooth, which can cause:
- **Missing beats**: Gaps in data stream
- **Spurious values**: Transmission errors
- **Timestamp drift**: Cumulative timing errors in long recordings

**Detection approach:**
```python
import numpy as np

def detect_bluetooth_issues(rr_intervals, threshold_short=300, threshold_long=2000):
    """Flag potential Bluetooth-related artifacts."""
    issues = {
        'implausibly_short': np.where(rr_intervals < threshold_short)[0],
        'implausibly_long': np.where(rr_intervals > threshold_long)[0],
        'total_flagged': 0
    }
    issues['total_flagged'] = len(issues['implausibly_short']) + len(issues['implausibly_long'])
    issues['percent_flagged'] = issues['total_flagged'] / len(rr_intervals) * 100
    return issues
```

---

## Stage 2: Artifact Detection

This is the most critical stage since you cannot return to raw ECG for verification.

### 2.1 The Lipponen-Tarvainen Algorithm (2019)

The current state-of-the-art for RR interval artifact detection. It uses time-varying thresholds based on:
- Distribution of successive RR differences (dRR)
- Deviations from local median RR

**Beat classifications:**
| Category | Description | Typical Cause |
|----------|-------------|---------------|
| Normal | Physiologically valid | — |
| Ectopic | Premature ventricular/atrial beat | Cardiac event |
| Long | One interval spans two beats | Missed detection |
| Short | Interval shorter than expected | Extra detection |
| Missed | Beat not detected | Signal dropout |
| Extra | False positive detection | Noise/artifact |

**Performance:** 96.96% sensitivity, 99.94% specificity for ectopic beat detection.

### 2.2 Implementation Options

**Option A: NeuroKit2 (Python)**
```python
import neurokit2 as nk

# Detect artifacts
artifacts, info = nk.hrv_correct_artifacts(rr_intervals, method="Lipponen2019")
```

**Option B: Kubios HRV (Recommended for visual inspection)**
- Import RR intervals directly
- Automatic artifact detection with manual override
- Visual inspection of each flagged beat
- Export cleaned data for further processing

**Recommendation:** For your 3-hour recordings with multiple conditions, use Kubios for artifact detection/correction with visual inspection, then export cleaned data to Python for batch analysis.

### 2.3 Artifact Threshold

Per 2024 Quigley et al. guidelines:
- **<5% artifacts**: Acceptable for reliable HRV
- **5–10% artifacts**: Use with caution, report prominently
- **>10% artifacts**: Consider excluding segment

For a 5-minute segment (~300 beats): maximum ~15 corrected beats.

---

## Stage 3: Artifact Correction

### 3.1 Correction Methods

| Method | Description | Best For |
|--------|-------------|----------|
| Deletion | Remove artifact beats | Few artifacts, time-domain only |
| Linear interpolation | Straight line between valid beats | Quick approximation |
| Cubic spline | Smooth curve fitting | Standard choice |
| Piecewise cubic Hermite | Shape-preserving interpolation | Ectopic beats |

### 3.2 Ectopic Beat Correction

Ectopic beats create a characteristic short-long pattern:
- Beat arrives early (short RR)
- Compensatory pause follows (long RR)
- Total time is approximately preserved

**Standard correction:** Replace the short+long pair with interpolated values that preserve total duration.

```python
def correct_ectopic_pair(rr_before, rr_short, rr_long, rr_after):
    """Replace ectopic short-long pair with interpolated values."""
    total_time = rr_short + rr_long
    # Simple approach: divide equally
    corrected = total_time / 2
    return [corrected, corrected]
    # Or use cubic interpolation for smoother result
```

### 3.3 Quality Decision Tree

```
Artifact percentage for segment:
│
├─ <5%  → Proceed with correction
│
├─ 5-10% → Correct, but flag segment in analysis
│         Report artifact % in results
│
└─ >10% → Consider excluding segment
          Document reason for exclusion
```

---

## Stage 4: Preprocessing (Detrending)

### 4.1 When to Detrend

| Segment Duration | Detrending | Rationale |
|-----------------|------------|-----------|
| ≤5 minutes | Usually unnecessary | Limited drift expected |
| 5–30 minutes | Consider for frequency analysis | Moderate non-stationarity |
| >30 minutes | Required | Significant drift from posture, circadian effects |

### 4.2 Tarvainen Smoothness Priors Method

The recommended detrending approach for HRV (Tarvainen et al., 2002):

```python
import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve

def detrend_tarvainen(rr_intervals, lambda_value=500):
    """
    Remove slow trends using smoothness priors.
    
    Parameters:
    -----------
    rr_intervals : array
        RR intervals in ms
    lambda_value : float
        Smoothing parameter (500 recommended for HRV)
        Higher = less smoothing (keeps more low-frequency content)
    
    Returns:
    --------
    detrended : array
        Detrended RR intervals (mean preserved)
    """
    T = len(rr_intervals)
    I = sparse.eye(T)
    D2 = sparse.diags([1, -2, 1], [0, 1, 2], shape=(T-2, T))
    
    trend = spsolve(I + lambda_value**2 * D2.T @ D2, rr_intervals)
    detrended = rr_intervals - trend + np.mean(rr_intervals)
    
    return detrended, trend
```

**Lambda parameter guidance:**
- λ = 500: Standard for HRV (cutoff ~0.035 Hz)
- λ = 300: More aggressive detrending
- λ = 1000: Gentler detrending (preserves more low-frequency)

---

## Stage 5: Segmentation Strategy

### 5.1 Segment Duration and Metric Validity

| Duration | Valid Metrics | Notes |
|----------|--------------|-------|
| 30 sec | Mean HR only | Insufficient for HRV |
| 60 sec | RMSSD, mean HR, possibly pNN50 | Validated for RMSSD in athlete monitoring |
| 2–3 min | All time-domain metrics | Acceptable for RMSSD-focused studies |
| 5 min | All short-term metrics (time, frequency, nonlinear) | **Standard recommendation** |
| >5 min | Time-domain; window frequency analysis | Stationarity concerns |
| 24 hr | Full metric suite including VLF, ULF, SDANN | Clinical standard |

**Critical:** Never compare SDNN values across different segment durations.

### 5.2 Segmentation Approaches for Your Design

**For baselines (pre/post):**
- Use standard 5-minute segments
- Allows comparison with published norms
- Compute full metric suite

**For extended task (~90 min):**

*Option A: Fixed windows*
```python
def segment_fixed_windows(rr_intervals, window_size_sec=300, step_sec=300):
    """Divide into consecutive epochs."""
    # Convert to cumulative time
    cumtime = np.cumsum(rr_intervals) / 1000  # seconds
    
    segments = []
    start_time = 0
    while start_time + window_size_sec <= cumtime[-1]:
        mask = (cumtime >= start_time) & (cumtime < start_time + window_size_sec)
        segments.append(rr_intervals[mask])
        start_time += step_sec
    
    return segments
```

*Option B: Sliding windows (for time-course analysis)*
```python
def segment_sliding_windows(rr_intervals, window_size_sec=300, step_sec=30):
    """Overlapping windows for continuous HRV time course."""
    # Same logic as above but with step < window_size
    pass
```

*Option C: Event-locked segments*
- Extract fixed-duration segments around specific events
- Useful for reactivity analysis

### 5.3 Handling Your Specific Design

```
Recording Structure:
│
├── Baseline 1 (pre)
│   └── 5-min segment → Full HRV analysis
│
├── Task Block 1
│   ├── Option: 5-min epochs throughout
│   └── Option: Event-locked segments
│
├── Break
│   └── Analyze separately or exclude
│
├── Task Block 2 (with adjustments)
│   └── Same approach as Block 1
│
└── Baseline 2 (post)
    └── 5-min segment → Full HRV analysis
```

---

## Stage 6: HRV Computation

### 6.1 Time-Domain Metrics

Calculated directly from RR intervals without transformation:

| Metric | Formula/Description | Interpretation |
|--------|---------------------|----------------|
| **RMSSD** | √(mean(ΔRR²)) | Primary vagal index; robust for short segments |
| **SDNN** | SD of all RR intervals | Total variability (sympathetic + parasympathetic) |
| **pNN50** | % of ΔRR > 50 ms | Vagal index; less sensitive than RMSSD |
| **Mean RR** | Mean of RR intervals | Inverse of mean HR |
| **SDSD** | SD of successive differences | Mathematically related to RMSSD |

```python
import neurokit2 as nk

# For RR intervals in ms
hrv_time = nk.hrv_time(rr_intervals, sampling_rate=None)
```

### 6.2 Frequency-Domain Metrics

Requires interpolation to uniform sampling:

**Preprocessing for spectral analysis:**
```python
from scipy import interpolate

def prepare_for_spectral(rr_intervals, fs=4.0):
    """
    Interpolate RR intervals to uniform sampling.
    
    Parameters:
    -----------
    rr_intervals : array
        RR intervals in ms
    fs : float
        Target sampling frequency (4 Hz standard)
    """
    # Create time vector
    t_rr = np.cumsum(rr_intervals) / 1000  # cumulative time in seconds
    t_rr = t_rr - t_rr[0]  # start at 0
    
    # Create uniform time vector
    t_uniform = np.arange(0, t_rr[-1], 1/fs)
    
    # Cubic spline interpolation
    f_interp = interpolate.interp1d(t_rr, rr_intervals, kind='cubic', 
                                     bounds_error=False, fill_value='extrapolate')
    rr_uniform = f_interp(t_uniform)
    
    return rr_uniform, t_uniform
```

**Standard frequency bands:**

| Band | Range | Physiological Correlate |
|------|-------|------------------------|
| ULF | <0.003 Hz | Circadian rhythms (24-hr only) |
| VLF | 0.003–0.04 Hz | Thermoregulation, hormonal (requires >5 min) |
| LF | 0.04–0.15 Hz | Baroreflex function (NOT sympathetic) |
| HF | 0.15–0.4 Hz | Respiratory sinus arrhythmia, vagal |

```python
hrv_freq = nk.hrv_frequency(rr_intervals, sampling_rate=None)
```

**Critical interpretive note:** Do NOT interpret LF as "sympathetic activity" or LF/HF ratio as "sympathovagal balance" — this interpretation is not supported by current evidence.

### 6.3 Nonlinear Metrics

| Metric | Description | Interpretation |
|--------|-------------|----------------|
| **SD1** | Poincaré plot width | ≈ RMSSD, short-term variability |
| **SD2** | Poincaré plot length | Longer-term variability |
| **SD1/SD2** | Ratio | Relates to fractal scaling |
| **DFA α1** | Short-term fractal scaling (4–16 beats) | Healthy ≈ 1.0–1.5 |
| **DFA α2** | Long-term fractal scaling | Circadian influences |
| **SampEn** | Sample entropy | Complexity/predictability |

```python
hrv_nonlinear = nk.hrv_nonlinear(rr_intervals, sampling_rate=None)
```

### 6.4 Recommended Metric Selection

**Primary metrics (always report):**
- RMSSD — Most robust vagal index
- SDNN — Total variability (within same-duration segments only)
- Mean HR/RR — Basic check and covariate

**Secondary metrics (for 5-min segments):**
- HF power (ms²) — Parasympathetic
- LF power (ms²) — Report but interpret cautiously
- Total power — Overall variability

**Optional (if relevant to research question):**
- SD1/SD2 — Quick nonlinear check
- DFA α1 — Complexity assessment

---

## Stage 7: Quality Control Checklist

### Pre-Analysis Verification

For each segment, confirm:

- [ ] Artifact percentage calculated and <5%
- [ ] No remaining physiologically implausible values
- [ ] Segment duration matches intended duration (±5%)
- [ ] Event markers correctly aligned
- [ ] Visual inspection of RR tachogram completed

### Visual Inspection Points

**RR Tachogram:**
- No sudden jumps (uncorrected artifacts)
- No flat lines (data dropout)
- Trend appropriate for segment duration

**Poincaré Plot:**
- Healthy "comet" shape expected
- No isolated outliers
- Symmetric distribution

**Power Spectrum (for frequency analysis):**
- No sharp spikes (residual artifacts)
- No flat regions (data problems)
- Peaks in expected frequency ranges

---

## Stage 8: Complete Processing Pipeline

### 8.1 Recommended Workflow

```
Raw RR Intervals (Polar H10)
           │
           ▼
    ┌─────────────────┐
    │ 1. Data Import  │
    │    & Validation │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 2. Artifact     │  ← Kubios HRV (visual inspection)
    │    Detection    │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 3. Artifact     │  ← Document % corrected
    │    Correction   │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 4. Export       │  ← Cleaned RR intervals
    │    Clean Data   │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 5. Segmentation │  ← Python/NeuroKit2
    │    by Events    │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 6. Detrending   │  ← For segments >5 min
    │    (if needed)  │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 7. HRV          │
    │    Computation  │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ 8. Quality      │
    │    Control      │
    └────────┬────────┘
             │
             ▼
      Analysis-Ready
         HRV Data
```

### 8.2 Example Python Pipeline

```python
import numpy as np
import pandas as pd
import neurokit2 as nk
from pathlib import Path

def process_hrv_recording(rr_file, events_file, output_dir):
    """
    Complete HRV processing pipeline for Polar H10 data.
    
    Parameters:
    -----------
    rr_file : str
        Path to cleaned RR intervals (after Kubios processing)
    events_file : str
        Path to event markers
    output_dir : str
        Directory for output files
    """
    
    # 1. Load data
    rr_intervals = load_rr_intervals(rr_file)  # Implement based on your format
    events = load_events(events_file)
    
    # 2. Segment by events
    segments = {}
    segments['baseline_pre'] = extract_segment(rr_intervals, events, 
                                                'baseline_start', duration_sec=300)
    segments['task'] = extract_segment(rr_intervals, events,
                                       'task_start', 'task_end')
    segments['baseline_post'] = extract_segment(rr_intervals, events,
                                                 'baseline_post_start', duration_sec=300)
    
    # 3. Process each segment
    results = {}
    for name, rr in segments.items():
        # Detrend if long segment
        if len(rr) * np.mean(rr) / 1000 > 300:  # >5 min
            rr, _ = detrend_tarvainen(rr, lambda_value=500)
        
        # Compute HRV metrics
        hrv = compute_hrv_metrics(rr)
        hrv['segment'] = name
        hrv['n_beats'] = len(rr)
        hrv['duration_sec'] = np.sum(rr) / 1000
        
        results[name] = hrv
    
    # 4. Combine and save
    results_df = pd.DataFrame(results).T
    results_df.to_csv(Path(output_dir) / 'hrv_results.csv')
    
    return results_df

def compute_hrv_metrics(rr_intervals):
    """Compute comprehensive HRV metrics."""
    metrics = {}
    
    # Time domain
    hrv_time = nk.hrv_time(rr_intervals, sampling_rate=None)
    metrics.update(hrv_time.iloc[0].to_dict())
    
    # Frequency domain (only if sufficient duration)
    duration_sec = np.sum(rr_intervals) / 1000
    if duration_sec >= 120:  # At least 2 minutes
        hrv_freq = nk.hrv_frequency(rr_intervals, sampling_rate=None)
        metrics.update(hrv_freq.iloc[0].to_dict())
    
    # Nonlinear
    hrv_nonlinear = nk.hrv_nonlinear(rr_intervals, sampling_rate=None)
    metrics.update(hrv_nonlinear.iloc[0].to_dict())
    
    return metrics
```

---

## Reporting Requirements

Following GRAPH checklist (Quintana et al., 2016) and Quigley et al. (2024) guidelines:

### Methods Section Must Include:

**Data Collection:**
- Device: Polar H10 chest strap
- Sampling: Native RR interval recording
- Recording app and version
- Total recording duration
- Environmental conditions (if controlled)

**Preprocessing:**
- Artifact detection algorithm (Lipponen-Tarvainen 2019)
- Artifact correction method (interpolation type)
- Mean artifact percentage (± SD) across participants
- Segments excluded and criteria
- Detrending method and parameters (if used)

**HRV Analysis:**
- Software and version (e.g., NeuroKit2 v0.2.x)
- Segment durations for each analysis
- Specific metrics computed
- Frequency band definitions
- Interpolation rate for spectral analysis

### Results Section Must Include:

- Artifact percentages per condition
- Sample sizes after exclusions
- All computed metrics with appropriate statistics
- Effect sizes for comparisons

---

## Common Pitfalls to Avoid

| Pitfall | Why It's a Problem | Solution |
|---------|-------------------|----------|
| Comparing SDNN across different durations | SDNN scales with duration | Only compare same-duration segments |
| Interpreting LF as "sympathetic" | Not supported by evidence | Report LF but interpret as baroreflex-related |
| Using LF/HF as sympathovagal balance | Mathematically and physiologically flawed | Avoid or interpret very cautiously |
| Over-correcting artifacts | Artificially reduces HRV | Limit to <5% correction; exclude if more needed |
| Ignoring respiratory confounds | Respiration affects HF interpretation | Note if breathing rate was unusual/uncontrolled |
| Computing frequency metrics on <2 min segments | Insufficient data for spectral estimation | Use time-domain only for short segments |

---

## Key References

**Guidelines:**
- Quigley, K.S., et al. (2024). Guidelines for HR/HRV measurement. *Psychophysiology*.
- Task Force (1996). HRV standards of measurement. *Circulation*, 93(5), 1043-1065.
- Quintana, D.S., et al. (2016). GRAPH guidelines. *International Journal of Psychophysiology*.

**Methods:**
- Lipponen, J.A., & Tarvainen, M.P. (2019). Robust ectopic beat correction. *Medical & Biological Engineering & Computing*.
- Tarvainen, M.P., et al. (2002). Smoothness priors detrending. *IEEE EMBS*.
- Tarvainen, M.P., et al. (2014). Kubios HRV methods. *Computer Methods and Programs in Biomedicine*.

**Software:**
- Makowski, D., et al. (2021). NeuroKit2. *Behavior Research Methods*.

**Interpretation:**
- Billman, G.E. (2013). LF/HF ratio does not measure sympathovagal balance. *Frontiers in Physiology*.
- Laborde, S., et al. (2017). HRV recommendations for psychophysiology. *Frontiers in Psychology*.
