"""Tests for the app-wide UI font-zoom feature (View -> Text size)."""

from __future__ import annotations

import re

import pytest


def _base_font_px(qss: str) -> int:
    """Pull the ``QWidget { font-size: Npx }`` value out of the sheet."""
    block = qss[qss.index("QWidget {") :]
    m = re.search(r"font-size:\s*(\d+)px", block)
    assert m, "base QWidget font-size not found in QSS"
    return int(m.group(1))


def test_qss_font_size_scales_with_scale():
    """``_qss_for`` must scale every font-size so the UI actually zooms."""
    from rrational.inspector.style.theme import _qss_for, palette_tokens

    p = palette_tokens("dark")
    small = _base_font_px(_qss_for(p, 1.0))
    big = _base_font_px(_qss_for(p, 1.5))
    tiny = _base_font_px(_qss_for(p, 0.8))
    assert small == 13  # design baseline
    assert big > small  # zooming in enlarges text
    assert tiny < small  # zooming out shrinks text


def test_qss_scale_is_clamped_against_absurd_values():
    """A corrupt/huge scale must not blow the font-size up unbounded."""
    from rrational.inspector.style.theme import _qss_for, palette_tokens

    p = palette_tokens("dark")
    # 99x would be unreadable; the builder clamps to <= 2.0.
    assert _base_font_px(_qss_for(p, 99.0)) == _base_font_px(_qss_for(p, 2.0))
    # negative/zero clamps up to the 0.7 floor, never <= 0.
    assert _base_font_px(_qss_for(p, -5.0)) > 0


def test_resolve_font_scale_defaults_and_clamps(qtbot, tmp_path):
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    from qtpy.QtCore import QSettings

    from rrational.inspector.app import (
        FONT_SCALE_MAX,
        FONT_SCALE_MIN,
        _FONT_SCALE_KEY,
        _resolve_font_scale,
    )

    # Missing key -> baseline 1.0.
    assert _resolve_font_scale() == 1.0
    # Out-of-range persisted values clamp into the supported band.
    QSettings().setValue(_FONT_SCALE_KEY, 9.0)
    assert _resolve_font_scale() == FONT_SCALE_MAX
    QSettings().setValue(_FONT_SCALE_KEY, 0.1)
    assert _resolve_font_scale() == FONT_SCALE_MIN
    # A garbage value falls back to 1.0 rather than raising.
    QSettings().setValue(_FONT_SCALE_KEY, "not-a-number")
    assert _resolve_font_scale() == 1.0


pytest.importorskip("pytestqt")


@pytest.fixture
def mw(qtbot, tmp_path):
    from rrational.inspector import settings
    from rrational.inspector.main_window import MainWindow

    settings.enable_test_mode(tmp_path)
    w = MainWindow()
    w.test_mode = True
    qtbot.addWidget(w)
    return w


def test_default_scale_is_baseline(mw):
    assert mw._font_scale == 1.0
    # Menu actions exist and both zoom directions are available at baseline.
    assert mw._zoom_in_act.isEnabled()
    assert mw._zoom_out_act.isEnabled()


def test_adjust_font_scale_steps_and_persists(mw):
    from rrational.inspector.app import _resolve_font_scale

    mw._adjust_font_scale(+1)
    assert mw._font_scale == pytest.approx(1.1)
    # Persisted so a relaunch restores it.
    assert _resolve_font_scale() == pytest.approx(1.1)
    mw._adjust_font_scale(-1)
    assert mw._font_scale == pytest.approx(1.0)


def test_reset_returns_to_baseline(mw):
    mw._adjust_font_scale(+1)
    mw._adjust_font_scale(+1)
    assert mw._font_scale > 1.0
    mw._set_font_scale(1.0)
    assert mw._font_scale == 1.0


def test_zoom_clamps_and_toggles_action_enabled(mw):
    from rrational.inspector.app import FONT_SCALE_MAX, FONT_SCALE_MIN

    # Drive all the way up: clamps at MAX and disables further increase.
    for _ in range(20):
        mw._adjust_font_scale(+1)
    assert mw._font_scale == pytest.approx(FONT_SCALE_MAX)
    assert not mw._zoom_in_act.isEnabled()
    assert mw._zoom_out_act.isEnabled()

    # Drive all the way down: clamps at MIN and disables further decrease.
    for _ in range(20):
        mw._adjust_font_scale(-1)
    assert mw._font_scale == pytest.approx(FONT_SCALE_MIN)
    assert not mw._zoom_out_act.isEnabled()
    assert mw._zoom_in_act.isEnabled()


def test_zoom_actually_enlarges_the_applied_qss(qtbot, mw):
    """End-to-end: bumping the scale enlarges the live application QSS.

    In the real app ``app.run`` applies the theme at startup; the test
    harness constructs MainWindow directly, so establish the baseline QSS
    explicitly before measuring.
    """
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance()
    mw._set_font_scale(1.0)  # establish baseline QSS as app.run would
    before = _base_font_px(app.styleSheet())
    mw._adjust_font_scale(+1)
    after = _base_font_px(app.styleSheet())
    assert after > before
