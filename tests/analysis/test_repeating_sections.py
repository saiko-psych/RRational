"""Tests for repeating section extraction and validation."""

from datetime import datetime, timedelta

from rrational.analysis.repeating_sections import (
    ProtocolConfig,
    DurationMismatchStrategy,
    extract_repeating_sections,
    get_sections_by_condition,
)
from rrational.io.hrv_logger import RRInterval


def create_test_rr_intervals(
    start_time: datetime,
    duration_minutes: float,
    rr_ms: int = 800,
) -> list[RRInterval]:
    """Create test RR intervals for a given duration."""
    intervals = []
    current_time = start_time
    cumulative_ms = 0

    total_ms = duration_minutes * 60 * 1000
    while cumulative_ms < total_ms:
        intervals.append(RRInterval(
            timestamp=current_time,
            rr_ms=rr_ms,
            elapsed_ms=cumulative_ms,
        ))
        cumulative_ms += rr_ms
        current_time += timedelta(milliseconds=rr_ms)

    return intervals


def test_extract_repeating_sections_basic():
    """Test basic repeating section extraction."""
    start = datetime(2024, 1, 1, 10, 0, 0)
    rr_intervals = create_test_rr_intervals(start, 90)

    events = {
        "measurement_start": start,
        "pause_start": start + timedelta(minutes=45),
        "pause_end": start + timedelta(minutes=45),
        "measurement_end": start + timedelta(minutes=90),
    }

    protocol = ProtocolConfig(
        expected_duration_min=90.0,
        section_length_min=5.0,
        pre_pause_sections=9,
        post_pause_sections=9,
    )

    analysis = extract_repeating_sections(
        rr_intervals=rr_intervals,
        events=events,
        condition_order=["condition_a", "condition_b", "condition_c"],
        protocol=protocol,
    )

    assert len(analysis.sections) == 18
    assert analysis.valid_sections == 18
    assert analysis.incomplete_sections == 0


def test_extract_repeating_sections_short_recording():
    """Test extraction with shorter than expected recording."""
    start = datetime(2024, 1, 1, 10, 0, 0)
    rr_intervals = create_test_rr_intervals(start, 80)

    events = {
        "measurement_start": start,
        "pause_start": start + timedelta(minutes=40),
        "pause_end": start + timedelta(minutes=40),
        "measurement_end": start + timedelta(minutes=80),
    }

    protocol = ProtocolConfig(
        expected_duration_min=90.0,
        section_length_min=5.0,
        pre_pause_sections=9,
        post_pause_sections=9,
        min_section_duration_min=4.0,
    )

    analysis = extract_repeating_sections(
        rr_intervals=rr_intervals,
        events=events,
        condition_order=["condition_a", "condition_b", "condition_c"],
        mismatch_strategy=DurationMismatchStrategy.FLAG_ONLY,
        protocol=protocol,
    )

    assert len(analysis.warnings) > 0
    assert analysis.duration_mismatch_s > 0


def test_sections_by_condition():
    """Test grouping sections by condition type."""
    start = datetime(2024, 1, 1, 10, 0, 0)
    rr_intervals = create_test_rr_intervals(start, 30)

    events = {
        "measurement_start": start,
        "measurement_end": start + timedelta(minutes=30),
    }

    protocol = ProtocolConfig(
        expected_duration_min=30.0,
        section_length_min=5.0,
        pre_pause_sections=6,
        post_pause_sections=0,
    )

    analysis = extract_repeating_sections(
        rr_intervals=rr_intervals,
        events=events,
        condition_order=["condition_a", "condition_b", "condition_c"],
        protocol=protocol,
    )

    by_condition = get_sections_by_condition(analysis)

    assert "condition_a" in by_condition
    assert "condition_b" in by_condition
    assert "condition_c" in by_condition
    assert len(by_condition["condition_a"]) == 2
    assert len(by_condition["condition_b"]) == 2
    assert len(by_condition["condition_c"]) == 2


def test_protocol_config_properties():
    """Test ProtocolConfig computed properties."""
    protocol = ProtocolConfig(
        expected_duration_min=90.0,
        section_length_min=5.0,
        pre_pause_sections=9,
        post_pause_sections=9,
    )

    assert protocol.total_sections == 18
    assert protocol.expected_pre_pause_min == 45.0
    assert protocol.expected_post_pause_min == 45.0


def test_backward_compat_imports():
    """Test that old import paths still work via aliases."""
    from rrational.analysis.repeating_sections import (
        MusicSection,
        MusicSectionAnalysis,
        extract_music_sections,
        get_sections_by_music_type,
    )

    # Verify aliases point to new classes
    from rrational.analysis.repeating_sections import (
        RepeatingSection,
        RepeatingSectionAnalysis,
        extract_repeating_sections,
        get_sections_by_condition,
    )

    assert MusicSection is RepeatingSection
    assert MusicSectionAnalysis is RepeatingSectionAnalysis
    assert extract_music_sections is extract_repeating_sections
    assert get_sections_by_music_type is get_sections_by_condition


def test_backward_compat_via_init():
    """Test that old imports via analysis __init__ still work."""
    from rrational.analysis import (
        MusicSection,
        MusicSectionAnalysis,
        extract_music_sections,
        get_sections_by_music_type,
    )

    assert MusicSection is not None
    assert MusicSectionAnalysis is not None
    assert extract_music_sections is not None
    assert get_sections_by_music_type is not None
