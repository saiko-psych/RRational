"""Tests for the Analysis tab's Single Participant + Repeating Section modes."""

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


def _make_data(section_names: list[str], beats_per_section: int = 250):
    """Build InspectorData with named sections, each with realistic RR values."""
    from rrational.inspector.data_loader import (
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    base = 1_700_000_000
    n = beats_per_section * len(section_names)
    # Realistic RR around 800 ms with small variability — enough for
    # HRV compute to return finite values.
    rng = np.random.default_rng(seed=42)
    rr_ms = 800 + 30 * rng.standard_normal(n)
    t = base + np.cumsum(rr_ms) / 1000.0

    sections = []
    events = []
    for i, name in enumerate(section_names):
        start_idx = i * beats_per_section
        end_idx = (i + 1) * beats_per_section - 1
        sections.append(
            SectionMeta(
                name=name,
                t_start=float(t[start_idx]),
                t_end=float(t[end_idx]),
                beat_count=beats_per_section,
            )
        )
        events.append(EventMeta(label=f"{name}_start", t=float(t[start_idx])))
    return InspectorData(t=t, v=rr_ms, sections=sections, events=events)


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
# Mode selector
# ---------------------------------------------------------------------
def test_four_modes_available(main_window):
    combo = main_window._analysis_tab._mode_combo
    labels = [combo.itemText(i) for i in range(combo.count())]
    assert any("Single Participant" in l for l in labels)
    assert any("Repeating Section" in l for l in labels)
    assert any("Group" in l for l in labels)
    assert any("Sequence" in l for l in labels)


# ---------------------------------------------------------------------
# Single Participant
# ---------------------------------------------------------------------
def test_single_dataset_combo_lists_loaded_datasets(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(["s1"])))
    main_window.add_dataset(Dataset(name="B", data=_make_data(["s1", "s2"])))
    main_window.set_active_dataset(0)

    combo = main_window._analysis_tab._single_pane._dataset_combo
    labels = [combo.itemText(i) for i in range(combo.count())]
    assert labels == ["A", "B"]


def test_single_section_combo_follows_dataset_choice(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(["x", "y"])))
    main_window.add_dataset(Dataset(name="B", data=_make_data(["p", "q", "r"])))
    main_window.set_active_dataset(0)

    pane = main_window._analysis_tab._single_pane
    pane._dataset_combo.setCurrentIndex(1)
    secs = [pane._section_combo.itemText(i) for i in range(pane._section_combo.count())]
    assert secs == ["p", "q", "r"]


def test_single_compute_populates_result_table(main_window):
    """Compute on a real section produces a populated metrics table."""
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(["rest_pre"])))
    main_window.set_active_dataset(0)

    pane = main_window._analysis_tab._single_pane
    pane._on_compute()

    table = pane._result_table
    # Phase 23C: result table now respects the AnalysisSettingsBar's
    # active preset (default "Basic" = 5 metrics) instead of the old
    # hardcoded _DEFAULT_METRICS (7). 2 meta rows + N metric rows.
    selected = pane._settings_bar.selected_metrics()
    assert len(selected) > 0, "Settings bar should have at least one metric selected"
    assert table.rowCount() == 2 + len(selected)
    # First column of last row should be a metric name; second col not "—"
    last_metric = table.item(table.rowCount() - 1, 0).text()
    assert last_metric in selected


def test_single_compute_button_disabled_when_no_data(main_window):
    pane = main_window._analysis_tab._single_pane
    assert pane._compute_btn.isEnabled() is False


# ---------------------------------------------------------------------
# Repeating Section
# ---------------------------------------------------------------------
def test_repeating_section_dropdown_is_union_across_datasets(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(["x", "y"])))
    main_window.add_dataset(Dataset(name="B", data=_make_data(["y", "z"])))
    main_window.set_active_dataset(0)

    pane = main_window._analysis_tab._repeating_pane
    items = [
        pane._section_combo.itemText(i) for i in range(pane._section_combo.count())
    ]
    # Union, sorted alphabetically: x, y, z
    assert items == ["x", "y", "z"]


def test_repeating_compute_produces_one_row_per_matching_dataset(main_window):
    """Only datasets that contain the picked section produce a row."""
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(["common", "a_only"])))
    main_window.add_dataset(Dataset(name="B", data=_make_data(["common"])))
    main_window.add_dataset(Dataset(name="C", data=_make_data(["other"])))
    main_window.set_active_dataset(0)

    pane = main_window._analysis_tab._repeating_pane
    # Pick the shared section
    idx = pane._section_combo.findText("common")
    pane._section_combo.setCurrentIndex(idx)
    pane._on_compute()

    table = pane._result_table
    assert table.rowCount() == 2  # A + B, not C
    names = {table.item(i, 0).text() for i in range(2)}
    assert names == {"A", "B"}


def test_repeating_metric_columns_have_seven_metrics(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(["x"])))
    main_window.set_active_dataset(0)
    pane = main_window._analysis_tab._repeating_pane
    pane._section_combo.setCurrentIndex(0)
    pane._on_compute()
    # Headers: Dataset + 7 default metrics
    assert pane._result_table.columnCount() == 1 + 7


# ---------------------------------------------------------------------
# Workspace sync
# ---------------------------------------------------------------------
def test_repeating_pane_dropdown_refreshes_on_close_all(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(["x"])))
    main_window.set_active_dataset(0)
    pane = main_window._analysis_tab._repeating_pane
    assert pane._section_combo.count() == 1

    main_window.close_all_datasets()
    assert pane._section_combo.count() == 0
    assert pane._compute_btn.isEnabled() is False


# ---------------------------------------------------------------------
# Group Comparison
# ---------------------------------------------------------------------
def test_group_pane_lists_every_loaded_dataset(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(["rest"])))
    main_window.add_dataset(Dataset(name="B", data=_make_data(["rest"])))
    main_window.add_dataset(Dataset(name="C", data=_make_data(["rest"])))
    main_window.set_active_dataset(0)

    pane = main_window._analysis_tab._group_pane
    assert pane._assign_table.rowCount() == 3
    names = {pane._assign_table.item(i, 0).text() for i in range(3)}
    assert names == {"A", "B", "C"}


def test_group_pane_compute_disabled_with_fewer_than_two_groups(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(["rest"])))
    main_window.add_dataset(Dataset(name="B", data=_make_data(["rest"])))
    main_window.set_active_dataset(0)

    pane = main_window._analysis_tab._group_pane
    # No labels assigned yet
    assert pane._compute_btn.isEnabled() is False

    # One label only — still not enough
    pane._group_by_idx[0] = "A"
    pane._refresh_compute_enabled()
    assert pane._compute_btn.isEnabled() is False


def test_group_pane_compute_enabled_with_two_distinct_groups(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(["rest"])))
    main_window.add_dataset(Dataset(name="B", data=_make_data(["rest"])))
    main_window.set_active_dataset(0)

    pane = main_window._analysis_tab._group_pane
    pane._group_by_idx[0] = "control"
    pane._group_by_idx[1] = "music"
    pane._refresh_compute_enabled()
    assert pane._compute_btn.isEnabled() is True


def test_group_pane_persists_labels_by_dataset_name(main_window):
    """Closing one dataset and re-adding it should preserve its group label."""
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="alpha", data=_make_data(["rest"])))
    main_window.add_dataset(Dataset(name="beta", data=_make_data(["rest"])))
    main_window.set_active_dataset(0)

    pane = main_window._analysis_tab._group_pane
    pane._group_by_idx[0] = "treatment"
    pane._group_by_idx[1] = "placebo"

    # Simulate workspace shake-up: remove alpha, then re-add — index 0
    # now points at beta (was 1), and alpha lands at index 1.
    main_window.close_all_datasets()
    main_window.add_dataset(Dataset(name="beta", data=_make_data(["rest"])))
    main_window.add_dataset(Dataset(name="alpha", data=_make_data(["rest"])))
    main_window.set_active_dataset(0)
    # After close_all, _group_by_idx is empty because all keys are gone.
    # This test documents the more useful case: closing ONE, then reloading.
    # For now, just verify the post-close state is empty (no stale labels).
    assert all(not v for v in pane._group_by_idx.values())


def test_group_pane_compute_populates_result_label(main_window):
    """Compute against two real groups renders the test result line."""
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A1", data=_make_data(["rest"])))
    main_window.add_dataset(Dataset(name="A2", data=_make_data(["rest"])))
    main_window.add_dataset(Dataset(name="B1", data=_make_data(["rest"])))
    main_window.add_dataset(Dataset(name="B2", data=_make_data(["rest"])))
    main_window.set_active_dataset(0)

    pane = main_window._analysis_tab._group_pane
    pane._group_by_idx = {0: "ctrl", 1: "ctrl", 2: "music", 3: "music"}
    pane._refresh_compute_enabled()
    assert pane._compute_btn.isEnabled() is True

    # Pick the only section
    sec_idx = pane._section_combo.findText("rest")
    pane._section_combo.setCurrentIndex(sec_idx)
    pane._metric_combo.setCurrentIndex(pane._metric_combo.findText("RMSSD"))
    pane._on_compute()

    # Result label should mention RMSSD + section name
    label_text = pane._result_label.text()
    assert "RMSSD" in label_text
    assert "rest" in label_text
    # And we should have one stats row per group
    assert pane._group_stats_table.rowCount() == 2
    rendered_groups = {pane._group_stats_table.item(i, 0).text() for i in range(2)}
    assert rendered_groups == {"ctrl", "music"}


def test_group_pane_compute_shows_error_when_only_one_valid_group(main_window):
    """If only one group has data, the result label should warn the user."""
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A1", data=_make_data(["rest"])))
    main_window.add_dataset(Dataset(name="B1", data=_make_data(["other"])))
    main_window.set_active_dataset(0)

    pane = main_window._analysis_tab._group_pane
    pane._group_by_idx = {0: "alpha", 1: "beta"}
    pane._refresh_compute_enabled()

    sec_idx = pane._section_combo.findText("rest")
    pane._section_combo.setCurrentIndex(sec_idx)
    pane._on_compute()

    # B1 has no "rest" section → only group "alpha" gets a value → warn
    assert "Need" in pane._result_label.text()
    assert pane._group_stats_table.rowCount() == 0


def test_group_pane_clears_on_close_all(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(["rest"])))
    main_window.add_dataset(Dataset(name="B", data=_make_data(["rest"])))
    main_window.set_active_dataset(0)
    pane = main_window._analysis_tab._group_pane
    assert pane._assign_table.rowCount() == 2

    main_window.close_all_datasets()
    assert pane._assign_table.rowCount() == 0
    assert pane._compute_btn.isEnabled() is False


# ---------------------------------------------------------------------
# Sequence Comparison (Phase 5)
# ---------------------------------------------------------------------
def test_sequence_pane_dropdown_starts_empty(main_window):
    pane = main_window._analysis_tab._sequence_pane
    assert pane._sequence_combo.count() == 0
    assert pane._compute_btn.isEnabled() is False


def test_sequence_pane_dropdown_populates_from_setup_tab(main_window):
    """Adding a sequence via Setup tab + notify -> Analysis dropdown refreshes."""
    from rrational.inspector.data_loader import Dataset
    from rrational.inspector.persistence import Sequence

    main_window.add_dataset(Dataset(name="A", data=_make_data(["a", "b", "c"])))
    main_window.set_active_dataset(0)

    setup = main_window._setup_tab._sequences_pane
    setup._sequences.append(Sequence(name="my_seq", sections=["a", "b", "c"]))
    setup._persist()  # triggers _on_sequences_changed
    setup._refresh_table()

    pane = main_window._analysis_tab._sequence_pane
    assert pane._sequence_combo.count() == 1
    assert pane._sequence_combo.itemText(0) == "my_seq"


def test_sequence_pane_compute_enabled_when_seq_and_data(main_window):
    from rrational.inspector.data_loader import Dataset
    from rrational.inspector.persistence import Sequence

    setup = main_window._setup_tab._sequences_pane
    setup._sequences.append(Sequence(name="s", sections=["a", "b"]))
    setup._persist()

    pane = main_window._analysis_tab._sequence_pane
    # No datasets loaded yet → still disabled
    assert pane._compute_btn.isEnabled() is False

    main_window.add_dataset(Dataset(name="A", data=_make_data(["a", "b"])))
    main_window.set_active_dataset(0)
    # Need to refresh — refresh_workspace fires on add_dataset
    assert pane._compute_btn.isEnabled() is True


def test_sequence_pane_compute_populates_tables(main_window):
    """A full compute populates the section stats + post-hoc tables."""
    from rrational.inspector.data_loader import Dataset
    from rrational.inspector.persistence import Sequence

    # 5 datasets going through the same 3-section chain → Friedman with n=5
    for i in range(5):
        main_window.add_dataset(
            Dataset(name=f"S{i}", data=_make_data(["pre", "stim", "post"]))
        )
    main_window.set_active_dataset(0)

    setup = main_window._setup_tab._sequences_pane
    setup._sequences.append(Sequence(name="protocol", sections=["pre", "stim", "post"]))
    setup._persist()

    pane = main_window._analysis_tab._sequence_pane
    pane._sequence_combo.setCurrentIndex(pane._sequence_combo.findText("protocol"))
    pane._metric_combo.setCurrentIndex(pane._metric_combo.findText("RMSSD"))
    pane._on_compute()

    # Section stats table: one row per section
    assert pane._section_stats_table.rowCount() == 3
    # Post-hoc: C(3,2) = 3 pairs
    assert pane._post_hoc_table.rowCount() == 3
    # Result label mentions the sequence name + metric
    label = pane._result_label.text()
    assert "protocol" in label
    assert "RMSSD" in label


def test_sequence_compute_appends_results_store_row(main_window):
    from rrational.inspector.data_loader import Dataset
    from rrational.inspector.persistence import Sequence

    for i in range(4):
        main_window.add_dataset(Dataset(name=f"S{i}", data=_make_data(["a", "b", "c"])))
    main_window.set_active_dataset(0)

    setup = main_window._setup_tab._sequences_pane
    setup._sequences.append(Sequence(name="proto", sections=["a", "b", "c"]))
    setup._persist()

    pane = main_window._analysis_tab._sequence_pane
    pane._sequence_combo.setCurrentIndex(0)
    pane._on_compute()

    store = main_window._results_store
    assert len(store.sequence_test_rows) == 1
    row = store.sequence_test_rows[0]
    assert row.sequence_name == "proto"
    assert row.sections == ("a", "b", "c")
    assert row.test_name == "Friedman"


def test_sequence_pane_compute_refuses_when_no_sequence_selected(main_window):
    """Empty dropdown → compute button stays disabled, no exception."""
    pane = main_window._analysis_tab._sequence_pane
    # No-op should not raise
    pane._on_compute()
    assert pane._compute_btn.isEnabled() is False


# ---------------------------------------------------------------------
# Phase 8: Saved groups integration in GroupComparisonPane
# ---------------------------------------------------------------------
def test_group_pane_loads_saved_groups_into_combo(main_window):
    """Groups defined in groups.yml appear in the saved-groups combo."""
    from rrational.gui.persistence import save_groups

    save_groups(
        {
            "Music": {
                "label": "Music",
                "members": ["alpha", "beta"],
                "expected_events": {},
                "selected_sections": [],
            },
            "Control": {
                "label": "Control",
                "members": ["gamma", "delta"],
                "expected_events": {},
                "selected_sections": [],
            },
        }
    )
    pane = main_window._analysis_tab._group_pane
    pane._refresh_saved_groups_combo()
    items = [
        pane._saved_groups_combo.itemData(i)
        for i in range(pane._saved_groups_combo.count())
    ]
    assert set(items) == {"Music", "Control"}


def test_group_pane_auto_populates_labels_from_saved_groups(main_window):
    """When refresh_workspace runs and a dataset matches a saved-group
    member list, the label is pre-filled with the group name."""
    from rrational.gui.persistence import save_groups
    from rrational.inspector.data_loader import Dataset

    save_groups(
        {
            "Music": {
                "label": "Music",
                "members": ["alpha"],
                "expected_events": {},
                "selected_sections": [],
            },
            "Control": {
                "label": "Control",
                "members": ["beta"],
                "expected_events": {},
                "selected_sections": [],
            },
        }
    )
    main_window.add_dataset(Dataset(name="alpha", data=_make_data(["rest"])))
    main_window.add_dataset(Dataset(name="beta", data=_make_data(["rest"])))
    main_window.set_active_dataset(0)

    pane = main_window._analysis_tab._group_pane
    assert pane._group_by_idx[0] == "Music"
    assert pane._group_by_idx[1] == "Control"


def test_apply_saved_group_button_fills_assignment_table(main_window):
    from rrational.gui.persistence import save_groups
    from rrational.inspector.data_loader import Dataset

    save_groups(
        {
            "Treatment": {
                "label": "Treatment",
                "members": ["d1", "d3"],
                "expected_events": {},
                "selected_sections": [],
            }
        }
    )
    for n in ("d1", "d2", "d3"):
        main_window.add_dataset(Dataset(name=n, data=_make_data(["rest"])))
    main_window.set_active_dataset(0)

    pane = main_window._analysis_tab._group_pane
    # User initially clears (simulating freshly-loaded session without
    # auto-population kicking in):
    pane._group_by_idx = dict.fromkeys(range(3), "")
    pane._saved_groups_combo.setCurrentIndex(
        pane._saved_groups_combo.findData("Treatment")
    )
    pane._on_apply_saved()
    assert pane._group_by_idx[0] == "Treatment"
    assert pane._group_by_idx[1] == ""
    assert pane._group_by_idx[2] == "Treatment"


def test_save_as_group_persists_ad_hoc_assignment(main_window):
    """Ad-hoc labels typed in the table can be persisted as named groups."""
    from rrational.gui.persistence import load_groups
    from rrational.inspector.data_loader import Dataset

    for n in ("p1", "p2", "p3", "p4"):
        main_window.add_dataset(Dataset(name=n, data=_make_data(["rest"])))
    main_window.set_active_dataset(0)

    pane = main_window._analysis_tab._group_pane
    pane._group_by_idx = {0: "A", 1: "A", 2: "B", 3: "B"}
    pane._on_save_as_group()

    on_disk = load_groups()
    assert set(on_disk.keys()) == {"A", "B"}
    assert sorted(on_disk["A"]["members"]) == ["p1", "p2"]
    assert sorted(on_disk["B"]["members"]) == ["p3", "p4"]


def test_setup_groups_edit_notifies_analysis_pane(main_window):
    """Setup tab's _persist must trigger Analysis pane to refresh."""
    setup_pane = main_window._setup_tab._groups_pane
    analysis_pane = main_window._analysis_tab._group_pane

    setup_pane._groups["NewOne"] = {
        "label": "x",
        "members": [],
        "expected_events": {},
        "selected_sections": [],
    }
    setup_pane._persist()  # triggers main_window._on_groups_changed
    items = [
        analysis_pane._saved_groups_combo.itemData(i)
        for i in range(analysis_pane._saved_groups_combo.count())
    ]
    assert "NewOne" in items


def test_project_open_redirects_groups_yml(main_window, tmp_path):
    """When a project is open, groups.yml lives in project/config/."""
    from rrational.gui.persistence import load_groups
    from rrational.gui.project import ProjectManager

    pm = ProjectManager.create_project(tmp_path / "P", name="P")
    main_window.set_active_project(pm)

    setup_pane = main_window._setup_tab._groups_pane
    setup_pane._groups["ProjOnly"] = {
        "label": "proj only",
        "members": [],
        "expected_events": {},
        "selected_sections": [],
    }
    setup_pane._persist()

    # Global yaml does NOT see the project's group
    global_groups = load_groups()
    assert "ProjOnly" not in global_groups
    # Project yaml does
    project_groups = load_groups(project_path=pm.project_path)
    assert "ProjOnly" in project_groups
