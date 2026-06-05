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
    assert data_tab._sources_tree is not None
    assert data_tab._participants_table is not None
    assert data_tab._bulk_import_btn is not None
    assert data_tab._bulk_assign_btn is not None
    assert data_tab._bulk_export_btn is not None


def test_participants_table_columns(data_tab):
    headers = [
        data_tab._participants_table.horizontalHeaderItem(i).text()
        for i in range(data_tab._participants_table.columnCount())
    ]
    # Phase 23A: 4 PreparationSummary columns inserted after "RR mean (ms)"
    # plus a trailing Quality badge column.
    assert headers == [
        "ID",
        "Group",
        "Sequence",
        "Beats",
        "Duration (min)",
        "RR mean (ms)",
        "Retained",
        "Artifacts %",
        "Duplicates",
        "RR range",
        "Events",
        "Sections",
        "Has artifacts",
        "Has NN",
        "Quality",
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
    assert data_tab._sources_tree.topLevelItemCount() == 0
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

    # Two top-level source rows present, in sorted order.
    assert tab._sources_tree.topLevelItemCount() == 2
    folders = {
        tab._sources_tree.topLevelItem(r).text(0).rstrip("/")
        for r in range(tab._sources_tree.topLevelItemCount())
    }
    assert folders == {"hrv_logger", "vns"}
    # Each source folder lists its files as children.
    hrv_item = next(
        tab._sources_tree.topLevelItem(r)
        for r in range(tab._sources_tree.topLevelItemCount())
        if tab._sources_tree.topLevelItem(r).text(0).startswith("hrv_logger")
    )
    assert hrv_item.childCount() == 2
    child_names = {hrv_item.child(i).text(0) for i in range(hrv_item.childCount())}
    assert child_names == {"RR_0001TEST.csv", "RR_0002TEST.csv"}

    # File counts populated via the child-count of each top-level row
    # (the third column also shows "N file(s)" but the source of truth
    # is the actual children we attached).
    counts_by_folder = {
        tab._sources_tree.topLevelItem(r)
        .text(0)
        .rstrip("/"): tab._sources_tree.topLevelItem(r).childCount()
        for r in range(tab._sources_tree.topLevelItemCount())
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
    # Phase 23A: 15-column layout. Use COL_* constants to avoid hard-coded
    # indices that drift when columns get added.
    from rrational.inspector.tabs.data_tab import (
        COL_BEATS,
        COL_DURATION,
        COL_HAS_NN,
        COL_SECTIONS,
    )

    assert data_tab._participants_table.item(row_for_pid, COL_SECTIONS).text() == "3"
    # Has NN — synthetic data has non-empty t array → "Yes"
    assert data_tab._participants_table.item(row_for_pid, COL_HAS_NN).text() == "Yes"
    # Streamlit-parity columns populate when dataset is loaded
    assert data_tab._participants_table.item(row_for_pid, COL_BEATS).text() != "-"
    assert data_tab._participants_table.item(row_for_pid, COL_DURATION).text() != "-"


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


# ---------------------------------------------------------------------
# Phase 23A — Cleaning thresholds + PreparationSummary columns
# ---------------------------------------------------------------------
def test_cleaning_thresholds_persist_across_apply(main_window, data_tab):
    """The Apply button writes the spin-box values to QSettings."""
    from rrational.inspector.settings import read_setting

    data_tab._cleaning_min_spin.setValue(350)
    data_tab._cleaning_max_spin.setValue(1800)
    data_tab._cleaning_sudden_spin.setValue(25)
    data_tab._on_apply_cleaning_clicked()

    assert float(read_setting("cleaning_min_rr_ms")) == 350.0
    assert float(read_setting("cleaning_max_rr_ms")) == 1800.0
    assert float(read_setting("cleaning_sudden_change_pct")) == 25.0


def test_retained_column_populates_after_load(main_window, data_tab):
    """Loading a dataset fills the Retained / Artifacts % / RR range cols."""
    from rrational.inspector.data_loader import Dataset
    from rrational.inspector.tabs.data_tab import (
        COL_ARTIFACT_PCT,
        COL_DUPLICATES,
        COL_RETAINED,
        COL_RR_RANGE,
    )

    main_window.add_dataset(
        Dataset(name="0099AAAA.rrational", data=_make_data(n_sections=2))
    )
    main_window.set_active_dataset(0)
    pt = main_window._participants_tab
    pt._participants["0099AAAA"] = {
        "label": "",
        "event_order": [],
        "manual_events": [],
    }
    data_tab.on_workspace_changed()

    row = None
    for r in range(data_tab._participants_table.rowCount()):
        if data_tab._participants_table.item(r, 0).text() == "0099AAAA":
            row = r
            break
    assert row is not None
    # All four PreparationSummary columns should hold real values, not "-".
    retained = data_tab._participants_table.item(row, COL_RETAINED).text()
    assert retained != "-"
    assert retained.isdigit() and int(retained) > 0
    artifact_pct = data_tab._participants_table.item(row, COL_ARTIFACT_PCT).text()
    assert artifact_pct != "-"
    assert artifact_pct.endswith("%")
    rr_range = data_tab._participants_table.item(row, COL_RR_RANGE).text()
    assert rr_range != "-"
    assert " ms" in rr_range and "-" in rr_range  # "<min>-<max> ms"
    assert data_tab._participants_table.item(row, COL_DUPLICATES).text() == "0"


# ---------------------------------------------------------------------
# Phase 24B — CSV import / export, ID pattern picker, Issues summary
# ---------------------------------------------------------------------
def test_phase24b_export_participants_csv_writes_expected_columns(
    main_window, data_tab, tmp_path
):
    """Filling the participants store then writing the CSV produces the
    expected headers + one row per participant."""
    pt = main_window._participants_tab
    pt._participants["S001"] = {
        "label": "",
        "group": "Music",
        "sequence": "Pre-Post",
        "event_order": [],
        "manual_events": [],
    }
    pt._participants["S002"] = {
        "label": "",
        "group": "Control",
        "sequence": "Pre-Post",
        "event_order": [],
        "manual_events": [],
    }
    data_tab.on_workspace_changed()

    out = tmp_path / "participants_test.csv"
    n = data_tab.export_participants_csv(out)
    assert n == 2
    text = out.read_text(encoding="utf-8")
    header = text.splitlines()[0]
    for col in (
        "ID",
        "Group",
        "Sequence",
        "Beats",
        "Duration (min)",
        "Artifacts %",
        "Duplicates",
        "Quality",
    ):
        assert col in header
    assert "S001" in text
    assert "S002" in text
    assert "Music" in text
    assert "Control" in text


def test_phase24b_id_pattern_extracts_participant_group():
    """The pattern picker's helper applies the regex and returns the
    captured 'participant' group."""
    from pathlib import Path

    from rrational.inspector.tabs.data_tab import extract_participant_id

    # Default HRV-Logger pattern: 4 digits + 4 uppercase letters
    assert extract_participant_id(Path("RR_0012MEBE_2024-01-01.csv")) == "0012MEBE"
    # Custom pattern — letters + digits like "P001"
    custom = r"(?P<participant>P\d{3})"
    assert extract_participant_id(Path("export_P017.csv"), pattern=custom) == "P017"
    # Pattern doesn't match -> fall back to stem
    fallback = extract_participant_id(Path("noid.csv"), pattern=custom)
    assert fallback == "noid"
    # Invalid regex -> safe fallback to stem
    assert (
        extract_participant_id(Path("anything.csv"), pattern="(?P<participant>[")
        == "anything"
    )


def test_phase24b_id_pattern_persists_to_qsettings(main_window, data_tab):
    """Typing into the pattern edit field writes the regex to QSettings."""
    from rrational.inspector.settings import read_setting

    new_pattern = r"(?P<participant>P\d{3})"
    data_tab._id_pattern_edit.setText(new_pattern)
    # Reading back should match
    assert read_setting("participant_id_pattern") == new_pattern


def test_phase24b_import_mapping_dialog_applies_assignments(
    main_window, tmp_path, monkeypatch
):
    """Running the import dialog merges group + sequence into participants.yml,
    auto-creating missing groups + sequences along the way."""
    from rrational.gui.project import ProjectManager
    from rrational.inspector.tabs.import_mapping_dialog import (
        ImportParticipantMappingDialog,
    )

    pm = ProjectManager.create_project(tmp_path / "MapProj", name="MapProj")
    main_window.set_active_project(pm)

    # Seed two participants in participants.yml first
    pt = main_window._participants_tab
    pt._participants = {
        "0001AAAA": {
            "label": "",
            "event_order": [],
            "manual_events": [],
        },
        "0002BBBB": {
            "label": "",
            "event_order": [],
            "manual_events": [],
        },
    }
    pt._persist()

    # Write a CSV with the mapping
    csv_path = tmp_path / "mapping.csv"
    csv_path.write_text(
        "code,group,sequence\n0001AAAA,Music,S1\n0002BBBB,Control,S2\n",
        encoding="utf-8",
    )

    dlg = ImportParticipantMappingDialog(main_window)
    dlg.set_csv_for_test(csv_path)
    # Sanity: the column combos auto-detected "code" / "group" / "sequence"
    assert dlg._id_combo.currentText() == "code"
    assert dlg._group_combo.currentText() == "group"
    assert dlg._sequence_combo.currentText() == "sequence"

    result = dlg._apply_mapping()
    assert result.updated_participants == 2
    assert "Music" in result.created_groups
    assert "Control" in result.created_groups
    assert {"S1", "S2"} <= set(result.created_sequences)

    # Reload from disk to confirm persistence
    from rrational.gui.persistence import load_groups, load_participants

    saved = load_participants(project_path=pm.project_path)
    assert saved["0001AAAA"]["group"] == "Music"
    assert saved["0001AAAA"]["sequence"] == "S1"
    assert saved["0002BBBB"]["group"] == "Control"
    groups = load_groups(project_path=pm.project_path)
    assert "Music" in groups
    assert "Control" in groups


def test_phase24b_issues_summary_filter_hides_rows(main_window, data_tab):
    """The Issues summary tags + filter hide non-matching rows."""
    pt = main_window._participants_tab
    pt._participants["S001"] = {
        "label": "",
        "event_order": [],
        "manual_events": [],
    }
    data_tab.on_workspace_changed()
    # Synthetic seeding: pretend S001 has a high-artifact tag.
    data_tab._row_issue_tags = [{"high_artifact"}]
    data_tab._on_issues_link("high_artifact")
    assert data_tab._issues_filter == "high_artifact"
    # That row stays visible
    assert data_tab._participants_table.isRowHidden(0) is False
    # Now flip to a tag the row doesn't carry — row should hide.
    data_tab._on_issues_link("no_events")
    assert data_tab._participants_table.isRowHidden(0) is True
    # Clearing the filter restores visibility.
    data_tab._on_issues_link("clear")
    assert data_tab._issues_filter is None
    assert data_tab._participants_table.isRowHidden(0) is False


def test_quality_badge_colour_matches_artifact_ratio(main_window, data_tab):
    """Quality colour reflects the helper's Good / OK / Poor mapping."""
    from qtpy.QtGui import QColor

    from rrational.inspector.data_loader import Dataset
    from rrational.inspector.tabs.data_tab import (
        COL_QUALITY,
        _QUALITY_COLOURS,
        _quality_for,
    )

    # Synthetic data with RR ~800 ms — well inside the default 300/2000
    # range, so the artifact ratio is 0 and Quality is "Good".
    main_window.add_dataset(
        Dataset(name="0042GOOD.rrational", data=_make_data(n_sections=2))
    )
    main_window.set_active_dataset(0)
    pt = main_window._participants_tab
    pt._participants["0042GOOD"] = {
        "label": "",
        "event_order": [],
        "manual_events": [],
    }
    data_tab.on_workspace_changed()

    row = None
    for r in range(data_tab._participants_table.rowCount()):
        if data_tab._participants_table.item(r, 0).text() == "0042GOOD":
            row = r
            break
    assert row is not None
    item = data_tab._participants_table.item(row, COL_QUALITY)
    assert item.text() == "Good"
    expected_colour: QColor = _QUALITY_COLOURS["Good"]
    assert item.foreground().color().rgb() == expected_colour.rgb()

    # Also exercise the pure helper across all 3 buckets.
    assert _quality_for(0.0)[0] == "Good"
    assert _quality_for(0.10)[0] == "OK"
    assert _quality_for(0.50)[0] == "Poor"
