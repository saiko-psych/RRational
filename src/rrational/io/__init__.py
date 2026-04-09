"""File ingestion helpers for HRV Logger, VNS Analyse, and generic RR formats."""

from rrational.io.hrv_logger import (
    DEFAULT_ID_PATTERN,
    PREDEFINED_PATTERNS,
    DuplicateInfo,
    EventMarker,
    HRVLoggerRecording,
    RRInterval,
    RecordingBundle,
    discover_recordings,
    extract_participant_id,
    load_events,
    load_recording,
    load_recordings_from_directory,
    load_rr_intervals,
)

from rrational.io.generic_rr import (
    GenericRecording,
    detect_format,
    load_generic_rr,
    SUPPORTED_FORMATS,
)

from rrational.io.vns_analyse import (
    VNSRecording,
    VNSRecordingBundle,
    discover_vns_recordings,
    load_vns_recording,
    load_vns_recordings_from_directory,
)

__all__ = [
    # HRV Logger
    "DEFAULT_ID_PATTERN",
    "PREDEFINED_PATTERNS",
    "DuplicateInfo",
    "EventMarker",
    "HRVLoggerRecording",
    "RRInterval",
    "RecordingBundle",
    "discover_recordings",
    "extract_participant_id",
    "load_events",
    "load_recording",
    "load_recordings_from_directory",
    "load_rr_intervals",
    # Generic RR formats (Polar, Empatica, Elite HRV, Kubios, plain text)
    "GenericRecording",
    "detect_format",
    "load_generic_rr",
    "SUPPORTED_FORMATS",
    # VNS Analyse
    "VNSRecording",
    "VNSRecordingBundle",
    "discover_vns_recordings",
    "load_vns_recording",
    "load_vns_recordings_from_directory",
]
