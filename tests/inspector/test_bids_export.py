"""BIDS-physio export round-trip + sidecar schema."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pytest


def _make_data(experimenter: str = "", device: str = "", line_freq=None):
    from rrational.inspector.data_loader import InspectorData

    t = np.arange(0, 60, 0.8) + 1_700_000_000
    v = 800 + 30 * np.sin(np.linspace(0, np.pi, len(t)))
    return InspectorData(
        t=t,
        v=v,
        experimenter=experimenter,
        device=device,
        line_freq=line_freq,
    )


def test_export_writes_both_files(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio

    paths = export_bids_physio(
        _make_data(), tmp_path, participant_id="001", task="rest"
    )
    assert paths.tsv_gz.exists()
    assert paths.json.exists()
    # Stem is identical between TSV.GZ and JSON sidecar (BIDS rule).
    assert paths.tsv_gz.stem.replace(".tsv", "") == paths.json.stem


def test_export_filename_includes_session_when_provided(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio

    paths = export_bids_physio(
        _make_data(),
        tmp_path,
        participant_id="001",
        task="rest",
        session="pre",
    )
    assert "ses-pre" in paths.tsv_gz.name
    assert "ses-pre" in paths.json.name


def test_export_filename_drops_session_when_absent(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio

    paths = export_bids_physio(
        _make_data(), tmp_path, participant_id="001", task="rest"
    )
    assert "ses-" not in paths.tsv_gz.name
    assert "ses-" not in paths.json.name


def test_sidecar_has_required_fields(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio

    paths = export_bids_physio(
        _make_data(), tmp_path, participant_id="001", task="rest"
    )
    sidecar = json.loads(paths.json.read_text())
    # BIDS v1.11.1 requires SamplingFrequency, StartTime, Columns.
    assert "SamplingFrequency" in sidecar
    assert sidecar["SamplingFrequency"] > 0
    assert "StartTime" in sidecar
    assert sidecar["Columns"] == ["cardiac"]
    assert sidecar["cardiac"]["Units"] == "ms"


def test_sidecar_omits_unset_optional_fields(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio

    paths = export_bids_physio(
        _make_data(), tmp_path, participant_id="001", task="rest"
    )
    sidecar = json.loads(paths.json.read_text())
    # Empty / None metadata fields are not written — sidecar stays clean.
    assert "Experimenter" not in sidecar
    assert "Manufacturer" not in sidecar
    assert "PowerLineFrequency" not in sidecar


def test_sidecar_includes_optional_fields_when_set(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio

    data = _make_data(experimenter="Dr Smith", device="Polar H10", line_freq=50.0)
    paths = export_bids_physio(data, tmp_path, participant_id="001", task="rest")
    sidecar = json.loads(paths.json.read_text())
    assert sidecar["Experimenter"] == "Dr Smith"
    assert sidecar["Manufacturer"] == "Polar H10"
    assert sidecar["PowerLineFrequency"] == 50.0


def test_tsv_gz_is_one_column_one_row_per_beat(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio

    data = _make_data()
    paths = export_bids_physio(data, tmp_path, participant_id="001", task="rest")
    with gzip.open(paths.tsv_gz, "rt", encoding="utf-8") as f:
        rows = [line.rstrip() for line in f if line.strip()]
    assert len(rows) == int(np.isfinite(data.v).sum())
    # Header-less; first row is a plain float.
    assert "\t" not in rows[0]
    float(rows[0])


def test_participant_id_must_be_alphanumeric(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio

    with pytest.raises(ValueError, match="alphanumeric"):
        export_bids_physio(
            _make_data(), tmp_path, participant_id="001/CTRL", task="rest"
        )


def test_task_must_be_alphanumeric(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio

    with pytest.raises(ValueError, match="alphanumeric"):
        export_bids_physio(
            _make_data(), tmp_path, participant_id="001", task="rest/baseline"
        )


def test_sidecar_does_not_emit_non_spec_RecordingType_key(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio

    paths = export_bids_physio(
        _make_data(), tmp_path, participant_id="001", task="rest"
    )
    sidecar = json.loads(paths.json.read_text())
    # BIDS-physio JSON does not define RecordingType — keeping it would
    # be a non-spec key. Drop it (audited in bids_cardiac_compat.md).
    assert "RecordingType" not in sidecar


def test_sidecar_emits_PhysioType_generic(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio

    paths = export_bids_physio(
        _make_data(), tmp_path, participant_id="001", task="rest"
    )
    sidecar = json.loads(paths.json.read_text())
    # RECOMMENDED field per BIDS spec; explicit > implicit.
    assert sidecar["PhysioType"] == "generic"


def test_cardiac_column_block_has_LongName(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio

    paths = export_bids_physio(
        _make_data(), tmp_path, participant_id="001", task="rest"
    )
    sidecar = json.loads(paths.json.read_text())
    assert sidecar["cardiac"]["LongName"] == "RR interval"


def test_out_dir_is_created_when_missing(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio

    out = tmp_path / "sub-001" / "ses-pre" / "func"
    paths = export_bids_physio(_make_data(), out, participant_id="001", task="rest")
    assert paths.tsv_gz.parent == out
    assert out.exists()


# ---------------------------------------------------------------------
# Cluster B6 — anonymize={"daysback": N}
# ---------------------------------------------------------------------
def test_anonymize_shifts_starttime_back(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio

    data = _make_data()
    paths_plain = export_bids_physio(
        data, tmp_path / "plain", participant_id="001", task="rest"
    )
    paths_anon = export_bids_physio(
        data,
        tmp_path / "anon",
        participant_id="001",
        task="rest",
        anonymize={"daysback": 365},
    )
    plain = json.loads(paths_plain.json.read_text())
    anon = json.loads(paths_anon.json.read_text())
    # 365 days in seconds.
    assert plain["StartTime"] - anon["StartTime"] == pytest.approx(365 * 86400.0)


def test_anonymize_drops_freetext_pii(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio

    data = _make_data(experimenter="Dr. Smith", device="Polar H10")
    data.description = "Pilot recording, subject ID redacted"
    paths = export_bids_physio(
        data,
        tmp_path,
        participant_id="001",
        task="rest",
        anonymize={"daysback": 30},
    )
    sidecar = json.loads(paths.json.read_text())
    assert "Experimenter" not in sidecar
    assert "TaskDescription" not in sidecar
    # Hardware manufacturer is equipment metadata, not PII — keeps.
    assert sidecar.get("Manufacturer") == "Polar H10"


def test_anonymize_without_daysback_only_strips_pii(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio

    data = _make_data(experimenter="Dr. Smith")
    paths = export_bids_physio(
        data,
        tmp_path,
        participant_id="001",
        task="rest",
        anonymize={},
    )
    sidecar = json.loads(paths.json.read_text())
    # Daysback omitted → StartTime unchanged from the raw data anchor.
    assert sidecar["StartTime"] == pytest.approx(float(data.t_start))
    # PII still stripped even without a daysback override.
    assert "Experimenter" not in sidecar
