"""Tests for the PreferencesDialog + MainWindow color-scheme wiring.

Covers:
- MainWindow loads + exposes ``self._color_scheme`` on init
- Preferences action is suppressed in test_mode
- Dialog OK persists + applies; Cancel discards
- Picking a preset re-syncs scheme; picking a swatch flips to Custom
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_color_dir(qapp, tmp_path):
    from rrational.inspector import color_scheme_persistence as csp
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    csp.set_color_scheme_config_dir(tmp_path)
    yield
    csp.set_color_scheme_config_dir(None)


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
# MainWindow integration
# ---------------------------------------------------------------------
def test_main_window_loads_default_scheme_on_init(main_window):
    from rrational.gui.color_scheme import ColorScheme
    from rrational.inspector.color_scheme_persistence import DEFAULT_PRESET_NAME

    assert main_window._color_preset == DEFAULT_PRESET_NAME
    assert isinstance(main_window._color_scheme, ColorScheme)


def test_main_window_loads_persisted_scheme_on_init(qtbot, tmp_path):
    from rrational.gui.color_scheme import PRESET_THEMES
    from rrational.inspector.color_scheme_persistence import save_color_scheme
    from rrational.inspector.main_window import MainWindow

    save_color_scheme("Colorful", PRESET_THEMES["Colorful"])

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    assert win._color_preset == "Colorful"
    assert win._color_scheme.rr_line == PRESET_THEMES["Colorful"].rr_line


def test_preferences_action_is_suppressed_in_test_mode(main_window):
    """Click the menu Action and verify no real dialog opens."""
    # test_mode=True path hits the status-bar message branch instead.
    main_window._on_preferences_clicked()
    assert "Preferences" in main_window.statusBar().currentMessage()


def test_apply_color_scheme_persists_and_repaints(main_window):
    from rrational.gui.color_scheme import ColorScheme
    from rrational.inspector.color_scheme_persistence import (
        CUSTOM_PRESET_NAME,
        load_color_scheme,
    )

    new_scheme = ColorScheme(rr_line="#abc123")
    # _apply_color_scheme does NOT persist by itself — that's the dialog's
    # job — but it should update the in-memory state + plot pen.
    main_window._apply_color_scheme(CUSTOM_PRESET_NAME, new_scheme)
    assert main_window._color_preset == CUSTOM_PRESET_NAME
    assert main_window._color_scheme.rr_line == "#abc123"
    assert main_window._plot._curve.opts["pen"].color().name().lower() == "#abc123"
    # Disk untouched by apply alone:
    preset, _ = load_color_scheme()
    # The autouse fixture redirected the global dir, and we haven't called
    # save_color_scheme — so on-disk state is the default.
    from rrational.inspector.color_scheme_persistence import DEFAULT_PRESET_NAME

    assert preset == DEFAULT_PRESET_NAME


# ---------------------------------------------------------------------
# Dialog behaviour
# ---------------------------------------------------------------------
@pytest.fixture
def dialog(qtbot):
    from rrational.gui.color_scheme import PRESET_THEMES
    from rrational.inspector.color_scheme_persistence import DEFAULT_PRESET_NAME
    from rrational.inspector.preferences_dialog import PreferencesDialog

    captured: dict = {}

    def _apply(name, scheme):
        captured["name"] = name
        captured["scheme"] = scheme

    dlg = PreferencesDialog(
        None,
        current_preset=DEFAULT_PRESET_NAME,
        current_scheme=PRESET_THEMES[DEFAULT_PRESET_NAME],
        apply_callback=_apply,
    )
    qtbot.addWidget(dlg)
    return dlg, captured


def test_dialog_ok_persists_and_invokes_callback(dialog, tmp_path):
    from rrational.inspector.color_scheme_persistence import (
        COLOR_SCHEME_FILENAME,
        load_color_scheme,
    )

    dlg, captured = dialog
    # Switch the preset programmatically (simulates dropdown change).
    dlg._on_preset_changed("Colorful")
    dlg._on_ok()  # equivalent of clicking OK

    # apply_callback was invoked
    assert captured["name"] == "Colorful"
    assert captured["scheme"].rr_line == "#6366F1"  # Colorful preset rr_line
    # And persistence wrote the file
    assert (tmp_path / COLOR_SCHEME_FILENAME).exists()
    preset, _ = load_color_scheme()
    assert preset == "Colorful"


def test_dialog_cancel_does_not_persist(qtbot, tmp_path):
    from rrational.gui.color_scheme import PRESET_THEMES
    from rrational.inspector.color_scheme_persistence import (
        COLOR_SCHEME_FILENAME,
        DEFAULT_PRESET_NAME,
    )
    from rrational.inspector.preferences_dialog import PreferencesDialog

    captured: dict = {}

    def _apply(name, scheme):
        captured["called"] = True

    dlg = PreferencesDialog(
        None,
        current_preset=DEFAULT_PRESET_NAME,
        current_scheme=PRESET_THEMES[DEFAULT_PRESET_NAME],
        apply_callback=_apply,
    )
    qtbot.addWidget(dlg)
    # Change something in the working copy
    dlg._on_preset_changed("Pastel")
    # Cancel — emulate clicking Cancel
    dlg.reject()
    # Callback never fired, file never written
    assert "called" not in captured
    assert not (tmp_path / COLOR_SCHEME_FILENAME).exists()


def test_picking_swatch_flips_preset_to_custom(dialog):
    from qtpy.QtGui import QColor

    from rrational.inspector.color_scheme_persistence import (
        CUSTOM_PRESET_NAME,
        DEFAULT_PRESET_NAME,
    )

    dlg, _captured = dialog
    assert dlg._preset_name == DEFAULT_PRESET_NAME
    # Trigger the rr_line swatch handler directly with a colour.
    cb = dlg._on_scalar_swatch_picked("rr_line")
    cb(QColor("#aa11bb"))
    assert dlg._preset_name == CUSTOM_PRESET_NAME
    assert dlg._scheme.rr_line.lower() == "#aa11bb"


def test_picking_preset_resets_swatches(dialog):
    from rrational.gui.color_scheme import PRESET_THEMES

    dlg, _ = dialog
    # Pick a preset
    dlg._on_preset_changed("High Contrast")
    assert dlg._scheme.rr_line == PRESET_THEMES["High Contrast"].rr_line
    # Swatch reflects new colour
    assert (
        dlg._scalar_swatches["rr_line"].color().name().lower()
        == PRESET_THEMES["High Contrast"].rr_line.lower()
    )


def test_picking_palette_swatch_flips_to_custom(dialog):
    from qtpy.QtGui import QColor

    from rrational.inspector.color_scheme_persistence import (
        CUSTOM_PRESET_NAME,
        DEFAULT_PRESET_NAME,
    )

    dlg, _ = dialog
    assert dlg._preset_name == DEFAULT_PRESET_NAME
    cb = dlg._on_palette_swatch_picked(0)
    cb(QColor("#112233"))
    assert dlg._preset_name == CUSTOM_PRESET_NAME
    assert dlg._scheme.group_palette[0].lower() == "#112233"


def test_dialog_apply_does_not_close(qtbot, tmp_path):
    from rrational.gui.color_scheme import PRESET_THEMES
    from rrational.inspector.color_scheme_persistence import (
        COLOR_SCHEME_FILENAME,
        DEFAULT_PRESET_NAME,
    )
    from rrational.inspector.preferences_dialog import PreferencesDialog

    captured: dict = {}

    def _apply(name, scheme):
        captured["name"] = name

    dlg = PreferencesDialog(
        None,
        current_preset=DEFAULT_PRESET_NAME,
        current_scheme=PRESET_THEMES[DEFAULT_PRESET_NAME],
        apply_callback=_apply,
    )
    qtbot.addWidget(dlg)
    dlg._on_preset_changed("Pastel")
    dlg._on_apply()
    # Apply persisted + invoked callback
    assert captured["name"] == "Pastel"
    assert (tmp_path / COLOR_SCHEME_FILENAME).exists()
    # ...but the dialog is still alive (no accept/reject called)
    assert dlg.result() == 0
