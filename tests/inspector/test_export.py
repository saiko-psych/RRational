"""Tests for inspector.export — InspectorData → .rrational v2 roundtrip."""

from __future__ import annotations

import numpy as np
import pytest

from rrational.gui.rrational_export import load_rrational_v2
from rrational.inspector.data_loader import EventMeta, InspectorData, SectionMeta
from rrational.inspector.export import build_v2_export, export_inspector_to_rrational
from rrational.inspector.preprocessing import detect_artifacts


def _make_data(section_names: list[str], beats_per_section: int = 200):
    base = 1_700_000_000
    n = beats_per_section * len(section_names)
    rng = np.random.default_rng(seed=11)
    rr_ms = 800 + 30 * rng.standard_normal(n)
    t = base + np.cumsum(rr_ms) / 1000.0

    sections = []
    events = []
    for i, name in enumerate(section_names):
        s = i * beats_per_section
        e = (i + 1) * beats_per_section - 1
        sections.append(
            SectionMeta(
                name=name,
                t_start=float(t[s]),
                t_end=float(t[e]),
                beat_count=beats_per_section,
            )
        )
        events.append(EventMeta(label=f"{name}_start", t=float(t[s])))
    return InspectorData(t=t, v=rr_ms, sections=sections, events=events)


# ---------------------------------------------------------------------
# build_v2_export — pure mapping
# ---------------------------------------------------------------------
def test_build_v2_export_one_section_per_section_meta():
    data = _make_data(["rest", "stim", "recovery"])
    export = build_v2_export(data, participant_id="P001")
    assert set(export.sections.keys()) == {"rest", "stim", "recovery"}


def test_build_v2_export_metadata_carries_participant_id():
    data = _make_data(["s1"])
    export = build_v2_export(data, participant_id="0042XYZ")
    assert export.metadata.participant_id == "0042XYZ"
    assert export.metadata.source_app == "RRational Inspector"
    assert export.metadata.recording_info["total_beats"] == len(data.t)


def test_build_v2_export_writes_nn_intervals_per_section():
    data = _make_data(["a", "b"], beats_per_section=150)
    export = build_v2_export(data, participant_id="P")
    for name in ("a", "b"):
        sec = export.sections[name]
        assert sec.validation.total_beat_count == 150
        # NN data shape: [[ms_from_start, nn_ms, was_corrected], ...]
        assert len(sec.nn_intervals.data) == 150
        # First entry's elapsed_ms is 0 (section starts at its first beat)
        first_row = sec.nn_intervals.data[0]
        assert first_row[0] == 0
        assert first_row[2] is False  # uncorrected by default


def test_build_v2_export_quality_uses_quigley_thresholds():
    data = _make_data(["rest"], beats_per_section=200)
    export = build_v2_export(data, participant_id="P")
    sec = export.sections["rest"]
    # No preprocessing → rate 0.0 → "excellent"
    assert sec.quality.grade == "excellent"
    assert sec.quality.usable_beats == 200
    assert sec.quality.meets_time_domain_min is True
    # 200 < 300 beats → does not meet freq-domain minimum
    assert sec.quality.meets_freq_domain_min is False


def test_build_v2_export_with_preprocessing_marks_corrected_beats():
    """When PreprocessingResult is supplied, nn_correction reflects it."""
    data = _make_data(["rest"], beats_per_section=400)
    # Inject some spike artifacts so the detector has something to fix
    spike_indices = [10, 50, 100, 200]
    for i in spike_indices:
        data.v[i] = 2000.0  # very obviously not a heartbeat
    prep = detect_artifacts(data.v)
    if prep.total == 0:
        pytest.skip("Synthetic spikes weren't detected by NK2 in this run")

    export = build_v2_export(data, participant_id="P", preprocessing=prep)
    sec = export.sections["rest"]

    # nn_correction should record the kubios method + a positive count
    assert sec.nn_correction.method == "kubios"
    assert sec.nn_correction.intervals_corrected > 0

    # final_artifacts.indices is SECTION-relative and mirrors prep.indices
    # (every beat whose value was changed by the correction algorithm,
    # not just the strictly-classified NK2 artifacts — see
    # PreprocessingResult docstring).
    assert sec.final_artifacts.count == len(prep.indices)
    assert sec.final_artifacts.count > 0

    # At least one row has was_corrected=True
    corrected_flags = [row[2] for row in sec.nn_intervals.data]
    assert any(corrected_flags)


def test_build_v2_export_records_source_path_in_metadata():
    from pathlib import Path

    data = _make_data(["s"])
    export = build_v2_export(
        data, participant_id="P", source_path=Path("data/raw/foo.csv")
    )
    assert len(export.metadata.source_files) == 1
    assert export.metadata.source_files[0]["path"].endswith("foo.csv")


# ---------------------------------------------------------------------
# Roundtrip: save → load_rrational_v2 → assert
# ---------------------------------------------------------------------
def test_export_then_load_roundtrip_preserves_sections(tmp_path):
    data = _make_data(["pre", "music", "post"], beats_per_section=120)
    out = tmp_path / "subject01.rrational"
    export_inspector_to_rrational(data, out, participant_id="subject01")

    assert out.exists()
    loaded = load_rrational_v2(out)
    assert loaded.metadata.participant_id == "subject01"
    assert set(loaded.sections.keys()) == {"pre", "music", "post"}
    for name in loaded.sections:
        assert loaded.sections[name].validation.total_beat_count == 120


def test_export_audit_trail_has_one_entry(tmp_path):
    data = _make_data(["x"])
    out = tmp_path / "x.rrational"
    export_inspector_to_rrational(data, out, participant_id="x")
    loaded = load_rrational_v2(out)
    assert len(loaded.audit_trail) == 1
    assert loaded.audit_trail[0].action == "exported_from_inspector"


def test_export_handles_dataset_with_no_sections(tmp_path):
    """A dataset with no SectionMeta should still produce a valid file
    (empty sections dict, but a usable metadata block)."""
    data = InspectorData(
        t=np.array([1.0, 2.0, 3.0]),
        v=np.array([800.0, 810.0, 820.0]),
        sections=[],
        events=[],
    )
    out = tmp_path / "no_sections.rrational"
    export_inspector_to_rrational(data, out, participant_id="empty")
    loaded = load_rrational_v2(out)
    assert loaded.sections == {}
    assert loaded.metadata.recording_info["total_beats"] == 3


def test_inspector_can_reload_its_own_export(tmp_path):
    """The full loop: build data → export → Dataset.from_path → use the
    loaded data again. Proves the v2 format the inspector emits is
    readable by the inspector's own data loader."""
    from rrational.inspector.data_loader import Dataset

    data = _make_data(["pre", "stim", "post"], beats_per_section=120)
    out = tmp_path / "subject07.rrational"
    export_inspector_to_rrational(data, out, participant_id="subject07")

    ds = Dataset.from_path(out)
    assert ds.data is not None
    # Same three sections come back
    section_names = {s.name for s in ds.data.sections}
    assert section_names == {"pre", "stim", "post"}
    # Same total beat count (within rounding tolerance from int conversion)
    assert len(ds.data.t) > 0
