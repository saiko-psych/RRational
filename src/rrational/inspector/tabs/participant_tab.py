"""Participant tab — per-subject deep-dive (Phase 22.2 + Phase 23B).

Streamlit-style focused per-participant view. Mirrors the workflow of
``src/rrational/gui/tabs/participant.py`` (Streamlit reference) but in
the PyQt inspector shell:

- Top bar: a participant dropdown listing every loaded dataset's stem,
  plus Previous / Next arrow buttons and a "Showing X of Y" status.
- Header metrics row (Phase 23B): "Participant | Group | Sequence |
  Beats | Duration | Duplicates" — pulled from the active dataset +
  ParticipantsTab metadata. Mirrors the Streamlit per-participant view.
- Left dock: a vertical list of the active participant's sections.
  Clicking a row zooms the plot to that section; the per-row
  "Validate" button records validation in ``{pid}_section_validations.yml``
  (Phase 23B — replaces the Phase 22.2 status-bar no-op).
- Center: the same ``RRPlotWidget`` the Browse tab uses (timeline +
  overlays + crosshair + keyboard nav).
- Right dock: the same ``PreprocessingPanel`` the Browse tab uses
  (workflow stepper + detect / correct / save buttons + Phase 14
  manual marking + Phase 15 exclusion zones + Phase 16 section edit
  mode + Phase 20 annotations).
- Bottom: an NN-intervals summary line — "X corrected of Y total NN
  intervals, artifact rate Z%" — refreshed after every preprocessing
  result.

Splits the monolithic Browse tab into a single-participant focus mode
without duplicating the heavy widgets. The dropdown drives the
workspace's active dataset via ``main_window.set_active_dataset(idx)``;
all the other tabs (and the original Browse tab itself) stay in lock-
step because they share the same notification fan-out.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import numpy as np
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QComboBox,
    QDockWidget,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rrational.inspector.plot_widget import RRPlotWidget
from rrational.inspector.tabs.base import InspectorTab

if TYPE_CHECKING:
    from rrational.inspector.data_loader import Dataset, InspectorData

# UserRole tag so list rows know which section they map to without
# leaning on row index (which is brittle if rows are ever reordered).
_ROLE_SECTION_NAME = Qt.UserRole + 1

# UserRole tag carrying the (t_start, t_end) tuple for a quality-issue
# row, so double-clicking zooms the plot to the offending segment.
_ROLE_QUALITY_RANGE = Qt.UserRole + 2

# Unicode check mark used to flag validated sections in the list. NOT
# an emoji — a plain U+2713 glyph that renders in any font that ships
# with a basic Latin/Symbols subset.
_VALIDATED_PREFIX = "✓ "

# Quality-issue detection thresholds (Phase 24C-retry).
# - Time gap: 5 s between consecutive beats is well past any plausible
#   RR interval (HR < 12 bpm) — almost certainly a sensor dropout or a
#   cross-section join.
# - Rolling CV: 30-beat window, 0.30 CV threshold mirrors the Streamlit
#   gui/diagnostics' "high variability" highlight band.
_QUALITY_GAP_THRESHOLD_S = 5.0
_QUALITY_CV_WINDOW = 30
_QUALITY_CV_THRESHOLD = 0.30


def _detect_time_gaps(
    t: np.ndarray, threshold_s: float
) -> list[tuple[float, float, float]]:
    """Return (gap_duration_s, t_start, t_end) for every consecutive pair
    of finite timestamps whose difference is >= ``threshold_s``.

    NaN-valued timestamps are skipped so inter-section gap markers
    (data_loader inserts NaNs there) don't generate false positives.
    """
    if t.size < 2:
        return []
    finite = np.isfinite(t)
    if not finite.any():
        return []
    t_clean = t[finite]
    if t_clean.size < 2:
        return []
    diffs = np.diff(t_clean)
    flagged = np.where(diffs >= threshold_s)[0]
    out: list[tuple[float, float, float]] = []
    for idx in flagged:
        gap_t_start = float(t_clean[idx])
        gap_t_end = float(t_clean[idx + 1])
        gap_s = float(diffs[idx])
        out.append((gap_s, gap_t_start, gap_t_end))
    return out


def _detect_high_variability_segments(
    t: np.ndarray,
    v: np.ndarray,
    window: int,
    cv_threshold: float,
) -> list[tuple[float, float, float]]:
    """Sliding rolling-CV detector: return list of (t_start, t_end, cv)
    for merged segments whose ``window``-beat CV (std/|mean|) exceeds
    ``cv_threshold``.

    Adjacent flagged windows are coalesced into one segment whose CV is
    the max across the constituent windows — keeps the UI list short
    when the recording has long noisy stretches.
    """
    if v.size < window or t.size != v.size:
        return []
    finite_mask = np.isfinite(v) & np.isfinite(t)
    if not finite_mask.any():
        return []
    t_clean = t[finite_mask]
    v_clean = v[finite_mask]
    n = v_clean.size
    if n < window:
        return []

    # Vectorised rolling stats via cumulative sums — keeps this fast on
    # the multi-hour recordings the inspector occasionally loads.
    csum = np.concatenate(([0.0], np.cumsum(v_clean)))
    csum_sq = np.concatenate(([0.0], np.cumsum(v_clean.astype(np.float64) ** 2)))
    n_windows = n - window + 1
    sums = csum[window:] - csum[:n_windows]
    sums_sq = csum_sq[window:] - csum_sq[:n_windows]
    means = sums / window
    # Population variance (matches np.std(...,ddof=0)) — close enough to
    # std/mean for "is this stretch noisy?" gating.
    var = np.maximum(0.0, sums_sq / window - means**2)
    stds = np.sqrt(var)
    with np.errstate(divide="ignore", invalid="ignore"):
        cvs = np.where(np.abs(means) > 1e-9, stds / np.abs(means), 0.0)

    flagged = cvs > cv_threshold
    if not flagged.any():
        return []

    # Merge adjacent True window indices into contiguous runs.
    segments: list[tuple[float, float, float]] = []
    in_run = False
    run_start = 0
    run_max_cv = 0.0
    for i, hit in enumerate(flagged):
        if hit and not in_run:
            in_run = True
            run_start = i
            run_max_cv = float(cvs[i])
        elif hit and in_run:
            run_max_cv = max(run_max_cv, float(cvs[i]))
        elif not hit and in_run:
            run_end = i - 1
            seg_t_start = float(t_clean[run_start])
            seg_t_end = float(t_clean[min(run_end + window - 1, n - 1)])
            segments.append((seg_t_start, seg_t_end, run_max_cv))
            in_run = False
    if in_run:
        run_end = len(flagged) - 1
        seg_t_start = float(t_clean[run_start])
        seg_t_end = float(t_clean[min(run_end + window - 1, n - 1)])
        segments.append((seg_t_start, seg_t_end, run_max_cv))
    return segments


class ParticipantTab(InspectorTab):
    """Single-participant deep-dive: dropdown + plot + sections + preprocessing."""

    TAB_LABEL = "Participant"

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(main_window, parent)
        # Cache of the current participant's loaded section validations
        # ({section_name: {validated_at, validator}, ...}). Populated by
        # _reload_validations on every dataset switch.
        self._section_validations: dict[str, dict[str, Any]] = {}
        self._build()
        # Populate from whatever the workspace currently holds (the tab
        # may be constructed AFTER datasets have been loaded, e.g. when
        # the user adds the tab partway through a session).
        self.on_workspace_changed()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build(self) -> None:
        # Mirror BrowseTab's nested QMainWindow trick so we can host
        # real QDockWidgets — gives users tear-off panels and Qt's
        # built-in saveState / restoreState geometry persistence.
        self._dock_host = QMainWindow(self)
        self._dock_host.setWindowFlags(Qt.Widget)

        # ----- Top bar: participant picker + arrows + status --------------
        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(8, 4, 8, 4)

        top_layout.addWidget(QLabel("<b>Participant:</b>"))

        self._participant_combo = QComboBox()
        self._participant_combo.setMinimumWidth(200)
        self._participant_combo.setToolTip(
            "Choose which loaded recording to inspect. The arrow buttons "
            "step through participants in workspace order."
        )
        # currentIndexChanged fires on both programmatic AND user-driven
        # changes; we filter out the programmatic ones via a guard flag
        # so rebuilding the dropdown doesn't bounce the active dataset.
        self._suppress_combo_signal = False
        self._participant_combo.currentIndexChanged.connect(self._on_combo_changed)
        top_layout.addWidget(self._participant_combo)

        self._prev_btn = QPushButton("<- Previous participant")
        self._prev_btn.setToolTip("Switch to the previous loaded recording")
        self._prev_btn.clicked.connect(self._on_prev_clicked)
        top_layout.addWidget(self._prev_btn)

        self._next_btn = QPushButton("Next participant ->")
        self._next_btn.setToolTip("Switch to the next loaded recording")
        self._next_btn.clicked.connect(self._on_next_clicked)
        top_layout.addWidget(self._next_btn)

        self._status_label = QLabel("No participants loaded.")
        self._status_label.setStyleSheet("color: #555; padding-left: 12px;")
        top_layout.addWidget(self._status_label)
        top_layout.addStretch()

        # ----- Header metrics row (Phase 23B) -----------------------------
        # Streamlit's per-participant view surfaces participant id, group,
        # sequence, beat counts, duration, and duplicate count alongside
        # the plot. The PyQt port mirrors that with a flat field/value
        # row separated by QFrame.HLine spacers so the header stays
        # scannable at a glance.
        self._header_metrics_bar = QWidget()
        self._header_metrics_layout = QHBoxLayout(self._header_metrics_bar)
        self._header_metrics_layout.setContentsMargins(8, 4, 8, 4)
        self._header_metrics_layout.setSpacing(8)
        # Per-field QLabel handles so _refresh_header_metrics can mutate
        # values in place without rebuilding the row (keeps Qt layout
        # geometry stable across dataset switches).
        self._hdr_participant_value = QLabel("-")
        self._hdr_group_value = QLabel("-")
        self._hdr_sequence_value = QLabel("-")
        self._hdr_beats_value = QLabel("-")
        self._hdr_duration_value = QLabel("-")
        self._hdr_duplicates_value = QLabel("-")
        self._build_header_metrics_row()

        # ----- Plot + bottom NN summary in the center --------------------
        self._plot = RRPlotWidget()
        self._plot.setFocusPolicy(Qt.StrongFocus)

        self._nn_summary = QLabel("No artifact detection run yet on this participant.")
        self._nn_summary.setStyleSheet(
            "color: #555; padding: 4px 8px; background: #f4f4f4; "
            "border-top: 1px solid #ccc;"
        )
        self._nn_summary.setWordWrap(True)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.addWidget(top_bar)
        center_layout.addWidget(self._header_metrics_bar)
        center_layout.addWidget(self._plot, stretch=1)
        center_layout.addWidget(self._nn_summary)
        self._dock_host.setCentralWidget(center)

        # ----- Left dock: sections list ----------------------------------
        self._sections_list = QListWidget()
        self._sections_list.setToolTip(
            "Click a section to zoom the plot to it. Use the per-row "
            "Validate button to mark the section as reviewed. Right-click "
            "a row to clear validation."
        )
        self._sections_list.itemClicked.connect(self._on_section_clicked)
        # Phase 23B: context menu lets the user clear a validation.
        self._sections_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._sections_list.customContextMenuRequested.connect(
            self._on_section_context_menu
        )

        sections_container = QWidget()
        sections_layout = QVBoxLayout(sections_container)
        sections_layout.setContentsMargins(4, 4, 4, 4)
        sections_layout.addWidget(QLabel("<b>Sections</b>"))
        sections_layout.addWidget(self._sections_list)

        # ----- Quality issues group (Phase 24C-retry) -------------------
        # Collapsible QGroupBox sitting below the section list. Holds
        # three short QListWidgets (time gaps, high-variability segments,
        # exact-duplicate count). Each list row carries a (t_start, t_end)
        # range in its UserRole so double-click zooms the plot to it.
        self._quality_box = QGroupBox("Quality issues")
        self._quality_box.setCheckable(True)
        self._quality_box.setChecked(False)  # start collapsed
        quality_layout = QVBoxLayout(self._quality_box)
        quality_layout.setContentsMargins(6, 6, 6, 6)
        quality_layout.setSpacing(4)

        quality_layout.addWidget(QLabel("<b>Time gaps (>= 5 s)</b>"))
        self._quality_gaps_list = QListWidget()
        self._quality_gaps_list.setMaximumHeight(80)
        self._quality_gaps_list.setToolTip(
            "Consecutive beats whose timestamp difference exceeds 5 s. "
            "Double-click a row to zoom the plot to the gap."
        )
        self._quality_gaps_list.itemDoubleClicked.connect(
            self._on_quality_item_activated
        )
        quality_layout.addWidget(self._quality_gaps_list)

        quality_layout.addWidget(
            QLabel("<b>High variability (CV > 0.30, 30-beat window)</b>")
        )
        self._quality_var_list = QListWidget()
        self._quality_var_list.setMaximumHeight(80)
        self._quality_var_list.setToolTip(
            "Sliding 30-beat windows where coefficient of variation "
            "(std/mean) exceeds 0.30. Adjacent flagged windows are merged. "
            "Double-click to zoom the plot to the segment."
        )
        self._quality_var_list.itemDoubleClicked.connect(
            self._on_quality_item_activated
        )
        quality_layout.addWidget(self._quality_var_list)

        quality_layout.addWidget(QLabel("<b>Duplicates</b>"))
        self._quality_dup_list = QListWidget()
        self._quality_dup_list.setMaximumHeight(80)
        self._quality_dup_list.setToolTip(
            "Count of exact-duplicate RR values across the recording."
        )
        quality_layout.addWidget(self._quality_dup_list)

        # Collapse-toggle wired to hide the inner widgets so the group
        # box shrinks to just its title bar when unchecked.
        self._quality_box.toggled.connect(self._on_quality_box_toggled)
        # Sync the initial collapsed state once.
        self._on_quality_box_toggled(False)
        sections_layout.addWidget(self._quality_box)

        self._sections_dock = QDockWidget("Sections", self._dock_host)
        self._sections_dock.setObjectName("ParticipantTab.SectionsDock")
        self._sections_dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        self._sections_dock.setWidget(sections_container)
        self._dock_host.addDockWidget(Qt.LeftDockWidgetArea, self._sections_dock)

        # ----- Right dock: preprocessing panel ---------------------------
        # Deferred import to keep importing participant_tab.py cheap and
        # to dodge the NeuroKit2 transitive dependency at module-load
        # time. The panel reads ``parent._plot`` to wire its plot
        # signals, so passing ``self`` (where ``self._plot`` is already
        # live) is sufficient.
        from rrational.inspector.tabs.preprocessing_panel import PreprocessingPanel

        self._preprocessing_panel = PreprocessingPanel(self._main_window, self)

        # Wrap a refresh of the bottom summary around the panel's
        # detect-result hook. We monkey-style-wrap by listening to the
        # same attribute the panel itself updates — _last_result — but
        # to keep things simple we just re-render after every plot
        # mutation the panel could trigger. The cheapest hook is the
        # exclusion_zones_changed signal which the panel fires on most
        # of its UI actions; combined with our own re-render in
        # ``on_active_dataset_changed`` that covers every transition.
        self._plot.exclusion_zones_changed.connect(self._refresh_nn_summary)

        self._preprocessing_dock = QDockWidget("Preprocessing", self._dock_host)
        self._preprocessing_dock.setObjectName("ParticipantTab.PreprocessingDock")
        self._preprocessing_dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        self._preprocessing_dock.setWidget(self._preprocessing_panel)
        self._dock_host.addDockWidget(Qt.RightDockWidgetArea, self._preprocessing_dock)

        # ----- Outer layout: just hosts the dock-host --------------------
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._dock_host)

    def _build_header_metrics_row(self) -> None:
        """Populate the header metrics row with label/value pairs + separators.

        Done once during _build; subsequent updates mutate the value
        labels in place via _refresh_header_metrics.
        """
        fields: list[tuple[str, QLabel]] = [
            ("Participant", self._hdr_participant_value),
            ("Group", self._hdr_group_value),
            ("Sequence", self._hdr_sequence_value),
            ("Beats", self._hdr_beats_value),
            ("Duration", self._hdr_duration_value),
            ("Duplicates", self._hdr_duplicates_value),
        ]
        for i, (name, value_label) in enumerate(fields):
            if i > 0:
                sep = QFrame()
                sep.setFrameShape(QFrame.VLine)
                sep.setFrameShadow(QFrame.Sunken)
                self._header_metrics_layout.addWidget(sep)
            name_label = QLabel(f"<b>{name}:</b>")
            name_label.setStyleSheet("color: #333;")
            value_label.setStyleSheet("color: #555;")
            self._header_metrics_layout.addWidget(name_label)
            self._header_metrics_layout.addWidget(value_label)
        self._header_metrics_layout.addStretch()

    # ------------------------------------------------------------------
    # InspectorTab hooks
    # ------------------------------------------------------------------
    def tab_label_state(self) -> str:
        idx = self._main_window._active_idx
        datasets = self._main_window._datasets
        if not datasets:
            return "(none selected)"
        if idx is None or not (0 <= idx < len(datasets)):
            return "(none selected)"
        stem = self._stem_for(datasets[idx])
        meta = self._participant_meta(stem)
        group = (meta.get("group") or "").strip()
        sequence = (meta.get("sequence") or "").strip()
        if group and sequence:
            return f"({stem} / {group} / {sequence})"
        if group:
            return f"({stem} / {group})"
        return f"({stem})"

    def on_workspace_changed(self) -> None:
        """Rebuild the dropdown from ``main_window._datasets``."""
        datasets = self._main_window._datasets
        self._suppress_combo_signal = True
        try:
            self._participant_combo.clear()
            for ds in datasets:
                self._participant_combo.addItem(self._stem_for(ds))
            # Re-sync the dropdown to the active dataset (if any) so the
            # user doesn't see a stale selection after a workspace edit.
            idx = self._main_window._active_idx
            if idx is not None and 0 <= idx < self._participant_combo.count():
                self._participant_combo.setCurrentIndex(idx)
        finally:
            self._suppress_combo_signal = False
        self._refresh_buttons_and_status()
        # If there's no active dataset (workspace empty) clear the
        # downstream UI so we don't leave stale section rows / plot
        # curves around.
        if not datasets or self._main_window._active_idx is None:
            self._clear_for_empty_state()

    def on_active_dataset_changed(self, data: "InspectorData | None") -> None:
        # Always notify the panel — it has bookkeeping that runs even
        # when ``data is None`` (clearing toggles, disabling Detect).
        self._preprocessing_panel.on_active_dataset_changed(data)
        if data is None:
            self._clear_for_empty_state()
            return
        idx = self._main_window._active_idx
        datasets = self._main_window._datasets
        if idx is None or not (0 <= idx < len(datasets)):
            return
        ds = datasets[idx]
        # Keep the dropdown in sync with whoever else may have changed
        # the active dataset (e.g. the Browse tab tree).
        self._suppress_combo_signal = True
        try:
            self._participant_combo.setCurrentIndex(idx)
        finally:
            self._suppress_combo_signal = False
        # Phase 23B: load this participant's section validations BEFORE
        # rendering the section list so each row shows the validated
        # state on first paint.
        self._reload_validations(ds)
        self._render_dataset(ds)
        self._refresh_buttons_and_status()
        self._refresh_nn_summary()
        self._refresh_header_metrics(ds)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _render_dataset(self, ds: "Dataset") -> None:
        """Push the dataset onto the plot + rebuild the section list."""
        self._plot.set_data(ds.data)
        for meta in ds.data.sections:
            self._plot.add_section_region(meta)
        for ev in ds.data.events:
            self._plot.add_event_marker(ev)
        self._rebuild_sections_list(ds)
        self._rebuild_quality_lists(ds)
        self._plot.setFocus()

    def _rebuild_sections_list(self, ds: "Dataset") -> None:
        self._sections_list.clear()
        for meta in ds.data.sections:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(4, 2, 4, 2)
            is_validated = meta.name in self._section_validations
            prefix = _VALIDATED_PREFIX if is_validated else ""
            # Validated rows render the name in a darker green so the
            # check mark + colour together survive any single rendering
            # quirk (some Linux fonts swallow U+2713).
            name_colour = "#2a7a2a" if is_validated else "#222"
            label = QLabel(
                f"<span style='color:{name_colour};'>{prefix}{meta.name}</span>  "
                f"<span style='color:#888;'>"
                f"({meta.beat_count} beats, "
                f"{meta.t_end - meta.t_start:.0f}s)</span>"
            )
            label.setTextFormat(Qt.RichText)
            row_layout.addWidget(label, stretch=1)
            validate_btn = QPushButton("Validate")
            validate_btn.setToolTip(
                f"Mark section '{meta.name}' as reviewed. Writes to "
                f"{{participant_id}}_section_validations.yml in the "
                "active project's processed folder."
            )
            # Default-arg binds the CURRENT name so a future rename
            # doesn't shadow the closure variable.
            validate_btn.clicked.connect(
                lambda _checked=False, name=meta.name: self._on_validate_section(name)
            )
            row_layout.addWidget(validate_btn)

            item = QListWidgetItem(self._sections_list)
            item.setData(_ROLE_SECTION_NAME, meta.name)
            item.setSizeHint(row_widget.sizeHint())
            self._sections_list.addItem(item)
            self._sections_list.setItemWidget(item, row_widget)

    def _clear_for_empty_state(self) -> None:
        """Wipe plot + sections list when there's no active dataset."""
        self._plot.clear_overlays()
        self._plot._curve.clear()
        self._plot._times = None
        self._plot._values = None
        self._sections_list.clear()
        self._quality_gaps_list.clear()
        self._quality_var_list.clear()
        self._quality_dup_list.clear()
        self._nn_summary.setText("No artifact detection run yet on this participant.")
        self._section_validations = {}
        # Reset the metrics row to placeholder dashes so the user can
        # tell at a glance that nothing is loaded.
        for value_label in (
            self._hdr_participant_value,
            self._hdr_group_value,
            self._hdr_sequence_value,
            self._hdr_beats_value,
            self._hdr_duration_value,
            self._hdr_duplicates_value,
        ):
            value_label.setText("-")

    def _refresh_buttons_and_status(self) -> None:
        datasets = self._main_window._datasets
        n = len(datasets)
        idx = self._main_window._active_idx
        self._prev_btn.setEnabled(n > 1 and idx is not None and idx > 0)
        self._next_btn.setEnabled(n > 1 and idx is not None and idx < n - 1)
        self._participant_combo.setEnabled(n > 0)
        if n == 0:
            self._status_label.setText("No participants loaded.")
        elif idx is None:
            self._status_label.setText(f"Showing none of {n}")
        else:
            self._status_label.setText(f"Showing participant {idx + 1} of {n}")

    def _refresh_nn_summary(self) -> None:
        """Update the bottom NN-intervals summary from the panel's result."""
        result = getattr(self._preprocessing_panel, "_last_result", None)
        if result is None:
            self._nn_summary.setText(
                "No artifact detection run yet on this participant."
            )
            return
        # ``total`` is the number of NN intervals examined; ``len(indices)``
        # is the number of beats flagged + (optionally) corrected by the
        # Kubios algorithm. ``rate`` is already 0.0-1.0.
        total = int(getattr(result, "total", 0))
        corrected = int(len(getattr(result, "indices", [])))
        rate_pct = float(getattr(result, "rate", 0.0)) * 100.0
        self._nn_summary.setText(
            f"{corrected} corrected of {total} total NN intervals, "
            f"artifact rate {rate_pct:.2f}%"
        )

    def _refresh_header_metrics(self, ds: "Dataset") -> None:
        """Repopulate the header metrics row from ``ds`` + participants.yml.

        Beats / Retained / Duration / Duplicates are derived directly
        from the InspectorData arrays so we don't need to block on
        PreparationSummary (Phase 23A ships that separately). Group +
        Sequence come from the ParticipantsTab — same source the
        Streamlit per-participant view uses.
        """
        stem = self._stem_for(ds)
        meta = self._participant_meta(stem)
        group = (meta.get("group") or "").strip() or "-"
        sequence = (meta.get("sequence") or "").strip() or "-"

        v = ds.data.v
        # Finite beats = non-NaN samples. NaNs in v mark inter-section
        # gaps that data_loader inserts so the timeline stays
        # monotonically non-decreasing.
        finite_mask = np.isfinite(v)
        total_beats = int(finite_mask.sum())
        # Phase 23A owns PreparationSummary; we fall back to "retained
        # == total" and "duplicates == 0" until that ships and tells us
        # otherwise. The header still reads correctly because the worst
        # case is just the absence of those two extra stats.
        retained = total_beats
        duplicates = 0
        # Duration in minutes from the first/last finite timestamp.
        if total_beats > 0:
            t_finite = ds.data.t[np.isfinite(ds.data.t)]
            duration_s = float(t_finite[-1] - t_finite[0]) if t_finite.size else 0.0
        else:
            duration_s = 0.0
        duration_min = duration_s / 60.0

        self._hdr_participant_value.setText(stem)
        self._hdr_group_value.setText(group)
        self._hdr_sequence_value.setText(sequence)
        self._hdr_beats_value.setText(f"{total_beats} ({retained} retained)")
        self._hdr_duration_value.setText(f"{duration_min:.1f} min")
        self._hdr_duplicates_value.setText(str(duplicates))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _stem_for(ds: "Dataset") -> str:
        """Streamlit-style stem: drop any file suffix, fall back to ds.name."""
        if ds.path is not None:
            return ds.path.stem
        # Synthetic / unsaved datasets carry a name like "0012MEBE.rrational";
        # strip the last suffix so the dropdown reads like the participant ID.
        name = ds.name
        if "." in name:
            return name.rsplit(".", 1)[0]
        return name

    def _participant_meta(self, pid: str) -> dict[str, Any]:
        """Look up ``pid``'s entry on the ParticipantsTab (empty if none).

        Tolerates the tab being missing entirely (older test scaffolds
        that build ParticipantTab without a full MainWindow), and the
        participant simply not being listed yet.
        """
        pt = getattr(self._main_window, "_participants_tab", None)
        if pt is None:
            return {}
        # ParticipantsTab exposes both the public ``participants``
        # property (returns a copy) and the underlying ``_participants``
        # dict. The public copy is safer — protects against future code
        # that might mutate the returned dict in place.
        try:
            all_p = pt.participants
        except AttributeError:
            all_p = getattr(pt, "_participants", {}) or {}
        return all_p.get(pid, {}) or {}

    def _project_path(self):
        """Active project's filesystem path, or None for the global config."""
        proj = getattr(self._main_window, "_project", None)
        return proj.project_path if proj is not None else None

    # ------------------------------------------------------------------
    # Section-validation persistence (Phase 23B)
    # ------------------------------------------------------------------
    def _reload_validations(self, ds: "Dataset") -> None:
        """Refresh self._section_validations from ``{pid}_section_validations.yml``.

        Called on every dataset switch so the freshly-loaded participant's
        validations drive the section list's check-mark prefixes.
        """
        from rrational.gui.persistence import load_section_validations

        stem = self._stem_for(ds)
        try:
            saved = load_section_validations(
                participant_id=stem,
                project_path=self._project_path(),
            )
        except Exception:  # pragma: no cover - defensive
            saved = None
        if not saved or "sections" not in saved:
            self._section_validations = {}
            return
        self._section_validations = dict(saved.get("sections") or {})

    def _persist_validations(self, stem: str) -> None:
        """Write ``self._section_validations`` back to the YAML file."""
        from rrational.gui.persistence import save_section_validations

        meta = self._participant_meta(stem)
        group = (meta.get("group") or "").strip()
        save_section_validations(
            participant_id=stem,
            group=group,
            section_validations=self._section_validations,
            project_path=self._project_path(),
        )

    # ------------------------------------------------------------------
    # Quality issues (Phase 24C-retry)
    # ------------------------------------------------------------------
    def _on_quality_box_toggled(self, checked: bool) -> None:
        """Show/hide the quality lists when the group box is toggled."""
        for w in (
            self._quality_gaps_list,
            self._quality_var_list,
            self._quality_dup_list,
        ):
            w.setVisible(checked)
        # Also hide the inline section labels — find children with the
        # matching <b> heading text. Cheapest path: walk the group box's
        # immediate children.
        for child in self._quality_box.findChildren(QLabel):
            child.setVisible(checked)

    def _rebuild_quality_lists(self, ds: "Dataset") -> None:
        """Recompute + repopulate the three quality QListWidgets."""
        self._quality_gaps_list.clear()
        self._quality_var_list.clear()
        self._quality_dup_list.clear()

        t = np.asarray(ds.data.t, dtype=np.float64)
        v = np.asarray(ds.data.v, dtype=np.float64)
        if t.size == 0:
            return
        # Use the first finite timestamp as t_start so relative offsets
        # don't get thrown off by leading NaNs (data_loader inserts those
        # between sections).
        finite_t_mask = np.isfinite(t)
        if not finite_t_mask.any():
            return
        t_origin = float(t[finite_t_mask][0])

        # ---- Time gaps ----
        gaps = _detect_time_gaps(t, _QUALITY_GAP_THRESHOLD_S)
        for i, (gap_s, gap_t_start, gap_t_end) in enumerate(gaps, start=1):
            rel = gap_t_start - t_origin
            mm = int(rel // 60)
            ss = int(rel % 60)
            label = f"Gap {i}: {gap_s:.1f}s at {mm:02d}:{ss:02d}"
            item = QListWidgetItem(label)
            item.setData(_ROLE_QUALITY_RANGE, (float(gap_t_start), float(gap_t_end)))
            self._quality_gaps_list.addItem(item)

        # ---- High-variability segments ----
        segments = _detect_high_variability_segments(
            t, v, window=_QUALITY_CV_WINDOW, cv_threshold=_QUALITY_CV_THRESHOLD
        )
        for i, (seg_t_start, seg_t_end, cv) in enumerate(segments, start=1):
            duration = seg_t_end - seg_t_start
            label = f"Segment {i}: {duration:.1f}s, CV {cv:.2f}"
            item = QListWidgetItem(label)
            item.setData(_ROLE_QUALITY_RANGE, (float(seg_t_start), float(seg_t_end)))
            self._quality_var_list.addItem(item)

        # ---- Duplicates ----
        finite_v = v[np.isfinite(v)]
        if finite_v.size:
            dup_count = int(finite_v.size - len(set(finite_v.tolist())))
            if dup_count > 0:
                self._quality_dup_list.addItem(
                    QListWidgetItem(f"{dup_count} exact duplicate RR values")
                )

    def _on_quality_item_activated(self, item: QListWidgetItem) -> None:
        """Double-click handler: zoom the plot to the offending range."""
        rng = item.data(_ROLE_QUALITY_RANGE)
        if not rng:
            return
        t_start, t_end = float(rng[0]), float(rng[1])
        # padding=0.1 mirrors the task spec; using setXRange directly
        # (RRPlotWidget IS a pg.PlotWidget) keeps the call cheap and the
        # zoom symmetric on both sides of the segment.
        self._plot.setXRange(t_start, t_end, padding=0.1)
        self._plot.setFocus()

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_combo_changed(self, idx: int) -> None:
        if self._suppress_combo_signal:
            return
        if idx < 0:
            return
        if not (0 <= idx < len(self._main_window._datasets)):
            return
        if self._main_window._active_idx == idx:
            return
        self._main_window.set_active_dataset(idx)

    def _on_prev_clicked(self) -> None:
        idx = self._main_window._active_idx
        if idx is None or idx <= 0:
            return
        self._main_window.set_active_dataset(idx - 1)

    def _on_next_clicked(self) -> None:
        idx = self._main_window._active_idx
        datasets = self._main_window._datasets
        if idx is None or idx >= len(datasets) - 1:
            return
        self._main_window.set_active_dataset(idx + 1)

    def _on_section_clicked(self, item: QListWidgetItem) -> None:
        name = item.data(_ROLE_SECTION_NAME)
        if name is None:
            return
        idx = self._main_window._active_idx
        if idx is None:
            return
        ds = self._main_window._datasets[idx]
        meta = next((s for s in ds.data.sections if s.name == name), None)
        if meta is None:
            return
        self._plot.zoom_to_range(meta.t_start, meta.t_end, padding_frac=0.02)
        self._plot.highlight_section(name)
        self._plot.setFocus()
        self._main_window.statusBar().showMessage(
            f"Section '{name}': {meta.beat_count} beats, "
            f"{meta.t_end - meta.t_start:.1f}s",
            3000,
        )

    def _on_validate_section(self, name: str) -> None:
        """Confirm + persist a section validation (Phase 23B).

        Pops a small confirmation dialog (suppressed in test_mode) and
        on Yes records the section in the participant's
        ``_section_validations.yml`` with a minimal schema:
        ``{"validated_at": ISO timestamp, "validator": "inspector"}``.
        Avoids duplicating the Streamlit dialog's full disambiguation
        flow — the inspector's plot + boundary-editing already covers
        that — and just records acceptance.
        """
        idx = self._main_window._active_idx
        if idx is None:
            return
        ds = self._main_window._datasets[idx]
        stem = self._stem_for(ds)

        if not getattr(self._main_window, "test_mode", False):
            reply = QMessageBox.question(
                self,
                "Validate section",
                f"Confirm that the boundaries for section '{name}' are correct?\n\n"
                f"This will record validation in {stem}_section_validations.yml.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if reply != QMessageBox.Yes:
                return

        self._section_validations[name] = {
            "validated_at": datetime.now().isoformat(),
            "validator": "inspector",
        }
        try:
            self._persist_validations(stem)
        except Exception as exc:  # pragma: no cover - defensive
            self._main_window.statusBar().showMessage(
                f"Could not save validation for '{name}': {exc}", 5000
            )
            return
        # Re-render so the new check mark shows up immediately.
        self._rebuild_sections_list(ds)
        self._main_window.statusBar().showMessage(
            f"Section '{name}' validated and saved.", 3000
        )

    def _on_section_context_menu(self, pos) -> None:
        """Right-click on a section row → offer 'Clear validation'."""
        item = self._sections_list.itemAt(pos)
        if item is None:
            return
        name = item.data(_ROLE_SECTION_NAME)
        if name is None:
            return
        menu = QMenu(self._sections_list)
        clear_act = menu.addAction("Clear validation")
        clear_act.setEnabled(name in self._section_validations)
        chosen = (
            menu.exec(self._sections_list.viewport().mapToGlobal(pos))
            if not getattr(self._main_window, "test_mode", False)
            else None
        )
        if chosen is clear_act:
            self._clear_validation(name)

    def _clear_validation(self, name: str) -> None:
        """Remove a section's validation entry + persist + refresh."""
        if name not in self._section_validations:
            return
        idx = self._main_window._active_idx
        if idx is None:
            return
        ds = self._main_window._datasets[idx]
        stem = self._stem_for(ds)
        del self._section_validations[name]
        try:
            self._persist_validations(stem)
        except Exception as exc:  # pragma: no cover - defensive
            self._main_window.statusBar().showMessage(
                f"Could not clear validation for '{name}': {exc}", 5000
            )
            return
        self._rebuild_sections_list(ds)
        self._main_window.statusBar().showMessage(
            f"Validation cleared for section '{name}'.", 3000
        )
