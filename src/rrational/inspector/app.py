"""Application entry — wires up QApplication and MainWindow.

This module is the canonical entry point for both the source-tree launcher
(``python -m rrational.inspector``) and the PyInstaller-built standalone
executable. Keep the ``main()`` function callable with no arguments so
PyInstaller's ``console_scripts``-style hook can find it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pyqtgraph as pg
from qtpy.QtCore import QSettings
from qtpy.QtWidgets import QApplication

from rrational.inspector.assets import app_icon
from rrational.inspector.main_window import MainWindow

# Cluster A1 — Render-Quality-Quartett.
#
# Background tuned to the dark-theme surface so the plot sits flush with
# the surrounding QSS panel (was white-on-graphite — looked like a print
# preview floating in the app). Light-theme callers override at runtime
# via ``set_plot_theme()`` below.
#
# antialias=True on by default: at the typical Inspector data scale
# (1k-50k beats) the frame-rate cost is invisible to the human eye, and
# the visual upgrade for 1px tachogram lines is substantial. The original
# 10k+ caveat held for full EEG streams (mne-qt-browser territory) — for
# RR we trade negligible perf for sharper rendering.
#
# Round 22 — useOpenGL was True since R11/A1 but produced an entirely
# black plot pane for real user recordings on Windows + PySide6. The
# hardware-accelerated path interacted badly with the nested QMainWindow
# hosting the BrowseTab plot, so curves rendered to the GL context but
# the surrounding QWidget paint cycle never composited the GL pixels
# into the visible widget. Antialias stays on (no measurable cost at
# RR-scale, ~10k points typical) but GL goes back off so the standard
# QPainter pipeline draws everything in the same paint pass.
pg.setConfigOptions(
    background="#1a1d22",
    foreground="#eaecef",
    antialias=True,
    useOpenGL=False,
)


def set_plot_theme(mode: str) -> None:
    """Re-skin PyQtGraph's global bg/fg to match the active app theme.

    Called from ``apply_app_theme`` so swapping QSS modes at runtime
    keeps the plot panel from suddenly looking out of place. Falls back
    silently for unknown ``mode`` strings — the QSettings reader already
    clamps to dark/light, but defensive matching keeps this safe to call
    from migration code with stale values.
    """
    if mode == "light":
        pg.setConfigOption("background", "#f8f6f1")
        pg.setConfigOption("foreground", "#1f2228")
    else:
        pg.setConfigOption("background", "#1a1d22")
        pg.setConfigOption("foreground", "#eaecef")


# QSettings key for the app-wide QSS theme mode ("dark" or "light"). Lives
# outside ``settings._DEFAULTS`` because it must be read BEFORE MainWindow
# instantiates anything that touches that module.
_THEME_MODE_KEY = "inspector/theme_mode"


def _resolve_theme_mode() -> str:
    """Return "dark" or "light" — defaults to "dark" on first launch.

    Reads directly from ``QSettings`` so the value is available before
    the inspector's settings module is imported. Unknown values fall
    back to "dark" rather than raising — a corrupted QSettings entry
    shouldn't stop the app from starting.
    """
    raw = QSettings().value(_THEME_MODE_KEY, "dark")
    mode = str(raw).strip().lower() if raw is not None else "dark"
    return mode if mode in ("dark", "light") else "dark"


def _build_parser() -> argparse.ArgumentParser:
    """argparse setup, factored out so tests can introspect it."""
    parser = argparse.ArgumentParser(
        prog="rrational-inspect",
        description="Smooth signal inspector for RRational HRV data.",
    )
    # Backwards-compat positional: ``rrational-inspect path/to/file.rrational``
    # was supported in Phases 1-8 before we standardised on ``--file``.
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help=(
            "Optional .rrational file or project folder to open at startup. "
            "If omitted, the inspector opens to an empty workspace. "
            "Prefer --file for new scripts."
        ),
    )
    parser.add_argument(
        "--file",
        dest="file_path",
        type=Path,
        default=None,
        help=(
            "Open a .rrational file at startup. Equivalent to the positional "
            "argument but explicit — useful for OS file-association launches "
            "where the OS passes ``--file C:\\path\\foo.rrational``."
        ),
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    """Boot the inspector and run the Qt event loop until close.

    Returns the Qt exit code (0 on clean shutdown). Pulled out from ``main``
    so the smoke test can call it with a mocked ``sys.exit`` and verify the
    parser accepts ``--help`` without leaving a QApplication leaked.
    """
    argv = argv if argv is not None else sys.argv[1:]

    parser = _build_parser()
    args = parser.parse_args(argv)

    # --file takes precedence over the positional fallback when both are given.
    initial_path: Path | None = args.file_path or args.path

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("RRational")
    app.setOrganizationName("RRational")
    # App-wide icon: shows in the OS taskbar / dock / alt-tab switcher
    # even before any window opens. MainWindow re-sets the same icon
    # so the per-window title-bar gets it too (Wayland honours the
    # per-window one, not the app-level one).
    app.setWindowIcon(app_icon())

    # Apply the Refined Laboratory QSS theme BEFORE constructing
    # MainWindow so the user never sees a flash of unstyled default Qt.
    # Mode is read from QSettings; defaults to dark on first launch.
    from rrational.inspector.style import apply_app_theme

    theme_mode = _resolve_theme_mode()
    apply_app_theme(app, mode=theme_mode)
    # Match the global plot bg/fg to the same theme so the central plot
    # panel reads as part of the QSS surface stack, not a print preview.
    set_plot_theme(theme_mode)

    window = MainWindow(initial_path=initial_path)
    window.show()

    # Qt event loop. Call the INSTANCE method — ``QApplication.exec_(app)`` is
    # wrong because ``exec_`` is a static/no-arg method, so passing ``app``
    # raised "exec_(): too many arguments" and the app never launched. Both
    # PySide6 and PyQt6 expose ``app.exec()``; PyQt5 also accepts ``app.exec()``.
    return app.exec() if hasattr(app, "exec") else app.exec_()


def main() -> int:
    """Standalone entry point used by PyInstaller and ``python -m``.

    Kept as a thin wrapper around ``run()`` so PyInstaller's entry-script
    can be ``from rrational.inspector.app import main; main()`` without
    pulling in argparse-handling logic.
    """
    return run()


if __name__ == "__main__":
    sys.exit(main())
