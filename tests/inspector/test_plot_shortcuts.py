"""Plot keyboard shortcuts + drag-annotation tests.

Covers the MNE-inspired R / 1 / 2 / 3 / A / E shortcuts and the
left-drag-in-annotation-mode flow that pins a new annotation at the
midpoint of the dragged range.

Pattern mirrors ``test_navigation.py``: state assertions on the
ViewBox after ``qtbot.keyClick`` instead of pixel-level regressions.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


# ---------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolated_settings(qapp, tmp_path):
    """Redirect QSettings + annotation persistence into a temp dir."""
    from rrational.inspector import annotation_persistence as ap
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    ap.set_annotation_config_dir(tmp_path / "annotations")
    yield
    ap.set_annotation_config_dir(None)


@pytest.fixture
def main_window(qtbot, synthetic_inspector_data):
    """Inspector with one synthetic dataset loaded into MNE-LAB layout.

    Shortcuts live on the BrowseTab plot, which is only the active /
    focus-receptive view in mnelab layout — same constraint as
    ``test_navigation.py``.
    """
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    win.set_ui_layout("mnelab")
    qtbot.addWidget(win)

    win.load_data(synthetic_inspector_data)

    win.show()
    qtbot.waitExposed(win)
    return win


def _x_range(win):
    return tuple(win._plot.getViewBox().viewRange()[0])


# ---------------------------------------------------------------------
# Zoom-preset shortcuts (R / 1 / 2 / 3)
# ---------------------------------------------------------------------
def test_key_r_resets_view(main_window, qtbot, synthetic_inspector_data):
    """R restores the full-recording view after a tight zoom."""
    from qtpy.QtCore import Qt

    data = synthetic_inspector_data
    # Zoom into a 10-second window first
    main_window._plot.getViewBox().setXRange(data.t_start, data.t_start + 10, padding=0)

    main_window._plot.setFocus()
    qtbot.keyClick(main_window._plot, Qt.Key_R)

    xmin, xmax = _x_range(main_window)
    expected_span = data.t_end - data.t_start
    assert (xmax - xmin) == pytest.approx(expected_span, rel=0.1), (
        "Key_R should zoom out to full recording"
    )


def test_key_3_resets_view(main_window, qtbot, synthetic_inspector_data):
    """3 mirrors R — both jump to the full-data range."""
    from qtpy.QtCore import Qt

    data = synthetic_inspector_data
    main_window._plot.getViewBox().setXRange(data.t_start, data.t_start + 10, padding=0)

    main_window._plot.setFocus()
    qtbot.keyClick(main_window._plot, Qt.Key_3)

    xmin, xmax = _x_range(main_window)
    expected_span = data.t_end - data.t_start
    assert (xmax - xmin) == pytest.approx(expected_span, rel=0.1)


def test_key_1_sets_60s_window(main_window, qtbot, synthetic_inspector_data):
    """1 anchors a 60-second window to the END of the recording."""
    from qtpy.QtCore import Qt

    main_window._plot.setFocus()
    qtbot.keyClick(main_window._plot, Qt.Key_1)

    xmin, xmax = _x_range(main_window)
    assert (xmax - xmin) == pytest.approx(60.0, abs=1.0)
    assert xmax == pytest.approx(synthetic_inspector_data.t_end, abs=1.0)


def test_key_2_sets_600s_window(main_window, qtbot, synthetic_inspector_data):
    """2 shows the last 600 s (10 min) of the recording."""
    from qtpy.QtCore import Qt

    main_window._plot.setFocus()
    qtbot.keyClick(main_window._plot, Qt.Key_2)

    xmin, xmax = _x_range(main_window)
    assert (xmax - xmin) == pytest.approx(600.0, abs=1.0)
    assert xmax == pytest.approx(synthetic_inspector_data.t_end, abs=1.0)


# ---------------------------------------------------------------------
# Mode-toggle shortcuts (A / E)
# ---------------------------------------------------------------------
def test_key_a_toggles_annotation_mode(main_window, qtbot):
    """A flips annotation mode on and off in sync with the panel checkbox."""
    from qtpy.QtCore import Qt

    plot = main_window._plot
    panel = main_window._browse_tab._preprocessing_panel
    # Sanity: with a dataset loaded, the checkbox should be enabled.
    assert panel._toggle_annotation_mode.isEnabled()
    assert not plot.is_annotation_mode()

    plot.setFocus()
    qtbot.keyClick(plot, Qt.Key_A)
    assert plot.is_annotation_mode()
    assert panel._toggle_annotation_mode.isChecked()

    qtbot.keyClick(plot, Qt.Key_A)
    assert not plot.is_annotation_mode()
    assert not panel._toggle_annotation_mode.isChecked()


def test_key_e_toggles_exclusion_mode(main_window, qtbot):
    """E flips exclusion mode on and off in sync with the panel checkbox."""
    from qtpy.QtCore import Qt

    plot = main_window._plot
    panel = main_window._browse_tab._preprocessing_panel
    vb = plot.getViewBox()

    plot.setFocus()
    qtbot.keyClick(plot, Qt.Key_E)
    assert vb._exclusion_mode is True
    assert panel._toggle_exclusion_mode.isChecked()

    qtbot.keyClick(plot, Qt.Key_E)
    assert vb._exclusion_mode is False
    assert not panel._toggle_exclusion_mode.isChecked()


# ---------------------------------------------------------------------
# Drag-annotation
# ---------------------------------------------------------------------
def test_drag_in_annotation_mode_emits_range(main_window, qtbot):
    """A meaningful drag in annotation mode emits ``plot_range_selected``."""
    plot = main_window._plot
    plot.set_annotation_mode(True)

    payloads: list[tuple[float, float]] = []
    plot.plot_range_selected.connect(lambda a, b: payloads.append((a, b)))

    # Drive the ViewBox handler directly with a synthetic MouseDragEvent.
    # qtbot.mouseClick / mouseMove on a QGraphicsView don't reach
    # pyqtgraph's ViewBox.mouseDragEvent path reliably (events are
    # filtered by QGraphicsScene first), so we call the public emitter.
    plot.getViewBox().annotation_drag_finished.emit(100.0, 200.0)

    assert payloads == [(100.0, 200.0)]


def test_drag_in_annotation_mode_creates_annotation(main_window, qtbot):
    """End-to-end: range emit → panel handler → annotation persisted."""
    plot = main_window._plot
    panel = main_window._browse_tab._preprocessing_panel

    # Turn annotation mode on via the canonical checkbox path so the
    # panel's gating in ``_on_plot_range_selected`` accepts the event.
    panel._toggle_annotation_mode.setChecked(True)
    assert plot.is_annotation_mode()

    n_before = len(panel._annotations)
    plot.plot_range_selected.emit(150.0, 250.0)

    assert len(panel._annotations) == n_before + 1
    new_ann = panel._annotations[-1]
    # Range annotations now store onset + duration directly (MNE-style)
    # instead of collapsing to the midpoint — the on-plot marker still
    # pins at the onset, but the dataclass carries the full range.
    assert new_ann.t == pytest.approx(150.0)
    assert new_ann.duration == pytest.approx(100.0)
    assert new_ann.t_end == pytest.approx(250.0)
    assert new_ann.is_range is True
    # Marker rendered onto the plot at the onset.
    assert any(abs(m.annotation_t - 150.0) < 1e-6 for m in plot.annotation_markers())


def test_short_drag_in_annotation_mode_ignored(main_window):
    """Sub-threshold drags (<0.5 s width) don't emit ``plot_range_selected``.

    Keeps the click-to-annotate path clean — a near-still click that
    Qt happens to dispatch as a drag should fall through to the
    existing ``plot_clicked`` handler.
    """
    plot = main_window._plot
    plot.set_annotation_mode(True)

    payloads: list = []
    plot.plot_range_selected.connect(lambda *a: payloads.append(a))

    # Width = 0.1 s, below MIN_ANNOTATION_DRAG_WIDTH_S = 0.5 s.
    plot.getViewBox().annotation_drag_finished.emit(100.0, 100.1)

    assert payloads == []


def test_drag_in_exclusion_mode_does_not_create_annotation(main_window):
    """Exclusion mode takes precedence — drag routes to a zone, not a note."""
    plot = main_window._plot
    panel = main_window._browse_tab._preprocessing_panel
    vb = plot.getViewBox()

    # Both modes on simultaneously: exclusion wins (documented in the
    # RRViewBox dispatcher).
    panel._toggle_annotation_mode.setChecked(True)
    panel._toggle_exclusion_mode.setChecked(True)

    n_ann_before = len(panel._annotations)
    n_zones_before = len(plot._exclusion_zones)

    # Simulate a finished left drag in dual-mode. The ViewBox flag is
    # what mouseDragEvent reads, so toggling the public API is enough.
    # We invoke the real dispatcher via the ViewBox signal path used
    # by the production code.
    vb.exclusion_drag_finished.emit(100.0, 200.0)

    assert len(panel._annotations) == n_ann_before
    assert len(plot._exclusion_zones) == n_zones_before + 1


# ---------------------------------------------------------------------
# Status messages bubble up
# ---------------------------------------------------------------------
def test_reset_view_pushes_status_message(main_window, qtbot):
    """R / Key_3 surface a transient status message via the bridge signal."""
    from qtpy.QtCore import Qt

    plot = main_window._plot
    plot.setFocus()
    qtbot.keyClick(plot, Qt.Key_R)

    assert "full recording" in main_window.statusBar().currentMessage().lower()
