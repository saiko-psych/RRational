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

``SectionRegion`` supports **draggable boundaries**:
``LinearRegionItem`` already exposes left+right edges as InfiniteLine
children, so toggling ``setMovable(True)`` is most of the work. The
extra plumbing here is:
- a ``snap_fn`` callable (set externally) that snaps a raw drag value
  to the nearest beat in the active dataset's ``t`` array
- a ``sigRegionChangeFinished`` listener on the parent — connected by
  the PlotWidget so MainWindow can persist the new bounds
- right-click context menu via ``mouseClickEvent`` (rename / delete /
  split at cursor)
- hover cursors: ``SizeHorCursor`` on the edges (handled by the
  InfiniteLine children once movable=True), ``SizeAllCursor`` on the
  band body
"""

from __future__ import annotations

import pyqtgraph as pg
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import QMenu

# Default visual style — kept here so PlotWidget callers don't have to
# repeat these constants. Section bands use a low alpha so the curve
# stays the dominant visual element.
SECTION_ALPHA = 35  # 0–255; ~14% opacity
SECTION_BORDER_ALPHA = 90
EVENT_LINE_ALPHA = 180


class SectionRegion(pg.LinearRegionItem):
    """A coloured time-range band marking one named section.

    Wraps PyQtGraph's ``LinearRegionItem``. Default appearance:
    semi-transparent fill (so the RR-tachogram beneath stays readable).

    When ``editable=True``:
    - the left+right edges become draggable handles
    - the snap_fn (if set) snaps each new bound to the nearest beat
    - ``sigRegionChangeFinished`` fires once per drag for persistence
    - right-click opens a context menu (rename / delete / split)

    Click handling (single-click selection) lives in the PlotWidget
    rather than the item: the widget knows which section is selected in
    the sidebar and can do the "click section → highlight in sidebar"
    handshake there.
    """

    # Emitted by the right-click context menu actions. The PlotWidget
    # listens and forwards to MainWindow, which mutates SectionMeta and
    # persists via gui.persistence.save_sections.
    sigRenameRequested = Signal(str)  # current label
    sigDeleteRequested = Signal(str)
    sigSplitRequested = Signal(str, float)  # label, cursor_t

    def __init__(
        self,
        t_start: float,
        t_end: float,
        label: str,
        color: QColor,
        editable: bool = False,
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
            movable=editable,
        )
        self.section_label = label  # plain attribute — read by MainWindow
        # Sit visually beneath event markers but above the gridlines.
        self.setZValue(-10)

        # Snap function: takes a raw bound (seconds-since-epoch) and
        # returns the nearest beat timestamp. Set externally by the
        # PlotWidget when section edit mode is enabled.
        self.snap_fn = None  # type: ignore[assignment]

        # Hover cursor for the body of the band. The edge cursors come
        # for free from LinearRegionItem's child InfiniteLine handles
        # once movable=True. ``setAcceptHoverEvents`` ensures the cursor
        # update fires; LinearRegionItem doesn't enable it by default.
        self.setAcceptHoverEvents(True)
        self._editable = editable

        # Internal flag to prevent the snap-on-change from recursing
        # into itself when ``setRegion`` is called from within the
        # sigRegionChanged handler.
        self._suppress_snap = False
        # PyQtGraph fires sigRegionChanged while dragging; we only
        # snap once the drag finishes so the user sees continuous
        # feedback while moving.
        self.sigRegionChangeFinished.connect(self._on_drag_finished)

    def set_editable(self, editable: bool) -> None:
        """Toggle drag-to-edit on the region edges + body."""
        self._editable = editable
        self.setMovable(editable)
        # LinearRegionItem also has per-line movability — the ``movable``
        # constructor flag sets both, but the runtime ``setMovable``
        # only flips the parent flag in older pyqtgraph versions. Touch
        # the child lines explicitly to be safe.
        for line in self.lines:
            line.setMovable(editable)

    def set_snap_function(self, snap_fn) -> None:
        """Install a ``(t: float) -> float`` snap callable.

        ``None`` clears the snap. Called by PlotWidget whenever the
        active dataset (and hence its beat array) changes.
        """
        self.snap_fn = snap_fn

    # ------------------------------------------------------------------
    # Drag-end handler — snap + emit
    # ------------------------------------------------------------------
    def _on_drag_finished(self) -> None:
        if not self._editable:
            return
        if self._suppress_snap:
            return
        lo, hi = self.getRegion()
        if self.snap_fn is not None:
            try:
                snapped_lo = float(self.snap_fn(float(lo)))
                snapped_hi = float(self.snap_fn(float(hi)))
            except Exception:
                snapped_lo, snapped_hi = float(lo), float(hi)
            if snapped_lo > snapped_hi:
                snapped_lo, snapped_hi = snapped_hi, snapped_lo
            if snapped_lo != lo or snapped_hi != hi:
                self._suppress_snap = True
                try:
                    self.setRegion((snapped_lo, snapped_hi))
                finally:
                    self._suppress_snap = False

    # ------------------------------------------------------------------
    # Right-click context menu (only in edit mode)
    # ------------------------------------------------------------------
    def mouseClickEvent(self, ev) -> None:  # noqa: N802 — Qt API name
        """Intercept right-clicks to open a context menu; leave left-
        clicks to LinearRegionItem (which handles selection on body)."""
        if self._editable and ev.button() == Qt.RightButton:
            ev.accept()
            # Use the scene position to derive the cursor's data x.
            try:
                view = self.getViewBox()
                if view is not None:
                    data_pt = view.mapSceneToView(ev.scenePos())
                    cursor_t = float(data_pt.x())
                else:
                    cursor_t = float(self.getRegion()[0])
            except Exception:
                cursor_t = float(self.getRegion()[0])
            self._show_context_menu(ev.screenPos(), cursor_t)
            return
        super().mouseClickEvent(ev)

    def _show_context_menu(self, screen_pos, cursor_t: float) -> None:
        menu = QMenu()
        act_rename = menu.addAction("Rename section...")
        act_split = menu.addAction("Split here...")
        menu.addSeparator()
        act_delete = menu.addAction("Delete section")

        chosen = menu.exec(screen_pos.toPoint())
        if chosen is act_rename:
            self.sigRenameRequested.emit(self.section_label)
        elif chosen is act_delete:
            self.sigDeleteRequested.emit(self.section_label)
        elif chosen is act_split:
            self.sigSplitRequested.emit(self.section_label, cursor_t)

    # ------------------------------------------------------------------
    # Hover cursor on the body of the band (edges are handled by the
    # child InfiniteLines, which switch to SizeHorCursor automatically
    # when movable=True).
    # ------------------------------------------------------------------
    def hoverEvent(self, ev) -> None:  # noqa: N802 — Qt API name
        if not self._editable or ev.isExit():
            try:
                self.setCursor(Qt.ArrowCursor)
            except Exception:
                pass
            return
        # SizeAllCursor signals "you can drag the whole band". The
        # LinearRegionItem child InfiniteLines override this with
        # SizeHorCursor when the hover lands on an edge, so the user
        # still sees the right cursor over the handles.
        try:
            self.setCursor(Qt.SizeAllCursor)
        except Exception:
            pass

    def set_highlighted(self, highlighted: bool) -> None:
        """Bump alpha when this section is the one selected in the sidebar.

        Round 27 — verified ``LinearRegionItem.brush`` IS a QBrush
        attribute (not a method) in pyqtgraph 0.13+. The reviewer's
        flagged "AttributeError on .brush" was a false positive — the
        attribute path works and is exercised by
        test_section_region_set_highlighted_increases_alpha.
        """
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
    line on pan/zoom — we just plumb the constructor args. No mouse
    interaction yet: future work can add ``movable=True`` for manual
    event creation.
    """

    def __init__(self, t: float, label: str, color: QColor) -> None:
        pen_color = QColor(color)
        pen_color.setAlpha(EVENT_LINE_ALPHA)

        # Round 27 — label fill was hardcoded white-at-70% which became
        # invisible against the light theme (white on near-white). Derive
        # from the global pyqtgraph background so the fill stays a
        # contrasting card on either theme.
        bg = pg.getConfigOption("background")
        bg_color = QColor(bg) if isinstance(bg, str) else QColor(255, 255, 255)
        fill_color = QColor(bg_color)
        fill_color.setAlpha(200)

        super().__init__(
            pos=t,
            angle=90,  # vertical
            pen=pg.mkPen(pen_color, width=1, style=Qt.DashLine),
            label=label,
            labelOpts={
                "position": 0.95,  # near the top of the visible y-range
                "color": pen_color,
                "fill": (
                    fill_color.red(),
                    fill_color.green(),
                    fill_color.blue(),
                    fill_color.alpha(),
                ),
                "movable": False,
            },
            movable=False,
        )
        # PyQtGraph's InfiniteLine already owns ``self.label`` (the
        # InfLineLabel widget) — we expose the text under a different
        # name so MainWindow / tests can read it back.
        self.event_label = label
        # Events sit on TOP of section bands but below the cursor
        # crosshair (z=10).
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
# Cluster A6 — warm-gray for excluded artifacts. Reads as "muted /
# de-emphasised" without the red-orange "alert" signal of the active
# artifact colour. Picked on the cool side of gray so it harmonises
# with both light and dark themes.
_EXCLUDED_COLOR = "#7d8390"
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

    Visually distinct from algorithm-detected artifacts — rendered as
    filled squares (instead of circles) using the artifact colour from
    the active ColorScheme. Behaviour is otherwise identical to
    :class:`ArtifactOverlay` (replace-all on ``set_points``).
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

    Cluster A6 — rendered in warm-gray (``_EXCLUDED_COLOR``) instead of
    the orange artifact colour so excluded beats read as "muted" rather
    than "still alarming". The ColorScheme-driven ``apply_color`` path
    is therefore deliberately a no-op: we never want excluded markers
    to inherit the artifact colour, regardless of theme.
    """

    def __init__(self) -> None:
        super().__init__(
            size=_ARTIFACT_SIZE,
            pen=pg.mkPen(_EXCLUDED_COLOR, width=1),
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
        """No-op kept for API parity with the other overlays.

        Cluster A6 — excluded markers are deliberately decoupled from
        the ColorScheme's ``artifact`` colour so they stay warm-gray
        regardless of which preset the user picks. Argument retained so
        ``RRPlotWidget.set_color_scheme`` can call ``apply_color`` on
        every overlay uniformly.
        """
        # Force warm-gray regardless of scheme. Brush stays transparent
        # — hollow outline is the visual cue for "excluded".
        c = QColor(_EXCLUDED_COLOR)
        c.setAlpha(180)
        self.setPen(pg.mkPen(c, width=1))
        self.setBrush(pg.mkBrush(0, 0, 0, 0))


# Visual constants for exclusion zones. The fill alpha is deliberately
# higher than SectionRegion's so the user can spot a narrow zone among
# section bands; the colour itself comes from ColorScheme.exclusion so
# users can re-skin via Preferences.
EXCLUSION_ALPHA = 90
EXCLUSION_BORDER_ALPHA = 200


class ExclusionRegion(pg.LinearRegionItem):
    """A draggable, deletable time-range marking beats to exclude.

    Wraps PyQtGraph's ``LinearRegionItem`` so each zone is independently
    movable along the X-axis — the user can fine-tune the boundaries
    after the initial drag-create. Sits above section bands (z=-10) but
    below event markers (z=0) so it visually reads as a "veil" over the
    signal.

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
        hover_fill = QColor(color)
        # Cluster A4 — hoverBrush bumps alpha to ~70% so the region
        # visibly "lights up" when the cursor is over it; otherwise the
        # default LinearRegionItem hoverBrush is the same as the resting
        # one (no visual feedback at all).
        hover_fill.setAlpha(min(255, EXCLUSION_ALPHA + 90))
        border = QColor(color)
        border.setAlpha(EXCLUSION_BORDER_ALPHA)
        # Cluster A6 — dashed border lines up with the warm-gray excluded
        # artifact dots: both communicate "muted / excluded from analysis"
        # via a dashed/hollow visual.
        super().__init__(
            values=(t_start, t_end),
            orientation="vertical",
            brush=fill,
            hoverBrush=hover_fill,
            pen=pg.mkPen(border, width=2, style=Qt.DashLine),
            hoverPen=pg.mkPen(border, width=2),
            movable=True,
        )
        self.reason = str(reason or "")
        # Slightly above section bands so the exclusion band paints on top
        # of them. Below EventMarker (z=0) and ArtifactOverlay (z=5).
        self.setZValue(-5)

        # Cluster A4 — explicit SizeHorCursor on the edge handles. The
        # parent LinearRegionItem only sets this on hover via the child
        # InfiniteLines, but on Qt6 / pyqtgraph 0.13 the cursor is
        # sometimes left at ArrowCursor until the user has actually
        # started dragging. Set it on construction as a fall-back.
        for line in self.lines:
            try:
                line.setCursor(Qt.SizeHorCursor)
            except Exception:
                pass

    def apply_color(self, color: QColor) -> None:
        """Re-paint fill + border from ``color`` (used by set_color_scheme)."""
        fill = QColor(color)
        fill.setAlpha(EXCLUSION_ALPHA)
        hover_fill = QColor(color)
        hover_fill.setAlpha(min(255, EXCLUSION_ALPHA + 90))
        border = QColor(color)
        border.setAlpha(EXCLUSION_BORDER_ALPHA)
        self.setBrush(fill)
        try:
            self.setHoverBrush(hover_fill)
        except AttributeError:  # pragma: no cover - older pyqtgraph
            pass
        border_pen = pg.mkPen(border, width=2, style=Qt.DashLine)
        for line in self.lines:
            line.setPen(border_pen)


# Visual constants for free-text annotations. Purple chosen so the
# line stands apart from both blue/grey section borders and the orange
# artifact dots.
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
        from datetime import timezone as _tz

        try:
            # Round 33 (A1) — convert the epoch in UTC then to the display
            # tz so the shown time is DST-stable (naive fromtimestamp used
            # local wall-clock and drifted an hour across a DST boundary).
            stamp = (
                _dt.fromtimestamp(self.annotation_t, tz=_tz.utc)
                .astimezone()
                .strftime("%Y-%m-%d %H:%M:%S")
            )
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
