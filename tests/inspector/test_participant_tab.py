"""Tests for Phase 22.2 — Participant tab (per-subject deep-dive).

The ParticipantTab is built as a standalone widget — it isn't auto-
registered in MainWindow's tab list (that's a separate worktree).
These tests instantiate the tab directly with a live MainWindow as
its workspace anchor, then drive it through the same notification
hooks the MainWindow would.
"""

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


def _make_data(n_sections=2):
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
    events = [EventMeta(label=f"ev{i}", t=float(t[i * 50])) for i in range(n_sections)]
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
def participant_tab(main_window, qtbot):
    from rrational.inspector.tabs.participant_tab import ParticipantTab

    tab = ParticipantTab(main_window)
    qtbot.addWidget(tab)
    tab.show()
    qtbot.waitExposed(tab)
    return tab


# ---------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------
def test_tab_instantiates_with_correct_label(participant_tab):
    assert participant_tab.TAB_LABEL == "Participant"


def test_tab_has_plot_and_preprocessing_panel(participant_tab):
    """ParticipantTab must REUSE RRPlotWidget + PreprocessingPanel (not duplicate)."""
    from rrational.inspector.plot_widget import RRPlotWidget
    from rrational.inspector.tabs.preprocessing_panel import PreprocessingPanel

    assert isinstance(participant_tab._plot, RRPlotWidget)
    assert isinstance(participant_tab._preprocessing_panel, PreprocessingPanel)


def test_starts_in_empty_state(participant_tab):
    assert participant_tab._participant_combo.count() == 0
    assert participant_tab._sections_list.count() == 0
    assert "No participants" in participant_tab._status_label.text()
    assert not participant_tab._prev_btn.isEnabled()
    assert not participant_tab._next_btn.isEnabled()


# ---------------------------------------------------------------------
# Tab label state badge
# ---------------------------------------------------------------------
def test_tab_label_state_empty(participant_tab):
    assert participant_tab.tab_label_state() == "(none selected)"


def test_tab_label_state_with_active_dataset(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="0012MEBE.rrational", data=_make_data()))
    main_window.set_active_dataset(0)
    # MainWindow doesn't know about this tab, so notify it manually:
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)
    assert participant_tab.tab_label_state() == "(showing 0012MEBE)"


# ---------------------------------------------------------------------
# Dropdown populates from the workspace
# ---------------------------------------------------------------------
def test_dropdown_populates_from_workspace(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    for n in ("0012MEBE.rrational", "0105LYMA.rrational", "0211ABCD.rrational"):
        main_window.add_dataset(Dataset(name=n, data=_make_data()))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)

    assert participant_tab._participant_combo.count() == 3
    items = [
        participant_tab._participant_combo.itemText(i)
        for i in range(participant_tab._participant_combo.count())
    ]
    assert items == ["0012MEBE", "0105LYMA", "0211ABCD"]


def test_dropdown_stem_uses_path_stem_when_available(
    main_window, participant_tab, tmp_path
):
    from rrational.inspector.data_loader import Dataset

    p = tmp_path / "P099XYZ.rrational"
    p.write_text("dummy")
    main_window.add_dataset(Dataset(name=p.name, data=_make_data(), path=p))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    assert participant_tab._participant_combo.itemText(0) == "P099XYZ"


# ---------------------------------------------------------------------
# Dropdown triggers set_active_dataset
# ---------------------------------------------------------------------
def test_dropdown_pick_calls_set_active_dataset(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    for n in ("0012MEBE.rrational", "0105LYMA.rrational"):
        main_window.add_dataset(Dataset(name=n, data=_make_data()))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()

    calls: list[int] = []
    original = main_window.set_active_dataset

    def spy(idx: int) -> None:
        calls.append(idx)
        original(idx)

    main_window.set_active_dataset = spy
    # User picks the second participant via the dropdown.
    participant_tab._participant_combo.setCurrentIndex(1)
    assert 1 in calls
    assert main_window._active_idx == 1


# ---------------------------------------------------------------------
# Prev / Next arrow buttons
# ---------------------------------------------------------------------
def test_next_button_advances_active(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    for n in ("A.rrational", "B.rrational", "C.rrational"):
        main_window.add_dataset(Dataset(name=n, data=_make_data()))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)

    participant_tab._on_next_clicked()
    # The tab isn't registered on MainWindow in this test, so we relay
    # the notification by hand — in production, _notify_tabs_active_changed
    # would call this for us.
    participant_tab.on_active_dataset_changed(main_window._data)
    assert main_window._active_idx == 1
    participant_tab._on_next_clicked()
    participant_tab.on_active_dataset_changed(main_window._data)
    assert main_window._active_idx == 2
    # Disabled at the end.
    assert not participant_tab._next_btn.isEnabled()


def test_prev_button_goes_back(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    for n in ("A.rrational", "B.rrational"):
        main_window.add_dataset(Dataset(name=n, data=_make_data()))
    main_window.set_active_dataset(1)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)

    participant_tab._on_prev_clicked()
    participant_tab.on_active_dataset_changed(main_window._data)
    assert main_window._active_idx == 0
    assert not participant_tab._prev_btn.isEnabled()


def test_status_label_reflects_position(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    for n in ("A.rrational", "B.rrational", "C.rrational"):
        main_window.add_dataset(Dataset(name=n, data=_make_data()))
    main_window.set_active_dataset(1)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)
    assert "2 of 3" in participant_tab._status_label.text()


# ---------------------------------------------------------------------
# Section list shows section names + plot renders
# ---------------------------------------------------------------------
def test_sections_list_shows_section_names(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="P1.rrational", data=_make_data(n_sections=3)))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)

    assert participant_tab._sections_list.count() == 3
    # The UserRole payload carries the section name (the visible widget
    # is a rich-text row composed inside _rebuild_sections_list).
    from rrational.inspector.tabs.participant_tab import _ROLE_SECTION_NAME

    names = [
        participant_tab._sections_list.item(i).data(_ROLE_SECTION_NAME)
        for i in range(participant_tab._sections_list.count())
    ]
    assert names == ["sec0", "sec1", "sec2"]


def test_plot_renders_active_dataset(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    data = _make_data(n_sections=2)
    main_window.add_dataset(Dataset(name="P1.rrational", data=data))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)

    assert participant_tab._plot._times is not None
    assert len(participant_tab._plot._times) == len(data.t)


def test_section_click_zooms_plot(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    data = _make_data(n_sections=2)
    main_window.add_dataset(Dataset(name="P1.rrational", data=data))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)

    item = participant_tab._sections_list.item(1)
    participant_tab._on_section_clicked(item)

    # The view-range should now overlap section 1's [t_start, t_end] window
    # rather than the full recording.
    sec = data.sections[1]
    x0, x1 = participant_tab._plot.getViewBox().viewRange()[0]
    assert x0 <= sec.t_start + 1  # padding allowed
    assert x1 >= sec.t_end - 1


# ---------------------------------------------------------------------
# Empty-state recovery
# ---------------------------------------------------------------------
def test_closing_all_clears_tab(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="P1.rrational", data=_make_data()))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)
    assert participant_tab._sections_list.count() > 0

    main_window.close_all_datasets()
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(None)
    assert participant_tab._sections_list.count() == 0
    assert participant_tab._participant_combo.count() == 0


# ---------------------------------------------------------------------
# NN summary line at the bottom
# ---------------------------------------------------------------------
def test_nn_summary_initial_text(participant_tab):
    assert "No artifact detection" in participant_tab._nn_summary.text()


def test_nn_summary_updates_after_preprocessing_result(main_window, participant_tab):
    """Simulate a panel result; the bottom summary line reads from it."""
    from rrational.inspector.data_loader import Dataset
    from rrational.inspector.preprocessing import PreprocessingResult

    main_window.add_dataset(Dataset(name="P1.rrational", data=_make_data()))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)

    # Inject a fake result onto the panel and refresh.
    participant_tab._preprocessing_panel._last_result = PreprocessingResult(
        indices=np.array([1, 2, 5, 7], dtype=np.int64),
        total=200,
        rate=0.02,
        grade="good",
    )
    participant_tab._refresh_nn_summary()
    text = participant_tab._nn_summary.text()
    assert "4 corrected" in text
    assert "200 total" in text
    assert "2.00%" in text
