"""Scrollable RR-tachogram plot widget built on PyQtGraph.

The widget renders a single 1D signal (RR intervals in ms over absolute
timestamps) and supports:

- Native mouse drag-to-pan + scroll-zoom (PyQtGraph's default ViewBox).
- Keyboard navigation: Left / Right pan 25% of the visible window;
  Up / Down zoom out / in; Home jumps to the start, End to the latest.
- ``setClipToView`` + automatic peak downsampling so 50k+ beats stay
  responsive even at full visible-range.

This file is intentionally minimal for the Phase-1 spike. Section
overlays, event lines, and artifact editing land in later phases.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pyqtgraph as pg
from qtpy.QtCore import Qt
from qtpy.QtGui import QKeyEvent

PAN_FRACTION = 0.25  # fraction of the visible window per Left/Right key press
ZOOM_FACTOR = 1.25  # multiplicative zoom per Up/Down key press
LINE_COLOR = "#2E86AB"  # matches the Scientific theme accent in color_scheme.py


class RRPlotWidget(pg.PlotWidget):
    """A pan/zoom-able plot of one RR signal vs absolute time."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # X-axis is a DateAxis so the user sees real wall-clock time, not
        # epoch milliseconds. PyQtGraph's built-in DateAxisItem handles tick
        # formatting at every zoom level.
        date_axis = pg.DateAxisItem(orientation="bottom")
        self.setAxisItems({"bottom": date_axis})

        self.setLabel("left", "RR interval", units="ms")
        self.setLabel("bottom", "Time")
        self.showGrid(x=True, y=True, alpha=0.25)

        # The PlotDataItem holds the actual line. Configure for speed:
        # - setClipToView: only paint what's visible
        # - setDownsampling auto + peak: keep min/max so spikes don't get lost
        # - setSkipFiniteCheck: trust our data has no NaN/Inf (we filter on load)
        self._curve = pg.PlotDataItem(
            pen=pg.mkPen(LINE_COLOR, width=1),
            connect="finite",
            skipFiniteCheck=True,
            clipToView=True,
            autoDownsample=True,
            downsampleMethod="peak",
        )
        self.addItem(self._curve)

        # Tachogram values are always positive; lock the Y origin so panning
        # vertically (which Plotly users sometimes do by accident) doesn't go
        # negative. We still allow Y-axis zoom via wheel.
        self.getViewBox().setLimits(yMin=0)

        # Cache for keyboard pan/zoom — Plotly defaults to date strings; we
        # store the raw timestamp window in seconds-since-epoch as numpy.
        self._times: np.ndarray | None = None
        self._values: np.ndarray | None = None

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def set_data(
        self, timestamps: list[datetime] | np.ndarray, rr_ms: list[float] | np.ndarray
    ) -> None:
        """Replace the displayed signal.

        ``timestamps`` must be datetime objects or seconds-since-epoch
        floats; ``rr_ms`` is the matched RR-interval value in ms.
        """
        if len(timestamps) == 0:
            self._curve.clear()
            self._times = None
            self._values = None
            return

        if isinstance(timestamps[0], datetime):
            t = np.array([ts.timestamp() for ts in timestamps], dtype=np.float64)
        else:
            t = np.asarray(timestamps, dtype=np.float64)
        v = np.asarray(rr_ms, dtype=np.float64)

        self._times = t
        self._values = v
        self._curve.setData(t, v)

        # Auto-range Y to the data, but X to the first 60 seconds for a
        # comfortable starting view on long recordings.
        if t[-1] - t[0] > 60:
            self.setXRange(t[0], t[0] + 60, padding=0)
        else:
            self.setXRange(t[0], t[-1], padding=0)
        self.enableAutoRange(axis="y")

    # ------------------------------------------------------------------
    # Keyboard navigation
    # ------------------------------------------------------------------
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Pan with Left/Right, zoom with Up/Down, jump with Home/End."""
        key = event.key()
        vb = self.getViewBox()
        x_lo, x_hi = vb.viewRange()[0]
        width = x_hi - x_lo

        if key == Qt.Key_Left:
            shift = width * PAN_FRACTION
            vb.setXRange(x_lo - shift, x_hi - shift, padding=0)
        elif key == Qt.Key_Right:
            shift = width * PAN_FRACTION
            vb.setXRange(x_lo + shift, x_hi + shift, padding=0)
        elif key == Qt.Key_Up:
            # zoom OUT (wider window)
            extra = width * (ZOOM_FACTOR - 1) / 2
            vb.setXRange(x_lo - extra, x_hi + extra, padding=0)
        elif key == Qt.Key_Down:
            # zoom IN (narrower window)
            shrink = width * (1 - 1 / ZOOM_FACTOR) / 2
            vb.setXRange(x_lo + shrink, x_hi - shrink, padding=0)
        elif key == Qt.Key_Home and self._times is not None:
            t = self._times
            vb.setXRange(t[0], min(t[0] + width, t[-1]), padding=0)
        elif key == Qt.Key_End and self._times is not None:
            t = self._times
            vb.setXRange(max(t[-1] - width, t[0]), t[-1], padding=0)
        else:
            super().keyPressEvent(event)
            return
        event.accept()
