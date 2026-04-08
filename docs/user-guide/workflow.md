# Complete Workflow Guide

This guide walks you through the entire RRational workflow — from opening the app to exporting publication-ready HRV results. Every step includes the exact clicks and settings.

---

!!! success "Recommended: Scientific Workflow"
    This workflow follows the **2024 Quigley et al. guidelines** and professor-reviewed best practices for HRV research:

    1. **Import** → Load data and verify participant detection
    2. **Inspect** → Visual tachogram review for each participant
    3. **Segment** → Time-based segmentation (5 min windows) for artifact detection
    4. **Detect** → Run artifact detection on **all validated sections** (same segments used for analysis)
    5. **Assess** → Per-segment quality grading — exclude segments with >10% artifacts
    6. **Analyze** → HRV metrics on clean, assessed segments
    7. **Report** → Always include: beat count, artifact rate, quality grade, and correction method

    This ensures **identical segments** for artifact detection and analysis, and **transparent quality reporting** as required by current guidelines.

---

## Step 1: Launch & Create a Project

### 1.1 Start RRational

Open a terminal and run:

```bash
uv run streamlit run src/rrational/gui/app.py
```

The app opens in your browser at [http://localhost:8501](http://localhost:8501).

<!-- screenshot: welcome-screen.png — Welcome screen with "Create New Project", "Open Existing", "Recent Projects" options -->

### 1.2 Create a New Project

1. Click **"Create New Project"**
2. Click **"Browse"** and select a folder (e.g., `Documents/HRV_Studies/`)
3. Enter a **project name** (e.g., `MyStudy`)
4. Optionally enter a description and author name
5. Under **Data Sources**, check the apps you used:
    - **HRV Logger** for CSV files
    - **VNS Analyse** for TXT files
6. Click **"Create Project"**

<!-- screenshot: create-project.png — Create project dialog with name, description, data source checkboxes -->

Your project folder is now created:

```
MyStudy/
├── project.rrational          # Project file
├── data/
│   ├── raw/
│   │   ├── hrv_logger/        # Put your CSV files here
│   │   └── vns/               # Put your TXT files here
│   └── processed/             # Saved events, exports
├── config/                    # Study configuration
└── analysis/                  # Analysis results
```

### 1.3 Copy Your Data Files

Copy your HRV recording files into the correct subfolder:

- **HRV Logger files** → `data/raw/hrv_logger/`
    - `*_RR_*.csv` (RR intervals)
    - `*_Events_*.csv` (event markers, optional)
- **VNS Analyse files** → `data/raw/vns/`
    - `*.txt` (single file per recording)

---

## Step 2: Import Data (Data Tab)

### 2.1 Load Recordings

1. Click **"Data"** in the sidebar
2. Verify the **Raw data directory path** points to your `data/raw/` folder
3. Click **"Analyze Folder"**
4. Wait for the scan to complete

<!-- screenshot: data-tab-loaded.png — Data tab showing "12 participants loaded", participant table with columns -->

### 2.2 Review Participants Overview

The **Participants Overview** table shows:

| Column | Meaning |
|--------|---------|
| **Participant** | Auto-extracted ID from filename |
| **CSV** | CSV import status |
| **Quality** | `[OK]` or warning indicators |
| **Saved** | `Y` if events have been saved |
| **App** | Recording app (HRV Logger / VNS Analyse) |
| **Device** | Recording device |
| **Files** | Number of RR/Events files |
| **Total Beats** | Total RR intervals in recording |
| **Duration (min)** | Recording length |

!!! warning "Check for issues"
    Look for warnings like:

    - "participant(s) with duplicate RR intervals" — normal for some HRV Logger versions, auto-handled
    - "participant(s) with no events detected" — check file naming or add events manually
    - "participant(s) with multiple files (merged)" — files were merged chronologically

### 2.3 Assign Groups (Optional)

If your study has groups (e.g., Control vs. Experimental):

1. Scroll down to **"Import Group/Sequence from CSV"**
2. Upload your study's master CSV with participant assignments
3. Map the columns: Participant ID, Group, Sequence
4. Click **"Apply Assignments"**

Alternatively, edit the **Group** column directly in the participants table.

---

## Step 3: Review Participants (Participants Tab)

### 3.1 Select a Participant

1. Click **"Participants"** in the sidebar
2. Select a participant from the **dropdown** at the top
3. The **tachogram** (RR interval plot) loads automatically

<!-- screenshot: participants-tachogram.png — Tachogram showing RR intervals over time with events as dashed lines -->

### 3.2 Understand the Tachogram

The tachogram shows RR intervals (milliseconds) over time. Key visual elements:

| Element | Appearance | Meaning |
|---------|------------|---------|
| Blue line | RR interval trace | Normal heart rhythm |
| Dashed vertical lines | Event markers | Recording events (measurement start, pause, etc.) |
| Red shading | Exclusion zones | Manually excluded time ranges |
| Gray shading | Time gaps | Missing data / recording interruptions |
| Orange markers | Artifacts | Detected ectopic/missed beats |
| Colored background | Condition sections | Repeating condition blocks |

### 3.3 Plot Options

Above the plot, enable/disable overlays using checkboxes:

- **Show events** — Vertical dashed lines at event timestamps
- **Show exclusions** — Red shading for excluded time ranges
- **Show condition sections** — Colored background for repeating conditions
- **Show condition events** — Individual event markers for conditions
- **Show artifacts** — Orange markers for detected artifacts
- **Show time gaps** — Gray shading for recording interruptions
- **Show variability segments** — Color-coded variability regions

<!-- screenshot: plot-options.png — Checkbox row showing all plot options -->

### 3.4 Navigate Between Participants

- Click **"Previous"** / **"Next"** buttons to move through participants
- Or select directly from the dropdown

---

## Step 4: Inspect & Clean (Signal Inspection)

!!! info "Why inspect before analysis?"
    Visual inspection is the **first step** in any HRV analysis pipeline. You need to identify artifacts, gaps, and noise before running statistical analyses. Skipping this step risks including corrupted data in your results.

### 4.1 Enter Signal Inspection Mode

1. In the Participants tab, find the **Mode** radio buttons
2. Select **"Signal Inspection"**

<!-- screenshot: signal-inspection-mode.png — Mode radio buttons with "Signal Inspection" selected -->

### 4.2 Configure Artifact Detection

Expand **"Detect New Artifacts"**:

1. **Method**: Select **"Lipponen 2019 (segmented)"** (recommended)
2. **Gap-adjacent beats**: Select **"Treat as segment boundaries"** (recommended)
3. **Detection Scope**: Choose one of:
    - **Full recording** — Detect across entire recording
    - **Selected section** — Detect within one section
    - **Custom time range** — Manual start/end times
    - **All validated sections** — Detect separately for each validated section (recommended)
4. **Segment Sizing**:
    - **Adaptive** (recommended) — Automatically determines optimal window size
    - **Preset** — Standard 350 beats/segment
    - **Manual** — Custom beats per segment

<!-- screenshot: artifact-detection-settings.png — Artifact detection expander showing method, scope, and sizing options -->

### 4.3 Run Detection

1. Click **"Run Detection"**
2. Review the results:
    - Artifact markers appear on the tachogram (orange dots)
    - Quality summary shows: artifact count, rate, and grade per segment
    - Segment assessment table with include/exclude checkboxes

<!-- screenshot: artifact-results.png — Tachogram with artifact markers and quality summary below -->

### 4.4 Per-Segment Quality Assessment

!!! success "Recommended Workflow"
    After detection, review quality **per segment**:

    - **Excellent** (<2% artifacts) — Include in analysis
    - **Good** (2-5% artifacts) — Include, apply correction
    - **Fair** (5-10% artifacts) — Include with caution, apply correction
    - **Poor** (>10% artifacts) — **Exclude from analysis** (Quigley 2024)

    Uncheck segments with >10% artifacts in the segment assessment table.

### 4.5 Save Artifact Corrections

1. Click **"Save Artifact Corrections"** in the sidebar
2. This creates a `.rrational` file in `data/processed/`
3. The file contains: corrected RR intervals, artifact indices, quality metrics

!!! tip "Export for Analysis"
    Click **"Export for Analysis"** to save a complete `.rrational` file with audit trail. This file can be loaded directly in the Analysis tab.

---

## Step 5: Configure Study (Setup Tab)

### 5.1 Define Events

1. Click **"Setup"** in the sidebar
2. Select the **"Events"** sub-tab
3. For each expected event:
    - Enter the **canonical name** (e.g., `measurement_start`)
    - Add **synonyms** for fuzzy matching (e.g., `Start Messung`, `Messung Anfang`)
    - Matching is case-insensitive

<!-- screenshot: setup-events.png — Events tab with canonical names and synonyms -->

!!! tip "Common event names"
    | Canonical Name | Typical Synonyms |
    |---------------|-----------------|
    | `measurement_start` | Start Messung, Messung Anfang |
    | `measurement_end` | Ende Messung, Messung Ende |
    | `pause_start` | Pause Start, Beginn Pause |
    | `pause_end` | Pause Ende, Ende Pause |
    | `rest_start` | Ruhe Start, Start Ruhe |

### 5.2 Define Groups

1. Select the **"Groups"** sub-tab
2. Click **"Create New Group"**
3. Enter a group name (e.g., `control`) and label (e.g., `Control Group`)
4. Repeat for each study group

### 5.3 Define Event Sequences (Optional)

For studies with repeating conditions (e.g., music randomization):

1. Select the **"Sequences"** sub-tab
2. Click **"Create New Event Sequence"**
3. Enter a sequence ID (e.g., `sequence_01`) and label
4. Enter the **condition order** as comma-separated values:
   ```
   condition_a, condition_b, condition_c
   ```
5. Create additional sequences with different orders for counterbalancing
6. Scroll down to **Condition Labels** to add display names and descriptions

<!-- screenshot: setup-sequences.png — Sequences tab with condition order and labels table -->

### 5.4 Define Sections

1. Select the **"Sections"** sub-tab
2. Define analysis sections with start/end events:

| Field | Example | Description |
|-------|---------|-------------|
| **Code** | `baseline` | Internal identifier |
| **Label** | `Baseline Rest` | Display name |
| **Start Event(s)** | `rest_start` | Comma-separated event names |
| **End Event(s)** | `rest_end, task_start` | First matching event ends the section |
| **Duration (min)** | `5` | Expected duration (for validation) |
| **Tolerance (min)** | `1` | Acceptable deviation from expected |

3. Click **"Save Section Changes"**

<!-- screenshot: setup-sections.png — Sections tab with data editor showing section definitions -->

---

## Step 6: Validate Sections (Participants Tab)

Before analysis, validate that sections are correctly detected for each participant.

### 6.1 Section Validation

1. Go to the **Participants** tab
2. Scroll down to **"Section Validation"**
3. Review each section:
    - **Green** = Valid (start and end events found, duration within tolerance)
    - **Yellow** = Needs attention (multiple candidates, disambiguation required)
    - **Red** = Invalid (missing events, duration mismatch)

<!-- screenshot: section-validation.png — Section validation panel showing valid/invalid sections -->

### 6.2 Disambiguate Events

If a section shows "multiple events found":

1. Select the correct **start event** from the dropdown
2. Select the correct **end event** from the dropdown
3. Verify the duration matches your expectation

### 6.3 Save Validations

1. Click **"Save"** next to the validation results
2. This stores your disambiguation choices for reproducibility

---

## Step 7: Analyze HRV (Analysis Tab)

### 7.1 Choose Analysis Mode

1. Click **"Analysis"** in the sidebar
2. Select an **Analysis Mode**:

| Mode | Use Case |
|------|----------|
| **Single Participant** | Analyze one participant's sections |
| **Repeating Section Analysis** | Protocol-based repeating condition comparison |
| **Group Analysis** | Batch comparison across study groups |

<!-- screenshot: analysis-mode.png — Analysis tab with mode selector -->

### 7.2 Single Participant Analysis

1. Select **"Single Participant"**
2. Choose a participant from the dropdown
3. All **validated sections** are pre-selected (you can deselect if needed)
4. Optionally expand **"Artifact Correction"** to enable Kubios correction
5. Choose analysis mode:
    - **Aggregated** — One result per section (combines all windows)
    - **Per-segment** — Results for each time-based segment within a section
6. Click **"Analyze HRV"**

<!-- screenshot: analysis-single-results.png — Analysis results with metrics table and plots -->

### 7.3 Understanding Results

The results table shows:

| Metric | Domain | Description |
|--------|--------|-------------|
| **RMSSD** | Time | Root mean square of successive differences (ms) — parasympathetic marker |
| **SDNN** | Time | Standard deviation of NN intervals (ms) — overall variability |
| **pNN50** | Time | Percentage of successive intervals differing >50 ms |
| **Mean HR** | Time | Average heart rate (bpm) |
| **LF** | Frequency | Low-frequency power (0.04-0.15 Hz, ms²) |
| **HF** | Frequency | High-frequency power (0.15-0.4 Hz, ms²) — parasympathetic |
| **LF/HF** | Frequency | Ratio — **not** "sympathovagal balance" (Quigley 2024) |
| **SD1** | Nonlinear | Poincaré plot short-term variability |
| **SD2** | Nonlinear | Poincaré plot long-term variability |

### 7.4 Diagnostic Plots

RRational generates four diagnostic plots:

1. **Tachogram** — RR intervals over time with event markers
2. **Poincaré Plot** — RR(n) vs RR(n+1) with SD1/SD2 ellipse
3. **Frequency Spectrum** — Power spectral density with LF/HF bands
4. **HR Distribution** — Heart rate histogram

<!-- screenshot: analysis-plots.png — Four analysis plots in a 2x2 grid -->

### 7.5 Group Analysis

1. Select **"Group Analysis"**
2. Choose groups to compare
3. Select sections and metrics
4. Click **"Run Group Analysis"**
5. Results show: group means, standard deviations, and comparison charts

### 7.6 Download Results

Click **"Download HRV Results (CSV)"** to export:

- One row per participant per section
- All computed HRV metrics
- Quality indicators (beat count, artifact rate, grade)
- Ready for R, SPSS, Python, or Excel

---

## Step 8: Report Your Results

!!! success "Publication Checklist (Quigley 2024)"
    When reporting HRV results, always include:

    - [ ] Recording device and app used
    - [ ] Recording duration per condition
    - [ ] Artifact detection method (e.g., "Lipponen & Tarvainen 2019")
    - [ ] Artifact correction method (e.g., "Kubios algorithm via NeuroKit2")
    - [ ] Artifact rate per condition (mean ± SD)
    - [ ] Number of excluded segments and exclusion criteria
    - [ ] Beat count per condition
    - [ ] Segment duration and overlap settings
    - [ ] Which HRV metrics and why (justify LF/HF interpretation!)

---

## Keyboard Shortcuts

| Key | Action | Context |
|-----|--------|---------|
| `R` | Refresh/rerun app | Anywhere |
| `C` | Clear cache | Anywhere |
| `I` | Toggle inspection zoom | Signal Inspection mode |
| `Arrow Left/Right` | Pan zoomed view | Signal Inspection zoom |

---

## Troubleshooting

### "No data loaded"

- Check files are in the correct `data/raw/` subfolder
- Verify filenames contain a recognizable participant ID
- Adjust the ID pattern in Import Settings

### "Section not detected"

- Check that events are mapped to canonical names (Setup > Events)
- Verify both start AND end events exist for the participant
- Click "Save" after adding events

### "No validated sections found"

- Go to Participants tab → Section Validation
- Ensure sections show as "valid" (green)
- Click "Save" to persist validation results

### Slow performance

- Reduce plot resolution in Settings (sidebar)
- Close other browser tabs
- Consider analyzing one participant at a time

For installation issues, see [Installation Guide](../getting-started/installation.md#troubleshooting).
