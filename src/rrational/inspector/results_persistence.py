"""YAML-backed persistence for the inspector's ResultsStore.

The :class:`~rrational.inspector.results_store.ResultsStore` accumulates
three row types:

- :class:`MetricRow` — one per (dataset, section) HRV compute
- :class:`GroupTestRow` — one per Group-Comparison test
- :class:`SequenceTestRow` — one per Sequence-Comparison test

Streamlit's ``group_analysis_results.yml`` stores LONG-FORMAT raw
per-participant values; the inspector's rows are AGGREGATE test stats
— a different model. To avoid format collisions we write to a
separate file, ``inspector_results.yml``, with a single top-level
structure containing all three lists.

Resolution order (mirrors the rest of inspector persistence):

1. ``{project}/data/processed/inspector_results.yml`` when a project
   is active (matches Streamlit's `data/processed/` convention for
   per-analysis outputs).
2. Global fallback: ``~/.rrational/inspector/inspector_results.yml``.

The inspector autoloads on project open and autosaves on every
successful compute; the Results tab exposes manual "Save now /
Reload from disk / Clear cache" actions for transparency.
"""

from __future__ import annotations

import math
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import yaml

from rrational.inspector.results_store import (
    GroupTestRow,
    MetricRow,
    ResultsStore,
    SequenceTestRow,
)

INSPECTOR_RESULTS_FILENAME = "inspector_results.yml"
SOFTWARE_VERSION = "inspector-phase-13"

_DEFAULT_DIR = Path.home() / ".rrational" / "inspector"


def _sanitize(value):
    """Recursively convert types YAML can't safe_dump:

    - numpy scalars → Python int/float (PyYAML doesn't know np types)
    - NaN floats → None (YAML can't round-trip NaN)
    - dataclass field dicts/lists → recursed
    """
    import numpy as _np

    if isinstance(value, _np.generic):
        value = value.item()  # numpy scalar → Python scalar
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize(v) for v in value]
    return value


def _resolve_path(project_path: Path | None) -> Path:
    """Return the absolute path of inspector_results.yml for the given scope."""
    if project_path is not None:
        target_dir = Path(project_path) / "data" / "processed"
    else:
        target_dir = _DEFAULT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / INSPECTOR_RESULTS_FILENAME


def save_results(store: ResultsStore, project_path: Path | None = None) -> Path:
    """Write the store to disk. Returns the path written.

    Empty stores still write a valid (empty-lists) file so the
    "Clear cache" button has something to delete.
    """
    import os
    import time

    target = _resolve_path(project_path)
    payload = {
        "saved_at": datetime.now().isoformat(),
        "software_version": SOFTWARE_VERSION,
        "metric_rows": [_sanitize(asdict(r)) for r in store.metric_rows],
        "group_test_rows": [_sanitize(asdict(r)) for r in store.group_test_rows],
        "sequence_test_rows": [_sanitize(asdict(r)) for r in store.sequence_test_rows],
    }
    # Round 29 — atomic write via per-call unique tmp + retry (same
    # pattern as Round 28 annotation_persistence / exclusion_persistence).
    # A crash mid-write previously left a zero-byte YAML that load_results
    # silently treated as empty store — every prior compute row lost.
    tmp = target.with_suffix(f"{target.suffix}.{os.getpid()}.{time.time_ns()}.tmp")
    tmp.write_text(
        yaml.safe_dump(payload, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    last_exc: BaseException | None = None
    for attempt in range(5):
        try:
            tmp.replace(target)
            return target
        except PermissionError as exc:
            last_exc = exc
            time.sleep(0.02 * (2**attempt))
    if last_exc is not None:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise last_exc
    return target


def load_results(project_path: Path | None = None) -> ResultsStore:
    """Load and return a fresh ResultsStore (empty if no file exists).

    Unknown / malformed entries are silently skipped — the load NEVER
    raises, so a corrupted cache can't brick the app.
    """
    target = _resolve_path(project_path)
    store = ResultsStore()
    if not target.exists():
        return store
    try:
        with target.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return store

    for entry in raw.get("metric_rows", []) or []:
        try:
            store.metric_rows.append(
                MetricRow(
                    mode=str(entry["mode"]),
                    dataset=str(entry["dataset"]),
                    section=str(entry["section"]),
                    n_beats=int(entry.get("n_beats", 0)),
                    metrics=dict(entry.get("metrics", {}) or {}),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    for entry in raw.get("group_test_rows", []) or []:
        try:
            store.group_test_rows.append(
                GroupTestRow(
                    section=str(entry["section"]),
                    metric=str(entry["metric"]),
                    test_name=str(entry["test_name"]),
                    statistic=float(entry["statistic"])
                    if entry.get("statistic") is not None
                    else float("nan"),
                    p_value=float(entry["p_value"])
                    if entry.get("p_value") is not None
                    else float("nan"),
                    effect_size_name=entry.get("effect_size_name"),
                    effect_size=(
                        float(entry["effect_size"])
                        if entry.get("effect_size") is not None
                        else None
                    ),
                    is_parametric=bool(entry.get("is_parametric", False)),
                    groups=tuple(entry.get("groups", []) or []),
                    n_per_group=dict(entry.get("n_per_group", {}) or {}),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    for entry in raw.get("sequence_test_rows", []) or []:
        try:
            store.sequence_test_rows.append(
                SequenceTestRow(
                    sequence_name=str(entry["sequence_name"]),
                    metric=str(entry["metric"]),
                    sections=tuple(entry.get("sections", []) or []),
                    n_complete_subjects=int(entry.get("n_complete_subjects", 0)),
                    test_name=str(entry["test_name"]),
                    statistic=float(entry["statistic"])
                    if entry.get("statistic") is not None
                    else float("nan"),
                    p_value=float(entry["p_value"])
                    if entry.get("p_value") is not None
                    else float("nan"),
                    effect_size_name=str(entry.get("effect_size_name", "")),
                    effect_size=(
                        float(entry["effect_size"])
                        if entry.get("effect_size") is not None
                        else float("nan")
                    ),
                    is_parametric=bool(entry.get("is_parametric", False)),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    return store


def clear_results(project_path: Path | None = None) -> bool:
    """Delete the cache file. Returns True if a file was actually removed."""
    target = _resolve_path(project_path)
    if not target.exists():
        return False
    try:
        target.unlink()
        return True
    except OSError:
        return False
