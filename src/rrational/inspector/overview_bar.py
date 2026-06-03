"""Mini-map of the full recording, with a draggable viewport indicator.

Sits above the main plot. The user always sees the WHOLE timeline at
a compact scale, with a translucent green rectangle marking the slice
that's currently zoomed-in on the main plot below. Dragging the rectangle
pans the main plot; main-plot pan/zoom updates the rectangle back.

Pattern borrowed from mne-qt-browser's ``OverviewBar`` (``_widgets.py``):
- imperative updates via direct method calls — no Qt-Signals between
  overview and main plot, to keep the feedback graph easy to reason about
- ``blockSignals`` brackets the cross-update so the bidirectional sync
  doesn't loop indefinitely
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from qtpy.QtGui import QColor

if TYPE_CHECKING:
    from rrational.inspector.plot_widget import RRPlotWidget

# Visual constants — tuned so the bar reads as "subordinate to main plot"
# without disappearing. Matches mne-qt-browser's overview-bar fade level.
_BAR_HEIGHT = 80
_LINE_COLOR = "#7FB3D5"  # paler than main plot, so eyes land on main first
_VIEWPORT_FILL = (46, 134, 171, 60)
_VIEWPORT_BORDER = (46, 134, 171, 200)


class OverviewBar(pg.PlotWidget):
    """Compact mini-plot of the full timeline with a viewport indicator."""

    def __init__(self, parent=None) -> None:
        # No DateAxisItem on the overview — labels at this scale just
        # add clutter; the main plot's bottom axis is already the
        # canonical time reference.
        super().__init__(parent)
        self.setMaximumHeight(_BAR_HEIGHT)
        self.setMinimumHeight(_BAR_HEIGHT)

        # The overview itself is non-interactive (no drag-to-pan, no
        # scroll-zoom). Only the LinearRegionItem inside it accepts
        # mouse input.
        self.setMouseEnabled(x=False, y=False)
        self.setMenuEnabled(False)
        self.hideAxis("left")
        self.hideAxis("bottom")
        self.setBackground("w")

        self._curve = pg.PlotDataItem(
            pen=pg.mkPen(_LINE_COLOR, width=1),
            connect="finite",
            clipToView=True,
            autoDownsample=True,
            downsampleMethod="peak",
        )
        self.addItem(self._curve)

        # The viewport indicator. Movable=True lets the user drag the
        # whole rectangle along the X axis; the edges are also
        # individually draggable to widen/narrow the main view.
        self._viewport_region = pg.LinearRegionItem(
            values=(0, 1),
            orientation="vertical",
            brush=QColor(*_VIEWPORT_FILL),
            pen=pg.mkPen(QColor(*_VIEWPORT_BORDER), width=2),
            movable=True,
        )
        # Sit ON TOP so the user can grab it even where the curve passes
        # underneath.
        self._viewport_region.setZValue(10)
        self.addItem(self._viewport_region)

        self._viewport_region.sigRegionChanged.connect(self._on_overview_region_dragged)

        # Wired up by ``link_to`` once the main plot exists.
        self._main_plot: "RRPlotWidget" | None = None
        # Re-entrancy guard for the bidirectional sync (see notes above).
        self._syncing = False

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------
    def link_to(self, plot: "RRPlotWidget") -> None:
        """Bind this overview bar to a main plot for bidirectional sync."""
        self._main_plot = plot
        plot.getViewBox().sigRangeChanged.connect(self._on_main_range_changed)

    # ------------------------------------------------------------------
    # Data + state
    # ------------------------------------------------------------------
    def set_data(self, t: np.ndarray, v: np.ndarray) -> None:
        """Replace the displayed signal. Fits the full range immediately."""
        if len(t) == 0:
            self._curve.clear()
            return
        self._curve.setData(t, v)
        finite_t = t[np.isfinite(t)]
        if len(finite_t) >= 2:
            self.setXRange(float(finite_t[0]), float(finite_t[-1]), padding=0)
        self.enableAutoRange(axis="y")

    def clear_data(self) -> None:
        self._curve.clear()

    # ------------------------------------------------------------------
    # Sync handlers
    # ------------------------------------------------------------------
    def _on_main_range_changed(self, _viewbox, ranges) -> None:
        """Main plot moved → bring the viewport rectangle along."""
        if self._syncing:
            return
        x0, x1 = ranges[0]
        self._syncing = True
        try:
            self._viewport_region.setRegion((x0, x1))
        finally:
            self._syncing = False

    def _on_overview_region_dragged(self) -> None:
        """User dragged the rectangle → pan/zoom the main plot to match."""
        if self._main_plot is None or self._syncing:
            return
        x0, x1 = self._viewport_region.getRegion()
        self._syncing = True
        try:
            self._main_plot.getViewBox().setXRange(x0, x1, padding=0)
        finally:
            self._syncing = False
