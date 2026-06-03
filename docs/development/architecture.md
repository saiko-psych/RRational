# Architecture Overview

## Directory Structure

```
src/rrational/
├── gui/
│   ├── app.py                 # Main Streamlit app + Participants tab
│   ├── tabs/                  # Tab modules
│   │   ├── data.py            # Data import, participant overview
│   │   ├── participant.py     # Participant tab (delegates to app.py)
│   │   ├── setup.py           # Events, Groups, Sequences, Sections
│   │   └── analysis.py        # HRV analysis, group comparison
│   ├── plots/                 # Visualization modules
│   │   ├── analysis_plots.py  # Tachogram, Poincare, frequency plots
│   │   └── group_plots.py     # Group comparison charts
│   ├── shared.py              # GUI utilities, caching
│   ├── persistence.py         # YAML storage for all config
│   ├── project.py             # ProjectManager class
│   ├── welcome.py             # Welcome screen & project wizard
│   ├── theme.py               # CSS/HTML/JS theming
│   ├── segmentation.py        # Unified time-based segments
│   ├── rrational_export.py    # .rrational export format
│   └── help_text.py           # In-app help strings
├── analysis/
│   ├── repeating_sections.py  # Repeating section extraction
│   ├── hrv_metrics.py         # Metric catalogs, presets, windowing
│   ├── hrv_compute.py         # HRV calculation, result transforms
│   ├── group_statistics.py    # Between-group hypothesis tests + effect sizes
│   └── sequence_statistics.py # Repeated-measures sequence statistics
├── cleaning/
│   ├── rr.py                  # RR interval cleaning
│   └── quality.py             # Artifact detection, quality grading
├── io/
│   ├── hrv_logger.py          # HRV Logger CSV parser
│   ├── vns_analyse.py         # VNS Analyse TXT parser
│   └── generic_rr.py          # Polar / Empatica / Elite HRV / Kubios / plain-text parsers
├── segments/
│   ├── section_normalizer.py  # Event name normalization
│   └── section_validation.py  # Section boundary validation
├── prep/
│   ├── participant_table.py   # Participant overview table
│   └── summaries.py           # Recording summary dataclasses
└── config/
    └── sections.py            # Section definition loading
```

## Key Design Decisions

### Lazy Imports
NeuroKit2 and Matplotlib are loaded on demand via `get_neurokit()` and `get_matplotlib()` to keep startup fast (~0.7s).

### Plot Downsampling
Plotly Scattergl with intelligent 5000-point downsampling for smooth rendering of long recordings.

### Caching
`@st.cache_data` for expensive operations (file loading, participant table building). Raw data is cached, not Streamlit objects.

### Unified Segmentation
Artifact detection and analysis use the same time-based segments (`gui/segmentation.py`), ensuring consistent quality assessment across the pipeline.

### Persistence
All configuration is stored as YAML files, either in the project folder (`config/`) or globally (`~/.rrational/`). The persistence layer handles both paths transparently.

## Dependencies

| Package | Purpose |
|---------|---------|
| Streamlit | Web GUI framework |
| NeuroKit2 | HRV metric computation, artifact correction |
| Plotly | Interactive plots (WebGL) |
| Pandas | Data manipulation |
| NumPy | Numerical operations |
| PyYAML | Configuration storage |
| streamlit-plotly-events | Click-to-add events directly on plots |
| streamlit-shortcuts | Keyboard shortcuts (Signal Inspection mode) |
