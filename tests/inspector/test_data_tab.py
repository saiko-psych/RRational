"""Tests for Phase 22.1 — Streamlit-style Data tab."""

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


def _make_data(n_sections: int = 2, n_events: int = 1):
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


@pytest.fixture
def data_tab(main_window):
    """Instantiate the DataTab against the live MainWindow.

    The MainWindow doesn't yet host the DataTab itself (that's another
    agent's task) — these tests just confirm the tab is independently
    constructible and observes shared state correctly.
    """
    from rrational.inspector.tabs.data_tab import DataTab

    return DataTab(main_window)


# ---------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------
def test_data_tab_instantiates(data_tab):
    assert data_tab.TAB_LABEL == "Data"
    # Core widgets exist
    assert data_tab._project_label is not None
    assert data_tab._sources_table is not None
    assert data_tab._participants_table is not None
    assert data_tab._bulk_import_btn is not None
    assert data_tab._bulk_assign_btn is not None
    assert data_tab._bulk_export_btn is not None


def test_participants_table_columns(data_tab):
    headers = [
        data_tab._participants_table.horizontalHeaderItem(i).text()
        for i in range(data_tab._participants_table.columnCount())
    ]
    assert headers == [
        "ID",
        "Group",
        "Sequence",
        "Section count",
        "Has artifacts",
        "Has NN intervals",
    ]


# ---------------------------------------------------------------------
# Project info block
# ---------------------------------------------------------------------
def test_project_block_shows_no_project_when_none_open(data_tab):
    text = data_tab._project_label.text()
    assert "No project active" in text
    assert data_tab._project_path_label.text() == ""
    assert data_tab._close_project_btn.isEnabled() is False


def test_project_block_shows_name_and_path_when_open(main_window, tmp_path):
    from rrational.gui.project import ProjectManager
    from rrational.inspector.tabs.data_tab import DataTab

    pm = ProjectManager.create_project(tmp_path / "MyProj", name="MyProj")
    main_window.set_active_project(pm)

    tab = DataTab(main_window)
    assert "MyProj" in tab._project_label.text()
    assert str(pm.project_path) == tab._project_path_label.text()
    assert tab._close_project_btn.isEnabled() is True


# ---------------------------------------------------------------------
# Data sources block
# ---------------------------------------------------------------------
def test_sources_block_empty_without_project(data_tab):
    assert data_tab._sources_table.rowCount() == 0
    assert "Open a project" in data_tab._sources_label.text()


def test_sources_block_lists_raw_subfolders(main_window, tmp_path):
    from rrational.gui.project import ProjectManager
    from rrational.inspector.tabs.data_tab import DataTab

    pm = ProjectManager.create_project(tmp_path / "Proj", name="Proj")
    raw = pm.get_data_dir()
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "hrv_logger").mkdir(exist_ok=True)
    (raw / "hrv_logger" / "RR_0001TEST.csv").write_text("rr\n800\n")
    (raw / "hrv_logger" / "RR_0002TEST.csv").write_text("rr\n810\n")
    (raw / "vns").mkdir(exist_ok=True)
    (raw / "vns" / "p1.txt").write_text("1.0\n0.8\n")

    main_window.set_active_project(pm)
    tab = DataTab(main_window)

    # Two source rows present, in sorted order
    assert tab._sources_table.rowCount() == 2
    folders = {
        tab._sources_table.item(r, 0).text()
        for r in range(tab._sources_table.rowCount())
    }
    assert folders == {"hrv_logger", "vns"}

    # File counts populated
    counts_by_folder = {
        tab._sources_table.item(r, 0).text(): int(tab._sources_table.item(r, 2).text())
        for r in range(tab._sources_table.rowCount())
    }
    assert counts_by_folder["hrv_logger"] == 2
    assert counts_by_folder["vns"] == 1


# ---------------------------------------------------------------------
# Participants table reflects shared state
# ---------------------------------------------------------------------
def test_participants_table_populates_from_main_window_state(main_window, data_tab):
    pt = main_window._participants_tab
    pt._participants["S001"] = {
        "label": "Subject 1",
        "group": "Music",
        "sequence": "Pre-Music-Post",
        "manual_events": [],
        "event_order": [],
    }
    pt._participants["S002"] = {
        "label": "Subject 2",
        "group": "Control",
        "sequence": "Pre-Pause-Post",
        "manual_events": [],
        "event_order": [],
    }
    data_tab.on_workspace_changed()
    assert data_tab._participants_table.rowCount() == 2
    # Pull IDs out (sorted) — sort stability is preserved by sorted() in
    # the refresh code; explicitly enumerate so the assertion is robust
    # to QTableWidget's internal sort handling.
    ids = {
        data_tab._participants_table.item(r, 0).text()
        for r in range(data_tab._participants_table.rowCount())
    }
    assert ids == {"S001", "S002"}


def test_participants_table_section_count_uses_loaded_dataset(main_window, data_tab):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(
        Dataset(name="0012MEBE.rrational", data=_make_data(n_sections=3))
    )
    main_window.set_active_dataset(0)
    pt = main_window._participants_tab
    pt._participants["0012MEBE"] = {
        "label": "",
        "event_order": [],
        "manual_events": [],
    }
    data_tab.on_workspace_changed()
    # Find the row for 0012MEBE
    row_for_pid = None
    for r in range(data_tab._participants_table.rowCount()):
        if data_tab._participants_table.item(r, 0).text() == "0012MEBE":
            row_for_pid = r
            break
    assert row_for_pid is not None
    assert data_tab._participants_table.item(row_for_pid, 3).text() == "3"
    # Has NN intervals → yes (the synthetic data has a non-empty t array)
    assert data_tab._participants_table.item(row_for_pid, 5).text() == "Yes"


# ---------------------------------------------------------------------
# Bulk action button enablement
# ---------------------------------------------------------------------
def test_bulk_import_disabled_without_project_raw_files(data_tab):
    assert data_tab._bulk_import_btn.isEnabled() is False
    assert data_tab._bulk_assign_btn.isEnabled() is False
    assert data_tab._bulk_export_btn.isEnabled() is False


def test_bulk_import_enabled_when_project_has_raw_files(main_window, tmp_path):
    from rrational.gui.project import ProjectManager
    from rrational.inspector.tabs.data_tab import DataTab

    pm = ProjectManager.create_project(tmp_path / "Proj", name="Proj")
    raw = pm.get_data_dir()
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "hrv_logger").mkdir(exist_ok=True)
    (raw / "hrv_logger" / "RR_001.csv").write_text("rr\n800\n")

    main_window.set_active_project(pm)
    tab = DataTab(main_window)
    assert tab._bulk_import_btn.isEnabled() is True


def test_bulk_assign_enabled_when_workspace_has_datasets(main_window, data_tab):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A.rrational", data=_make_data()))
    main_window.set_active_dataset(0)
    data_tab.on_workspace_changed()
    assert data_tab._bulk_assign_btn.isEnabled() is True
    assert data_tab._bulk_export_btn.isEnabled() is True


# ---------------------------------------------------------------------
# Tab label state badge
# ---------------------------------------------------------------------
def test_tab_label_state_empty_when_no_data(data_tab):
    assert data_tab.tab_label_state() == "(empty)"


def test_tab_label_state_counts_participants_and_datasets(main_window, data_tab):
    from rrational.inspector.data_loader import Dataset

    # Add the dataset FIRST — add_dataset fans on_workspace_changed out
    # to every registered tab, which causes ParticipantsTab to reload
    # from disk and wipe any in-memory test injection we did beforehand.
    main_window.add_dataset(Dataset(name="A.rrational", data=_make_data()))
    main_window.set_active_dataset(0)

    pt = main_window._participants_tab
    pt._participants["S001"] = {
        "label": "",
        "event_order": [],
        "manual_events": [],
    }
    pt._participants["S002"] = {
        "label": "",
        "event_order": [],
        "manual_events": [],
    }

    label = data_tab.tab_label_state()
    assert "2 participant" in label
    assert "1 dataset" in label


# ---------------------------------------------------------------------
# Active-dataset hook is a no-op for this workspace-level tab
# ---------------------------------------------------------------------
def test_on_active_dataset_changed_is_a_noop(data_tab):
    # Just verify it doesn't raise; the participants table shouldn't
    # mutate its row count on an active-dataset switch.
    before = data_tab._participants_table.rowCount()
    data_tab.on_active_dataset_changed(None)
    assert data_tab._participants_table.rowCount() == before
