"""Tests for inspector.persistence — YAML-backed Sequence storage."""

from __future__ import annotations

import pytest

from rrational.inspector.persistence import (
    Sequence,
    load_sequences,
    save_sequences,
    set_inspector_config_dir,
)


@pytest.fixture(autouse=True)
def temp_config_dir(tmp_path):
    set_inspector_config_dir(tmp_path)
    yield
    set_inspector_config_dir(None)


def test_load_returns_empty_when_no_file():
    assert load_sequences() == []


def test_save_then_load_roundtrip():
    seqs = [
        Sequence(name="Pre-Music-Post", sections=["rest_pre", "music", "rest_post"]),
        Sequence(name="Full", sections=["baseline", "stim", "recovery"]),
    ]
    save_sequences(seqs)
    loaded = load_sequences()
    assert len(loaded) == 2
    assert loaded[0].name == "Pre-Music-Post"
    assert loaded[0].sections == ["rest_pre", "music", "rest_post"]
    assert loaded[1].name == "Full"


def test_save_overwrites_previous_content():
    save_sequences([Sequence(name="A", sections=["x", "y"])])
    save_sequences([Sequence(name="B", sections=["p", "q"])])
    loaded = load_sequences()
    assert len(loaded) == 1
    assert loaded[0].name == "B"


def test_load_skips_empty_name_and_empty_sections():
    save_sequences(
        [
            Sequence(name="real", sections=["a", "b"]),
            Sequence(name="", sections=["c"]),
            Sequence(name="ghost", sections=[]),
        ]
    )
    loaded = load_sequences()
    assert len(loaded) == 1
    assert loaded[0].name == "real"


def test_load_survives_corrupted_yaml(tmp_path):
    # Write garbage directly to the file
    set_inspector_config_dir(tmp_path)
    (tmp_path / "sequences.yml").write_text(
        "this is :: not :: yaml :: at all", encoding="utf-8"
    )
    assert load_sequences() == []


def test_save_creates_directory_if_missing(tmp_path):
    new_dir = tmp_path / "fresh" / "deep"
    set_inspector_config_dir(new_dir)
    save_sequences([Sequence(name="A", sections=["x"])])
    assert (new_dir / "sequences.yml").exists()


def test_sequence_dataclass_roundtrip():
    s = Sequence(name="X", sections=["a", "b", "c"])
    d = s.to_dict()
    assert d == {"name": "X", "sections": ["a", "b", "c"]}
    s2 = Sequence.from_dict(d)
    assert s2.name == "X"
    assert s2.sections == ["a", "b", "c"]
