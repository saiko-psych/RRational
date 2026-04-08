# Complete Workflow Guide

This guide walks you through every step of the RRational workflow — from opening the app to exporting publication-ready HRV results.

---

!!! success "Recommended: Scientific Workflow (Quigley 2024)"
    This workflow follows professor-reviewed best practices:

    1. **Import** → Load data and verify participant detection
    2. **Inspect** → Visual tachogram review for each participant
    3. **Segment** → Time-based segmentation (5 min windows)
    4. **Detect** → Run artifact detection on **all validated sections**
    5. **Assess** → Per-segment quality grading — exclude segments with >10% artifacts
    6. **Analyze** → HRV metrics on clean, assessed segments
    7. **Report** → Always include: beat count, artifact rate, quality grade

---

## Step 1: Launch & Create a Project

### 1.1 Start RRational

```bash
uv run streamlit run src/rrational/gui/app.py
```

The app opens at [http://localhost:8501](http://localhost:8501). You'll see the Data tab as the landing page.

![The Data tab is the landing page. The sidebar (left) shows navigation buttons for all four tabs: Data, Participants, Setup, and Analysis. At the bottom of the sidebar you'll find Settings, Documentation link, Report a Bug button, and the current version number.](../assets/screenshots/01-data-top.png)

*The screenshot above shows the main interface. Notice the **sidebar** on the left with four navigation buttons (Data, Participants, Setup, Analysis). Below them you can see the project indicator ("Temporary Workspace"), participant count, and at the bottom: Settings, Documentation, Report a Bug, and version info.*

### 1.2 Create a Project

On the Welcome Screen (or via "Open Project" in the sidebar), click **"Create New Project"**:

1. Click **"Browse"** → choose a folder (e.g., `Documents/HRV_Studies/`)
2. Enter a **project name** (e.g., `MyStudy`)
3. Optionally add description and author name
4. Select **data sources**: HRV Logger, VNS Analyse, or both
5. Click **"Create Project"**

Your project folder:

```
MyStudy/
├── project.rrational          # Project file (YAML)
├── data/
│   ├── raw/
│   │   ├── hrv_logger/        # Your CSV files go here
│   │   └── vns/               # Your TXT files go here
│   └── processed/             # Saved events, exports
├── config/                    # Study configuration
└── analysis/                  # Analysis results
```

!!! tip "Copy your data first"
    Copy your HRV recording files into the appropriate `data/raw/` subfolder **before** loading data in the app.

---

## Step 2: Import Data (Data Tab)

### 2.1 Load Recordings

1. In the **Data** tab, verify the **Raw data directory path** points to your project's `data/raw/` folder
2. Click **"Analyze Folder"**
3. Wait for the scan to complete

### 2.2 Review Participants Overview

After loading, the **Participants Overview** appears with a summary of all detected participants:

![The Participants Overview shows a success message ("All 12 participants look good!") and a table listing every participant. Each row shows: Participant ID, CSV import status, Quality indicator, whether data has been Saved, the recording App and Device, number of Files, Total Beats, Retained beats, Duplicates, Artifact percentage, and Duration in minutes.](../assets/screenshots/03-data-participants-overview.png)

*Look at the table columns: **Participant** (auto-extracted ID), **Quality** ([OK] or warnings), **App** (HRV Logger or VNS Analyse), **Total Beats**, and **Duration**. This gives you an immediate overview of your dataset quality.*

![Scrolling down reveals the full participant table. You can edit the Group column directly in this table to assign participants to study groups. Below the table are "Download Participants CSV" and "Import Group/Sequence from CSV" buttons.](../assets/screenshots/04-data-participants-table.png)

*The table is interactive — you can sort by clicking column headers, and edit the **Group** column directly. The **CSV** column shows which participants have been imported from a master CSV file.*

### 2.3 Import Group Assignments (Optional)

If you have a CSV file with group/sequence assignments:

1. Click **"Import Group/Sequence from CSV"**
2. Define **value labels** for your group and sequence columns
3. Upload your CSV file
4. Map the columns (Participant ID, Group, Sequence)
5. Click **"Apply Assignments"**

![The CSV import section lets you upload a study master CSV. On the left, define Group Value Labels (e.g., value "5" means "MAR"). On the right, define Sequence Value Labels. Below, specify which CSV columns map to Participant ID, Group, and Sequence.](../assets/screenshots/05-data-csv-import.png)

---

## Step 3: Review Participants (Participants Tab)

Click **"Participants"** in the sidebar to switch to the Participants tab.

### 3.1 Participant Header

The top of the Participants tab shows participant details at a glance:

![The participant header shows a dropdown to select a participant (e.g., "0001CTRL"), Previous/Next navigation buttons, and a summary line showing Group, Randomization, and position in the list (e.g., "1 of 12"). Below are four metric cards: Total Beats (6577), Retained (6577), Duplicates (0), and Duration (106.0 min).](../assets/screenshots/07-participants-metrics.png)

*The four metric cards give you an immediate sense of the recording quality. **Total Beats** vs **Retained** shows if any beats were removed. **Duplicates** should ideally be 0. **Duration** tells you the total recording length.*

### 3.2 Interaction Modes

Below the header, you'll see three mode buttons and the plot options:

![The mode selector offers three options: "Add Events" (click plot to add markers), "Add Exclusions" (click two points to exclude a time range), and "Signal Inspection" (detailed artifact analysis). Below are Plot Options checkboxes for toggling overlays.](../assets/screenshots/08-participants-mode-selector.png)

### 3.3 Plot Options

The checkboxes control what's visible on the tachogram:

![Plot Options shows six checkboxes: "Show events" (event markers), "Show condition sections" (colored backgrounds for repeating conditions), "Show artifacts" (orange markers), "Show time gaps" (gray shading), "Show exclusions" (red shading), and "Show condition events" (individual event markers). On the right is a Gap threshold slider.](../assets/screenshots/09-participants-plot-options.png)

*Enable **Show artifacts** to see artifact markers and access the artifact detection tools. Enable **Show condition sections** to see repeating experimental conditions as colored background regions.*

### 3.4 The Tachogram

The tachogram is the main visualization — it shows RR intervals (milliseconds) over time:

![The tachogram plot shows RR intervals on the Y-axis (in ms, typically 800-1100ms) and time on the X-axis. The blue line traces the heart rhythm. Vertical dashed lines mark events (measurement start, pause, etc.). Orange dots indicate detected artifacts. The plot title shows "Tachogram - 0001CTRL" and a legend identifies "RR Intervals".](../assets/screenshots/10-participants-tachogram.png)

*Key things to look for in the tachogram:*

- ***Blue line pattern***: Should show regular oscillations (respiratory sinus arrhythmia). Flat lines or sudden jumps indicate artifacts.
- ***Vertical dashed lines***: These are events (measurement start, pause, etc.)
- ***Orange dots***: Detected artifacts — ectopic beats, missed beats, or noise
- ***Overall stability***: Large changes in baseline suggest movement or position changes

---

## Step 4: Artifact Detection (Signal Inspection)

!!! info "Why artifacts matter"
    Even a small number of artifacts can dramatically distort HRV metrics. The 2024 Quigley guidelines specify maximum artifact rates for each metric type. Always detect and assess artifacts before analysis.

### 4.1 Enable Artifact Display

1. Check the **"Show artifacts"** checkbox in Plot Options
2. This reveals the **"Detect New Artifacts"** expander below the plot

![After enabling "Show artifacts", the tachogram shows artifact markers as orange dots overlaid on the RR interval trace. Upward-pointing triangles mark ectopic beats, downward triangles mark missed beats. A yellow info bar reminds you to run detection if none has been saved yet.](../assets/screenshots/11-participants-tachogram-artifacts.png)

### 4.2 Configure Detection

Expand **"Detect New Artifacts"** to see the detection settings:

![The artifact detection panel shows: Method selector (Lipponen 2019 segmented, recommended), Gap-adjacent beats handling (Treat as segment boundaries, recommended), Detection Scope with four options (Full recording, Selected section, Custom time range, All validated sections), a section selector dropdown, and Segment Sizing options (Adaptive recommended, Preset, Manual).](../assets/screenshots/12-artifact-detection-expander.png)

*The key settings:*

- **Method**: "Lipponen 2019 (segmented)" is recommended — it's the current gold standard
- **Detection Scope**: Choose **"All validated sections"** to run detection separately for each study section (recommended for the scientific workflow)
- **Segment Sizing**: "Adaptive" automatically calculates optimal segment size

### 4.3 Detection Scope Options

The Detection Scope determines which part of the recording is analyzed:

![The Detection Scope radio buttons show all four options vertically: "Full recording" (entire recording), "Selected section" (one specific section), "Custom time range" (manual start/end), and "All validated sections" (recommended — processes each validated section separately). Below is a section dropdown and time range display.](../assets/screenshots/13-artifact-detection-scope.png)

*Use **"All validated sections"** for the recommended scientific workflow. This ensures the same segments are used for both artifact detection and analysis.*

### 4.4 Run Detection & Review Results

Click **"Run Detection"** and wait for the results:

![After running detection, the results panel shows detection statistics and a segment quality table. Each segment shows its artifact count, artifact rate percentage, and quality grade (Excellent, Good, Fair, or Poor). Include/exclude checkboxes let you remove poor-quality segments.](../assets/screenshots/14-artifact-detection-results.png)

![Further down, the segment quality assessment shows detailed per-segment information. Segments with >10% artifacts are flagged as "Poor" and should be excluded from analysis.](../assets/screenshots/15-artifact-segment-quality.png)

!!! success "Quality Grading (Quigley 2024)"
    | Grade | Artifact Rate | Action |
    |-------|--------------|--------|
    | **Excellent** | <2% | Include as-is |
    | **Good** | 2-5% | Include, apply correction |
    | **Fair** | 5-10% | Include with caution |
    | **Poor** | >10% | **Exclude from analysis** |

### 4.5 Save Results

Click **"Save Artifact Corrections"** in the sidebar to persist your artifact detection results.

---

## Step 5: Section Validation (Participants Tab)

Scroll down in the Participants tab to find **Section Validation**:

![The Section Validation panel shows each defined section with its validation status. For each section you can see: the section name and label, the time range (start and end timestamps), the RR duration, and whether the expected duration matches. Valid sections show green indicators, sections with issues show warnings.](../assets/screenshots/16-section-validation.png)

*The validation checks that:*

- *Both start and end events exist for the participant*
- *The actual duration is within the expected tolerance*
- *The RR interval sum matches the event-based duration*

![Below the section list, the Data Integrity Check compares Event Duration (from event timestamps) with RR+Gap Duration (from summing RR intervals and gaps). The Difference column shows the mismatch. Small differences (<1%) are normal.](../assets/screenshots/17-section-validation-details.png)

*The **Data Integrity Check** is important: it verifies that the sum of RR intervals plus gaps matches the event-based duration. Large mismatches (>1%) indicate data problems.*

### 5.1 Event Mapping

Below validation, the **Event Mapping Status** shows which expected events were found:

![The Event Mapping Status table lists each expected event (e.g., pause_end, pause_start, rest_pre_start) with its Status (Found/Missing) and the Raw Label from the recording (e.g., "Pause Ende", "Start Ruhe"). Missing events prevent sections from being validated.](../assets/screenshots/18-events-mapping.png)

*Green "Found" means the event was automatically matched. Red "Missing" means you need to add the event manually or update your event synonyms in the Setup tab.*

---

## Step 6: Configure Study (Setup Tab)

Click **"Setup"** in the sidebar. The Setup tab has four sub-tabs.

### 6.1 Events

Define canonical event names and their synonyms for automatic matching:

![The Events sub-tab shows "Event Mapping" with a table of event definitions. Each row has a canonical name (e.g., "measurement_start"), synonyms for fuzzy matching, and a regex pattern. The "Create New Event" expander lets you add new event definitions.](../assets/screenshots/20-setup-events-top.png)

![The event definition table is editable. You can add synonyms (comma-separated) for each canonical event name. Events are matched case-insensitively. Below the table is a "Save Event Changes" button.](../assets/screenshots/21-setup-events-table.png)

### 6.2 Groups

Click the **"Groups"** radio button to define study groups:

![The Groups sub-tab lets you create study groups (e.g., "control", "experimental"). Each group has a name, label, and a list of events that should be present for participants in that group.](../assets/screenshots/22-setup-groups.png)

### 6.3 Event Sequences

Click **"Sequences"** to define repeating condition orders:

![The Sequences sub-tab shows "Event Sequences (Condition Randomization)". A help expander explains the concept. Below is "Create New Event Sequence" where you enter a sequence ID, label, and comma-separated condition order (e.g., "condition_a, condition_b, condition_c").](../assets/screenshots/23-setup-sequences-top.png)

![Scrolling down shows the list of existing event sequences. Each sequence can be expanded to edit its label and condition order. The "Condition Order" is displayed as arrows (e.g., "music_1 → music_2 → music_4 → music_3"). Participants assigned to each sequence are listed.](../assets/screenshots/24-setup-sequences-list.png)

![At the bottom of the Sequences sub-tab, the Condition Labels table lets you define display names and descriptions for each condition code. For example, "music_1" can be labeled "Bach" with description "Brandenburgische Konzerte Bach". These labels appear in exports and the analysis results.](../assets/screenshots/25-setup-condition-labels.png)

### 6.4 Sections

Click **"Sections"** to define analysis time windows:

![The Sections sub-tab provides an editable table where you define analysis sections. Each section has a Code (internal name), Label (display name), Start Event(s) and End Event(s) (comma-separated for multiple), expected Duration in minutes, and Tolerance in minutes.](../assets/screenshots/26-setup-sections.png)

*Each section is defined by start/end events. You can specify multiple events (comma-separated) — the first matching event will be used.*

---

## Step 7: Analyze HRV (Analysis Tab)

Click **"Analysis"** in the sidebar.

### 7.1 Choose Analysis Mode

![The Analysis tab offers three modes via radio buttons: "Single Participant" (analyze one participant's sections), "Repeating Section Analysis" (protocol-based repeating condition comparison), and "Group Analysis" (batch comparison across study groups).](../assets/screenshots/27-analysis-mode-selection.png)

### 7.2 Single Participant Analysis

![In Single Participant mode, select a participant from the dropdown. All validated sections are pre-selected in the multiselect. Below is an "Artifact Correction" expander for enabling Kubios correction, and analysis mode options (Aggregated vs Per-segment).](../assets/screenshots/28-analysis-single-settings.png)

*The **section multiselect** defaults to all validated sections for the selected participant. You can deselect sections you want to skip.*

### 7.3 Repeating Section Analysis

![Repeating Section Analysis mode adds Protocol Settings (expected duration, section length, pre/post pause sections). Below, the participant selector shows the assigned event sequence and condition order. A warning appears if no sequence is assigned.](../assets/screenshots/29-analysis-repeating-top.png)

![The protocol settings include: expected total duration, section length, number of pre/post-pause sections, minimum valid section duration and beats, and a duration mismatch handling strategy (Flag only, Strict, or Proportional).](../assets/screenshots/30-analysis-repeating-settings.png)

### 7.4 Group Analysis

![Group Analysis mode lets you select groups to compare, choose sections, and run batch analysis across all participants in the selected groups. Results include group means, standard deviations, and comparison charts.](../assets/screenshots/31-analysis-group.png)

### 7.5 Understanding Results

After clicking **"Analyze HRV"**, the results include:

| Metric | Domain | What It Tells You |
|--------|--------|-------------------|
| **RMSSD** | Time | Beat-to-beat variability — primary parasympathetic marker |
| **SDNN** | Time | Overall HRV — reflects all sources of variability |
| **pNN50** | Time | Percentage of large beat-to-beat changes |
| **Mean HR** | Time | Average heart rate in beats per minute |
| **LF** | Frequency | Low-frequency power (0.04-0.15 Hz) |
| **HF** | Frequency | High-frequency power (0.15-0.4 Hz) — parasympathetic |
| **LF/HF** | Frequency | Ratio — **not** "sympathovagal balance" (Quigley 2024) |
| **SD1** | Nonlinear | Short-term variability (Poincare) |
| **SD2** | Nonlinear | Long-term variability (Poincare) |

---

## Step 8: Export & Save

### 8.1 Export for Analysis

In the Participants tab sidebar, click **"Export for Analysis"**:

![The "Export for Analysis" expander at the bottom of the page lets you save a .rrational file containing corrected RR intervals, artifact indices, quality metrics, and a full audit trail. This file can be reloaded in the Analysis tab for reproducible results.](../assets/screenshots/19-export-for-analysis.png)

### 8.2 Download CSV

In the Analysis tab, click **"Download HRV Results (CSV)"** to export:

- One row per participant per section
- All computed HRV metrics
- Quality indicators (beat count, artifact rate, grade)
- Ready for R, SPSS, Python, or Excel

---

## Sidebar Reference

The sidebar provides quick access to all navigation and tools:

![The sidebar shows: navigation buttons (Data, Participants, Setup, Analysis — the active tab is highlighted in a darker shade), project indicator with "Switch Project" button, participant count, render time, Settings expander, "Documentation" link button (opens ReadTheDocs), "Report a Bug" link button (opens GitHub Issues), and version number with git commit hash.](../assets/screenshots/33-sidebar-bottom.png)

---

## Publication Checklist

!!! success "Required Information for HRV Papers (Quigley 2024)"
    When reporting HRV results, always include:

    - [ ] Recording device and app used
    - [ ] Recording duration per condition
    - [ ] Artifact detection method (e.g., "Lipponen & Tarvainen 2019")
    - [ ] Artifact correction method (e.g., "Kubios algorithm via NeuroKit2")
    - [ ] Artifact rate per condition (mean +/- SD)
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
| `Left/Right` | Pan zoomed view | Signal Inspection zoom |

---

## Troubleshooting

### "No data loaded"

- Check files are in the correct `data/raw/` subfolder
- Verify filenames contain a recognizable participant ID
- Adjust the ID pattern in Import Settings

### "Section not detected"

- Check events are mapped in Setup > Events
- Verify both start AND end events exist for the participant
- Click "Save" in the sidebar after changes

### "No validated sections found"

- Go to Participants tab > Section Validation
- Ensure sections show as valid
- Click "Save" to persist validation results

### Slow performance

- Reduce plot resolution in Settings
- Close other browser tabs
- Analyze one participant at a time for large datasets

For installation issues, see [Installation Guide](../getting-started/installation.md#troubleshooting).
