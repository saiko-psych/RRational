# Configuration & Storage

## Project-Based Workflow

RRational uses a project-based workflow where each study is a self-contained folder.

### Creating a Project

1. Launch RRational — the welcome screen appears
2. Click **"Create New Project"**
3. Choose a location and enter project details
4. Select your data sources (HRV Logger, VNS Analyse)
5. Click "Create Project"

### Project Structure

```
MyStudy/
├── project.rrational          # Project metadata (YAML)
├── data/
│   ├── raw/                   # Your original HRV files
│   │   ├── hrv_logger/        # HRV Logger CSV files
│   │   └── vns/               # VNS Analyse TXT files
│   └── processed/             # Exported .rrational files, saved events
├── config/                    # Project-specific configuration
│   ├── groups.yml             # Study groups
│   ├── events.yml             # Event definitions
│   ├── sections.yml           # Section definitions
│   ├── event_sequences.yml    # Event sequence definitions
│   ├── condition_labels.yml   # Condition display labels
│   └── protocol.yml           # Analysis protocol settings
└── analysis/                  # Analysis results (future)
```

### Sharing Projects

To share a study with collaborators:
1. Copy the entire project folder
2. Recipient opens it with "Open Existing Project"
3. All configuration and processed data is included

> **Note**: Raw HRV data files are in `data/raw/` — include or exclude as needed.

---

## Global Settings

Some settings are always stored globally in `~/.rrational/`:

```
~/.rrational/
├── settings.yml            # App settings (last project, plot options)
└── [config files]          # Fallback when not using a project
```

### What's Stored Where

| Data | Project Mode | No Project |
|------|-------------|------------|
| Events, exclusion zones | `data/processed/*.yml` | `~/.rrational/` |
| Groups, sections, events config | `config/*.yml` | `~/.rrational/` |
| Plot options, recent projects | `~/.rrational/settings.yml` | Same |
| Ready for Analysis exports | `data/processed/*.rrational` | `~/.rrational/` |

---

## Auto-Load

RRational remembers your last project and automatically loads it on startup. Click "Switch Project" in the sidebar to choose a different project.

---

## Saving

Click **"Save"** in the sidebar to persist all changes. Changes to groups, events, and sections are also auto-saved when you modify them in the Setup tab.
