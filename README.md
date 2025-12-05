# Music HRV Toolkit

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Version](https://img.shields.io/badge/version-0.6.4-green.svg)](pyproject.toml)

Python-based pipeline for ingesting HRV data (HRV Logger & VNS Analyse), cleaning RR intervals, segmenting sessions by music style, and producing per-participant + group HRV metrics powered by `neurokit2`. Features a Streamlit GUI for researchers with no coding background.

## Quick Start

```bash
# Install dependencies
uv sync --group dev

# Launch the GUI
uv run streamlit run src/music_hrv/gui/app.py

# Run tests
uv run pytest
```

## Features (v0.6.4)

### Data Import & Management
- **HRV Logger CSV Import**: Load RR intervals and event markers from HRV Logger exports
- **VNS Analyse TXT Import**: Load VNS Analyse exports with automatic timestamp parsing from filename
- **Multi-file Support**: Automatically merges multiple files per participant
- **Participant ID Patterns**: 6 predefined patterns + custom regex for extracting IDs from filenames
- **Group Assignment**: Assign participants to study groups with expected events

### Interactive Visualization
- **WebGL-Accelerated Plots**: Fast rendering with Plotly Scattergl (5000 point downsampling)
- **Click-to-Add Events**: Click on the plot to add manual event markers
- **Toggle Overlays**: Show/hide variability segments, exclusion zones, music sections
- **Zoom & Pan**: Full interactive exploration of RR interval data
- **Exclusion Zones**: Define and edit time ranges to exclude from analysis

### Section-Based Validation
- **Flexible Section Definitions**: Define sections with start event and multiple possible end events
- **Duration Validation**: Set expected duration and tolerance for each section
- **Automatic Validation**: Check if all sections are present and have correct durations
- **Visual Feedback**: Clear status indicators (✅ valid, ⚠️ duration issue, ❌ missing events)

### Music Section Analysis
- **Playlist Groups**: Define randomization groups with different music orders
- **Auto-Generate Music Events**: Create music section boundaries at configurable intervals
- **Per-Music-Style Analysis**: Analyze HRV separately for each music type
- **Music Labels**: Define display names and descriptions for music items

### HRV Analysis
- **NeuroKit2 Integration**: Full HRV analysis (time domain, frequency domain)
- **Section-Based Analysis**: Analyze specific time segments with exclusion zone support
- **Artifact Handling**: Follows 2024 Quigley guidelines for artifact rates
- **Group Analysis**: Compare HRV across participant groups
- **CSV Export**: Download results for further analysis

### Scientific Best Practices
- **Artifact Reporting**: Transparent reporting of artifact rates and beat counts
- **Data Requirements**: Enforces minimum 100 beats (time domain), 300 beats (frequency domain)
- **Exclusion Criteria**: Automatic exclusion of segments with >10% artifacts
- **Documentation**: Built-in scientific best practices guide accessible from GUI

## GUI Tabs

| Tab | Purpose |
|-----|---------|
| **Participants** | View RR data, manage events, validate sections, define exclusion zones |
| **Setup > Events** | Define expected events with synonym patterns (regex support) |
| **Setup > Groups** | Create/edit study groups, select expected sections |
| **Setup > Playlists** | Manage music randomization groups and music labels |
| **Setup > Sections** | Define time ranges with start/end events, duration, tolerance |
| **Analysis** | Run NeuroKit2 HRV analysis, view metrics and export results |

## Data Sources

### HRV Logger (CSV)
- Automatically paired `*_RR_*.csv` and `*_Events_*.csv` files
- Timestamps from device
- Event markers with labels

### VNS Analyse (TXT)
- Single `.txt` file per participant
- Date/time parsed from filename: `dd.mm.yyyy hh.mm <name> xh xxmin.txt`
- Raw or corrected RR intervals (configurable)
- Notes embedded as events

## Data Storage

Configuration persists across sessions in `~/.music_hrv/`:
- `groups.yml` - Study group definitions
- `events.yml` - Event types and synonyms
- `sections.yml` - Section definitions with duration/tolerance
- `participants.yml` - Participant assignments and saved events
- `playlist_groups.yml` - Music randomization groups
- `music_labels.yml` - Music item labels and descriptions

## Project Structure

```
music_hrv/
├── src/music_hrv/
│   ├── gui/
│   │   ├── app.py           # Main Streamlit application
│   │   ├── tabs/            # Tab modules (data, setup, analysis)
│   │   ├── shared.py        # Shared utilities and caching
│   │   └── persistence.py   # YAML storage helpers
│   ├── io/
│   │   ├── hrv_logger.py    # HRV Logger CSV parsing
│   │   └── vns_analyse.py   # VNS Analyse TXT parsing
│   ├── cleaning/
│   │   └── rr.py            # RR interval cleaning
│   └── segments/
│       └── section_normalizer.py  # Event normalization
├── tests/                   # Pytest suite (18 tests)
├── docs/                    # Documentation
└── data/raw/                # Place HRV data here
```

## Configuration

### Cleaning Thresholds (Configurable in GUI)

- **RR Range**: 300-2000 ms (physiologically plausible)
- **Sudden Change**: 30% (detect ectopic beats)
- **Gap Threshold**: 15 seconds (for HRV Logger)

### Section Configuration

Sections support:
- Single start event
- Multiple end events (any can end the section)
- Expected duration in minutes
- Tolerance for duration validation

## Development

```bash
# Install dev dependencies
uv sync --group dev

# Run tests
uv run pytest

# Lint code
uv run ruff check src/ tests/ --fix

# Format code
uv run black src/ tests/
```

## Version History

| Version | Highlights |
|---------|------------|
| v0.6.4 | Multiple end events for sections, VNS timestamp parsing from filename |
| v0.6.3 | Section-based validation with duration/tolerance |
| v0.6.2 | Editable exclusion zones |
| v0.6.1 | Auto-fill boundary events, custom events from plot |
| v0.6.0 | Music Section Analysis mode |
| v0.5.x | VNS Analyse support, participant view improvements |

## Future Roadmap

- [ ] Standalone app (no Python required) - PyInstaller/Nuitka
- [ ] Example simulated data for testing/demo
- [ ] Tutorial videos
- [ ] Playlist group comparison across music types

## Documentation

- `QUICKSTART.md` - User guide for getting started
- `CLAUDE.md` - Quick reference for development
- `MEMORY.md` - Detailed session history and implementation notes
- `docs/HRV_project_spec.md` - Full pipeline specification

## License

MIT License - see LICENSE file for details.

---

*Version 0.6.4 | Last updated: 2025-12-05*
