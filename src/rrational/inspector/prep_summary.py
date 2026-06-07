"""Inspector-side helper for computing PreparationSummary from a Dataset.

Surfaces the Streamlit prep pipeline (artifact ratio, retained beats,
duplicate count, RR range, artifact reasons) inside the Inspector's
Data tab.

Reuses the existing ``rrational.prep.summaries`` and
``rrational.cleaning.rr`` modules — this file is glue, not a
re-implementation. The summary is built from the in-memory
``InspectorData`` (``t`` + ``v`` arrays) by reconstructing a minimal
list of ``RRInterval`` objects and delegating to ``clean_rr_intervals``
+ ``rr_summary`` exactly the way ``summarize_recording`` does.

Caching: ``compute_inspector_summary`` keeps a per-``id(dataset)`` LRU
so re-rendering the participants table is O(participant_count) cheap.
Call ``invalidate_cache()`` after changing the ``CleaningConfig``.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from rrational.cleaning.rr import CleaningConfig, clean_rr_intervals, rr_summary
from rrational.io.hrv_logger import RRInterval
from rrational.prep.summaries import PreparationSummary


# id(dataset) -> (config_signature, PreparationSummary | None).
# Keyed by ``id()`` rather than dataset name so renaming/reloading a
# file doesn't return stale numbers.
_SUMMARY_CACHE: dict[int, tuple[tuple, PreparationSummary | None]] = {}


def _config_signature(config: CleaningConfig) -> tuple:
    return (config.rr_min_ms, config.rr_max_ms, config.sudden_change_pct)


def invalidate_cache(dataset_id: int | None = None) -> None:
    """Drop cached summaries.

    Pass an explicit ``id(dataset)`` to invalidate one entry, or omit to
    clear everything (e.g. after the user changes thresholds).
    """
    if dataset_id is None:
        _SUMMARY_CACHE.clear()
    else:
        _SUMMARY_CACHE.pop(dataset_id, None)


def _build_rr_intervals_from_data(data) -> list[RRInterval]:
    """Reconstruct a list of ``RRInterval`` objects from ``InspectorData``.

    ``InspectorData`` stores ``t`` (seconds-since-epoch) and ``v``
    (RR-ms) with possible NaN gaps between sections. We drop the NaN
    samples and pair the remaining ``t``/``v`` values back into
    ``RRInterval`` records so the downstream cleaning code sees
    something it understands.
    """
    if data is None:
        return []
    t = getattr(data, "t", None)
    v = getattr(data, "v", None)
    if t is None or v is None:
        return []
    t_arr = np.asarray(t, dtype=np.float64)
    v_arr = np.asarray(v, dtype=np.float64)
    if t_arr.size == 0 or v_arr.size == 0:
        return []
    mask = np.isfinite(t_arr) & np.isfinite(v_arr)
    if not mask.any():
        return []
    t_clean = t_arr[mask]
    v_clean = v_arr[mask]
    intervals: list[RRInterval] = []
    for ts_s, rr_ms in zip(t_clean.tolist(), v_clean.tolist()):
        try:
            dt = datetime.fromtimestamp(float(ts_s), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            dt = None
        intervals.append(
            RRInterval(timestamp=dt, rr_ms=int(round(float(rr_ms))), elapsed_ms=None)
        )
    return intervals


def _participant_id_for(dataset) -> str:
    """Best-effort participant id for a Dataset (filename stem)."""
    name = getattr(dataset, "name", "") or ""
    from pathlib import Path as _Path

    stem = _Path(name).stem
    return stem or name or "unknown"


def compute_inspector_summary(
    dataset, cleaning_config: CleaningConfig | None = None
) -> PreparationSummary | None:
    """Return a ``PreparationSummary`` for an Inspector ``Dataset``.

    Returns ``None`` when the dataset is too sparse to clean (no
    intervals after dropping NaN gaps). Results are cached per
    ``id(dataset)`` keyed by the cleaning config so repeated calls
    inside a single table refresh are essentially free.
    """
    if dataset is None:
        return None
    cfg = cleaning_config or CleaningConfig()
    sig = _config_signature(cfg)
    key = id(dataset)
    cached = _SUMMARY_CACHE.get(key)
    if cached is not None and cached[0] == sig:
        return cached[1]

    data = getattr(dataset, "data", None)
    intervals = _build_rr_intervals_from_data(data)
    if not intervals:
        _SUMMARY_CACHE[key] = (sig, None)
        return None

    cleaned, stats = clean_rr_intervals(intervals, cfg)
    rr_stats = rr_summary(cleaned or intervals)

    pid = _participant_id_for(dataset)
    n_events = len(getattr(data, "events", []) or []) if data is not None else 0
    first_ts = intervals[0].timestamp
    last_ts = intervals[-1].timestamp

    summary = PreparationSummary(
        participant_id=pid,
        recording_datetime=first_ts,
        first_timestamp=first_ts,
        last_timestamp=last_ts,
        total_beats=stats.total_samples,
        retained_beats=stats.retained_samples,
        removed_beats=stats.removed_samples,
        artifact_ratio=stats.artifact_ratio,
        duration_s=rr_stats["duration_s"],
        events_detected=n_events,
        duplicate_events=0,
        duplicate_rr_intervals=0,
        duplicate_details=[],
        rr_min_ms=rr_stats["min"],
        rr_max_ms=rr_stats["max"],
        rr_mean_ms=rr_stats["mean"],
        artifact_reasons=dict(stats.reasons),
        events=[],
        present_sections=set(),
        source_app="Inspector",
    )
    _SUMMARY_CACHE[key] = (sig, summary)
    return summary


__all__ = ["compute_inspector_summary", "invalidate_cache"]
