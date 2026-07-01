"""Round 32 regression tests — BIDS detect_format guard + section-cascade.

- BIDS2: detect_format on a BIDS cardiac .tsv.gz whose JSON sidecar is
  missing must return None cleanly (not latin-1-decode the gzip binary into
  garbage "lines"), and any other .gz is bailed early.
- SU2: deleting a section must purge it from every sequence; a sequence left
  with < 2 sections is dropped entirely.
"""

from __future__ import annotations

import gzip

import pytest

from rrational.io.generic_rr import detect_format


# ---------------------------------------------------------------------
# BIDS2 — detect_format guards gzip binaries
# ---------------------------------------------------------------------
def test_bids_cardiac_gz_without_sidecar_returns_none(tmp_path):
    p = tmp_path / "sub-01_task-rest_recording-cardiac_physio.tsv.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        f.write("cardiac\n800\n810\n")
    # No .json sidecar written -> must be None, not a garbage-sniffed format.
    assert detect_format(p) is None


def test_bids_cardiac_gz_with_sidecar_detected(tmp_path):
    p = tmp_path / "sub-01_task-rest_recording-cardiac_physio.tsv.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        f.write("cardiac\n800\n810\n")
    p.with_name(p.name[: -len(".tsv.gz")] + ".json").write_text("{}", encoding="utf-8")
    assert detect_format(p) == "bids_physio"


def test_arbitrary_gz_returns_none(tmp_path):
    p = tmp_path / "random.tsv.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        f.write("800\n810\n820\n")
    # A .gz that isn't a BIDS cardiac bundle is gzip binary, not sniffable.
    assert detect_format(p) is None


# ---------------------------------------------------------------------
# SU2 — deleting a section cascades to sequences
# ---------------------------------------------------------------------
def test_drop_section_from_all_filters_and_drops(qtbot, tmp_path):
    pytest.importorskip("pytestqt")
    from rrational.inspector import persistence
    from rrational.inspector.persistence import Sequence
    from rrational.inspector.tabs.setup_tab import _SequencesPane

    persistence.set_inspector_config_dir(tmp_path)
    try:

        class _FakeMW:
            _datasets: list = []

        pane = _SequencesPane(_FakeMW())
        qtbot.addWidget(pane)
        pane._sequences = [
            Sequence(name="triple", sections=["rest_pre", "music", "rest_post"]),
            Sequence(name="pair", sections=["rest_pre", "music"]),
            Sequence(name="untouched", sections=["a", "b", "c"]),
        ]

        pane.drop_section_from_all("music")

        by_name = {s.name: s for s in pane._sequences}
        # "triple" keeps its two remaining sections.
        assert by_name["triple"].sections == ["rest_pre", "rest_post"]
        # "pair" falls to a single section -> dropped entirely.
        assert "pair" not in by_name
        # A sequence not referencing "music" is untouched.
        assert by_name["untouched"].sections == ["a", "b", "c"]
    finally:
        persistence.set_inspector_config_dir(None)
