"""Advanced E2E workflow simulation — edge cases + niche workflows.

Goes beyond e2e_workflow.py: stress-tests the inspector with many
datasets, long recordings, light-mode, every dialog, all analysis
plot tabs, and screen sizes ranging from compact to widescreen.

Output: tests/visual/e2e_snapshots/adv_NN_<scenario>.png
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import numpy as np
from qtpy.QtCore import QEventLoop, QTimer
from qtpy.QtWidgets import QApplication, QPushButton

from rrational.inspector.app import set_plot_theme  # noqa: E402
from rrational.inspector.data_loader import (  # noqa: E402
    Dataset,
    EventMeta,
    InspectorData,
    SectionMeta,
)
from rrational.inspector.main_window import MainWindow  # noqa: E402
from rrational.inspector.style import apply_app_theme  # noqa: E402

_OUT = Path(__file__).parent / "e2e_snapshots"
_OUT.mkdir(exist_ok=True)

TEST_PROJECT = Path(
    "C:/Users/David/Nextcloud2/Documents/Uni Graz/Praxis Master/test_project"
)


def _settle(app, ms=500):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    app.processEvents()


def _snap(widget, name, note=""):
    """Grab + scale to max 1200x900 so the resulting PNGs stay below the
    multi-image API ceiling. Originals would otherwise land at 2400x1838
    on HiDPI grabs."""
    from qtpy.QtCore import Qt

    path = _OUT / f"adv_{name}.png"
    pix = widget.grab()
    # Scale only down, never up. KeepAspectRatio so layouts stay square.
    if pix.width() > 1200 or pix.height() > 900:
        pix = pix.scaled(1200, 900, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    pix.save(str(path), "PNG")
    suffix = f" -- {note}" if note else ""
    print(f"[snap] {path.name} {pix.width()}x{pix.height()}{suffix}")


def _try(label, fn):
    try:
        return fn()
    except Exception as exc:
        print(f"[FAIL] {label}: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return None


def _synth_dataset(name, n_beats=600, n_sections=3, seed=42, mean_rr=800):
    rng = np.random.default_rng(seed=seed)
    rr = mean_rr + 30 * rng.standard_normal(n_beats)
    base = 1_700_000_000 + seed * 1000
    t = base + np.cumsum(rr) / 1000.0
    sections = []
    step = n_beats // max(1, n_sections)
    for i in range(n_sections):
        a = i * step
        b = (i + 1) * step - 1 if i < n_sections - 1 else n_beats - 1
        sections.append(
            SectionMeta(
                name=f"sec_{i:02d}",
                t_start=float(t[a]),
                t_end=float(t[b]),
                beat_count=b - a + 1,
            )
        )
    events = [
        EventMeta(label=f"evt_{i}", t=float(t[i * step])) for i in range(n_sections)
    ]
    data = InspectorData(t=t, v=rr, sections=sections, events=events)
    return Dataset(name=name, data=data)


def _find_action(win, menu_keyword, action_keyword, *, verbose=False):
    """Find a QAction in a top-level menu by keyword search.

    ``menu_keyword`` matches against the menubar entry's label (case
    insensitive, ``&`` mnemonic stripped). ``action_keyword`` matches
    against the action label inside that menu. Returns the first match
    or ``None`` if nothing fits — set ``verbose=True`` to dump every
    candidate so a missing menu wiring is obvious in the E2E log.
    """
    for menu_action in win.menuBar().actions():
        menu_label = menu_action.text().replace("&", "").lower()
        if menu_keyword.lower() not in menu_label:
            continue
        menu = menu_action.menu()
        if not menu:
            continue
        for act in menu.actions():
            text = act.text().replace("&", "").lower()
            if verbose:
                print(f"  [menu_scan] {menu_label!r} -> {text!r}")
            if action_keyword.lower() in text:
                return act
    if verbose:
        print(f"  [menu_scan] NO MATCH for {menu_keyword!r} -> {action_keyword!r}")
    return None


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    apply_app_theme(app, mode="dark")
    set_plot_theme("dark")
    print(f"[boot] test_project exists: {TEST_PROJECT.exists()}")

    win = MainWindow()
    win.resize(1024, 720)
    win.show()
    win.setGeometry(20, 20, 1024, 720)
    _settle(app, 500)
    _snap(win, "01_dark_small_window", "1024x720 dark welcome")

    win.resize(1920, 1200)
    _settle(app, 500)
    _snap(win, "02_dark_large_window", "1920x1200 after resize")

    win.resize(1024, 720)
    _settle(app, 500)
    _snap(win, "03_dark_resized_back", "back to 1024x720")

    apply_app_theme(app, mode="light")
    set_plot_theme("light")
    _settle(app, 300)
    _snap(win, "04_light_welcome", "light theme")

    apply_app_theme(app, mode="dark")
    set_plot_theme("dark")
    _settle(app, 300)

    if TEST_PROJECT.exists():
        ok = _try("open_project", lambda: win.open_project_path(TEST_PROJECT))
        _settle(app, 400)
        _snap(win, "05_real_project_opened", f"open_project returned {ok!r}")

        rr_files = sorted((TEST_PROJECT / "data" / "raw" / "hrv_logger").rglob("*.csv"))
        rr_files = [f for f in rr_files if "_events" not in f.name.lower()]
        if rr_files:
            print(f"\n[load] {rr_files[0].name}")
            _try("open_path real RR", lambda f=rr_files[0]: win.open_path(f))
            _settle(app, 800)
            win.resize(1600, 1000)
            _settle(app, 600)
            _snap(win, "06_real_rr_loaded", f"{rr_files[0].name}")

    print("\n[scenario] Loading 12 synthetic datasets")
    for i in range(12):
        ds = _synth_dataset(
            name=f"synth_{i:02d}_subj.csv",
            n_beats=400 + (i * 50),
            n_sections=2 + (i % 3),
            seed=42 + i,
            mean_rr=750 + (i * 10),
        )
        win.add_dataset(ds)
    _settle(app, 500)
    _snap(win, "07_workspace_13_datasets", "12 synthetic + 1 real")

    win.set_active_dataset(5)
    _settle(app, 500)
    _snap(win, "08_active_dataset_5", "active=5")

    tabs = win._tabs_widget
    for i in range(tabs.count()):
        if not tabs.isTabVisible(i):
            continue
        tabs.setCurrentIndex(i)
        _settle(app, 500)
        title = tabs.tabText(i).split("(")[0].strip().replace(" ", "_")
        _snap(win, f"09_tab_{i:02d}_{title}", "many-datasets")

    browse_idx = tabs.indexOf(win._browse_tab)
    if browse_idx >= 0:
        tabs.setCurrentIndex(browse_idx)
        _settle(app, 400)

    panel = getattr(win._browse_tab, "_preprocessing_panel", None)
    if panel is not None:
        detect_btn = None
        for b in panel.findChildren(QPushButton):
            if "detect" in b.text().lower():
                detect_btn = b
                break
        if detect_btn:
            _try("click detect", lambda: detect_btn.click())
            _settle(app, 1500)
            _snap(win, "10_after_detect_artifacts", "artifact overlay")

    # The menubar dialog handlers call ``dlg.exec()`` (modal). That spins
    # its own event loop and blocks the script until the dialog closes.
    # Capture-then-close has to run INSIDE that event loop via
    # QTimer.singleShot so the snapshot lands while the dialog is still
    # on screen.

    def _snap_modal(action, class_keyword, snap_name, *, extra_click=None):
        """Trigger ``action`` and snapshot any matching top-level dialog.

        ``class_keyword`` matches against ``type(widget).__name__`` (case
        sensitive). ``extra_click`` is an optional ``(dialog) -> None``
        that runs before the snapshot — used by the compare-dialog flow
        to click "Plot" before grabbing the curve overlay.
        """

        def _capture_and_close():
            target = None
            for w in app.topLevelWidgets():
                if class_keyword in type(w).__name__ and w.isVisible():
                    target = w
                    break
            if target is None:
                visible = [
                    type(w).__name__ for w in app.topLevelWidgets() if w.isVisible()
                ]
                print(
                    f"  [snap_modal] no top-level widget matching "
                    f"{class_keyword!r}; visible={visible}"
                )
                for w in app.topLevelWidgets():
                    if w.isVisible() and w is not win:
                        w.close()
                return
            if extra_click is not None:
                try:
                    extra_click(target)
                except Exception as exc:
                    print(f"  [snap_modal] extra_click raised: {exc}")
                app.processEvents()
            _snap(target, snap_name, f"modal->{class_keyword}")
            target.close()

        QTimer.singleShot(700, _capture_and_close)
        _try(f"trigger {snap_name}", action.trigger)
        _settle(app, 200)

    print("\n[diag] menubar dump:")
    for ma in win.menuBar().actions():
        sub = ma.menu()
        print(f"  menu={ma.text()!r} sub_actions={len(sub.actions()) if sub else 0}")
        if sub:
            for sub_act in sub.actions():
                print(f"    -> {sub_act.text()!r}")

    compare_act = _find_action(win, "tools", "compare")
    if compare_act:

        def _plot_then_snap(dlg):
            for b in dlg.findChildren(QPushButton):
                if b.text().lower() == "plot":
                    b.click()
                    break

        _snap_modal(
            compare_act, "Compare", "11_compare_dialog", extra_click=_plot_then_snap
        )

    pref_act = _find_action(win, "edit", "preferences")
    if pref_act:
        _snap_modal(pref_act, "Preferences", "13_preferences_dialog")

    wt_act = _find_action(win, "help", "walkthrough")
    if wt_act:
        captured = {"count": 0}

        def _walk_all_pages(dlg):
            _snap(dlg, "14_walkthrough_p00", "walkthrough page 0")
            captured["count"] = 1
            next_btn = None
            for b in dlg.findChildren(QPushButton):
                if b.text().lower() == "next":
                    next_btn = b
                    break
            if next_btn is None:
                return
            for page in range(1, 14):
                if not next_btn.isEnabled():
                    break
                next_btn.click()
                app.processEvents()
                _snap(dlg, f"14_walkthrough_p{page:02d}", f"walkthrough page {page}")
                captured["count"] = page + 1

        def _capture_walkthrough():
            for w in app.topLevelWidgets():
                if "Walkthrough" in type(w).__name__ and w.isVisible():
                    _walk_all_pages(w)
                    w.close()
                    return
            print("  [snap_modal] no Walkthrough widget visible")

        QTimer.singleShot(700, _capture_walkthrough)
        _try("trigger walkthrough", wt_act.trigger)
        _settle(app, 200)
        print(f"  [walkthrough] captured {captured['count']} page(s)")

    # Close any leftover dialogs the walkthrough's "Try it" buttons may
    # have opened — without this, the next snapshot loop snaps the wrong
    # dialog (the first lingering _PlotDialog, not the freshly triggered
    # one). MainWindow is never closed.
    def _close_stray_dialogs():
        for w in app.topLevelWidgets():
            if w.isVisible() and w is not win:
                w.close()
        app.processEvents()

    _close_stray_dialogs()
    _settle(app, 300)

    # Tachogram / Poincare / PSD / HR-distribution all share the
    # ``_PlotDialog`` class and are NON-modal (``setModal(False)``), so
    # trigger() returns immediately and we can grab the dialog the normal
    # way — disambiguated by ``windowTitle()`` instead of class name.
    plot_title_map = (
        ("tachogram", "tachogram", "tachogram"),
        ("poincare", "poincare", "poincare"),
        ("psd", "spectral", "psd"),
        ("hr distribution", "heart rate", "hr_dist"),
    )
    for menu_kw, title_kw, label in plot_title_map:
        act = _find_action(win, "tools", menu_kw)
        if not act:
            print(f"  [plot_dialog] no menu action for {menu_kw!r}")
            continue
        _try(f"trigger {menu_kw}", act.trigger)
        _settle(app, 800)
        target = None
        for w in app.topLevelWidgets():
            if not w.isVisible():
                continue
            if w is win:
                continue
            title = w.windowTitle().lower()
            if title_kw in title:
                target = w
                break
        if target is None:
            visible = [
                f"{type(w).__name__}({w.windowTitle()!r})"
                for w in app.topLevelWidgets()
                if w.isVisible()
            ]
            print(f"  [plot_dialog] no match for {title_kw!r}; visible={visible}")
        else:
            _snap(target, f"15_dialog_{label}", f"plot->{title_kw}")
            target.close()
        _settle(app, 200)

    _close_stray_dialogs()
    _settle(app, 300)

    ann_act = _find_action(win, "tools", "annotation")
    if ann_act:
        _snap_modal(ann_act, "Annotation", "16_annotation_table")

    win.resize(800, 600)
    _settle(app, 400)
    _snap(win, "17_tiny_window", "800x600 min-size handling")

    print(f"\n[done] snapshots in {_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
