"""Smoke tests for the in-memory ResultsStore.

ResultsStore itself is plain-Python (no I/O) — the YAML round-trip
lives in ``results_persistence.py`` and is covered by
``test_results_persistence.py``. These tests pin the dataclass +
container behaviour the Analysis / Results tabs rely on.
"""

from __future__ import annotations

from rrational.inspector.results_store import (
    GroupTestRow,
    MetricRow,
    ResultsStore,
    SequenceTestRow,
)


def _make_metric_row(dataset: str = "P01", section: str = "rest") -> MetricRow:
    return MetricRow(
        mode="single",
        dataset=dataset,
        section=section,
        n_beats=300,
        metrics={"mean_rr": 850.0, "rmssd": 42.5},
    )


def _make_group_row(section: str = "rest") -> GroupTestRow:
    return GroupTestRow(
        section=section,
        metric="rmssd",
        test_name="Welch t-test",
        statistic=2.1,
        p_value=0.04,
        effect_size_name="Cohen d",
        effect_size=0.6,
        is_parametric=True,
        groups=("A", "B"),
        n_per_group={"A": 12, "B": 14},
    )


def _make_sequence_row() -> SequenceTestRow:
    return SequenceTestRow(
        sequence_name="rest-music-rest",
        metric="rmssd",
        sections=("rest_pre", "music", "rest_post"),
        n_complete_subjects=10,
        test_name="Friedman",
        statistic=8.2,
        p_value=0.016,
        effect_size_name="Kendall W",
        effect_size=0.41,
        is_parametric=False,
    )


# ---------------------------------------------------------------------
# Empty / fresh store
# ---------------------------------------------------------------------
def test_empty_store_has_no_rows():
    store = ResultsStore()
    assert store.metric_rows == []
    assert store.group_test_rows == []
    assert store.sequence_test_rows == []


# ---------------------------------------------------------------------
# add_*_row appenders
# ---------------------------------------------------------------------
def test_add_metric_row_increments_count():
    store = ResultsStore()
    store.add_metric_row(_make_metric_row())
    assert len(store.metric_rows) == 1
    store.add_metric_row(_make_metric_row(dataset="P02"))
    assert len(store.metric_rows) == 2
    # Order preserved (append semantics).
    assert store.metric_rows[0].dataset == "P01"
    assert store.metric_rows[1].dataset == "P02"


def test_add_group_test_row_increments_count():
    store = ResultsStore()
    store.add_group_test_row(_make_group_row())
    assert len(store.group_test_rows) == 1
    assert store.group_test_rows[0].test_name == "Welch t-test"


def test_add_sequence_test_row_increments_count():
    store = ResultsStore()
    store.add_sequence_test_row(_make_sequence_row())
    assert len(store.sequence_test_rows) == 1
    assert store.sequence_test_rows[0].test_name == "Friedman"


# ---------------------------------------------------------------------
# clear() drops everything
# ---------------------------------------------------------------------
def test_clear_drops_all_rows():
    store = ResultsStore()
    store.add_metric_row(_make_metric_row())
    store.add_group_test_row(_make_group_row())
    store.add_sequence_test_row(_make_sequence_row())
    assert len(store.metric_rows) == 1
    assert len(store.group_test_rows) == 1
    assert len(store.sequence_test_rows) == 1
    store.clear()
    assert store.metric_rows == []
    assert store.group_test_rows == []
    assert store.sequence_test_rows == []


# ---------------------------------------------------------------------
# Filtering by attribute (manual — Results tab pattern)
# ---------------------------------------------------------------------
def test_metric_rows_filter_by_dataset():
    """Mirrors the Results tab's per-participant filter idiom."""
    store = ResultsStore()
    store.add_metric_row(_make_metric_row(dataset="P01"))
    store.add_metric_row(_make_metric_row(dataset="P02"))
    store.add_metric_row(_make_metric_row(dataset="P01", section="music"))
    subset = [r for r in store.metric_rows if r.dataset == "P01"]
    assert len(subset) == 2
    assert {r.section for r in subset} == {"rest", "music"}


def test_metric_row_is_frozen_dataclass():
    row = _make_metric_row()
    # frozen=True → assigning to a field must raise.
    try:
        row.dataset = "P99"  # type: ignore[misc]
    except Exception:
        pass
    else:  # pragma: no cover - documents intent
        raise AssertionError("MetricRow should be frozen (immutable)")
