"""Tests for Phase 14 — Manual artifact marking (MNE-LAB-style).

Covers:
- Click adds a manual artifact at the nearest beat
- Click on an algorithm-detected artifact moves it to the excluded set
- Click on a manual mark removes it (toggle)
- Click outside tolerance is a no-op
- Manual-mark mode toggle gates interaction
- Persistence: manual + excluded indices land in {pid}_artifacts.yml
- Restore: reopening the dataset re-populates the manual + excluded sets
- Undo reverses the last mark; redo replays it
- Undo / redo menu actions enable / disable based on stack contents
"""

from __future__ import annotations


import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path, monkeypatch):
    """Redirect every persistence store at the inspector + gui layers.

    Same isolation pattern as ``tests/inspector/test_artifact_persistence.py``
    so tests can't pollute the developer's real ~/.rrational/.
    """
    from rrational.gui import persistence as gui_persistence
    from rrational.inspector import persistence as inspector_persistence
    from rrational.inspector import results_persistence as rp
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    inspector_persistence.set_inspector_config_dir(tmp_path)
    monkeypatch.setattr(gui_persistence, "CONFIG_DIR", tmp_path / "gui_config")
    monkeypatch.setattr(
        gui_persistence, "SETTINGS_FILE", tmp_path / "gui_config" / "settings.yml"
    )
    monkeypatch.setattr(rp, "_DEFAULT_DIR", tmp_path / "inspector_global")
    yield
    inspector_persistence.set_inspector_config_dir(None)


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    # Phase 22.3: manual-artifact panel lives inside BrowseTab (MNE-LAB).
    win.set_ui_layout("mnelab")
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


def _synthetic_dataset(main_window, n: int = 200, name: str = "synthetic.csv"):
    """Inject a clean synthetic dataset so click-coordinate math is reliable."""
    from rrational.inspector.data_loader import (
        Dataset,
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    rng = np.random.default_rng(0)
    rr_ms = 800 + 30 * rng.standard_normal(n)
    t = 1_700_000_000.0 + np.cumsum(rr_ms) / 1000.0
    data = InspectorData(
        t=t,
        v=rr_ms,
        sections=[
            SectionMeta(name="s", t_start=float(t[0]), t_end=float(t[-1]), beat_count=n)
        ],
        events=[EventMeta(label="ev", t=float(t[0]))],
    )
    main_window.add_dataset(Dataset(name=name, data=data))
    main_window.set_active_dataset(len(main_window._datasets) - 1)
    return data


def _click_at_beat(plot, idx: int) -> None:
    """Drive the plot's toggle handler at the exact time of beat ``idx``.

    The scene-level click signal needs a real QGraphicsSceneMouseEvent
    which is awkward to synthesise; the panel's auto-save / undo logic
    only cares that ``_toggle_manual_at`` runs, so we exercise that
    directly and emit the same signal the scene handler would.
    """
    action = plot._toggle_manual_at(idx)
    if action is not None:
        plot.manual_artifact_changed.emit(int(idx), action)


# ---------------------------------------------------------------------
# Plot-widget behaviour
# ---------------------------------------------------------------------
def test_click_adds_manual_artifact(main_window):
    """Clicking a free beat adds it to the manual set."""
    _synthetic_dataset(main_window)
    plot = main_window._browse_tab._plot

    _click_at_beat(plot, 50)
    assert 50 in plot.manual_added_indices()
    assert 50 not in plot.manual_removed_indices()


def test_click_on_algorithm_artifact_excludes_it(main_window):
    """Clicking on an algorithm-detected dot moves it to excluded."""
    _synthetic_dataset(main_window)
    plot = main_window._browse_tab._plot

    # Seed an algorithm artifact at idx=80
    plot.set_artifacts(np.array([80], dtype=np.int64))

    _click_at_beat(plot, 80)
    assert 80 in plot.manual_removed_indices()
    # Not added to manual_added — it's an algo artifact being EXCLUDED
    assert 80 not in plot.manual_added_indices()


def test_click_on_manual_artifact_removes_it(main_window):
    """A second click on a manual mark toggles it off."""
    _synthetic_dataset(main_window)
    plot = main_window._browse_tab._plot

    _click_at_beat(plot, 50)
    assert 50 in plot.manual_added_indices()
    _click_at_beat(plot, 50)
    assert 50 not in plot.manual_added_indices()


def test_click_on_excluded_artifact_reinstates_it(main_window):
    """Re-clicking an excluded algo artifact takes it back out of excluded."""
    _synthetic_dataset(main_window)
    plot = main_window._browse_tab._plot
    plot.set_artifacts(np.array([80], dtype=np.int64))

    _click_at_beat(plot, 80)
    assert 80 in plot.manual_removed_indices()
    _click_at_beat(plot, 80)
    assert 80 not in plot.manual_removed_indices()


def test_nearest_finite_beat_within_tolerance(main_window):
    """``_nearest_finite_beat`` snaps to closest beat within 2 s."""
    _synthetic_dataset(main_window)
    plot = main_window._browse_tab._plot

    target_idx = 75
    t_click = float(plot._times[target_idx]) + 0.1  # 100ms off
    found = plot._nearest_finite_beat(t_click)
    assert found == target_idx


def test_nearest_finite_beat_outside_tolerance_returns_none(main_window):
    """Clicks > 2 s away from any beat return None (no mark)."""
    _synthetic_dataset(main_window)
    plot = main_window._browse_tab._plot

    t_click = float(plot._times[-1]) + 1000.0  # way past the data
    assert plot._nearest_finite_beat(t_click) is None


def test_manual_mark_mode_off_blocks_click_handler(main_window):
    """When mode is OFF, the scene click signal does nothing."""
    _synthetic_dataset(main_window)
    plot = main_window._browse_tab._plot

    # _on_scene_mouse_clicked must early-return when mode is off.
    # We test the gate by calling it with a fake event that would
    # otherwise hit a beat.
    from qtpy.QtCore import QPointF, Qt

    class _FakeEvent:
        def __init__(self, scene_pos, button=Qt.LeftButton):
            self._sp = scene_pos
            self._button = button
            self.accepted = False

        def scenePos(self):
            return self._sp

        def button(self):
            return self._button

        def accept(self):
            self.accepted = True

    plot.set_manual_mark_mode(False)
    fake = _FakeEvent(QPointF(0.0, 0.0))
    plot._on_scene_mouse_clicked(fake)
    assert not plot.manual_added_indices()


def test_set_manual_mark_mode_toggles_state(main_window):
    """``set_manual_mark_mode`` flips the internal flag."""
    _synthetic_dataset(main_window)
    plot = main_window._browse_tab._plot
    plot.set_manual_mark_mode(True)
    assert plot.manual_mark_mode() is True
    plot.set_manual_mark_mode(False)
    assert plot.manual_mark_mode() is False


# ---------------------------------------------------------------------
# Panel checkbox UI
# ---------------------------------------------------------------------
def test_panel_manual_checkbox_drives_plot_mode(main_window):
    """Flipping the panel's checkbox flips the plot's mode flag."""
    _synthetic_dataset(main_window)
    panel = main_window._browse_tab._preprocessing_panel
    plot = main_window._browse_tab._plot

    assert plot.manual_mark_mode() is False
    panel._toggle_manual_mark.setChecked(True)
    assert plot.manual_mark_mode() is True
    panel._toggle_manual_mark.setChecked(False)
    assert plot.manual_mark_mode() is False


def test_panel_manual_checkbox_disabled_with_no_data(main_window):
    """Checkbox is disabled until a dataset is loaded."""
    panel = main_window._browse_tab._preprocessing_panel
    # No dataset loaded yet
    assert panel._toggle_manual_mark.isEnabled() is False


def test_panel_manual_checkbox_enabled_after_load(main_window):
    """Once a dataset is active, the checkbox can be flipped on."""
    _synthetic_dataset(main_window)
    panel = main_window._browse_tab._preprocessing_panel
    assert panel._toggle_manual_mark.isEnabled() is True


def test_panel_help_label_visible_when_mode_on(main_window):
    """The help text appears only when manual-mark mode is enabled."""
    _synthetic_dataset(main_window)
    panel = main_window._browse_tab._preprocessing_panel
    assert panel._manual_help.isVisible() is False
    panel._toggle_manual_mark.setChecked(True)
    assert panel._manual_help.isVisible() is True


# ---------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------
def test_manual_marks_persist_to_yaml(main_window):
    """A click triggers an autosave that writes manual_artifacts entries."""
    from rrational.gui.persistence import load_artifact_corrections

    _synthetic_dataset(main_window, name="persist_test.csv")
    plot = main_window._browse_tab._plot

    _click_at_beat(plot, 42)

    loaded = load_artifact_corrections("persist_test", section_key="_full")
    assert loaded is not None
    manual = loaded.get("manual_artifacts", [])
    assert any(m.get("original_idx") == 42 for m in manual)


def test_excluded_indices_persist_to_yaml(main_window):
    """Clicking an algorithm artifact writes it to excluded_artifact_indices."""
    from rrational.gui.persistence import load_artifact_corrections

    _synthetic_dataset(main_window, name="exclude_test.csv")
    plot = main_window._browse_tab._plot
    plot.set_artifacts(np.array([99], dtype=np.int64))

    _click_at_beat(plot, 99)

    loaded = load_artifact_corrections("exclude_test", section_key="_full")
    assert loaded is not None
    assert 99 in loaded.get("excluded_artifact_indices", [])


def test_persistence_roundtrip_via_load(main_window):
    """save -> load roundtrip preserves both added + removed sets."""
    from rrational.gui.persistence import load_artifact_corrections

    _synthetic_dataset(main_window, name="rt_test.csv")
    plot = main_window._browse_tab._plot
    plot.set_artifacts(np.array([10, 20], dtype=np.int64))

    _click_at_beat(plot, 50)  # add manual
    _click_at_beat(plot, 10)  # exclude algo

    loaded = load_artifact_corrections("rt_test", section_key="_full")
    manual_idxs = {m["original_idx"] for m in loaded.get("manual_artifacts", [])}
    excluded_idxs = set(loaded.get("excluded_artifact_indices", []))
    assert 50 in manual_idxs
    assert 10 in excluded_idxs


def test_reopen_restores_both_sets(main_window):
    """Closing + reopening the same pid restores added + excluded."""
    _synthetic_dataset(main_window, name="restore_test.csv")
    plot = main_window._browse_tab._plot
    plot.set_artifacts(np.array([15, 25], dtype=np.int64))

    _click_at_beat(plot, 60)  # add manual @ 60
    _click_at_beat(plot, 25)  # exclude algo @ 25

    main_window.close_all_datasets()
    # Re-create with the same name → restore should fire
    _synthetic_dataset(main_window, name="restore_test.csv")

    plot = main_window._browse_tab._plot
    assert 60 in plot.manual_added_indices()
    assert 25 in plot.manual_removed_indices()


# ---------------------------------------------------------------------
# Undo / Redo
# ---------------------------------------------------------------------
def test_undo_reverses_last_mark(main_window):
    """Undo pops the most recent manual click."""
    _synthetic_dataset(main_window)
    panel = main_window._browse_tab._preprocessing_panel
    plot = main_window._browse_tab._plot

    _click_at_beat(plot, 30)
    assert 30 in plot.manual_added_indices()

    assert panel.undo() is True
    assert 30 not in plot.manual_added_indices()


def test_undo_then_redo_round_trips(main_window):
    """Redo restores what undo just removed."""
    _synthetic_dataset(main_window)
    panel = main_window._browse_tab._preprocessing_panel
    plot = main_window._browse_tab._plot

    _click_at_beat(plot, 30)
    panel.undo()
    assert 30 not in plot.manual_added_indices()
    assert panel.redo() is True
    assert 30 in plot.manual_added_indices()


def test_undo_with_empty_stack_returns_false(main_window):
    """Calling undo with no prior marks must not crash and returns False."""
    _synthetic_dataset(main_window)
    panel = main_window._browse_tab._preprocessing_panel
    assert panel.undo() is False
    assert panel.redo() is False


def test_undo_redo_actions_track_stack_state(main_window):
    """The Edit-menu actions enable / disable as the stacks fill."""
    _synthetic_dataset(main_window)
    panel = main_window._browse_tab._preprocessing_panel
    plot = main_window._browse_tab._plot

    assert main_window._undo_action.isEnabled() is False
    assert main_window._redo_action.isEnabled() is False

    _click_at_beat(plot, 30)
    assert main_window._undo_action.isEnabled() is True
    assert main_window._redo_action.isEnabled() is False

    panel.undo()
    assert main_window._undo_action.isEnabled() is False
    assert main_window._redo_action.isEnabled() is True


def test_undo_stack_capped_at_50(main_window):
    """Long histories don't blow up — only the last 50 entries are kept."""
    from rrational.inspector.tabs.preprocessing_panel import _UNDO_DEPTH

    _synthetic_dataset(main_window, n=300)
    panel = main_window._browse_tab._preprocessing_panel
    plot = main_window._browse_tab._plot

    # 60 unique clicks → only the last 50 should remain on the undo stack
    for i in range(60):
        _click_at_beat(plot, i)
    assert len(panel._undo_stack) == _UNDO_DEPTH


def test_new_mark_clears_redo_stack(main_window):
    """A fresh click after undo invalidates the redo history."""
    _synthetic_dataset(main_window)
    panel = main_window._browse_tab._preprocessing_panel
    plot = main_window._browse_tab._plot

    _click_at_beat(plot, 30)
    panel.undo()
    assert panel._redo_stack  # not empty
    _click_at_beat(plot, 40)  # fresh mark
    assert not panel._redo_stack
