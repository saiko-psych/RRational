"""Combined BIDS-physio export -> import round-trip tests.

``test_bids_export.py`` covers export-side invariants and
``test_bids_import.py`` covers the loader. These tests instead exercise
the full export/import cycle as a single unit so any drift between the
two halves -- a sidecar field the loader stops respecting, an
anonymisation flag that gets serialised one way and parsed another --
shows up here rather than slipping past a one-sided regression.

The shared ``_make_data`` helper from the existing files is duplicated
locally (not imported) on purpose: those helpers are private to the
sibling tests and we do not want a refactor over there to silently
change what this round-trip suite is asserting.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np


def _make_data(
    experimenter: str = "Dr X",
    device: str = "Polar H10",
    line_freq: float | None = 50.0,
):
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


def test_export_import_preserves_rr_within_1ms(tmp_path: Path) -> None:
    """The TSV writes 6 decimals and the loader rounds to int ms, so
    the round-trip is lossless to within 1 ms. Verify on every finite
    sample, not just the count -- a sign-flip or scaling bug would slip
    past a length-only assertion.
    """
    from rrational.inspector.bids_export import export_bids_physio
    from rrational.io.generic_rr import load_generic_rr

    data = _make_data()
    paths = export_bids_physio(data, tmp_path, participant_id="001", task="rest")
    recording = load_generic_rr(paths.tsv_gz, source_app="bids_physio")

    original = data.v[np.isfinite(data.v)]
    loaded = np.array([iv.rr_ms for iv in recording.rr_intervals], dtype=float)
    assert loaded.size == original.size
    assert np.allclose(loaded, original, atol=1.0)


def test_export_import_preserves_metadata(tmp_path: Path) -> None:
    """Sidecar metadata (experimenter, device, line_freq) must survive
    the full round-trip. The loader stores them under the
    ``recording.metadata`` dict so we assert against that surface.
    """
    from rrational.inspector.bids_export import export_bids_physio
    from rrational.io.generic_rr import load_generic_rr

    data = _make_data(experimenter="Dr Round Trip", device="Movesense MD")
    paths = export_bids_physio(data, tmp_path, participant_id="042", task="rest")
    recording = load_generic_rr(paths.tsv_gz, source_app="bids_physio")

    assert recording.metadata["experimenter"] == "Dr Round Trip"
    assert recording.metadata["manufacturer"] == "Movesense MD"


def test_round_trip_with_anonymize_keeps_data_strips_pii(tmp_path: Path) -> None:
    """Anonymising on export should shift the timeline but keep the RR
    payload byte-for-byte (within rounding). PII fields must be absent
    after the round-trip even though the data column is unaffected.
    """
    from rrational.inspector.bids_export import export_bids_physio
    from rrational.io.generic_rr import load_generic_rr

    data = _make_data(experimenter="PII Person")
    paths = export_bids_physio(
        data,
        tmp_path,
        participant_id="001",
        task="rest",
        anonymize={"daysback": 1000},
    )
    recording = load_generic_rr(paths.tsv_gz, source_app="bids_physio")

    # Data column unaffected by anonymisation.
    original = data.v[np.isfinite(data.v)]
    loaded = np.array([iv.rr_ms for iv in recording.rr_intervals], dtype=float)
    assert np.allclose(loaded, original, atol=1.0)

    # Experimenter is the canonical PII field stripped under anonymise.
    # The loader either omits the key entirely or sets it to "" --
    # treat both as a pass so we are not coupled to one specific
    # representation.
    assert not recording.metadata.get("experimenter")

    # And the StartTime has been shifted back ~1000 days from the
    # original (86_400 s/day -- so anything not in that ballpark would
    # mean anonymisation silently dropped on the floor).
    first_ts = recording.rr_intervals[0].timestamp
    assert first_ts is not None
    shift_s = float(data.t[0]) - first_ts.timestamp()
    assert abs(shift_s - 1000 * 86_400) < 1.0


def test_round_trip_with_session_finds_via_match(tmp_path: Path) -> None:
    """Export with session='rest' should land where ``RRBIDSPath.match``
    can find it. This protects the contract that the path builder and
    the exporter agree on the BIDS basename layout.
    """
    from rrational.inspector.bids_export import export_bids_physio
    from rrational.inspector.bids_path import RRBIDSPath

    paths = export_bids_physio(
        _make_data(),
        tmp_path,
        participant_id="001",
        task="rest",
        session="rest",
    )

    bp = RRBIDSPath(subject="001", root=tmp_path, session="rest", task="rest")
    # The match() suffix is the part of the filename AFTER the core
    # entity stem -- for cardiac physio that is ``recording-cardiac_physio``.
    hits = bp.match(suffix="recording-cardiac_physio", extension=".tsv.gz")
    assert paths.tsv_gz in hits, f"export at {paths.tsv_gz} not found by match: {hits}"

    json_hits = bp.match(suffix="recording-cardiac_physio", extension=".json")
    assert paths.json in json_hits
