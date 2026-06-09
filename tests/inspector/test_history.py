"""Tests for the MNELAB-style reproducible-action history.

Covers the structured ``Action`` dataclasses, the ``HistoryRecorder``
ledger, and the ``to_script`` renderer that turns the ledger into a
runnable Python script (the user-facing recipe artefact).

The MainWindow-side hooks (LoadRecording on open_path,
DetectArtifacts on the panel, etc.) are exercised in
``test_save_recipe.py`` because they need a full pytest-qt fixture.
"""

from __future__ import annotations

import ast

from rrational.inspector.history import (
    AddAnnotation,
    AddExclusionZone,
    BatchPreprocess,
    DetectArtifacts,
    HistoryRecorder,
    LoadRecording,
    OpenProject,
    SaveRRationalExport,
    to_script,
)


# ---------------------------------------------------------------------
# Action.to_python() — string content + Python-syntax round-trip
# ---------------------------------------------------------------------
def test_open_project_action_to_python_uses_path_and_persistence():
    a = OpenProject(path="/tmp/proj")
    code = a.to_python()
    assert "set_active_project_config_dir" in code
    assert "/tmp/proj" in code


def test_load_recording_action_to_python_has_load_call():
    a = LoadRecording(path="/tmp/x.csv", fmt="hrv_logger")
    code = a.to_python()
    assert "load_generic_rr" in code
    assert "/tmp/x.csv" in code
    assert "hrv_logger" in code


def test_load_recording_without_fmt_uses_auto_detect():
    a = LoadRecording(path="/tmp/y.csv")
    code = a.to_python()
    assert "detect_format" in code
    assert "/tmp/y.csv" in code


def test_detect_artifacts_action_renders_clean_call():
    a = DetectArtifacts(method="lipponen2019", pid="S01")
    code = a.to_python()
    assert "clean_rr_intervals" in code
    assert "CleaningConfig" in code
    assert "lipponen2019" in code


def test_add_exclusion_zone_action_renders_pid_and_bounds():
    a = AddExclusionZone(pid="S01", t_start=12.0, t_end=18.5, reason="motion")
    code = a.to_python()
    assert "S01" in code
    assert "12.0" in code
    assert "18.5" in code
    assert "motion" in code


def test_add_annotation_action_renders_attach_comment():
    a = AddAnnotation(pid="S02", t=42.5, label="subject coughed")
    code = a.to_python()
    assert "Annotation" in code
    assert "S02" in code
    assert "42.5" in code
    assert "subject coughed" in code


def test_save_rrational_export_action_renders_metadata():
    a = SaveRRationalExport(
        pid="S03",
        section="rest_pre",
        out_path="/tmp/out/S03.rrational",
        n_beats=480,
    )
    code = a.to_python()
    assert "/tmp/out/S03.rrational" in code
    assert "480" in code
    assert "S03" in code
    assert "rest_pre" in code


def test_batch_preprocess_action_loops_over_paths():
    a = BatchPreprocess(
        recording_paths=("/tmp/a.csv", "/tmp/b.csv"),
        method="lipponen2019",
    )
    code = a.to_python()
    assert "for _p in _paths" in code
    assert "/tmp/a.csv" in code
    assert "/tmp/b.csv" in code
    assert "lipponen2019" in code


# ---------------------------------------------------------------------
# HistoryRecorder ledger behaviour
# ---------------------------------------------------------------------
def test_recorder_appends_and_iterates():
    r = HistoryRecorder()
    r.record(LoadRecording(path="a"))
    r.record(LoadRecording(path="b"))
    assert len(r) == 2
    assert [a.path for a in r] == ["a", "b"]


def test_recorder_record_none_is_noop():
    r = HistoryRecorder()
    r.record(None)  # type: ignore[arg-type]
    assert len(r) == 0


def test_recorder_clear_drops_everything():
    r = HistoryRecorder()
    r.record(LoadRecording(path="a"))
    r.record(LoadRecording(path="b"))
    r.clear()
    assert len(r) == 0
    assert list(r) == []


# ---------------------------------------------------------------------
# Serializer — produces valid Python with the expected structure
# ---------------------------------------------------------------------
def test_to_script_produces_valid_python_for_mixed_actions():
    r = HistoryRecorder()
    r.record(OpenProject(path="/tmp/proj"))
    r.record(LoadRecording(path="/tmp/x.csv"))
    r.record(DetectArtifacts(method="lipponen2019"))
    r.record(
        SaveRRationalExport(
            pid="S01", section="full", out_path="/tmp/S01.rrational", n_beats=200
        )
    )
    src = to_script(r)
    # MUST parse — semantic replay is out of scope for Sprint 1.
    ast.parse(src)
    # Header sanity: the script imports Path so per-action snippets can
    # reference it without re-importing.
    assert "from pathlib import Path" in src
    # Every action's distinguishing token shows up in the script body.
    assert "/tmp/proj" in src
    assert "/tmp/x.csv" in src
    assert "clean_rr_intervals" in src
    assert "/tmp/S01.rrational" in src


def test_empty_recorder_produces_no_actions_comment():
    src = to_script(HistoryRecorder())
    # Comment is human-readable so users opening the file see something
    # explaining the emptiness, and the script still parses.
    assert "No actions recorded" in src
    ast.parse(src)


def test_to_script_preserves_action_order():
    r = HistoryRecorder()
    r.record(LoadRecording(path="/tmp/first.csv"))
    r.record(LoadRecording(path="/tmp/second.csv"))
    src = to_script(r)
    # First < second in the rendered text.
    first_idx = src.index("/tmp/first.csv")
    second_idx = src.index("/tmp/second.csv")
    assert first_idx < second_idx
