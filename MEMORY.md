# MEMORY.md - Detailed Session History

This file contains detailed session notes and implementation history. For quick reference, see CLAUDE.md.

---

## Version History Summary

| Version | Date | Key Changes |
|---------|------|-------------|
| v0.8.1 | 2026-03-30 | Unified time-based segmentation, project restructuring, issue fixes (#16/#19/#27/#28) |
| v0.7.8 | 2026-01-18 | .rrational v2.0 format with section-based NN intervals, Analysis tab v2.0 support |
| v0.7.7 | 2026-01-18 | Explicit section validation storage, VNS multi-file merge (#20), Mac auto-load fix (#6) |
| v0.7.6 | 2026-01-17 | Centralized section validation with disambiguation UI |
| v0.7.4 | 2026-01-17 | Fix project config persistence (#23), project name in header, VNS description fix |
| v0.7.3 | 2026-01-16 | Manual artifact demarking (#4), detection workflow with save/load |
| v0.7.2 | 2026-01-15 | Project management system, welcome screen, auto-load last project |
| v0.7.1 | 2026-01-14 | Ready for Analysis export (.rrational files with audit trail) |
| v0.7.0 | 2026-01 | Renamed to RRational, Kubios-like artifact workflow, smart power formatting |
| v0.6.8 | 2026-01-11 | Professional analysis plots with reference values, data quality warnings |
| v0.6.7 | 2026-01-11 | Analysis tab event detection fix, processed folder storage, --test-mode |
| v0.6.x | 2025-12 | Section validation, exclusion zones, music section analysis |
| v0.5.x | 2025-12 | VNS support, NeuroKit2 artifact detection |
| v0.4.x | 2025-12 | VNS loader fixes, App column |
| v0.3.x | 2025-11/12 | CSV import, performance optimization, batch processing |
| v0.2.x | 2025-11 | Plotly visualization, multi-file support |
| v0.1.x | 2025-11 | Initial Streamlit GUI, persistent storage |

For detailed notes on v0.6.x and earlier, see [MEMORY_ARCHIVE.md](MEMORY_ARCHIVE.md).

---

## Development Style Guide for Music HRV App

This section documents coding patterns, styling guidelines, and best practices for future development.

### Theme & Color System

**Theme is controlled via `.streamlit/config.toml`** - NOT CSS injection.

```toml
# Light theme (default - professional/scientific)
[theme]
primaryColor = "#2E86AB"           # Blue accent
backgroundColor = "#FFFFFF"         # White background
secondaryBackgroundColor = "#F0F2F6" # Light gray (sidebar, expanders)
textColor = "#31333F"               # Dark gray text
```

**Color Palette Guidelines:**
- **Primary accent**: `#2E86AB` (professional blue)
- **Success/Good**: `#28A745` or `#92C88A` (green)
- **Warning**: `#FFC107` (amber)
- **Error/Danger**: `#DC3545` or `#FF6B6B` (red)
- **Neutral grays**: `#31333F` (text), `#6C757D` (secondary), `#F0F2F6` (background)

**NEVER use:** Purple gradients, hardcoded dark colors in light mode, CSS !important for theme colors.

### Dark Mode Canvas Fix

**Problem:** `st.data_editor` uses Glide Data Grid which renders to canvas (ignores CSS).

**Solution:**
```css
:root.dark-theme .stDataFrame [data-testid="stDataFrameResizable"],
:root.dark-theme [data-testid="glideDataEditor"] {
    filter: invert(0.93) hue-rotate(180deg);
}
```

### Streamlit Component Guidelines

**Always use native Streamlit components** for theme compatibility:
- `st.metric()`, `st.columns()`, `st.expander()`, `st.tabs()`, `st.progress()`, `st.divider()`

**Custom CSS is OK for:** Border radius, padding/margins, font weights, subtle shadows.

### HRV Reference Values (Scientific)

```python
HRV_REFERENCE_VALUES = {
    "RMSSD": {"low": 20, "normal": 42, "high": 70, "unit": "ms"},
    "SDNN": {"low": 50, "normal": 141, "high": 200, "unit": "ms"},
    # Source: Shaffer & Ginsberg (2017), Nunan et al. (2010)
}
```

### Data Classes vs Dicts

```python
# Handle both types
if isinstance(config, dict):
    self.config = config.copy()
elif hasattr(config, '__dict__'):
    self.config = {"rr_min_ms": getattr(config, 'rr_min_ms', 200), ...}
```

### Plot Styling (Plotly)

```python
PLOT_COLORS = {
    "primary": "#2E86AB", "secondary": "#A23B72",
    "accent": "#F18F01", "bands": ["#E8F4F8", "#D1E9F0", "#B9DEE8"],
}
fig.update_layout(template="plotly_white", font=dict(family="Arial, sans-serif", size=12))
```

### Session State Patterns

```python
if "key" not in st.session_state:
    st.session_state.key = default_value
value = st.session_state.get("key", default)
```

---

## Chrome Extension Testing Guide

### App Structure & Navigation

**Sidebar Navigation** (left side):
- `Data`, `Participants`, `Setup`, `Analysis` buttons

**Settings** (sidebar bottom): Expander "Settings" with theme, data folder, plot options.

### Key UI Elements by Page

- **Data Tab**: "Load Selected Sources", file type checkboxes, participant table
- **Participants Tab**: Participant dropdown, Previous/Next buttons, plot options row, mode selector
- **Analysis Tab**: Participant/section multiselects, "Analyze HRV" button, results in expandable sections

### Common Interactions

**To run HRV analysis:**
1. Navigate to Analysis tab
2. Select participant and section(s)
3. Click "Analyze HRV"

**Theme buttons** are inside an iframe - use JavaScript to click them.

### Important: Iframe Interactions

Use `mcp__claude-in-chrome__javascript_tool` to execute JS for iframe content.

### Test Mode

With `--test-mode`: Title shows "[TEST MODE]", auto-loads demo data.

---

## Session 2026-03-30: Unified Time-Based Segmentation System

### Version Tag: `v0.8.1`

### Major Feature: Professor Feedback Implementation

Implemented unified time-based segmentation for artifact detection and analysis, based on HRV expert feedback.

**Key Changes:**
1. **New module `segmentation.py`**: `Segment` dataclass + `generate_segments()` using numpy vectorization (`cumsum` + `searchsorted`)
2. **Artifact detection refactored**: Beat-based segmentation replaced with time-based via `generate_segments()`. Parameter `segment_beats` deprecated in favor of `window_s` (seconds).
3. **Segment assessment UI**: After artifact detection, shows per-segment quality table with include/exclude checkboxes. Auto-excludes segments >10% artifacts (Quigley 2024).
4. **Analysis integration**: `_calculate_hrv_metrics()` now accepts `segments` and `window_s` parameters. Two analysis modes: per-segment and aggregated.

**Design Decisions:**
- 0% overlap for artifact detection (each beat classified exactly once)
- Configurable overlap for analysis (default 50%)
- `generate_segments()` returns index ranges, not copied arrays
- Backward-compatible: old `segment_beats` parameter still works

**Files Created:**
- `src/rrational/gui/segmentation.py` (~100 lines)
- `tests/segments/test_segmentation.py` (28 tests)

**Files Modified:**
- `src/rrational/gui/app.py`: `cached_artifact_detection()`, `run_segmented_artifact_detection_at_gaps()`, segment UI
- `src/rrational/gui/tabs/analysis.py`: `_calculate_hrv_metrics()`, analysis mode UI

**Tests:** 46/46 passing (18 existing + 28 new)

---

## Session 2026-01-18: .rrational v2.0 Format Implementation

### Version Tag: `v0.7.8`

### Major Feature: Section-Based Analysis Export

Implemented .rrational v2.0 format for analysis-ready exports with section-based structure.

**Key Design Decisions:**
1. **Export-on-Demand**: .rrational created ONLY when user clicks "Export for Analysis"
2. **Incremental Updates**: Only changed sections are re-exported
3. **NN-Only Data**: Contains only corrected NN intervals, not raw RR (raw stays in source)
4. **Global Exclusion Zones**: Affect all overlapping sections
5. **Gaps vs Exclusions**: Marked differently - gaps are "missing data", exclusions are "bad data"

**New in persistence.py:**
- `save_nn_intervals()` - store corrected NN per section
- `load_nn_intervals()` - retrieve NN intervals
- `list_sections_with_nn_intervals()` - list sections with saved NN
- `get_nn_intervals_summary()` - overview of NN data

**New in rrational_export.py:**
- `SectionExportV2`, `MetadataV2`, `NNIntervalsDataV2`, etc. - v2.0 dataclasses
- `build_rrational_v2()` - consolidate data from intermediate files
- `save_rrational_v2()` - save with incremental update support
- `load_rrational_v2()` - load v2.0 format
- `get_rrational_version()` - detect file version
- `calculate_analysis_segments()` - split sections by exclusions/gaps

**Updated in analysis.py:**
- Version detection for ready files
- V2.0 section selection UI with quality info
- Direct NN interval loading from v2.0 exports
- Warnings when using raw data instead of ready files

**File Structure (v2.0):**
```yaml
rrational_version: "2.0"
metadata: {...}
sections:
  rest_pre:
    definition: {...}
    validation: {...}
    exclusion_zones: [...]
    analysis_segments: [...]
    nn_intervals: {data: [...], corrections: [...]}
    quality: {grade: "excellent", ...}
exclusion_zones_summary: [...]
recording_gaps: [...]
audit_trail: [...]
```

---

## Session 2026-01-17: Centralized Section Validation

### Version Tag: `v0.7.6`

### Problem
Section times differed between "Add Events" tab Section Validation and "Detect New Artifacts" scope selector. When multiple events could match a section boundary (e.g., multiple `rest_pre_start` markers), different parts of the app would pick different events.

### Solution: Centralized ValidatedSection System

**New Data Structures** (in `shared.py`):
- `EventCandidate` - represents a possible event for section boundary
- `ValidatedSection` - validated section with explicit event references
- `SectionValidationResult` - validation result with disambiguation info

**New Functions** (in `shared.py`):
- `find_event_candidates()` - finds all matching events for a boundary
- `validate_section_for_participant()` - centralized validation logic
- `get_validated_sections_for_participant()` - batch validation
- `save_section_selection()` - saves user's disambiguation choice
- `get_section_time_range()` - single source of truth for section boundaries

### Features
1. **Disambiguation UI**: When multiple events match, Section Validation shows dropdowns to select which specific event to use
2. **Persistence**: User selections saved to `participants.yml` and restored on reload
3. **Consistency**: All features (Section Validation, Artifact Detection, Signal Inspection) use same boundaries

### Bug Fixes
- Events looked up with wrong key (`events_{id}` vs `participant_events[id]`)
- Artifact detection wasn't filtering by group's selected sections
- Duration calculated as `beats/60` instead of actual timestamp difference

### Commits:
- `518ab72` - feat: centralized section validation with disambiguation UI
- `231c55d` - fix: correct event source lookup for section validation
- `1cf5516` - fix: use correct event source in Section Validation UI
- `84d6f29` - fix: filter artifact detection sections by group's selected sections
- `5f9e800` - fix: use actual section duration instead of beats/60 estimate

---

## Session 2026-01-17: Fix Project Config Persistence (Issue #23)

### Version Tag: `v0.7.4`

### Bug Fix: Groups/Events Not Saving to Project Folder

**Problem:** Groups and events created in a new project were lost on page reload.

**Root Cause:** Save functions in `shared.py`, `data.py`, and `app.py` were not passing `project_path`, causing config to save to `~/.rrational/` instead of `project/config/`.

**Files Fixed:**
- `src/rrational/gui/shared.py`: `save_all_config()`, `save_participant_data()`, `init_session_state()` now use `project_path`
- `src/rrational/gui/tabs/data.py`: CSV import save calls now pass `project_path`
- `src/rrational/gui/app.py`: Synonym tagging `save_events()` call now passes `project_path`
- `src/rrational/gui/persistence.py`: Updated type hint to `Path | str | None`

### Additional Improvements:
1. **Project name in header**: Added "Project: {name}" heading below main title
2. **Documentation updates**: Fixed VNS Analyse description ("iOS app" not "Windows software"), added app links
3. **GitHub workflow**: Added automatic priority labeling for issues

### Testing: All 18 tests passing, cross-platform path handling verified.

### Commits:
- `660f1f0` - fix: save groups/events to project folder instead of global config
- `eb2b4a4` - chore: bump version to 0.7.4

---

## Session 2026-01-16: Artifact Workflow Simplification

### Version Tag: `v0.7.3` (continued)

### Changes Made:
1. **Removed Validated Artifacts Concept**: Saving = implicit validation
2. **Added Warning for New Detection Over Saved Data**: Requires explicit confirmation
3. **Fixed `loaded_info_key` Undefined Error**
4. **Fixed Save Button Behavior**: Inline success message instead of rerun
5. **Fixed Show Artifacts Toggle**: Manual artifacts now respect toggle

### Files Modified:
- `src/rrational/gui/app.py`: Warning dialog, save button, artifacts display
- `src/rrational/gui/persistence.py`: Removed validated_artifacts, format_version 1.1

---

## Session 2026-01-16: Artifact Detection Workflow Improvements

### Version Tag: `v0.7.3`

### Major Feature: Manual Artifact Demarking + Detection Controls

1. **Separated Saved Artifacts from New Detection**: Explicit "Run Detection" button
2. **Manual Artifact Marking/Demarking**: Click to mark/unmark, purple diamonds for manual
3. **Performance Optimizations**: Fast path for marker-only updates
4. **Artifact Persistence**: Save/load with method and threshold settings

### Bug Fixes:
- Clear button not appearing
- Manual marking not updating UI
- Algorithm detection running automatically
- Deprecation warnings fixed

### GitHub Issue Closed: #4 "manual artifact demarking"

---

## Session 2026-01-15: Project Management System

### Version Tag: `v0.7.2`

### Major Feature: Project-Based Architecture

Each project is a self-contained folder:
```
MyStudy/
├── project.rrational          # Project metadata (YAML)
├── data/
│   ├── raw/                   # Raw HRV data files
│   └── processed/             # Exported files + participant events
├── config/                    # Project-specific configuration
└── analysis/                  # Analysis results (future)
```

### New Files Created:
- `src/rrational/gui/project.py` (509 lines): `ProjectMetadata`, `ProjectManager`
- `src/rrational/gui/welcome.py` (505 lines): Welcome screen, project creation wizard

### Key Implementation Details:
- **Native Folder Dialog**: Cross-platform via subprocess/tkinter
- **Auto-Load Last Project**: Loads on startup from `~/.rrational/settings.yml`
- **Project-Aware Config Storage**: All save/load functions accept `project_path`

### Bug Fixes:
- Browse button path sharing
- UnboundLocalError for Path
- Switch Project not working
- Auto-load data not triggering

---

## Session 2026-01-14: Ready for Analysis Export Feature

### Version Tag: `v0.7.1`

### Major Feature: .rrational Export Format

**New Export Module (`rrational_export.py`):**
- `RRationalExport` dataclass with comprehensive fields
- Metadata, segment definition, raw RR data, processing state, quality metrics, audit trail
- Quality grading based on Quigley et al. (2024) guidelines

**Export Section in Participants Tab:**
- Export type options: Full Recording, Selected Sections, Custom Time Range
- Include options: Artifact detection, Manual markings, Corrected NN intervals, Audit trail

**Analysis Tab Integration:**
- Detects `.rrational` files, shows "Ready Files" with file selector
- Uses stored artifact indices for analysis

### Files Created:
- `src/rrational/gui/rrational_export.py` (471 lines)

---

*For session notes on v0.6.x and earlier, see [MEMORY_ARCHIVE.md](MEMORY_ARCHIVE.md).*
