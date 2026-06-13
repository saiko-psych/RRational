"""Button-by-button visual smoke — click every interactive control on every
visible tab and snapshot the result.

The advanced + deep E2E scripts focus on workflow snapshots; this one
inverts the lens: walk every QPushButton, QCheckBox, QComboBox, QSpinBox,
QToolButton that's currently visible, click/toggle it, and snap the
before/after. Anything that explodes (modal dialog, traceback, frozen
state) gets logged with the offending widget's text.

Output: tests/visual/e2e_snapshots/btn_NN_<scenario>.png
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

import numpy as np
from qtpy.QtCore import QEventLoop, Qt, QTimer
from qtpy.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QPushButton,
    QSpinBox,
    QToolButton,
    QWidget,
)

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


def _settle(app, ms=300):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    app.processEvents()


def _snap(widget, name, note=""):
    path = _OUT / f"btn_{name}.png"
    pix = widget.grab()
    if pix.width() > 1200 or pix.height() > 900:
        pix = pix.scaled(1200, 900, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    pix.save(str(path), "PNG")
    suffix = f" -- {note}" if note else ""
    print(f"[snap] {path.name} {pix.width()}x{pix.height()}{suffix}")


def _close_strays(app, keep):
    """Close every visible top-level widget except ``keep``."""
    for w in app.topLevelWidgets():
        if w is keep:
            continue
        if w.isVisible():
            try:
                w.close()
            except Exception:
                pass


def _synth_dataset(name, n_beats=400, seed=42, mean_rr=800):
    rng = np.random.default_rng(seed=seed)
    rr = mean_rr + 30 * rng.standard_normal(n_beats)
    base = 1_700_000_000 + seed * 1000
    t = base + np.cumsum(rr) / 1000.0
    sections = [
        SectionMeta(
            name="sec_00",
            t_start=float(t[0]),
            t_end=float(t[n_beats // 2 - 1]),
            beat_count=n_beats // 2,
        ),
        SectionMeta(
            name="sec_01",
            t_start=float(t[n_beats // 2]),
            t_end=float(t[-1]),
            beat_count=n_beats // 2,
        ),
    ]
    events = [
        EventMeta(label="rest_pre_start", t=float(t[0])),
        EventMeta(label="measurement_start", t=float(t[n_beats // 2])),
        EventMeta(label="measurement_end", t=float(t[-1])),
    ]
    return Dataset(
        name=name,
        data=InspectorData(t=t, v=rr, sections=sections, events=events),
    )


def _click_buttons(app, win, container: QWidget, label: str, max_clicks=8):
    """Click every visible QPushButton inside ``container`` and snap after each.

    Buttons that pop a modal dialog get auto-closed via QTimer.singleShot
    so the iteration doesn't deadlock. Skip rules:

    * Buttons whose text is empty or whitespace (icon-only — too noisy).
    * Buttons whose text is "Close" / "Cancel" / "Quit" (would shut us
      down before we finish).
    * Disabled buttons.
    """
    skip_text = {
        "close",
        "cancel",
        "quit",
        "exit",
        "delete selected",  # destructive
        "remove",  # destructive
        "delete",
        "clear",
        "clear cache",
        "save now",  # touches disk
        "reload from disk",
        "export csv...",  # opens file dialog
        "export wide format...",
        "export csv...",
        "save recipe...",
        "import csv...",
        "export codebook...",
    }
    clicked = 0
    for b in container.findChildren(QPushButton):
        if clicked >= max_clicks:
            break
        if not b.isVisible() or not b.isEnabled():
            continue
        # Strip out any non-ASCII glyphs from the button text before
        # printing — Windows cp1252 console can't encode chars like
        # checkmark (U+2713) or em-dash, and the print() failure
        # bubbles up and aborts the whole sweep.
        raw_txt = b.text().strip().lower().replace("&", "")
        txt = raw_txt.encode("ascii", "ignore").decode("ascii")
        if not txt or raw_txt in skip_text:
            continue

        # Auto-close any modal that appears so the iteration keeps moving.
        def _autoclose():
            for w in app.topLevelWidgets():
                if w.isVisible() and w is not win:
                    try:
                        w.close()
                    except Exception:
                        pass

        QTimer.singleShot(450, _autoclose)
        try:
            print(f"  [click] {label}: {txt!r}")
            b.click()
        except Exception as exc:
            print(f"  [FAIL] {label} click {txt!r}: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            continue
        _settle(app, 500)
        slug = txt.replace(" ", "_").replace("/", "_")[:24]
        _snap(win, f"{label}_btn{clicked:02d}_{slug}", f"after click {txt!r}")
        clicked += 1
        _close_strays(app, win)


def _toggle_checkboxes(app, win, container: QWidget, label: str, max_toggles=4):
    """Toggle every checkbox once, snap after."""
    toggled = 0
    for cb in container.findChildren(QCheckBox):
        if toggled >= max_toggles:
            break
        if not cb.isVisible() or not cb.isEnabled():
            continue
        txt = cb.text().strip().replace("&", "")
        if not txt:
            continue
        try:
            print(f"  [toggle] {label}: {txt!r}")
            cb.toggle()
        except Exception as exc:
            print(f"  [FAIL] toggle {txt!r}: {type(exc).__name__}: {exc}")
            continue
        _settle(app, 400)
        slug = txt.lower().replace(" ", "_")[:24]
        _snap(win, f"{label}_chk{toggled:02d}_{slug}", f"toggle {txt!r}")
        toggled += 1


def _cycle_combos(app, win, container: QWidget, label: str, max_cycles=4):
    """Step every combo box forward once, snap after."""
    cycled = 0
    for cb in container.findChildren(QComboBox):
        if cycled >= max_cycles:
            break
        if not cb.isVisible() or not cb.isEnabled() or cb.count() < 2:
            continue
        cur = cb.currentIndex()
        nxt = (cur + 1) % cb.count()
        prev_text = cb.itemText(cur)
        next_text = cb.itemText(nxt)
        try:
            print(f"  [combo] {label}: {prev_text!r} -> {next_text!r}")
            cb.setCurrentIndex(nxt)
        except Exception as exc:
            print(f"  [FAIL] combo {prev_text!r}: {type(exc).__name__}: {exc}")
            continue
        _settle(app, 400)
        slug = next_text.lower().replace(" ", "_")[:20]
        _snap(win, f"{label}_cb{cycled:02d}_{slug}", f"combo {next_text!r}")
        cycled += 1


def _bump_spinboxes(app, win, container: QWidget, label: str, max_bumps=3):
    """Step every spinbox up once, snap after."""
    bumped = 0
    for sb in container.findChildren(QSpinBox):
        if bumped >= max_bumps:
            break
        if not sb.isVisible() or not sb.isEnabled():
            continue
        try:
            sb.stepUp()
        except Exception as exc:
            print(f"  [FAIL] spinbox: {type(exc).__name__}: {exc}")
            continue
        _settle(app, 300)
        _snap(win, f"{label}_spin{bumped:02d}", "spin up")
        bumped += 1


def _toolbar_walk(app, win, container: QWidget, label: str, max_clicks=4):
    """Click visible QToolButtons (toolbar buttons usually icon-only)."""
    clicked = 0
    for tb in container.findChildren(QToolButton):
        if clicked >= max_clicks:
            break
        if not tb.isVisible() or not tb.isEnabled():
            continue
        # ASCII-strip BOTH text() and tooltip() so the cp1252 console
        # doesn't choke on glyphs like the circled "(i)" info icon
        # (U+24D8). Without the strip, every print() of a unicode-laden
        # toolbutton aborted the sweep mid-run.
        raw_txt = (tb.text() or tb.toolTip() or "tool").strip().replace("&", "")
        txt = raw_txt.encode("ascii", "ignore").decode("ascii").strip()
        if not txt:
            txt = "icon"
        try:
            print(f"  [tool] {label}: {txt!r}")
            QTimer.singleShot(450, lambda: _close_strays(app, win))
            tb.click()
        except Exception as exc:
            print(f"  [FAIL] tool {txt!r}: {type(exc).__name__}: {exc}")
            continue
        _settle(app, 400)
        slug = txt.lower().replace(" ", "_")[:20]
        _snap(win, f"{label}_tool{clicked:02d}_{slug}", f"tool {txt!r}")
        clicked += 1
        _close_strays(app, win)


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    apply_app_theme(app, mode="dark")
    set_plot_theme("dark")

    print("[boot] Button-smash E2E starting")
    win = MainWindow()
    win.resize(1600, 1000)
    win.show()
    _settle(app, 600)

    # Open the real project so Setup tabs have real content (codebook, events).
    if TEST_PROJECT.exists():
        try:
            win.open_project_path(TEST_PROJECT)
        except Exception as exc:
            print(f"[boot] open_project failed: {exc}")
        _settle(app, 500)

    # Load 3 synthetic datasets with shared section labels for downstream
    # buttons that need an active dataset (compute, detect, export...).
    for i in range(3):
        ds = _synth_dataset(name=f"btn_subj_{i}.csv", seed=10 + i, mean_rr=780 + i * 20)
        try:
            win.add_dataset(ds)
        except Exception as exc:
            print(f"[boot] add_dataset {i} failed: {exc}")
    win.set_active_dataset(0)
    _settle(app, 600)
    _snap(win, "00_boot_with_datasets", "3 datasets loaded, ready")

    # Walk each visible top-level tab and exercise its controls.
    tabs = win._tabs_widget
    for i in range(tabs.count()):
        if not tabs.isTabVisible(i):
            continue
        tabs.setCurrentIndex(i)
        _settle(app, 500)
        title = tabs.tabText(i).split("(")[0].strip().replace(" ", "_") or f"tab{i}"
        label = f"{i:02d}_{title}"
        tab_widget = tabs.widget(i)
        print(f"\n=== TAB {i}: {title} ===")
        _snap(win, f"{label}_pre", "tab opened")
        _click_buttons(app, win, tab_widget, label, max_clicks=6)
        _toggle_checkboxes(app, win, tab_widget, label, max_toggles=3)
        _cycle_combos(app, win, tab_widget, label, max_cycles=3)
        _bump_spinboxes(app, win, tab_widget, label, max_bumps=2)
        _toolbar_walk(app, win, tab_widget, label, max_clicks=2)
        _snap(win, f"{label}_post", "tab fully smashed")
        _close_strays(app, win)

    # Browse-tab plot toolbar (the small icons above the dataset chips)
    print("\n=== Browse-tab plot toolbar ===")
    browse = getattr(win, "_browse_tab", None)
    if browse is not None:
        idx = tabs.indexOf(browse)
        if idx >= 0:
            tabs.setCurrentIndex(idx)
            _settle(app, 300)
        _toolbar_walk(app, win, browse, "99_browse_toolbar", max_clicks=6)

    print("\n[done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
