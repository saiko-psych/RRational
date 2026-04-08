# Quick Start Guide

This guide walks you through your first HRV analysis with RRational.

---

## 1. Launch RRational

```bash
uv run streamlit run src/rrational/gui/app.py
```

The app opens at [http://localhost:8501](http://localhost:8501).

!!! tip "Demo Mode"
    Try RRational without your own data:
    ```bash
    uv run streamlit run src/rrational/gui/app.py -- --test-mode
    ```

## 2. Create a Project

On the Welcome Screen, click **"Create New Project"**:

1. Choose a folder (e.g., `Documents/HRV_Studies/`)
2. Enter a project name (e.g., `MyStudy`)
3. Select your data sources (HRV Logger, VNS Analyse, or both)
4. Click **"Create Project"**

This creates an organized folder:

```
MyStudy/
├── project.rrational          # Project metadata
├── data/
│   ├── raw/
│   │   ├── hrv_logger/        # Your HRV Logger CSV files
│   │   └── vns/               # Your VNS Analyse TXT files
│   └── processed/             # Exported files and saved events
├── config/                    # Study configuration
└── analysis/                  # Analysis results
```

!!! note "Already have data?"
    Copy your HRV files into the appropriate `data/raw/` subfolder before proceeding.

## 3. Import Data

1. Go to the **Data** tab
2. Verify the data path points to your `data/raw/` folder
3. Click **"Analyze Folder"**
4. Review the participant overview table

RRational extracts participant IDs from filenames using patterns (default: 4 digits + 4 letters, e.g., `0001CTRL`). Adjust in **Import Settings** if needed.

## 4. Review & Clean

1. Go to the **Participants** tab
2. Select a participant from the dropdown
3. Review the **tachogram** (RR interval plot)
4. Switch to **Signal Inspection** mode for artifact detection

**Plot options** (checkboxes above the plot):

| Option | Shows |
|--------|-------|
| Show events | Vertical dashed lines at event timestamps |
| Show exclusions | Red shading for excluded time ranges |
| Show condition sections | Colored background for repeating conditions |
| Show artifacts | Orange markers for detected artifacts |
| Show time gaps | Gray shading for recording interruptions |

## 5. Configure Study

Use the **Setup** tab to define your study structure:

| Sub-tab | Purpose |
|---------|---------|
| **Events** | Define expected events and synonyms for fuzzy matching |
| **Groups** | Create study groups (Control, Experimental, etc.) |
| **Sequences** | Define repeating condition orders for randomization |
| **Sections** | Define analysis sections (Baseline, Task, Recovery) |

**Example section definition**:

- Name: `baseline`
- Start event: `rest_start`
- End event: `rest_end`
- Expected duration: 5 minutes (±1 min tolerance)

## 6. Run Analysis

1. Go to the **Analysis** tab
2. Select **Single Participant** or **Group Analysis**
3. Choose section(s) to analyze
4. Enable **artifact correction** if needed (recommended for 2-10% artifact rates)
5. Click **"Analyze HRV"**

**Results include**:

- **Time domain**: RMSSD, SDNN, pNN50, Mean HR
- **Frequency domain**: LF power, HF power, LF/HF ratio
- **Nonlinear**: SD1, SD2 (Poincaré plot)
- **Quality metrics**: Beat count, artifact rate, quality grade
- **Plots**: Tachogram, Poincaré plot, frequency spectrum, HR distribution

## 7. Export

- **CSV Export** — Download button in Analysis tab for statistical software
- **Ready for Analysis** — Save as `.rrational` file (sidebar) with full audit trail

---

## Next Steps

- [User Guide: Complete Workflow](../user-guide/workflow.md) — Detailed instructions for each step
- [Data Formats](../user-guide/data-formats.md) — File format specifications
- [Scientific Background](../science/guidelines.md) — HRV guidelines and best practices
