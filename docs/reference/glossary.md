# Glossary

## Core Concepts

**RR Interval**
:   Time between consecutive heartbeats (R-peaks on ECG), measured in milliseconds. Also called inter-beat interval (IBI).

**NN Interval**
:   "Normal-to-Normal" interval — RR intervals after removing artifacts and ectopic beats. HRV metrics are computed from NN intervals, not raw RR intervals.

**Heart Rate Variability (HRV)**
:   The variation in time intervals between consecutive heartbeats. Higher HRV generally indicates better cardiovascular health and autonomic flexibility.

**Tachogram**
:   A plot of RR (or NN) intervals over time. The primary visual tool for inspecting heart rate recordings.

---

## Time-Domain Metrics

**RMSSD** (Root Mean Square of Successive Differences)
:   The square root of the mean squared differences between consecutive NN intervals. Primary marker of parasympathetic (vagal) activity. Most robust short-term metric.

**SDNN** (Standard Deviation of NN intervals)
:   Overall variability of the NN interval series. Reflects total autonomic modulation (both sympathetic and parasympathetic). Strongly influenced by recording length.

**pNN50** (Proportion of NN50)
:   Percentage of consecutive NN intervals differing by more than 50 ms. Correlates with RMSSD; reflects parasympathetic tone.

**Mean HR** (Mean Heart Rate)
:   Average heart rate in beats per minute (BPM), derived from NN intervals: `HR = 60000 / mean(NN)`.

**Mean NN**
:   Average NN interval in milliseconds.

---

## Frequency-Domain Metrics

**VLF** (Very Low Frequency)
:   Power in the 0.003–0.04 Hz band. Reflects thermoregulation and hormonal fluctuations. Requires recordings > 5 minutes.

**LF** (Low Frequency)
:   Power in the 0.04–0.15 Hz band. Reflects both sympathetic and parasympathetic modulation plus baroreflex activity. Not a pure sympathetic marker.

**HF** (High Frequency)
:   Power in the 0.15–0.4 Hz band. Primarily reflects parasympathetic (vagal) activity and respiratory sinus arrhythmia.

**LF/HF Ratio**
:   Ratio of LF to HF power. Previously interpreted as sympathovagal balance, this interpretation is now considered invalid (Quigley et al., 2024). Included for legacy compatibility.

---

## Nonlinear Metrics

**SD1** (Poincaré Plot)
:   Short-term variability from the Poincaré plot (width of the point cloud perpendicular to the line of identity). Mathematically related to RMSSD.

**SD2** (Poincaré Plot)
:   Long-term variability from the Poincaré plot (length of the point cloud along the line of identity). Related to SDNN.

---

## Quality & Artifacts

**Artifact**
:   An anomalous RR interval caused by measurement error, movement, or ectopic beats. Must be detected and corrected before analysis.

**Ectopic Beat**
:   A heartbeat originating from an abnormal location in the heart (premature atrial or ventricular contraction). Produces a short RR interval followed by a long one.

**Artifact Rate**
:   Percentage of detected artifacts relative to total beats. Critical quality indicator — segments with > 10% should be excluded.

**Quality Grade** (Quigley 2024)
:   A–D classification based on artifact rate. Grade A (< 2%): excellent; Grade B (2–5%): good; Grade C (5–10%): acceptable for time-domain only; Grade D (> 10%): exclude.

**Kubios Algorithm**
:   Artifact detection method by Lipponen & Tarvainen (2019). Classifies artifacts as extra beats, missed beats, or misaligned. Used in NeuroKit2's `signal_fixpeaks`.

---

## Application Concepts

**Section**
:   A time range defined by experimental events (e.g., "measurement_start" to "pause_start"). Used for protocol-based analysis.

**Segment**
:   A fixed-duration time window (e.g., 5 minutes) used for artifact detection and quality assessment. Generated automatically.

**Event Sequence**
:   The order of experimental conditions assigned to a participant (e.g., music → silence → music). Supports counterbalanced designs.

**Condition Label**
:   Human-readable name for a condition type (e.g., "condition_a" → "Relaxing Music").

**Canonical Event**
:   A standardized event name (e.g., `measurement_start`) that maps to various raw labels from recording devices (e.g., "Messung Start", "Begin recording").

**Project**
:   A folder containing configuration files (`config/*.yml`) and data. Projects keep settings isolated between studies.

---

## References

- Lipponen, J. A., & Tarvainen, M. P. (2019). A robust algorithm for heart rate variability time series artefact correction using novel beat classification. *Journal of Medical Engineering & Technology*, 43(3), 173–181.
- Quigley, K. S., et al. (2024). Guidelines for heart rate variability measurement and reporting. *Psychophysiology*.
- Task Force of ESC and NASPE (1996). Heart rate variability: Standards of measurement, physiological interpretation, and clinical use. *Circulation*, 93(5), 1043–1065.
- Quintana, D. S., et al. (2016). Guidelines for reporting articles on psychiatry and heart rate variability (GRAPH). *Translational Psychiatry*, 6(5), e803.
