"""Scrollable RR-tachogram plot widget built on PyQtGraph.

The widget renders a single 1D signal (RR intervals in ms over absolute
timestamps) and supports:

- Native mouse drag-to-pan + scroll-zoom (PyQtGraph's default ViewBox).
- Keyboard navigation via QShortcut (focus-independent — works even when
  the section sidebar has the keyboard focus):
    - Left  / Right       — pan 25 % of the visible window
    - Up    / Down        — zoom out / in
    - Home  / End         — jump to first / last beat
- ``setClipToView`` + automatic peak downsampling so 50k+ beats stay
  responsive at full visible-range.

QShortcut is used instead of overriding ``keyPressEvent`` because
PyQtGraph's PlotWidget forwards key events to its QGraphicsScene before
the widget's own override sees Home/End — the events were getting eaten
by QGraphicsView's scroll-area behaviour.

This file is intentionally minimal for the Phase-1 spike. Section
overlays, event lines, and artifact editing land in later phases.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pyqtgraph as pg
from qtpy.QtCore import Qt
from qtpy.QtGui import QKeySequence, QShortcut

PAN_FRACTION = 0.25  # fraction of the visible window per Left/Right press
ZOOM_FACTOR = 1.25  # multiplicative zoom per Up/Down press
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

        # Single persistent PlotDataItem — never recreated, just .setData()'d.
        # Avoids the QGraphicsLayout memory leaks PyQtGraph has on PySide6 ≥ 6.5.
        # Speed knobs:
        #   - clipToView: only paint visible X-range
        #   - autoDownsample/peak: keep min/max so spikes survive decimation
        #   - skipFiniteCheck: we filter NaN/Inf at load time
        self._curve = pg.PlotDataItem(
            pen=pg.mkPen(LINE_COLOR, width=1),
            connect="finite",
            skipFiniteCheck=True,
            clipToView=True,
            autoDownsample=True,
            downsampleMethod="peak",
        )
        self.addItem(self._curve)

        # Tachogram values are always positive — clamp the lower Y bound so
        # accidental vertical pan can't show negative ms.
        self.getViewBox().setLimits(yMin=0)

        # Data cache — used by the QShortcut handlers below.
        self._times: np.ndarray | None = None
        self._values: np.ndarray | None = None

        # Focus is required for mouse-wheel zoom to feel responsive even
        # before the user has clicked into the plot.
        self.setFocusPolicy(Qt.StrongFocus)

        # ------------------------------------------------------------------
        # Keyboard shortcuts for arrow keys live on the plot widget itself
        # because the plot has to be focused (or the window active) for
        # them to feel responsive. Home/End are registered separately at
        # MainWindow level with ApplicationShortcut context — QGraphicsView
        # (PlotWidget's parent class) eats Home/End for its own scroll-area
        # behaviour, so a shortcut hung off this widget never fires for
        # those two keys.
        # ------------------------------------------------------------------
        self._make_shortcut(QKeySequence(Qt.Key_Left), self.pan_left)
        self._make_shortcut(QKeySequence(Qt.Key_Right), self.pan_right)
        self._make_shortcut(QKeySequence(Qt.Key_Up), self.zoom_out)
        self._make_shortcut(QKeySequence(Qt.Key_Down), self.zoom_in)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _make_shortcut(self, key_seq: QKeySequence, slot) -> QShortcut:
        sc = QShortcut(key_seq, self)
        # WindowShortcut fires when ANY widget in this widget's top-level
        # window has the focus — exactly what we want for a viewer pane.
        sc.setContext(Qt.WindowShortcut)
        sc.activated.connect(slot)
        return sc

    def _x_window(self) -> tuple[float, float, float]:
        x_lo, x_hi = self.getViewBox().viewRange()[0]
        return x_lo, x_hi, x_hi - x_lo

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def set_data(
        self,
        timestamps: list[datetime] | np.ndarray,
        rr_ms: list[float] | np.ndarray,
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

        # Comfortable starting view: first 60 seconds on long recordings,
        # the whole signal otherwise.
        if t[-1] - t[0] > 60:
            self.setXRange(t[0], t[0] + 60, padding=0)
        else:
            self.setXRange(t[0], t[-1], padding=0)
        self.enableAutoRange(axis="y")

    # ------------------------------------------------------------------
    # Shortcut handlers — public so MainWindow can wire its own
    # ApplicationShortcut-context QShortcuts to them (needed for Home/End,
    # which QGraphicsView eats if hung off this widget directly).
    # ------------------------------------------------------------------
    def pan_left(self) -> None:
        x_lo, x_hi, width = self._x_window()
        shift = width * PAN_FRACTION
        self.getViewBox().setXRange(x_lo - shift, x_hi - shift, padding=0)

    def pan_right(self) -> None:
        x_lo, x_hi, width = self._x_window()
        shift = width * PAN_FRACTION
        self.getViewBox().setXRange(x_lo + shift, x_hi + shift, padding=0)

    def zoom_out(self) -> None:
        x_lo, x_hi, width = self._x_window()
        extra = width * (ZOOM_FACTOR - 1) / 2
        self.getViewBox().setXRange(x_lo - extra, x_hi + extra, padding=0)

    def zoom_in(self) -> None:
        x_lo, x_hi, width = self._x_window()
        shrink = width * (1 - 1 / ZOOM_FACTOR) / 2
        self.getViewBox().setXRange(x_lo + shrink, x_hi - shrink, padding=0)

    def jump_start(self) -> None:
        """Jump viewport to start of signal.

        Always shows a fixed 60 s window (not the current zoom width) — if
        the user is fully zoomed out, ``setXRange(t[0], t[0] + width)``
        with width == total duration would be a no-op, which makes the
        feature feel broken.
        """
        if self._times is None:
            return
        t = self._times
        end = min(t[0] + 60, t[-1])
        self.getViewBox().setXRange(t[0], end, padding=0)

    def jump_end(self) -> None:
        """Jump viewport to end of signal (last 60 s window)."""
        if self._times is None:
            return
        t = self._times
        start = max(t[-1] - 60, t[0])
        self.getViewBox().setXRange(start, t[-1], padding=0)
