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

    def apply_colors(self, fill_color: QColor, border_color: QColor) -> None:
        """Re-paint this region with new fill + border colours.

        Used by ``RRPlotWidget.set_color_scheme`` so a Preferences
        change refreshes existing items without recreating them.
        LinearRegionItem owns two ``InfiniteLine`` border instances on
        ``self.lines`` — those carry the border pen, not the region
        itself, so we update each in turn.
        """
        new_fill = QColor(fill_color)
        new_fill.setAlpha(SECTION_ALPHA)
        new_border = QColor(border_color)
        new_border.setAlpha(SECTION_BORDER_ALPHA)
        self.setBrush(new_fill)
        border_pen = pg.mkPen(new_border, width=1)
        for line in self.lines:
            line.setPen(border_pen)


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

    def apply_color(self, color: QColor) -> None:
        """Re-paint the vertical line with a new colour (label included)."""
        pen_color = QColor(color)
        pen_color.setAlpha(EVENT_LINE_ALPHA)
        self.setPen(pg.mkPen(pen_color, width=1, style=Qt.DashLine))
        # InfiniteLine label is an InfLineLabel; setColor accepts a QColor.
        try:
            self.label.setColor(pen_color)
        except (AttributeError, RuntimeError):  # pragma: no cover - defensive
            pass


# Visual constants for artifact overlay. Orange picked to contrast with
# the blue tachogram and the cooler section-band palette.
_ARTIFACT_COLOR = "#ff7f0e"
_ARTIFACT_SIZE = 8  # pixel diameter of each dot


class ArtifactOverlay(pg.ScatterPlotItem):
    """Scatter overlay marking detected artifact positions on the plot.

    One ``ArtifactOverlay`` is added per signal — calling ``set_points``
    replaces the entire artifact set so we don't accumulate stale items
    across re-detections. Using ScatterPlotItem (one C++ object) instead
    of one InfiniteLine per artifact keeps Qt's scene tree small even
    for >1000-artifact recordings.
    """

    def __init__(self) -> None:
        super().__init__(
            size=_ARTIFACT_SIZE,
            pen=pg.mkPen(_ARTIFACT_COLOR, width=1),
            brush=pg.mkBrush(_ARTIFACT_COLOR),
            symbol="o",
            pxMode=True,
        )
        # Above section bands + events, below the crosshair.
        self.setZValue(5)

    def set_points(self, ts: list[float], vs: list[float]) -> None:
        """Replace the artifact set with the supplied (time, value) pairs."""
        self.setData(x=ts, y=vs)

    def clear_points(self) -> None:
        self.setData(x=[], y=[])

    def apply_color(self, color: QColor) -> None:
        """Re-paint every artifact dot with a new pen + brush colour."""
        c = QColor(color)
        self.setPen(pg.mkPen(c, width=1))
        self.setBrush(pg.mkBrush(c))


class ManualArtifactOverlay(pg.ScatterPlotItem):
    """Scatter overlay for user-added manual artifact markers.

    Phase 14: visually distinct from algorithm-detected artifacts —
    rendered as filled squares (instead of circles) using the artifact
    colour from the active ColorScheme. Behaviour is otherwise identical
    to :class:`ArtifactOverlay` (replace-all on ``set_points``).
    """

    def __init__(self) -> None:
        super().__init__(
            size=_ARTIFACT_SIZE,
            pen=pg.mkPen(_ARTIFACT_COLOR, width=1),
            brush=pg.mkBrush(_ARTIFACT_COLOR),
            symbol="s",  # square — distinguishes manual from algo (circles)
            pxMode=True,
        )
        # Above algorithm artifacts so a manual mark overlaying an algo
        # site is visible. Below the crosshair (z=20).
        self.setZValue(6)

    def set_points(self, ts: list[float], vs: list[float]) -> None:
        self.setData(x=ts, y=vs)

    def clear_points(self) -> None:
        self.setData(x=[], y=[])

    def apply_color(self, color: QColor) -> None:
        c = QColor(color)
        self.setPen(pg.mkPen(c, width=1))
        self.setBrush(pg.mkBrush(c))


class ExcludedArtifactOverlay(pg.ScatterPlotItem):
    """Scatter overlay for algorithm artifacts the user has excluded.

    Phase 14: when the user clicks an algorithm-detected artifact, it
    becomes "excluded" — still visible but rendered hollow + dimmed so
    the eye can tell which beats the analysis should ignore. Drawn as
    an outline circle (no fill) with reduced opacity.
    """

    def __init__(self) -> None:
        super().__init__(
            size=_ARTIFACT_SIZE,
            pen=pg.mkPen(_ARTIFACT_COLOR, width=1),
            brush=pg.mkBrush(0, 0, 0, 0),  # transparent fill
            symbol="o",
            pxMode=True,
        )
        # Sits on top of ArtifactOverlay so excluded markers cover the
        # filled dot beneath them.
        self.setZValue(7)

    def set_points(self, ts: list[float], vs: list[float]) -> None:
        self.setData(x=ts, y=vs)

    def clear_points(self) -> None:
        self.setData(x=[], y=[])

    def apply_color(self, color: QColor) -> None:
        c = QColor(color)
        c.setAlpha(120)  # dimmed so excluded reads as "muted"
        self.setPen(pg.mkPen(c, width=1))
        # Brush stays transparent — hollow appearance is the whole point.
        self.setBrush(pg.mkBrush(0, 0, 0, 0))


# Visual constants for exclusion zones (Phase 15). The fill alpha is
# deliberately higher than SectionRegion's so the user can spot a
# narrow zone among section bands; the colour itself comes from
# ColorScheme.exclusion so users can re-skin via Preferences.
EXCLUSION_ALPHA = 90
EXCLUSION_BORDER_ALPHA = 200


class ExclusionRegion(pg.LinearRegionItem):
    """A draggable, deletable time-range marking beats to exclude.

    Phase 15 wraps PyQtGraph's ``LinearRegionItem`` so each zone is
    independently movable along the X-axis - the user can fine-tune the
    boundaries after the initial drag-create. Sits above section bands
    (z=-10) but below event markers (z=0) so it visually reads as a
    "veil" over the signal.

    The zone carries a ``reason`` string + a back-reference to the
    :class:`~rrational.inspector.exclusion_persistence.ExclusionZone`
    dataclass it represents, so the PlotWidget can keep model + view
    in sync without parallel bookkeeping.
    """

    def __init__(
        self, t_start: float, t_end: float, reason: str, color: QColor
    ) -> None:
        fill = QColor(color)
        fill.setAlpha(EXCLUSION_ALPHA)
        border = QColor(color)
        border.setAlpha(EXCLUSION_BORDER_ALPHA)
        super().__init__(
            values=(t_start, t_end),
            orientation="vertical",
            brush=fill,
            pen=pg.mkPen(border, width=2),
            movable=True,
        )
        self.reason = str(reason or "")
        # Slightly above section bands so the exclusion band paints on top
        # of them. Below EventMarker (z=0) and ArtifactOverlay (z=5).
        self.setZValue(-5)

    def apply_color(self, color: QColor) -> None:
        """Re-paint fill + border from ``color`` (used by set_color_scheme)."""
        fill = QColor(color)
        fill.setAlpha(EXCLUSION_ALPHA)
        border = QColor(color)
        border.setAlpha(EXCLUSION_BORDER_ALPHA)
        self.setBrush(fill)
        border_pen = pg.mkPen(border, width=2)
        for line in self.lines:
            line.setPen(border_pen)


# Visual constants for free-text annotations (Phase 20). Purple chosen
# so the line stands apart from both blue/grey section borders and the
# orange artifact dots.
_ANNOTATION_COLOR = "#8b3a8c"
_ANNOTATION_LINE_ALPHA = 200


class AnnotationMarker(pg.InfiniteLine):
    """Vertical line + text label for one free-text annotation.

    Built on ``pg.InfiniteLine`` so the label tracks the line on pan /
    zoom. The widget itself is dumb — the PlotWidget wires click /
    hover handlers from the outside. ``annotation`` stores the dataclass
    so the edit / delete handlers can look it up without an indexable
    container.
    """

    def __init__(self, t: float, text: str, label_text: str | None = None) -> None:
        pen_color = QColor(_ANNOTATION_COLOR)
        pen_color.setAlpha(_ANNOTATION_LINE_ALPHA)

        # Trim long annotations to keep the on-plot label readable.
        display = label_text if label_text is not None else (text or "(empty)")
        if len(display) > 24:
            display = display[:21] + "..."

        super().__init__(
            pos=t,
            angle=90,
            pen=pg.mkPen(pen_color, width=1, style=Qt.DotLine),
            label=display,
            labelOpts={
                "position": 0.05,  # bottom of the visible y-range
                "color": pen_color,
                "fill": (255, 255, 220, 200),
                "movable": False,
            },
            movable=False,
        )
        # Store the source text + timestamp so the hover tooltip can
        # show the full text even when the label is truncated.
        self.annotation_text = str(text)
        self.annotation_t = float(t)
        # Above section bands + events; below cursor crosshair.
        self.setZValue(6)
        # Hover-tooltip — set whenever the source text changes.
        self._refresh_tooltip()

    def set_annotation_text(self, new_text: str) -> None:
        """Update the on-plot label + tooltip to match ``new_text``."""
        self.annotation_text = str(new_text)
        display = new_text or "(empty)"
        if len(display) > 24:
            display = display[:21] + "..."
        # InfLineLabel exposes setFormat on PyQtGraph 0.13+; fall back
        # to direct text rewrite on older versions.
        try:
            self.label.setFormat(display)
        except AttributeError:  # pragma: no cover - PyQtGraph < 0.13
            self.label.setText(display)
        self._refresh_tooltip()

    def _refresh_tooltip(self) -> None:
        from datetime import datetime as _dt

        try:
            stamp = _dt.fromtimestamp(self.annotation_t).strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OSError, OverflowError):  # pragma: no cover - defensive
            stamp = str(self.annotation_t)
        # InfiniteLine doesn't render a QWidget tooltip natively; we
        # attach the string on the item so the PlotWidget hover handler
        # can pull it back out without rebuilding it.
        self._tooltip_text = f"{self.annotation_text}\n({stamp})"
        self.setToolTip(self._tooltip_text)

    @property
    def tooltip_text(self) -> str:
        return getattr(self, "_tooltip_text", self.annotation_text)
