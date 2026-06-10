"""Phase 20 — BrowseTab QDockWidget layout tests."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def _isolate_settings(qapp, tmp_path):
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    yield


def _make_synthetic(name: str = "A"):
    from rrational.inspector.data_loader import (
        Dataset,
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    base = 1_700_000_000
    t = base + np.arange(100, dtype=np.float64)
    v = 800 + 50 * np.sin(np.linspace(0, np.pi, 100))
    data = InspectorData(
        t=t,
        v=v,
        sections=[
            SectionMeta(
                name="rec", t_start=float(t[0]), t_end=float(t[-1]), beat_count=100
            )
        ],
        events=[EventMeta(label="s", t=float(t[0]))],
    )
    return Dataset(name=f"{name}.csv", data=data)


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    # Phase 22.3: BrowseTab + its docks are only visible in MNE-LAB
    # mode; this whole test module is about dock behaviour, so opt in.
    win.set_ui_layout("mnelab")
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


# ---------------------------------------------------------------------
# Dock existence
# ---------------------------------------------------------------------
def test_browse_tab_has_dock_widgets(main_window):
    from qtpy.QtWidgets import QDockWidget

    bt = main_window._browse_tab
    assert isinstance(bt._datasets_dock, QDockWidget)
    assert isinstance(bt._preprocessing_dock, QDockWidget)


def test_datasets_dock_hosts_the_sidebar_tree(main_window):
    bt = main_window._browse_tab
    assert bt._datasets_dock.widget() is bt._dataset_tree


def test_preprocessing_dock_hosts_the_panel(main_window):
    bt = main_window._browse_tab
    assert bt._preprocessing_dock.widget() is bt._preprocessing_panel


def test_docks_are_visible_by_default(main_window):
    """Round 16 — Datasets dock is always on; Preprocessing dock is on
    once a recording is loaded (hidden at the welcome state so the
    empty-state landing screen isn't surrounded by disabled controls).
    """
    bt = main_window._browse_tab
    assert bt._datasets_dock.isVisible()
    main_window.add_dataset(_make_synthetic())
    main_window.set_active_dataset(0)
    assert bt._preprocessing_dock.isVisible()


# ---------------------------------------------------------------------
# View-menu toggles
# ---------------------------------------------------------------------
def test_view_menu_toggle_hides_datasets_dock(main_window):
    main_window._toggle_datasets_dock_act.setChecked(False)
    assert main_window._browse_tab._datasets_dock.isVisible() is False

    main_window._toggle_datasets_dock_act.setChecked(True)
    assert main_window._browse_tab._datasets_dock.isVisible() is True


def test_view_menu_toggle_hides_preprocessing_dock(main_window):
    main_window._toggle_preprocessing_dock_act.setChecked(False)
    assert main_window._browse_tab._preprocessing_dock.isVisible() is False

    main_window._toggle_preprocessing_dock_act.setChecked(True)
    assert main_window._browse_tab._preprocessing_dock.isVisible() is True


# ---------------------------------------------------------------------
# saveState / restoreState round-trip
# ---------------------------------------------------------------------
def test_save_dock_state_returns_non_empty_bytes(main_window):
    state = main_window._browse_tab.save_dock_state()
    # QByteArray supports len() and bool conversion.
    assert state is not None
    assert len(bytes(state)) > 0


def test_restore_dock_state_round_trips(main_window):
    bt = main_window._browse_tab
    state_before = bt.save_dock_state()
    # Mutate: hide a dock.
    bt.set_datasets_dock_visible(False)
    assert bt._datasets_dock.isVisible() is False
    # Restore the original layout.
    restored = bt.restore_dock_state(state_before)
    assert restored is True
    assert bt._datasets_dock.isVisible() is True


# ---------------------------------------------------------------------
# closeEvent → settings.save_window_state path
# ---------------------------------------------------------------------
def test_save_window_state_persists_to_qsettings(main_window):
    """Force a save by calling the helper directly (closeEvent is gated
    on ``not test_mode``). After the call, QSettings carries non-None
    geometry + window_state + browse_dock_state."""
    from rrational.inspector import settings

    # Load a dataset so the dock actually has interesting state.
    main_window.add_dataset(_make_synthetic("A"))
    main_window.set_active_dataset(0)

    main_window._save_window_state()
    assert settings.read_setting("geometry") is not None
    assert settings.read_setting("window_state") is not None
    assert settings.read_setting("browse_dock_state") is not None
