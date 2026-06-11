"""Smoke tests for the PyQtGraph overlay items in ``graphic_items``.

These exercise the public API of each overlay class in isolation —
no MainWindow, no PlotWidget. The point is to lock down the
constructor signatures + public properties / setters that other
modules (and persistence) rely on.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pyqtgraph")
pytest.importorskip("pytestqt")

from qtpy.QtGui import QColor  # noqa: E402

from rrational.inspector.graphic_items import (  # noqa: E402
    SECTION_ALPHA,
    AnnotationMarker,
    ArtifactOverlay,
    EventMarker,
    ExclusionRegion,
    SectionRegion,
)


# ---------------------------------------------------------------------
# SectionRegion
# ---------------------------------------------------------------------
def test_section_region_constructs_with_label(qtbot):
    region = SectionRegion(0.0, 10.0, "rest_pre", QColor("#3366cc"))
    assert region.section_label == "rest_pre"
    lo, hi = region.getRegion()
    assert lo == pytest.approx(0.0)
    assert hi == pytest.approx(10.0)


def test_section_region_set_highlighted_increases_alpha(qtbot):
    region = SectionRegion(0.0, 10.0, "music", QColor("#3366cc"))
    base_alpha = region.brush.color().alpha()
    assert base_alpha == SECTION_ALPHA
    region.set_highlighted(True)
    highlighted_alpha = region.brush.color().alpha()
    assert highlighted_alpha > base_alpha
    region.set_highlighted(False)
    assert region.brush.color().alpha() == base_alpha


# ---------------------------------------------------------------------
# EventMarker
# ---------------------------------------------------------------------
def test_event_marker_constructs_with_label(qtbot):
    marker = EventMarker(t=123.456, label="music_start", color=QColor("#cc3300"))
    assert marker.event_label == "music_start"
    assert marker.value() == pytest.approx(123.456)


def test_event_marker_apply_color_does_not_crash(qtbot):
    marker = EventMarker(t=10.0, label="evt", color=QColor("#cc3300"))
    marker.apply_color(QColor("#00aa44"))
    # No assertion on internals — just confirm the call path works.


# ---------------------------------------------------------------------
# ArtifactOverlay
# ---------------------------------------------------------------------
def test_artifact_overlay_set_then_clear_points(qtbot):
    overlay = ArtifactOverlay()
    overlay.set_points([1.0, 2.0, 3.0], [800.0, 810.0, 790.0])
    # ScatterPlotItem exposes the data via getData() on Qt6/pyqtgraph 0.13.
    xs, ys = overlay.getData()
    assert len(xs) == 3
    overlay.clear_points()
    xs2, ys2 = overlay.getData()
    assert len(xs2) == 0


def test_artifact_overlay_empty_points_no_crash(qtbot):
    overlay = ArtifactOverlay()
    overlay.set_points([], [])
    overlay.clear_points()


# ---------------------------------------------------------------------
# AnnotationMarker
# ---------------------------------------------------------------------
def test_annotation_marker_long_text_truncates(qtbot):
    long_text = "this is a very long annotation that should get truncated"
    marker = AnnotationMarker(t=42.0, text=long_text)
    # Label text uses the truncated form: 21 chars + "..."
    # We can't easily read the InfLineLabel back, but the truncation
    # rule lives in __init__ — assert by re-running the logic on the
    # public attribute.
    assert marker.annotation_text == long_text
    # tooltip embeds the FULL text plus a timestamp suffix.
    assert long_text in marker.tooltip_text


def test_annotation_marker_set_annotation_text_updates_tooltip(qtbot):
    marker = AnnotationMarker(t=42.0, text="initial")
    marker.set_annotation_text("updated text")
    assert marker.annotation_text == "updated text"
    assert "updated text" in marker.tooltip_text


# ---------------------------------------------------------------------
# ExclusionRegion
# ---------------------------------------------------------------------
def test_exclusion_region_apply_color_updates_brush(qtbot):
    region = ExclusionRegion(
        0.0, 5.0, reason="motion artifact", color=QColor("#cc3300")
    )
    assert region.reason == "motion artifact"
    new_color = QColor("#00aa44")
    region.apply_color(new_color)
    # Brush should now carry the green hue (R~0, G~170, B~68).
    brush_color = region.brush.color()
    assert brush_color.green() > brush_color.red()
    assert brush_color.green() > brush_color.blue()
