"""Tests for the Pareto-style drop-log widget (Cluster B8)."""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")
pg = pytest.importorskip("pyqtgraph")

from rrational.inspector.plots.drop_log import build_drop_log_widget


def _plot_items(widget: pg.PlotWidget) -> list:
    """Return all items registered on the widget's PlotItem."""
    return widget.getPlotItem().items


def test_empty_counts_returns_placeholder_widget(qtbot):
    """``build_drop_log_widget({})`` must not crash and must show a hint."""
    w = build_drop_log_widget({})
    qtbot.addWidget(w)
    text_items = [it for it in _plot_items(w) if isinstance(it, pg.TextItem)]
    # Placeholder text item is the "No drops recorded." hint.
    assert any("No drops" in it.toPlainText() for it in text_items)


def test_single_category_renders_one_bar(qtbot):
    """A single drop-reason produces exactly one BarGraphItem."""
    w = build_drop_log_widget({"too_short": 5})
    qtbot.addWidget(w)
    bars = [it for it in _plot_items(w) if isinstance(it, pg.BarGraphItem)]
    assert len(bars) == 1


def test_multiple_reasons_sorted_descending(qtbot):
    """Bars must be sorted by count descending (Pareto convention)."""
    counts = {"low_freq": 3, "ectopic": 12, "movement": 7}
    w = build_drop_log_widget(counts)
    qtbot.addWidget(w)
    bars = [it for it in _plot_items(w) if isinstance(it, pg.BarGraphItem)]
    assert len(bars) == 1  # one BarGraphItem holds all bars
    widths = list(bars[0].opts["width"])
    # Sorted descending: ectopic(12) > movement(7) > low_freq(3)
    assert widths == [12.0, 7.0, 3.0]


def test_cumulative_line_overlay_present(qtbot):
    """The cumulative-percent overlay must render as a PlotDataItem."""
    w = build_drop_log_widget({"a": 2, "b": 1})
    qtbot.addWidget(w)
    curves = [it for it in _plot_items(w) if isinstance(it, pg.PlotDataItem)]
    assert len(curves) == 1
    # Last y is the last reason index; last x equals max_count (100% point).
    x, _ = curves[0].getData()
    assert x[-1] == pytest.approx(2.0, rel=1e-6)


def test_y_axis_uses_reason_labels(qtbot):
    """The left axis ticks must carry the drop-reason strings."""
    counts = {"ectopic": 5, "low_snr": 2}
    w = build_drop_log_widget(counts)
    qtbot.addWidget(w)
    ticks = w.getAxis("left")._tickLevels
    # _tickLevels is a list of (pos, label) tuple lists; flatten + check labels.
    labels = [label for level in (ticks or []) for _pos, label in level]
    assert "ectopic" in labels
    assert "low_snr" in labels


def test_widget_minimum_height_scales_with_reason_count(qtbot):
    """Each row adds ~28 px so labels stay readable for long lists."""
    w_few = build_drop_log_widget({"a": 1})
    w_many = build_drop_log_widget({k: i + 1 for i, k in enumerate("abcdef")})
    qtbot.addWidget(w_few)
    qtbot.addWidget(w_many)
    assert w_many.minimumHeight() > w_few.minimumHeight()
