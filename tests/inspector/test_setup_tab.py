"""Tests for the Setup tab's sub-panes (Events / Sections / Groups / Sequences)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path, monkeypatch):
    from rrational.gui import persistence as gui_persistence
    from rrational.inspector import persistence, settings

    settings.enable_test_mode(tmp_path)
    persistence.set_inspector_config_dir(tmp_path)
    # Streamlit-backend persistence (groups.yml, events.yml, etc.) also
    # reads/writes a global location — patch it to the temp dir so the
    # tests don't see the developer's real RRational config.
    monkeypatch.setattr(gui_persistence, "CONFIG_DIR", tmp_path / "gui_config")
    monkeypatch.setattr(
        gui_persistence, "SETTINGS_FILE", tmp_path / "gui_config" / "settings.yml"
    )
    yield
    persistence.set_inspector_config_dir(None)


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
def test_groups_pane_starts_empty(main_window):
    """Groups pane shows group DEFINITIONS, not datasets. Empty on first run."""
    assert main_window._setup_tab._groups_pane._table.rowCount() == 0
    assert main_window._setup_tab._groups_pane.groups == {}


def test_groups_pane_add_definition_persists_to_disk(main_window):
    """Adding a group via _persist() writes groups.yml that Streamlit can read."""
    from rrational.gui.persistence import load_groups

    pane = main_window._setup_tab._groups_pane
    pane._groups["Music"] = {
        "label": "Music Group",
        "description": "Music intervention cohort",
        "members": ["alpha", "beta"],
        "expected_events": {},
        "selected_sections": [],
    }
    pane._persist()
    pane._refresh_table()

    assert pane._table.rowCount() == 1
    # Round-trip through gui.persistence.load_groups (the Streamlit reader)
    on_disk = load_groups()
    assert "Music" in on_disk
    assert on_disk["Music"]["label"] == "Music Group"
    assert on_disk["Music"]["members"] == ["alpha", "beta"]


def test_groups_pane_columns_show_name_label_members_description(main_window):
    pane = main_window._setup_tab._groups_pane
    pane._groups["Ctrl"] = {
        "label": "Control",
        "description": "no intervention",
        "members": ["m1", "m2", "m3"],
        "expected_events": {},
        "selected_sections": [],
    }
    pane._refresh_table()
    assert pane._table.item(0, 0).text() == "Ctrl"
    assert pane._table.item(0, 1).text() == "Control"
    assert pane._table.item(0, 2).text() == "3"  # member count
    assert pane._table.item(0, 3).text() == "no intervention"


def test_groups_pane_remove_removes_from_disk(main_window):
    from rrational.gui.persistence import load_groups

    pane = main_window._setup_tab._groups_pane
    pane._groups["ToDelete"] = {
        "label": "x",
        "members": [],
        "expected_events": {},
        "selected_sections": [],
    }
    pane._persist()
    assert "ToDelete" in load_groups()
    # Simulate delete
    del pane._groups["ToDelete"]
    pane._persist()
    pane._refresh_table()
    assert "ToDelete" not in load_groups()
    assert pane._table.rowCount() == 0


def test_groups_pane_buttons_disabled_without_selection(main_window):
    pane = main_window._setup_tab._groups_pane
    assert pane._edit_btn.isEnabled() is False
    assert pane._remove_btn.isEnabled() is False
    # Add button stays enabled regardless
    assert pane._add_btn.isEnabled() is True


def test_groups_pane_survives_close_all_workspace(main_window):
    """Group definitions live independently of the loaded datasets."""
    from rrational.inspector.data_loader import Dataset

    pane = main_window._setup_tab._groups_pane
    pane._groups["Stable"] = {
        "label": "Stable group",
        "members": ["A", "B"],
        "expected_events": {},
        "selected_sections": [],
    }
    pane._persist()

    main_window.add_dataset(Dataset(name="A", data=_make_data()))
    main_window.set_active_dataset(0)
    main_window.close_all_datasets()
    # The dataset workspace is empty, but the group definition persists
    assert pane._table.rowCount() == 1
    assert "Stable" in pane.groups


# ---------------------------------------------------------------------
# Phase 10: Events pane editor
# ---------------------------------------------------------------------
def test_events_pane_definitions_start_empty(main_window):
    pane = main_window._setup_tab._events_pane
    assert pane._defs_table.rowCount() == 0
    assert pane.events == {}


def test_events_pane_add_persists_with_streamlit_schema(main_window):
    """Direct save uses gui.persistence so Streamlit can read it back."""
    from rrational.gui.persistence import load_events

    pane = main_window._setup_tab._events_pane
    pane._events["rest_pre_start"] = ["Rest_Pre", "Pre_Rest", "/^ruhe.vor/i"]
    pane._persist()
    pane._refresh_defs_table()

    on_disk = load_events()
    assert on_disk == {"rest_pre_start": ["Rest_Pre", "Pre_Rest", "/^ruhe.vor/i"]}
    assert pane._defs_table.rowCount() == 1
    # Columns: name, count, preview
    assert pane._defs_table.item(0, 0).text() == "rest_pre_start"
    assert pane._defs_table.item(0, 1).text() == "3"


def test_events_pane_remove_clears_from_disk(main_window):
    from rrational.gui.persistence import load_events

    pane = main_window._setup_tab._events_pane
    pane._events["x"] = ["foo"]
    pane._persist()
    assert "x" in load_events()
    del pane._events["x"]
    pane._persist()
    pane._refresh_defs_table()
    assert load_events() == {}
    assert pane._defs_table.rowCount() == 0


def test_events_pane_buttons_disabled_without_selection(main_window):
    pane = main_window._setup_tab._events_pane
    assert pane._edit_btn.isEnabled() is False
    assert pane._remove_btn.isEnabled() is False
    assert pane._add_btn.isEnabled() is True


def test_events_pane_keeps_lower_table_for_found_events(main_window):
    """The bottom (read-only) table still mirrors data.events."""
    data = _make_data(n_events=4)
    main_window.load_data(data)
    pane = main_window._setup_tab._events_pane
    # bottom table is _table (read-only); top is _defs_table (editor)
    assert pane._table.rowCount() == 4
    assert pane._defs_table.rowCount() == 0  # editor empty


# ---------------------------------------------------------------------
# Phase 10: Sections pane editor
# ---------------------------------------------------------------------
def test_sections_pane_definitions_start_empty(main_window):
    pane = main_window._setup_tab._sections_pane
    assert pane._defs_table.rowCount() == 0
    assert pane.sections == {}


def test_sections_pane_add_persists_with_streamlit_schema(main_window):
    from rrational.gui.persistence import load_sections

    pane = main_window._setup_tab._sections_pane
    pane._sections["rest_pre"] = {
        "label": "Rest Pre",
        "description": "Baseline rest before music",
        "start_events": ["rest_pre_start"],
        "end_events": ["rest_pre_end", "music_start"],
    }
    pane._persist()
    pane._refresh_defs_table()

    on_disk = load_sections()
    assert "rest_pre" in on_disk
    assert on_disk["rest_pre"]["start_events"] == ["rest_pre_start"]
    assert on_disk["rest_pre"]["end_events"] == ["rest_pre_end", "music_start"]
    assert pane._defs_table.item(0, 2).text() == "rest_pre_start"


def test_sections_pane_dialog_uses_events_from_events_pane(main_window):
    """The SectionDialog should see events from the live EventsPane."""
    events_pane = main_window._setup_tab._events_pane
    events_pane._events["e1"] = ["alias1"]
    events_pane._events["e2"] = ["alias2"]

    sections_pane = main_window._setup_tab._sections_pane
    available = sections_pane._available_events()
    assert set(available) == {"e1", "e2"}


def test_sections_pane_keeps_lower_table_for_found_sections(main_window):
    """The bottom (read-only) table still mirrors data.sections."""
    main_window.load_data(_make_data(n_sections=3))
    pane = main_window._setup_tab._sections_pane
    assert pane._table.rowCount() == 3
    assert pane._defs_table.rowCount() == 0  # editor empty


# ---------------------------------------------------------------------
# Sequences pane
# ---------------------------------------------------------------------
def test_sequences_pane_starts_empty(main_window):
    pane = main_window._setup_tab._sequences_pane
    assert pane._table.rowCount() == 0
    assert pane.sequences == []


def test_sequences_pane_loads_preexisting_yaml(qtbot, tmp_path, qapp):
    """A sequence written to disk before MainWindow is built shows up on load."""
    from rrational.inspector import persistence, settings
    from rrational.inspector.main_window import MainWindow

    settings.enable_test_mode(tmp_path)
    persistence.set_inspector_config_dir(tmp_path)
    persistence.save_sequences(
        [persistence.Sequence(name="Pre-Post", sections=["a", "b"])]
    )
    try:
        win = MainWindow()
        win.test_mode = True
        qtbot.addWidget(win)
        pane = win._setup_tab._sequences_pane
        assert pane._table.rowCount() == 1
        assert pane._table.item(0, 0).text() == "Pre-Post"
        assert pane._table.item(0, 1).text() == "2"
    finally:
        persistence.set_inspector_config_dir(None)


def test_sequences_pane_add_persists_to_disk(main_window):
    """Adding a sequence directly (bypassing modal dialog) writes to disk."""
    from rrational.inspector.persistence import Sequence, load_sequences

    pane = main_window._setup_tab._sequences_pane
    pane._sequences.append(Sequence(name="X", sections=["s1", "s2"]))
    pane._persist()
    pane._refresh_table()

    assert pane._table.rowCount() == 1
    on_disk = load_sequences()
    assert len(on_disk) == 1
    assert on_disk[0].name == "X"


def test_sequences_pane_action_buttons_disabled_without_selection(main_window):
    pane = main_window._setup_tab._sequences_pane
    assert pane._edit_btn.isEnabled() is False
    assert pane._remove_btn.isEnabled() is False
    assert pane._duplicate_btn.isEnabled() is False
    # Add stays enabled regardless
    assert pane._add_btn.isEnabled() is True


def test_sequences_pane_available_sections_is_union_across_datasets(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(n_sections=2)))
    main_window.add_dataset(Dataset(name="B", data=_make_data(n_sections=4)))
    main_window.set_active_dataset(0)

    pane = main_window._setup_tab._sequences_pane
    available = pane._available_sections()
    # n_sections=2 → sec0, sec1; n_sections=4 → sec0..sec3
    assert set(available) == {"sec0", "sec1", "sec2", "sec3"}
