"""Tests for the content-addressed BIDS pipeline cache (Cluster C8)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rrational.inspector.bids_pipeline import CachedBIDSPipeline


def _make_recording(tmp_path: Path, name: str = "rec.csv") -> Path:
    p = tmp_path / name
    p.write_text("rr_ms\n850\n860\n870\n", encoding="utf-8")
    return p


def test_process_cache_miss_runs_fn_and_persists_sidecar(tmp_path):
    pipeline = CachedBIDSPipeline(root=tmp_path)
    recording = _make_recording(tmp_path)
    calls: list[Path] = []

    def my_fn(rec: Path) -> Path:
        calls.append(rec)
        artefact = tmp_path / "out" / f"{rec.stem}.processed"
        artefact.parent.mkdir(parents=True, exist_ok=True)
        artefact.write_text("processed", encoding="utf-8")
        return artefact

    result = pipeline.process(recording, my_fn)
    assert result.read_text(encoding="utf-8") == "processed"
    assert len(calls) == 1
    # Sidecar exists in the cache dir.
    sidecars = list(pipeline.cache_dir.glob("*.json"))
    assert len(sidecars) == 1


def test_process_cache_hit_skips_fn_on_second_call(tmp_path):
    pipeline = CachedBIDSPipeline(root=tmp_path)
    recording = _make_recording(tmp_path)
    calls: list[Path] = []

    def my_fn(rec: Path) -> Path:
        calls.append(rec)
        artefact = tmp_path / f"{rec.stem}.processed"
        artefact.write_text("processed", encoding="utf-8")
        return artefact

    first = pipeline.process(recording, my_fn)
    second = pipeline.process(recording, my_fn)
    assert first == second
    # fn ran exactly ONCE — the second call hit the cache.
    assert len(calls) == 1


def test_process_invalidates_when_artefact_deleted(tmp_path):
    pipeline = CachedBIDSPipeline(root=tmp_path)
    recording = _make_recording(tmp_path)
    calls = []

    def my_fn(rec: Path) -> Path:
        calls.append(rec)
        artefact = tmp_path / f"{rec.stem}.processed"
        artefact.write_text("processed", encoding="utf-8")
        return artefact

    first = pipeline.process(recording, my_fn)
    first.unlink()  # drop the cached artefact
    pipeline.process(recording, my_fn)
    # fn ran twice because the cached file no longer exists.
    assert len(calls) == 2


def test_process_raises_typeerror_when_fn_returns_non_path(tmp_path):
    pipeline = CachedBIDSPipeline(root=tmp_path)
    recording = _make_recording(tmp_path)

    def bad_fn(rec):
        return "not-a-path"

    with pytest.raises(TypeError, match="Path"):
        pipeline.process(recording, bad_fn)


def test_custom_cache_dir_is_respected(tmp_path):
    custom = tmp_path / "elsewhere"
    pipeline = CachedBIDSPipeline(root=tmp_path, cache_dir=custom)
    assert pipeline.cache_dir == custom
    assert custom.is_dir()
