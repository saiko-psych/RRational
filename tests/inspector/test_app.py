"""Smoke tests for the application-wide QSS theme.

Mirrors the structure of ``test_standalone_entry.py``: the theme module
is imported at top-level, then we assert that the public
``apply_app_theme`` entry point runs without raising and leaves the
``QApplication`` in a styled state. Visual correctness is checked
separately via the ``tests/visual/snapshot_app.py`` harness — these
tests only verify the wire-up + that both palette modes parse.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")


@pytest.fixture(autouse=True)
def _force_offscreen_qpa(monkeypatch):
    """Mirror the CI environment so QApplication boots without a display.

    The theme can be applied before any widget renders, but Qt's QSS
    parser still requires a live ``QApplication`` instance — which
    needs a QPA platform.
    """
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    yield


def test_apply_dark_theme_sets_stylesheet(qtbot):
    """``apply_app_theme(app, "dark")`` runs and leaves a non-empty QSS."""
    from qtpy.QtWidgets import QApplication

    from rrational.inspector.style import apply_app_theme

    app = QApplication.instance() or QApplication([])
    apply_app_theme(app, mode="dark")
    qss = app.styleSheet()
    assert qss, "apply_app_theme should set a non-empty application stylesheet"
    # Spot-check that the palette actually made it into the QSS — the
    # dark base background colour is a unique-enough token to grep for.
    assert "#1a1d22" in qss, "dark mode QSS should reference the dark base colour"


def test_apply_light_theme_sets_stylesheet(qtbot):
    """The "light" mode is equally callable and produces its own palette."""
    from qtpy.QtWidgets import QApplication

    from rrational.inspector.style import apply_app_theme

    app = QApplication.instance() or QApplication([])
    apply_app_theme(app, mode="light")
    qss = app.styleSheet()
    assert qss
    # Light-mode warm off-white token from the brief.
    assert "#f8f6f1" in qss, "light mode QSS should reference the light base colour"


def test_apply_theme_with_unknown_mode_falls_back_to_dark(qtbot):
    """Passing an unrecognised mode silently uses the dark palette.

    Defensive: a typo in a call site shouldn't crash the app at
    startup. The implementation in ``theme.apply_app_theme`` does the
    fallback inline so we just assert the dark token is present.
    """
    from qtpy.QtWidgets import QApplication

    from rrational.inspector.style import apply_app_theme

    app = QApplication.instance() or QApplication([])
    apply_app_theme(app, mode="totally-unknown")
    qss = app.styleSheet()
    assert "#1a1d22" in qss


def test_primary_button_selector_is_present_in_qss(qtbot):
    """The QSS exposes the ``QPushButton[primary="true"]`` selector.

    A handful of call sites flip ``setProperty("primary", True)`` on
    their action button and expect the amber-accent fill. If the
    selector regresses out of the template those callers silently lose
    their styling.
    """
    from qtpy.QtWidgets import QApplication

    from rrational.inspector.style import apply_app_theme

    app = QApplication.instance() or QApplication([])
    apply_app_theme(app, mode="dark")
    qss = app.styleSheet()
    assert 'QPushButton[primary="true"]' in qss


def test_palette_tokens_exposes_named_dict():
    """``palette_tokens(mode)`` returns the same hex codes used by the QSS.

    Other modules (e.g. workflow_stepper, tests) can read the token
    dict to stay aligned with the theme without re-typing hex codes.
    """
    from rrational.inspector.style.theme import palette_tokens

    dark = palette_tokens("dark")
    light = palette_tokens("light")
    assert dark["bg_base"] == "#1a1d22"
    assert light["bg_base"] == "#f8f6f1"
    # Sanity: both palettes expose the same keys so the QSS template
    # works against either without missing-key errors.
    assert set(dark.keys()) == set(light.keys())
