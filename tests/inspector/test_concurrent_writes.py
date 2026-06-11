"""Concurrent-write smoke tests for BIDS export, pipeline cache, annotations.

These tests catch the class of bug where two threads racing on the same
filesystem target either corrupt the output (half-written YAML, lost
sidecar) or violate the documented invariant (more than one cache entry
for a single key, missing exports). They use ``ThreadPoolExecutor``
rather than ``multiprocessing`` because the failure modes we worry
about (file overwrites, partial writes, YAML truncation) reproduce in
the in-process thread model too while staying cheap to run on CI.

We do not try to prove the production code is thread-safe in a formal
sense -- only that the happy path under contention produces the
expected on-disk shape. Real-world callers serialise writes elsewhere
(QFutureWatcher in the GUI), so these tests are about the
worst-case-from-a-script behaviour.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import yaml


def _make_data():
    from rrational.inspector.data_loader import InspectorData

    t = np.arange(0, 60, 0.8) + 1_700_000_000
    v = 800 + 30 * np.sin(np.linspace(0, np.pi, len(t)))
    return InspectorData(t=t, v=v, experimenter="Tester", device="Test")


def test_concurrent_bids_export_5_workers_5_distinct_files(tmp_path: Path) -> None:
    """Five workers exporting five distinct participant ids must end
    up with five non-empty TSV/JSON pairs. A race on the directory
    creation or filename composition would manifest as a missing pair
    or a zero-byte sidecar.
    """
    from rrational.inspector.bids_export import export_bids_physio

    data = _make_data()

    def _do_export(pid: str) -> Path:
        # Each worker gets its own destination subdir so we are testing
        # the export pipeline under contention, not the mkdir-parent
        # behaviour (which has its own dedicated tests).
        out_dir = tmp_path / pid
        out_dir.mkdir()
        return export_bids_physio(data, out_dir, participant_id=pid, task="rest").tsv_gz

    pids = [f"sub{i:03d}" for i in range(5)]
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(_do_export, pids))

    assert len(set(results)) == 5, "expected 5 distinct output paths"
    for tsv in results:
        assert tsv.exists() and tsv.stat().st_size > 0
        sidecar = tsv.with_name(tsv.name[: -len(".tsv.gz")] + ".json")
        assert sidecar.exists() and sidecar.stat().st_size > 0


def test_concurrent_bids_pipeline_cache_same_key_only_one_sidecar(
    tmp_path: Path,
) -> None:
    """Five threads asking the cache for the same (recording, fn) key
    must converge on a single sidecar file at the end. Either the
    cache wins the race once (1 sidecar, fn ran >=1 times) or the
    overwrites are idempotent (1 sidecar, same JSON contents). Either
    way, more than one sidecar with the same hash would be a contract
    violation.
    """
    from rrational.inspector.bids_pipeline import CachedBIDSPipeline

    rec = tmp_path / "recording.csv"
    rec.write_text("800\n820\n810\n")
    artefact = tmp_path / "out.json"
    artefact.write_text("{}")

    def _stable_fn(_path: Path) -> Path:
        # Return the SAME artefact path on every call -- the cache key
        # only includes mtime + fn-name, so this models the realistic
        # "same expensive computation requested by several threads".
        return artefact

    pipeline = CachedBIDSPipeline(root=tmp_path, cache_dir=tmp_path / "cache")

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(pipeline.process, rec, _stable_fn) for _ in range(5)]
        outputs = [f.result() for f in futures]

    # All threads must observe the same final artefact path.
    assert all(p == artefact for p in outputs)
    # Exactly one sidecar must live in the cache dir (same key -> same
    # filename, so concurrent writes overwrite rather than multiply).
    sidecars = list((tmp_path / "cache").glob("*.json"))
    assert len(sidecars) == 1, f"expected 1 cache sidecar, got {sidecars}"


def test_concurrent_annotation_save_yields_parseable_yaml(tmp_path: Path) -> None:
    """Five threads writing annotations to the SAME participant must
    leave a YAML file that ``yaml.safe_load`` can read. The last
    writer wins (no merge semantics in save_annotations), so we do
    NOT assert on the contents -- only that whatever survives is
    structurally valid and not a half-flushed buffer.
    """
    from rrational.inspector import persistence
    from rrational.inspector.annotation_persistence import (
        annotations_path,
        save_annotations,
    )
    from rrational.inspector.annotations import Annotation

    # Pin persistence dir at tmp so we are not poking the user profile.
    persistence.set_active_project_config_dir(tmp_path / "config")
    try:
        pid = "S99"

        def _do_save(idx: int) -> None:
            anns = [
                Annotation.create(t=float(idx) + 0.1, text=f"note-{idx}", duration=0.0)
            ]
            save_annotations(pid, anns)

        with ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(_do_save, range(5)))

        path = annotations_path(pid)
        assert path.exists()
        # Reload via yaml.safe_load to confirm the file is not
        # truncated mid-document (common failure mode for concurrent
        # rewrites without atomic-rename guards).
        with path.open("r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        assert isinstance(doc, dict)
        assert doc.get("participant_id") == pid
        # One annotation per save call, last writer wins -> exactly 1.
        assert isinstance(doc.get("annotations"), list)
        assert len(doc["annotations"]) == 1
    finally:
        persistence.set_active_project_config_dir(None)
