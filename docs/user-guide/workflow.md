# Complete Workflow

This guide covers the full RRational workflow in detail — from data import to publication-ready results.

---

## Overview

```
Import Data → Review & Clean → Configure Study → Analyze → Export
   (Data)      (Participants)      (Setup)       (Analysis)
```

RRational's four tabs map directly to this workflow.

---

## Step 1: Import Data

### Supported Formats

| App | Files | Where to Put Them |
|-----|-------|-------------------|
| HRV Logger | `*_RR_*.csv` + `*_Events_*.csv` | `data/raw/hrv_logger/` |
| VNS Analyse | `*.txt` | `data/raw/vns/` |

See [Data Formats](data-formats.md) for detailed file specifications.

### Participant ID Extraction

RRational extracts participant IDs from filenames using regex patterns:

| Pattern | Example Match | Description |
|---------|---------------|-------------|
| `\d{4}[A-Z]{4}` | `0001CTRL` | 4 digits + 4 uppercase letters (default) |
| `\d{4}[A-Za-z]{4,5}` | `0001Taste` | 4 digits + 4-5 mixed-case letters |
| Custom regex | Your pattern | Configurable in Import Settings |

### Loading Data

1. Go to the **Data** tab
2. Verify the raw data directory path
3. Click **"Analyze Folder"**
4. The Participants Overview table shows all detected participants

!!! warning "Duplicate RR intervals"
    Some HRV Logger versions record duplicate timestamps. RRational detects and reports these automatically. They are removed during analysis.

---

## Step 2: Review & Clean (Participants Tab)

### Interaction Modes

Switch between modes using the **Mode** radio buttons:

| Mode | Purpose | How |
|------|---------|-----|
| **View Events** | Inspect detected events | Events shown as dashed vertical lines |
| **Add Events** | Add missing event markers | Click on the plot at the desired timestamp |
| **Add Exclusions** | Exclude bad data segments | Click two points to define start/end |
| **Signal Inspection** | Detailed artifact analysis | See below |

### Signal Inspection

Signal Inspection mode provides artifact detection and quality assessment:

1. Expand **"Detect New Artifacts"**
2. Choose detection method (Lipponen 2019 recommended)
3. Select **scope**: Full recording, Selected section, or All validated sections
4. Click **"Run Detection"**
5. Review artifact markers on the plot
6. Check the quality grade per segment

!!! info "Artifact Correction"
    RRational uses NeuroKit2's implementation of the **Kubios algorithm** for artifact correction. This corrects ectopic beats, missed beats, and extra detections while preserving the original data.

### Saving Your Work

- Click **"Save"** in the sidebar to persist changes
- **"Export for Analysis"** creates a `.rrational` file with full audit trail

---

## Step 3: Configure Study (Setup Tab)

### Events

Define canonical event names and synonyms for automatic matching:

- **Canonical name**: The standardized event name (e.g., `measurement_start`)
- **Synonyms**: Alternative names that should match (e.g., `Start Messung`, `Messung Anfang`)
- Matching is case-insensitive and uses fuzzy matching

### Groups

Create study groups to organize participants:

- Define groups (e.g., `control`, `experimental`)
- Assign participants to groups in the Data tab
- Select which sections each group should use

### Event Sequences

Define repeating condition orders for randomization studies:

- Create sequences with ordered condition lists (e.g., `condition_a → condition_b → condition_c`)
- Assign participants to sequences
- Used in **Repeating Section Analysis** and **Generate Repetitive Events**

### Sections

Define analysis time windows using event boundaries:

- **Start event(s)**: One or more events that mark the section start
- **End event(s)**: One or more events that mark the section end
- **Expected duration**: For validation (with tolerance)
- Sections are validated per-participant in the Participants tab

---

## Step 4: Analyze (Analysis Tab)

### Analysis Modes

| Mode | Use Case |
|------|----------|
| **Single Participant** | Analyze one participant's sections individually |
| **Repeating Section Analysis** | Protocol-based repeating condition analysis |
| **Group Analysis** | Batch comparison across study groups |

### HRV Metrics

| Domain | Metrics | Min. Requirements |
|--------|---------|-------------------|
| **Time** | RMSSD, SDNN, pNN50, Mean HR, Mean RR | 100 beats |
| **Frequency** | LF, HF, VLF, LF/HF, Total Power | 300 beats, ~5 min |
| **Nonlinear** | SD1, SD2, SD1/SD2 | 100 beats |

### Segment Sizing

For longer recordings, RRational divides data into overlapping windows:

- **Adaptive** (recommended): Automatically determines optimal window size
- **Preset**: Standard 5-minute windows
- **Manual**: Custom window size and overlap

### Artifact Correction

Enable artifact correction for recordings with 2-10% artifact rates:

- Uses NeuroKit2 Kubios algorithm
- Corrects ectopic, missed, and extra beats
- Original data is preserved (correction is non-destructive)

!!! warning "High artifact rates"
    Recordings with >10% artifacts should be excluded from analysis (Quigley et al., 2024). RRational flags these automatically.

---

## Step 5: Export Results

### CSV Export

Click **"Download HRV Results (CSV)"** in the Analysis tab for:

- Per-section HRV metrics
- Quality indicators (beat count, artifact rate, grade)
- Ready for import into R, SPSS, or Python

### Ready for Analysis Export

From the Participants tab sidebar:

- Saves as `.rrational` YAML file
- Includes: corrected RR intervals, artifact indices, quality metrics
- Full audit trail: detection method, parameters, exclusion zones
- Can be reloaded in the Analysis tab for reproducible results

---

## Tips & Best Practices

### Scientific Guidelines (Quigley 2024)

| Metric | Max Artifact Rate | Min Beats | Min Duration |
|--------|-------------------|-----------|--------------|
| RMSSD, SDNN | ~36% | 100 | — |
| pNN50 | ~4% | 100 | — |
| HF, LF, LF/HF | ~2% | 300 | ~5 min |

### Recommended Workflow

1. **Visual inspection** — Always review the tachogram before analysis
2. **Check artifacts** — Use Signal Inspection mode
3. **Exclude problems** — Define exclusion zones for bad segments
4. **Use correction** — Enable artifact correction for 2-10% artifact rates
5. **Report metrics** — Always note beat count and artifact rate in publications

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `R` | Rerun app (refresh) |
| `C` | Clear cache |
| `I` | Toggle inspection zoom (in Signal Inspection mode) |
| `Arrow keys` | Pan left/right (in inspection zoom) |

---

## Troubleshooting

### "No data loaded"

- Check files are in the correct `data/raw/` subfolder
- Verify file format matches the expected pattern
- Check Import Settings → ID pattern

### "Section not detected"

- Verify events are mapped to canonical names (Events tab)
- Check that start and end events exist for the participant
- Ensure events are saved (click "Save" in sidebar)

### Performance Issues

- Reduce plot resolution in Settings
- Close other browser tabs
- Use "Analyze Folder" once, then work with loaded data

For more troubleshooting, see [Installation Guide](../getting-started/installation.md#troubleshooting).
