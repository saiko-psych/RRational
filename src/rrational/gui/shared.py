"""Shared helpers, constants, and caching for the Music HRV GUI."""

from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import streamlit as st

from rrational.cleaning.rr import CleaningConfig
from rrational.io import DEFAULT_ID_PATTERN, PREDEFINED_PATTERNS, load_recording, discover_recordings
from rrational.prep.summaries import load_hrv_logger_preview, load_vns_preview
from rrational.segments.section_normalizer import SectionNormalizer
from rrational.config.sections import SectionsConfig, SectionDefinition, load_sections_config, DEFAULT_SECTIONS_PATH
from rrational.gui.persistence import (
    save_groups,
    load_groups,
    save_events,
    load_events,
    save_sections,
    save_participants,
    load_participants,
)

# Re-export for convenience
__all__ = [
    # Constants
    "DEFAULT_CANONICAL_EVENTS",
    "DEFAULT_ID_PATTERN",
    "PREDEFINED_PATTERNS",
    "NEUROKIT_AVAILABLE",
    # ValidatedSection System
    "EventCandidate",
    "ValidatedSection",
    "SectionValidationResult",
    "find_event_candidates",
    "validate_section_for_participant",
    "get_validated_sections_for_participant",
    "save_section_selection",
    "save_full_section_validations",
    "load_and_restore_section_validations",
    "get_section_time_range",
    # Functions
    "get_neurokit",
    "get_matplotlib",
    "create_gui_normalizer",
    "save_all_config",
    "save_participant_data",
    "update_normalizer",
    "show_toast",
    "auto_save_config",
    "validate_regex_pattern",
    "extract_section_rr_intervals",
    "filter_exclusion_zones",
    "detect_quality_changepoints",
    "get_quality_badge",
    "detect_time_gaps",
    "detect_artifacts_fixpeaks",
    "scroll_to_top",
    "get_participant_list",
    "get_summary_dict",
    # Cached functions
    "cached_load_hrv_logger_preview",
    "cached_load_vns_preview",
    "cached_load_participants",
    "cached_discover_recordings",
    "cached_load_recording",
    "cached_load_vns_recording",
    "cached_clean_rr_intervals",
    "cached_quality_analysis",
    "cached_get_plot_data",
    # Session state
    "init_session_state",
]

def _normalize_timestamp(ts):
    """Normalize a timestamp to naive datetime for safe comparison.

    Handles mixed timezone-aware and timezone-naive datetimes from old saved data.
    """
    if ts is None:
        return datetime.min
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return datetime.min
    # Convert to naive datetime to avoid offset-naive vs offset-aware comparison errors
    if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
        ts = ts.replace(tzinfo=None)
    return ts


# Default canonical events for the Default Group
DEFAULT_CANONICAL_EVENTS = {
    "rest_pre_start": [],
    "rest_pre_end": [],
    "measurement_start": [],
    "pause_start": [],
    "pause_end": [],
    "measurement_end": [],
    "rest_post_start": [],
    "rest_post_end": [],
}


# =============================================================================
# ValidatedSection System — canonical implementations in rrational.segments.section_validation
# Re-exported here for backward compatibility.
# =============================================================================
from rrational.segments.section_validation import (  # noqa: E402, F811
    EventCandidate,
    ValidatedSection,
    SectionValidationResult,
    find_event_candidates,
    validate_section_for_participant,
    _normalize_timestamp,
)


def get_validated_sections_for_participant(
    participant_id: str,
    sections_config: dict,
    normalizer,
    rr_intervals: list = None,
) -> dict[str, SectionValidationResult]:
    """Get all validated sections for a participant.

    This retrieves saved events from session state and validates all sections.
    User selections are loaded from session state if available.

    Args:
        participant_id: The participant ID
        sections_config: Dict of section definitions (from st.session_state.sections)
        normalizer: SectionNormalizer for mapping labels
        rr_intervals: Optional list of RR intervals for beat counting

    Returns:
        Dict mapping section_name to SectionValidationResult
    """
    # Get saved events for this participant
    # Events are stored in participant_events[participant_id] dict with 'events' and 'manual' keys
    participant_events = st.session_state.get("participant_events", {})
    participant_data = participant_events.get(participant_id, {})
    saved_events = participant_data.get("events", []) + participant_data.get("manual", [])

    if not saved_events:
        # No saved events - return empty results
        return {
            name: SectionValidationResult(
                section_name=name,
                is_valid=False,
                error_message="No events available for participant",
            )
            for name in sections_config.keys()
        }

    # Get any user selections for disambiguation
    user_selections_key = f"section_selections_{participant_id}"
    user_selections = st.session_state.get(user_selections_key, {})

    results = {}
    for section_name, section_def in sections_config.items():
        # Add name to def for convenience
        section_def_with_name = {**section_def, "name": section_name}

        # Get user selection for this section if exists
        user_selection = user_selections.get(section_name)

        result = validate_section_for_participant(
            section_def=section_def_with_name,
            events=saved_events,
            normalizer=normalizer,
            rr_intervals=rr_intervals,
            user_selection=user_selection,
        )
        results[section_name] = result

    return results


def save_section_selection(
    participant_id: str,
    section_name: str,
    start_index: int,
    end_index: int,
):
    """Save user's disambiguation choice for a section.

    Args:
        participant_id: The participant ID
        section_name: Name of the section (e.g., "rest_pre")
        start_index: Index of selected start candidate
        end_index: Index of selected end candidate
    """
    key = f"section_selections_{participant_id}"
    if key not in st.session_state:
        st.session_state[key] = {}

    st.session_state[key][section_name] = {
        "start_index": start_index,
        "end_index": end_index,
    }


def save_full_section_validations(participant_id: str):
    """Save the full section validation state for a participant to disk.

    This persists all section validation data explicitly, including:
    - Group membership
    - For each section: validity, events, disambiguation choices, etc.

    Call this whenever section validations change to ensure data is persisted.
    """
    from rrational.gui.persistence import save_section_validations

    # Get participant's group
    group = st.session_state.participant_groups.get(participant_id, "Default")

    # Get the group's sections config
    group_data = st.session_state.groups.get(group, {})
    if isinstance(group_data, dict):
        selected_sections = group_data.get("selected_sections", [])
    else:
        selected_sections = []

    # Get sections config
    sections_config = st.session_state.get("sections", {})
    normalizer = st.session_state.get("normalizer")

    if not normalizer or not sections_config:
        return

    # Filter sections by group's selected sections if configured
    if selected_sections:
        sections_to_validate = {k: v for k, v in sections_config.items() if k in selected_sections}
    else:
        sections_to_validate = sections_config

    # Get RR intervals for beat count and duration calculation
    rr_intervals = None
    full_rr_key = f"full_rr_data_{participant_id}"
    full_rr_data = st.session_state.get(full_rr_key, {})
    if full_rr_data:
        # Full RR data contains separate 'timestamps' and 'rr_values' lists
        timestamps = full_rr_data.get("timestamps", [])
        rr_values = full_rr_data.get("rr_values", [])
        if timestamps and rr_values and len(timestamps) == len(rr_values):
            # Convert to simple objects for validation
            from dataclasses import dataclass

            @dataclass
            class RRPoint:
                timestamp: object
                rr_ms: float

            rr_intervals = [RRPoint(timestamp=ts, rr_ms=rr) for ts, rr in zip(timestamps, rr_values)]

    # Get validation results for this participant
    validation_results = get_validated_sections_for_participant(
        participant_id,
        sections_to_validate,
        normalizer,
        rr_intervals=rr_intervals,
    )

    # Build explicit section validation state
    section_validations = {}

    for section_name, result in validation_results.items():
        section_data = {
            "is_valid": result.is_valid,
            "needs_disambiguation": result.needs_disambiguation,
            "error_message": result.error_message,
            "start_candidates_count": len(result.start_candidates),
            "end_candidates_count": len(result.end_candidates),
            "missing_start": len(result.start_candidates) == 0,
            "missing_end": len(result.end_candidates) == 0,
        }

        # Add validated section details if valid
        if result.validated_section:
            vs = result.validated_section
            section_data["start_event"] = {
                "canonical": vs.start_event.canonical_name,
                "raw_label": vs.start_event.raw_label,
                "timestamp": vs.start_event.timestamp.isoformat() if vs.start_event.timestamp else None,
                "index": vs.start_event.index,
            }
            section_data["end_event"] = {
                "canonical": vs.end_event.canonical_name,
                "raw_label": vs.end_event.raw_label,
                "timestamp": vs.end_event.timestamp.isoformat() if vs.end_event.timestamp else None,
                "index": vs.end_event.index,
            }
            section_data["manually_selected"] = vs.is_user_selected

            # Calculate duration from timestamps (event-based) if RR-based is 0
            duration_s = vs.duration_s
            if duration_s == 0 and vs.start_event.timestamp and vs.end_event.timestamp:
                # Calculate from event timestamps (normalize to avoid timezone issues)
                start_norm = _normalize_timestamp(vs.start_event.timestamp)
                end_norm = _normalize_timestamp(vs.end_event.timestamp)
                duration_s = (end_norm - start_norm).total_seconds()

            section_data["duration_s"] = duration_s
            section_data["beat_count"] = vs.beat_count

        # Store user's selection indices
        selections_key = f"section_selections_{participant_id}"
        user_selections = st.session_state.get(selections_key, {})
        if section_name in user_selections:
            section_data["selected_start_index"] = user_selections[section_name].get("start_index", 0)
            section_data["selected_end_index"] = user_selections[section_name].get("end_index", 0)

        section_validations[section_name] = section_data

    # Save to disk
    project_path = st.session_state.get("current_project")
    data_dir = st.session_state.get("data_dir")

    save_section_validations(
        participant_id=participant_id,
        group=group,
        section_validations=section_validations,
        data_dir=data_dir,
        project_path=project_path,
    )


def load_and_restore_section_validations(participant_id: str) -> bool:
    """Load saved section validations and restore to session state.

    This restores the user's section selection indices from the explicit
    validation file, ensuring disambiguation choices are preserved.

    Returns:
        True if validations were loaded, False if none existed.
    """
    from rrational.gui.persistence import load_section_validations

    project_path = st.session_state.get("current_project")
    data_dir = st.session_state.get("data_dir")

    saved = load_section_validations(
        participant_id=participant_id,
        data_dir=data_dir,
        project_path=project_path,
    )

    if not saved:
        return False

    # Restore section selections to session state
    selections_key = f"section_selections_{participant_id}"
    if selections_key not in st.session_state:
        st.session_state[selections_key] = {}

    sections = saved.get("sections", {})
    for section_name, section_data in sections.items():
        start_idx = section_data.get("selected_start_index")
        end_idx = section_data.get("selected_end_index")

        if start_idx is not None or end_idx is not None:
            st.session_state[selections_key][section_name] = {
                "start_index": start_idx if start_idx is not None else 0,
                "end_index": end_idx if end_idx is not None else 0,
            }

    return True


def get_section_time_range(
    participant_id: str,
    section_name: str,
    sections_config: dict,
    normalizer,
) -> tuple[Optional[datetime], Optional[datetime]]:
    """Convenience function to get start/end timestamps for a section.

    This is the ONLY function that should be used to get section boundaries.
    Replaces all ad-hoc implementations throughout the codebase.

    Args:
        participant_id: The participant ID
        section_name: Name of the section
        sections_config: Dict of section definitions
        normalizer: SectionNormalizer

    Returns:
        Tuple of (start_timestamp, end_timestamp), or (None, None) if invalid
    """
    if section_name not in sections_config:
        return None, None

    results = get_validated_sections_for_participant(
        participant_id=participant_id,
        sections_config=sections_config,
        normalizer=normalizer,
    )

    result = results.get(section_name)
    if not result or not result.is_valid or not result.validated_section:
        return None, None

    section = result.validated_section
    return section.start_event.timestamp, section.end_event.timestamp


# Lazy import for neurokit2 and matplotlib (saves ~0.9s on startup)
NEUROKIT_AVAILABLE = True
_nk = None
_plt = None


def get_neurokit():
    """Lazily import neurokit2 to speed up app startup."""
    global _nk, NEUROKIT_AVAILABLE
    if _nk is None:
        try:
            import neurokit2 as nk
            _nk = nk
        except ImportError:
            NEUROKIT_AVAILABLE = False
            _nk = None
    return _nk


def get_matplotlib():
    """Lazily import matplotlib to speed up app startup."""
    global _plt
    if _plt is None:
        import matplotlib.pyplot as plt
        _plt = plt
    return _plt


def create_gui_normalizer(gui_events_dict):
    """Create a SectionNormalizer that merges default patterns with GUI-defined events.

    The normalizer uses patterns from sections.yml as the base, then adds any
    additional synonyms defined in the GUI. This ensures German labels like
    'messung start' are properly matched even if not explicitly configured.

    GUI synonyms are treated as EXACT matches (escaped for regex, full-string match).
    Default patterns from sections.yml are treated as regex patterns.
    """
    # Load default patterns from sections.yml
    default_config = load_sections_config(DEFAULT_SECTIONS_PATH)

    # Build canonical order: start with default order, then add GUI-only events
    canonical_order = list(default_config.canonical_order)
    for name in gui_events_dict.keys():
        if name not in canonical_order:
            canonical_order.append(name)

    # Build sections_dict in canonical order (order matters for pattern matching!)
    sections_dict = {}
    for event_name in canonical_order:
        # Start with default patterns if available
        default_def = default_config.sections.get(event_name)
        default_synonyms = list(default_def.synonyms) if default_def else []

        # Get GUI-defined synonyms and convert to exact-match patterns
        # GUI synonyms are user-entered literal strings, not regex
        gui_synonyms_raw = gui_events_dict.get(event_name, [])
        gui_synonyms = [f"^{re.escape(s)}$" for s in gui_synonyms_raw if s]

        # Merge: GUI exact-match patterns first (higher priority), then default regex patterns
        merged_synonyms = gui_synonyms + [s for s in default_synonyms if s not in gui_synonyms]

        sections_dict[event_name] = SectionDefinition(
            name=event_name,
            synonyms=tuple(merged_synonyms),
            required=default_def.required if default_def else False,
            description=default_def.description if default_def else None,
            group=default_def.group if default_def else None
        )

    config = SectionsConfig(
        version=1,
        canonical_order=tuple(canonical_order),
        sections=sections_dict,
        groups={}
    )

    return SectionNormalizer(config=config, fallback_label="unknown")


def init_session_state():
    """Initialize all session state variables."""
    if "data_dir" not in st.session_state:
        st.session_state.data_dir = None
    if "summaries" not in st.session_state:
        st.session_state.summaries = []
    if "cleaning_config" not in st.session_state:
        st.session_state.cleaning_config = CleaningConfig()

    # Get project path for loading config
    project_path = st.session_state.get("current_project")

    # Load persisted groups
    if "groups" not in st.session_state:
        loaded_groups = load_groups(project_path)
        if not loaded_groups:
            st.session_state.groups = {
                "Default": {
                    "label": "Default Group",
                    "expected_events": DEFAULT_CANONICAL_EVENTS.copy(),
                    "selected_sections": []
                }
            }
        else:
            for group_name, group_data in loaded_groups.items():
                if "selected_sections" not in group_data:
                    group_data["selected_sections"] = []
            st.session_state.groups = loaded_groups

    # Load persisted events
    if "all_events" not in st.session_state:
        loaded_events = load_events(project_path)
        if not loaded_events:
            st.session_state.all_events = DEFAULT_CANONICAL_EVENTS.copy()
        else:
            st.session_state.all_events = loaded_events

    # Create normalizer from GUI events - always recreate to pick up code/config changes
    st.session_state.normalizer = create_gui_normalizer(st.session_state.all_events)

    # Load participant-specific data
    if "participant_groups" not in st.session_state or "event_order" not in st.session_state:
        loaded_participants = load_participants(project_path)
        if loaded_participants:
            st.session_state.participant_groups = {
                pid: data.get("group", "Default")
                for pid, data in loaded_participants.items()
            }
            st.session_state.event_order = {
                pid: data.get("event_order", [])
                for pid, data in loaded_participants.items()
            }
            st.session_state.manual_events = {
                pid: data.get("manual_events", [])
                for pid, data in loaded_participants.items()
            }
            # Note: section_selections are now stored in dedicated {participant_id}_section_validations.yml
            # and loaded via load_and_restore_section_validations() when participant is selected
        else:
            st.session_state.participant_groups = {}
            st.session_state.event_order = {}
            st.session_state.manual_events = {}


def save_all_config():
    """Save all configuration to persistent storage."""
    project_path = st.session_state.get("current_project")
    save_groups(st.session_state.groups, project_path)
    save_events(st.session_state.all_events, project_path)
    if hasattr(st.session_state, 'sections'):
        save_sections(st.session_state.sections, project_path)
    save_participant_data()


def save_participant_data():
    """Save participant-specific data (groups, playlists, labels, event orders, manual events).

    Note: Section selections are stored separately in {participant_id}_section_validations.yml
    via save_full_section_validations().
    """
    project_path = st.session_state.get("current_project")
    participants_data = {}

    # Collect all participant IDs that have any data
    all_participant_ids = set(
        list(st.session_state.participant_groups.keys()) +
        list(st.session_state.get("participant_playlists", {}).keys()) +
        list(st.session_state.get("participant_labels", {}).keys()) +
        list(st.session_state.event_order.keys()) +
        list(st.session_state.manual_events.keys())
    )

    for pid in all_participant_ids:
        participants_data[pid] = {
            "group": st.session_state.participant_groups.get(pid, "Default"),
            "sequence": st.session_state.get("participant_sequences", {}).get(pid, ""),
            "label": st.session_state.get("participant_labels", {}).get(pid, ""),
            "event_order": st.session_state.event_order.get(pid, []),
            "manual_events": st.session_state.manual_events.get(pid, []),
        }

    save_participants(participants_data, project_path)


def update_normalizer():
    """Update the normalizer when events are added/removed in GUI."""
    st.session_state.normalizer = create_gui_normalizer(st.session_state.all_events)
    cached_load_hrv_logger_preview.clear()
    cached_load_vns_preview.clear()


def show_toast(message, icon="success"):
    """Show a toast notification with auto-dismiss."""
    if icon == "success":
        st.toast(f"{message}", icon=":material/check:")
    elif icon == "info":
        st.toast(f"{message}", icon=":material/info:")
    elif icon == "warning":
        st.toast(f"{message}", icon=":material/warning:")
    elif icon == "error":
        st.toast(f"{message}", icon=":material/error:")
    else:
        st.toast(message)


def auto_save_config():
    """Auto-save configuration with non-intrusive feedback."""
    save_all_config()
    st.session_state.last_save_time = time.time()


def validate_regex_pattern(pattern):
    """Validate regex pattern and return error message if invalid."""
    try:
        re.compile(pattern)
        return None
    except re.error as e:
        return str(e)


def extract_section_rr_intervals(recording, section_def, normalizer, saved_events=None, participant_id=None):
    """Extract RR intervals for a specific section based on start/end events.

    Args:
        recording: Recording object with rr_intervals and events
        section_def: Section definition dict with start_events/end_events (lists) or
                     start_event/end_event (legacy single values). Must include "name" key
                     for centralized validation.
        normalizer: SectionNormalizer for mapping labels to canonical names
        saved_events: Optional list of saved/edited events (EventStatus objects or dicts).
                     If provided, uses these instead of recording.events.
                     This allows using user-edited events from session state.
        participant_id: Optional participant ID. If provided, uses centralized validation
                        which respects user disambiguation selections.
    """
    section_name = section_def.get("name")

    # If we have participant_id and section_name, use centralized validation for consistency
    if participant_id and section_name:
        sections_config = st.session_state.get("sections", {})
        if section_name in sections_config:
            start_ts, end_ts = get_section_time_range(
                participant_id=participant_id,
                section_name=section_name,
                sections_config=sections_config,
                normalizer=normalizer,
            )
            if start_ts and end_ts:
                section_rr = []
                start_ts_norm = _normalize_timestamp(start_ts)
                end_ts_norm = _normalize_timestamp(end_ts)
                for rr in recording.rr_intervals:
                    rr_ts_norm = _normalize_timestamp(rr.timestamp) if rr.timestamp else None
                    if rr_ts_norm and start_ts_norm <= rr_ts_norm <= end_ts_norm:
                        section_rr.append(rr)
                return section_rr if section_rr else None

    # Fallback: use legacy logic (for backwards compatibility)
    # Support both old (start_event/end_event) and new (start_events/end_events) format
    start_event_names = section_def.get("start_events", [])
    if not start_event_names and "start_event" in section_def:
        start_event_names = [section_def["start_event"]]
    end_event_names = section_def.get("end_events", [])
    if not end_event_names and "end_event" in section_def:
        end_event_names = [section_def["end_event"]]

    if not start_event_names or not end_event_names:
        return None

    start_ts = None
    end_ts = None

    # Use saved events if provided, otherwise fall back to recording.events
    if saved_events:
        # Saved events are EventStatus objects or dicts with canonical/first_timestamp
        for event in saved_events:
            # Handle both EventStatus objects and dicts
            if isinstance(event, dict):
                canonical = event.get("canonical")
                timestamp = event.get("first_timestamp")
                raw_label = event.get("raw_label", "")
            else:
                canonical = getattr(event, "canonical", None)
                timestamp = getattr(event, "first_timestamp", None)
                raw_label = getattr(event, "raw_label", "")

            if not timestamp:
                continue

            # Check canonical name (already normalized in saved events)
            if canonical in start_event_names:
                start_ts = timestamp
            elif canonical in end_event_names:
                if end_ts is None:
                    end_ts = timestamp
            # Also check raw label as fallback
            elif raw_label in start_event_names:
                start_ts = timestamp
            elif raw_label in end_event_names:
                if end_ts is None:
                    end_ts = timestamp
    else:
        # Fall back to recording.events (raw events from file)
        for event in recording.events:
            label = event.label
            canonical = normalizer.normalize(label)

            # First check if label is already a canonical name (for manual events)
            if label in start_event_names and event.timestamp:
                start_ts = event.timestamp
            elif label in end_event_names and event.timestamp:
                if end_ts is None:
                    end_ts = event.timestamp
            elif canonical in start_event_names and event.timestamp:
                start_ts = event.timestamp
            elif canonical in end_event_names and event.timestamp:
                if end_ts is None:
                    end_ts = event.timestamp

    if not start_ts or not end_ts:
        return None

    section_rr = []
    start_ts_norm = _normalize_timestamp(start_ts)
    end_ts_norm = _normalize_timestamp(end_ts)
    for rr in recording.rr_intervals:
        rr_ts_norm = _normalize_timestamp(rr.timestamp) if rr.timestamp else None
        if rr_ts_norm and start_ts_norm <= rr_ts_norm <= end_ts_norm:
            section_rr.append(rr)

    return section_rr if section_rr else None


# =============================================================================
# Signal quality functions — canonical implementations in rrational.cleaning.quality
# Re-exported here for backward compatibility.
# =============================================================================
from rrational.cleaning.quality import (  # noqa: E402, F811
    detect_quality_changepoints,
    get_quality_badge,
    detect_time_gaps,
    detect_artifacts_fixpeaks,
    filter_exclusion_zones,
)


# ================== Cached Functions ==================

@st.cache_data(show_spinner=False, ttl=300)
def cached_load_hrv_logger_preview(data_dir_str, pattern, config_dict, gui_events_dict):
    """Cached version of load_hrv_logger_preview for instant navigation."""
    data_path = Path(data_dir_str)
    config = CleaningConfig(
        rr_min_ms=config_dict["rr_min_ms"],
        rr_max_ms=config_dict["rr_max_ms"],
        sudden_change_pct=config_dict["sudden_change_pct"]
    )
    normalizer = create_gui_normalizer(gui_events_dict)
    return load_hrv_logger_preview(data_path, pattern=pattern, config=config, normalizer=normalizer)


@st.cache_data(show_spinner=False, ttl=300)
def cached_load_vns_preview(data_dir_str, pattern, config_dict, gui_events_dict, use_corrected=False):
    """Cached version of load_vns_preview for VNS Analyse data."""
    data_path = Path(data_dir_str)
    config = CleaningConfig(
        rr_min_ms=config_dict["rr_min_ms"],
        rr_max_ms=config_dict["rr_max_ms"],
        sudden_change_pct=config_dict["sudden_change_pct"]
    )
    normalizer = create_gui_normalizer(gui_events_dict)
    return load_vns_preview(data_path, pattern=pattern, config=config, normalizer=normalizer, use_corrected=use_corrected)


@st.cache_data(show_spinner=False, ttl=300)
def cached_load_participants():
    """Cached version of load_participants for faster access.

    TTL ensures cache is refreshed periodically to prevent memory accumulation.
    """
    return load_participants()


@st.cache_data(show_spinner=False, ttl=600)
def cached_discover_recordings(data_dir_str: str, pattern: str):
    """Cache discovery of recordings to avoid re-scanning directory."""
    data_path = Path(data_dir_str)
    return list(discover_recordings(data_path, pattern=pattern))


@st.cache_data(show_spinner=False, ttl=600)
def cached_load_recording(rr_paths_tuple, events_paths_tuple, participant_id: str):
    """Cache loaded recording data for instant access."""
    from rrational.io.hrv_logger import RecordingBundle
    bundle = RecordingBundle(
        participant_id=participant_id,
        rr_paths=[Path(p) for p in rr_paths_tuple],
        events_paths=[Path(p) for p in events_paths_tuple]
    )
    recording, raw_events, _ = load_recording(bundle)
    return {
        'rr_intervals': [(rr.timestamp, rr.rr_ms, rr.elapsed_ms) for rr in recording.rr_intervals],
        'events': [(e.label, e.timestamp) for e in recording.events],
        'raw_events': raw_events
    }


@st.cache_data(show_spinner=False, ttl=300)
def cached_clean_rr_intervals(rr_data_tuple, config_dict):
    """Cache cleaned RR intervals to avoid recomputation."""
    from rrational.cleaning.rr import clean_rr_intervals, RRInterval
    rr_intervals = [RRInterval(timestamp=ts, rr_ms=rr, elapsed_ms=elapsed)
                    for ts, rr, elapsed in rr_data_tuple]
    config = CleaningConfig(
        rr_min_ms=config_dict["rr_min_ms"],
        rr_max_ms=config_dict["rr_max_ms"],
        sudden_change_pct=config_dict["sudden_change_pct"]
    )
    cleaned, stats = clean_rr_intervals(rr_intervals, config)
    return [(rr.timestamp, rr.rr_ms) for rr in cleaned if rr.timestamp], stats


@st.cache_data(show_spinner=False, ttl=300)
def cached_quality_analysis(rr_values_tuple, timestamps_tuple):
    """Cache quality changepoint detection results."""
    rr_list = list(rr_values_tuple)
    timestamps_list = list(timestamps_tuple)
    result = detect_quality_changepoints(rr_list, change_type="var")
    n_ts = len(timestamps_list)
    for seg_stats in result["segment_stats"]:
        start_idx = seg_stats["start_idx"]
        end_idx = min(seg_stats["end_idx"], n_ts - 1)
        seg_stats["start_time"] = timestamps_list[start_idx] if start_idx < n_ts else None
        seg_stats["end_time"] = timestamps_list[end_idx] if end_idx < n_ts else None
    return result


@st.cache_data(show_spinner=False, ttl=300)
def cached_get_plot_data(timestamps_tuple, rr_values_tuple, participant_id: str, downsample_threshold: int = 5000):
    """Cache processed plot data (NOT the figure - that's slow to serialize)."""
    timestamps = list(timestamps_tuple)
    rr_values = list(rr_values_tuple)

    n_points = len(timestamps)
    if n_points > downsample_threshold:
        step = n_points // downsample_threshold
        timestamps = timestamps[::step]
        rr_values = rr_values[::step]

    y_min = min(rr_values)
    y_max = max(rr_values)
    y_range = y_max - y_min

    return {
        'timestamps': timestamps,
        'rr_values': rr_values,
        'y_min': y_min,
        'y_max': y_max,
        'y_range': y_range,
        'n_original': n_points,
        'n_displayed': len(timestamps),
        'participant_id': participant_id
    }


@st.cache_data(show_spinner=False, ttl=600)
def cached_load_vns_recording(vns_paths_tuple: tuple, participant_id: str, use_corrected: bool = False):
    """Cache loaded VNS recording data for instant access.

    Args:
        vns_paths_tuple: Tuple of VNS file path strings (for cache key hashability)
        participant_id: Participant identifier
        use_corrected: Whether to use corrected RR values from VNS files
    """
    from rrational.io.vns_analyse import VNSRecordingBundle, load_vns_recording
    bundle = VNSRecordingBundle(
        participant_id=participant_id,
        file_paths=[Path(p) for p in vns_paths_tuple],
    )
    recording = load_vns_recording(bundle, use_corrected=use_corrected)

    # Serialize file segments for caching
    file_segments = None
    if recording.file_segments:
        file_segments = [
            {
                'file_name': seg.file_path.name,
                'start_time': seg.start_time,
                'end_time': seg.end_time,
                'duration_ms': seg.duration_ms,
                'beat_count': seg.beat_count,
            }
            for seg in recording.file_segments
        ]

    # Serialize gaps
    gaps = None
    if recording.gaps:
        gaps = [
            {
                'after_file': gap.after_file.name,
                'before_file': gap.before_file.name,
                'gap_start': gap.gap_start,
                'gap_end': gap.gap_end,
                'gap_duration_s': gap.gap_duration_s,
            }
            for gap in recording.gaps
        ]

    # Serialize overlaps
    overlaps = None
    if recording.overlaps:
        overlaps = [
            {
                'file1': ov.file1.name,
                'file2': ov.file2.name,
                'overlap_start': ov.overlap_start,
                'overlap_end': ov.overlap_end,
                'overlap_duration_s': ov.overlap_duration_s,
            }
            for ov in recording.overlaps
        ]

    return {
        'rr_intervals': [(rr.timestamp, rr.rr_ms, rr.elapsed_ms) for rr in recording.rr_intervals],
        'events': [(e.label, e.timestamp) for e in recording.events],
        'raw_events': [],  # VNS doesn't have duplicate tracking
        'file_segments': file_segments,
        'gaps': gaps,
        'overlaps': overlaps,
    }


def scroll_to_top():
    """Inject JavaScript to scroll the page to the top.

    This is useful when navigating between participants or sections.
    """
    js = """
    <script>
        var streamlitDoc = window.parent.document;
        streamlitDoc.querySelector('[data-testid="stAppViewContainer"]').scrollTop = 0;
    </script>
    """
    st.components.v1.html(js, height=0)


def get_participant_list():
    """Get cached list of participant IDs (O(1) after first call per summaries change)."""
    if not st.session_state.summaries:
        return []
    # Use a simple cache key based on number of summaries and first/last IDs
    summaries = st.session_state.summaries
    cache_key = f"{len(summaries)}:{summaries[0].participant_id if summaries else ''}:{summaries[-1].participant_id if summaries else ''}"
    if st.session_state.get("_participant_list_cache_key") != cache_key:
        st.session_state._participant_list = [s.participant_id for s in summaries]
        st.session_state._participant_list_cache_key = cache_key
    return st.session_state._participant_list


def get_summary_dict():
    """Get cached dict mapping participant_id to summary (O(1) lookup after first call)."""
    if not st.session_state.summaries:
        return {}
    summaries = st.session_state.summaries
    cache_key = f"{len(summaries)}:{summaries[0].participant_id if summaries else ''}:{summaries[-1].participant_id if summaries else ''}"
    if st.session_state.get("_summary_dict_cache_key") != cache_key:
        st.session_state._summary_dict = {s.participant_id: s for s in summaries}
        st.session_state._summary_dict_cache_key = cache_key
    return st.session_state._summary_dict
