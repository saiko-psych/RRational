"""Round 17 — Tooltip coverage on View + Tools menu actions.

The Audit revealed that several discoverability-critical menu items
lacked explicit ``setToolTip`` calls. This module asserts that the
following QActions expose non-empty tooltips so hover-help works in
every layout mode.
"""

from __future__ import annotations

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
# View menu — display toggles
# ---------------------------------------------------------------------
def test_toggle_hud_action_has_tooltip(main_window):
    tip = main_window._toggle_hud_act.toolTip()
    assert tip
    assert "Shortcut: H" in tip


def test_toggle_crosshair_action_has_tooltip(main_window):
    tip = main_window._toggle_crosshair_act.toolTip()
    assert tip
    assert "Shortcut: C" in tip


def test_toggle_info_dock_action_has_tooltip(main_window):
    tip = main_window._toggle_info_dock_act.toolTip()
    assert tip
    assert "metadata panel" in tip


def test_toggle_zen_action_has_tooltip(main_window):
    tip = main_window._toggle_zen_act.toolTip()
    assert tip
    assert "Shortcut: Z" in tip


# ---------------------------------------------------------------------
# Tools menu — Compare + exports
# ---------------------------------------------------------------------
def test_compare_curves_action_has_tooltip(main_window):
    tip = main_window._compare_curves_act.toolTip()
    assert tip
    assert "bootstrap" in tip.lower()


def test_bids_export_action_has_tooltip(main_window):
    tip = main_window._bids_export_act.toolTip()
    assert tip
    assert "BIDS" in tip
    # Round 21 — anonymize affordance must be surfaced in the tooltip.
    assert "anonymiz" in tip.lower()


def test_prism_export_action_has_tooltip(main_window):
    tip = main_window._prism_export_act.toolTip()
    assert tip
    assert "PRISM" in tip
    # Round 21 — "multi-modal research framework" framing.
    assert "multi-modal" in tip.lower()


# ---------------------------------------------------------------------
# File menu — recipe export (Round 21)
# ---------------------------------------------------------------------
def test_save_recipe_action_has_tooltip(main_window):
    tip = main_window._save_recipe_act.toolTip()
    assert tip
    assert "Python" in tip
    assert "walkthrough" in tip.lower()
