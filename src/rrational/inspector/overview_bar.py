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
# Round 20: the trace colour is no longer a hardcoded sky-blue. We read
# the active theme's secondary-text token at construct time so the bar
# follows the user's Okabe-Ito / preset choice and stays legible in both
# dark and light modes.
_BAR_HEIGHT = 80
_VIEWPORT_FILL = (46, 134, 171, 60)
_VIEWPORT_BORDER = (46, 134, 171, 200)


def _resolve_line_color() -> str:
    """Pull a theme-aware curve colour from the active palette tokens.

    Falls back to the legacy sky-blue ``#7FB3D5`` when the theme module
    is not importable (e.g. headless tests that bypass the inspector
    style stack), so existing tests stay stable.
    """
    try:
        from rrational.inspector.style.theme import palette_tokens

        return palette_tokens()["text_secondary"]
    except (ImportError, KeyError):
        return "#7FB3D5"


# Mirror stripes — same families as the main-plot overlays, slightly
# muted so they don't compete with the viewport rectangle.
_EXCLUSION_STRIPE = (125, 131, 144, 120)  # warm-gray, matches drop-log palette
_ANNOTATION_STRIPE = (203, 70, 175, 160)  # magenta-ish, matches main annotations


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
        # Background defers to the global pyqtgraph config (dark/light theme).

        self._curve = pg.PlotDataItem(
            pen=pg.mkPen(_resolve_line_color(), width=1),
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
        # Stripe items mirroring the main-plot overlays. We hold them in
        # lists so ``clear_overlays`` can remove them without touching
        # the curve or viewport region.
        self._exclusion_items: list[pg.LinearRegionItem] = []
        self._annotation_items: list[pg.LinearRegionItem] = []

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
        self.clear_overlays()

    # ------------------------------------------------------------------
    # Mirror overlays — exclusion zones + annotations
    # ------------------------------------------------------------------
    def clear_overlays(self) -> None:
        """Remove all stripe mirrors. Called before a fresh set_overlays."""
        for item in self._exclusion_items + self._annotation_items:
            self.removeItem(item)
        self._exclusion_items.clear()
        self._annotation_items.clear()

    def set_exclusion_zones(self, zones) -> None:
        """Mirror the main-plot exclusion zones as warm-gray stripes.

        ``zones`` is any iterable of ``(t_start, t_end)`` tuples in the
        same coordinate frame as the curve (seconds since epoch).
        Re-calls fully replace the previous mirror so the bar always
        reflects the current truth.
        """
        # Drop only the exclusion family; annotations stay put.
        for item in self._exclusion_items:
            self.removeItem(item)
        self._exclusion_items.clear()
        for t0, t1 in zones:
            stripe = pg.LinearRegionItem(
                values=(float(t0), float(t1)),
                orientation="vertical",
                brush=QColor(*_EXCLUSION_STRIPE),
                pen=pg.mkPen(QColor(*_EXCLUSION_STRIPE), width=0),
                movable=False,
            )
            stripe.setZValue(1)  # below the viewport rectangle
            self.addItem(stripe)
            self._exclusion_items.append(stripe)

    def set_annotations(self, spans) -> None:
        """Mirror annotation spans as magenta stripes.

        ``spans`` is any iterable of ``(t_start, t_end)`` tuples (use
        ``t_end == t_start`` for point annotations — they'll render as
        a 1px line via pyqtgraph's degenerate-region behaviour).
        """
        for item in self._annotation_items:
            self.removeItem(item)
        self._annotation_items.clear()
        for t0, t1 in spans:
            stripe = pg.LinearRegionItem(
                values=(float(t0), float(t1)),
                orientation="vertical",
                brush=QColor(*_ANNOTATION_STRIPE),
                pen=pg.mkPen(QColor(*_ANNOTATION_STRIPE), width=0),
                movable=False,
            )
            stripe.setZValue(2)
            self.addItem(stripe)
            self._annotation_items.append(stripe)

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
