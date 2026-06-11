"""Smoke tests for the inspector PreparationSummary glue layer.

``prep_summary`` is a compute helper, not a widget — it bridges
``InspectorData`` to the Streamlit-side ``PreparationSummary`` via
the cleaning + summary modules. These tests pin the cache
behaviour, the None-on-empty contract, and the wall-clock metadata
fields the Data tab surfaces in its table.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from rrational.cleaning.rr import CleaningConfig
from rrational.inspector.data_loader import (
    Dataset,
    EventMeta,
    InspectorData,
    SectionMeta,
)
from rrational.inspector.prep_summary import (
    compute_inspector_summary,
    invalidate_cache,
)
from rrational.prep.summaries import PreparationSummary

_T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc).timestamp()


def _make_dataset(name: str = "P01.rrational", n: int = 100) -> Dataset:
    t = _T0 + np.arange(n, dtype=np.float64)
    v = 850.0 + 10.0 * np.sin(np.linspace(0, 2 * np.pi, n))
    sections = [
        SectionMeta(name="rest", t_start=float(t[0]), t_end=float(t[-1]), beat_count=n)
    ]
    events = [EventMeta(label="rest_start", t=float(t[0]))]
    data = InspectorData(t=t, v=v, sections=sections, events=events)
    return Dataset(name=name, data=data, path=None)


def setup_function(_func):
    """Clear cache between tests — global state on the module."""
    invalidate_cache()


# ---------------------------------------------------------------------
# None / empty inputs
# ---------------------------------------------------------------------
def test_returns_none_for_none_dataset():
    assert compute_inspector_summary(None) is None


def test_returns_none_for_empty_arrays():
    data = InspectorData(t=np.array([]), v=np.array([]))
    ds = Dataset(name="empty.rrational", data=data, path=None)
    assert compute_inspector_summary(ds) is None


# ---------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------
def test_returns_preparation_summary_for_normal_dataset():
    ds = _make_dataset(n=100)
    summary = compute_inspector_summary(ds)
    assert isinstance(summary, PreparationSummary)
    # Participant id falls back to the filename stem.
    assert summary.participant_id == "P01"
    assert summary.total_beats == 100
    assert summary.source_app == "Inspector"
    # RR values cluster around 850 ms — sanity-check the range.
    assert 800.0 <= summary.rr_mean_ms <= 900.0


def test_events_count_propagates():
    ds = _make_dataset(n=50)
    # Two events on this synthetic dataset.
    ds.data.events.append(EventMeta(label="rest_end", t=ds.data.t[-1]))
    summary = compute_inspector_summary(ds)
    assert summary is not None
    assert summary.events_detected == 2


# ---------------------------------------------------------------------
# Cache + invalidate
# ---------------------------------------------------------------------
def test_cache_returns_same_summary_for_same_config():
    ds = _make_dataset()
    first = compute_inspector_summary(ds)
    second = compute_inspector_summary(ds)
    # Same identity → cache hit returns the SAME object.
    assert first is second


def test_invalidate_cache_forces_recomputation():
    ds = _make_dataset()
    first = compute_inspector_summary(ds)
    invalidate_cache()
    second = compute_inspector_summary(ds)
    # Different objects after invalidation, but logically equal.
    assert first is not second
    assert first.total_beats == second.total_beats


def test_different_cleaning_config_recomputes():
    ds = _make_dataset()
    first = compute_inspector_summary(ds, CleaningConfig())
    tight_cfg = CleaningConfig(rr_min_ms=200, rr_max_ms=1500)
    second = compute_inspector_summary(ds, tight_cfg)
    # Cache key changes with the config signature → different object.
    assert first is not second
