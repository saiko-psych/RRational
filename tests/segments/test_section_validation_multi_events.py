"""Section validation with several start/end candidates (issue #22)."""

from datetime import datetime

from rrational.segments.section_validation import validate_section_for_participant


def _evt(canonical: str, hh: int, mm: int) -> dict:
    return {
        "canonical": canonical,
        "raw_label": canonical,
        "first_timestamp": datetime(2024, 1, 1, hh, mm),
    }


SECTION = {
    "name": "rest_post",
    "start_events": ["rest_post_start"],
    "end_events": ["rest_end", "measurement_end"],
}


def test_end_event_before_start_does_not_invalidate_section():
    # "rest_end" is also used before this section (e.g. shared synonym).
    # The earliest end (10:05) precedes the start; 10:45 is a valid pairing.
    events = [
        _evt("rest_end", 10, 5),
        _evt("rest_post_start", 10, 40),
        _evt("rest_end", 10, 45),
    ]
    result = validate_section_for_participant(SECTION, events, normalizer=None)

    assert result.is_valid, result.error_message
    sec = result.validated_section
    assert sec.start_event.timestamp == datetime(2024, 1, 1, 10, 40)
    assert sec.end_event.timestamp == datetime(2024, 1, 1, 10, 45)
    assert result.needs_disambiguation  # user is still offered the choice


def test_unchanged_when_earliest_end_already_follows_start():
    events = [
        _evt("rest_post_start", 10, 0),
        _evt("rest_end", 10, 5),
        _evt("measurement_end", 10, 30),
    ]
    sec = validate_section_for_participant(
        SECTION, events, normalizer=None
    ).validated_section
    assert sec.end_event.timestamp == datetime(2024, 1, 1, 10, 5)


def test_still_invalid_when_no_end_follows_start():
    events = [_evt("rest_end", 10, 5), _evt("rest_post_start", 10, 40)]
    result = validate_section_for_participant(SECTION, events, normalizer=None)
    assert not result.is_valid
    assert "before end" in result.error_message


def test_explicit_user_selection_is_respected():
    events = [
        _evt("rest_end", 10, 5),
        _evt("rest_post_start", 10, 40),
        _evt("rest_end", 10, 45),
    ]
    result = validate_section_for_participant(
        SECTION,
        events,
        normalizer=None,
        user_selection={"start_index": 0, "end_index": 0},
    )
    assert not result.is_valid  # user explicitly chose the 10:05 end
