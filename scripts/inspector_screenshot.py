"""Headless screenshot helper for the inspector.

Boots MainWindow under offscreen-Qt, loads a file or synthetic data,
optionally fires UI actions, and writes a PNG. Designed so the assistant
can call this from Bash to visually verify rendering without needing
the user to look at a real window.

Usage:
    python scripts/inspector_screenshot.py [options] OUT_PATH

Examples:
    # Single file, default initial view
    python scripts/inspector_screenshot.py \\
        --file data/kubios_comparison/0012MEBE.rrational \\
        screenshots/loaded_one.png

    # Two files (multi-dataset sidebar)
    python scripts/inspector_screenshot.py \\
        --file data/kubios_comparison/0012MEBE.rrational \\
        --file data/kubios_comparison/0105LYMA.rrational \\
        screenshots/two_datasets.png

    # Empty state (no file loaded)
    python scripts/inspector_screenshot.py screenshots/empty.png
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Force the platform BEFORE QApplication is constructed. We use the
# real "windows" platform (with the actual font stack) rather than
# "offscreen" — offscreen drops back to a stub font engine which
# renders every glyph as a tofu box, making the screenshot unreadable.
# We still never call .show() in any user-visible sense; grab() works
# on a hidden window just fine.
os.environ.setdefault(
    "QT_QPA_PLATFORM", "windows" if sys.platform == "win32" else "offscreen"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out_path", type=Path, help="PNG output path")
    parser.add_argument(
        "--file",
        type=Path,
        action="append",
        default=[],
        help="A .rrational file to open at startup (repeat for multi-dataset)",
    )
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument(
        "--show-section",
        type=str,
        default=None,
        help="After loading, simulate sidebar click on this section name "
        "(zooms + highlights it).",
    )
    parser.add_argument(
        "--hide",
        action="append",
        default=[],
        choices=["sidebar", "overview", "sections", "events", "grid", "crosshair"],
        help="Turn off a View-menu toggle before taking the screenshot",
    )
    parser.add_argument(
        "--tab",
        type=str,
        default=None,
        choices=["browse", "setup", "analysis", "results"],
        help="Switch to a specific tab before grabbing",
    )
    parser.add_argument(
        "--detect-artifacts",
        action="store_true",
        help="Click 'Detect artifacts' in the Preprocessing panel before "
        "the screenshot — useful for showing the full detected state",
    )
    args = parser.parse_args()

    import pyqtgraph as pg
    from qtpy.QtWidgets import QApplication
    from rrational.inspector.main_window import MainWindow

    # Same defaults as the production entry point in inspector/app.py —
    # white plot bg, black foreground, no antialias (speed).
    pg.setConfigOptions(background="w", foreground="k", antialias=False)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("RRational Inspector (screenshot)")
    app.setOrganizationName("RRational")

    win = MainWindow()
    win.test_mode = True
    win.resize(args.width, args.height)
    # On the real Windows platform .show() pops an actual window — we
    # use setAttribute(WA_DontShowOnScreen) so the widget gets laid out
    # (which grab() needs) without ever appearing on the desktop.
    from qtpy.QtCore import Qt as _Qt

    win.setAttribute(_Qt.WA_DontShowOnScreen, True)
    win.show()
    app.processEvents()

    for fp in args.file:
        if not fp.exists():
            print(f"ERROR: {fp} not found", file=sys.stderr)
            return 1
        win.open_path(fp)
    app.processEvents()

    toggle_map = {
        "sidebar": "_toggle_sidebar_act",
        "overview": "_toggle_overview_act",
        "sections": "_toggle_sections_act",
        "events": "_toggle_events_act",
        "grid": "_toggle_grid_act",
        "crosshair": "_toggle_crosshair_act",
    }
    for hide_key in args.hide:
        getattr(win, toggle_map[hide_key]).setChecked(False)
    app.processEvents()

    if args.tab is not None:
        tab_attr = {
            "browse": "_browse_tab",
            "setup": "_setup_tab",
            "analysis": "_analysis_tab",
            "results": "_results_tab",
        }[args.tab]
        tab = getattr(win, tab_attr)
        win._tabs_widget.setCurrentWidget(tab)
        app.processEvents()

    if args.detect_artifacts and win._data is not None:
        win._browse_tab._preprocessing_panel._on_detect_clicked()
        app.processEvents()

    if args.show_section and win._data is not None:
        # Click the matching section in the sidebar tree.
        from rrational.inspector.main_window import _ROLE_SECTION_NAME

        tree = win._dataset_tree
        for i in range(tree.topLevelItemCount()):
            top = tree.topLevelItem(i)
            for j in range(top.childCount()):
                child = top.child(j)
                if child.data(0, _ROLE_SECTION_NAME) == args.show_section:
                    win._on_tree_item_clicked(child, 0)
                    break
        app.processEvents()

    # Ensure the layout has actually settled before grabbing — one more
    # event-loop tick fixes the "partially painted" first-frame artefact
    # under offscreen QPA.
    for _ in range(3):
        app.processEvents()

    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    pixmap = win.grab()
    if not pixmap.save(str(args.out_path)):
        print(f"ERROR: failed to write {args.out_path}", file=sys.stderr)
        return 1
    print(f"wrote {args.out_path} ({pixmap.width()}x{pixmap.height()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
