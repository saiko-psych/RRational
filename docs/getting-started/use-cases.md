# When to Use RRational

RRational is designed for researchers who collect heart rate variability (HRV) data using mobile recording apps and need a reliable, transparent way to analyze it. If any of the following scenarios apply to you, RRational can help.

---

## Who Is This For?

### Researchers with HRV Recording Data

You recorded RR intervals using **HRV Logger** (iOS/Android) or **VNS Analyse** (iOS) and need to:

- Clean and inspect your data visually
- Detect and correct artifacts
- Analyze HRV metrics per experimental condition
- Compare metrics across participants or groups
- Export publication-ready results

### Students Working on HRV Projects

You're working on a thesis or course project involving HRV data and need:

- A free alternative to Kubios HRV (no license costs)
- Step-by-step guidance through the analysis pipeline
- Scientific best practices built into the tool
- Transparent, reproducible results

### Anyone Who Wants a Free Kubios Alternative

Kubios HRV is the gold standard but requires a paid license. RRational provides comparable functionality for common research workflows — for free.

---

## Research Scenarios

### Music & Emotion Studies

The original use case for RRational. Your study involves:

- Participants listening to different music pieces in randomized order
- Each condition lasts a fixed duration (e.g., 5 minutes)
- You want to compare HRV metrics between music conditions
- Multiple randomization sequences for counterbalancing

**RRational features for this**: Event sequences, repeating section analysis, condition-based grouping, per-section HRV metrics.

### Stress & Relaxation Research

Your study measures physiological stress responses:

- Baseline → Stress task → Recovery phases
- You need to compare HRV between phases
- Multiple measurement sessions per participant

**RRational features for this**: Section definitions with event boundaries, expected duration validation, group-level comparison.

### Clinical HRV Monitoring

You collect HRV data in clinical settings:

- Long recordings (60-120+ minutes)
- Need to identify and exclude artifact-heavy segments
- Quality assessment is critical for publication

**RRational features for this**: Time-based segmentation, per-segment quality grading (Quigley 2024), artifact correction, exclusion zones.

### Repeated-Measures Designs

Any study with repeating experimental conditions:

- Condition A → Condition B → Condition C → (repeat)
- Fixed intervals between conditions
- Counterbalanced order across participants

**RRational features for this**: Event sequences with condition order, repeating section analysis, automatic condition assignment.

---

## What You Need

| Requirement | Details |
|-------------|---------|
| **HRV data** | CSV files from HRV Logger or TXT files from VNS Analyse |
| **Computer** | Windows, macOS, or Linux |
| **Python** | Version 3.11, 3.12, or 3.13 |
| **Time** | ~10 minutes for setup, ~5 minutes per participant for analysis |

---

## What RRational Does NOT Do

- **R-peak detection from raw ECG/PPG** — RRational works with pre-detected RR intervals, not raw physiological signals
- **Real-time monitoring** — RRational is for post-hoc analysis, not live data
- **Advanced nonlinear analysis** — DFA, sample entropy, and multiscale entropy are not yet implemented
- **Automated report generation** — Results are exported as CSV; you write the report

---

## Next Steps

Ready to get started?

1. [Install RRational](installation.md)
2. [Follow the Quick Start Guide](quickstart.md)
3. [Read the Complete Workflow](../user-guide/workflow.md)
