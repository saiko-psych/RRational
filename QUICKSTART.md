# RRational Quick Start Guide

**Version: v0.7.2** | **Last Updated: January 2026**

---

## Installation

### Prerequisites

- Python 3.11, 3.12, or 3.13 ([Download](https://www.python.org/downloads/))
- uv package manager ([Install uv](https://docs.astral.sh/uv/getting-started/installation/))

### Install RRational

```bash
# Clone the repository
git clone https://github.com/saiko-psych/rrational.git
cd rrational

# Install dependencies
uv sync

# Launch the app
uv run streamlit run src/rrational/gui/app.py
```

The app opens at http://localhost:8501

---

## First Launch: Welcome Screen

When you start RRational, you'll see the **Welcome Screen**:

| Option | When to Use |
|--------|-------------|
| **Recent Projects** | Click any listed project to open it |
| **Open Existing Project** | Browse to a folder containing `project.rrational` |
| **Create New Project** | Start a new study with organized folder structure |
| **Continue Without Project** | Quick testing (settings saved to `~/.rrational/`) |

### Recommended: Create a Project

Projects keep your HRV studies organized and portable:

1. Click **"Create New Project"**
2. **Browse** to choose where to save (e.g., `Documents/HRV_Studies/`)
3. Enter a **project name** (this creates a folder, e.g., `MyStudy/`)
4. Optionally add description and author
5. Select **data sources** (HRV Logger, VNS Analyse, or both)
6. Click **"Create Project"**

Your project folder structure:

```
MyStudy/
├── project.rrational          # Project metadata
├── data/
│   ├── raw/
│   │   ├── hrv_logger/        # Put your HRV Logger CSV files here
│   │   └── vns/               # Put your VNS Analyse TXT files here
│   └── processed/             # Exported files and saved events
├── config/                    # Your study configuration
└── analysis/                  # Future: analysis results
```

---

## Typical Workflow

### 1. Import Data

1. Copy your HRV files to `data/raw/hrv_logger/` or `data/raw/vns/`
2. Go to the **Data** tab
3. Click **"Load Selected Sources"**
4. Review the participant overview table

**File naming**: RRational extracts participant IDs using patterns (default: 4 digits + 4 letters, e.g., `0001CTRL`). Adjust in Import Settings if needed.

### 2. Review Participants

1. Go to the **Participants** tab
2. Select a participant from the dropdown
3. The tachogram (RR interval plot) shows your data
4. Use **Previous/Next** buttons to navigate

**Plot options** (checkboxes):
- Show events (vertical lines)
- Show exclusion zones (red shading)
- Show artifacts (orange markers)
- Show time gaps (gray shading)

### 3. Inspect & Clean Data

Switch between modes using the **Mode** radio buttons:

| Mode | Purpose |
|------|---------|
| **View Events** | See and edit detected events |
| **Add Events** | Click plot to add new event markers |
| **Add Exclusions** | Click two points to exclude a time range |
| **Signal Inspection** | Detailed artifact analysis |

**Signal Inspection** workflow:
1. Select Signal Inspection mode
2. Choose detection method (Lipponen 2019 recommended)
3. Review artifact markers on the plot
4. Check quality grade (Excellent/Good/Acceptable/Poor)
5. Define exclusion zones for problem areas

### 4. Configure Study

Use the **Setup** tabs to configure your study:

| Tab | Purpose |
|-----|---------|
| **Events** | Define expected events and synonyms |
| **Groups** | Create study groups (Control, Experimental, etc.) |
| **Sections** | Define analysis sections (Baseline, Task, Recovery) |

**Example section definition**:
- Name: `baseline`
- Start event: `rest_start`
- End events: `rest_end` or `task_start`
- Expected duration: 5 minutes (±1 min tolerance)

### 5. Run Analysis

1. Go to the **Analysis** tab
2. Select participant(s)
3. Select section(s) to analyze
4. Enable **"Apply artifact correction"** if needed
5. Click **"Analyze HRV"**

**Results include**:
- Time domain: RMSSD, SDNN, pNN50, Mean HR
- Frequency domain: LF, HF, LF/HF ratio
- Plots: Tachogram, Poincaré, Frequency spectrum
- Quality metrics: Beat count, artifact rate, grade

### 6. Export Results

**CSV Export**: Download button in Analysis tab for statistical analysis

**Ready for Analysis Export** (Participants tab sidebar):
- Saves inspected data as `.rrational` files
- Includes full audit trail
- Quality metrics and artifact indices preserved
- Can be reloaded in Analysis tab

---

## Data Format Reference

### HRV Logger (CSV)

Expected files in `data/raw/hrv_logger/`:
- `*_RR_*.csv` - RR interval data
- `*_Events_*.csv` - Event markers (optional)

### VNS Analyse (TXT)

Expected files in `data/raw/vns/`:
- `*.txt` - Single file with RR data and annotations

**Import Settings** (Data tab):
- Choose Raw or Corrected RR values
- VNS filenames should include date/time: `15.03.2025 09.07`

---

## Saving Your Work

### Auto-Save

- Click **"Save"** in the sidebar to persist all changes
- Changes are saved to your project's `config/` folder

### What's Saved

| Data | Location |
|------|----------|
| Events, exclusion zones | `data/processed/PARTICIPANT_events.yml` |
| Groups, sections, events | `config/*.yml` |
| Ready for Analysis exports | `data/processed/*.rrational` |

### Switching Projects

- Click **"Switch Project"** in sidebar
- Your last project is remembered and auto-loads next time

---

## Tips & Best Practices

### Scientific Guidelines (Quigley 2024)

| Metric Type | Max Artifact Rate | Min Beats |
|-------------|-------------------|-----------|
| RMSSD, SDNN | ~36% | 100 |
| pNN50 | ~4% | 100 |
| HF, LF, LF/HF | ~2% | 300 |

### Recommended Workflow

1. **Visual inspection** - Always review tachogram before analysis
2. **Check artifacts** - Enable Signal Inspection mode
3. **Exclude problems** - Define exclusion zones for bad segments
4. **Use correction** - Enable artifact correction for 2-10% artifact rates
5. **Report metrics** - Note beat count and artifact rate in publications

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| R | Rerun app (refresh) |
| C | Clear cache |

---

## Troubleshooting

### Common Issues

**"No data loaded"**
- Check files are in correct `data/raw/` subfolder
- Verify file format matches expected pattern
- Check Import Settings → ID pattern

**"Section not detected"**
- Verify events are mapped to canonical names (Events tab)
- Check that start and end events exist for the participant
- Ensure events are saved

**Performance slow**
- Reduce plot resolution in Settings
- Close other browser tabs
- Use "Load Preview" first, then load individual participants

### Getting Help

- In-app help: Look for ℹ️ icons and expandable help sections
- Documentation: See README.md and docs/ folder
- Issues: https://github.com/saiko-psych/rrational/issues

---

## Version History

| Version | Highlights |
|---------|------------|
| **v0.7.2** | Project management system, welcome screen, auto-load |
| v0.7.1 | Ready for Analysis export with audit trail |
| v0.7.0 | Renamed to RRational, artifact detection improvements |

---

**RRational - A rational approach to HRV analysis**

*Free and open-source. If you use this tool in your research, please cite appropriately.*
