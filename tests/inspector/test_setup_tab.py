"""Tests for the Setup tab's sub-panes (Events / Sections / Groups / Sequences)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path):
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    yield


def _make_data(n_sections=2, n_events=3):
    from rrational.inspector.data_loader import (
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    n_beats = max(300, n_sections * 100 + 10)
    base = 1_700_000_000
    t = base + np.arange(n_beats, dtype=np.float64)
    v = 800 + 10 * np.sin(np.linspace(0, 2 * np.pi, n_beats))
    sections = [
        SectionMeta(
            name=f"sec{i}",
            t_start=float(t[i * 100]),
            t_end=float(t[(i + 1) * 100 - 1]),
            beat_count=100,
        )
        for i in range(n_sections)
    ]
    events = [EventMeta(label=f"ev{i}", t=float(t[i * 50])) for i in range(n_events)]
    return InspectorData(t=t, v=v, sections=sections, events=events)


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


# ---------------------------------------------------------------------
# Sub-tab shell
# ---------------------------------------------------------------------
def test_setup_has_four_subtabs(main_window):
    setup = main_window._setup_tab
    titles = [setup._subtabs.tabText(i) for i in range(setup._subtabs.count())]
    assert titles == ["Events", "Sections", "Groups", "Sequences"]


# ---------------------------------------------------------------------
# Events pane
# ---------------------------------------------------------------------
def test_events_pane_empty_before_load(main_window):
    assert main_window._setup_tab._events_pane._table.rowCount() == 0


def test_events_pane_populated_after_load(main_window):
    data = _make_data(n_sections=2, n_events=5)
    main_window.load_data(data)
    table = main_window._setup_tab._events_pane._table
    assert table.rowCount() == 5
    # First column should match the first event label
    assert table.item(0, 0).text() == "ev0"


def test_events_pane_clears_on_close_all(main_window):
    main_window.load_data(_make_data())
    main_window.close_all_datasets()
    assert main_window._setup_tab._events_pane._table.rowCount() == 0


# ---------------------------------------------------------------------
# Sections pane
# ---------------------------------------------------------------------
def test_sections_pane_populated_after_load(main_window):
    main_window.load_data(_make_data(n_sections=3))
    table = main_window._setup_tab._sections_pane._table
    assert table.rowCount() == 3
    # Columns: name, start, end, duration, beats
    assert table.item(0, 0).text() == "sec0"
    assert table.item(0, 4).text() == "100"  # beat_count


# ---------------------------------------------------------------------
# Groups pane
# ---------------------------------------------------------------------
def test_groups_pane_lists_every_loaded_dataset(main_window):
    """One row per loaded Dataset."""
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(n_sections=2)))
    main_window.add_dataset(Dataset(name="B", data=_make_data(n_sections=4)))
    main_window.set_active_dataset(0)

    table = main_window._setup_tab._groups_pane._table
    assert table.rowCount() == 2
    names = {table.item(i, 0).text() for i in range(2)}
    assert names == {"A", "B"}


def test_groups_pane_shows_section_count(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(n_sections=2)))
    main_window.set_active_dataset(0)
    table = main_window._setup_tab._groups_pane._table
    # Section-count column for first dataset
    assert table.item(0, 1).text() == "2"


def test_groups_pane_clears_on_close_all(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data()))
    main_window.set_active_dataset(0)
    main_window.close_all_datasets()
    assert main_window._setup_tab._groups_pane._table.rowCount() == 0
