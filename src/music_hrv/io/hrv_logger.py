"""HRV Logger CSV ingestion utilities."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence

DEFAULT_ID_PATTERN = r"(?P<participant>[A-Za-z0-9]+)"
_RR_REQUIRED_COLUMNS = ("date", "rr")
_EVENT_REQUIRED_COLUMNS = ("annotation", "timestamp")


def _prepare_reader(path: Path) -> csv.DictReader:
    """Return a CSV reader with stripped headers/body."""

    text = path.read_text(encoding="utf-8", errors="ignore")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return csv.DictReader(io.StringIO(text))


def _normalise_row(row: dict[str, str | None]) -> dict[str, str]:
    """Lowercase + strip CSV keys/values for tolerant parsing."""

    return {
        (key.strip().lower() if key else ""): (value or "").strip()
        for key, value in row.items()
    }


@dataclass(slots=True)
class RRInterval:
    """Single beat from the HRV Logger RR CSV."""

    timestamp: datetime | None
    rr_ms: int
    elapsed_ms: int | None


@dataclass(slots=True)
class EventMarker:
    """Marker/annotation extracted from the Events CSV."""

    label: str
    timestamp: datetime | None
    offset_s: float | None


@dataclass(slots=True)
class RecordingBundle:
    """Paired RR + Events file for one participant."""

    participant_id: str
    rr_path: Path
    events_path: Path | None = None


@dataclass(slots=True)
class HRVLoggerRecording:
    """Full HRV Logger recording (RR beats + optional events)."""

    participant_id: str
    rr_intervals: list[RRInterval]
    events: list[EventMarker]


def extract_participant_id(name: str, pattern: str = DEFAULT_ID_PATTERN) -> str:
    """Return the participant identifier derived from file names."""

    stem = Path(name).stem
    regex = re.compile(pattern)
    matches = list(regex.finditer(stem))
    for match in reversed(matches):
        participant = match.groupdict().get("participant")
        if participant:
            return participant
    tokens = re.findall(r"[A-Za-z0-9]+", stem)
    if tokens:
        return tokens[-1]
    return "unknown"


def discover_recordings(
    root: Path, *, pattern: str = DEFAULT_ID_PATTERN
) -> list[RecordingBundle]:
    """Discover RR/Events pairs under the provided root folder."""

    root = root.expanduser().resolve()
    rr_index: dict[str, list[Path]] = {}
    events_index: dict[str, list[Path]] = {}

    for rr_path in sorted(root.rglob("*RR*.csv")):
        participant = extract_participant_id(rr_path.name, pattern)
        rr_index.setdefault(participant, []).append(rr_path)

    for events_path in sorted(root.rglob("*Events*.csv")):
        participant = extract_participant_id(events_path.name, pattern)
        events_index.setdefault(participant, []).append(events_path)

    bundles: list[RecordingBundle] = []
    for participant, paths in sorted(rr_index.items()):
        rr_path = paths[0]
        events_candidates = events_index.get(participant) or []
        bundles.append(
            RecordingBundle(
                participant_id=participant,
                rr_path=rr_path,
                events_path=events_candidates[0] if events_candidates else None,
            )
        )
    return bundles


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S %z")
    except ValueError:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None


def _parse_int(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def load_rr_intervals(rr_path: Path) -> list[RRInterval]:
    """Parse RR CSV rows."""

    intervals: list[RRInterval] = []
    for row in _prepare_reader(rr_path):
        cleaned = _normalise_row(row)
        if not all(col in cleaned for col in _RR_REQUIRED_COLUMNS):
            continue
        timestamp = _parse_datetime(cleaned.get("date"))
        rr_ms = _parse_int(cleaned.get("rr"))
        elapsed_ms = _parse_int(cleaned.get("since start") or cleaned.get("since_start"))
        if rr_ms is None:
            continue
        intervals.append(
            RRInterval(
                timestamp=timestamp,
                rr_ms=rr_ms,
                elapsed_ms=elapsed_ms,
            )
        )
    return intervals


def load_events(events_path: Path) -> list[EventMarker]:
    """Parse HRV Logger Events CSV rows."""

    markers: list[EventMarker] = []
    for row in _prepare_reader(events_path):
        cleaned = _normalise_row(row)
        if not all(col in cleaned for col in _EVENT_REQUIRED_COLUMNS):
            continue
        label = cleaned.get("annotation") or ""
        if not label:
            continue
        timestamp = _parse_datetime(cleaned.get("date"))
        offset_s: float | None = None
        ts_value = cleaned.get("timestamp")
        if ts_value:
            try:
                offset_s = float(ts_value)
            except ValueError:
                offset_s = None
        markers.append(
            EventMarker(
                label=label,
                timestamp=timestamp,
                offset_s=offset_s,
            )
        )
    return markers


def load_recording(bundle: RecordingBundle) -> HRVLoggerRecording:
    """Load RR + events content for a discovered bundle."""

    rr_intervals = load_rr_intervals(bundle.rr_path)
    events: list[EventMarker] = []
    if bundle.events_path and bundle.events_path.exists():
        events = load_events(bundle.events_path)
    return HRVLoggerRecording(
        participant_id=bundle.participant_id,
        rr_intervals=rr_intervals,
        events=events,
    )


def load_recordings_from_directory(
    root: Path, *, pattern: str = DEFAULT_ID_PATTERN
) -> list[HRVLoggerRecording]:
    """Convenience helper returning fully parsed recordings."""

    bundles = discover_recordings(root, pattern=pattern)
    return [load_recording(bundle) for bundle in bundles]


__all__ = [
    "DEFAULT_ID_PATTERN",
    "RRInterval",
    "EventMarker",
    "RecordingBundle",
    "HRVLoggerRecording",
    "discover_recordings",
    "extract_participant_id",
    "load_events",
    "load_recording",
    "load_recordings_from_directory",
    "load_rr_intervals",
]
