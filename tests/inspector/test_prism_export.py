"""PRISM Studio biometrics export — schema + round-trip."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest


def _make_data(experimenter: str = "", device: str = "Polar H10"):
    from rrational.inspector.data_loader import InspectorData

    t = np.arange(0, 60, 0.8) + 1_700_000_000
    v = 800 + 30 * np.sin(np.linspace(0, np.pi, len(t)))
    return InspectorData(t=t, v=v, experimenter=experimenter, device=device)


SAMPLE_METRICS = {
    "n_beats": 75,
    "duration_s": 60.0,
    "mean_hr_bpm": 75.0,
    "mean_nn_ms": 800.0,
    "sdnn_ms": 42.3,
    "rmssd_ms": 34.7,
    "pnn50_pct": 24.3,
    "lf_ms2": 612.4,
    "hf_ms2": 489.7,
    "lf_hf_ratio": 1.25,
    "sd1_ms": 24.6,
    "sd2_ms": 54.2,
}


def test_export_writes_both_files(tmp_path: Path):
    from rrational.inspector.prism_export import export_prism_biometrics

    paths = export_prism_biometrics(
        SAMPLE_METRICS,
        tmp_path,
        participant_id="001",
        task="rest",
        data=_make_data(),
    )
    assert paths.tsv.exists()
    assert paths.json.exists()
    # Stem shared between TSV + sidecar (PRISM rule, mirrors BIDS).
    assert paths.tsv.stem == paths.json.stem


def test_filename_uses_biometrics_suffix_not_physio(tmp_path: Path):
    from rrational.inspector.prism_export import export_prism_biometrics

    paths = export_prism_biometrics(
        SAMPLE_METRICS,
        tmp_path,
        participant_id="001",
        task="rest",
        data=_make_data(),
    )
    # PRISM biometrics has its own suffix; must NOT be _physio.
    assert paths.tsv.name.endswith("_biometrics.tsv")
    assert "biometrics-hrv" in paths.tsv.name


def test_filename_includes_session_when_provided(tmp_path: Path):
    from rrational.inspector.prism_export import export_prism_biometrics

    paths = export_prism_biometrics(
        SAMPLE_METRICS,
        tmp_path,
        participant_id="001",
        task="rest",
        session="pre",
        data=_make_data(),
    )
    assert "ses-pre" in paths.tsv.name


def test_filename_drops_session_when_absent(tmp_path: Path):
    from rrational.inspector.prism_export import export_prism_biometrics

    paths = export_prism_biometrics(
        SAMPLE_METRICS,
        tmp_path,
        participant_id="001",
        task="rest",
        data=_make_data(),
    )
    assert "ses-" not in paths.tsv.name


def test_tsv_has_header_row_then_value_row(tmp_path: Path):
    from rrational.inspector.prism_export import export_prism_biometrics

    paths = export_prism_biometrics(
        SAMPLE_METRICS,
        tmp_path,
        participant_id="001",
        task="rest",
        data=_make_data(),
    )
    with paths.tsv.open("r", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        rows = list(reader)
    # PRISM biometrics TSV has a header — distinct from BIDS-physio
    # which is header-less. One value row per recording.
    assert len(rows) == 2
    assert rows[0] == list(SAMPLE_METRICS.keys())
    # Values round-trip to within 6-significant-digit precision.
    for column_name, value in zip(rows[0], rows[1]):
        if column_name == "n_beats":
            assert value == "75"
        else:
            assert float(value) == pytest.approx(SAMPLE_METRICS[column_name])


def test_sidecar_has_prism_top_level_blocks(tmp_path: Path):
    from rrational.inspector.prism_export import export_prism_biometrics

    paths = export_prism_biometrics(
        SAMPLE_METRICS,
        tmp_path,
        participant_id="001",
        task="rest",
        data=_make_data(),
    )
    sidecar = json.loads(paths.json.read_text())
    # The three PRISM-mandated top-level blocks.
    assert sidecar["Technical"]["Type"] == "Biometrics"
    assert sidecar["Technical"]["FileFormat"] == "tsv"
    assert sidecar["Technical"]["SoftwarePlatform"] == "RRational"
    assert sidecar["Study"]["BiometricName"] == "Heart rate variability"
    assert sidecar["Metadata"]["SchemaVersion"] == "1.1.1"


def test_software_platform_is_overridable(tmp_path: Path):
    from rrational.inspector.prism_export import export_prism_biometrics

    paths = export_prism_biometrics(
        SAMPLE_METRICS,
        tmp_path,
        participant_id="001",
        task="rest",
        software_platform="Kubios",
        data=_make_data(),
    )
    sidecar = json.loads(paths.json.read_text())
    assert sidecar["Technical"]["SoftwarePlatform"] == "Kubios"


def test_sidecar_column_blocks_describe_each_metric(tmp_path: Path):
    from rrational.inspector.prism_export import export_prism_biometrics

    paths = export_prism_biometrics(
        SAMPLE_METRICS,
        tmp_path,
        participant_id="001",
        task="rest",
        data=_make_data(),
    )
    sidecar = json.loads(paths.json.read_text())
    # Spot-check: every TSV column has a sidecar block with units +
    # data type.
    assert sidecar["sdnn_ms"]["Units"] == "ms"
    assert sidecar["pnn50_pct"]["Units"] == "%"
    assert sidecar["lf_hf_ratio"]["DataType"] == "number"
    assert sidecar["n_beats"]["DataType"] == "integer"


def test_sidecar_propagates_device_into_technical_equipment(tmp_path: Path):
    from rrational.inspector.prism_export import export_prism_biometrics

    paths = export_prism_biometrics(
        SAMPLE_METRICS,
        tmp_path,
        participant_id="001",
        task="rest",
        data=_make_data(device="Polar H10"),
    )
    sidecar = json.loads(paths.json.read_text())
    assert sidecar["Technical"]["Equipment"] == "Polar H10"


def test_sidecar_propagates_experimenter(tmp_path: Path):
    from rrational.inspector.prism_export import export_prism_biometrics

    paths = export_prism_biometrics(
        SAMPLE_METRICS,
        tmp_path,
        participant_id="001",
        task="rest",
        data=_make_data(experimenter="Dr Smith"),
    )
    sidecar = json.loads(paths.json.read_text())
    assert sidecar["Technical"]["Experimenter"] == "Dr Smith"


def test_runs_without_data_using_safe_defaults(tmp_path: Path):
    from rrational.inspector.prism_export import export_prism_biometrics

    paths = export_prism_biometrics(
        SAMPLE_METRICS, tmp_path, participant_id="001", task="rest"
    )
    sidecar = json.loads(paths.json.read_text())
    assert sidecar["Technical"]["Equipment"] == "Unknown"


def test_participant_id_must_be_alphanumeric(tmp_path: Path):
    from rrational.inspector.prism_export import export_prism_biometrics

    with pytest.raises(ValueError, match="alphanumeric"):
        export_prism_biometrics(
            SAMPLE_METRICS,
            tmp_path,
            participant_id="001/CTRL",
            task="rest",
        )


def test_unknown_columns_pass_through_tsv_but_skip_sidecar(tmp_path: Path):
    from rrational.inspector.prism_export import export_prism_biometrics

    metrics = {"n_beats": 100, "custom_metric": 42.0}
    paths = export_prism_biometrics(
        metrics, tmp_path, participant_id="001", task="rest"
    )
    with paths.tsv.open("r", encoding="utf-8") as f:
        rows = list(csv.reader(f, delimiter="\t"))
    assert rows[0] == ["n_beats", "custom_metric"]
    # n_beats is known so it has a sidecar block; custom_metric does not.
    sidecar = json.loads(paths.json.read_text())
    assert "n_beats" in sidecar
    assert "custom_metric" not in sidecar


def test_out_dir_is_created_when_missing(tmp_path: Path):
    from rrational.inspector.prism_export import export_prism_biometrics

    out = tmp_path / "nested" / "biometrics"
    paths = export_prism_biometrics(
        SAMPLE_METRICS,
        out,
        participant_id="001",
        task="rest",
        data=_make_data(),
    )
    assert out.exists()
    assert paths.tsv.parent == out
