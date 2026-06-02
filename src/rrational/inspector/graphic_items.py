"""PyQtGraph overlay items: section bands and event markers.

The pattern is borrowed from mne-qt-browser's ``_graphic_items.py``:
each overlay is a thin subclass of a stock PyQtGraph item, holds a
reference to its metadata source, and exposes a ``label`` property so
the MainWindow can find it again later (e.g. on sidebar selection).

We deliberately keep these items **stateless about the rest of the
app** — they don't know about MainWindow or InspectorData. The
PlotWidget instantiates them with whatever colour/movability flags it
wants, and connects to the standard ``sigClicked`` / ``sigRegionChanged``
PyQtGraph signals from the outside.

mne-qt-browser kept strong Python refs to all annotation items inside
a container to avoid the "wrapped C++ object deleted" bug
(github.com/mne-tools/mne-qt-browser/issues/82). We follow the same
discipline in ``plot_widget.py`` — the widget keeps lists of overlay
items as attributes.
"""

from __future__ import annotations

import pyqtgraph as pg
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor

# Default visual style — kept here so PlotWidget callers don't have to
# repeat these constants. Section bands use a low alpha so the curve
# stays the dominant visual element.
SECTION_ALPHA = 35  # 0–255; ~14% opacity
SECTION_BORDER_ALPHA = 90
EVENT_LINE_ALPHA = 180


class SectionRegion(pg.LinearRegionItem):
    """A coloured time-range band marking one named section.

    Wraps PyQtGraph's ``LinearRegionItem``. Default appearance:
    semi-transparent fill (so the RR-tachogram beneath stays readable),
    movable=False (Phase 2 doesn't allow edit-by-drag yet — that lands
    in Phase 3 with the artifact editor).

    Click handling lives in the PlotWidget rather than the item: the
    widget knows which section is selected in the sidebar and can do
    the "click section → highlight in sidebar" handshake there.
    """

    def __init__(
        self,
        t_start: float,
        t_end: float,
        label: str,
        color: QColor,
    ) -> None:
        fill = QColor(color)
        fill.setAlpha(SECTION_ALPHA)
        border = QColor(color)
        border.setAlpha(SECTION_BORDER_ALPHA)

        super().__init__(
            values=(t_start, t_end),
            orientation="vertical",
            brush=fill,
            pen=pg.mkPen(border, width=1),
            movable=False,  # Phase 3 will toggle this on for editing
        )
        self.section_label = label  # plain attribute — read by MainWindow
        # Sit visually beneath event markers but above the gridlines.
        self.setZValue(-10)

    def set_highlighted(self, highlighted: bool) -> None:
        """Bump alpha when this section is the one selected in the sidebar."""
        fill = self.brush.color()
        fill.setAlpha(SECTION_ALPHA * 3 if highlighted else SECTION_ALPHA)
        self.setBrush(fill)


class EventMarker(pg.InfiniteLine):
    """A vertical line at one event timestamp, with the event label.

    Stock ``InfiniteLine`` already supports a label that follows the
    line on pan/zoom — we just plumb the constructor args. As with
    ``SectionRegion``, no Phase 2 mouse interaction: future phases can
    add ``movable=True`` for manual event creation.
    """

    def __init__(self, t: float, label: str, color: QColor) -> None:
        pen_color = QColor(color)
        pen_color.setAlpha(EVENT_LINE_ALPHA)

        super().__init__(
            pos=t,
            angle=90,  # vertical
            pen=pg.mkPen(pen_color, width=1, style=Qt.DashLine),
            label=label,
            labelOpts={
                "position": 0.95,  # near the top of the visible y-range
                "color": pen_color,
                "fill": (255, 255, 255, 180),
                "movable": False,
            },
            movable=False,
        )
        # PyQtGraph's InfiniteLine already owns ``self.label`` (the
        # InfLineLabel widget) — we expose the text under a different
        # name so MainWindow / tests can read it back.
        self.event_label = label
        # Events sit on TOP of section bands but below the cursor crosshair
        # (which we'll add in Phase 3 at z=10).
        self.setZValue(0)
