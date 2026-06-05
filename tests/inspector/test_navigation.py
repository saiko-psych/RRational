"""Keyboard- and toolbar-driven navigation tests for the inspector.

Regression net for the Phase-1 Home/End bug: the original
``jump_start``/``jump_end`` preserved the current viewport width, which
made the keys a no-op whenever the user was already showing the whole
signal. The tests below assert window SIZE in addition to position, so
that bug would have been caught immediately.

Pattern borrowed from mne-qt-browser's ``tests/test_pg_specific.py``:
state assertions on the viewbox after a ``qtbot.keyClick`` rather than
pixel-level screenshot regression.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path):
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    yield


@pytest.fixture
def main_window(qtbot, synthetic_inspector_data):
    """Construct a MainWindow with synthetic InspectorData pre-loaded."""
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True  # silence modal dialogs
    # Phase 22.3: navigation keypresses act on the BrowseTab plot, which
    # is only visible (and focus-receptive) in MNE-LAB mode.
    win.set_ui_layout("mnelab")
    qtbot.addWidget(win)

    win.load_data(synthetic_inspector_data)

    win.show()
    qtbot.waitExposed(win)
    return win


def _x_range(win):
    """Convenience: return (xmin, xmax) of the plot's visible X range."""
    return tuple(win._plot.getViewBox().viewRange()[0])


# ---------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------
def test_initial_view_shows_full_recording(main_window, synthetic_inspector_data):
    """Phase-2 default: load shows the WHOLE timeline, not first 60 s.

    The user picks structure out of the overview, then zooms via
    sidebar/keys. This is the inverse of the Phase-1 default and the
    central UX premise behind the continuous-timeline rewrite.
    """
    data = synthetic_inspector_data
    xmin, xmax = _x_range(main_window)
    span = xmax - xmin
    expected_span = data.t_end - data.t_start
    # padding=0.02 in set_data → up to ±4% wider
    assert span == pytest.approx(expected_span, rel=0.08)
    assert xmin <= data.t_start
    assert xmax >= data.t_end


# ---------------------------------------------------------------------
# Home / End — the original bug
# ---------------------------------------------------------------------
def test_end_key_jumps_to_last_60s(main_window, qtbot, synthetic_inspector_data):
    """End must move the viewport to the LAST 60 s of the signal.

    Regression: original ``jump_end`` preserved current width — when
    the viewport already covered the full signal (which Phase 2 makes
    the DEFAULT load state!), pressing End was a no-op. This test
    starts from full-zoom (the new default) and asserts the fixed
    60 s window.
    """
    from qtpy.QtCore import Qt

    t1 = synthetic_inspector_data.t_end

    qtbot.keyClick(main_window, Qt.Key_End)

    xmin, xmax = _x_range(main_window)
    assert xmax == pytest.approx(t1, abs=0.5)
    assert (xmax - xmin) == pytest.approx(60, abs=1.0)


def test_home_key_jumps_to_first_60s(main_window, qtbot, synthetic_inspector_data):
    """Home must jump back to first 60 s after the user has panned away."""
    from qtpy.QtCore import Qt

    t0, t1 = synthetic_inspector_data.t_start, synthetic_inspector_data.t_end
    # Pan to the end first
    main_window._plot.getViewBox().setXRange(t1 - 30, t1, padding=0)

    qtbot.keyClick(main_window, Qt.Key_Home)

    xmin, xmax = _x_range(main_window)
    assert xmin == pytest.approx(t0, abs=0.5)
    assert (xmax - xmin) == pytest.approx(60, abs=1.0)


def test_home_key_fires_even_when_sidebar_has_focus(
    main_window, qtbot, synthetic_inspector_data
):
    """The global eventFilter must intercept Home before QListWidget eats it.

    Without the QApplication-level filter, focusing the sidebar would
    let QListWidget swallow Home for its own list navigation. This is
    why we use an eventFilter rather than a QShortcut.
    """
    from qtpy.QtCore import Qt

    t0, t1 = synthetic_inspector_data.t_start, synthetic_inspector_data.t_end
    main_window._plot.getViewBox().setXRange(t1 - 30, t1, padding=0)
    main_window._dataset_tree.setFocus()  # focus sidebar, not plot

    qtbot.keyClick(main_window._dataset_tree, Qt.Key_Home)

    xmin, _ = _x_range(main_window)
    assert xmin == pytest.approx(t0, abs=0.5), (
        "Home was consumed by QListWidget instead of jumping the plot"
    )


# ---------------------------------------------------------------------
# Pan / zoom (smoke checks — plot-widget-internal QShortcuts)
# ---------------------------------------------------------------------
def test_right_arrow_pans_right(main_window, qtbot):
    """Right arrow shifts the viewport forward by 25 % of current width."""
    from qtpy.QtCore import Qt

    # Zoom into a defined window first so the pan amount is predictable.
    t0 = main_window._data.t_start
    main_window._plot.getViewBox().setXRange(t0, t0 + 100, padding=0)

    xmin_before, xmax_before = _x_range(main_window)
    width = xmax_before - xmin_before

    main_window._plot.setFocus()
    qtbot.keyClick(main_window._plot, Qt.Key_Right)

    xmin_after, xmax_after = _x_range(main_window)
    expected_shift = width * 0.25
    assert (xmin_after - xmin_before) == pytest.approx(expected_shift, abs=0.5)
    assert (xmax_after - xmax_before) == pytest.approx(expected_shift, abs=0.5)


def test_down_arrow_zooms_in(main_window, qtbot):
    """Down arrow shrinks the visible X range."""
    from qtpy.QtCore import Qt

    width_before = _x_range(main_window)[1] - _x_range(main_window)[0]
    main_window._plot.setFocus()
    qtbot.keyClick(main_window._plot, Qt.Key_Down)
    width_after = _x_range(main_window)[1] - _x_range(main_window)[0]
    assert width_after < width_before


# ---------------------------------------------------------------------
# Toolbar parity
# ---------------------------------------------------------------------
def test_toolbar_start_button_triggers_jump_to_start(
    main_window, qtbot, synthetic_inspector_data
):
    """Clicking the toolbar Start button must do the same as Home key."""
    from qtpy.QtWidgets import QToolBar

    t0, t1 = synthetic_inspector_data.t_start, synthetic_inspector_data.t_end
    main_window._plot.getViewBox().setXRange(t1 - 30, t1, padding=0)

    toolbar = main_window.findChild(QToolBar)
    start_action = next(a for a in toolbar.actions() if "Start" in a.text())
    start_action.trigger()

    xmin, _ = _x_range(main_window)
    assert xmin == pytest.approx(t0, abs=0.5)


def test_toolbar_fit_all_button(main_window, synthetic_inspector_data):
    """Fit all must restore the full-recording view after any zoom."""
    from qtpy.QtWidgets import QToolBar

    # Zoom into a tiny window first
    t0 = synthetic_inspector_data.t_start
    main_window._plot.getViewBox().setXRange(t0, t0 + 10, padding=0)

    toolbar = main_window.findChild(QToolBar)
    fit_action = next(a for a in toolbar.actions() if "Fit all" in a.text())
    fit_action.trigger()

    xmin, xmax = _x_range(main_window)
    data = synthetic_inspector_data
    assert (xmax - xmin) == pytest.approx(data.t_end - data.t_start, rel=0.05)
