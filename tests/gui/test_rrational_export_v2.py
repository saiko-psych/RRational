"""Tests for build_rrational_v2 (v2.0 .rrational export consolidation)."""

from __future__ import annotations

from importlib.metadata import version

import pytest

from rrational.gui.persistence import save_nn_intervals, save_section_validations
from rrational.gui.rrational_export import build_rrational_v2

PID = "P01"


def _validation(start_beat: int, end_beat: int, start_ts: str, end_ts: str) -> dict:
    return {
        "is_valid": True,
        "start_event": {
            "canonical": "s",
            "timestamp": start_ts,
            "beat_idx": start_beat,
        },
        "end_event": {"canonical": "e", "timestamp": end_ts, "beat_idx": end_beat},
        "duration_s": 300.0,
        "beat_count": end_beat - start_beat,
    }


def _intervals(n: int, first_value: int = 800) -> list[list]:
    """n NN intervals whose nn_ms encodes the index (first_value + i)."""
    return [[i * 800, first_value + i, False] for i in range(n)]


@pytest.fixture
def project(tmp_path):
    return tmp_path


def test_software_version_comes_from_package_metadata(project):
    save_section_validations(
        PID,
        "g",
        {"rest": _validation(0, 10, "2024-01-01T10:00:00", "2024-01-01T10:05:00")},
        project_path=project,
    )
    export, _ = build_rrational_v2(PID, ["rest"], project_path=project)
    assert export.metadata.software_versions["rrational"] == version("rrational")
    assert export.metadata.software_versions["rrational"] != "0.7.7"


# --- scope offset when slicing a section from a broader NN scope -------------


def _save_parent(project, name, n, scope_offset=None, corrections=None):
    nn = {
        "correction_method": "kubios",
        "corrected_at": "2024-01-01T11:00:00",
        "original_beat_count": n,
        "final_nn_count": n,
        "intervals": _intervals(n),
        "corrections": corrections or [],
    }
    if scope_offset is not None:
        nn["scope_offset"] = scope_offset
    save_nn_intervals(PID, name, nn, project_path=project)


def _save_section(project, start_beat, end_beat):
    save_section_validations(
        PID,
        "g",
        {
            "rest": _validation(
                start_beat, end_beat, "2024-01-01T10:00:00", "2024-01-01T10:05:00"
            )
        },
        project_path=project,
    )


def test_scope_offset_is_persisted_and_loaded(project):
    from rrational.gui.persistence import load_nn_intervals

    _save_parent(project, "measurement", 50, scope_offset=100)
    loaded = load_nn_intervals(PID, project_path=project)["sections"]["measurement"]
    assert loaded["scope_offset"] == 100


def test_slice_from_parent_uses_scope_offset(project):
    # measurement scope starts at global beat 100; section is global beats 110-120
    _save_parent(
        project,
        "measurement",
        50,
        scope_offset=100,
        corrections=[
            {"nn_idx": 12, "original_rr_ms": 1500, "corrected_nn_ms": 812},
            {"nn_idx": 40, "original_rr_ms": 1500, "corrected_nn_ms": 840},
        ],
    )
    _save_section(project, 110, 120)

    export, warnings = build_rrational_v2(PID, ["rest"], project_path=project)

    nn = export.sections["rest"].nn_intervals
    # local beats 10..19 of the parent -> nn_ms 810..819
    assert [iv[1] for iv in nn.data] == list(range(810, 820))
    assert nn.data[0][0] == 0  # timestamps re-based to section start
    # only the correction at local idx 12 falls in the slice, re-indexed to 2
    assert [c["nn_idx"] for c in nn.corrections] == [2]
    assert any("sliced from 'measurement'" in w for w in warnings)


def test_section_outside_parent_scope_is_not_sliced(project):
    _save_parent(project, "measurement", 50, scope_offset=100)
    _save_section(project, 10, 20)  # before the scope starts

    export, _ = build_rrational_v2(PID, ["rest"], project_path=project)
    assert export.sections["rest"].nn_intervals.data == []


def test_legacy_parent_without_offset_is_skipped_not_misaligned(project):
    # Old files have no scope_offset: the old code would silently slice
    # beats 10..19 here even though the scope may not start at beat 0.
    _save_parent(project, "measurement", 50)
    _save_section(project, 10, 20)

    export, warnings = build_rrational_v2(PID, ["rest"], project_path=project)
    assert export.sections["rest"].nn_intervals.data == []
    assert any("no scope offset" in w for w in warnings)


def test_full_scope_without_offset_defaults_to_zero(project):
    _save_parent(project, "_full", 50)
    _save_section(project, 10, 20)

    export, _ = build_rrational_v2(PID, ["rest"], project_path=project)
    assert [iv[1] for iv in export.sections["rest"].nn_intervals.data] == list(
        range(810, 820)
    )


# --- VNS multi-file recording gaps ------------------------------------------


def test_vns_gaps_are_exported_and_split_segments(project):
    from datetime import datetime

    # section 10:00:00-10:05:00 (300 s); file gap 10:02:00-10:02:30 inside it,
    # second gap outside the section
    _save_parent(project, "rest", 100)
    _save_section(project, 0, 100)
    gaps = [
        {
            "after_file": "P01_a.txt",
            "before_file": "P01_b.txt",
            "gap_start": datetime(2024, 1, 1, 10, 2, 0),
            "gap_end": datetime(2024, 1, 1, 10, 2, 30),
            "gap_duration_s": 30.0,
        },
        {
            "after_file": "P01_b.txt",
            "before_file": "P01_c.txt",
            "gap_start": datetime(2024, 1, 1, 11, 0, 0),
            "gap_end": datetime(2024, 1, 1, 11, 1, 0),
            "gap_duration_s": 60.0,
        },
    ]

    export, _ = build_rrational_v2(
        PID, ["rest"], project_path=project, recording_gaps=gaps
    )

    assert [g.gap_id for g in export.recording_gaps] == ["gap_1", "gap_2"]
    assert export.recording_gaps[0].gap_start == "2024-01-01T10:02:00"
    assert export.recording_gaps[0].after_file == "P01_a.txt"

    section = export.sections["rest"]
    assert [g.gap_id for g in section.gaps] == ["gap_1"]
    assert section.quality.usable_duration_s == pytest.approx(270.0)
    types = [seg.type for seg in section.analysis_segments]
    assert types.count("data") == 2  # split at the gap
    assert "gap" in types


def test_gap_partially_overlapping_section_is_clipped(project):
    from datetime import datetime

    _save_parent(project, "rest", 100)
    _save_section(project, 0, 100)
    gaps = [
        {
            "after_file": "a",
            "before_file": "b",
            "gap_start": datetime(2024, 1, 1, 9, 59, 0),
            "gap_end": datetime(2024, 1, 1, 10, 0, 20),
            "gap_duration_s": 80.0,
        }
    ]
    export, _ = build_rrational_v2(
        PID, ["rest"], project_path=project, recording_gaps=gaps
    )
    assert export.sections["rest"].quality.usable_duration_s == pytest.approx(280.0)


def test_no_gaps_by_default(project):
    _save_parent(project, "rest", 100)
    _save_section(project, 0, 100)
    export, _ = build_rrational_v2(PID, ["rest"], project_path=project)
    assert export.recording_gaps == []
    assert export.sections["rest"].gaps == []


def test_gaps_survive_save_load_roundtrip(project):
    from datetime import datetime

    from rrational.gui.rrational_export import load_rrational_v2, save_rrational_v2

    _save_parent(project, "rest", 100)
    _save_section(project, 0, 100)
    gaps = [
        {
            "after_file": "a",
            "before_file": "b",
            "gap_start": datetime(2024, 1, 1, 10, 2, 0),
            "gap_end": datetime(2024, 1, 1, 10, 2, 30),
            "gap_duration_s": 30.0,
        }
    ]
    export, _ = build_rrational_v2(
        PID, ["rest"], project_path=project, recording_gaps=gaps
    )
    out = project / "out.rrational"
    save_rrational_v2(export, out)
    loaded = load_rrational_v2(out)
    assert [g.gap_id for g in loaded.recording_gaps] == ["gap_1"]
    assert [g.gap_id for g in loaded.sections["rest"].gaps] == ["gap_1"]
