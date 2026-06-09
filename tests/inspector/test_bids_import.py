"""BIDS-physio import (TSV.GZ + JSON sidecar) round-trip + detection."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np


def _make_data():
    from rrational.inspector.data_loader import InspectorData

    t = np.arange(0, 60, 0.8) + 1_700_000_000
    v = 800 + 30 * np.sin(np.linspace(0, np.pi, len(t)))
    return InspectorData(
        t=t,
        v=v,
        experimenter="Dr X",
        device="Polar H10",
        line_freq=50.0,
    )


def test_detect_format_recognises_bids_physio(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio
    from rrational.io.generic_rr import detect_format

    paths = export_bids_physio(
        _make_data(), tmp_path, participant_id="001", task="rest"
    )
    assert detect_format(paths.tsv_gz) == "bids_physio"


def test_detect_format_requires_matching_sidecar(tmp_path: Path):
    from rrational.io.generic_rr import detect_format

    # Manufactured .tsv.gz that LOOKS BIDS but has no sidecar.
    bogus = tmp_path / "sub-001_task-rest_recording-cardiac_physio.tsv.gz"
    with gzip.open(bogus, "wt", encoding="utf-8") as f:
        f.write("800.0\n820.0\n")
    assert detect_format(bogus) is None


def test_detect_format_ignores_unrelated_tsv_gz(tmp_path: Path):
    from rrational.io.generic_rr import detect_format

    # A gzipped TSV that doesn't have the BIDS naming pattern.
    other = tmp_path / "some_arbitrary.tsv.gz"
    with gzip.open(other, "wt", encoding="utf-8") as f:
        f.write("foo\tbar\n1\t2\n")
    assert detect_format(other) is None


def test_load_bids_physio_returns_correct_beat_count(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio
    from rrational.io.generic_rr import load_generic_rr

    data = _make_data()
    paths = export_bids_physio(data, tmp_path, participant_id="001", task="rest")
    recording = load_generic_rr(paths.tsv_gz, source_app="bids_physio")
    assert len(recording.rr_intervals) == int(np.isfinite(data.v).sum())


def test_load_bids_physio_preserves_rr_values(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio
    from rrational.io.generic_rr import load_generic_rr

    data = _make_data()
    paths = export_bids_physio(data, tmp_path, participant_id="001", task="rest")
    recording = load_generic_rr(paths.tsv_gz, source_app="bids_physio")
    # TSV writes 6 decimal places; loader rounds-to-nearest int. The
    # round-trip is therefore lossless to within 1 ms (which is the
    # native HRV resolution for every device we support).
    original = data.v[np.isfinite(data.v)]
    loaded = np.array([iv.rr_ms for iv in recording.rr_intervals])
    assert loaded.size == original.size
    assert np.allclose(loaded, np.round(original), atol=1)


def test_load_bids_physio_carries_sidecar_metadata(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio
    from rrational.io.generic_rr import load_generic_rr

    paths = export_bids_physio(
        _make_data(), tmp_path, participant_id="001", task="rest"
    )
    recording = load_generic_rr(paths.tsv_gz, source_app="bids_physio")
    assert recording.metadata["manufacturer"] == "Polar H10"
    assert recording.metadata["experimenter"] == "Dr X"


def test_load_bids_physio_anchors_timestamps_from_start_time(tmp_path: Path):
    from rrational.inspector.bids_export import export_bids_physio
    from rrational.io.generic_rr import load_generic_rr

    data = _make_data()
    paths = export_bids_physio(data, tmp_path, participant_id="001", task="rest")
    recording = load_generic_rr(paths.tsv_gz, source_app="bids_physio")
    first_ts = recording.rr_intervals[0].timestamp
    assert first_ts is not None
    # The exported StartTime is the first finite t in the data — assert
    # the reimport reproduces it within float precision.
    assert abs(first_ts.timestamp() - float(data.t[0])) < 1e-3


def test_load_bids_physio_without_sidecar_uses_safe_defaults(tmp_path: Path):
    from rrational.io.generic_rr import load_generic_rr

    # Hand-roll a TSV.GZ matching BIDS naming but no sidecar — the
    # detector skips this case, but if a caller forces source_app
    # we should still parse the body without crashing.
    bogus = tmp_path / "sub-001_task-rest_recording-cardiac_physio.tsv.gz"
    with gzip.open(bogus, "wt", encoding="utf-8") as f:
        f.write("800.0\n820.0\n810.0\n")
    rec = load_generic_rr(bogus, source_app="bids_physio")
    assert [iv.rr_ms for iv in rec.rr_intervals] == [800, 820, 810]
    # No StartTime in the (missing) sidecar -> no timestamp.
    assert rec.rr_intervals[0].timestamp is None


def test_load_bids_physio_honours_columns_array(tmp_path: Path):
    from rrational.io.generic_rr import load_generic_rr

    # Multi-column TSV; cardiac is column 1, not 0.
    tsv = tmp_path / "sub-002_task-rest_recording-cardiac_physio.tsv.gz"
    with gzip.open(tsv, "wt", encoding="utf-8") as f:
        f.write("0\t800.0\n0\t820.0\n")
    sidecar = tsv.with_name(tsv.name[: -len(".tsv.gz")] + ".json")
    sidecar.write_text(
        json.dumps(
            {
                "SamplingFrequency": 1.0,
                "StartTime": 1_700_000_000.0,
                "Columns": ["respiratory", "cardiac"],
            }
        )
    )
    rec = load_generic_rr(tsv, source_app="bids_physio")
    assert [iv.rr_ms for iv in rec.rr_intervals] == [800, 820]
