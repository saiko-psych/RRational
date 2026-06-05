"""Phase 27: app icon is wired into MainWindow.

Guards against two regressions:
  1. The icon files getting deleted from src/.../assets/ (the wheel would
     ship without them and the OS taskbar would fall back to the generic
     Python icon).
  2. MainWindow.__init__ losing its ``setWindowIcon`` call (so the
     title-bar would go blank on Wayland and the alt-tab thumbnail would
     fall back to a placeholder on every platform).
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


def test_main_window_has_app_icon(qtbot, tmp_path):
    """``MainWindow().windowIcon()`` must be the populated app icon."""
    from rrational.inspector import settings
    from rrational.inspector.main_window import MainWindow

    # Mirror the standalone-entry test: redirect QSettings so we don't
    # pollute the developer's registry / plist.
    settings.enable_test_mode(tmp_path)

    win = MainWindow()
    qtbot.addWidget(win)

    icon = win.windowIcon()
    assert icon.isNull() is False, (
        "MainWindow should set a non-null window icon in __init__ — the OS "
        "taskbar / title-bar falls back to a generic Python logo otherwise."
    )
