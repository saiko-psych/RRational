"""Section validation: dataclasses and pure validation logic.

Determines section boundaries from event markers. No Streamlit dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


def _normalize_timestamp(ts) -> datetime:
    """Normalize a timestamp to naive datetime for safe comparison."""
    if ts is None:
        return datetime.min
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return datetime.min
    if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
        ts = ts.replace(tzinfo=None)
    return ts


@dataclass
class EventCandidate:
    """A candidate event that could be used as a section boundary."""
    canonical_name: str
    raw_label: str
    timestamp: datetime
    index: int

    def display_label(self) -> str:
        time_str = self.timestamp.strftime("%H:%M:%S") if self.timestamp else "?"
        return f"{self.raw_label} @ {time_str}"


@dataclass
class ValidatedSection:
    """A validated section with explicit event references.

    Single source of truth for section boundaries across all features.
    """
    section_name: str
    start_event: EventCandidate
    end_event: EventCandidate
    beat_count: int = 0
    duration_s: float = 0.0
    is_user_selected: bool = False


@dataclass
class SectionValidationResult:
    """Result of attempting to validate a section for a participant."""
    section_name: str
    is_valid: bool
    validated_section: Optional[ValidatedSection] = None
    start_candidates: list[EventCandidate] = field(default_factory=list)
    end_candidates: list[EventCandidate] = field(default_factory=list)
    needs_disambiguation: bool = False
    error_message: Optional[str] = None


def find_event_candidates(
    events: list,
    target_canonical_names: list[str],
    normalizer,
) -> list[EventCandidate]:
    """Find all events matching target canonical names.

    Args:
        events: Event objects (EventStatus, dict, or raw Event).
        target_canonical_names: Canonical names to match.
        normalizer: SectionNormalizer for mapping raw labels.

    Returns:
        EventCandidate list, sorted by timestamp.
    """
    candidates = []

    for idx, event in enumerate(events):
        if isinstance(event, dict):
            canonical = event.get("canonical")
            raw_label = event.get("raw_label", event.get("label", ""))
            timestamp = event.get("first_timestamp") or event.get("timestamp")
        else:
            canonical = getattr(event, "canonical", None)
            raw_label = getattr(event, "raw_label", None) or getattr(event, "label", "")
            timestamp = getattr(event, "first_timestamp", None) or getattr(event, "timestamp", None)
            if not canonical and raw_label and normalizer:
                canonical = normalizer.normalize(raw_label)

        if not timestamp:
            continue

        if canonical in target_canonical_names or raw_label in target_canonical_names:
            candidates.append(EventCandidate(
                canonical_name=canonical or raw_label,
                raw_label=raw_label,
                timestamp=timestamp,
                index=idx,
            ))

    candidates.sort(key=lambda c: _normalize_timestamp(c.timestamp))
    return candidates


def validate_section_for_participant(
    section_def: dict,
    events: list,
    normalizer,
    rr_intervals: list = None,
    user_selection: dict = None,
) -> SectionValidationResult:
    """Validate a section for a participant by finding matching events.

    Central function for determining section boundaries. All features
    (Analysis, Artifact Detection, Signal Inspection) should use this.

    Args:
        section_def: Section definition with start_events/end_events lists.
        events: Participant's events.
        normalizer: SectionNormalizer for mapping labels.
        rr_intervals: Optional RR intervals to calculate beat count.
        user_selection: Optional {"start_index": int, "end_index": int} for disambiguation.

    Returns:
        SectionValidationResult with validation status.
    """
    section_name = section_def.get("name", "unknown")

    start_event_names = section_def.get("start_events", [])
    if not start_event_names and "start_event" in section_def:
        start_event_names = [section_def["start_event"]]
    end_event_names = section_def.get("end_events", [])
    if not end_event_names and "end_event" in section_def:
        end_event_names = [section_def["end_event"]]

    if not start_event_names or not end_event_names:
        return SectionValidationResult(
            section_name=section_name, is_valid=False,
            error_message="Section definition missing start or end events",
        )

    start_candidates = find_event_candidates(events, start_event_names, normalizer)
    end_candidates = find_event_candidates(events, end_event_names, normalizer)

    if not start_candidates:
        return SectionValidationResult(
            section_name=section_name, is_valid=False,
            error_message=f"No start event found ({', '.join(start_event_names)})",
        )
    if not end_candidates:
        return SectionValidationResult(
            section_name=section_name, is_valid=False,
            error_message=f"No end event found ({', '.join(end_event_names)})",
        )

    needs_disambiguation = len(start_candidates) > 1 or len(end_candidates) > 1

    if user_selection:
        start_idx = min(user_selection.get("start_index", 0), len(start_candidates) - 1)
        end_idx = min(user_selection.get("end_index", 0), len(end_candidates) - 1)
        is_user_selected = True
    else:
        start_idx = 0
        end_idx = 0
        is_user_selected = False

    selected_start = start_candidates[start_idx]
    selected_end = end_candidates[end_idx]

    if _normalize_timestamp(selected_start.timestamp) >= _normalize_timestamp(selected_end.timestamp):
        return SectionValidationResult(
            section_name=section_name, is_valid=False,
            start_candidates=start_candidates, end_candidates=end_candidates,
            needs_disambiguation=needs_disambiguation,
            error_message="Start event must come before end event",
        )

    beat_count = 0
    duration_s = 0.0
    if rr_intervals:
        start_ts = _normalize_timestamp(selected_start.timestamp)
        end_ts = _normalize_timestamp(selected_end.timestamp)
        for rr in rr_intervals:
            ts = getattr(rr, "timestamp", None)
            ts_norm = _normalize_timestamp(ts) if ts else None
            if ts_norm and start_ts <= ts_norm <= end_ts:
                beat_count += 1
                duration_s += getattr(rr, "rr_ms", 0) / 1000.0

    validated = ValidatedSection(
        section_name=section_name,
        start_event=selected_start,
        end_event=selected_end,
        beat_count=beat_count,
        duration_s=duration_s,
        is_user_selected=is_user_selected,
    )

    return SectionValidationResult(
        section_name=section_name, is_valid=True,
        validated_section=validated,
        start_candidates=start_candidates, end_candidates=end_candidates,
        needs_disambiguation=needs_disambiguation,
    )
