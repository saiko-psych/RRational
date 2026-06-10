"""Smoke tests for ``ParticipantGridWidget`` (Cluster C3)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pytestqt")

from rrational.inspector.plots.participant_grid import ParticipantGridWidget


def _fake_dataset(subject_id: str, n: int = 50, mean_rr: float = 800.0):
    t = np.arange(n, dtype=float) * (mean_rr / 1000.0)
    rr = np.full(n, mean_rr, dtype=float)
    return (subject_id, t, rr)


def test_widget_constructs_empty(qtbot):
    w = ParticipantGridWidget(n_cols=4)
    qtbot.addWidget(w)
    assert w._n_cols == 4
    assert w._cells == []


def test_set_datasets_populates_cells(qtbot):
    w = ParticipantGridWidget(n_cols=2)
    qtbot.addWidget(w)
    w.set_datasets([_fake_dataset("S01"), _fake_dataset("S02"), _fake_dataset("S03")])
    assert len(w._cells) == 3


def test_set_datasets_clears_previous_cells(qtbot):
    w = ParticipantGridWidget(n_cols=2)
    qtbot.addWidget(w)
    w.set_datasets([_fake_dataset("S01"), _fake_dataset("S02")])
    assert len(w._cells) == 2
    w.set_datasets([_fake_dataset("S99")])
    assert len(w._cells) == 1


def test_empty_dataset_list_resets_grid(qtbot):
    w = ParticipantGridWidget(n_cols=3)
    qtbot.addWidget(w)
    w.set_datasets([_fake_dataset("S01")])
    w.set_datasets([])
    assert w._cells == []


def test_dataset_with_nan_gaps_renders(qtbot):
    """connect='finite' should accept arrays with NaN inter-section gaps."""
    w = ParticipantGridWidget(n_cols=1)
    qtbot.addWidget(w)
    t = np.arange(100, dtype=float)
    rr = np.full(100, 800.0)
    rr[40:60] = np.nan  # gap
    w.set_datasets([("S01", t, rr)])
    assert len(w._cells) == 1


def test_click_callback_default_is_noop(qtbot):
    w = ParticipantGridWidget(n_cols=1)
    qtbot.addWidget(w)
    # Should not raise even if the user never installs a callback.
    w.on_subject_click("S01")
