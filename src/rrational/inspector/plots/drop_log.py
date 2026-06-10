"""Pareto-style drop-reason bar chart (Cluster B8).

Mirrors ``mne.Epochs.plot_drop_log()``: sort drop reasons by count
descending, render as a horizontal bar so long reason labels stay
readable, and overlay the cumulative-percentage line so the user
can see which 2-3 reasons drive most of the rejections.

Input shape is the simplest one that round-trips through the
preprocessing layer: a ``{reason: count}`` dict. Callers that have
indexed reasons (one per dropped beat) should pre-aggregate via
``collections.Counter`` before calling.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pyqtgraph as pg
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor


# Colour matches the inspector's "muted exclusion" warm-gray family so
# the drop-log reads as "rejections" rather than "alerts" — alarm-red
# bars overstate severity for routine preprocessing.
_BAR_COLOR = QColor("#7d8390")
_CUMULATIVE_COLOR = QColor("#e8a13a")


def build_drop_log_widget(counts: Mapping[str, int]) -> pg.PlotWidget:
    """Return a configured PlotWidget rendering the drop-log Pareto.

    The widget is a standalone QWidget; embed it via ``layout.addWidget``
    or pop it in its own QDialog. Bars are sorted by count descending,
    and the cumulative-percent line (right axis) lets the user spot
    "80% from top 2 reasons" patterns at a glance.

    Empty ``counts`` produces a widget with a single placeholder label
    so the caller does not need to branch on emptiness.
    """
    widget = pg.PlotWidget()
    # Background defers to the global pyqtgraph config (dark/light theme).
    widget.showGrid(x=True, y=False, alpha=0.3)
    if not counts:
        # Placeholder: empty drop-log is the happy path — show a label
        # rather than a degenerate empty axes plot.
        widget.addItem(
            pg.TextItem(
                "No drops recorded.",
                color=QColor("#555"),
                anchor=(0.5, 0.5),
            )
        )
        return widget

    # Sort by count descending — Pareto convention.
    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    reasons = [k for k, _ in items]
    values = np.asarray([v for _, v in items], dtype=float)
    total = float(values.sum()) or 1.0
    cumulative_pct = (np.cumsum(values) / total) * 100.0

    # Horizontal bar: x = count, y = reason index. Bottom axis ticks
    # use the reason label.
    bar = pg.BarGraphItem(
        x0=0,
        y=np.arange(len(reasons)),
        height=0.6,
        width=values,
        brush=_BAR_COLOR,
        pen=pg.mkPen(_BAR_COLOR.darker(140), width=1),
    )
    widget.addItem(bar)

    # Cumulative-percent overlay as a stepped line on a secondary x-axis.
    # PyQtGraph does not give us a free second x-axis the way matplotlib
    # does, so we map the percent values onto the bar-width range via
    # scaling and annotate the labels manually.
    max_count = float(values.max())
    pct_line_x = (cumulative_pct / 100.0) * max_count
    pct_curve = pg.PlotDataItem(
        x=pct_line_x,
        y=np.arange(len(reasons)),
        pen=pg.mkPen(_CUMULATIVE_COLOR, width=2, style=Qt.DashLine),
        symbol="o",
        symbolBrush=_CUMULATIVE_COLOR,
        symbolSize=6,
    )
    widget.addItem(pct_curve)

    # Y-axis: reason labels (one tick per row).
    y_axis = widget.getAxis("left")
    y_axis.setTicks([list(zip(range(len(reasons)), reasons))])

    # X-axis: counts, with a hint about the cumulative-percent overlay.
    widget.getAxis("bottom").setLabel("Dropped beats (count)")
    widget.setTitle("Drop reasons (Pareto) — dashed line: cumulative % of total drops")
    # Invert so the largest reason sits at the TOP of the chart.
    widget.getViewBox().invertY(True)
    widget.setMinimumHeight(40 + 28 * len(reasons))
    return widget
