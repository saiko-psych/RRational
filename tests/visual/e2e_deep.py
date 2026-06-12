"""Deep visual coverage — every workflow that e2e_advanced.py only
hits at the empty-state level: filled analysis tables, plotted compare
curves, group charts with real data, light-theme tour of every tab,
HTML report export, BIDS / PRISM dialogs, batch preprocess + quality
triage, and the Holter / 100-dataset cases the radical harness
truncated.

Output: tests/visual/e2e_snapshots/deep_NN_<scenario>.png
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import numpy as np
from qtpy.QtCore import QEventLoop, Qt, QTimer
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
    path = _OUT / f"deep_{name}.png"
    pix = widget.grab()
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


def _find_action(win, menu_keyword, action_keyword):
    for menu_action in win.menuBar().actions():
        menu_label = menu_action.text().replace("&", "").lower()
        if menu_keyword.lower() not in menu_label:
            continue
        menu = menu_action.menu()
        if not menu:
            continue
        for act in menu.actions():
            text = act.text().replace("&", "").lower()
            if action_keyword.lower() in text:
                return act
    return None


def _synth_dataset(name, n_beats=600, seed=42, mean_rr=800, n_sections=3):
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


def _walk_all_tabs(app, win, prefix, theme_note):
    """Snap every visible top-level tab — used to capture a full theme tour."""
    tabs = win._tabs_widget
    for i in range(tabs.count()):
        if not tabs.isTabVisible(i):
            continue
        tabs.setCurrentIndex(i)
        _settle(app, 600)
        title = tabs.tabText(i).split("(")[0].strip().replace(" ", "_")
        _snap(win, f"{prefix}_{i:02d}_{title}", f"{theme_note}")


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    apply_app_theme(app, mode="dark")
    set_plot_theme("dark")

    print("[boot] Deep E2E starting")
    win = MainWindow()
    win.resize(1600, 1000)
    win.show()
    _settle(app, 500)

    # Open the real test project so Setup / Participants tabs have actual content.
    if TEST_PROJECT.exists():
        _try("open project", lambda: win.open_project_path(TEST_PROJECT))
        _settle(app, 500)

    # ----- Phase 1: load 8 synthetic datasets with shared section structure -
    print("\n[1] Load 8 synthetic datasets (varied means)")
    for i in range(8):
        ds = _synth_dataset(
            name=f"deep_subj_{i:02d}.csv",
            n_beats=500,
            seed=100 + i,
            mean_rr=780 + (i % 4) * 25,  # 780/805/830/855
            n_sections=3,
        )
        win.add_dataset(ds)
    _settle(app, 400)
    print(f"  loaded={len(win._datasets)}")

    # ----- Phase 2: Compare HRV curves WITH plot ----------------------------
    print("\n[2] Compare HRV curves — actually click Plot")
    compare_act = _find_action(win, "tools", "compare")
    if compare_act:

        def _select_and_plot(dlg):
            # Pick datasets 0-3 for Group A, 4-7 for Group B, then click Plot
            from qtpy.QtWidgets import QListWidget

            lists = dlg.findChildren(QListWidget)
            if len(lists) >= 2:
                for row in range(min(4, lists[0].count())):
                    lists[0].item(row).setSelected(True)
                for row in range(4, min(8, lists[1].count())):
                    lists[1].item(row).setSelected(True)
            app.processEvents()
            for b in dlg.findChildren(QPushButton):
                if b.text().lower() == "plot":
                    b.click()
                    break

        def _capture_compare():
            for w in app.topLevelWidgets():
                if "Compare" in type(w).__name__ and w.isVisible():
                    _snap(w, "10_compare_initial", "before plot")
                    _select_and_plot(w)
                    app.processEvents()
                    _settle(app, 1000)
                    _snap(w, "11_compare_plotted", "after Plot click")
                    w.close()
                    return
            print("  [compare] dialog not found")

        QTimer.singleShot(700, _capture_compare)
        _try("trigger compare", compare_act.trigger)
        _settle(app, 300)

    # ----- Phase 3: Analysis tab — actually Compute --------------------------
    print("\n[3] Analysis tab — Compute HRV metrics")
    tabs = win._tabs_widget
    analysis_tab = getattr(win, "_analysis_tab", None)
    if analysis_tab is not None:
        idx = tabs.indexOf(analysis_tab)
        if idx >= 0:
            tabs.setCurrentIndex(idx)
            _settle(app, 600)
            _snap(win, "12_analysis_before_compute", "metrics empty state")
            # Find and click Compute button
            compute_btn = None
            for b in analysis_tab.findChildren(QPushButton):
                if "compute" in b.text().lower():
                    compute_btn = b
                    break
            if compute_btn:
                _try("click compute", compute_btn.click)
                _settle(app, 2000)
                _snap(win, "13_analysis_after_compute", "metrics table populated")

    # ----- Phase 4: Group comparison mode in Analysis ------------------------
    print("\n[4] Analysis — Group comparison mode")
    if analysis_tab is not None:
        # Look for the Mode combo (Single Participant / Repeating / Group / Sequence)
        from qtpy.QtWidgets import QComboBox

        for cb in analysis_tab.findChildren(QComboBox):
            for k in range(cb.count()):
                if "group" in cb.itemText(k).lower():
                    cb.setCurrentIndex(k)
                    break
        _settle(app, 600)
        _snap(win, "14_analysis_group_mode", "mode=Group comparison")
        # Try compute again in group mode
        for b in analysis_tab.findChildren(QPushButton):
            if "compute" in b.text().lower() or "run" in b.text().lower():
                _try("click compute (group)", b.click)
                _settle(app, 2500)
                _snap(win, "15_analysis_group_results", "group bars rendered")
                break

    # ----- Phase 5: Results tab after compute -------------------------------
    print("\n[5] Results tab — populated metrics table")
    results_tab = getattr(win, "_results_tab", None)
    if results_tab is not None:
        idx = tabs.indexOf(results_tab)
        if idx >= 0:
            tabs.setCurrentIndex(idx)
            _settle(app, 600)
            _snap(win, "16_results_populated", "table after compute")

    # ----- Phase 6: Detect-artifact on active dataset, then exclusion -------
    print("\n[6] Browse tab — detect + exclusion overlays")
    browse_tab = getattr(win, "_browse_tab", None)
    if browse_tab is not None:
        idx = tabs.indexOf(browse_tab)
        if idx >= 0:
            tabs.setCurrentIndex(idx)
            _settle(app, 500)
        # Click Detect artifacts
        panel = getattr(browse_tab, "_preprocessing_panel", None)
        if panel is not None:
            for b in panel.findChildren(QPushButton):
                if "detect" in b.text().lower():
                    _try("click detect", b.click)
                    _settle(app, 1500)
                    _snap(win, "17_browse_detect_overlay", "artifact marks on plot")
                    break

    # ----- Phase 7: BIDS / PRISM export dialogs ----------------------------
    print("\n[7] BIDS + PRISM export dialogs (UI only — no file write)")
    for keyword, class_kw, label in (
        ("bids", "BIDS", "20_bids_dialog"),
        ("prism", "PRISM", "21_prism_dialog"),
    ):
        act = _find_action(win, "tools", keyword)
        if act:

            def _capture_export_dlg(class_kw=class_kw, label=label):
                for w in app.topLevelWidgets():
                    if class_kw in type(w).__name__ and w.isVisible():
                        _snap(w, label, f"{class_kw} export dialog")
                        w.close()
                        return
                visible = [
                    type(w).__name__
                    for w in app.topLevelWidgets()
                    if w.isVisible() and w is not win
                ]
                print(f"  [export {class_kw}] not found; visible={visible}")
                # Close any unrelated dialog so we don't deadlock on next iter
                for w in app.topLevelWidgets():
                    if w.isVisible() and w is not win:
                        w.close()

            QTimer.singleShot(700, _capture_export_dlg)
            _try(f"trigger {keyword}", act.trigger)
            _settle(app, 300)

    # ----- Phase 8: Batch preprocess + Quality triage ----------------------
    print("\n[8] Batch preprocess + Quality triage dashboard")
    batch_act = _find_action(win, "tools", "preprocessing on all")
    if batch_act:

        def _capture_batch():
            for w in app.topLevelWidgets():
                if (
                    "Batch" in type(w).__name__ or "Triage" in type(w).__name__
                ) and w.isVisible():
                    _snap(w, "22_batch_dashboard", "batch dashboard")
                    w.close()
                    return
            visible = [
                type(w).__name__
                for w in app.topLevelWidgets()
                if w.isVisible() and w is not win
            ]
            print(f"  [batch] not found; visible={visible}")
            for w in app.topLevelWidgets():
                if w.isVisible() and w is not win:
                    w.close()

        QTimer.singleShot(3000, _capture_batch)
        _try("trigger batch", batch_act.trigger)
        _settle(app, 500)

    triage_act = _find_action(win, "tools", "quality triage")
    if triage_act:

        def _capture_triage():
            for w in app.topLevelWidgets():
                if "Triage" in type(w).__name__ and w.isVisible():
                    _snap(w, "23_triage_dashboard", "quality triage dashboard")
                    w.close()
                    return
            print("  [triage] not found")

        QTimer.singleShot(900, _capture_triage)
        _try("trigger triage", triage_act.trigger)
        _settle(app, 400)

    # ----- Phase 9: LIGHT theme tour ---------------------------------------
    print("\n[9] LIGHT theme tour — every tab")
    apply_app_theme(app, mode="light")
    set_plot_theme("light")
    _settle(app, 500)
    _walk_all_tabs(app, win, prefix="30_light", theme_note="LIGHT")
    # Re-trigger the plot dialogs under light theme to verify badge/contrast fixes
    for keyword, title_kw, label in (
        ("tachogram", "tachogram", "31_light_tachogram"),
        ("poincare", "poincare", "32_light_poincare"),
        ("psd", "spectral", "33_light_psd"),
        ("hr distribution", "heart rate", "34_light_hrdist"),
    ):
        act = _find_action(win, "tools", keyword)
        if act:
            _try(f"trigger {keyword}", act.trigger)
            _settle(app, 800)
            for w in app.topLevelWidgets():
                if not w.isVisible() or w is win:
                    continue
                if title_kw in w.windowTitle().lower():
                    _snap(w, label, f"light theme {keyword}")
                    w.close()
                    break
            _settle(app, 200)

    # Compare dialog in light theme
    compare_act = _find_action(win, "tools", "compare")
    if compare_act:

        def _light_compare_plot(dlg):
            from qtpy.QtWidgets import QListWidget

            lists = dlg.findChildren(QListWidget)
            if len(lists) >= 2:
                for row in range(min(4, lists[0].count())):
                    lists[0].item(row).setSelected(True)
                for row in range(4, min(8, lists[1].count())):
                    lists[1].item(row).setSelected(True)
            for b in dlg.findChildren(QPushButton):
                if b.text().lower() == "plot":
                    b.click()
                    break

        def _capture_compare_light():
            for w in app.topLevelWidgets():
                if "Compare" in type(w).__name__ and w.isVisible():
                    _light_compare_plot(w)
                    app.processEvents()
                    _settle(app, 1000)
                    _snap(w, "35_light_compare", "light compare with curves")
                    w.close()
                    return
            print("  [light compare] not found")

        QTimer.singleShot(700, _capture_compare_light)
        _try("trigger light compare", compare_act.trigger)
        _settle(app, 300)

    # Back to dark for any follow-up phases
    apply_app_theme(app, mode="dark")
    set_plot_theme("dark")
    _settle(app, 300)

    # ----- Phase 10: Holter scale --------------------------------------
    print("\n[10] Holter-scale recording (86k beats)")
    rng = np.random.default_rng(seed=12345)
    n = 86_400
    rr = 800 + 80 * rng.standard_normal(n)
    t = np.cumsum(rr) / 1000.0
    sections = []
    step = n // 24  # 24 sections, hour-scale
    for i in range(24):
        a = i * step
        b = (i + 1) * step - 1 if i < 23 else n - 1
        sections.append(
            SectionMeta(
                name=f"hour_{i:02d}",
                t_start=float(t[a]),
                t_end=float(t[b]),
                beat_count=b - a + 1,
            )
        )
    holter = Dataset(
        name="holter_24h_sim.csv",
        data=InspectorData(t=t, v=rr, sections=sections, events=[]),
    )
    _try("add holter", lambda: win.add_dataset(holter))
    _try("activate holter", lambda: win.set_active_dataset(len(win._datasets) - 1))
    _settle(app, 2000)
    _snap(win, "40_holter_browse", "Holter rendered in Browse")

    # ----- Phase 11: 100-dataset workspace stress ----------------------
    print("\n[11] 100-dataset workspace stress")
    rng = np.random.default_rng(seed=55555)
    target = 100
    added = 0
    while added < target:
        n = 400
        rr = 800 + 30 * rng.standard_normal(n)
        t = np.cumsum(rr) / 1000.0
        try:
            ds = Dataset(
                name=f"stress_{added:03d}.csv",
                data=InspectorData(t=t, v=rr),
            )
            win.add_dataset(ds)
            added += 1
        except Exception as exc:
            print(f"  [stress] add {added} failed: {exc}")
            break
        if added % 20 == 0:
            app.processEvents()
    _settle(app, 1000)
    print(f"  total in workspace = {len(win._datasets)}")
    _snap(win, "41_stress_workspace", f"{len(win._datasets)} datasets total")

    # Participants tab under stress
    participants_tab = getattr(win, "_participants_tab", None)
    if participants_tab is not None:
        idx = tabs.indexOf(participants_tab)
        if idx >= 0:
            tabs.setCurrentIndex(idx)
            _settle(app, 2500)
            _snap(win, "42_stress_participants_grid", "grid with 100+ recordings")

    print("\n[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
