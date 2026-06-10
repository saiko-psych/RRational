"""Tests for the RRBIDSPath dataclass (Cluster B5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rrational.inspector.bids_path import RRBIDSPath


def test_basename_with_required_fields_only(tmp_path: Path) -> None:
    bp = RRBIDSPath(subject="01", root=tmp_path)
    assert bp.basename == "sub-01"


def test_basename_full_entity_order(tmp_path: Path) -> None:
    bp = RRBIDSPath(subject="01", root=tmp_path, session="pre", task="rest", run="2")
    assert bp.basename == "sub-01_ses-pre_task-rest_run-2"


def test_basename_drops_none_entities(tmp_path: Path) -> None:
    bp = RRBIDSPath(subject="01", root=tmp_path, session=None, task="rest")
    assert bp.basename == "sub-01_task-rest"


def test_update_returns_new_instance_and_is_immutable(tmp_path: Path) -> None:
    bp = RRBIDSPath(subject="01", root=tmp_path)
    bp2 = bp.update(task="music")
    assert bp.task is None
    assert bp2.task == "music"
    # frozen dataclass — direct mutation raises.
    with pytest.raises(Exception):
        bp.subject = "02"  # type: ignore[misc]


def test_update_rejects_unknown_field(tmp_path: Path) -> None:
    bp = RRBIDSPath(subject="01", root=tmp_path)
    with pytest.raises(TypeError):
        bp.update(bogus="x")


def test_directory_includes_session_when_set(tmp_path: Path) -> None:
    bp = RRBIDSPath(subject="01", root=tmp_path, session="pre")
    assert bp.directory == tmp_path / "sub-01" / "ses-pre" / "physio"


def test_directory_skips_session_when_unset(tmp_path: Path) -> None:
    bp = RRBIDSPath(subject="01", root=tmp_path)
    assert bp.directory == tmp_path / "sub-01" / "physio"


def test_mkdir_creates_directory(tmp_path: Path) -> None:
    bp = RRBIDSPath(subject="01", root=tmp_path, session="pre")
    d = bp.mkdir()
    assert d.is_dir()
    assert d == tmp_path / "sub-01" / "ses-pre" / "physio"


def test_match_finds_sidecars(tmp_path: Path) -> None:
    bp = RRBIDSPath(subject="01", root=tmp_path, task="rest")
    d = bp.mkdir()
    (d / "sub-01_task-rest_physio.json").write_text("{}")
    (d / "sub-01_task-rest_physio.tsv.gz").write_text("")
    hits = bp.match(suffix="physio", extension=".json")
    assert len(hits) == 1
    assert hits[0].name == "sub-01_task-rest_physio.json"


def test_match_returns_empty_when_root_missing(tmp_path: Path) -> None:
    bp = RRBIDSPath(subject="01", root=tmp_path / "does_not_exist")
    assert bp.match() == []


def test_find_matching_sidecar_returns_none_on_miss(tmp_path: Path) -> None:
    bp = RRBIDSPath(subject="01", root=tmp_path)
    bp.mkdir()
    assert bp.find_matching_sidecar() is None
