# Plan: Enhanced .rrational File Format v2.0

## Overview

The `.rrational` file is the **analysis-ready export** for a participant. It contains ONLY:
- Validated sections with corrected NN intervals
- Processing metadata and audit trail
- NO raw RR data (stays in source files)
- NO unvalidated sections

**Key behaviors:**
- Created/updated ONLY when user clicks "Export for Analysis"
- Updates are incremental (only changed sections re-exported)
- Gaps (from VNS multi-file) marked differently than exclusion zones, but both create separate analysis segments
- Exclusion zones are GLOBAL (affect all overlapping sections)

## Current State

### Existing Files (per participant in `project/processed/`):
1. `{id}_events.yml` - events, manual_events, music_events, exclusion_zones
2. `{id}_artifacts.yml` - per-section artifact detection
3. `{id}_section_validations.yml` - validated sections with event choices

### Problems:
- NN intervals (corrected beats) not saved
- No single "ready for analysis" file
- Unclear if section is ready for analysis or not
- Exclusion zones not clearly linked to sections

---

## Proposed .rrational v2.0 Structure

```yaml
rrational_version: "2.0"
file_type: "analysis_ready"

# =============================================================================
# METADATA
# =============================================================================
metadata:
  participant_id: "VP01"
  created_at: "2026-01-18T14:30:00"
  last_modified: "2026-01-18T15:45:00"
  source_app: "HRV Logger"  # or "VNS Analyse"
  source_files:
    - path: "data/raw/VP01_rr.csv"
      type: "rr_intervals"
      hash: "sha256:abc123..."  # For integrity verification
    - path: "data/raw/VP01_events.csv"
      type: "events"
      hash: "sha256:def456..."
  recording_info:
    start: "2026-01-15T10:00:00"
    end: "2026-01-15T11:30:00"
    total_beats: 5400
    total_duration_s: 5400.0
  software_versions:
    rrational: "0.7.7"
    neurokit2: "0.2.10"

# =============================================================================
# VALIDATED SECTIONS (Only sections that are ready for analysis)
# =============================================================================
# NOTE: Raw RR data is NOT included - only corrected NN intervals
# Raw data stays in source files for reproducibility
sections:
  rest_pre:
    # --- Section Definition ---
    definition:
      start_event: "rest_pre_start"
      end_event: "rest_pre_end"
      label: "Pre-Rest"

    # --- Validation (which events were chosen) ---
    validation:
      validated_at: "2026-01-18T14:35:00"
      start_event:
        label: "rest_pre_start"
        timestamp: "2026-01-15T10:05:00"
        beat_idx: 352
      end_event:
        label: "rest_pre_end"
        timestamp: "2026-01-15T10:10:00"
        beat_idx: 704
      total_duration_s: 300.0
      total_beat_count: 352

    # --- Exclusion Zones (within this section) ---
    exclusion_zones:
      - id: "excl_001"
        start_timestamp: "2026-01-15T10:07:00"
        end_timestamp: "2026-01-15T10:07:30"
        start_beat_idx: 493
        end_beat_idx: 528
        reason: "movement_artifact"
        created_at: "2026-01-18T14:40:00"

    # --- Gaps (from multi-file recordings, e.g., VNS restart) ---
    gaps: []  # None for this section

    # --- Artifact Detection ---
    artifact_detection:
      method: "lipponen2019"
      threshold_pct: 20
      run_at: "2026-01-18T14:45:00"
      detected_count: 4
      by_type:
        ectopic: 2
        missed: 1
        extra: 1
      artifact_rate_detected: 0.011

    # --- Manual Artifact Markings ---
    manual_artifacts:
      added_indices: [389]      # User marked as artifact
      removed_indices: [445]    # User unmarked (demarked)
      last_modified: "2026-01-18T14:50:00"

    # --- Final Artifact Summary ---
    final_artifacts:
      indices: [358, 389, 401, 502]  # Algorithm + manual_added - manual_removed
      count: 4
      rate: 0.011

    # --- Quality Assessment ---
    quality:
      grade: "excellent"  # Based on Quigley et al. (2024)
      recommendation: "suitable_for_all_metrics"
      usable_beats: 348
      usable_duration_s: 270.0  # After exclusion zones
      meets_time_domain_min: true   # >= 100 beats
      meets_freq_domain_min: true   # >= 300 beats AND >= 2 min

    # --- NN Correction ---
    nn_correction:
      method: "kubios"
      corrected_at: "2026-01-18T14:55:00"
      intervals_corrected: 3

    # --- Analysis Segments (split by exclusion zones and gaps) ---
    analysis_segments:
      - segment_id: "rest_pre_seg1"
        type: "data"  # "data" or "exclusion" or "gap"
        start_timestamp: "2026-01-15T10:05:00"
        end_timestamp: "2026-01-15T10:07:00"
        duration_s: 120.0
        nn_count: 141
        nn_start_idx: 0      # Index in nn_intervals array
        nn_end_idx: 140

      - segment_id: "rest_pre_excl1"
        type: "exclusion"
        reason: "movement_artifact"
        start_timestamp: "2026-01-15T10:07:00"
        end_timestamp: "2026-01-15T10:07:30"

      - segment_id: "rest_pre_seg2"
        type: "data"
        start_timestamp: "2026-01-15T10:07:30"
        end_timestamp: "2026-01-15T10:10:00"
        duration_s: 150.0
        nn_count: 176
        nn_start_idx: 141
        nn_end_idx: 316

    # --- Corrected NN Intervals (the actual data for analysis) ---
    nn_intervals:
      # Compact format: [timestamp_ms, nn_ms, was_corrected]
      # timestamp_ms = milliseconds since section start
      data:
        - [0, 850, false]
        - [850, 858, false]
        - [1708, 862, false]
        # ... more intervals
        - [30450, 855, true]   # This one was corrected (interpolated)
        # ... rest of NN intervals

      # For corrected intervals, store original value separately
      corrections:
        - nn_idx: 35
          original_rr_ms: 1250
          corrected_nn_ms: 855

  music_1:
    # Similar structure for each validated section
    # ...

# =============================================================================
# GLOBAL EXCLUSION ZONES (Reference - actual zones stored per-section above)
# =============================================================================
# These are stored here for overview; each section lists which zones affect it
exclusion_zones_summary:
  - id: "excl_001"
    timestamp_range: "2026-01-15T10:07:00 - 10:07:30"
    reason: "movement_artifact"
    affects_sections: ["rest_pre"]
    created_at: "2026-01-18T14:40:00"

# =============================================================================
# GAPS FROM MULTI-FILE RECORDINGS
# =============================================================================
# For VNS Analyse with multiple files (measurement restarts)
recording_gaps:
  - gap_id: "gap_001"
    after_file: "05.01.2026 10.00 VP01 1h 00min.txt"
    before_file: "05.01.2026 11.05 VP01 0h 30min.txt"
    gap_start: "2026-01-05T11:00:00"
    gap_end: "2026-01-05T11:05:00"
    gap_duration_s: 300.0
    affects_sections: ["music_2"]  # Which sections span this gap

# =============================================================================
# AUDIT TRAIL
# =============================================================================
audit_trail:
  - step: 1
    action: "export_created"
    timestamp: "2026-01-18T14:30:00"
    details: "Created .rrational export for participant VP01"
    sections_included: ["rest_pre", "music_1"]

  - step: 2
    action: "section_exported"
    timestamp: "2026-01-18T14:30:01"
    section: "rest_pre"
    details: "Exported rest_pre: 317 NN intervals, 2 segments (1 exclusion zone)"

  - step: 3
    action: "export_updated"
    timestamp: "2026-01-18T16:00:00"
    details: "Updated section music_1 with new artifact detection"
    sections_updated: ["music_1"]
```

---

## Implementation Plan

### Phase 1: Update Intermediate Storage (Foundation)

**Goal**: Ensure all data needed for .rrational export is properly saved in project files.

1. **Update exclusion zones in `_events.yml`**
   - Add beat indices (not just timestamps)
   - Add unique IDs for tracking
   - Keep in _events.yml (already working)

2. **Add NN intervals storage** (NEW)
   - Create `save_nn_intervals()` and `load_nn_intervals()` in persistence.py
   - File: `{participant_id}_nn_intervals.yml`
   - Store per-section: correction method, corrected intervals, statistics

3. **Update artifacts in `_artifacts.yml`**
   - Ensure quality assessment fields are saved
   - Track algorithm vs manual separately
   - Already mostly working, may need minor updates

### Phase 2: Create .rrational v2.0 Export Module

**Goal**: Build the export functionality that consolidates all files.

1. **New dataclasses in `rrational_export.py`**
   ```python
   @dataclass
   class SectionExport:
       definition: dict
       validation: dict
       exclusion_zones: list
       gaps: list
       artifact_detection: dict
       manual_artifacts: dict
       final_artifacts: dict
       quality: dict
       nn_correction: dict
       analysis_segments: list
       nn_intervals: dict  # data + corrections

   @dataclass
   class RRationalExportV2:
       version: str = "2.0"
       metadata: dict
       sections: dict[str, SectionExport]
       exclusion_zones_summary: list
       recording_gaps: list
       audit_trail: list
   ```

2. **Build function**: `build_rrational_v2(participant_id, sections_to_export) -> RRationalExportV2`
   - Load from all intermediate files
   - Calculate analysis segments (split by exclusions/gaps)
   - Generate audit trail
   - Return export object

3. **Save/Load functions**
   - `save_rrational_v2()` - with incremental update support
   - `load_rrational_v2()` - with v1.0 migration

4. **Incremental update logic**
   - Compare existing .rrational with current state
   - Only update changed sections
   - Append to audit trail

### Phase 3: Export UI

**Goal**: Add "Export for Analysis" button in Participants tab.

1. **Readiness check function**
   - For each section: validated? artifacts detected? NN corrected?
   - Return checklist with status per section

2. **Export dialog**
   - Show checklist: which sections are ready
   - Warnings for incomplete sections
   - Select which sections to export
   - "Export" button

3. **Progress feedback**
   - Show export progress
   - Summary: "Exported 3 sections with 1,542 NN intervals"

### Phase 4: Analysis Tab - Load from .rrational

**Goal**: Analysis tab uses .rrational as primary data source.

1. **Data source selection**
   - Check for .rrational file first
   - If found: show sections available, quality grades
   - If not: warning "No export found, using raw data (results may be unreliable)"

2. **Load NN intervals from .rrational**
   - Parse analysis_segments
   - Load NN data for selected section(s)

### Phase 5: Analysis Tab - Segmented Analysis

**Goal**: Add segmentation options for HRV analysis.

1. **Segmentation mode selector**
   - Overall (entire section as one)
   - Fixed-time (e.g., 2 min, 5 min)
   - Adaptive (auto-size based on section length)

2. **Overlap option** (for fixed-time)
   - 0%, 25%, 50%, 75%

3. **Gap/Exclusion handling display**
   - Show how section is split into analysis segments
   - Each segment analyzed separately (default)
   - Results aggregated: mean ± SD across segments

4. **Results output**
   - Per-segment HRV table
   - Summary statistics (mean, SD, min, max)
   - Export to CSV

---

## Key Design Decisions

### 1. Export-on-Demand
**Decision**: .rrational created ONLY when user clicks "Export for Analysis"

**Rationale**:
- User controls when data is "frozen" for analysis
- Intermediate files can be edited freely
- Clear separation between "work in progress" and "ready for analysis"

### 2. Incremental Updates
**Decision**: Updating .rrational only changes affected sections

**Rationale**:
- Preserves audit trail for unchanged sections
- Faster updates for large files
- Avoids accidental data loss

### 3. Only NN Data in Export
**Decision**: .rrational contains only corrected NN intervals, not raw RR

**Rationale**:
- Smaller file size
- Clear purpose: "ready for analysis"
- Raw data stays in source files for reproducibility

### 4. Exclusion Zones are Global
**Decision**: If a time range is excluded, it's excluded from all overlapping sections

**Rationale**:
- Simpler mental model
- If data is bad, it's bad for all analyses
- User can still choose which sections to export

### 5. Gaps vs Exclusions
**Decision**: Gaps (from VNS restarts) marked differently than user exclusions

**Rationale**:
- Gaps are "missing data" (couldn't record)
- Exclusions are "bad data" (user decided to exclude)
- Both create separate analysis segments
- Audit trail is clearer

---

## File Structure After Implementation

```
MyProject/
├── project.rrational           # Project metadata
├── data/
│   └── raw/                    # Source files (unchanged)
├── processed/
│   ├── VP01_events.yml         # Events + exclusion zones
│   ├── VP01_artifacts.yml      # Artifact detection per section
│   ├── VP01_section_validations.yml  # Section choices
│   ├── VP01_nn_intervals.yml   # NEW: Corrected NN per section
│   └── VP01.rrational          # EXPORT: Analysis-ready file
└── config/
    └── ...
```
