"""Analysis tab — HRV-metric computation modes.

Phase 4c brings the first two of RRational's four analysis modes:

- **Single Participant**: pick a dataset + section, get HRV metrics for
  that one segment
- **Repeating Section**: pick a section name, get the same metrics
  computed across every loaded dataset that has that section (e.g.
  "rest_pre" across all subjects)

Group + Sequence Comparison land in Phase 4d.

All modes delegate the science to ``rrational.analysis.hrv_compute``;
this module is just the UI form + result-table rendering on top.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rrational.inspector.tabs.base import InspectorTab

if TYPE_CHECKING:
    from rrational.inspector.data_loader import InspectorData

# Subset of metrics we expose by default. Picked as the "Basic" preset
# from rrational/analysis/hrv_metrics — every researcher recognises
# RMSSD, SDNN, LF/HF, pNN50.
_DEFAULT_METRICS = ["RMSSD", "SDNN", "MeanHR", "LF", "HF", "LF_HF", "pNN50"]


def _format_metric(value) -> str:
    """Format an HRV-metric value for table display."""
    if value is None:
        return "—"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(f):
        return "—"
    if abs(f) >= 1000 or abs(f) < 0.01:
        return f"{f:.2e}"
    return f"{f:.2f}"


def _slice_section(data: "InspectorData", section_name: str) -> np.ndarray | None:
    """Return the RR (ms) values inside the section with the given name."""
    section = next((s for s in data.sections if s.name == section_name), None)
    if section is None:
        return None
    in_section = (data.t >= section.t_start) & (data.t <= section.t_end)
    finite = np.isfinite(data.v)
    return data.v[in_section & finite]


def _compute_metrics(rr_ms: np.ndarray) -> dict[str, float]:
    """Run HRV compute on an RR array. Returns metric → value."""
    from rrational.analysis.hrv_compute import calculate_hrv_metrics

    if len(rr_ms) < 10:
        return {m: float("nan") for m in _DEFAULT_METRICS}
    metrics, _, _ = calculate_hrv_metrics(
        nn_ms_list=rr_ms.tolist(),
        use_windows=False,
        selected_metrics=_DEFAULT_METRICS,
    )
    return metrics


class _SingleParticipantPane(QWidget):
    """Pick a dataset + section, compute HRV metrics on that segment."""

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self._main_window = main_window

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        form_box = QGroupBox("Inputs")
        form = QFormLayout(form_box)
        self._dataset_combo = QComboBox()
        self._dataset_combo.currentIndexChanged.connect(self._on_dataset_changed)
        self._section_combo = QComboBox()
        form.addRow("Dataset:", self._dataset_combo)
        form.addRow("Section:", self._section_combo)
        outer.addWidget(form_box)

        button_row = QHBoxLayout()
        self._compute_btn = QPushButton("Compute HRV metrics")
        self._compute_btn.clicked.connect(self._on_compute)
        self._compute_btn.setEnabled(False)
        button_row.addWidget(self._compute_btn)
        button_row.addStretch()
        outer.addLayout(button_row)

        self._result_table = QTableWidget(0, 2, self)
        self._result_table.setHorizontalHeaderLabels(["Metric", "Value"])
        self._result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._result_table.setAlternatingRowColors(True)
        self._result_table.verticalHeader().setVisible(False)
        self._result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        outer.addWidget(self._result_table)

    def refresh_workspace(self) -> None:
        """Rebuild the dataset dropdown from the workspace."""
        prev = self._dataset_combo.currentData()
        self._dataset_combo.blockSignals(True)
        self._dataset_combo.clear()
        for i, ds in enumerate(self._main_window._datasets):
            self._dataset_combo.addItem(ds.name, i)
        # Restore previous selection if still valid
        if prev is not None:
            idx = self._dataset_combo.findData(prev)
            if idx >= 0:
                self._dataset_combo.setCurrentIndex(idx)
        self._dataset_combo.blockSignals(False)
        self._on_dataset_changed(self._dataset_combo.currentIndex())

    def _on_dataset_changed(self, _row: int) -> None:
        self._section_combo.clear()
        idx = self._dataset_combo.currentData()
        if idx is None or not (0 <= idx < len(self._main_window._datasets)):
            self._compute_btn.setEnabled(False)
            return
        ds = self._main_window._datasets[idx]
        for sec in ds.data.sections:
            self._section_combo.addItem(sec.name)
        self._compute_btn.setEnabled(self._section_combo.count() > 0)

    def _on_compute(self) -> None:
        ds_idx = self._dataset_combo.currentData()
        sec_name = self._section_combo.currentText()
        if ds_idx is None or not sec_name:
            return
        ds = self._main_window._datasets[ds_idx]
        rr = _slice_section(ds.data, sec_name)
        if rr is None or len(rr) == 0:
            self._main_window.statusBar().showMessage(
                f"No samples in section '{sec_name}'", 3000
            )
            return
        self._main_window.statusBar().showMessage(
            f"Computing HRV on '{sec_name}' ({len(rr)} beats)…"
        )
        metrics = _compute_metrics(rr)
        self._populate_result_table(metrics, n_beats=len(rr), section=sec_name)
        self._main_window.statusBar().showMessage(
            f"HRV computed for {ds.name} · {sec_name} ({len(rr)} beats)", 4000
        )

    def _populate_result_table(self, metrics: dict, n_beats: int, section: str) -> None:
        self._result_table.setRowCount(0)
        # First row: meta info
        meta_rows = [
            ("Section", section),
            ("Beats analysed", str(n_beats)),
        ]
        for name, value in meta_rows:
            row = self._result_table.rowCount()
            self._result_table.insertRow(row)
            self._result_table.setItem(row, 0, QTableWidgetItem(name))
            self._result_table.setItem(row, 1, QTableWidgetItem(value))
        # Metric rows
        for m in _DEFAULT_METRICS:
            row = self._result_table.rowCount()
            self._result_table.insertRow(row)
            self._result_table.setItem(row, 0, QTableWidgetItem(m))
            self._result_table.setItem(
                row, 1, QTableWidgetItem(_format_metric(metrics.get(m)))
            )


class _RepeatingSectionPane(QWidget):
    """Pick one section name; compute HRV across every dataset that has it."""

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self._main_window = main_window

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        form_box = QGroupBox("Inputs")
        form = QFormLayout(form_box)
        self._section_combo = QComboBox()
        form.addRow("Section name (across datasets):", self._section_combo)
        outer.addWidget(form_box)

        button_row = QHBoxLayout()
        self._compute_btn = QPushButton("Compute across all datasets")
        self._compute_btn.clicked.connect(self._on_compute)
        self._compute_btn.setEnabled(False)
        button_row.addWidget(self._compute_btn)
        button_row.addStretch()
        outer.addLayout(button_row)

        self._result_table = QTableWidget(0, 1 + len(_DEFAULT_METRICS), self)
        self._result_table.setHorizontalHeaderLabels(["Dataset", *_DEFAULT_METRICS])
        self._result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._result_table.setAlternatingRowColors(True)
        self._result_table.verticalHeader().setVisible(False)
        self._result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        outer.addWidget(self._result_table)

    def refresh_workspace(self) -> None:
        """Rebuild the section-name dropdown from the union across datasets."""
        prev = self._section_combo.currentText()
        section_names = sorted(
            {sec.name for ds in self._main_window._datasets for sec in ds.data.sections}
        )
        self._section_combo.blockSignals(True)
        self._section_combo.clear()
        for name in section_names:
            self._section_combo.addItem(name)
        if prev in section_names:
            idx = self._section_combo.findText(prev)
            if idx >= 0:
                self._section_combo.setCurrentIndex(idx)
        self._section_combo.blockSignals(False)
        self._compute_btn.setEnabled(bool(section_names))

    def _on_compute(self) -> None:
        sec_name = self._section_combo.currentText()
        if not sec_name:
            return
        self._main_window.statusBar().showMessage(
            f"Computing HRV on '{sec_name}' across every dataset…"
        )
        rows: list[tuple[str, dict]] = []
        for ds in self._main_window._datasets:
            rr = _slice_section(ds.data, sec_name)
            if rr is None or len(rr) == 0:
                continue
            metrics = _compute_metrics(rr)
            rows.append((ds.name, metrics))
        self._populate_result_table(rows)
        self._main_window.statusBar().showMessage(
            f"HRV computed for '{sec_name}' on {len(rows)} dataset(s)", 4000
        )

    def _populate_result_table(self, rows: list[tuple[str, dict]]) -> None:
        self._result_table.setRowCount(0)
        for ds_name, metrics in rows:
            row = self._result_table.rowCount()
            self._result_table.insertRow(row)
            self._result_table.setItem(row, 0, QTableWidgetItem(ds_name))
            for col, m in enumerate(_DEFAULT_METRICS, start=1):
                self._result_table.setItem(
                    row, col, QTableWidgetItem(_format_metric(metrics.get(m)))
                )


class _ComingSoonPane(QWidget):
    """Placeholder for Group + Sequence Comparison (Phase 4d)."""

    def __init__(self, label: str, body: str, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        msg = QLabel(f"<h3>{label}</h3><p style='color:#888'>{body}</p>")
        msg.setAlignment(Qt.AlignCenter)
        msg.setWordWrap(True)
        layout.addWidget(msg)


class AnalysisTab(InspectorTab):
    TAB_LABEL = "Analysis"

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(main_window, parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        # Mode selector at the top — switches the stacked widget below.
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self._mode_combo = QComboBox()
        self._mode_combo.addItem("Single Participant", "single")
        self._mode_combo.addItem("Repeating Section", "repeating")
        self._mode_combo.addItem("Group (Phase 4d)", "group_stub")
        self._mode_combo.addItem("Sequence Comparison (Phase 4d)", "sequence_stub")
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._mode_combo)
        mode_row.addStretch()
        outer.addLayout(mode_row)

        self._stack = QStackedWidget(self)
        self._single_pane = _SingleParticipantPane(main_window, self)
        self._repeating_pane = _RepeatingSectionPane(main_window, self)
        self._group_pane = _ComingSoonPane(
            "Group",
            "Compare HRV metrics across condition groups with hypothesis tests. "
            "Coming in Phase 4d.",
            self,
        )
        self._sequence_pane = _ComingSoonPane(
            "Sequence Comparison",
            "Compare ordered chains of sections (e.g. music_block_1 → rest → "
            "music_block_2) across participants. Coming in Phase 4d.",
            self,
        )
        self._stack.addWidget(self._single_pane)
        self._stack.addWidget(self._repeating_pane)
        self._stack.addWidget(self._group_pane)
        self._stack.addWidget(self._sequence_pane)
        outer.addWidget(self._stack)

    def _on_mode_changed(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # Notification hooks
    # ------------------------------------------------------------------
    def on_workspace_changed(self) -> None:
        self._single_pane.refresh_workspace()
        self._repeating_pane.refresh_workspace()

    def on_active_dataset_changed(self, data: "InspectorData | None") -> None:
        # Single-Participant pane defaults to whatever's currently active;
        # easiest is to re-sync from the workspace each time.
        self._single_pane.refresh_workspace()
        if data is not None:
            idx = self._main_window._active_idx
            if idx is not None:
                self._single_pane._dataset_combo.setCurrentIndex(idx)
