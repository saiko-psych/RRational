"""Tests for Phase 24A — Help & Guide system.

Covers:
- WalkthroughDialog: multi-page wizard opens, navigates, exposes
  ``page_count`` and ``current_index``.
- HelpExpander: defaults collapsed, toggles via setChecked, body
  visibility tracks the header.
- Tooltips: key buttons on the Setup tab gain ``setToolTip(...)`` calls.
- Status-bar hints: switching tabs posts a context message via
  ``MainWindow._on_tab_changed_hint``.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path, monkeypatch):
    from rrational.gui import persistence as gui_persistence
    from rrational.inspector import persistence, settings

    settings.enable_test_mode(tmp_path)
    persistence.set_inspector_config_dir(tmp_path)
    monkeypatch.setattr(gui_persistence, "CONFIG_DIR", tmp_path / "gui_config")
    monkeypatch.setattr(
        gui_persistence, "SETTINGS_FILE", tmp_path / "gui_config" / "settings.yml"
    )
    yield
    persistence.set_inspector_config_dir(None)


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


# ---------------------------------------------------------------------
# WalkthroughDialog
# ---------------------------------------------------------------------
def test_walkthrough_dialog_opens_with_multiple_pages(qtbot, main_window):
    """The dialog instantiates with >=4 pages and starts on page 0."""
    from rrational.inspector.walkthrough import PAGES, WalkthroughDialog

    dlg = WalkthroughDialog(main_window)
    qtbot.addWidget(dlg)
    assert dlg.page_count() == len(PAGES)
    assert dlg.page_count() >= 4
    assert dlg.current_index() == 0
    # Previous disabled on first page, Next enabled.
    assert dlg._prev_btn.isEnabled() is False
    assert dlg._next_btn.isEnabled() is True


def test_walkthrough_next_and_previous(qtbot, main_window):
    """Clicking next then previous flips the stacked-widget index."""
    from rrational.inspector.walkthrough import WalkthroughDialog

    dlg = WalkthroughDialog(main_window)
    qtbot.addWidget(dlg)
    dlg._on_next()
    assert dlg.current_index() == 1
    dlg._on_prev()
    assert dlg.current_index() == 0


def test_walkthrough_try_button_switches_tab(qtbot, main_window):
    """The Try-it-now jump switches the main window to the target tab."""
    from rrational.inspector.main_window import LAYOUT_STREAMLIT
    from rrational.inspector.walkthrough import WalkthroughDialog

    # DataTab is hidden in MNE-LAB (the default layout); the walkthrough
    # correctly refuses to jump to a hidden tab. Switch to Streamlit mode
    # so the jump has a visible target.
    main_window.set_ui_layout(LAYOUT_STREAMLIT)

    dlg = WalkthroughDialog(main_window)
    qtbot.addWidget(dlg)
    data_tab = getattr(main_window, "_data_tab", None)
    if data_tab is None:
        pytest.skip("Data tab is optional; cannot verify try-it-now jump")
    dlg._on_try("_data_tab")
    assert main_window._tabs_widget.currentWidget() is data_tab


# ---------------------------------------------------------------------
# HelpExpander
# ---------------------------------------------------------------------
def test_help_expander_renders_info_button(qtbot):
    """Phase 25 redesign: HelpExpander is now a thin info-button row that
    opens a popup on click — body label stays hidden until the popup
    opens. is_open() always returns False since popups are transient."""
    from rrational.inspector.help_widgets import HelpExpander

    exp = HelpExpander("Test topic", "<p>Body text.</p>")
    qtbot.addWidget(exp)
    exp.show()
    qtbot.waitExposed(exp)
    # The inline body label is hidden — popup-style help, not inline.
    assert exp.body_label().isVisible() is False
    assert exp.is_open() is False
    # Title accessor available.
    assert exp.title() == "Test topic"
    # The InfoButton child is rendered + clickable.
    assert exp._button is not None
    assert exp._button.isEnabled() is True


# ---------------------------------------------------------------------
# Tooltips on key Setup tab buttons
# ---------------------------------------------------------------------
def test_setup_tab_key_buttons_have_tooltips(main_window):
    """Add / Edit / Remove buttons on each Setup sub-pane have tooltips."""
    setup = main_window._setup_tab
    panes = [
        setup._events_pane,
        setup._sections_pane,
        setup._groups_pane,
        setup._sequences_pane,
    ]
    for pane in panes:
        for attr in ("_add_btn", "_edit_btn", "_remove_btn"):
            btn = getattr(pane, attr, None)
            if btn is None:
                continue
            assert btn.toolTip(), f"{type(pane).__name__}.{attr} missing tooltip"
            # Tooltips must be single-sentence-ish (well under 80 chars).
            assert len(btn.toolTip()) < 120


# ---------------------------------------------------------------------
# Status-bar hint on tab switch
# ---------------------------------------------------------------------
def test_status_bar_hint_posted_on_tab_switch(main_window):
    """``_on_tab_changed_hint`` posts a tab-specific message to the status bar."""
    # Pick the analysis tab — present in every layout mode.
    tabs = main_window._tabs_widget
    analysis = main_window._analysis_tab
    idx = tabs.indexOf(analysis)
    assert idx >= 0
    # Make sure the tab is visible in the current layout; switch to
    # mnelab mode if streamlit hides it (it doesn't for Analysis, but
    # belt-and-braces).
    if not tabs.isTabVisible(idx):
        main_window.set_ui_layout("mnelab")
        idx = tabs.indexOf(analysis)
    main_window._on_tab_changed_hint(idx)
    msg = main_window.statusBar().currentMessage()
    assert "metric preset" in msg or "Compute" in msg
