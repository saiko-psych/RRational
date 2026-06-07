"""Phase 22.3 — View → Layout switcher (Streamlit / MNE-LAB modes).

The switcher controls which top-level tabs are visible. Implementation
constructs every tab unconditionally and toggles ``setTabVisible`` per
mode, so cross-tab state (active dataset, results store, etc.) survives
a mode switch unchanged.

DataTab and ParticipantTab are added by parallel agents — these tests
must keep passing whether or not those classes exist yet.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def _isolate_settings(qapp, tmp_path):
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    yield


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


def _visible_tab_widgets(win):
    """Return the ordered list of currently-visible tab widgets."""
    tw = win._tabs_widget
    return [tw.widget(i) for i in range(tw.count()) if tw.isTabVisible(i)]


# ---------------------------------------------------------------------
# Default mode
# ---------------------------------------------------------------------
def test_default_layout_is_mnelab(main_window):
    """A fresh QSettings (autouse-isolated) ⇒ MNE-LAB is the default.

    The classic sidebar + plot + tool-rail pattern is the most intuitive
    entry point for newcomers. Users who previously chose Streamlit keep
    that preference; this just changes the value used when no preference
    is on record.
    """
    from rrational.inspector.main_window import LAYOUT_MNELAB

    assert main_window._ui_layout == LAYOUT_MNELAB


def test_streamlit_mode_hides_browse_tab(main_window):
    from rrational.inspector.main_window import LAYOUT_STREAMLIT

    main_window.set_ui_layout(LAYOUT_STREAMLIT)
    assert main_window._browse_tab not in _visible_tab_widgets(main_window)


# ---------------------------------------------------------------------
# MNE-LAB mode
# ---------------------------------------------------------------------
def test_mnelab_mode_shows_browse_and_hides_streamlit_only_tabs(main_window):
    from rrational.inspector.main_window import LAYOUT_MNELAB

    main_window.set_ui_layout(LAYOUT_MNELAB)
    visible = _visible_tab_widgets(main_window)
    # Browse always shown in MNE-LAB mode.
    assert main_window._browse_tab in visible
    # Standard tabs visible regardless of optional-tab presence.
    assert main_window._setup_tab in visible
    assert main_window._participants_tab in visible
    assert main_window._analysis_tab in visible
    assert main_window._results_tab in visible
    # Streamlit-only tabs, if they exist at all, must be HIDDEN.
    if main_window._data_tab is not None:
        assert main_window._data_tab not in visible
    if main_window._participant_tab is not None:
        assert main_window._participant_tab not in visible


def test_streamlit_mode_visible_tabs(main_window):
    """Streamlit mode = Data / Participant / Setup / Analysis / Results,
    minus any optional tabs that haven't been added yet."""
    from rrational.inspector.main_window import LAYOUT_STREAMLIT

    main_window.set_ui_layout(LAYOUT_STREAMLIT)
    visible = _visible_tab_widgets(main_window)
    # BrowseTab is always hidden in Streamlit mode.
    assert main_window._browse_tab not in visible
    # Setup / Analysis / Results are always shown.
    assert main_window._setup_tab in visible
    assert main_window._analysis_tab in visible
    assert main_window._results_tab in visible


# ---------------------------------------------------------------------
# Round-trip switching
# ---------------------------------------------------------------------
def test_switch_back_and_forth_is_idempotent(main_window):
    from rrational.inspector.main_window import LAYOUT_MNELAB, LAYOUT_STREAMLIT

    main_window.set_ui_layout(LAYOUT_MNELAB)
    assert main_window._browse_tab in _visible_tab_widgets(main_window)

    main_window.set_ui_layout(LAYOUT_STREAMLIT)
    assert main_window._browse_tab not in _visible_tab_widgets(main_window)

    main_window.set_ui_layout(LAYOUT_MNELAB)
    assert main_window._browse_tab in _visible_tab_widgets(main_window)


# ---------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------
def test_layout_persists_across_main_window_reconstruction(qtbot, qapp):
    """Write the mode in one window, instantiate a new one — the second
    window must come up in the saved mode."""
    from rrational.inspector import settings
    from rrational.inspector.main_window import (
        LAYOUT_MNELAB,
        LAYOUT_STREAMLIT,
        MainWindow,
    )

    # First window: switch to MNE-LAB and explicitly persist (test_mode
    # blocks the auto-write, so we mimic the production path).
    w1 = MainWindow()
    w1.test_mode = False  # so set_ui_layout writes to QSettings
    qtbot.addWidget(w1)
    w1.set_ui_layout(LAYOUT_MNELAB)
    assert settings.read_setting("ui_layout") == LAYOUT_MNELAB
    w1.close()

    # Second window: should pick up MNE-LAB from QSettings.
    w2 = MainWindow()
    w2.test_mode = True
    qtbot.addWidget(w2)
    assert w2._ui_layout == LAYOUT_MNELAB
    assert w2._browse_tab in _visible_tab_widgets(w2)
    w2.close()

    # Switch back to streamlit + re-instantiate.
    w3 = MainWindow()
    w3.test_mode = False
    qtbot.addWidget(w3)
    w3.set_ui_layout(LAYOUT_STREAMLIT)
    assert settings.read_setting("ui_layout") == LAYOUT_STREAMLIT
    w3.close()

    w4 = MainWindow()
    w4.test_mode = True
    qtbot.addWidget(w4)
    assert w4._ui_layout == LAYOUT_STREAMLIT
    assert w4._browse_tab not in _visible_tab_widgets(w4)
    w4.close()


# ---------------------------------------------------------------------
# Menu wiring
# ---------------------------------------------------------------------
def test_layout_menu_actions_are_radio(main_window):
    """The two layout actions live in an exclusive QActionGroup."""
    grp = main_window._layout_action_group
    assert grp.isExclusive()
    actions = grp.actions()
    assert main_window._layout_streamlit_act in actions
    assert main_window._layout_mnelab_act in actions
    # Exactly one should be checked at any time.
    checked = [a for a in actions if a.isChecked()]
    assert len(checked) == 1


def test_clicking_mnelab_menu_action_switches_mode(main_window):
    from rrational.inspector.main_window import LAYOUT_MNELAB, LAYOUT_STREAMLIT

    # Force streamlit first so triggering the MNE action is a real switch
    # (default mode is now MNE-LAB; triggering an already-checked action
    # in an exclusive QActionGroup is a no-op).
    main_window.set_ui_layout(LAYOUT_STREAMLIT)
    main_window._layout_mnelab_act.trigger()
    assert main_window._ui_layout == LAYOUT_MNELAB
    assert main_window._browse_tab in _visible_tab_widgets(main_window)


def test_clicking_streamlit_menu_action_switches_mode(main_window):
    from rrational.inspector.main_window import LAYOUT_MNELAB, LAYOUT_STREAMLIT

    main_window.set_ui_layout(LAYOUT_MNELAB)
    main_window._layout_streamlit_act.trigger()
    assert main_window._ui_layout == LAYOUT_STREAMLIT
    assert main_window._browse_tab not in _visible_tab_widgets(main_window)


def test_set_ui_layout_syncs_menu_action_state(main_window):
    """Calling set_ui_layout programmatically still updates the menu."""
    from rrational.inspector.main_window import LAYOUT_MNELAB, LAYOUT_STREAMLIT

    main_window.set_ui_layout(LAYOUT_MNELAB)
    assert main_window._layout_mnelab_act.isChecked()
    assert not main_window._layout_streamlit_act.isChecked()

    main_window.set_ui_layout(LAYOUT_STREAMLIT)
    assert main_window._layout_streamlit_act.isChecked()
    assert not main_window._layout_mnelab_act.isChecked()


# ---------------------------------------------------------------------
# All tabs constructed regardless of mode
# ---------------------------------------------------------------------
def test_all_required_tabs_are_constructed(main_window):
    """Visibility is per-mode; the WIDGETS themselves always exist so
    cross-tab state survives switching."""
    assert main_window._browse_tab is not None
    assert main_window._setup_tab is not None
    assert main_window._participants_tab is not None
    assert main_window._analysis_tab is not None
    assert main_window._results_tab is not None


def test_invalid_layout_falls_back_to_mnelab(main_window):
    from rrational.inspector.main_window import LAYOUT_MNELAB

    main_window.set_ui_layout("bogus-mode")
    assert main_window._ui_layout == LAYOUT_MNELAB
