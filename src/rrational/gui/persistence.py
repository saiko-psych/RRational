"""Persistence layer for GUI configuration (groups, events, sections).

Supports both global config (~/.rrational/) and project-based config.
When project_path is provided, config is stored in project/config/ folder.
"""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any


CONFIG_DIR = Path.home() / ".rrational"
LEGACY_CONFIG_DIR = Path.home() / ".music_hrv"  # Pre-v0.7.0 config directory
GROUPS_FILE = CONFIG_DIR / "groups.yml"
EVENTS_FILE = CONFIG_DIR / "events.yml"
SECTIONS_FILE = CONFIG_DIR / "sections.yml"
PARTICIPANTS_FILE = CONFIG_DIR / "participants.yml"
PLAYLIST_GROUPS_FILE = CONFIG_DIR / "playlist_groups.yml"
MUSIC_LABELS_FILE = CONFIG_DIR / "music_labels.yml"
PROTOCOL_FILE = CONFIG_DIR / "protocol.yml"
PARTICIPANT_EVENTS_FILE = CONFIG_DIR / "participant_events.yml"
SETTINGS_FILE = CONFIG_DIR / "settings.yml"

# Default settings
DEFAULT_SETTINGS = {
    "data_folder": "",  # Empty = use file picker
    "auto_load": False,  # Auto-load from default folder on startup
    "accent_color": "#2E86AB",  # UI accent color
    "plot_resolution": 5000,
    "plot_options": {
        "show_events": True,
        "show_exclusions": True,
        "show_music_sections": True,
        "show_music_events": False,
        "show_artifacts": False,
        "show_variability": False,
        "show_gaps": True,
        "gap_threshold": 15.0,
        "colors": {
            "line": "#2E86AB",  # RR interval line color
            "artifact": "#FF6B6B",  # Artifact marker color
        },
    },
    "recent_projects": [],  # List of recently opened projects
    "max_recent_projects": 10,
    "last_project": "",  # Path to last used project (auto-load on startup)
}


def ensure_config_dir() -> None:
    """Create config directory if it doesn't exist."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def _get_config_path(filename: str, project_path: Path | str | None = None) -> Path:
    """Get the path for a config file, supporting project-based storage.

    Args:
        filename: Name of the config file (e.g., 'groups.yml')
        project_path: If provided (Path or str), returns project/config/{filename}
                      Otherwise returns ~/.rrational/{filename}

    Returns:
        Path to the config file
    """
    if project_path:
        # Ensure project_path is a Path object (handles both Path and str)
        config_dir = Path(project_path) / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / filename
    return CONFIG_DIR / filename


def migrate_legacy_config() -> bool:
    """Migrate configuration from legacy ~/.music_hrv to ~/.rrational.

    This handles the v0.7.0 rename from music_hrv to rrational.
    Migrates files when:
    - New file doesn't exist, OR
    - Legacy file has more content (larger size) than new file
      (indicates new file only has defaults, legacy has real user data)

    Returns:
        True if migration was performed, False if not needed
    """
    import shutil

    if not LEGACY_CONFIG_DIR.exists():
        return False  # No legacy config to migrate

    # List of files to migrate
    legacy_files = [
        "groups.yml",
        "events.yml",
        "sections.yml",
        "participants.yml",
        "playlist_groups.yml",
        "music_labels.yml",
        "protocol.yml",
        "participant_events.yml",
        "settings.yml",
    ]

    migrated_any = False
    ensure_config_dir()

    for filename in legacy_files:
        legacy_file = LEGACY_CONFIG_DIR / filename
        new_file = CONFIG_DIR / filename

        if not legacy_file.exists():
            continue

        # Migrate if: new file doesn't exist OR legacy is larger (has more user data)
        should_migrate = False
        if not new_file.exists():
            should_migrate = True
        else:
            # If legacy file is significantly larger, it likely has real user data
            # while new file only has defaults
            legacy_size = legacy_file.stat().st_size
            new_size = new_file.stat().st_size
            if legacy_size > new_size:
                should_migrate = True

        if should_migrate:
            try:
                shutil.copy2(legacy_file, new_file)
                migrated_any = True
            except Exception:
                pass  # Silently continue if copy fails

    return migrated_any


# --- Groups ---

def save_groups(groups: dict[str, Any], project_path: Path | None = None) -> None:
    """Save groups configuration to YAML.

    Args:
        groups: Groups configuration dict
        project_path: If provided, saves to project/config/groups.yml
    """
    if not project_path:
        ensure_config_dir()
    target = _get_config_path("groups.yml", project_path)
    with open(target, "w", encoding="utf-8") as f:
        yaml.safe_dump(groups, f, default_flow_style=False, allow_unicode=True)


def load_groups(project_path: Path | None = None) -> dict[str, Any]:
    """Load groups configuration from YAML.

    Args:
        project_path: If provided, loads from project/config/groups.yml

    Returns:
        Groups configuration dict, or empty dict if not found
    """
    target = _get_config_path("groups.yml", project_path)
    if not target.exists():
        return {}
    with open(target, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# --- Events ---

def save_events(events: dict[str, list[str]], project_path: Path | None = None) -> None:
    """Save events configuration to YAML.

    Args:
        events: Events configuration dict (canonical -> synonyms)
        project_path: If provided, saves to project/config/events.yml
    """
    if not project_path:
        ensure_config_dir()
    target = _get_config_path("events.yml", project_path)
    with open(target, "w", encoding="utf-8") as f:
        yaml.safe_dump(events, f, default_flow_style=False, allow_unicode=True)


def load_events(project_path: Path | None = None) -> dict[str, list[str]]:
    """Load events configuration from YAML.

    Args:
        project_path: If provided, loads from project/config/events.yml

    Returns:
        Events configuration dict, or empty dict if not found
    """
    target = _get_config_path("events.yml", project_path)
    if not target.exists():
        return {}
    with open(target, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# --- Sections ---

def save_sections(sections: dict[str, Any], project_path: Path | None = None) -> None:
    """Save sections configuration to YAML.

    Args:
        sections: Sections configuration dict
        project_path: If provided, saves to project/config/sections.yml
    """
    if not project_path:
        ensure_config_dir()
    target = _get_config_path("sections.yml", project_path)
    with open(target, "w", encoding="utf-8") as f:
        yaml.safe_dump(sections, f, default_flow_style=False, allow_unicode=True)


def load_sections(project_path: Path | None = None) -> dict[str, Any]:
    """Load sections configuration from YAML.

    Args:
        project_path: If provided, loads from project/config/sections.yml

    Returns:
        Sections configuration dict, or empty dict if not found
    """
    target = _get_config_path("sections.yml", project_path)
    if not target.exists():
        return {}
    with open(target, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# --- Participants ---

def save_participants(participants_data: dict[str, Any], project_path: Path | None = None) -> None:
    """Save participants configuration to YAML.

    Args:
        participants_data: Participant data dict
        project_path: If provided, saves to project/config/participants.yml

    Format:
    {
        "participant_id": {
            "group": "group_name",
            "event_order": ["event1", "event2", ...],
            "manual_events": [...]
        }
    }
    """
    if not project_path:
        ensure_config_dir()
    target = _get_config_path("participants.yml", project_path)
    with open(target, "w", encoding="utf-8") as f:
        yaml.safe_dump(participants_data, f, default_flow_style=False, allow_unicode=True)


def load_participants(project_path: Path | None = None) -> dict[str, Any]:
    """Load participants configuration from YAML.

    Args:
        project_path: If provided, loads from project/config/participants.yml

    Returns:
        Participants configuration dict, or empty dict if not found
    """
    target = _get_config_path("participants.yml", project_path)
    if not target.exists():
        return {}
    with open(target, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# --- Playlist Groups ---

def save_playlist_groups(playlist_groups: dict[str, Any], project_path: Path | None = None) -> None:
    """Save playlist/randomization groups configuration to YAML.

    Args:
        playlist_groups: Playlist groups configuration dict
        project_path: If provided, saves to project/config/playlist_groups.yml

    Format:
    {
        "R1": {
            "label": "Randomization 1",
            "music_order": ["music_1", "music_3", "music_2"]
        },
        "R2": {
            "label": "Randomization 2",
            "music_order": ["music_2", "music_1", "music_3"]
        }
    }
    """
    if not project_path:
        ensure_config_dir()
    target = _get_config_path("playlist_groups.yml", project_path)
    with open(target, "w", encoding="utf-8") as f:
        yaml.safe_dump(playlist_groups, f, default_flow_style=False, allow_unicode=True)


def load_playlist_groups(project_path: Path | None = None) -> dict[str, Any]:
    """Load playlist/randomization groups configuration from YAML.

    Args:
        project_path: If provided, loads from project/config/playlist_groups.yml

    Returns:
        Playlist groups configuration dict, or empty dict if not found
    """
    target = _get_config_path("playlist_groups.yml", project_path)
    if not target.exists():
        return {}
    with open(target, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# --- Music Labels ---

def save_music_labels(music_labels: dict[str, Any], project_path: Path | None = None) -> None:
    """Save music labels configuration to YAML.

    Args:
        music_labels: Music labels configuration dict
        project_path: If provided, saves to project/config/music_labels.yml

    Format:
    {
        "music_1": {
            "label": "Music 1",
            "description": "Brandenburg Concerto No. 3 - Bach"
        },
        "music_2": {
            "label": "Music 2",
            "description": "Moonlight Sonata - Beethoven"
        }
    }
    """
    if not project_path:
        ensure_config_dir()
    target = _get_config_path("music_labels.yml", project_path)
    with open(target, "w", encoding="utf-8") as f:
        yaml.safe_dump(music_labels, f, default_flow_style=False, allow_unicode=True)


def load_music_labels(project_path: Path | None = None) -> dict[str, Any]:
    """Load music labels configuration from YAML.

    Args:
        project_path: If provided, loads from project/config/music_labels.yml

    Returns:
        Music labels configuration dict, or empty dict if not found
    """
    target = _get_config_path("music_labels.yml", project_path)
    if not target.exists():
        return {}
    with open(target, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# --- Protocol ---

def save_protocol(protocol: dict[str, Any], project_path: Path | None = None) -> None:
    """Save protocol configuration to YAML.

    Args:
        protocol: Protocol configuration dict
        project_path: If provided, saves to project/config/protocol.yml

    Format:
    {
        "expected_duration_min": 90.0,
        "section_length_min": 5.0,
        "pre_pause_sections": 9,
        "post_pause_sections": 9,
        "min_section_duration_min": 4.0,
        "min_section_beats": 100,
        "mismatch_strategy": "flag_only"
    }
    """
    if not project_path:
        ensure_config_dir()
    target = _get_config_path("protocol.yml", project_path)
    with open(target, "w", encoding="utf-8") as f:
        yaml.safe_dump(protocol, f, default_flow_style=False, allow_unicode=True)


def load_protocol(project_path: Path | None = None) -> dict[str, Any]:
    """Load protocol configuration from YAML.

    Args:
        project_path: If provided, loads from project/config/protocol.yml

    Returns:
        Protocol configuration dict with defaults for missing keys
    """
    target = _get_config_path("protocol.yml", project_path)
    if not target.exists():
        return {
            "expected_duration_min": 90.0,
            "section_length_min": 5.0,
            "pre_pause_sections": 9,
            "post_pause_sections": 9,
            "min_section_duration_min": 4.0,
            "min_section_beats": 100,
            "mismatch_strategy": "flag_only",
        }
    with open(target, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# --- Participant Events ---

def save_participant_events(
    participant_id: str,
    events_data: dict[str, Any],
    data_dir: str | None = None,
    project_path: Path | None = None,
) -> None:
    """Save participant events (edited events) to YAML.

    Storage priority:
    1. If project_path provided: saves to project/processed/{participant_id}_events.yml
    2. If data_dir provided: saves to {data_dir}/../processed/{participant_id}_events.yml
    3. Otherwise: saves to ~/.rrational/participant_events.yml (fallback)

    This keeps event data with the project for portability.
    """
    # Convert EventStatus objects to serializable dicts
    serialized = {"events": [], "manual": [], "music_events": [], "exclusion_zones": []}

    for key in ["events", "manual", "music_events"]:
        for evt in events_data.get(key, []):
            evt_dict = {
                "raw_label": getattr(evt, "raw_label", str(evt)),
                "canonical": getattr(evt, "canonical", None),
                "first_timestamp": getattr(evt, "first_timestamp", None),
                "last_timestamp": getattr(evt, "last_timestamp", None),
            }
            # Convert datetime to ISO string for YAML
            if evt_dict["first_timestamp"]:
                evt_dict["first_timestamp"] = evt_dict["first_timestamp"].isoformat()
            if evt_dict["last_timestamp"]:
                evt_dict["last_timestamp"] = evt_dict["last_timestamp"].isoformat()
            serialized[key].append(evt_dict)

    # Handle exclusion zones (already dicts with serializable data)
    for zone in events_data.get("exclusion_zones", []):
        zone_dict = {
            "start": zone.get("start"),
            "end": zone.get("end"),
            "reason": zone.get("reason", ""),
            "exclude_from_duration": zone.get("exclude_from_duration", True),
        }
        # Convert datetime to ISO string if needed
        if zone_dict["start"] and hasattr(zone_dict["start"], "isoformat"):
            zone_dict["start"] = zone_dict["start"].isoformat()
        if zone_dict["end"] and hasattr(zone_dict["end"], "isoformat"):
            zone_dict["end"] = zone_dict["end"].isoformat()
        serialized["exclusion_zones"].append(zone_dict)

    # Determine save location (priority: project > data_dir > global)
    if project_path:
        processed_dir = Path(project_path) / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        participant_file = processed_dir / f"{participant_id}_events.yml"

        output_data = {
            "participant_id": participant_id,
            "format_version": "1.0",
            "source_type": "rrational_toolkit",
            **serialized
        }

        with open(participant_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(output_data, f, default_flow_style=False, allow_unicode=True)

    elif data_dir:
        # Save to processed folder (portable with project)
        data_path = Path(data_dir)
        processed_dir = data_path.parent / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)

        participant_file = processed_dir / f"{participant_id}_events.yml"

        output_data = {
            "participant_id": participant_id,
            "format_version": "1.0",
            "source_type": "rrational_toolkit",
            **serialized
        }

        with open(participant_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(output_data, f, default_flow_style=False, allow_unicode=True)
    else:
        # Fallback: save to app config (no project folder available)
        ensure_config_dir()

        all_events = {}
        if PARTICIPANT_EVENTS_FILE.exists():
            with open(PARTICIPANT_EVENTS_FILE, "r", encoding="utf-8") as f:
                all_events = yaml.safe_load(f) or {}

        all_events[participant_id] = serialized

        with open(PARTICIPANT_EVENTS_FILE, "w", encoding="utf-8") as f:
            yaml.safe_dump(all_events, f, default_flow_style=False, allow_unicode=True)


def load_participant_events(
    participant_id: str,
    data_dir: str | None = None,
    project_path: Path | None = None,
) -> dict[str, Any] | None:
    """Load saved participant events from YAML.

    Storage priority:
    1. If project_path provided: checks project/processed/{participant_id}_events.yml
    2. If data_dir provided: checks {data_dir}/../processed/{participant_id}_events.yml
    3. Falls back to ~/.rrational/participant_events.yml

    Returns None if no saved events exist for this participant.
    """
    # First, try to load from project folder
    if project_path:
        processed_dir = Path(project_path) / "processed"
        participant_file = processed_dir / f"{participant_id}_events.yml"

        if participant_file.exists():
            with open(participant_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            # Remove metadata fields before returning
            data.pop("participant_id", None)
            data.pop("format_version", None)
            data.pop("source_type", None)
            return data

    # Try to load from data_dir processed folder
    if data_dir:
        data_path = Path(data_dir)
        processed_dir = data_path.parent / "processed"
        participant_file = processed_dir / f"{participant_id}_events.yml"

        if participant_file.exists():
            with open(participant_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            # Remove metadata fields before returning
            data.pop("participant_id", None)
            data.pop("format_version", None)
            data.pop("source_type", None)
            return data

    # Fall back to app config
    if not PARTICIPANT_EVENTS_FILE.exists():
        return None

    with open(PARTICIPANT_EVENTS_FILE, "r", encoding="utf-8") as f:
        all_events = yaml.safe_load(f) or {}

    if participant_id not in all_events:
        return None

    return all_events[participant_id]


def delete_participant_events(
    participant_id: str,
    data_dir: str | None = None,
    project_path: Path | None = None,
) -> bool:
    """Delete saved events for a participant (reset to original).

    Deletes from all locations for backwards compatibility:
    - project/processed/{participant_id}_events.yml (project folder)
    - {data_dir}/../processed/{participant_id}_events.yml (data folder)
    - ~/.rrational/participant_events.yml (app config)

    Returns True if events were deleted from any location, False if none existed.
    """
    deleted_any = False

    # Delete from project folder
    if project_path:
        processed_dir = Path(project_path) / "processed"
        participant_file = processed_dir / f"{participant_id}_events.yml"

        if participant_file.exists():
            participant_file.unlink()
            deleted_any = True

    # Delete from data_dir processed folder
    if data_dir:
        data_path = Path(data_dir)
        processed_dir = data_path.parent / "processed"
        participant_file = processed_dir / f"{participant_id}_events.yml"

        if participant_file.exists():
            participant_file.unlink()
            deleted_any = True

    # Delete from app config
    if PARTICIPANT_EVENTS_FILE.exists():
        with open(PARTICIPANT_EVENTS_FILE, "r", encoding="utf-8") as f:
            all_events = yaml.safe_load(f) or {}

        if participant_id in all_events:
            del all_events[participant_id]

            with open(PARTICIPANT_EVENTS_FILE, "w", encoding="utf-8") as f:
                yaml.safe_dump(all_events, f, default_flow_style=False, allow_unicode=True)

            deleted_any = True

    return deleted_any


def list_saved_participant_events() -> list[str]:
    """List all participant IDs that have saved events."""
    if not PARTICIPANT_EVENTS_FILE.exists():
        return []

    with open(PARTICIPANT_EVENTS_FILE, "r", encoding="utf-8") as f:
        all_events = yaml.safe_load(f) or {}

    return list(all_events.keys())


# --- Settings (always global) ---

def save_settings(settings: dict[str, Any]) -> None:
    """Save application settings to YAML.

    Settings are always saved to ~/.rrational/settings.yml (global).

    Format:
    {
        "data_folder": "/path/to/data",
        "plot_resolution": 5000,
        "plot_options": {...},
        "recent_projects": [...]
    }
    """
    ensure_config_dir()
    # Merge with defaults to ensure all keys exist
    merged = {**DEFAULT_SETTINGS, **settings}
    if "plot_options" in settings:
        merged["plot_options"] = {**DEFAULT_SETTINGS["plot_options"], **settings["plot_options"]}
        # Also merge nested colors within plot_options
        if "colors" in settings["plot_options"]:
            merged["plot_options"]["colors"] = {
                **DEFAULT_SETTINGS["plot_options"]["colors"],
                **settings["plot_options"]["colors"]
            }
        else:
            merged["plot_options"]["colors"] = DEFAULT_SETTINGS["plot_options"]["colors"].copy()
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(merged, f, default_flow_style=False, allow_unicode=True)


def load_settings() -> dict[str, Any]:
    """Load application settings from YAML, with defaults for missing keys."""
    if not SETTINGS_FILE.exists():
        return DEFAULT_SETTINGS.copy()

    with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
        saved = yaml.safe_load(f) or {}

    # Merge with defaults to handle missing keys
    result = {**DEFAULT_SETTINGS, **saved}
    if "plot_options" in saved:
        result["plot_options"] = {**DEFAULT_SETTINGS["plot_options"], **saved.get("plot_options", {})}
        # Also merge nested colors within plot_options
        saved_colors = saved.get("plot_options", {}).get("colors", {})
        result["plot_options"]["colors"] = {
            **DEFAULT_SETTINGS["plot_options"]["colors"],
            **saved_colors
        }
    else:
        result["plot_options"] = DEFAULT_SETTINGS["plot_options"].copy()

    return result


def get_setting(key: str, default: Any = None) -> Any:
    """Get a single setting value."""
    settings = load_settings()
    if "." in key:
        # Support nested keys like "plot_options.show_events"
        parts = key.split(".")
        value = settings
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return default
        return value if value is not None else default
    return settings.get(key, default)


def save_last_project(project_path: str | Path | None) -> None:
    """Save the last used project path for auto-load on startup.

    Args:
        project_path: Path to the project, or None/empty to clear
    """
    settings = load_settings()
    settings["last_project"] = str(project_path) if project_path else ""
    save_settings(settings)


def get_last_project() -> str | None:
    """Get the last used project path.

    Returns:
        Path to last project, or None if not set or doesn't exist
    """
    last = get_setting("last_project", "")
    if last and Path(last).exists():
        return last
    return None


# --- Processed Directory ---

def get_processed_dir(
    data_dir: str | Path | None = None,
    project_path: Path | None = None,
) -> Path:
    """Get the processed directory path for storing .rrational files and artifacts.

    Args:
        data_dir: The data directory path (e.g., project/data/raw)
        project_path: Project path (takes priority if provided)

    Priority:
    1. If project_path: returns project/data/processed/
    2. If data_dir: returns {data_dir}/../processed/ (sibling to raw folder)
    3. Otherwise: returns ~/.rrational/exports/

    Returns:
        Path to the processed directory (created if needed)
    """
    if project_path:
        processed_dir = Path(project_path) / "data" / "processed"
    elif data_dir:
        processed_dir = Path(data_dir).parent / "processed"
    else:
        processed_dir = CONFIG_DIR / "exports"

    processed_dir.mkdir(parents=True, exist_ok=True)
    return processed_dir


def list_ready_files_for_participant(
    participant_id: str,
    data_dir: str | Path | None = None,
    project_path: Path | None = None,
) -> list[Path]:
    """List all .rrational ready files for a participant.

    Convenience wrapper around rrational_export.find_rrational_files()
    for API consistency with other persistence functions.

    Args:
        participant_id: The participant ID to find files for
        data_dir: Optional data directory to search
        project_path: Project path (takes priority if provided)

    Returns:
        List of .rrational file paths, sorted by modification time (newest first)
    """
    from rrational.gui.rrational_export import find_rrational_files
    return find_rrational_files(participant_id, data_dir, project_path)


# --- Artifact Corrections ---

def save_artifact_corrections(
    participant_id: str,
    manual_artifacts: list[dict],
    artifact_exclusions: set[int] | list[int],
    data_dir: str | None = None,
    project_path: Path | None = None,
    algorithm_artifacts: list[int] | None = None,
    algorithm_method: str | None = None,
    algorithm_threshold: float | None = None,
    scope: dict | None = None,
    section_key: str = "_full",
    segment_beats: int | None = None,
    indices_by_type: dict[str, list[int]] | None = None,
) -> Path:
    """Save artifact corrections (algorithm-detected, manual markings, and exclusions) to YAML.

    Artifacts are stored per-section, allowing independent detection for different parts
    of the recording. The section_key identifies which section these artifacts belong to.

    NOTE: This file stores ONLY artifact information (indices, method, etc.), NOT the
    corrected RR intervals. Use save_nn_intervals() for the corrected data.

    Storage priority:
    1. If project_path provided: saves to project/data/processed/{participant_id}_artifacts.yml
    2. If data_dir provided: saves to {data_dir}/../processed/{participant_id}_artifacts.yml
    3. Otherwise: saves to ~/.rrational/{participant_id}_artifacts.yml (fallback)

    Args:
        participant_id: The participant ID
        manual_artifacts: List of manually marked artifacts (dicts with original_idx, timestamp, rr_value, etc.)
        artifact_exclusions: Set of original indices for excluded detected artifacts
        data_dir: Optional data directory
        project_path: Project path (takes priority if provided)
        algorithm_artifacts: List of indices detected by algorithm (optional)
        algorithm_method: Detection method used (e.g., "threshold", "malik")
        algorithm_threshold: Threshold value used for detection
        scope: Detection scope info (type, name/range, offset) (optional)
        section_key: Section identifier ("_full" for full recording, or section name like "rest_pre")
        segment_beats: Segment size used for segmented methods (optional)
        indices_by_type: Dict mapping artifact type to list of indices (ectopic, missed, extra, longshort)

    Returns:
        Path to the saved file
    """
    from datetime import datetime

    # Use the same processed directory as .rrational files
    processed_dir = get_processed_dir(data_dir=data_dir, project_path=project_path)
    artifact_file = processed_dir / f"{participant_id}_artifacts.yml"

    # Load existing data if file exists (to preserve other sections)
    existing_data = {}
    if artifact_file.exists():
        try:
            with open(artifact_file, "r", encoding="utf-8") as f:
                existing_data = yaml.safe_load(f) or {}
        except Exception:
            existing_data = {}

    # Migrate old format (v1.2 and earlier) to new section-based format (v1.3)
    if existing_data.get("format_version", "1.0") < "1.3" and "sections" not in existing_data:
        # Old format had artifacts at root level - migrate to "_full" section
        if "algorithm_artifact_indices" in existing_data or "manual_artifacts" in existing_data:
            old_section_data = {
                "algorithm_artifact_indices": existing_data.get("algorithm_artifact_indices", []),
                "algorithm_method": existing_data.get("algorithm_method"),
                "algorithm_threshold": existing_data.get("algorithm_threshold"),
                "manual_artifacts": existing_data.get("manual_artifacts", []),
                "excluded_artifact_indices": existing_data.get("excluded_artifact_indices", []),
                "scope": existing_data.get("scope"),
                "saved_at": existing_data.get("saved_at"),
            }
            existing_data = {
                "participant_id": participant_id,
                "format_version": "1.3",
                "source_type": "rrational_toolkit",
                "sections": {"_full": old_section_data},
            }

    # Ensure sections dict exists
    if "sections" not in existing_data:
        existing_data["sections"] = {}

    # Build section data
    section_data = {
        "algorithm_artifact_indices": list(algorithm_artifacts) if algorithm_artifacts is not None else [],
        "algorithm_method": algorithm_method,
        "algorithm_threshold": algorithm_threshold,
        "manual_artifacts": manual_artifacts,
        "excluded_artifact_indices": list(artifact_exclusions) if artifact_exclusions else [],
        "scope": scope,
        "saved_at": datetime.now().isoformat(),
    }

    # Add optional fields
    if segment_beats is not None:
        section_data["segment_beats"] = segment_beats
    if indices_by_type is not None:
        section_data["indices_by_type"] = indices_by_type

    # Handle overlapping sections: newer detection replaces overlapping older ones
    # Rule 1: Saving "_full" clears all section-specific artifacts (full replaces everything)
    # Rule 2: Saving a specific section clears "_full" (section-specific invalidates full)
    if section_key == "_full":
        # Clear all other sections - full recording detection replaces everything
        existing_data["sections"] = {}
    else:
        # Clear "_full" if it exists - we're now doing section-specific detection
        if "_full" in existing_data["sections"]:
            del existing_data["sections"]["_full"]

    # Update section in existing data
    existing_data["sections"][section_key] = section_data
    existing_data["participant_id"] = participant_id
    existing_data["format_version"] = "1.3"
    existing_data["source_type"] = "rrational_toolkit"
    existing_data["last_modified"] = datetime.now().isoformat()

    with open(artifact_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(existing_data, f, default_flow_style=False, allow_unicode=True)

    return artifact_file


def load_artifact_corrections(
    participant_id: str,
    data_dir: str | None = None,
    project_path: Path | None = None,
    section_key: str | None = None,
) -> dict[str, Any] | None:
    """Load saved artifact corrections from YAML.

    Uses the same processed directory as .rrational files (via get_processed_dir).
    Also checks ~/.rrational/ as fallback for legacy files.

    Args:
        participant_id: The participant ID
        data_dir: Optional data directory
        project_path: Project path (takes priority if provided)
        section_key: If provided, loads only this section. If None, returns all sections data.

    Returns:
        For v1.3+ files with section_key specified:
            Dict with section's artifact data (algorithm_artifact_indices, manual_artifacts, etc.)
        For v1.3+ files without section_key:
            Dict with 'sections' containing all sections, plus 'format_version' and metadata
        For legacy files (v1.2 and earlier):
            Dict with 'manual_artifacts' (list), 'excluded_artifact_indices' (list),
            and optionally other fields
        Returns None if no saved corrections exist.
    """
    # Primary location: same as .rrational files
    processed_dir = get_processed_dir(data_dir=data_dir, project_path=project_path)
    artifact_file = processed_dir / f"{participant_id}_artifacts.yml"

    # Also check legacy location as fallback
    search_paths = [artifact_file, CONFIG_DIR / f"{participant_id}_artifacts.yml"]

    for artifact_file in search_paths:
        if artifact_file.exists():
            with open(artifact_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            # Handle v1.3+ format with sections
            if data.get("format_version", "1.0") >= "1.3" and "sections" in data:
                if section_key is not None:
                    # Return specific section data
                    section_data = data.get("sections", {}).get(section_key)
                    if section_data:
                        return {
                            "manual_artifacts": section_data.get("manual_artifacts", []),
                            "excluded_artifact_indices": section_data.get("excluded_artifact_indices", []),
                            "algorithm_artifact_indices": section_data.get("algorithm_artifact_indices", []),
                            "algorithm_method": section_data.get("algorithm_method"),
                            "algorithm_threshold": section_data.get("algorithm_threshold"),
                            "scope": section_data.get("scope"),
                            "segment_beats": section_data.get("segment_beats"),
                            "indices_by_type": section_data.get("indices_by_type", {}),
                            "saved_at": section_data.get("saved_at"),
                            "section_key": section_key,
                        }
                    return None
                else:
                    # Return full data with sections
                    return {
                        "format_version": data.get("format_version", "1.3"),
                        "sections": data.get("sections", {}),
                        "last_modified": data.get("last_modified"),
                    }

            # Legacy format (v1.2 and earlier) - no sections
            result = {
                "manual_artifacts": data.get("manual_artifacts", []),
                "excluded_artifact_indices": data.get("excluded_artifact_indices", []),
                "saved_at": data.get("saved_at"),
                "section_key": "_full",  # Legacy data is always full recording
            }

            # Include algorithm artifacts if present (format version 1.1+)
            if "algorithm_artifact_indices" in data:
                result["algorithm_artifact_indices"] = data.get("algorithm_artifact_indices", [])
                result["algorithm_method"] = data.get("algorithm_method")
                result["algorithm_threshold"] = data.get("algorithm_threshold")

            # Include scope and corrected_rr if present (format version 1.2+)
            if "scope" in data:
                result["scope"] = data.get("scope")
            if "corrected_rr" in data:
                result["corrected_rr"] = data.get("corrected_rr")

            return result

    return None


def list_artifact_sections(
    participant_id: str,
    data_dir: str | None = None,
    project_path: Path | None = None,
) -> list[str]:
    """List all sections that have saved artifact data for a participant.

    Returns:
        List of section keys (e.g., ["_full", "rest_pre", "music_1"])
        Returns empty list if no artifact data exists.
    """
    data = load_artifact_corrections(participant_id, data_dir, project_path, section_key=None)
    if data is None:
        return []

    # v1.3+ format with sections
    if "sections" in data:
        return list(data["sections"].keys())

    # Legacy format - only has full recording
    return ["_full"]


def get_merged_artifacts_for_display(
    participant_id: str,
    data_dir: str | None = None,
    project_path: Path | None = None,
) -> dict[str, Any]:
    """Get merged artifact data from all sections for display on plot.

    This combines artifacts from all sections into a single dict for plotting,
    while tracking which section each artifact belongs to.

    Returns:
        Dict with:
        - 'algorithm_artifact_indices': list of all algorithm-detected artifact indices
        - 'manual_artifacts': list of all manual artifacts
        - 'excluded_artifact_indices': list of all excluded indices
        - 'sections_info': dict mapping section_key to summary info
    """
    data = load_artifact_corrections(participant_id, data_dir, project_path, section_key=None)
    if data is None:
        return {
            "algorithm_artifact_indices": [],
            "manual_artifacts": [],
            "excluded_artifact_indices": [],
            "sections_info": {},
        }

    all_algo = []
    all_manual = []
    all_excluded = []
    sections_info = {}

    # v1.3+ format with sections
    if "sections" in data:
        for section_key, section_data in data["sections"].items():
            algo_indices = section_data.get("algorithm_artifact_indices", [])
            manual = section_data.get("manual_artifacts", [])
            excluded = section_data.get("excluded_artifact_indices", [])

            all_algo.extend(algo_indices)
            all_manual.extend(manual)
            all_excluded.extend(excluded)

            sections_info[section_key] = {
                "algorithm_count": len(algo_indices),
                "manual_count": len(manual),
                "excluded_count": len(excluded),
                "method": section_data.get("algorithm_method"),
                "scope": section_data.get("scope"),
                "saved_at": section_data.get("saved_at"),
            }
    else:
        # Legacy format
        all_algo = data.get("algorithm_artifact_indices", [])
        all_manual = data.get("manual_artifacts", [])
        all_excluded = data.get("excluded_artifact_indices", [])
        sections_info["_full"] = {
            "algorithm_count": len(all_algo),
            "manual_count": len(all_manual),
            "excluded_count": len(all_excluded),
            "method": data.get("algorithm_method"),
            "scope": data.get("scope"),
            "saved_at": data.get("saved_at"),
        }

    return {
        "algorithm_artifact_indices": all_algo,
        "manual_artifacts": all_manual,
        "excluded_artifact_indices": all_excluded,
        "sections_info": sections_info,
    }


def delete_artifact_corrections(
    participant_id: str,
    data_dir: str | None = None,
    project_path: Path | None = None,
) -> bool:
    """Delete saved artifact corrections for a participant.

    Returns True if corrections were deleted, False if none existed.
    """
    deleted_any = False

    # Primary location: same as .rrational files
    processed_dir = get_processed_dir(data_dir=data_dir, project_path=project_path)
    delete_paths = [
        processed_dir / f"{participant_id}_artifacts.yml",
        CONFIG_DIR / f"{participant_id}_artifacts.yml",  # Legacy fallback
    ]

    for artifact_file in delete_paths:
        if artifact_file.exists():
            artifact_file.unlink()
            deleted_any = True

    return deleted_any


def load_artifact_corrections_from_rrational(
    rrational_file: Path,
) -> dict[str, Any] | None:
    """Load artifact markings from a .rrational export file.

    This allows restoring artifact markings from a previously exported file
    when no _artifacts.yml exists (fallback).

    Args:
        rrational_file: Path to the .rrational file

    Returns:
        Dict with 'manual_artifacts' (list) and 'excluded_artifact_indices' (list),
        or None if file doesn't exist or has no artifact data.
    """
    if not rrational_file.exists():
        return None

    try:
        with open(rrational_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        processing = data.get("processing", {})
        manual_artifacts = processing.get("manual_artifacts", [])
        excluded_indices = processing.get("excluded_detected_indices", [])

        # Convert ManualArtifact format to session state format
        converted_manual = []
        for ma in manual_artifacts:
            converted_manual.append({
                "original_idx": ma.get("original_idx", 0),
                "timestamp": ma.get("timestamp", ""),
                "rr_value": ma.get("rr_value", 0),
                "source": ma.get("source", "manual"),
                "plot_idx": ma.get("original_idx", 0),  # Use original_idx as plot_idx
            })

        if converted_manual or excluded_indices:
            return {
                "manual_artifacts": converted_manual,
                "excluded_artifact_indices": excluded_indices,
                "source_file": str(rrational_file),
            }

        return None

    except Exception:
        return None


# --- Section Validations (explicit per-participant storage) ---

def save_section_validations(
    participant_id: str,
    group: str,
    section_validations: dict[str, Any],
    data_dir: str | None = None,
    project_path: Path | None = None,
) -> Path:
    """Save explicit section validation state for a participant.

    This provides robust storage of section validation choices, independent of
    session state. Each participant's validations are stored in a dedicated file.

    Storage location:
    1. If project_path: project/data/processed/{participant_id}_section_validations.yml
    2. If data_dir: {data_dir}/../processed/{participant_id}_section_validations.yml
    3. Otherwise: ~/.rrational/{participant_id}_section_validations.yml

    Args:
        participant_id: The participant ID
        group: The group this participant belongs to
        section_validations: Dict mapping section_name to validation state:
            {
                "rest_pre": {
                    "is_valid": True,
                    "start_event": {
                        "canonical": "rest_pre_start",
                        "raw_label": "Ruhe Anfang",
                        "timestamp": "2024-01-01T10:00:00",
                        "index": 0  # Which candidate was selected
                    },
                    "end_event": {
                        "canonical": "rest_pre_end",
                        "raw_label": "Ruhe Ende",
                        "timestamp": "2024-01-01T10:05:00",
                        "index": 0
                    },
                    "manually_selected": False,
                    "missing_start": False,
                    "missing_end": False,
                    "needs_disambiguation": False,
                    "start_candidates_count": 1,
                    "end_candidates_count": 1,
                    "duration_s": 300.0,
                    "beat_count": 350
                },
                ...
            }
        data_dir: Optional data directory
        project_path: Project path (takes priority if provided)

    Returns:
        Path to the saved file
    """
    from datetime import datetime as dt

    # Determine save location
    processed_dir = get_processed_dir(data_dir=data_dir, project_path=project_path)
    validation_file = processed_dir / f"{participant_id}_section_validations.yml"

    # Build output data structure
    output_data = {
        "participant_id": participant_id,
        "group": group,
        "format_version": "1.0",
        "saved_at": dt.now().isoformat(),
        "sections": section_validations,
    }

    with open(validation_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(output_data, f, default_flow_style=False, allow_unicode=True)

    return validation_file


def load_section_validations(
    participant_id: str,
    data_dir: str | None = None,
    project_path: Path | None = None,
) -> dict[str, Any] | None:
    """Load saved section validation state for a participant.

    Returns:
        Dict with:
        - 'group': str - The group the participant belongs to
        - 'sections': dict - Section validation states (see save_section_validations)
        - 'saved_at': str - ISO timestamp of when validations were saved

        Returns None if no saved validations exist.
    """
    # Primary location: processed directory
    processed_dir = get_processed_dir(data_dir=data_dir, project_path=project_path)
    validation_file = processed_dir / f"{participant_id}_section_validations.yml"

    # Also check legacy/fallback locations
    search_paths = [
        validation_file,
        CONFIG_DIR / f"{participant_id}_section_validations.yml",
    ]

    for file_path in search_paths:
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}

                return {
                    "group": data.get("group", ""),
                    "sections": data.get("sections", {}),
                    "saved_at": data.get("saved_at"),
                    "format_version": data.get("format_version", "1.0"),
                }
            except Exception:
                continue

    return None


def delete_section_validations(
    participant_id: str,
    data_dir: str | None = None,
    project_path: Path | None = None,
) -> bool:
    """Delete saved section validations for a participant.

    Returns True if validations were deleted, False if none existed.
    """
    deleted_any = False

    # Check all possible locations
    processed_dir = get_processed_dir(data_dir=data_dir, project_path=project_path)
    delete_paths = [
        processed_dir / f"{participant_id}_section_validations.yml",
        CONFIG_DIR / f"{participant_id}_section_validations.yml",
    ]

    for file_path in delete_paths:
        if file_path.exists():
            file_path.unlink()
            deleted_any = True

    return deleted_any


def list_participants_with_section_validations(
    data_dir: str | None = None,
    project_path: Path | None = None,
) -> list[str]:
    """List all participant IDs that have saved section validations.

    Returns:
        List of participant IDs
    """
    participants = []

    # Check processed directory
    processed_dir = get_processed_dir(data_dir=data_dir, project_path=project_path)
    if processed_dir.exists():
        for file_path in processed_dir.glob("*_section_validations.yml"):
            # Extract participant ID from filename
            pid = file_path.stem.replace("_section_validations", "")
            if pid:
                participants.append(pid)

    # Also check legacy location
    if CONFIG_DIR.exists():
        for file_path in CONFIG_DIR.glob("*_section_validations.yml"):
            pid = file_path.stem.replace("_section_validations", "")
            if pid and pid not in participants:
                participants.append(pid)

    return sorted(participants)


# --- NN Intervals (corrected intervals per section) ---

def save_nn_intervals(
    participant_id: str,
    section_name: str,
    nn_data: dict[str, Any],
    data_dir: str | None = None,
    project_path: Path | None = None,
) -> Path:
    """Save corrected NN intervals for a participant's section.

    This stores the artifact-corrected (interpolated) NN intervals that are
    ready for HRV analysis. Data is saved in two files:

    1. CSV file: `{participant_id}_{section}_nn.csv` - the actual interval data
       Columns: beat_idx, timestamp_ms, nn_ms, was_corrected

    2. Metadata file: `{participant_id}_nn_metadata.yml` - correction info for all sections
       Contains: correction_method, timestamps, beat counts, correction details

    Storage location:
    1. If project_path: project/data/processed/
    2. If data_dir: {data_dir}/../processed/
    3. Otherwise: ~/.rrational/ (fallback)

    Args:
        participant_id: The participant ID
        section_name: The section name (e.g., "rest_pre", "music_1")
        nn_data: Dict containing the NN interval data for this section:
            {
                "correction_method": "kubios",  # or "none" if no correction
                "corrected_at": "2026-01-18T14:55:00",  # ISO timestamp
                "original_beat_count": 352,
                "artifacts_removed": 4,
                "intervals_corrected": 3,  # How many were interpolated
                "final_nn_count": 348,
                "intervals": [
                    # Compact format: [timestamp_ms_from_section_start, nn_ms, was_corrected]
                    [0, 850, False],
                    [850, 858, False],
                    [1708, 855, True],  # This one was corrected
                    # ...
                ],
                "corrections": [
                    # Details for corrected intervals
                    {"nn_idx": 35, "original_rr_ms": 1250, "corrected_nn_ms": 855},
                    # ...
                ],
            }
        data_dir: Optional data directory
        project_path: Project path (takes priority if provided)

    Returns:
        Path to the CSV file
    """
    from datetime import datetime as dt

    # Determine save location
    processed_dir = get_processed_dir(data_dir=data_dir, project_path=project_path)

    # Save CSV file with interval data
    csv_file = processed_dir / f"{participant_id}_{section_name}_nn.csv"
    intervals = nn_data.get("intervals", [])

    with open(csv_file, "w", encoding="utf-8", newline="") as f:
        f.write("beat_idx,timestamp_ms,nn_ms,was_corrected\n")
        for i, interval in enumerate(intervals):
            if len(interval) >= 3:
                ts_ms, nn_ms, was_corrected = interval[0], interval[1], interval[2]
                f.write(f"{i},{ts_ms},{nn_ms},{str(was_corrected).lower()}\n")

    # Save/update metadata file
    metadata_file = processed_dir / f"{participant_id}_nn_metadata.yml"

    if metadata_file.exists():
        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = yaml.safe_load(f) or {}
    else:
        metadata = {
            "participant_id": participant_id,
            "format_version": "2.0",
            "created_at": dt.now().isoformat(),
            "sections": {},
        }

    # Store metadata for this section (without the intervals - those are in CSV)
    section_metadata = {
        "correction_method": nn_data.get("correction_method"),
        "corrected_at": nn_data.get("corrected_at"),
        "original_beat_count": nn_data.get("original_beat_count"),
        "artifacts_removed": nn_data.get("artifacts_removed"),
        "intervals_corrected": nn_data.get("intervals_corrected"),
        "final_nn_count": nn_data.get("final_nn_count"),
        "corrections": nn_data.get("corrections", []),
        "csv_file": csv_file.name,
    }
    metadata["sections"][section_name] = section_metadata
    metadata["last_modified"] = dt.now().isoformat()

    with open(metadata_file, "w", encoding="utf-8") as f:
        yaml.safe_dump(metadata, f, default_flow_style=False, allow_unicode=True)

    return csv_file


def load_nn_intervals(
    participant_id: str,
    section_name: str | None = None,
    data_dir: str | None = None,
    project_path: Path | None = None,
) -> dict[str, Any] | None:
    """Load corrected NN intervals for a participant.

    Supports both v2.0 format (CSV + metadata) and legacy v1.0 format (single YAML).

    Args:
        participant_id: The participant ID
        section_name: If provided, returns only that section's data.
                      If None, returns all sections.
        data_dir: Optional data directory
        project_path: Project path (takes priority if provided)

    Returns:
        If section_name is provided:
            Dict with the section's NN data (including 'intervals' list), or None if not found.
        If section_name is None:
            Dict with:
            - 'sections': dict mapping section_name -> NN data
            - 'last_modified': str - ISO timestamp
            - 'format_version': str

            Returns None if no saved NN intervals exist.
    """
    processed_dir = get_processed_dir(data_dir=data_dir, project_path=project_path)

    # Try v2.0 format first (metadata YAML + CSV files)
    metadata_file = processed_dir / f"{participant_id}_nn_metadata.yml"
    if metadata_file.exists():
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = yaml.safe_load(f) or {}

            if section_name:
                # Load specific section
                section_meta = metadata.get("sections", {}).get(section_name)
                if section_meta:
                    # Load intervals from CSV
                    csv_file = processed_dir / f"{participant_id}_{section_name}_nn.csv"
                    if csv_file.exists():
                        intervals = _load_nn_csv(csv_file)
                        return {**section_meta, "intervals": intervals}
                return None
            else:
                # Load all sections
                sections = {}
                for sec_name, sec_meta in metadata.get("sections", {}).items():
                    csv_file = processed_dir / f"{participant_id}_{sec_name}_nn.csv"
                    if csv_file.exists():
                        intervals = _load_nn_csv(csv_file)
                        sections[sec_name] = {**sec_meta, "intervals": intervals}
                    else:
                        sections[sec_name] = sec_meta

                return {
                    "sections": sections,
                    "last_modified": metadata.get("last_modified"),
                    "format_version": metadata.get("format_version", "2.0"),
                }
        except Exception:
            pass

    # Fall back to legacy v1.0 format (single YAML file)
    legacy_paths = [
        processed_dir / f"{participant_id}_nn_intervals.yml",
        CONFIG_DIR / f"{participant_id}_nn_intervals.yml",
    ]

    for file_path in legacy_paths:
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}

                if section_name:
                    sections = data.get("sections", {})
                    return sections.get(section_name)
                else:
                    return {
                        "sections": data.get("sections", {}),
                        "last_modified": data.get("last_modified"),
                        "format_version": data.get("format_version", "1.0"),
                    }
            except Exception:
                continue

    return None


def _load_nn_csv(csv_file: Path) -> list[list]:
    """Load NN intervals from CSV file.

    Returns:
        List of [timestamp_ms, nn_ms, was_corrected] tuples.
    """
    intervals = []
    with open(csv_file, "r", encoding="utf-8") as f:
        next(f)  # Skip header
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 4:
                # beat_idx, timestamp_ms, nn_ms, was_corrected
                ts_ms = int(parts[1])
                nn_ms = float(parts[2])
                was_corrected = parts[3].lower() == "true"
                intervals.append([ts_ms, nn_ms, was_corrected])
    return intervals


def delete_nn_intervals(
    participant_id: str,
    section_name: str | None = None,
    data_dir: str | None = None,
    project_path: Path | None = None,
) -> bool:
    """Delete saved NN intervals for a participant.

    Handles both v2.0 format (CSV + metadata) and legacy v1.0 format (single YAML).

    Args:
        participant_id: The participant ID
        section_name: If provided, deletes only that section's NN data.
                      If None, deletes all NN interval files.
        data_dir: Optional data directory
        project_path: Project path (takes priority if provided)

    Returns:
        True if NN intervals were deleted, False if none existed.
    """
    deleted_any = False
    processed_dir = get_processed_dir(data_dir=data_dir, project_path=project_path)

    # Handle v2.0 format (CSV + metadata)
    metadata_file = processed_dir / f"{participant_id}_nn_metadata.yml"
    if metadata_file.exists():
        if section_name:
            # Delete specific section's CSV and update metadata
            csv_file = processed_dir / f"{participant_id}_{section_name}_nn.csv"
            if csv_file.exists():
                csv_file.unlink()
                deleted_any = True

            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = yaml.safe_load(f) or {}

                if section_name in metadata.get("sections", {}):
                    del metadata["sections"][section_name]
                    metadata["last_modified"] = __import__("datetime").datetime.now().isoformat()

                    with open(metadata_file, "w", encoding="utf-8") as f:
                        yaml.safe_dump(metadata, f, default_flow_style=False, allow_unicode=True)
                    deleted_any = True
            except Exception:
                pass
        else:
            # Delete all CSV files for this participant
            for csv_file in processed_dir.glob(f"{participant_id}_*_nn.csv"):
                csv_file.unlink()
                deleted_any = True
            metadata_file.unlink()
            deleted_any = True

    # Also handle legacy v1.0 format
    legacy_paths = [
        processed_dir / f"{participant_id}_nn_intervals.yml",
        CONFIG_DIR / f"{participant_id}_nn_intervals.yml",
    ]

    for file_path in legacy_paths:
        if file_path.exists():
            if section_name:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}

                    if section_name in data.get("sections", {}):
                        del data["sections"][section_name]
                        data["last_modified"] = __import__("datetime").datetime.now().isoformat()

                        with open(file_path, "w", encoding="utf-8") as f:
                            yaml.safe_dump(data, f, default_flow_style=False, allow_unicode=True)
                        deleted_any = True
                except Exception:
                    pass
            else:
                file_path.unlink()
                deleted_any = True

    return deleted_any


def list_sections_with_nn_intervals(
    participant_id: str,
    data_dir: str | None = None,
    project_path: Path | None = None,
) -> list[str]:
    """List all section names that have saved NN intervals for a participant.

    Returns:
        List of section names that have NN interval data
    """
    data = load_nn_intervals(participant_id, data_dir=data_dir, project_path=project_path)
    if data and "sections" in data:
        return list(data["sections"].keys())
    return []


def get_nn_intervals_summary(
    participant_id: str,
    data_dir: str | None = None,
    project_path: Path | None = None,
) -> dict[str, dict[str, Any]] | None:
    """Get a summary of NN intervals status for all sections.

    Returns:
        Dict mapping section_name to summary:
        {
            "rest_pre": {
                "has_nn": True,
                "nn_count": 348,
                "correction_method": "kubios",
                "corrected_at": "2026-01-18T14:55:00",
            },
            "music_1": {
                "has_nn": False,
            },
        }

        Returns None if no NN intervals file exists.
    """
    data = load_nn_intervals(participant_id, data_dir=data_dir, project_path=project_path)
    if not data:
        return None

    summary = {}
    for section_name, section_data in data.get("sections", {}).items():
        summary[section_name] = {
            "has_nn": True,
            "nn_count": section_data.get("final_nn_count", len(section_data.get("intervals", []))),
            "correction_method": section_data.get("correction_method", "unknown"),
            "corrected_at": section_data.get("corrected_at"),
            "intervals_corrected": section_data.get("intervals_corrected", 0),
        }

    return summary
