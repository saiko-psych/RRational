"""Tests for View-menu HUD + Zen toggles + InfoDock minimum width (Sprint 5).

These actions belong to Cluster A2/A7 and complement the plot widget's
existing H/Z QShortcut bindings — the View-menu entries make the
feature discoverable for users who do not know the shortcuts.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path):
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    yield


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
# HUD toggle
# ---------------------------------------------------------------------
def test_hud_action_exists_and_is_checkable(main_window):
    """View menu must expose a checkable 'Show HUD readout' action."""
    act = main_window._toggle_hud_act
    assert act is not None
    assert act.isCheckable() is True
    # Default ON so first-launch users see the readout.
    assert act.isChecked() is True


def test_hud_action_toggles_plot_hud_state(main_window):
    """Flipping the action must propagate to ``PlotWidget.set_hud_visible``."""
    act = main_window._toggle_hud_act
    plot = main_window._plot
    # Start enabled.
    assert plot._hud_enabled is True
    act.setChecked(False)
    assert plot._hud_enabled is False
    act.setChecked(True)
    assert plot._hud_enabled is True


# ---------------------------------------------------------------------
# Zen toggle
# ---------------------------------------------------------------------
def test_zen_action_exists_and_is_checkable(main_window):
    """View menu must expose a checkable 'Zen mode' action (default off)."""
    act = main_window._toggle_zen_act
    assert act is not None
    assert act.isCheckable() is True
    assert act.isChecked() is False


def test_zen_action_triggers_zen_toggle_on_plot(main_window):
    """Triggering the action must flip both HUD + crosshair via _toggle_zen_mode."""
    act = main_window._toggle_zen_act
    plot = main_window._plot
    # Start with HUD + crosshair on (matching plot defaults).
    plot.set_hud_visible(True)
    plot.set_crosshair_visible(True)
    assert plot._hud_enabled is True
    assert plot._crosshair_enabled is True

    act.trigger()  # both flip off
    assert plot._hud_enabled is False
    assert plot._crosshair_enabled is False

    act.trigger()  # both flip back on
    assert plot._hud_enabled is True
    assert plot._crosshair_enabled is True


# ---------------------------------------------------------------------
# InfoDock visibility fix
# ---------------------------------------------------------------------
def test_info_dock_has_usable_minimum_width(main_window):
    """The right-side InfoDock must not collapse to a 1-px slit.

    Round 29 deliberately reduced the container floor from 280 to 220 so
    medium-length filenames elide reasonably without dropping every
    information-bearing character. The original 280 threshold became
    stale at that point — the dock-level guard remains, just at the
    smaller value.
    """
    dock = main_window._info_dock
    assert dock.minimumWidth() >= 220
