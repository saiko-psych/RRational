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
from qtpy.QtWidgets import QApplication

from rrational.inspector.main_window import MainWindow

# White background matches Streamlit-side theme + scientific-plotting convention.
# antialias=False is intentional: on long signals (10k+ points) antialiasing
# halves the frame rate. Turn it on for screenshot exports only.
pg.setConfigOptions(background="w", foreground="k", antialias=False)


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
    app.setApplicationName("RRational Inspector")
    app.setOrganizationName("RRational")

    window = MainWindow(initial_path=initial_path)
    window.show()

    # Qt event loop (NOT Python exec — Qt uses .exec() as standard method name).
    return QApplication.exec_(app) if hasattr(QApplication, "exec_") else app.exec()


def main() -> int:
    """Standalone entry point used by PyInstaller and ``python -m``.

    Kept as a thin wrapper around ``run()`` so PyInstaller's entry-script
    can be ``from rrational.inspector.app import main; main()`` without
    pulling in argparse-handling logic.
    """
    return run()


if __name__ == "__main__":
    sys.exit(main())
