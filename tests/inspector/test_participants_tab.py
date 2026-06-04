"""Tests for Phase 11 — Participants top-level tab + Protocol sub-pane."""

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
# Top-level tab shell
# ---------------------------------------------------------------------
def test_participants_tab_is_registered(main_window):
    assert main_window._participants_tab is not None
    assert main_window._participants_tab.TAB_LABEL == "Participants"


def test_participants_tab_starts_empty(main_window):
    pane = main_window._participants_tab
    assert pane._table.rowCount() == 0
    assert pane.participants == {}


# ---------------------------------------------------------------------
# Participants persistence
# ---------------------------------------------------------------------
def test_add_participant_persists_streamlit_schema(main_window):
    from rrational.gui.persistence import load_participants

    pane = main_window._participants_tab
    pane._participants["P001"] = {
        "label": "Pilot 1",
        "group": "Music",
        "sequence": "Pre-Music-Post",
        "event_order": [],
        "manual_events": [],
    }
    pane._persist()
    pane._refresh_table()

    on_disk = load_participants()
    assert "P001" in on_disk
    assert on_disk["P001"]["group"] == "Music"
    assert on_disk["P001"]["sequence"] == "Pre-Music-Post"
    assert pane._table.rowCount() == 1


def test_participants_table_columns(main_window):
    pane = main_window._participants_tab
    pane._participants["S01"] = {
        "label": "Subject 1",
        "group": "G1",
        "sequence": "Seq1",
        "manual_events": [{}, {}, {}],
    }
    pane._refresh_table()
    assert pane._table.item(0, 0).text() == "S01"
    assert pane._table.item(0, 1).text() == "Subject 1"
    assert pane._table.item(0, 2).text() == "G1"
    assert pane._table.item(0, 3).text() == "Seq1"
    assert pane._table.item(0, 4).text() == "3"


def test_import_workspace_button_creates_one_per_dataset(main_window):
    from rrational.inspector.data_loader import Dataset

    for n in ("0012MEBE.rrational", "0105LYMA.rrational"):
        main_window.add_dataset(Dataset(name=n, data=_make_data()))
    main_window.set_active_dataset(0)

    pane = main_window._participants_tab
    pane._on_import_workspace()
    assert set(pane._participants.keys()) == {"0012MEBE", "0105LYMA"}


def test_import_workspace_skips_existing(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="0012MEBE.rrational", data=_make_data()))
    main_window.set_active_dataset(0)
    pane = main_window._participants_tab
    # Pre-existing entry with rich metadata
    pane._participants["0012MEBE"] = {
        "label": "Existing",
        "group": "G1",
        "event_order": ["ev1"],
        "manual_events": [],
    }
    pane._persist()
    pane._on_import_workspace()
    # Existing entry preserved (NOT overwritten)
    assert pane._participants["0012MEBE"]["label"] == "Existing"
    assert pane._participants["0012MEBE"]["group"] == "G1"


def test_remove_participant_clears_from_disk(main_window):
    from rrational.gui.persistence import load_participants

    pane = main_window._participants_tab
    pane._participants["P1"] = {"label": "x", "event_order": [], "manual_events": []}
    pane._persist()
    assert "P1" in load_participants()
    del pane._participants["P1"]
    pane._persist()
    pane._refresh_table()
    assert load_participants() == {}
    assert pane._table.rowCount() == 0


def test_buttons_disabled_without_selection(main_window):
    pane = main_window._participants_tab
    assert pane._edit_btn.isEnabled() is False
    assert pane._remove_btn.isEnabled() is False
    # Add always enabled
    assert pane._add_btn.isEnabled() is True
    # Import disabled when no datasets loaded
    assert pane._import_btn.isEnabled() is False


def test_import_button_enabled_when_dataset_loaded(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A.rrational", data=_make_data()))
    main_window.set_active_dataset(0)
    pane = main_window._participants_tab
    assert pane._import_btn.isEnabled() is True


def test_project_open_redirects_participants_yml(main_window, tmp_path):
    """participants.yml lives in project/config/ when a project is open."""
    from rrational.gui.persistence import load_participants
    from rrational.gui.project import ProjectManager

    pm = ProjectManager.create_project(tmp_path / "Project", name="P")
    main_window.set_active_project(pm)

    pane = main_window._participants_tab
    pane._participants["ProjOnly"] = {
        "label": "proj only",
        "event_order": [],
        "manual_events": [],
    }
    pane._persist()
    # Project yaml has it
    proj_data = load_participants(project_path=pm.project_path)
    assert "ProjOnly" in proj_data
    # Global yaml does NOT
    assert "ProjOnly" not in (load_participants() or {})


# ---------------------------------------------------------------------
# Protocol pane
# ---------------------------------------------------------------------
def test_protocol_pane_starts_with_defaults(main_window):
    pane = main_window._setup_tab._protocol_pane
    proto = pane.protocol
    # The Streamlit-compatible defaults
    assert proto["expected_duration_min"] == 90.0
    assert proto["section_length_min"] == 5.0
    assert proto["pre_pause_sections"] == 9
    assert proto["post_pause_sections"] == 9
    assert proto["min_section_duration_min"] == 4.0
    assert proto["min_section_beats"] == 100
    assert proto["mismatch_strategy"] == "flag_only"


def test_protocol_save_persists_with_streamlit_schema(main_window):
    from rrational.gui.persistence import load_protocol

    pane = main_window._setup_tab._protocol_pane
    # Modify a couple of fields via the underlying widgets
    pane._expected_dur.setValue(120.0)
    pane._min_beats.setValue(250)
    pane._on_save()

    on_disk = load_protocol()
    assert on_disk["expected_duration_min"] == 120.0
    assert on_disk["min_section_beats"] == 250
    # Untouched fields keep their values
    assert on_disk["section_length_min"] == 5.0


def test_protocol_loads_existing_yaml_on_construction(qtbot, tmp_path, monkeypatch):
    """When protocol.yml already exists, the pane reads it on init."""
    from rrational.gui import persistence as gui_persistence
    from rrational.inspector import persistence, settings
    from rrational.inspector.main_window import MainWindow

    settings.enable_test_mode(tmp_path)
    persistence.set_inspector_config_dir(tmp_path)
    monkeypatch.setattr(gui_persistence, "CONFIG_DIR", tmp_path / "gui_config")
    monkeypatch.setattr(
        gui_persistence, "SETTINGS_FILE", tmp_path / "gui_config" / "settings.yml"
    )
    # Pre-write a protocol.yml
    from rrational.gui.persistence import save_protocol

    save_protocol(
        {
            "expected_duration_min": 60.0,
            "section_length_min": 2.5,
            "pre_pause_sections": 4,
            "post_pause_sections": 4,
            "min_section_duration_min": 2.0,
            "min_section_beats": 80,
            "mismatch_strategy": "reject",
        }
    )

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    pane = win._setup_tab._protocol_pane
    proto = pane.protocol
    assert proto["expected_duration_min"] == 60.0
    assert proto["mismatch_strategy"] == "reject"
    assert proto["min_section_beats"] == 80
    persistence.set_inspector_config_dir(None)


def test_protocol_reset_to_defaults_persists(main_window):
    from rrational.gui.persistence import load_protocol, save_protocol

    # Pre-set a non-default value
    save_protocol(
        {
            "expected_duration_min": 999.0,
            "section_length_min": 1.0,
            "pre_pause_sections": 1,
            "post_pause_sections": 1,
            "min_section_duration_min": 0.5,
            "min_section_beats": 1,
            "mismatch_strategy": "reject",
        }
    )
    pane = main_window._setup_tab._protocol_pane
    pane.refresh_from_workspace()  # pick up the on-disk overrides
    assert pane.protocol["expected_duration_min"] == 999.0

    pane._on_reset()
    on_disk = load_protocol()
    assert on_disk["expected_duration_min"] == 90.0  # back to default
    assert on_disk["mismatch_strategy"] == "flag_only"
