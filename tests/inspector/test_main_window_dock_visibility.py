"""Round 16 — welcome-state dock visibility.

The Preprocessing + Info docks have nothing to act on when no datasets
are loaded, so they hide at the welcome state. They reappear (honouring
the persisted QSettings show_*_dock preferences) once a recording lands
in the workspace and re-hide when the user closes everything.
"""

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


def _make_dataset(name: str = "alpha.csv"):
    from rrational.inspector.data_loader import Dataset, InspectorData

    base = 1_700_000_000
    t = base + np.arange(120, dtype=np.float64)
    v = 800 + 25 * np.sin(np.linspace(0, np.pi, 120))
    return Dataset(name=name, data=InspectorData(t=t, v=v))


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    # Preprocessing dock lives inside BrowseTab; force MNE-LAB layout so
    # it is the visible tab — matches the production welcome path.
    win.set_ui_layout("mnelab")
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


def test_welcome_state_hides_preprocessing_and_info_docks(main_window):
    """Empty workspace -> both side docks invisible."""
    assert main_window._datasets == []
    prep_dock = main_window._browse_tab._preprocessing_dock
    info_dock = main_window._info_dock
    assert prep_dock.isVisible() is False
    assert info_dock.isVisible() is False


def test_loading_dataset_shows_both_docks(main_window):
    """add_dataset -> Preprocessing + Info docks become visible."""
    main_window.add_dataset(_make_dataset())
    main_window.set_active_dataset(0)
    prep_dock = main_window._browse_tab._preprocessing_dock
    info_dock = main_window._info_dock
    assert prep_dock.isVisible() is True
    assert info_dock.isVisible() is True


def test_close_all_returns_to_welcome_state(main_window):
    """close_all_datasets -> docks hide again."""
    main_window.add_dataset(_make_dataset())
    main_window.set_active_dataset(0)
    assert main_window._browse_tab._preprocessing_dock.isVisible() is True

    main_window.close_all_datasets()
    assert main_window._browse_tab._preprocessing_dock.isVisible() is False
    assert main_window._info_dock.isVisible() is False
