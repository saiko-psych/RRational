"""Regression tests for ResultsStore's value-identical-row dedup guard.

Round 30 added a dedup guard to each ``add_*_row`` appender: repeated
Compute clicks / autosave-reload cycles previously appended unbounded
duplicates, so downstream statistical tests ran on non-independent
observations. Each appender now drops a second *value-identical* row
while still accepting a genuinely different one.

All three row types are ``@dataclass(frozen=True)``, so the ``in``
membership test the guard relies on uses value equality. These tests
are pure-logic (no Qt / MainWindow) — they construct the dataclasses
directly and assert on the container length.
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


def _make_sequence_row(sequence_name: str = "rest-music-rest") -> SequenceTestRow:
    return SequenceTestRow(
        sequence_name=sequence_name,
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
# add_metric_row
# ---------------------------------------------------------------------
def test_add_metric_row_dedups_value_identical():
    store = ResultsStore()
    store.add_metric_row(_make_metric_row())
    # A second, value-identical row must be ignored.
    store.add_metric_row(_make_metric_row())
    assert len(store.metric_rows) == 1


def test_add_metric_row_appends_distinct():
    store = ResultsStore()
    store.add_metric_row(_make_metric_row())
    # A genuinely different row (other dataset) is still appended.
    store.add_metric_row(_make_metric_row(dataset="P02"))
    assert len(store.metric_rows) == 2
    assert [r.dataset for r in store.metric_rows] == ["P01", "P02"]


# ---------------------------------------------------------------------
# add_group_test_row
# ---------------------------------------------------------------------
def test_add_group_test_row_dedups_value_identical():
    store = ResultsStore()
    store.add_group_test_row(_make_group_row())
    store.add_group_test_row(_make_group_row())
    assert len(store.group_test_rows) == 1


def test_add_group_test_row_appends_distinct():
    store = ResultsStore()
    store.add_group_test_row(_make_group_row())
    store.add_group_test_row(_make_group_row(section="music"))
    assert len(store.group_test_rows) == 2
    assert [r.section for r in store.group_test_rows] == ["rest", "music"]


# ---------------------------------------------------------------------
# add_sequence_test_row
# ---------------------------------------------------------------------
def test_add_sequence_test_row_dedups_value_identical():
    store = ResultsStore()
    store.add_sequence_test_row(_make_sequence_row())
    store.add_sequence_test_row(_make_sequence_row())
    assert len(store.sequence_test_rows) == 1


def test_add_sequence_test_row_appends_distinct():
    store = ResultsStore()
    store.add_sequence_test_row(_make_sequence_row())
    store.add_sequence_test_row(_make_sequence_row(sequence_name="baseline-task"))
    assert len(store.sequence_test_rows) == 2
    assert [r.sequence_name for r in store.sequence_test_rows] == [
        "rest-music-rest",
        "baseline-task",
    ]
