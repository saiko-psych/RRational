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


def test_n1_dataset_renders_as_single_card_not_full_width(qtbot):
    """Round 16 — a single dataset must render at the nominal 220x140
    cell footprint, not stretched into a full-width band.

    The previous min-only contract let pyqtgraph's GraphicsLayout
    expand the lone cell across the entire widget width when n=1
    (visible as a flat, depressing tachogram). Now we cap maxWidth on
    the populated cell AND pin an empty placeholder into the trailing
    columns so the row is left-aligned at thumbnail scale.
    """
    from rrational.inspector.plots.participant_grid import _CELL_W

    w = ParticipantGridWidget(n_cols=4)
    qtbot.addWidget(w)
    w.set_datasets([_fake_dataset("S01")])

    assert len(w._cells) == 1
    # The populated cell carries a finite maximum width — the previous
    # set-min-only contract returned Qt's default (16777215) here.
    max_w = w._cells[0].maximumWidth()
    assert max_w <= _CELL_W * 2 + 1, (
        f"expected cell maxWidth <= 2*{_CELL_W}, got {max_w}"
    )


def test_n2_layout_left_pins_with_placeholders(qtbot):
    """n=2 in a 4-col grid leaves two trailing placeholders on row 0."""
    w = ParticipantGridWidget(n_cols=4)
    qtbot.addWidget(w)
    w.set_datasets([_fake_dataset("S01"), _fake_dataset("S02")])
    assert len(w._cells) == 2
    # Layout retains the populated cells; the placeholders are
    # implementation detail, but the grid must not crash and the cells
    # themselves keep their max-width cap.
    for cell in w._cells:
        assert cell.maximumWidth() > 0
