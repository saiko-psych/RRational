"""Right-side panel of the Browse tab — artifact detection + summary.

Mirrors the Streamlit Participants tab's preprocessing flow:
1. Click "Detect artifacts" → runs NK2 Kubios algorithm on the active
   dataset's RR array
2. Shows artifact rate + Quigley-2024 quality grade
3. Toggles overlay visibility on the main plot
4. Exports as .rrational v2 once the user has validated sections

Also offers an exclusion-mode toggle + a per-dataset zones list (with
Edit / Delete buttons) that auto-persists to ``{pid}_exclusions.yml``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from qtpy.QtCore import Qt  # noqa: F401 — used inline for setTextFormat(Qt.RichText)
from qtpy.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rrational.inspector import settings
from rrational.inspector.exclusion_persistence import (
    load_exclusion_zones,
    save_exclusion_zones,
)
from rrational.inspector.history import (
    AddAnnotation,
    AddExclusionZone,
    DetectArtifacts,
    SaveRRationalExport,
)

if TYPE_CHECKING:
    from rrational.inspector.annotations import Annotation
    from rrational.inspector.data_loader import InspectorData
    from rrational.inspector.preprocessing import PreprocessingResult


# Colour-code the quality grade so the eye lands on it before reading
# the text. Chosen for white-background readability.
_GRADE_COLOR = {
    "excellent": "#2ca02c",  # green
    "good": "#5b8def",  # blue
    "moderate": "#ff7f0e",  # orange
    "poor": "#d62728",  # red
    "unknown": "#888888",  # grey
}

# Cap on the undo/redo stack size. 50 mirrors mne-qt-browser's default
# annotation undo depth.
_UNDO_DEPTH = 50


class PreprocessingPanel(QWidget):
    """Side panel that runs artifact detection and shows the result."""

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self._main_window = main_window
        self._last_result: "PreprocessingResult | None" = None

        # Wider so the workflow-stepper buttons aren't truncated.
        self.setMaximumWidth(340)
        self.setMinimumWidth(280)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        from qtpy.QtWidgets import QGroupBox

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Workflow stepper at the very top so users see the linear
        # 4-step path (Load → Detect → Review → Save) before anything else.
        from rrational.inspector.workflow_stepper import WorkflowStepper

        self._stepper = WorkflowStepper(self)
        self._stepper.step_clicked.connect(self._on_workflow_step_clicked)
        layout.addWidget(self._stepper)

        # --- Group 1: Artifact detection ------------------------------------
        detect_box = QGroupBox("Artifact detection")
        detect_layout = QVBoxLayout(detect_box)
        detect_layout.setContentsMargins(12, 18, 12, 12)
        detect_layout.setSpacing(8)

        self._detect_btn = QPushButton("Detect artifacts")
        self._detect_btn.setToolTip(
            "Run NeuroKit2 Kubios algorithm on the active dataset's RR series"
        )
        # Primary action of the panel: amber-accent variant from the QSS theme.
        self._detect_btn.setProperty("primary", True)
        self._detect_btn.clicked.connect(self._on_detect_clicked)
        self._detect_btn.setEnabled(False)
        detect_layout.addWidget(self._detect_btn)

        # RichText so the inline <i>/<b> markup in the placeholder + the
        # status messages set later actually render — without this Qt
        # ships them through as literal "<i>Detect artifacts</i>" text.
        self._summary = QLabel(
            "No artifact detection run yet.\n\nLoad a recording, then "
            "click <i>Detect artifacts</i>."
        )
        self._summary.setTextFormat(Qt.RichText)
        self._summary.setWordWrap(True)
        self._summary.setProperty("muted", True)
        detect_layout.addWidget(self._summary)

        self._toggle_show_artifacts = QCheckBox("Show artifact markers")
        self._toggle_show_artifacts.setChecked(True)
        self._toggle_show_artifacts.toggled.connect(self._on_toggle_show_artifacts)
        self._toggle_show_artifacts.setEnabled(False)
        detect_layout.addWidget(self._toggle_show_artifacts)

        self._toggle_use_corrected = QCheckBox("Use corrected RR values")
        self._toggle_use_corrected.setChecked(False)
        self._toggle_use_corrected.setToolTip(
            "Replace the plotted RR series with the artifact-corrected "
            "(interpolated) version."
        )
        self._toggle_use_corrected.toggled.connect(self._on_toggle_use_corrected)
        self._toggle_use_corrected.setEnabled(False)
        detect_layout.addWidget(self._toggle_use_corrected)

        self._toggle_manual_mark = QCheckBox("Manual mark mode")
        self._toggle_manual_mark.setChecked(False)
        self._toggle_manual_mark.setToolTip(
            "Click on the timeline to mark a beat as an artifact, click an "
            "existing algorithm artifact to exclude it, or click a manual "
            "mark to remove it."
        )
        self._toggle_manual_mark.toggled.connect(self._on_toggle_manual_mark)
        self._toggle_manual_mark.setEnabled(False)
        detect_layout.addWidget(self._toggle_manual_mark)

        self._manual_help = QLabel(
            "Left-click near a beat: add manual mark<br>"
            "Left-click on algorithm artifact: exclude<br>"
            "Left-click on manual mark: remove<br>"
            "Edit → Undo / Redo (Ctrl+Z / Ctrl+Y)"
        )
        self._manual_help.setTextFormat(Qt.RichText)
        self._manual_help.setWordWrap(True)
        self._manual_help.setProperty("muted", True)
        self._manual_help.setVisible(False)
        detect_layout.addWidget(self._manual_help)

        layout.addWidget(detect_box)

        # Undo/redo stacks. Each entry is a (action_tag, idx) tuple —
        # replayed in reverse on undo, re-applied on redo. Capped at
        # ``_UNDO_DEPTH`` so a long marathon session doesn't hoard memory.
        self._undo_stack: list[tuple[str, int]] = []
        self._redo_stack: list[tuple[str, int]] = []

        # --- Group 2: Exclusion zones ---------------------------------------
        excl_box = QGroupBox("Exclusion zones")
        excl_layout = QVBoxLayout(excl_box)
        excl_layout.setContentsMargins(12, 18, 12, 12)
        excl_layout.setSpacing(8)

        self._toggle_exclusion_mode = QCheckBox("Exclusion mode (drag-select)")
        self._toggle_exclusion_mode.setToolTip(
            "When ON, click-drag on the plot creates a new exclusion zone. "
            "Beats inside a zone are filtered out of every HRV analysis."
        )
        self._toggle_exclusion_mode.toggled.connect(self._on_toggle_exclusion_mode)
        excl_layout.addWidget(self._toggle_exclusion_mode)

        self._zones_table = QTableWidget(0, 4, self)
        self._zones_table.setHorizontalHeaderLabels(["Start", "End", "Reason", ""])
        self._zones_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._zones_table.verticalHeader().setVisible(False)
        self._zones_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self._zones_table.setMaximumHeight(140)
        excl_layout.addWidget(self._zones_table)
        layout.addWidget(excl_box)

        plot = getattr(parent, "_plot", None)
        if plot is not None:
            plot.exclusion_zones_changed.connect(self._on_zones_changed)

        # --- Group 3: Section editing ---------------------------------------
        section_box = QGroupBox("Section editing")
        section_layout = QVBoxLayout(section_box)
        section_layout.setContentsMargins(12, 18, 12, 12)
        section_layout.setSpacing(8)
        self._toggle_section_edit = QCheckBox("Section edit mode")
        self._toggle_section_edit.setChecked(False)
        self._toggle_section_edit.setToolTip(
            "Drag section edges to adjust boundaries (snaps to the nearest beat). "
            "Right-click a band to rename, split, or delete it."
        )
        self._toggle_section_edit.toggled.connect(self._on_toggle_section_edit)
        section_layout.addWidget(self._toggle_section_edit)
        layout.addWidget(section_box)

        # --- Group 4: Export + Annotations ----------------------------------
        export_box = QGroupBox("Export & annotations")
        export_layout = QVBoxLayout(export_box)
        export_layout.setContentsMargins(12, 18, 12, 12)
        export_layout.setSpacing(8)

        self._export_btn = QPushButton("Save as .rrational v2…")
        self._export_btn.setToolTip(
            "Export the current dataset (plus detected artifacts + "
            "any section overrides) as a .rrational v2 file"
        )
        self._export_btn.clicked.connect(self._on_export_clicked)
        self._export_btn.setEnabled(False)
        export_layout.addWidget(self._export_btn)

        self._toggle_annotation_mode = QCheckBox("Annotation mode")
        self._toggle_annotation_mode.setToolTip(
            "When ON, left-click on the timeline to add a free-text note."
        )
        self._toggle_annotation_mode.toggled.connect(self._on_toggle_annotation_mode)
        self._toggle_annotation_mode.setEnabled(False)
        export_layout.addWidget(self._toggle_annotation_mode)

        self._annotation_count_label = QLabel("No annotations.")
        self._annotation_count_label.setTextFormat(Qt.RichText)
        self._annotation_count_label.setWordWrap(True)
        self._annotation_count_label.setProperty("muted", True)
        export_layout.addWidget(self._annotation_count_label)
        layout.addWidget(export_box)

        layout.addStretch()

        # Plumb plot signals — the plot fires plot_clicked / annotation_context
        # only when our mode is on / a marker is under the cursor. The
        # panel is instantiated INSIDE BrowseTab._build, so we reach for
        # the plot via the parent rather than _main_window._browse_tab
        # (which isn't assigned yet).
        if parent is not None and hasattr(parent, "_plot"):
            plot = parent._plot
            plot.plot_clicked.connect(self._on_plot_clicked)
            plot.annotation_context.connect(self._on_annotation_right_clicked)
            # Drag-annotation: a left-drag in annotation mode emits a
            # range; we anchor the annotation at the midpoint and prompt
            # for text exactly like the click path.
            plot.plot_range_selected.connect(self._on_plot_range_selected)

        # Annotation state — one list per active dataset, persisted.
        self._annotations: list[Annotation] = []

        # Wire the plot's manual-click signal to our handler. BrowseTab
        # constructs the plot then this panel inside the same ``_build``
        # call, so ``parent`` is the BrowseTab and ``_plot`` is already
        # live. Going through ``parent`` rather than
        # ``main_window._browse_tab`` matters: the latter isn't assigned
        # on MainWindow until BrowseTab.__init__ returns.
        plot = parent._plot if parent is not None and hasattr(parent, "_plot") else None
        if plot is not None:
            plot.manual_artifact_changed.connect(self._on_manual_artifact_changed)

    # ------------------------------------------------------------------
    # State sync
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Workflow-stepper helpers
    # ------------------------------------------------------------------
    def _refresh_workflow_steps(self) -> None:
        """Recompute the 1-2-3-4 step states from current panel state."""
        stepper = getattr(self, "_stepper", None)
        if stepper is None:
            return
        has_data = self._main_window._data is not None
        has_detection = self._last_result is not None
        has_correction = bool(
            has_detection
            and (
                self._toggle_use_corrected.isChecked()
                or getattr(self, "_export_done_once", False)
                or self._undo_stack
            )
        )
        exported = getattr(self, "_export_done_once", False)

        # State transitions: done → active → locked, in order.
        states: dict[int, str] = {}
        states[1] = "done" if has_data else "active"
        states[2] = "done" if has_detection else ("active" if has_data else "locked")
        states[3] = (
            "done" if has_correction else ("active" if has_detection else "locked")
        )
        states[4] = "done" if exported else ("active" if has_detection else "locked")
        stepper.set_step_states(states)

    def _on_workflow_step_clicked(self, step: int) -> None:
        """Click handler for any of the 4 stepper buttons."""
        stepper = self._stepper
        state = stepper.state_for(step)
        if state == "locked":
            self._main_window.statusBar().showMessage(
                "Complete the previous step first.", 3000
            )
            return
        if step == 1:
            self._main_window._on_open_clicked()
        elif step == 2:
            self._on_detect_clicked()
        elif step == 3:
            # Focus the use-corrected checkbox so user knows where to act.
            self._toggle_use_corrected.setFocus()
        elif step == 4:
            self._on_export_clicked()

    def on_active_dataset_changed(self, data: "InspectorData | None") -> None:
        """Reset the panel when the user switches/unloads a dataset.

        When a dataset is loaded, also try to auto-restore any
        previously-saved artifact corrections from ``{pid}_artifacts.yml``
        (Streamlit-shared) and any exclusion zones from
        ``{pid}_exclusions.yml``. Also resets the undo/redo stacks
        (per-dataset history), the plot's manual / excluded sets, and
        the workflow-stepper state.
        """
        self._last_result = None
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._export_done_once = False
        if data is None:
            self._summary.setText(
                "<i>No dataset loaded.</i> Use File → Open to load a recording."
            )
            self._detect_btn.setEnabled(False)
            self._export_btn.setEnabled(False)
        else:
            self._summary.setText(
                f"Loaded: <b>{len(data.t)}</b> beats.\n\n"
                "Click <i>Detect artifacts</i> to run the Kubios algorithm."
            )
            self._detect_btn.setEnabled(True)
            # Export is allowed even without artifact detection — the
            # raw RR + sections still make a valid (if lower-quality)
            # .rrational v2 file.
            self._export_btn.setEnabled(True)
        self._toggle_show_artifacts.setEnabled(False)
        self._toggle_use_corrected.setEnabled(False)
        self._toggle_use_corrected.blockSignals(True)
        self._toggle_use_corrected.setChecked(False)
        self._toggle_use_corrected.blockSignals(False)
        # Manual-mark mode resets to OFF whenever the dataset changes —
        # otherwise the user could click into a stale dataset.
        self._toggle_manual_mark.blockSignals(True)
        self._toggle_manual_mark.setChecked(False)
        self._toggle_manual_mark.blockSignals(False)
        self._toggle_manual_mark.setEnabled(data is not None)
        self._manual_help.setVisible(False)
        # Reset the plot's manual sets too. The restore call below will
        # repopulate them if the dataset has prior corrections.
        plot = self._main_window._browse_tab._plot
        plot.set_manual_artifact_indices(added=set(), removed=set())
        plot.set_manual_mark_mode(False)
        self._update_undo_redo_actions()

        # Annotation toggle follows dataset availability + auto-restore
        # any persisted annotations for this dataset's pid.
        self._toggle_annotation_mode.setEnabled(data is not None)
        if data is None:
            self._toggle_annotation_mode.blockSignals(True)
            self._toggle_annotation_mode.setChecked(False)
            self._toggle_annotation_mode.blockSignals(False)
            self._annotations = []
            self._refresh_annotation_label()
        else:
            self._restore_annotations()

        # Attempt auto-restore from disk.
        if data is not None:
            self._try_restore_artifacts(data)
            self._try_restore_exclusion_zones(data)
        # When unloading a dataset, clear the zones table; the plot's
        # own clear_overlays / clear_exclusion_zones (called by
        # set_data) already dropped the regions.
        if data is None:
            self._refresh_zones_table()
        self._refresh_workflow_steps()

    def _try_restore_artifacts(self, data: "InspectorData") -> None:
        """Look for {pid}_artifacts.yml for the active dataset; if found,
        restore the result + plot overlay + status."""
        from rrational.gui.persistence import load_artifact_corrections
        from rrational.inspector.preprocessing import (
            PreprocessingResult,
            _grade_for_rate,
        )

        active_idx = self._main_window._active_idx
        if active_idx is None or active_idx >= len(self._main_window._datasets):
            return
        ds = self._main_window._datasets[active_idx]
        pid = Path(ds.name).stem

        proj = getattr(self._main_window, "_project", None)
        project_path = proj.project_path if proj is not None else None
        try:
            entry = load_artifact_corrections(
                pid, project_path=project_path, section_key="_full"
            )
        except Exception:
            entry = None
        if entry is None:
            return

        algo_indices = entry.get("algorithm_artifact_indices") or []
        # Also restore manual + excluded sets.
        manual_entries = entry.get("manual_artifacts") or []
        manual_added = {
            int(m["original_idx"])
            for m in manual_entries
            if isinstance(m, dict) and "original_idx" in m
        }
        manual_removed = {
            int(i) for i in (entry.get("excluded_artifact_indices") or [])
        }

        # Bail only if there's literally nothing saved for this pid —
        # otherwise we still want to restore manual / excluded marks.
        if not algo_indices and not manual_added and not manual_removed:
            return

        # Rebuild a PreprocessingResult shell (we don't reload
        # corrected_v from disk — that lives in nn_metadata.yml).
        import numpy as _np

        indices_arr = _np.asarray(algo_indices, dtype=_np.int64)
        # Round 32 — divide by the number of REAL beats, not len(data.v):
        # data.v carries NaN gap-markers between sections, so len(data.v)
        # inflates the denominator and reports an artificially low artifact
        # rate (and a falsely optimistic quality grade) on gapped recordings.
        n_finite = int(_np.isfinite(data.v).sum())
        rate = (len(indices_arr) / n_finite) if n_finite > 0 else 0.0
        grade, msg = _grade_for_rate(rate)
        by_type = dict(entry.get("indices_by_type") or {})
        restored = PreprocessingResult(
            indices=indices_arr,
            by_type={
                k: len(v) if isinstance(v, list) else int(v) for k, v in by_type.items()
            },
            total=len(indices_arr),
            rate=rate,
            corrected_v=None,
            grade=grade,
            recommendation=msg,
        )
        self._last_result = restored

        # Render exactly like a fresh detection
        plot = self._main_window._browse_tab._plot
        plot.set_artifacts(restored.indices)
        # Push manual sets BEFORE flipping visibility so the refresh
        # paints them on the same overlay-show cycle.
        plot.set_manual_artifact_indices(added=manual_added, removed=manual_removed)
        plot.set_artifacts_visible(self._toggle_show_artifacts.isChecked())
        color = _GRADE_COLOR.get(restored.grade, "#888888")
        manual_suffix = ""
        if manual_added or manual_removed:
            manual_suffix = (
                f"<br><small style='color:#666'>"
                f"Restored manual marks: {len(manual_added)} added, "
                f"{len(manual_removed)} excluded</small>"
            )
        self._summary.setText(
            f"<b>Restored from disk:</b><br>"
            f"<b>{restored.total}</b> artifacts in {len(data.v)} beats<br>"
            f"<b>Rate:</b> {restored.rate * 100:.2f}%<br>"
            f"<b>Grade:</b> "
            f"<span style='color:{color};'><b>{restored.grade}</b></span><br>"
            f"<small style='color:#666'>{restored.recommendation}</small>"
            f"{manual_suffix}"
        )
        self._toggle_show_artifacts.setEnabled(True)
        # Without corrected_v we can't enable the use-corrected toggle
        self._toggle_use_corrected.setEnabled(False)
        self._main_window.statusBar().showMessage(
            f"Restored {restored.total} artifacts for '{pid}' from disk", 4000
        )

    # ------------------------------------------------------------------
    # Exclusion zones
    # ------------------------------------------------------------------
    def _try_restore_exclusion_zones(self, data: "InspectorData") -> None:
        """Auto-restore zones from ``{pid}_exclusions.yml`` on dataset switch.

        Silent on missing/unreadable files — the user's first interaction
        with the panel is allowed to be a no-op restore that produces an
        empty table.
        """
        active_idx = self._main_window._active_idx
        if active_idx is None or active_idx >= len(self._main_window._datasets):
            return
        ds = self._main_window._datasets[active_idx]
        pid = Path(ds.name).stem
        proj = getattr(self._main_window, "_project", None)
        project_path = proj.project_path if proj is not None else None
        try:
            zones = load_exclusion_zones(pid, project_path=project_path)
        except Exception:
            zones = []
        plot = self._main_window._browse_tab._plot
        # set_data already cleared, but be defensive in case of out-of-order
        # init in tests.
        plot.clear_exclusion_zones()
        for z in zones:
            # emit=False during restore — we don't want to fire the
            # auto-save loop until the user actually mutates state.
            plot.add_exclusion_zone(z, emit=False)
        self._refresh_zones_table()

    def _on_toggle_exclusion_mode(self, checked: bool) -> None:
        plot = self._main_window._browse_tab._plot
        plot.set_exclusion_mode(bool(checked))
        if checked:
            self._main_window.statusBar().showMessage(
                "Exclusion mode ON — drag on the plot to mark a zone", 4000
            )
        # Cluster A8 — refresh persistent context label so the mode
        # change is visible in the status bar even after the transient
        # showMessage hint times out.
        if hasattr(self._main_window, "_refresh_status_context"):
            self._main_window._refresh_status_context()

    def _on_zones_changed(self) -> None:
        """Plot fired ``exclusion_zones_changed`` — refresh + auto-save.

        Also pushes an :class:`AddExclusionZone` action into the inspector
        history when the zone count grew since the last call (delete /
        edit don't generate a recipe entry — the recipe replays
        creations, not interactive edits).
        """
        plot = self._main_window._browse_tab._plot
        prev_count = getattr(self, "_history_zone_count", 0)
        zones = list(plot._exclusion_zones)
        if len(zones) > prev_count:
            for zone in zones[prev_count:]:
                self._record_exclusion_history(zone)
        self._history_zone_count = len(zones)
        self._refresh_zones_table()
        self._autosave_exclusion_zones()
        # Cluster A8 — keep the status-bar counts in sync.
        if hasattr(self._main_window, "_refresh_status_context"):
            self._main_window._refresh_status_context()

    def _refresh_zones_table(self) -> None:
        plot = self._main_window._browse_tab._plot
        zones = list(plot._exclusion_zones)
        self._zones_table.setRowCount(0)
        for i, z in enumerate(zones):
            row = self._zones_table.rowCount()
            self._zones_table.insertRow(row)
            start_str = datetime.fromtimestamp(z.start_t).strftime("%H:%M:%S")
            end_str = datetime.fromtimestamp(z.end_t).strftime("%H:%M:%S")
            self._zones_table.setItem(row, 0, QTableWidgetItem(start_str))
            self._zones_table.setItem(row, 1, QTableWidgetItem(end_str))
            self._zones_table.setItem(row, 2, QTableWidgetItem(z.reason or ""))
            actions = QWidget()
            row_layout = QHBoxLayout(actions)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(2)
            edit_btn = QPushButton("Edit")
            edit_btn.setToolTip("Edit the reason for this exclusion zone")
            edit_btn.clicked.connect(lambda _c, idx=i: self._on_edit_reason(idx))
            del_btn = QPushButton("X")
            del_btn.setToolTip("Delete this zone")
            del_btn.clicked.connect(lambda _c, idx=i: self._on_delete_zone(idx))
            row_layout.addWidget(edit_btn)
            row_layout.addWidget(del_btn)
            self._zones_table.setCellWidget(row, 3, actions)

    def _on_edit_reason(self, index: int) -> None:
        plot = self._main_window._browse_tab._plot
        if not (0 <= index < len(plot._exclusion_zones)):
            return
        current = plot._exclusion_zones[index].reason or ""
        if self._main_window.test_mode:
            new = current + " (edited)"
            ok = True
        else:
            new, ok = QInputDialog.getText(
                self,
                "Edit exclusion reason",
                "Reason:",
                text=current,
            )
        if not ok:
            return
        plot.update_exclusion_reason(index, new)

    def _on_delete_zone(self, index: int) -> None:
        plot = self._main_window._browse_tab._plot
        plot.remove_exclusion_zone(index)

    def _autosave_exclusion_zones(self) -> None:
        """Persist current zones to disk; silent on failure."""
        active_idx = self._main_window._active_idx
        if active_idx is None or active_idx >= len(self._main_window._datasets):
            return
        ds = self._main_window._datasets[active_idx]
        pid = Path(ds.name).stem
        proj = getattr(self._main_window, "_project", None)
        project_path = proj.project_path if proj is not None else None
        plot = self._main_window._browse_tab._plot
        zones = list(plot._exclusion_zones)
        try:
            save_exclusion_zones(pid, zones, project_path=project_path)
        except Exception:  # pragma: no cover - autosave must not crash
            pass

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_detect_clicked(self) -> None:
        from rrational.inspector.preprocessing import detect_artifacts

        data = self._main_window._data
        if data is None or len(data.v) == 0:
            return
        result = detect_artifacts(data.v)
        self._last_result = result

        # Push markers to the plot, then update summary text.
        plot = self._main_window._browse_tab._plot
        plot.set_artifacts(result.indices)
        plot.set_artifacts_visible(self._toggle_show_artifacts.isChecked())

        color = _GRADE_COLOR.get(result.grade, "#888888")
        type_breakdown = (
            ", ".join(
                f"{name}: {count}"
                for name, count in result.by_type.items()
                if count > 0
            )
            or "no individual types reported"
        )
        self._summary.setText(
            f"<b>{result.total}</b> artifacts in {len(data.v)} beats<br>"
            f"<b>Rate:</b> {result.rate * 100:.2f}%<br>"
            f"<b>Grade:</b> "
            f"<span style='color:{color};'><b>{result.grade}</b></span><br>"
            f"<small style='color:#666'>{result.recommendation}</small><br>"
            f"<small style='color:#888'>{type_breakdown}</small>"
        )
        self._toggle_show_artifacts.setEnabled(True)
        # Corrected-values toggle only useful when there are actual artifacts.
        self._toggle_use_corrected.setEnabled(result.total > 0)
        self._export_btn.setEnabled(True)
        # Auto-persist so future loads restore this state.
        self._autosave_artifacts(result, data)
        # Record detect into the reproducible-action history. ``pid`` is
        # optional context — handy when the recipe is reviewed by a
        # second pair of eyes.
        try:
            history = getattr(self._main_window, "history", None)
            if history is not None:
                history.record(
                    DetectArtifacts(method="lipponen2019", pid=self._active_pid())
                )
        except Exception:  # pragma: no cover - history must not break detect
            pass
        self._main_window.statusBar().showMessage(
            f"Artifact detection: {result.total} found "
            f"({result.rate * 100:.2f}%, {result.grade})",
            4000,
        )
        self._refresh_workflow_steps()

    def _autosave_artifacts(self, result, data: "InspectorData") -> None:
        """Persist the freshly-detected artifacts to disk.

        Writes to ``{project}/data/processed/{pid}_artifacts.yml`` (or
        the global fallback) using the v1.3 section-scoped schema with
        section_key=`_full` — matches what Streamlit produces for a
        whole-recording detection. Silent on failure (autosave must not
        crash compute).

        Preserves any pre-existing manual / excluded marks the user
        already had on the plot — re-running Detect doesn't wipe
        hand-edits.
        """
        from rrational.gui.persistence import save_artifact_corrections

        active_idx = self._main_window._active_idx
        if active_idx is None or active_idx >= len(self._main_window._datasets):
            return
        ds = self._main_window._datasets[active_idx]
        pid = Path(ds.name).stem
        proj = getattr(self._main_window, "_project", None)
        project_path = proj.project_path if proj is not None else None

        # PreprocessingResult.by_type is {label: count}; the streamlit
        # schema wants {label: [indices]}. We don't have per-index type
        # info — pass the (count-typed) data through as best-effort
        # provenance. Streamlit reads only the algorithm_artifact_indices
        # for actual analysis, so this is information-preserving.
        indices_by_type = {k: [] for k in (result.by_type or {}).keys()}

        plot = self._main_window._browse_tab._plot
        added = plot.manual_added_indices()
        removed = plot.manual_removed_indices()
        manual_artifacts = []
        for i in sorted(added):
            if 0 <= i < len(data.v):
                rr_val = float(data.v[i]) if np.isfinite(data.v[i]) else None
                ts_val = float(data.t[i]) if np.isfinite(data.t[i]) else None
                manual_artifacts.append(
                    {
                        "original_idx": int(i),
                        "rr_value": rr_val,
                        "timestamp": ts_val,
                    }
                )
        try:
            save_artifact_corrections(
                participant_id=pid,
                manual_artifacts=manual_artifacts,
                artifact_exclusions=[int(i) for i in sorted(removed)],
                algorithm_artifacts=[int(i) for i in result.indices],
                algorithm_method="lipponen2019",
                indices_by_type=indices_by_type,
                section_key="_full",
                project_path=project_path,
            )
        except Exception:  # pragma: no cover - autosave must not crash detect
            pass

    # ------------------------------------------------------------------
    # Batch-apply API — used by MainWindow's "Run on all loaded" entry
    # and by the Quality-triage dashboard.
    # ------------------------------------------------------------------
    def process_single(self, ds, save_export: bool = True) -> "BatchResult":
        """Run detect + (optional) .rrational save on ``ds``.

        Mirrors what ``_on_detect_clicked`` + ``_on_export_clicked`` do
        for the currently-active dataset, but takes the dataset
        explicitly so it can run on every workspace entry in turn
        without flipping the active selection / re-rendering the plot
        per recording. Returns a :class:`BatchResult` row suitable for
        :class:`QualityTriageDialog`.

        ``save_export=False`` skips the .rrational write (the Tools →
        Quality triage menu uses this to recompute grades without
        clobbering on-disk exports the user already curated).
        """
        from rrational.inspector.preprocessing import (
            _grade_letter_for_rate,
            detect_artifacts,
        )
        from rrational.inspector.quality_triage_dialog import BatchResult

        data = ds.data
        n_beats = int(len(data.v)) if data is not None else 0

        if data is None or n_beats == 0:
            return BatchResult(
                name=ds.name,
                n_beats=0,
                n_artifacts=0,
                artifact_rate=0.0,
                grade="?",
                saved_path=None,
            )

        try:
            result = detect_artifacts(data.v)
        except Exception:
            # Batch must never crash on one bad recording — surface as a
            # "?" grade row so the user can still see the others.
            return BatchResult(
                name=ds.name,
                n_beats=n_beats,
                n_artifacts=0,
                artifact_rate=0.0,
                grade="?",
                saved_path=None,
            )

        rate = float(result.rate)
        letter = _grade_letter_for_rate(rate)

        # Persist the artifact correction so a subsequent single-dataset
        # open auto-restores the same state via _try_restore_artifacts.
        # Failures are swallowed (autosave must not crash batch).
        try:
            self._autosave_artifacts_for(result, ds)
        except Exception:  # pragma: no cover - defensive
            pass

        saved_path: str | None = None
        if save_export:
            saved_path = self._export_dataset_silent(ds, result)

        return BatchResult(
            name=ds.name,
            n_beats=n_beats,
            n_artifacts=int(result.total),
            artifact_rate=rate,
            grade=letter,
            saved_path=saved_path,
        )

    def apply_to_recordings(
        self, recordings, progress_cb=None, save_export: bool = True
    ) -> list:
        """Run :meth:`process_single` across ``recordings``.

        ``progress_cb(i, total, name)`` is called BEFORE each recording
        is processed so a wrapping QProgressDialog can update its label.
        Returns the list of :class:`BatchResult` rows in input order.
        """
        results = []
        total = len(recordings)
        for i, ds in enumerate(recordings):
            if progress_cb is not None:
                try:
                    progress_cb(i, total, ds.name)
                except Exception:  # pragma: no cover - defensive
                    pass
            results.append(self.process_single(ds, save_export=save_export))
        return results

    def _autosave_artifacts_for(self, result, ds) -> None:
        """Per-dataset variant of :meth:`_autosave_artifacts`.

        The single-dataset version peeks at ``self._main_window._data``
        + the plot's manual sets; in batch we have neither (we're not
        rendering ``ds``), so we write the algorithm artifacts only and
        leave the manual / excluded sets untouched (any prior file for
        ``ds`` keeps its hand edits because save_artifact_corrections
        rewrites the whole document — see note below).
        """
        from rrational.gui.persistence import (
            load_artifact_corrections,
            save_artifact_corrections,
        )

        pid = Path(ds.name).stem
        proj = getattr(self._main_window, "_project", None)
        project_path = proj.project_path if proj is not None else None

        # Preserve any existing manual / excluded marks for this pid by
        # reading them back BEFORE overwriting the algorithm set.
        prior = None
        try:
            prior = load_artifact_corrections(
                pid, project_path=project_path, section_key="_full"
            )
        except Exception:
            prior = None
        manual_artifacts = (prior or {}).get("manual_artifacts") or []
        artifact_exclusions = list((prior or {}).get("excluded_artifact_indices") or [])

        indices_by_type = {k: [] for k in (result.by_type or {}).keys()}
        save_artifact_corrections(
            participant_id=pid,
            manual_artifacts=manual_artifacts,
            artifact_exclusions=[int(i) for i in artifact_exclusions],
            algorithm_artifacts=[int(i) for i in result.indices],
            algorithm_method="lipponen2019",
            indices_by_type=indices_by_type,
            section_key="_full",
            project_path=project_path,
        )

    def _export_dataset_silent(self, ds, result) -> str | None:
        """Write ``ds`` as a .rrational v2 file without prompting.

        Destination = ``{project}/data/processed/{stem}.rrational`` when
        a project is active, otherwise the QSettings ``last_dir`` falls
        back to the dataset's source folder, then ``Path.cwd()``.
        Returns the absolute path string on success, None on any error
        (batch must never crash on a single bad recording).
        """
        from rrational.inspector.export import export_inspector_to_rrational

        pid = Path(ds.name).stem
        proj = getattr(self._main_window, "_project", None)
        if proj is not None:
            out_dir = proj.project_path / "data" / "processed"
        else:
            last_dir = settings.read_setting("last_dir")
            if last_dir:
                out_dir = Path(str(last_dir))
            elif ds.path is not None:
                out_dir = ds.path.parent
            else:
                out_dir = Path.cwd()
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None
        out_path = out_dir / f"{pid}.rrational"
        try:
            export_inspector_to_rrational(
                ds.data,
                out_path,
                participant_id=pid,
                preprocessing=result,
                source_path=ds.path,
            )
        except Exception:
            return None
        # Record into the reproducible-action history so a recipe built
        # off a batch run still reflects every export that landed on
        # disk (the surrounding BatchPreprocess action is the
        # higher-level "for-each-loop" trace).
        try:
            history = getattr(self._main_window, "history", None)
            if history is not None:
                section_name = ds.data.sections[0].name if ds.data.sections else ""
                n_beats = int(len(ds.data.v)) if ds.data is not None else 0
                history.record(
                    SaveRRationalExport(
                        pid=pid,
                        section=section_name,
                        out_path=str(out_path),
                        n_beats=n_beats,
                    )
                )
        except Exception:  # pragma: no cover - history must not break batch
            pass
        return str(out_path)

    def _on_toggle_show_artifacts(self, checked: bool) -> None:
        plot = self._main_window._browse_tab._plot
        plot.set_artifacts_visible(checked)

    def _on_toggle_section_edit(self, checked: bool) -> None:
        """Flip the plot's section-edit mode."""
        plot = self._main_window._browse_tab._plot
        plot.set_section_edit_mode(bool(checked))
        msg = (
            "Section edit mode ON — drag edges or right-click a band"
            if checked
            else "Section edit mode OFF"
        )
        self._main_window.statusBar().showMessage(msg, 2500)
        if hasattr(self._main_window, "_refresh_status_context"):
            self._main_window._refresh_status_context()

    def _on_toggle_use_corrected(self, checked: bool) -> None:
        if self._last_result is None or self._last_result.corrected_v is None:
            return
        plot = self._main_window._browse_tab._plot
        data = self._main_window._data
        if data is None:
            return
        if checked:
            plot._curve.setData(data.t, self._last_result.corrected_v)
        else:
            plot._curve.setData(data.t, data.v)
        # Round 32 (PP1) — propagate the choice to the ACTIVE dataset so the
        # Analysis tab's Compute uses the corrected series too, not just the
        # plot. Previously the toggle only re-drew the curve, so Compute
        # silently ran on raw data while the export used corrected values.
        self._apply_use_corrected_to_active_dataset(checked)
        self._refresh_workflow_steps()

    def _apply_use_corrected_to_active_dataset(self, checked: bool) -> None:
        """Store the corrected series + flag on the active Dataset (PP1)."""
        try:
            ds = self._main_window._datasets[self._main_window._active_idx]
        except (AttributeError, IndexError, TypeError):
            return
        if (
            checked
            and self._last_result is not None
            and self._last_result.corrected_v is not None
        ):
            ds.corrected_v = self._last_result.corrected_v
            ds.use_corrected = True
        else:
            ds.use_corrected = False

    # ------------------------------------------------------------------
    # Manual artifact marking + undo / redo
    # ------------------------------------------------------------------
    def _on_toggle_manual_mark(self, checked: bool) -> None:
        """Forward the checkbox state to the plot's interaction mode."""
        plot = self._main_window._browse_tab._plot
        plot.set_manual_mark_mode(checked)
        self._manual_help.setVisible(checked)
        if checked:
            self._main_window.statusBar().showMessage(
                "Manual mark mode ON — click a beat to mark / unmark", 3000
            )
        else:
            self._main_window.statusBar().showMessage("Manual mark mode OFF", 1500)
        if hasattr(self._main_window, "_refresh_status_context"):
            self._main_window._refresh_status_context()

    def _on_manual_artifact_changed(self, idx: int, action: str) -> None:
        """Plot tells us a beat-index was just marked / unmarked.

        Push the action onto the undo stack (clearing redo), then
        auto-save the new state to disk. Updates the menu enabledness.
        """
        self._push_undo((action, int(idx)))
        self._redo_stack.clear()
        self._autosave_full_state()
        self._update_undo_redo_actions()

    def _push_undo(self, entry: tuple[str, int]) -> None:
        self._undo_stack.append(entry)
        if len(self._undo_stack) > _UNDO_DEPTH:
            # Drop the oldest entry — the user can't undo back that far.
            del self._undo_stack[0]

    def undo(self) -> bool:
        """Reverse the last manual mark. Returns True if anything happened."""
        if not self._undo_stack:
            return False
        action, idx = self._undo_stack.pop()
        plot = self._main_window._browse_tab._plot
        added = plot.manual_added_indices()
        removed = plot.manual_removed_indices()
        # Invert each action exactly. The inverse of "add" is removing
        # from manual_added; inverse of "exclude_algo" is removing from
        # manual_removed; etc.
        if action == "add":
            added.discard(idx)
        elif action == "remove_manual":
            added.add(idx)
        elif action == "exclude_algo":
            removed.discard(idx)
        elif action == "include_algo":
            removed.add(idx)
        plot.set_manual_artifact_indices(added=added, removed=removed)
        self._redo_stack.append((action, idx))
        if len(self._redo_stack) > _UNDO_DEPTH:
            del self._redo_stack[0]
        self._autosave_full_state()
        self._update_undo_redo_actions()
        self._main_window.statusBar().showMessage(f"Undid: {action} @ {idx}", 2000)
        return True

    def redo(self) -> bool:
        """Replay the last undone manual mark. Returns True if anything happened."""
        if not self._redo_stack:
            return False
        action, idx = self._redo_stack.pop()
        plot = self._main_window._browse_tab._plot
        added = plot.manual_added_indices()
        removed = plot.manual_removed_indices()
        if action == "add":
            added.add(idx)
        elif action == "remove_manual":
            added.discard(idx)
        elif action == "exclude_algo":
            removed.add(idx)
        elif action == "include_algo":
            removed.discard(idx)
        plot.set_manual_artifact_indices(added=added, removed=removed)
        self._undo_stack.append((action, idx))
        if len(self._undo_stack) > _UNDO_DEPTH:
            del self._undo_stack[0]
        self._autosave_full_state()
        self._update_undo_redo_actions()
        self._main_window.statusBar().showMessage(f"Redid: {action} @ {idx}", 2000)
        return True

    def _update_undo_redo_actions(self) -> None:
        """Sync the MainWindow Edit-menu actions to the stack contents."""
        mw = self._main_window
        if hasattr(mw, "_undo_action") and mw._undo_action is not None:
            mw._undo_action.setEnabled(bool(self._undo_stack))
        if hasattr(mw, "_redo_action") and mw._redo_action is not None:
            mw._redo_action.setEnabled(bool(self._redo_stack))

    def _autosave_full_state(self) -> None:
        """Persist the FULL artifact state — algo + manual + excluded.

        Called after every manual click (and undo / redo). Mirrors the
        :meth:`_autosave_artifacts` schema so the Streamlit app reads back
        a consistent v1.3 file regardless of which app produced it.
        """
        from rrational.gui.persistence import save_artifact_corrections

        data = self._main_window._data
        active_idx = self._main_window._active_idx
        if (
            data is None
            or active_idx is None
            or active_idx >= len(self._main_window._datasets)
        ):
            return
        ds = self._main_window._datasets[active_idx]
        pid = Path(ds.name).stem
        proj = getattr(self._main_window, "_project", None)
        project_path = proj.project_path if proj is not None else None

        plot = self._main_window._browse_tab._plot
        added = plot.manual_added_indices()
        removed = plot.manual_removed_indices()

        # Streamlit expects manual_artifacts entries to be dicts with at
        # least original_idx, rr_value, timestamp. We synthesise these
        # from the inspector's (t, v) cache.
        manual_artifacts = []
        for i in sorted(added):
            if 0 <= i < len(data.v):
                rr_val = float(data.v[i]) if np.isfinite(data.v[i]) else None
                ts_val = float(data.t[i]) if np.isfinite(data.t[i]) else None
                manual_artifacts.append(
                    {
                        "original_idx": int(i),
                        "rr_value": rr_val,
                        "timestamp": ts_val,
                    }
                )

        algo_indices = (
            [int(i) for i in self._last_result.indices]
            if self._last_result is not None
            else []
        )
        indices_by_type = (
            {k: [] for k in (self._last_result.by_type or {}).keys()}
            if self._last_result is not None
            else {}
        )
        try:
            save_artifact_corrections(
                participant_id=pid,
                manual_artifacts=manual_artifacts,
                artifact_exclusions=[int(i) for i in sorted(removed)],
                algorithm_artifacts=algo_indices,
                algorithm_method="lipponen2019" if algo_indices else None,
                indices_by_type=indices_by_type,
                section_key="_full",
                project_path=project_path,
            )
        except Exception:  # pragma: no cover - autosave must not crash UI
            pass

    def _on_export_clicked(self) -> None:
        """Export the active dataset as a .rrational v2 file.

        Asks for a participant ID (defaults to the dataset name minus
        any extension), then pops a Save-As dialog. The export carries
        the last artifact-detection result if one has been run; otherwise
        raw RR is written with quality = "unknown".
        """
        from rrational.inspector.export import export_inspector_to_rrational

        data = self._main_window._data
        if data is None:
            return

        active_ds = self._main_window._datasets[self._main_window._active_idx]
        default_pid = Path(active_ds.name).stem
        if self._main_window.test_mode:
            participant_id = default_pid
            ok = True
        else:
            participant_id, ok = QInputDialog.getText(
                self,
                "Participant ID",
                "Enter participant ID for this export:",
                text=default_pid,
            )
        if not ok or not participant_id.strip():
            return
        participant_id = participant_id.strip()

        last_dir = settings.read_setting("last_dir") or str(Path.cwd())
        suggested = str(Path(last_dir) / f"{participant_id}.rrational")
        if self._main_window.test_mode:
            out_path_str = suggested
        else:
            out_path_str, _ = QFileDialog.getSaveFileName(
                self,
                "Save as .rrational v2",
                suggested,
                "RRational v2 files (*.rrational)",
            )
        if not out_path_str:
            return
        out_path = Path(out_path_str)

        # Round 32 (PP2) — carry the plot's manual artifact edits into the
        # export so a manually-marked/unmarked beat is reflected in the file,
        # not just the algorithm's set.
        plot = self._main_window._browse_tab._plot
        manual_added = set(getattr(plot, "_manual_added_indices", set()))
        manual_removed = set(getattr(plot, "_manual_removed_indices", set()))
        try:
            export = export_inspector_to_rrational(
                data,
                out_path,
                participant_id=participant_id,
                preprocessing=self._last_result,
                source_path=active_ds.path,
                manual_added=manual_added,
                manual_removed=manual_removed,
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Export failed", f"Could not save .rrational file:\n\n{e}"
            )
            return

        n_sections = len(export.sections)
        n_corrected = sum(
            s.nn_correction.intervals_corrected for s in export.sections.values()
        )
        # Record the export into the reproducible-action history. The
        # ``section`` field is best-effort — we report the first section
        # name (single-section recordings are the common case); a future
        # extension can emit one record per section if needed.
        try:
            history = getattr(self._main_window, "history", None)
            if history is not None:
                section_name = (
                    next(iter(export.sections.keys()), "") if export.sections else ""
                )
                history.record(
                    SaveRRationalExport(
                        pid=participant_id,
                        section=section_name,
                        out_path=str(out_path),
                        n_beats=int(len(data.v)),
                    )
                )
        except Exception:  # pragma: no cover - history must not break export
            pass
        self._main_window.statusBar().showMessage(
            f"Exported {n_sections} section(s), "
            f"{n_corrected} corrected interval(s) → {out_path.name}",
            5000,
        )
        self._export_done_once = True
        self._refresh_workflow_steps()

    # ------------------------------------------------------------------
    # Free-text annotations
    # ------------------------------------------------------------------
    def _on_toggle_annotation_mode(self, checked: bool) -> None:
        plot = self._main_window._browse_tab._plot
        plot.set_annotation_mode(checked)
        if checked:
            self._main_window.statusBar().showMessage(
                "Annotation mode: click on the timeline to add a note.", 4000
            )
        else:
            self._main_window.statusBar().showMessage("Annotation mode off.", 2000)
        if hasattr(self._main_window, "_refresh_status_context"):
            self._main_window._refresh_status_context()

    def _active_pid(self) -> str | None:
        """Stem of the active dataset's filename, used as persistence key."""
        active_idx = self._main_window._active_idx
        if active_idx is None or active_idx >= len(self._main_window._datasets):
            return None
        return Path(self._main_window._datasets[active_idx].name).stem

    def _project_path(self):
        proj = getattr(self._main_window, "_project", None)
        return proj.project_path if proj is not None else None

    def _refresh_annotation_label(self) -> None:
        n = len(self._annotations)
        # Label has the "muted" property + RichText format set at build
        # time — palette-aware grey + working inline markup come for free.
        if n == 0:
            self._annotation_count_label.setText("No annotations.")
        else:
            self._annotation_count_label.setText(
                f"<b>{n}</b> annotation(s) on this dataset."
            )
        # Cluster A8 — keep the status-bar count in sync. Centralised
        # here so create / delete / restore paths all flow through one
        # status update site.
        if hasattr(self._main_window, "_refresh_status_context"):
            self._main_window._refresh_status_context()

    def _persist_annotations(self) -> None:
        from rrational.inspector.annotation_persistence import (
            save_annotations as _save_annotations,
        )

        pid = self._active_pid()
        if pid is None:
            return
        try:
            _save_annotations(pid, self._annotations, project_path=self._project_path())
        except Exception:  # pragma: no cover - autosave must not crash
            pass

    def _restore_annotations(self) -> None:
        """Read annotations from disk + render markers for the active dataset."""
        from rrational.inspector.annotation_persistence import (
            load_annotations as _load_annotations,
        )

        plot = self._main_window._browse_tab._plot
        plot.clear_annotation_markers()
        self._annotations = []
        pid = self._active_pid()
        if pid is None:
            self._refresh_annotation_label()
            return
        try:
            stored = _load_annotations(pid, project_path=self._project_path())
        except Exception:
            stored = []
        self._annotations = list(stored)
        for ann in self._annotations:
            plot.add_annotation_marker(ann.t, ann.text)
        self._refresh_annotation_label()

    def _on_plot_clicked(self, t: float) -> None:
        """Annotation-mode left-click on the timeline: pop input dialog."""
        from rrational.inspector.annotations import Annotation as _Annotation

        if not self._toggle_annotation_mode.isChecked():
            return
        if self._main_window.test_mode:
            text = f"auto-test annotation @ {t:.0f}"
            ok = True
        else:
            text, ok = QInputDialog.getText(self, "New annotation", "Note text:")
        if not ok or not str(text).strip():
            return
        text = str(text).strip()
        ann = _Annotation.create(t=t, text=text)
        self._annotations.append(ann)
        plot = self._main_window._browse_tab._plot
        plot.add_annotation_marker(ann.t, ann.text)
        self._persist_annotations()
        self._refresh_annotation_label()
        self._record_annotation_history(ann.t, ann.text)
        self._main_window.statusBar().showMessage(
            f"Added annotation '{ann.text[:40]}'", 3000
        )

    def _on_plot_range_selected(self, t0: float, t1: float) -> None:
        """Annotation-mode drag finished — pin a range annotation.

        Stores onset + duration directly (MNE-style) so the annotation
        round-trips as a real range through persistence, the table
        dialog, the recipe export, and any future BIDS-physio export.
        """
        from rrational.inspector.annotations import Annotation as _Annotation

        if not self._toggle_annotation_mode.isChecked():
            return
        width_s = abs(float(t1) - float(t0))
        if self._main_window.test_mode:
            text = f"auto-test range @ {min(t0, t1):.0f} ({width_s:.1f}s)"
            ok = True
        else:
            text, ok = QInputDialog.getText(
                self,
                "New annotation",
                f"Note text (range: {width_s:.1f} s):",
            )
        if not ok or not str(text).strip():
            return
        text = str(text).strip()
        ann = _Annotation.create_range(t_start=float(t0), t_end=float(t1), text=text)
        self._annotations.append(ann)
        plot = self._main_window._browse_tab._plot
        # The marker is still pinned at the onset — the duration shows
        # up in the table dialog + tooltip rather than as a band on the
        # plot (which we keep visually distinct from exclusion zones).
        plot.add_annotation_marker(ann.t, ann.text)
        self._persist_annotations()
        self._refresh_annotation_label()
        self._record_annotation_history(ann.t, ann.text)
        self._main_window.statusBar().showMessage(
            f"Added annotation '{ann.text[:40]}'", 3000
        )

    # ------------------------------------------------------------------
    # History bridge — record annotation + exclusion actions
    # ------------------------------------------------------------------
    def _record_annotation_history(self, t: float, label: str) -> None:
        """Push one :class:`AddAnnotation` into the inspector history.

        Best-effort: an exception in the recorder must never break the
        annotation flow. ``pid`` falls back to an empty string when no
        active dataset is loaded so the rendered recipe still parses.
        """
        try:
            history = getattr(self._main_window, "history", None)
            if history is None:
                return
            pid = self._active_pid() or ""
            history.record(AddAnnotation(pid=pid, t=float(t), label=str(label)))
        except Exception:  # pragma: no cover - history must not break
            pass

    def _record_exclusion_history(self, zone) -> None:
        """Push one :class:`AddExclusionZone` into the inspector history."""
        try:
            history = getattr(self._main_window, "history", None)
            if history is None:
                return
            pid = self._active_pid() or ""
            history.record(
                AddExclusionZone(
                    pid=pid,
                    t_start=float(zone.start_t),
                    t_end=float(zone.end_t),
                    reason=str(zone.reason or ""),
                )
            )
        except Exception:  # pragma: no cover - history must not break
            pass

    def _annotation_for_marker(self, marker) -> "Annotation | None":
        """Find the dataclass that produced ``marker`` (match by time)."""
        for ann in self._annotations:
            if abs(ann.t - marker.annotation_t) < 1e-6:
                return ann
        return None

    def _on_annotation_right_clicked(self, marker, screen_pos) -> None:
        """Right-click on an annotation marker → edit / delete menu."""
        from qtpy.QtWidgets import QMenu as _QMenu

        ann = self._annotation_for_marker(marker)
        if ann is None:
            return
        if self._main_window.test_mode:
            # Default to "no-op" in headless tests; tests drive
            # ``edit_annotation`` / ``delete_annotation`` directly.
            return
        menu = _QMenu(self)
        edit_act = menu.addAction("Edit annotation…")
        delete_act = menu.addAction("Delete annotation")
        if screen_pos is None:
            # Falling back to the panel's centre is fine — exec_ accepts None
            # but Qt warns; offset slightly into the panel for visibility.
            screen_pos = self.mapToGlobal(self.rect().center())
        try:
            point = screen_pos.toPoint()
        except AttributeError:
            point = screen_pos
        chosen = menu.exec(point)
        if chosen is edit_act:
            self.edit_annotation(ann)
        elif chosen is delete_act:
            self.delete_annotation(ann)

    def edit_annotation(self, ann: "Annotation") -> None:
        """Pop an edit-text dialog for ``ann`` and persist on accept."""
        if self._main_window.test_mode:
            new_text = ann.text + " (edited)"
            ok = True
        else:
            new_text, ok = QInputDialog.getText(
                self, "Edit annotation", "Note text:", text=ann.text
            )
        if not ok or not str(new_text).strip():
            return
        ann.text = str(new_text).strip()
        # Update the matching marker label / tooltip in place.
        plot = self._main_window._browse_tab._plot
        for m in plot.annotation_markers():
            if abs(m.annotation_t - ann.t) < 1e-6:
                m.set_annotation_text(ann.text)
                break
        self._persist_annotations()
        self._refresh_annotation_label()

    def delete_annotation(self, ann: "Annotation") -> None:
        """Remove ``ann`` from state + disk + plot."""
        plot = self._main_window._browse_tab._plot
        for m in list(plot.annotation_markers()):
            if abs(m.annotation_t - ann.t) < 1e-6:
                plot.remove_annotation_marker(m)
                break
        try:
            self._annotations.remove(ann)
        except ValueError:
            pass
        self._persist_annotations()
        self._refresh_annotation_label()
