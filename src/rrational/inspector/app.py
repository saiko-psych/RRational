"""Application entry — wires up QApplication and MainWindow."""

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


def run(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="rrational-inspect",
        description="Smooth signal inspector for RRational HRV data.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help=(
            "Optional .rrational file or project folder to open at startup. "
            "If omitted, the inspector opens to an empty workspace."
        ),
    )
    args = parser.parse_args(argv)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("RRational Inspector")
    app.setOrganizationName("RRational")

    window = MainWindow(initial_path=args.path)
    window.show()

    # Qt event loop (NOT Python exec — Qt uses .exec() as standard method name).
    return QApplication.exec_(app) if hasattr(QApplication, "exec_") else app.exec()
