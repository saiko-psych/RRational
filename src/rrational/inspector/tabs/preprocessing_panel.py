"""Right-side panel of the Browse tab — artifact detection + summary.

Mirrors the Streamlit Participants tab's preprocessing flow:
1. Click "Detect artifacts" → runs NK2 Kubios algorithm on the active
   dataset's RR array
2. Shows artifact rate + Quigley-2024 quality grade
3. Toggles overlay visibility on the main plot
4. (Phase 4-Prep step 2: export as .rrational v2 once user has
   validated sections)

Phase 15 adds an exclusion-mode toggle + a per-dataset zones list (with
Edit / Delete buttons) that auto-persists to ``{pid}_exclusions.yml``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
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

if TYPE_CHECKING:
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

# Phase 14: cap on the undo/redo stack size. 50 mirrors mne-qt-browser's
# default annotation undo depth.
_UNDO_DEPTH = 50


class PreprocessingPanel(QWidget):
    """Side panel that runs artifact detection and shows the result."""

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self._main_window = main_window
        self._last_result: "PreprocessingResult | None" = None

        self.setMaximumWidth(280)
        self.setMinimumWidth(220)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QLabel("<b>Preprocessing</b>")
        header.setAlignment(Qt.AlignLeft)
        layout.addWidget(header)

        self._detect_btn = QPushButton("Detect artifacts")
        self._detect_btn.setToolTip(
            "Run NeuroKit2 Kubios algorithm on the active dataset's RR series"
        )
        self._detect_btn.clicked.connect(self._on_detect_clicked)
        # Disabled until on_active_dataset_changed fires with real data.
        self._detect_btn.setEnabled(False)
        layout.addWidget(self._detect_btn)

        # Quality summary (multi-line label).
        self._summary = QLabel(
            "No artifact detection run yet.\n\nLoad a recording, then "
            "click <i>Detect artifacts</i>."
        )
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet("color: #555; padding: 4px 0;")
        layout.addWidget(self._summary)

        # Divider so the toggle group reads as a separate block.
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        self._toggle_show_artifacts = QCheckBox("Show artifact markers")
        self._toggle_show_artifacts.setChecked(True)
        self._toggle_show_artifacts.toggled.connect(self._on_toggle_show_artifacts)
        self._toggle_show_artifacts.setEnabled(False)
        layout.addWidget(self._toggle_show_artifacts)

        self._toggle_use_corrected = QCheckBox("Use corrected RR values")
        self._toggle_use_corrected.setChecked(False)
        self._toggle_use_corrected.setToolTip(
            "Replace the plotted RR series with the artifact-corrected "
            "(interpolated) version."
        )
        self._toggle_use_corrected.toggled.connect(self._on_toggle_use_corrected)
        self._toggle_use_corrected.setEnabled(False)
        layout.addWidget(self._toggle_use_corrected)

        # Phase 14 — Manual artifact marking (MNE-LAB-style).
        self._toggle_manual_mark = QCheckBox("Manual mark mode")
        self._toggle_manual_mark.setChecked(False)
        self._toggle_manual_mark.setToolTip(
            "Click on the timeline to mark a beat as an artifact, click an "
            "existing algorithm artifact to exclude it, or click a manual "
            "mark to remove it."
        )
        self._toggle_manual_mark.toggled.connect(self._on_toggle_manual_mark)
        self._toggle_manual_mark.setEnabled(False)
        layout.addWidget(self._toggle_manual_mark)

        self._manual_help = QLabel(
            "<small style='color:#666'>"
            "Left-click near a beat: add manual mark<br>"
            "Left-click on algorithm artifact: exclude<br>"
            "Left-click on manual mark: remove<br>"
            "Edit → Undo / Redo (Ctrl+Z / Ctrl+Y)"
            "</small>"
        )
        self._manual_help.setWordWrap(True)
        self._manual_help.setVisible(False)
        layout.addWidget(self._manual_help)

        # Undo/redo stacks. Each entry is a (action_tag, idx) tuple —
        # replayed in reverse on undo, re-applied on redo. Capped at
        # ``_UNDO_DEPTH`` so a long marathon session doesn't hoard memory.
        self._undo_stack: list[tuple[str, int]] = []
        self._redo_stack: list[tuple[str, int]] = []

        # ----- Phase 15 - Exclusion zones -----------------------------------
        sep_excl = QFrame()
        sep_excl.setFrameShape(QFrame.HLine)
        sep_excl.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep_excl)

        excl_header = QLabel("<b>Exclusion zones</b>")
        layout.addWidget(excl_header)

        self._toggle_exclusion_mode = QCheckBox("Exclusion mode (drag-select)")
        self._toggle_exclusion_mode.setToolTip(
            "When ON, click-drag on the plot creates a new exclusion zone. "
            "Beats inside a zone are filtered out of every HRV analysis."
        )
        self._toggle_exclusion_mode.toggled.connect(self._on_toggle_exclusion_mode)
        layout.addWidget(self._toggle_exclusion_mode)

        self._zones_table = QTableWidget(0, 4, self)
        self._zones_table.setHorizontalHeaderLabels(["Start", "End", "Reason", ""])
        self._zones_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._zones_table.verticalHeader().setVisible(False)
        self._zones_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self._zones_table.setMaximumHeight(160)
        layout.addWidget(self._zones_table)

        # Listen for any zone mutation so we can refresh the table + auto-save.
        # The plot is created inside BrowseTab BEFORE this panel - but the
        # BrowseTab hasn't published itself on ``main_window`` yet, so we
        # reach the plot through the panel's ``parent`` (the BrowseTab
        # instance). Guarded with getattr to keep the panel testable in
        # isolation.
        plot = getattr(parent, "_plot", None)
        if plot is not None:
            plot.exclusion_zones_changed.connect(self._on_zones_changed)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep2)

        self._export_btn = QPushButton("Save as .rrational v2…")
        self._export_btn.setToolTip(
            "Export the current dataset (plus detected artifacts + "
            "any section overrides) as a .rrational v2 file"
        )
        self._export_btn.clicked.connect(self._on_export_clicked)
        self._export_btn.setEnabled(False)
        layout.addWidget(self._export_btn)

        layout.addStretch()

        # Phase 14: wire the plot's manual-click signal to our handler.
        # BrowseTab constructs the plot then this panel inside the same
        # ``_build`` call, so ``parent`` is the BrowseTab and ``_plot``
        # is already live. Going through ``parent`` rather than
        # ``main_window._browse_tab`` matters: the latter isn't assigned
        # on MainWindow until BrowseTab.__init__ returns.
        plot = parent._plot if parent is not None and hasattr(parent, "_plot") else None
        if plot is not None:
            plot.manual_artifact_changed.connect(self._on_manual_artifact_changed)

    # ------------------------------------------------------------------
    # State sync
    # ------------------------------------------------------------------
    def on_active_dataset_changed(self, data: "InspectorData | None") -> None:
        """Reset the panel when the user switches/unloads a dataset.

        Phase 12: when a dataset is loaded, also try to auto-restore any
        previously-saved artifact corrections from
        ``{pid}_artifacts.yml`` (Streamlit-shared).
        Phase 14: also reset the undo/redo stacks (per-dataset history)
        and the plot's manual / excluded sets.
        Phase 15: same drill for exclusion zones from ``{pid}_exclusions.yml``.
        """
        self._last_result = None
        self._undo_stack.clear()
        self._redo_stack.clear()
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
        # Reset the plot's manual sets too. The Phase-12 restore below
        # will repopulate them if the dataset has prior corrections.
        plot = self._main_window._browse_tab._plot
        plot.set_manual_artifact_indices(added=set(), removed=set())
        plot.set_manual_mark_mode(False)
        self._update_undo_redo_actions()

        # Phase 12: attempt auto-restore from disk
        if data is not None:
            self._try_restore_artifacts(data)
            self._try_restore_exclusion_zones(data)
        # When unloading a dataset, clear the zones table; the plot's
        # own clear_overlays / clear_exclusion_zones (called by
        # set_data) already dropped the regions.
        if data is None:
            self._refresh_zones_table()

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
        # Phase 14: also restore manual + excluded sets.
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

        # Rebuild a PreprocessingResult shell (we don't reload corrected_v
        # from disk — that lives in nn_metadata.yml in Phase 12.2).
        import numpy as _np

        indices_arr = _np.asarray(algo_indices, dtype=_np.int64)
        rate = (len(indices_arr) / len(data.v)) if len(data.v) > 0 else 0.0
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
        # Phase 14: push manual sets BEFORE flipping visibility so the
        # refresh paints them on the same overlay-show cycle.
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
    # Phase 15 — Exclusion zones
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

    def _on_zones_changed(self) -> None:
        """Plot fired ``exclusion_zones_changed`` — refresh + auto-save."""
        self._refresh_zones_table()
        self._autosave_exclusion_zones()

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
        # Phase 12: auto-persist so future loads restore this state
        self._autosave_artifacts(result, data)
        self._main_window.statusBar().showMessage(
            f"Artifact detection: {result.total} found "
            f"({result.rate * 100:.2f}%, {result.grade})",
            4000,
        )

    def _autosave_artifacts(self, result, data: "InspectorData") -> None:
        """Phase 12: persist the freshly-detected artifacts to disk.

        Writes to ``{project}/data/processed/{pid}_artifacts.yml`` (or
        the global fallback) using the v1.3 section-scoped schema with
        section_key=`_full` — matches what Streamlit produces for a
        whole-recording detection. Silent on failure (autosave must not
        crash compute).

        Phase 14: also preserves any pre-existing manual / excluded
        marks the user already had on the plot — re-running Detect
        doesn't wipe their hand-edits.
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

    def _on_toggle_show_artifacts(self, checked: bool) -> None:
        plot = self._main_window._browse_tab._plot
        plot.set_artifacts_visible(checked)

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

    # ------------------------------------------------------------------
    # Phase 14 — Manual artifact marking + undo / redo
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

        try:
            export = export_inspector_to_rrational(
                data,
                out_path,
                participant_id=participant_id,
                preprocessing=self._last_result,
                source_path=active_ds.path,
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
        self._main_window.statusBar().showMessage(
            f"Exported {n_sections} section(s), "
            f"{n_corrected} corrected interval(s) → {out_path.name}",
            5000,
        )
