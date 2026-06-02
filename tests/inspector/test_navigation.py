"""Keyboard- and toolbar-driven navigation tests for the inspector.

These tests exist primarily as a regression net for the Home/End bug we
hit in development: the original ``jump_start``/``jump_end`` preserved
the current viewport width, which made the keys a no-op whenever the
user was already showing the whole signal. The test below would have
caught that — it asserts the viewport size, not just position.

Pattern borrowed from mne-qt-browser's ``tests/test_pg_specific.py``:
state assertions on the viewbox after a ``qtbot.keyClick`` rather than
pixel-level screenshot regression.
"""

from __future__ import annotations

import pytest

# pytest-qt's auto-use ``qapp`` fixture creates one QApplication per
# session, so we just need to import the widgets lazily.
pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture
def main_window(qtbot, synthetic_section):
    """Construct a MainWindow with one synthetic section pre-loaded."""
    from qtpy.QtCore import Qt
    from qtpy.QtWidgets import QListWidgetItem

    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    qtbot.addWidget(win)  # ensures cleanup even if the test crashes

    # Inject the synthetic section directly into the in-memory store —
    # avoids needing a real .rrational file on disk for the keyboard test.
    timestamps, rr_ms = synthetic_section
    win._sections = {"test_section": (timestamps, rr_ms)}
    item = QListWidgetItem("test_section")
    item.setData(Qt.UserRole, "test_section")
    win._section_list.addItem(item)
    win._on_section_selected(item)  # triggers set_data + sets initial view

    win.show()
    qtbot.waitExposed(win)
    return win


def _x_range(win):
    """Convenience: return (xmin, xmax) of the plot's visible X range."""
    return tuple(win._plot.getViewBox().viewRange()[0])


# ---------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------
def test_initial_view_is_first_60s(main_window, synthetic_section):
    """``set_data`` should auto-zoom to first 60 s on long signals.

    Anchors the rest of the suite: tests below assume we don't start
    fully zoomed out (which would mask Home/End bugs).
    """
    timestamps, _ = synthetic_section
    t0 = timestamps[0].timestamp()
    xmin, xmax = _x_range(main_window)
    assert xmin == pytest.approx(t0, abs=0.5)
    assert (xmax - xmin) == pytest.approx(60, abs=1.0)


# ---------------------------------------------------------------------
# Home / End — the original bug
# ---------------------------------------------------------------------
def test_end_key_jumps_to_last_60s(main_window, qtbot, synthetic_section):
    """End must move the viewport to the LAST 60 s of the signal.

    Regression: the original code preserved current width, so pressing
    End from the default 60 s view *did* move correctly; but when the
    user had zoomed out to the full 300 s, End became a no-op. We
    therefore test from the full-zoom state to lock in the new
    fixed-60-s-window semantics.
    """
    from qtpy.QtCore import Qt

    # Zoom out to full signal first — this is the state where the old
    # bug manifested.
    timestamps, _ = synthetic_section
    t0, t1 = timestamps[0].timestamp(), timestamps[-1].timestamp()
    main_window._plot.getViewBox().setXRange(t0, t1, padding=0)

    qtbot.keyClick(main_window, Qt.Key_End)

    xmin, xmax = _x_range(main_window)
    assert xmax == pytest.approx(t1, abs=0.5)
    # Window must be ~60 s — NOT the previous full-signal width.
    assert (xmax - xmin) == pytest.approx(60, abs=1.0)


def test_home_key_jumps_to_first_60s(main_window, qtbot, synthetic_section):
    """Home must jump back to first 60 s after the user has panned away."""
    from qtpy.QtCore import Qt

    timestamps, _ = synthetic_section
    t0, t1 = timestamps[0].timestamp(), timestamps[-1].timestamp()
    # Pan to the end first
    main_window._plot.getViewBox().setXRange(t1 - 30, t1, padding=0)

    qtbot.keyClick(main_window, Qt.Key_Home)

    xmin, xmax = _x_range(main_window)
    assert xmin == pytest.approx(t0, abs=0.5)
    assert (xmax - xmin) == pytest.approx(60, abs=1.0)


def test_home_key_fires_even_when_sidebar_has_focus(
    main_window, qtbot, synthetic_section
):
    """The global eventFilter must intercept Home before QListWidget eats it.

    Without the QApplication-level filter, focusing the sidebar would
    let QListWidget swallow Home for its own list navigation. This is
    why we use an eventFilter rather than a QShortcut.
    """
    from qtpy.QtCore import Qt

    timestamps, _ = synthetic_section
    t0, t1 = timestamps[0].timestamp(), timestamps[-1].timestamp()
    main_window._plot.getViewBox().setXRange(t1 - 30, t1, padding=0)
    main_window._section_list.setFocus()  # focus sidebar, not plot

    qtbot.keyClick(main_window._section_list, Qt.Key_Home)

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
# Toolbar buttons trigger the same navigation API
# ---------------------------------------------------------------------
def test_toolbar_start_button_triggers_jump_to_start(
    main_window, qtbot, synthetic_section
):
    """Clicking the toolbar Start button must do the same as Home key."""
    from qtpy.QtWidgets import QToolBar

    timestamps, _ = synthetic_section
    t0, t1 = timestamps[0].timestamp(), timestamps[-1].timestamp()
    main_window._plot.getViewBox().setXRange(t1 - 30, t1, padding=0)

    toolbar = main_window.findChild(QToolBar)
    start_action = next(a for a in toolbar.actions() if "Start" in a.text())
    start_action.trigger()

    xmin, _ = _x_range(main_window)
    assert xmin == pytest.approx(t0, abs=0.5)
