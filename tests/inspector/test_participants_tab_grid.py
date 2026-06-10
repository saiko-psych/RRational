"""Tests for the ParticipantGridWidget embedded in ParticipantsTab (Sprint 4).

Verifies that the per-subject mini-tachogram grid above the editor
table populates from the workspace, refreshes on workspace changes,
and routes click callbacks to ``MainWindow.set_active_dataset``.
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


def _make_data(n_beats: int = 300):
    from rrational.inspector.data_loader import InspectorData

    base = 1_700_000_000
    t = base + np.arange(n_beats, dtype=np.float64)
    v = 800 + 10 * np.sin(np.linspace(0, 2 * np.pi, n_beats))
    return InspectorData(t=t, v=v)


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


def test_grid_widget_is_embedded_in_participants_tab(main_window):
    """ParticipantsTab must expose ``_grid`` as a ParticipantGridWidget."""
    from rrational.inspector.plots.participant_grid import ParticipantGridWidget

    pane = main_window._participants_tab
    assert hasattr(pane, "_grid")
    assert isinstance(pane._grid, ParticipantGridWidget)
    # Empty workspace → no cells.
    assert pane._grid._cells == []


def test_grid_refreshes_when_datasets_load(main_window):
    """``on_workspace_changed`` must repopulate the grid with one cell per dataset."""
    from rrational.inspector.data_loader import Dataset

    for n in ("0012MEBE.rrational", "0105LYMA.rrational", "0299WXYZ.rrational"):
        main_window.add_dataset(Dataset(name=n, data=_make_data()))
    main_window.set_active_dataset(0)

    pane = main_window._participants_tab
    assert len(pane._grid._cells) == 3


def test_grid_click_activates_matching_dataset(main_window):
    """Clicking a grid cell must call ``set_active_dataset`` on the host."""
    from rrational.inspector.data_loader import Dataset

    for n in ("alpha.rrational", "bravo.rrational"):
        main_window.add_dataset(Dataset(name=n, data=_make_data()))
    main_window.set_active_dataset(0)

    pane = main_window._participants_tab
    pane._on_grid_subject_click("bravo")
    assert main_window._active_idx == 1


def test_grid_click_unknown_subject_is_noop(main_window):
    """An unknown subject_id must not raise + must not change active_idx."""
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="alpha.rrational", data=_make_data()))
    main_window.set_active_dataset(0)
    pane = main_window._participants_tab
    # No raise + active stays at 0.
    pane._on_grid_subject_click("does-not-exist")
    assert main_window._active_idx == 0


def test_grid_hidden_when_workspace_has_fewer_than_two_datasets(main_window):
    """Round 16 — grid stays hidden at n<=1 (nothing to compare).

    Uses ``isVisibleTo(parent)`` so the assertion holds regardless of
    whether the Participants tab is currently the foreground tab —
    only the widget's own visibility flag is under test here.
    """
    from rrational.inspector.data_loader import Dataset

    pane = main_window._participants_tab
    # Empty workspace -> grid hidden.
    assert pane._grid.isVisibleTo(pane) is False

    # n=1 -> still hidden; single thumbnail isn't a comparison view.
    main_window.add_dataset(Dataset(name="alpha.rrational", data=_make_data()))
    main_window.set_active_dataset(0)
    assert pane._grid.isVisibleTo(pane) is False


def test_grid_visible_once_workspace_has_two_or_more_datasets(main_window):
    """n>=2 -> grid widget is marked visible (independent of tab focus)."""
    from rrational.inspector.data_loader import Dataset

    pane = main_window._participants_tab
    for n in ("alpha.rrational", "bravo.rrational"):
        main_window.add_dataset(Dataset(name=n, data=_make_data()))
    main_window.set_active_dataset(0)
    assert pane._grid.isVisibleTo(pane) is True
