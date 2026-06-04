"""Scrollable RR-tachogram plot widget built on PyQtGraph.

Renders ONE continuous timeline of RR intervals (ms) against absolute
wall-clock time, with optional overlays:

- ``SectionRegion`` — coloured bands marking named sections
- ``EventMarker`` — vertical lines at event timestamps

Phase 2 introduces the custom ``RRViewBox`` subclass: currently a thin
no-op wrapper, but it's the hook point where Phase 3's click-to-add-
event-marker and drag-to-edit-region will plug in. Subclassing the
ViewBox now means later additions don't require touching every call
site.

Keyboard model:
    Left  / Right  — pan 25 % of the visible window
    Up    / Down   — zoom out / in
    Home  / End    — jump to first / last 60 s of signal
                     (Home/End live on MainWindow as an eventFilter —
                     QGraphicsView eats them if wired here directly)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QColor, QKeySequence, QShortcut

from rrational.inspector.exclusion_persistence import ExclusionZone
from rrational.inspector.graphic_items import (
    AnnotationMarker,
    ArtifactOverlay,
    EventMarker,
    ExcludedArtifactOverlay,
    ExclusionRegion,
    ManualArtifactOverlay,
    SectionRegion,
)

# Module-level alias keeps the AnnotationMarker import alive in spite
# of the ruff/black unused-import lint — every reference inside the
# class body is hidden behind ``from __future__ import annotations``
# (string-evaluated type hints), so the linter can't see them.
_AnnotationMarker = AnnotationMarker

if TYPE_CHECKING:
    from rrational.inspector.data_loader import (
        EventMeta,
        InspectorData,
        SectionMeta,
    )

# Re-exported so callers can ``from rrational.inspector.plot_widget
# import ExclusionZone`` without crossing module boundaries — mirrors
# how ``SectionRegion`` / ``EventMarker`` are surfaced here too.
__all__ = ["RRPlotWidget", "ExclusionZone", "ExclusionRegion"]

PAN_FRACTION = 0.25  # fraction of the visible window per Left/Right press
ZOOM_FACTOR = 1.25  # multiplicative zoom per Up/Down press
JUMP_WINDOW_S = 60.0  # Home/End viewport size
LINE_COLOR = "#2E86AB"  # matches Scientific theme accent in color_scheme.py
EXCLUSION_COLOR = "#FFA500"  # Phase 15 default; ColorScheme.exclusion overrides
MIN_EXCLUSION_WIDTH_S = 0.5  # ignore microscopic drags (jitter from a click)

# Distinct colours cycled through section regions / event markers. Picked
# from the matplotlib "tab10" palette for adequate contrast against the
# blue RR-tachogram on a white background. Phase 3 will move this into
# the user-configurable ColorScheme.
_SECTION_PALETTE = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]


class RRViewBox(pg.ViewBox):
    """Custom ViewBox — Phase 15 drag-create for exclusion zones.

    When ``exclusion_mode`` is ON (toggled from the PreprocessingPanel
    sidebar), a left-button drag emits ``exclusion_drag_finished(t0, t1)``
    instead of the default pan behaviour. The RRPlotWidget catches the
    signal and materialises a new ``ExclusionRegion``.

    When OFF, every default ``ViewBox`` behaviour (drag-to-pan,
    scroll-zoom, right-click menu) is inherited so users can still
    explore the timeline normally.

    Same architectural choice as mne-qt-browser's ``RawViewBox`` — a
    single override point keeps the rest of the codebase ignorant of
    Qt's event model.
    """

    # (t_start, t_end) of a finished left-drag, in data-coordinate seconds
    exclusion_drag_finished = Signal(float, float)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._exclusion_mode = False

    def set_exclusion_mode(self, enabled: bool) -> None:
        self._exclusion_mode = bool(enabled)

    def mouseDragEvent(self, ev, axis=None) -> None:  # noqa: N802 — Qt API
        # In exclusion mode we intercept LEFT-button drags only. Middle/
        # right keep their stock zoom/menu semantics so users still have
        # an escape hatch for navigation.
        if not self._exclusion_mode or ev.button() != Qt.LeftButton:
            return super().mouseDragEvent(ev, axis=axis)
        ev.accept()
        if ev.isFinish():
            start_scene = ev.buttonDownScenePos()
            end_scene = ev.scenePos()
            t0 = float(self.mapSceneToView(start_scene).x())
            t1 = float(self.mapSceneToView(end_scene).x())
            if t0 > t1:
                t0, t1 = t1, t0
            self.exclusion_drag_finished.emit(t0, t1)


class RRPlotWidget(pg.PlotWidget):
    """A pan/zoom-able plot of one RR signal vs absolute time, with overlays."""

    # Emitted whenever the mouse moves over the plot AND data is loaded.
    # (t = seconds-since-epoch, v = interpolated RR ms; v is NaN if the
    # cursor is over a gap between sections.)
    cursor_moved = Signal(float, float)
    # Emitted when the mouse leaves the plot region — readout should clear.
    cursor_left = Signal()
    # Phase 14: emitted after a successful manual mark / unmark click.
    # The payload is the beat-index touched and a short string action
    # tag ("add" | "remove_manual" | "exclude_algo" | "include_algo").
    # PreprocessingPanel listens to auto-save + update the undo stack.
    manual_artifact_changed = Signal(int, str)
    # Phase 15 - emitted after any zone create/edit/delete so the
    # PreprocessingPanel can refresh its sidebar list + auto-save to disk.
    exclusion_zones_changed = Signal()
    # Phase 20: emitted when the user left-clicks on an empty part of the
    # plot AND annotation mode is enabled. Carries the data-coords X
    # position (t, seconds-since-epoch).
    plot_clicked = Signal(float)
    # Phase 20: emitted on right-click of an AnnotationMarker so the
    # panel can pop an edit / delete menu without coupling to QInfiniteLine.
    annotation_context = Signal(object, object)  # (AnnotationMarker, QPoint)

    def __init__(self, parent=None) -> None:
        super().__init__(parent, viewBox=RRViewBox())

        # X-axis is a DateAxis so the user sees real wall-clock time, not
        # epoch milliseconds. PyQtGraph's built-in DateAxisItem handles
        # tick formatting at every zoom level.
        date_axis = pg.DateAxisItem(orientation="bottom")
        self.setAxisItems({"bottom": date_axis})

        # Y-axis: RR in ms. Disable PyQtGraph's autoSIPrefix — RR values
        # cluster around 800 ms, which the SI auto-formatter would
        # otherwise relabel as "0.8 kms" (kiloseconds). That unit just
        # doesn't exist in HRV literature; we keep it plain ms.
        self.setLabel("left", "RR interval", units="ms")
        self.getAxis("left").enableAutoSIPrefix(False)
        self.setLabel("bottom", "Time")
        self.showGrid(x=True, y=True, alpha=0.25)

        # Single persistent PlotDataItem — never recreated, just .setData()'d.
        # Avoids the QGraphicsLayout memory leaks PyQtGraph has on
        # PySide6 ≥ 6.5 (mne-qt-browser issues #136/#82).
        # Speed knobs:
        #   - clipToView: only paint visible X-range
        #   - autoDownsample/peak: keep min/max so artifact spikes survive
        #   - connect="finite": NaN samples in the timeline break the line
        #     (used for inter-section gaps from data_loader)
        # skipFiniteCheck is OFF because connect="finite" requires the
        # finite check to know where to break.
        self._curve = pg.PlotDataItem(
            pen=pg.mkPen(LINE_COLOR, width=1),
            connect="finite",
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

        # Overlay containers. Lists keep strong Python refs to every
        # item; without these, PySide6 garbage-collects them and the
        # plot ends up with "wrapped C++ object deleted" errors
        # (mne-qt-browser issue #82).
        self._section_regions: list[SectionRegion] = []
        self._event_markers: list[EventMarker] = []
        self._sections_by_label: dict[str, SectionRegion] = {}

        # Artifact overlay — one ScatterPlotItem holds every artifact
        # dot for the current dataset; ``set_artifacts`` replaces the
        # whole point set, so re-detection doesn't stack stale dots.
        self._artifact_overlay = ArtifactOverlay()
        self._artifact_overlay.setVisible(False)
        self.addItem(self._artifact_overlay)

        # Phase 14: manual-mark mode (MNE-LAB-style).
        # ``_manual_added_indices`` are beat-indices the user clicked to
        # ADD as artifacts; ``_manual_removed_indices`` are algorithm-
        # detected indices the user clicked to exclude from analysis.
        # The disjoint sets keep the click logic simple - there's no
        # state where the same index is in both.
        self._manual_added_indices: set[int] = set()
        self._manual_removed_indices: set[int] = set()
        # Latest algorithm-detected indices (cached so the click handler
        # can decide between "click on algo dot" vs "click on free
        # beat"). Updated by ``set_artifacts``.
        self._algorithm_indices: set[int] = set()
        self._manual_overlay = ManualArtifactOverlay()
        self._manual_overlay.setVisible(False)
        self.addItem(self._manual_overlay)
        self._excluded_overlay = ExcludedArtifactOverlay()
        self._excluded_overlay.setVisible(False)
        self.addItem(self._excluded_overlay)
        # Flipped by PreprocessingPanel.manual-mark checkbox.
        self._manual_mark_mode = False
        # Click tolerance - within this many seconds of a beat, a click
        # snaps to that beat. 2 s matches the resting RR period at the
        # low end (bradycardia ~30 bpm) so single-beat snapping always
        # works on real recordings.
        self._click_tolerance_s = 2.0

        # Phase 20: annotation overlays. ``_annotation_markers`` keeps
        # strong Python refs so PySide6 doesn't garbage-collect the
        # InfiniteLine items out from under the scene.
        self._annotation_markers: list[AnnotationMarker] = []
        self._annotation_mode = False
        # Scene-level click signal is connected once below alongside
        # the Phase 14 sigMouseMoved hookup - keep ordering centralized.

        # Focus is required for mouse-wheel zoom to feel responsive even
        # before the user has clicked into the plot.
        self.setFocusPolicy(Qt.StrongFocus)

        # ------------------------------------------------------------------
        # Keyboard shortcuts for arrow keys live on the plot widget itself.
        # Home/End are registered separately at MainWindow level with an
        # eventFilter — QGraphicsView (PlotWidget's parent class) eats
        # Home/End for its own scroll-area handling, so a shortcut hung
        # off this widget never fires for those two keys.
        # ------------------------------------------------------------------
        self._make_shortcut(QKeySequence(Qt.Key_Left), self.pan_left)
        self._make_shortcut(QKeySequence(Qt.Key_Right), self.pan_right)
        self._make_shortcut(QKeySequence(Qt.Key_Up), self.zoom_out)
        self._make_shortcut(QKeySequence(Qt.Key_Down), self.zoom_in)

        # ----- Crosshair ----------------------------------------------------
        # Vertical InfiniteLine that tracks the cursor X position. Hidden
        # by default until set_crosshair_visible(True) is called by the
        # MainWindow (based on the View menu toggle). Z above section
        # bands but below the user's right-click menu — so the cursor
        # stays visible without blocking interaction.
        self._crosshair = pg.InfiniteLine(
            angle=90,
            pen=pg.mkPen(QColor(70, 70, 70, 160), width=1, style=Qt.DashLine),
            movable=False,
        )
        self._crosshair.setZValue(20)
        self._crosshair.setVisible(False)
        self.addItem(self._crosshair)
        self._crosshair_enabled = False

        # The PyQtGraph scene exposes a mouse-moved signal that gives us
        # pixel coordinates; we'll convert to data coords in the handler.
        self.scene().sigMouseMoved.connect(self._on_scene_mouse_moved)
        # Phase 14: left-clicks land here in manual-mark mode.
        self.scene().sigMouseClicked.connect(self._on_scene_mouse_clicked)

        # ----- Phase 15 — exclusion zones -----------------------------------
        # ``_exclusion_zones`` is the model: a list of dataclasses kept in
        # lock-step with the on-plot ExclusionRegion widgets in
        # ``_exclusion_regions``. Same array index => same zone. Selection
        # tracks the currently-active region so Delete-key / context-menu
        # actions know which one to mutate.
        self._exclusion_zones: list[ExclusionZone] = []
        self._exclusion_regions: list[ExclusionRegion] = []
        self._exclusion_color: QColor = QColor(EXCLUSION_COLOR)
        self._selected_exclusion_idx: int | None = None
        self.getViewBox().exclusion_drag_finished.connect(
            self._on_exclusion_drag_finished
        )
        # Delete-key shortcut removes the currently-selected zone.
        self._make_shortcut(
            QKeySequence(Qt.Key_Delete), self._delete_selected_exclusion
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _make_shortcut(self, key_seq: QKeySequence, slot) -> QShortcut:
        sc = QShortcut(key_seq, self)
        sc.setContext(Qt.WindowShortcut)
        sc.activated.connect(slot)
        return sc

    def _x_window(self) -> tuple[float, float, float]:
        x_lo, x_hi = self.getViewBox().viewRange()[0]
        return x_lo, x_hi, x_hi - x_lo

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------
    def set_data(self, data: "InspectorData") -> None:
        """Replace the displayed timeline.

        Clears any previously-added section/event overlays — the caller
        (MainWindow) is responsible for re-adding them after ``set_data``,
        because the colour assignment depends on per-application state
        the widget doesn't track.
        """
        self.clear_overlays()

        if len(data.t) == 0:
            self._curve.clear()
            self._times = None
            self._values = None
            return

        self._times = data.t
        self._values = data.v
        self._curve.setData(data.t, data.v)

        # Initial view: show the WHOLE recording. The continuous-timeline
        # UX is built around the user picking out structure visually
        # (sections, events) at a glance, then zooming into the bit they
        # want via sidebar click or Home/End. mne-qt-browser does the
        # same on first load (`_pg_figure.py: _onload_data_finished`).
        t0, t1 = data.t_start, data.t_end
        self.setXRange(t0, t1, padding=0.02)
        self.enableAutoRange(axis="y")

    # ------------------------------------------------------------------
    # Overlay API
    # ------------------------------------------------------------------
    def add_section_region(
        self, meta: "SectionMeta", color: QColor | None = None
    ) -> SectionRegion:
        """Add a coloured band for one section. Returns the created item."""
        if color is None:
            color = self._color_for_index(len(self._section_regions))
        region = SectionRegion(meta.t_start, meta.t_end, meta.name, color)
        self.addItem(region)
        self._section_regions.append(region)
        self._sections_by_label[meta.name] = region
        return region

    def add_event_marker(
        self, meta: "EventMeta", color: QColor | None = None
    ) -> EventMarker:
        """Add a vertical event line at ``meta.t``. Returns the created item."""
        if color is None:
            # Events use a darker variant of the palette so they read on
            # top of section bands at any zoom level.
            color = QColor("#444444")
        marker = EventMarker(meta.t, meta.label, color)
        self.addItem(marker)
        self._event_markers.append(marker)
        return marker

    def set_sections_visible(self, visible: bool) -> None:
        """Show or hide every SectionRegion band without dropping them."""
        for r in self._section_regions:
            r.setVisible(visible)

    def set_events_visible(self, visible: bool) -> None:
        """Show or hide every EventMarker line without dropping them."""
        for m in self._event_markers:
            m.setVisible(visible)

    def set_grid_visible(self, visible: bool) -> None:
        """Toggle the X+Y gridlines."""
        self.showGrid(x=visible, y=visible, alpha=0.25 if visible else 0)

    def set_artifacts(self, indices: np.ndarray) -> None:
        """Mark the supplied array indices as artifacts on the plot.

        Reads the (t, v) of each index from the data cache; pass an
        empty array to clear the overlay (or use ``clear_artifacts``).
        """
        # Phase 14: keep a Python-set cache so click handler can answer
        # "is this index an algorithm artifact?" in O(1).
        self._algorithm_indices = {int(i) for i in indices} if len(indices) else set()
        if self._times is None or len(indices) == 0:
            self._artifact_overlay.clear_points()
            return
        ts = self._times[indices].tolist()
        vs = self._values[indices].tolist()
        self._artifact_overlay.set_points(ts, vs)
        self._artifact_overlay.setVisible(True)
        # Re-render Phase-14 overlays now that the algo set is known.
        self._refresh_manual_overlays()

    def clear_artifacts(self) -> None:
        self._artifact_overlay.clear_points()
        self._artifact_overlay.setVisible(False)
        self._algorithm_indices = set()
        self._manual_added_indices.clear()
        self._manual_removed_indices.clear()
        self._refresh_manual_overlays()

    def set_artifacts_visible(self, visible: bool) -> None:
        """Toggle visibility of artifact overlay without dropping points."""
        self._artifact_overlay.setVisible(visible)
        # The manual + excluded overlays follow the same toggle — they
        # belong to the same "artifact markers" concept from the user's
        # perspective. Keeping one master switch keeps the UI simple.
        self._manual_overlay.setVisible(visible and bool(self._manual_added_indices))
        self._excluded_overlay.setVisible(
            visible and bool(self._manual_removed_indices)
        )

    # ------------------------------------------------------------------
    # Phase 14 — Manual artifact marking (MNE-LAB-style)
    # ------------------------------------------------------------------
    def set_manual_mark_mode(self, enabled: bool) -> None:
        """Enable/disable click-to-mark interaction on the plot.

        When enabled, the ViewBox's default left-click "set range" is
        suppressed so a single click adds (or toggles) an artifact at
        the nearest beat. When disabled, left-click behaves normally.
        """
        self._manual_mark_mode = bool(enabled)

    def manual_mark_mode(self) -> bool:
        return self._manual_mark_mode

    def set_manual_artifact_indices(
        self,
        added: set[int] | list[int] | None = None,
        removed: set[int] | list[int] | None = None,
    ) -> None:
        """Programmatic API used by the panel for restore / undo / redo.

        Replaces the manual-added / excluded sets wholesale and refreshes
        the overlays. Does NOT emit ``manual_artifact_changed`` — callers
        already know what they did.
        """
        if added is not None:
            self._manual_added_indices = {int(i) for i in added}
        if removed is not None:
            self._manual_removed_indices = {int(i) for i in removed}
        self._refresh_manual_overlays()

    def manual_added_indices(self) -> set[int]:
        return set(self._manual_added_indices)

    def manual_removed_indices(self) -> set[int]:
        return set(self._manual_removed_indices)

    def _refresh_manual_overlays(self) -> None:
        """Re-paint the manual + excluded scatter overlays from the sets."""
        if self._times is None:
            self._manual_overlay.clear_points()
            self._excluded_overlay.clear_points()
            return

        n = len(self._times)
        added_valid = sorted(i for i in self._manual_added_indices if 0 <= i < n)
        removed_valid = sorted(i for i in self._manual_removed_indices if 0 <= i < n)
        if added_valid:
            ts = self._times[added_valid].tolist()
            vs = self._values[added_valid].tolist()
            self._manual_overlay.set_points(ts, vs)
            self._manual_overlay.setVisible(self._artifact_overlay.isVisible())
        else:
            self._manual_overlay.clear_points()
            self._manual_overlay.setVisible(False)

        if removed_valid:
            ts = self._times[removed_valid].tolist()
            vs = self._values[removed_valid].tolist()
            self._excluded_overlay.set_points(ts, vs)
            self._excluded_overlay.setVisible(self._artifact_overlay.isVisible())
        else:
            self._excluded_overlay.clear_points()
            self._excluded_overlay.setVisible(False)

    def _nearest_finite_beat(self, t_click: float) -> int | None:
        """Return the index of the finite beat closest to ``t_click``.

        ``None`` if the click is further than ``_click_tolerance_s`` from
        every finite beat (i.e. landed in a NaN gap or off the data
        range entirely).
        """
        if self._times is None or len(self._times) == 0:
            return None
        finite_mask = np.isfinite(self._times) & np.isfinite(self._values)
        if not np.any(finite_mask):
            return None
        finite_positions = np.nonzero(finite_mask)[0]
        finite_times = self._times[finite_positions]
        # Binary search for the bracketing beats and compare distances.
        ins = int(np.searchsorted(finite_times, t_click))
        candidates = []
        if ins < len(finite_times):
            candidates.append(int(finite_positions[ins]))
        if ins > 0:
            candidates.append(int(finite_positions[ins - 1]))
        if not candidates:
            return None
        best = min(candidates, key=lambda idx: abs(self._times[idx] - t_click))
        if abs(self._times[best] - t_click) > self._click_tolerance_s:
            return None
        return best

    def _on_scene_mouse_clicked(self, ev) -> None:
        """Route scene clicks into Phase 14 (manual mark) or Phase 20 (annotation).

        Phase 14: left-click in manual-mark mode toggles an artifact at
        the nearest beat. Phase 20: left-click in annotation mode emits
        ``plot_clicked(t)`` so the panel can open the new-annotation
        dialog; right-click on an existing AnnotationMarker emits
        ``annotation_context(marker, screen_pos)`` for an edit / delete
        menu. Outside both modes the default ViewBox behaviour (pan,
        right-click context menu) is left untouched.
        """
        if self._times is None:
            return
        vb = self.getViewBox()
        scene_pos = ev.scenePos()
        if not self.sceneBoundingRect().contains(scene_pos):
            return
        data_pos = vb.mapSceneToView(scene_pos)
        t_click = float(data_pos.x())

        # Phase 20: right-click on an annotation marker fires the context
        # signal so the panel can pop edit / delete options.
        if ev.button() == Qt.RightButton:
            marker = self._marker_under(t_click)
            if marker is not None:
                ev.accept()
                screen_pos = ev.screenPos() if hasattr(ev, "screenPos") else None
                self.annotation_context.emit(marker, screen_pos)
            return

        if ev.button() != Qt.LeftButton:
            return

        # Phase 14: manual-mark mode click → toggle artifact at nearest beat.
        if self._manual_mark_mode:
            idx = self._nearest_finite_beat(t_click)
            if idx is None:
                return
            # Eating the event prevents the ViewBox from also interpreting
            # this click as the start of a rubber-band rectangle select.
            ev.accept()
            action = self._toggle_manual_at(idx)
            if action is not None:
                self.manual_artifact_changed.emit(int(idx), action)
            return

        # Phase 20: annotation-mode click → emit plot_clicked for the panel.
        if self._annotation_mode:
            ev.accept()
            self.plot_clicked.emit(t_click)

    def _toggle_manual_at(self, idx: int) -> str | None:
        """State-machine for a click on beat ``idx``. Returns the action tag.

        Rules (in order):
        1. Click on a manual-added → REMOVE it from added (undo a prior add)
        2. Click on a manual-removed (excluded algo) → REINSTATE algo
        3. Click on an algorithm artifact → EXCLUDE it
        4. Click on a free beat → ADD as manual artifact
        """
        if idx in self._manual_added_indices:
            self._manual_added_indices.discard(idx)
            self._refresh_manual_overlays()
            return "remove_manual"
        if idx in self._manual_removed_indices:
            self._manual_removed_indices.discard(idx)
            self._refresh_manual_overlays()
            return "include_algo"
        if idx in self._algorithm_indices:
            self._manual_removed_indices.add(idx)
            self._refresh_manual_overlays()
            return "exclude_algo"
        self._manual_added_indices.add(idx)
        self._refresh_manual_overlays()
        return "add"

    # ------------------------------------------------------------------
    # Phase 15 — Exclusion zones API
    # ------------------------------------------------------------------
    def set_exclusion_mode(self, enabled: bool) -> None:
        """Toggle drag-to-create exclusion mode on the underlying ViewBox.

        When ON, the next left-click-drag becomes a new ``ExclusionRegion``;
        when OFF, default pan behaviour is restored.
        """
        vb = self.getViewBox()
        if hasattr(vb, "set_exclusion_mode"):
            vb.set_exclusion_mode(enabled)

    def add_exclusion_zone(
        self, zone: ExclusionZone, *, emit: bool = True
    ) -> ExclusionRegion:
        """Materialise ``zone`` as an on-plot region and stash both.

        ``emit`` toggles the ``exclusion_zones_changed`` notification —
        callers loading from disk use ``emit=False`` so auto-restore
        doesn't immediately re-fire an auto-save loop.
        """
        region = ExclusionRegion(
            zone.start_t, zone.end_t, zone.reason, self._exclusion_color
        )
        # Keep the model in sync as the user drags the region edges; this
        # also doubles as selection (last-interacted region is "selected"
        # for the Delete shortcut). PyQtGraph's LinearRegionItem does not
        # expose a click signal, so we hijack the interaction signals.
        region.sigRegionChangeFinished.connect(
            lambda _r, z=zone, reg=region: self._on_region_edited(z, reg)
        )
        region.sigRegionChanged.connect(
            lambda _r, reg=region: self._on_region_clicked(reg)
        )
        self.addItem(region)
        self._exclusion_zones.append(zone)
        self._exclusion_regions.append(region)
        if emit:
            self.exclusion_zones_changed.emit()
        return region

    def remove_exclusion_zone(self, index: int) -> None:
        """Delete the zone at ``index`` (model + view + selection)."""
        if not (0 <= index < len(self._exclusion_zones)):
            return
        region = self._exclusion_regions.pop(index)
        self._exclusion_zones.pop(index)
        self.removeItem(region)
        if self._selected_exclusion_idx == index:
            self._selected_exclusion_idx = None
        elif (
            self._selected_exclusion_idx is not None
            and self._selected_exclusion_idx > index
        ):
            self._selected_exclusion_idx -= 1
        self.exclusion_zones_changed.emit()

    def clear_exclusion_zones(self) -> None:
        """Drop every zone (used on dataset switch before auto-restore)."""
        for region in self._exclusion_regions:
            self.removeItem(region)
        self._exclusion_zones.clear()
        self._exclusion_regions.clear()
        self._selected_exclusion_idx = None
        # No emit on clear — switching datasets is internal bookkeeping.

    def update_exclusion_reason(self, index: int, reason: str) -> None:
        """Edit the ``reason`` of the zone at ``index`` (auto-save will fire)."""
        if not (0 <= index < len(self._exclusion_zones)):
            return
        self._exclusion_zones[index].reason = str(reason or "")
        self._exclusion_regions[index].reason = self._exclusion_zones[index].reason
        self.exclusion_zones_changed.emit()

    def _on_exclusion_drag_finished(self, t0: float, t1: float) -> None:
        """Handle a finished left-button drag in exclusion mode."""
        if abs(t1 - t0) < MIN_EXCLUSION_WIDTH_S:
            return
        zone = ExclusionZone(
            start_t=float(t0),
            end_t=float(t1),
            start_beat_idx=self._beat_idx_for_time(t0),
            end_beat_idx=self._beat_idx_for_time(t1),
        )
        self.add_exclusion_zone(zone)

    def _on_region_edited(self, zone: ExclusionZone, region: ExclusionRegion) -> None:
        """Sync model.start_t/end_t after a drag-edit of an existing region."""
        lo, hi = region.getRegion()
        zone.start_t = float(min(lo, hi))
        zone.end_t = float(max(lo, hi))
        zone.start_beat_idx = self._beat_idx_for_time(zone.start_t)
        zone.end_beat_idx = self._beat_idx_for_time(zone.end_t)
        self.exclusion_zones_changed.emit()

    def _on_region_clicked(self, region: ExclusionRegion) -> None:
        """Click-to-select bookkeeping for Delete-key / context-menu ops."""
        try:
            self._selected_exclusion_idx = self._exclusion_regions.index(region)
        except ValueError:
            self._selected_exclusion_idx = None

    def _delete_selected_exclusion(self) -> None:
        """Bound to the Delete shortcut — drops the currently-selected zone."""
        if self._selected_exclusion_idx is None:
            return
        self.remove_exclusion_zone(self._selected_exclusion_idx)

    def _beat_idx_for_time(self, t: float) -> int | None:
        """Return the nearest beat index to ``t`` for provenance, or None.

        Best-effort: when no data is loaded or ``t`` falls outside the
        recording, returns None so persistence stores None rather than
        a misleading clamped value.
        """
        if self._times is None or len(self._times) == 0:
            return None
        finite = np.isfinite(self._times)
        if not np.any(finite):
            return None
        ts = self._times
        if t < ts[finite][0] or t > ts[finite][-1]:
            return None
        return int(np.searchsorted(ts, t))

    # ------------------------------------------------------------------
    # Phase 20: free-text annotations
    # ------------------------------------------------------------------
    def set_annotation_mode(self, enabled: bool) -> None:
        """Toggle whether left-clicks on the plot emit ``plot_clicked``."""
        self._annotation_mode = bool(enabled)

    def is_annotation_mode(self) -> bool:
        return self._annotation_mode

    def add_annotation_marker(self, t: float, text: str) -> AnnotationMarker:
        """Render one annotation as a vertical line + label. Returns the item."""
        marker = AnnotationMarker(t=t, text=text)
        self.addItem(marker)
        self._annotation_markers.append(marker)
        return marker

    def remove_annotation_marker(self, marker: AnnotationMarker) -> None:
        """Pop a marker from the overlay container + scene."""
        if marker in self._annotation_markers:
            self._annotation_markers.remove(marker)
        try:
            self.removeItem(marker)
        except (RuntimeError, ValueError):  # pragma: no cover - defensive
            pass

    def clear_annotation_markers(self) -> None:
        """Drop every annotation overlay (e.g. on dataset switch)."""
        for m in list(self._annotation_markers):
            try:
                self.removeItem(m)
            except (RuntimeError, ValueError):  # pragma: no cover - defensive
                pass
        self._annotation_markers.clear()

    def annotation_markers(self) -> list[AnnotationMarker]:
        return list(self._annotation_markers)

    def _marker_under(self, t_click: float) -> AnnotationMarker | None:
        """Return the nearest annotation marker within 1% of viewport width."""
        if not self._annotation_markers:
            return None
        x_lo, x_hi, _ = self._x_window()
        tolerance = max(1e-6, (x_hi - x_lo) * 0.01)
        best: tuple[float, AnnotationMarker] | None = None
        for m in self._annotation_markers:
            d = abs(m.annotation_t - t_click)
            if d <= tolerance and (best is None or d < best[0]):
                best = (d, m)
        return best[1] if best is not None else None

    def set_crosshair_visible(self, visible: bool) -> None:
        """Enable / disable the cursor-tracking crosshair."""
        self._crosshair_enabled = visible
        self._crosshair.setVisible(False)  # hidden until next mouse move

    def _on_scene_mouse_moved(self, scene_pos) -> None:
        """Map cursor scene pos → data coords, update crosshair + emit signal."""
        if not self._crosshair_enabled or self._times is None:
            return
        vb = self.getViewBox()
        if not self.sceneBoundingRect().contains(scene_pos):
            self._crosshair.setVisible(False)
            self.cursor_left.emit()
            return
        data_pos = vb.mapSceneToView(scene_pos)
        t_cursor = data_pos.x()
        v_cursor = self._value_at(t_cursor)
        self._crosshair.setPos(t_cursor)
        self._crosshair.setVisible(True)
        self.cursor_moved.emit(t_cursor, v_cursor)

    def _value_at(self, t_cursor: float) -> float:
        """Linearly-interpolated RR value at ``t_cursor``.

        Returns NaN if the cursor sits in a between-section gap (where
        the NaN sample placed by ``data_loader`` lives) or outside the
        loaded range. The MainWindow status-bar formatter uses NaN as
        the "show a dash" sentinel.
        """
        t = self._times
        if t is None or len(t) == 0:
            return float("nan")
        if t_cursor < t[0] or t_cursor > t[-1]:
            return float("nan")
        # np.interp ignores NaN in the y array — propagate NaN ourselves
        # so the readout honestly shows "no data here" over a gap.
        finite = np.isfinite(self._values)
        if not np.any(finite):
            return float("nan")
        # Find the nearest finite samples on either side; if the cursor
        # lies between two NaN samples, the closest samples themselves
        # will be NaN and we want to report NaN.
        idx = int(np.searchsorted(t, t_cursor))
        # Check the neighbours we'd use for interpolation
        lo = max(0, idx - 1)
        hi = min(len(t) - 1, idx)
        if not (finite[lo] and finite[hi]):
            return float("nan")
        return float(
            np.interp(t_cursor, [t[lo], t[hi]], [self._values[lo], self._values[hi]])
        )

    def clear_overlays(self) -> None:
        """Remove every section region, event marker, and artifact dot."""
        for r in self._section_regions:
            self.removeItem(r)
        for m in self._event_markers:
            self.removeItem(m)
        self._section_regions.clear()
        self._event_markers.clear()
        self._sections_by_label.clear()
        self.clear_artifacts()
        # Phase 15 - dataset switch must also drop the previous file's
        # exclusion zones; the PreprocessingPanel is responsible for
        # re-loading the next dataset's zones from disk.
        self.clear_exclusion_zones()
        # Phase 20: annotations are per-dataset; dropping overlays on
        # dataset switch wipes the old ones so the panel can re-add the
        # new dataset's markers from disk without dupes.
        self.clear_annotation_markers()

    def highlight_section(self, label: str | None) -> None:
        """Boost the band alpha for one section, dim the rest.

        Passing ``None`` clears all highlighting. Called by MainWindow
        when the user picks a different section in the sidebar.
        """
        for name, region in self._sections_by_label.items():
            region.set_highlighted(name == label)

    def set_color_scheme(self, scheme) -> None:
        """Re-skin every existing plot element from ``scheme``.

        Iterates the live curve, artifact overlay, section regions and
        event markers and asks each to re-paint with the matching colour
        from the :class:`~rrational.gui.color_scheme.ColorScheme`.
        Items added AFTER this call still use their own constructor
        colours — :meth:`add_section_region` / :meth:`add_event_marker`
        callers should stash the current scheme and re-apply if needed.
        """
        from rrational.gui.color_scheme import ColorScheme  # noqa: F401

        # RR curve pen
        self._curve.setPen(pg.mkPen(scheme.rr_line, width=1))
        # Artifact dots
        self._artifact_overlay.apply_color(QColor(scheme.artifact))
        # Phase 14: manual + excluded overlays share the artifact colour
        self._manual_overlay.apply_color(QColor(scheme.artifact))
        self._excluded_overlay.apply_color(QColor(scheme.artifact))
        # Section bands
        fill = QColor(scheme.section_border)
        border = QColor(scheme.section_border)
        for region in self._section_regions:
            region.apply_colors(fill, border)
        # Event markers
        evt_color = QColor(scheme.event_marker)
        for marker in self._event_markers:
            marker.apply_color(evt_color)
        # Exclusion zones — store the colour so future zones inherit it,
        # then re-skin every existing region.
        excl_color = QColor(getattr(scheme, "exclusion", EXCLUSION_COLOR))
        self._exclusion_color = excl_color
        for region in self._exclusion_regions:
            region.apply_color(excl_color)

    def zoom_to_range(
        self, t_start: float, t_end: float, padding_frac: float = 0.05
    ) -> None:
        """Zoom the X-axis to ``[t_start, t_end]`` with a small margin."""
        pad = (t_end - t_start) * padding_frac
        self.getViewBox().setXRange(t_start - pad, t_end + pad, padding=0)

    @staticmethod
    def _color_for_index(idx: int) -> QColor:
        return QColor(_SECTION_PALETTE[idx % len(_SECTION_PALETTE)])

    # ------------------------------------------------------------------
    # Pan / zoom / jump — public so MainWindow's toolbar buttons and the
    # global eventFilter can invoke them.
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
        """Jump viewport to the first ``JUMP_WINDOW_S`` seconds.

        Fixed-window semantics — not "preserve current width" — so the
        action is visibly distinct from "show everything", which would
        otherwise be a no-op when the user is already fully zoomed out.
        """
        if self._times is None:
            return
        # First non-NaN timestamp (NaN samples mark inter-section gaps).
        finite = np.isfinite(self._times)
        t = self._times[finite]
        end = min(t[0] + JUMP_WINDOW_S, t[-1])
        self.getViewBox().setXRange(t[0], end, padding=0)

    def jump_end(self) -> None:
        """Jump viewport to the last ``JUMP_WINDOW_S`` seconds."""
        if self._times is None:
            return
        finite = np.isfinite(self._times)
        t = self._times[finite]
        start = max(t[-1] - JUMP_WINDOW_S, t[0])
        self.getViewBox().setXRange(start, t[-1], padding=0)
