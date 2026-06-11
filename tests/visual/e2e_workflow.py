"""End-to-end workflow simulation against the real test_project.

Boots the inspector with the user's actual ``test_project`` folder
(C:/Users/David/Nextcloud2/Documents/Uni Graz/Praxis Master/test_project),
opens the project, loads each recording, walks through every tab, and
snapshots each step so we can eyeball what the user actually sees —
NOT a headless mock with synthetic data.

Run:
    uv run python tests/visual/e2e_workflow.py

Outputs go to ``tests/visual/e2e_snapshots/<NN_step>.png``.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

from qtpy.QtCore import QEventLoop, QTimer
from qtpy.QtWidgets import QApplication

# Import early so MainWindow can find lazy-imports
from rrational.inspector.app import set_plot_theme  # noqa: E402
from rrational.inspector.main_window import MainWindow  # noqa: E402
from rrational.inspector.style import apply_app_theme  # noqa: E402

_OUT_DIR = Path(__file__).parent / "e2e_snapshots"
_OUT_DIR.mkdir(exist_ok=True)

TEST_PROJECT = Path(
    "C:/Users/David/Nextcloud2/Documents/Uni Graz/Praxis Master/test_project"
)


def _settle(app: QApplication, ms: int = 400) -> None:
    """Real event loop with a timer — single processEvents() is not enough
    for nested QMainWindows + pyqtgraph to finish their deferred layout."""
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    app.processEvents()


def _snap(widget, name: str, note: str = "") -> None:
    """Grab + save a screenshot. ``note`` is printed for the run log."""
    path = _OUT_DIR / f"{name}.png"
    pix = widget.grab()
    pix.save(str(path), "PNG")
    suffix = f" — {note}" if note else ""
    print(f"[snap] {name}.png {pix.width()}x{pix.height()}{suffix}")


def _try(label: str, fn):
    """Run ``fn`` and report any exception without aborting the workflow."""
    try:
        return fn()
    except Exception as exc:
        print(f"[FAIL] {label}: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return None


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)

    # Apply theme BEFORE first widget renders.
    apply_app_theme(app, mode="dark")
    set_plot_theme("dark")

    print(f"[boot] QApplication ready, test_project exists: {TEST_PROJECT.exists()}")
    if not TEST_PROJECT.exists():
        print(f"[boot] PATH MISSING: {TEST_PROJECT}")
        return 2

    win = MainWindow()
    # Force a generous viewport so docks + plot all have real estate.
    win.resize(1600, 1000)
    win.show()
    app.processEvents()
    win.setGeometry(20, 20, 1600, 1000)
    _settle(app, 500)
    _snap(win, "01_welcome_initial", "fresh boot, no project")

    # -------- Step 1: open the real project ---------------------------------
    print("\n[step] open_project_path(test_project)")
    ok = _try("open_project_path", lambda: win.open_project_path(TEST_PROJECT))
    _settle(app, 500)
    _snap(win, "02_project_opened", f"open_project returned {ok!r}")
    print(f"[state] active_project = {getattr(win, '_project', None)}")
    print(f"[state] dataset count = {len(getattr(win, '_datasets', []))}")

    # -------- Step 2: scan raw files (skip events companions) -------------
    raw = TEST_PROJECT / "data" / "raw"
    candidates = []
    for pattern in ("*.csv", "*.txt"):
        for p in raw.rglob(pattern):
            name = p.name.lower()
            # Round 22 — Events companion files crash silently with bogus
            # 'beats' counts, skip them in the scan so the smoke test
            # exercises the real RR loader path.
            if "_events" in name or name.endswith("events.csv"):
                continue
            candidates.append(p)
    print(f"\n[scan] data/raw -> {len(candidates)} candidate RR files")
    for c in candidates[:8]:
        print(f"       * {c.relative_to(TEST_PROJECT)}")

    # -------- Step 3: load first 3 files programmatically ------------------
    loaded = 0
    for f in candidates[:3]:
        print(f"\n[load] {f.name}")
        ok = _try(f"open_path({f.name})", lambda f=f: win.open_path(f))
        _settle(app, 400)
        if ok:
            loaded += 1
    _snap(win, "03_after_load_3_files", f"{loaded}/{min(3, len(candidates))} loaded")
    print(f"[state] dataset count after loads = {len(getattr(win, '_datasets', []))}")

    # -------- Step 4: walk every visible tab -------------------------------
    tabs = win._tabs_widget
    print(f"\n[tabs] tab count = {tabs.count()}")
    for i in range(tabs.count()):
        visible = tabs.isTabVisible(i)
        title = tabs.tabText(i)
        if not visible:
            print(f"       * tab {i} '{title}' HIDDEN, skip")
            continue
        tabs.setCurrentIndex(i)
        _settle(app, 400)
        widget_name = type(tabs.widget(i)).__name__
        clean_title = title.split("(")[0].strip().replace(" ", "_") or widget_name
        _snap(win, f"04_tab_{i:02d}_{clean_title}", f"widget={widget_name}")

    # -------- Step 5: trigger the walkthrough dialog -----------------------
    print("\n[help] open walkthrough dialog")
    walkthrough_act = None
    for menu_action in win.menuBar().actions():
        menu = menu_action.menu()
        if not menu:
            continue
        for act in menu.actions():
            text = act.text().replace("&", "").lower()
            if "walkthrough" in text:
                walkthrough_act = act
                break
        if walkthrough_act:
            break
    if walkthrough_act:
        _try("trigger walkthrough", lambda: walkthrough_act.trigger())
        _settle(app, 500)
        wt_dlg = None
        for w in app.topLevelWidgets():
            if "Walkthrough" in type(w).__name__:
                wt_dlg = w
                break
        if wt_dlg:
            _snap(wt_dlg, "05_walkthrough_page_0", "first page")
            # Walk the Next button if findable
            from qtpy.QtWidgets import QPushButton

            next_btn = None
            for b in wt_dlg.findChildren(QPushButton):
                if "next" in b.text().lower():
                    next_btn = b
                    break
            if next_btn:
                for page in range(1, 14):
                    if not next_btn.isEnabled():
                        print(f"[walk] page {page} — Next button DISABLED, stop")
                        break
                    next_btn.click()
                    _settle(app, 200)
                    _snap(wt_dlg, f"05_walkthrough_page_{page}", f"after click {page}")
            else:
                print("[walk] no Next button found in walkthrough dialog")
            wt_dlg.close()
            _settle(app, 200)
        else:
            print("[walk] WalkthroughDialog not found among top-level widgets")
    else:
        print("[walk] no walkthrough QAction found in menu bar")

    # -------- Step 6: tools menu — Compare HRV Curves dialog ---------------
    print("\n[tools] open Compare HRV curves dialog")
    compare_act = None
    for menu_action in win.menuBar().actions():
        if "tool" not in menu_action.text().lower().replace("&", ""):
            continue
        menu = menu_action.menu()
        for act in menu.actions():
            text = act.text().replace("&", "").lower()
            if "compare" in text and "hrv" in text:
                compare_act = act
                break
    if compare_act:
        _try("trigger compare-curves", lambda: compare_act.trigger())
        _settle(app, 400)
        for w in app.topLevelWidgets():
            if "Compare" in type(w).__name__:
                _snap(w, "06_compare_curves_dialog", "tools menu entry")
                w.close()
                break
    else:
        print("[tools] no compare-curves action found")

    _settle(app, 200)
    _snap(win, "07_final_state", "all interactions done")

    print(f"\n[done] {len(list(_OUT_DIR.glob('*.png')))} screenshots in {_OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
