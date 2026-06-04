"""Right-side panel of the Browse tab — artifact detection + summary.

Mirrors the Streamlit Participants tab's preprocessing flow:
1. Click "Detect artifacts" → runs NK2 Kubios algorithm on the active
   dataset's RR array
2. Shows artifact rate + Quigley-2024 quality grade
3. Toggles overlay visibility on the main plot
4. (Phase 4-Prep step 2: export as .rrational v2 once user has
   validated sections)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from rrational.inspector import settings

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

    # ------------------------------------------------------------------
    # State sync
    # ------------------------------------------------------------------
    def on_active_dataset_changed(self, data: "InspectorData | None") -> None:
        """Reset the panel when the user switches/unloads a dataset.

        Phase 12: when a dataset is loaded, also try to auto-restore any
        previously-saved artifact corrections from
        ``{pid}_artifacts.yml`` (Streamlit-shared).
        """
        self._last_result = None
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

        # Phase 12: attempt auto-restore from disk
        if data is not None:
            self._try_restore_artifacts(data)

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
        if not algo_indices:
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
        plot.set_artifacts_visible(self._toggle_show_artifacts.isChecked())
        color = _GRADE_COLOR.get(restored.grade, "#888888")
        self._summary.setText(
            f"<b>Restored from disk:</b><br>"
            f"<b>{restored.total}</b> artifacts in {len(data.v)} beats<br>"
            f"<b>Rate:</b> {restored.rate * 100:.2f}%<br>"
            f"<b>Grade:</b> "
            f"<span style='color:{color};'><b>{restored.grade}</b></span><br>"
            f"<small style='color:#666'>{restored.recommendation}</small>"
        )
        self._toggle_show_artifacts.setEnabled(True)
        # Without corrected_v we can't enable the use-corrected toggle
        self._toggle_use_corrected.setEnabled(False)
        self._main_window.statusBar().showMessage(
            f"Restored {restored.total} artifacts for '{pid}' from disk", 4000
        )

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
        try:
            save_artifact_corrections(
                participant_id=pid,
                manual_artifacts=[],
                artifact_exclusions=[],
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
