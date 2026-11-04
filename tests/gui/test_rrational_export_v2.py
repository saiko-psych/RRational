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
        "start_event": {"canonical": "s", "timestamp": start_ts, "beat_idx": start_beat},
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
