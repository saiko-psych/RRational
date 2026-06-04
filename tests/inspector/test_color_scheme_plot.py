"""Tests that ``RRPlotWidget.set_color_scheme`` actually updates pens.

Each test instantiates a real ``RRPlotWidget`` via ``qtbot`` and pokes
``set_color_scheme(scheme)`` with deliberately distinct colours, then
asserts the live pen / brush colours reflect them.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture
def plot_widget(qtbot):
    from rrational.inspector.plot_widget import RRPlotWidget

    w = RRPlotWidget()
    qtbot.addWidget(w)
    return w


def _color_eq(qcolor, hex_str: str) -> bool:
    from qtpy.QtGui import QColor

    return qcolor.name(QColor.HexRgb).lower() == hex_str.lower()


def test_set_color_scheme_changes_rr_line_pen(plot_widget):
    from rrational.gui.color_scheme import ColorScheme

    scheme = ColorScheme(rr_line="#ff00aa")
    plot_widget.set_color_scheme(scheme)
    pen = plot_widget._curve.opts["pen"]
    # PyQtGraph stores .opts["pen"] as a QPen
    assert _color_eq(pen.color(), "#ff00aa")


def test_set_color_scheme_changes_artifact_color(plot_widget):
    from rrational.gui.color_scheme import ColorScheme

    scheme = ColorScheme(artifact="#00ffaa")
    plot_widget.set_color_scheme(scheme)
    # ArtifactOverlay.apply_color updates pen + brush.
    pen = plot_widget._artifact_overlay.opts["pen"]
    brush = plot_widget._artifact_overlay.opts["brush"]
    assert _color_eq(pen.color(), "#00ffaa")
    assert _color_eq(brush.color(), "#00ffaa")


def test_set_color_scheme_repaints_existing_sections(plot_widget):
    from rrational.gui.color_scheme import ColorScheme
    from rrational.inspector.data_loader import SectionMeta

    meta = SectionMeta(
        name="rest_pre", t_start=1_700_000_000.0, t_end=1_700_000_200.0, beat_count=100
    )
    plot_widget.add_section_region(meta)
    new_scheme = ColorScheme(section_border="#deadbe")
    plot_widget.set_color_scheme(new_scheme)
    region = plot_widget._section_regions[0]
    # Pen colour reflects the new border; alpha set by apply_colors.
    pen_color = region.lines[0].pen.color()
    assert pen_color.red() == 0xDE
    assert pen_color.green() == 0xAD
    assert pen_color.blue() == 0xBE


def test_set_color_scheme_repaints_existing_event_markers(plot_widget):
    from rrational.gui.color_scheme import ColorScheme
    from rrational.inspector.data_loader import EventMeta

    plot_widget.add_event_marker(EventMeta(label="start", t=1_700_000_000.0))
    new_scheme = ColorScheme(event_marker="#abcdef")
    plot_widget.set_color_scheme(new_scheme)
    marker = plot_widget._event_markers[0]
    pen_color = marker.pen.color()
    assert pen_color.red() == 0xAB
    assert pen_color.green() == 0xCD
    assert pen_color.blue() == 0xEF


def test_set_color_scheme_is_noop_when_no_overlays(plot_widget):
    """Calling on a fresh plot with no sections/events/artifacts must not
    raise — covers the "items not present" branch."""
    from rrational.gui.color_scheme import ColorScheme

    plot_widget.set_color_scheme(ColorScheme())  # no raise
    assert plot_widget._section_regions == []
    assert plot_widget._event_markers == []


def test_set_color_scheme_after_real_data(plot_widget):
    """Verify pen update survives a ``set_data`` cycle."""
    from rrational.gui.color_scheme import ColorScheme
    from rrational.inspector.data_loader import InspectorData

    t = np.arange(100, dtype=np.float64) + 1_700_000_000.0
    v = 800 + 30 * np.sin(np.linspace(0, 6, 100))
    data = InspectorData(t=t, v=v, sections=[], events=[])
    plot_widget.set_data(data)
    plot_widget.set_color_scheme(ColorScheme(rr_line="#112233"))
    assert _color_eq(plot_widget._curve.opts["pen"].color(), "#112233")
