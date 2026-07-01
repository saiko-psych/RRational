"""In-memory store for HRV computation results.

The Analysis tab appends rows here every time the user clicks Compute;
the Results tab reads from the same store and renders them as sortable
tables. Keeping the store on MainWindow (not on either tab) means both
front-ends see the same data — and tests can drive results without
touching either UI.

Two row types:

- :class:`MetricRow` — one row per (dataset, section) compute. Used by
  Single Participant + Repeating Section modes.
- :class:`GroupTestRow` — one row per Group-Comparison Compute call.
  Captures the test name, p-value, effect size, and the group labels
  that participated.

Both are plain dataclasses; the Results tab walks ``store.metric_rows``
and ``store.group_test_rows`` directly to build its tables.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MetricRow:
    """One (dataset, section) HRV-compute result."""

    mode: str  # "single" | "repeating"
    dataset: str
    section: str
    n_beats: int
    metrics: dict[str, float]


@dataclass(frozen=True)
class GroupTestRow:
    """One between-group hypothesis test result."""

    section: str
    metric: str
    test_name: str
    statistic: float
    p_value: float
    effect_size_name: str | None
    effect_size: float | None
    is_parametric: bool
    groups: tuple[str, ...]
    n_per_group: dict[str, int]


@dataclass(frozen=True)
class SequenceTestRow:
    """One repeated-measures sequence-comparison result."""

    sequence_name: str
    metric: str
    sections: tuple[str, ...]
    n_complete_subjects: int
    test_name: str  # "Friedman" or "RM-ANOVA"
    statistic: float
    p_value: float
    effect_size_name: str
    effect_size: float
    is_parametric: bool


@dataclass
class ResultsStore:
    """All HRV results accumulated this session."""

    metric_rows: list[MetricRow] = field(default_factory=list)
    group_test_rows: list[GroupTestRow] = field(default_factory=list)
    sequence_test_rows: list[SequenceTestRow] = field(default_factory=list)

    def add_metric_row(self, row: MetricRow) -> None:
        # Round 30 — dedup guard: repeated Compute / autosave-reload cycles
        # previously appended unbounded duplicates, so statistical tests
        # ran on non-independent observations. All three row types are
        # `@dataclass(frozen=True)` so `in` uses value equality.
        if row in self.metric_rows:
            return
        self.metric_rows.append(row)

    def add_group_test_row(self, row: GroupTestRow) -> None:
        if row in self.group_test_rows:
            return
        self.group_test_rows.append(row)

    def add_sequence_test_row(self, row: SequenceTestRow) -> None:
        if row in self.sequence_test_rows:
            return
        self.sequence_test_rows.append(row)

    def clear(self) -> None:
        self.metric_rows.clear()
        self.group_test_rows.clear()
        self.sequence_test_rows.clear()
