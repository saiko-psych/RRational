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
        from rrational.inspector.results_store import MetricRow

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
        # Push to the central results store; Results tab picks it up.
        self._main_window._results_store.add_metric_row(
            MetricRow(
                mode="single",
                dataset=ds.name,
                section=sec_name,
                n_beats=int(len(rr)),
                metrics=dict(metrics),
            )
        )
        self._main_window._results_tab.refresh_results()
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
        from rrational.inspector.results_store import MetricRow

        sec_name = self._section_combo.currentText()
        if not sec_name:
            return
        self._main_window.statusBar().showMessage(
            f"Computing HRV on '{sec_name}' across every dataset…"
        )
        rows: list[tuple[str, dict, int]] = []
        for ds in self._main_window._datasets:
            rr = _slice_section(ds.data, sec_name)
            if rr is None or len(rr) == 0:
                continue
            metrics = _compute_metrics(rr)
            rows.append((ds.name, metrics, int(len(rr))))
        self._populate_result_table([(n, m) for n, m, _ in rows])
        # Push each per-dataset row into the central store.
        for ds_name, metrics, n_beats in rows:
            self._main_window._results_store.add_metric_row(
                MetricRow(
                    mode="repeating",
                    dataset=ds_name,
                    section=sec_name,
                    n_beats=n_beats,
                    metrics=dict(metrics),
                )
            )
        self._main_window._results_tab.refresh_results()
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


class _GroupComparisonPane(QWidget):
    """Per-dataset group assignment + hypothesis-test comparison.

    Two assignment modes:

    - **Saved groups** (Streamlit-shared): pick from groups defined in
      the Setup tab's Groups sub-pane (which writes ``groups.yml`` via
      ``gui.persistence.save_groups``). Members are auto-applied.
    - **Ad-hoc labels**: type a free-text label directly in the second
      column of the assignment table. Useful for quick exploration.
      When Compute is clicked, the ad-hoc assignment can be persisted
      as a new group definition via the "Save as group…" button.
    """

    DEFAULT_GROUP = ""  # empty string = unassigned

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self._main_window = main_window
        # Per-dataset group label (keyed by dataset index — re-keyed on
        # workspace change so close-then-reload doesn't carry stale labels).
        self._group_by_idx: dict[int, str] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        # ---- 1a. Saved-groups picker (top) ---------------------------
        saved_box = QGroupBox("Saved groups (from Setup → Groups)")
        saved_row = QHBoxLayout(saved_box)
        self._saved_groups_combo = QComboBox()
        self._saved_groups_combo.setPlaceholderText("Pick a saved group definition…")
        self._apply_saved_btn = QPushButton("Apply members")
        self._apply_saved_btn.setToolTip(
            "Apply the selected saved group's member list to the assignment table"
        )
        self._apply_saved_btn.clicked.connect(self._on_apply_saved)
        self._apply_saved_btn.setEnabled(False)
        self._saved_groups_combo.currentIndexChanged.connect(
            lambda _: self._apply_saved_btn.setEnabled(
                self._saved_groups_combo.currentIndex() >= 0
            )
        )
        saved_row.addWidget(self._saved_groups_combo, 1)
        saved_row.addWidget(self._apply_saved_btn)
        outer.addWidget(saved_box)

        # ---- 1b. Group assignment table ------------------------------
        assign_box = QGroupBox("Group assignment (edit column 2 for ad-hoc labels)")
        assign_layout = QVBoxLayout(assign_box)
        self._assign_table = QTableWidget(0, 2, self)
        self._assign_table.setHorizontalHeaderLabels(["Dataset", "Group"])
        self._assign_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._assign_table.verticalHeader().setVisible(False)
        self._assign_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._assign_table.itemChanged.connect(self._on_assignment_changed)
        assign_layout.addWidget(self._assign_table)

        # "Save as group" button — persists current ad-hoc labels as a
        # named group definition the Streamlit app will see too.
        save_row = QHBoxLayout()
        save_row.addStretch()
        self._save_as_group_btn = QPushButton("Save assignment as new group…")
        self._save_as_group_btn.setToolTip(
            "Persist the current assignment as one or more groups in groups.yml"
        )
        self._save_as_group_btn.clicked.connect(self._on_save_as_group)
        self._save_as_group_btn.setEnabled(False)
        save_row.addWidget(self._save_as_group_btn)
        assign_layout.addLayout(save_row)
        outer.addWidget(assign_box)

        # ---- 2. Inputs + Compute -------------------------------------
        form_box = QGroupBox("Comparison inputs")
        form = QFormLayout(form_box)
        self._section_combo = QComboBox()
        self._metric_combo = QComboBox()
        for m in _DEFAULT_METRICS:
            self._metric_combo.addItem(m)
        form.addRow("Section name:", self._section_combo)
        form.addRow("Metric:", self._metric_combo)
        outer.addWidget(form_box)

        button_row = QHBoxLayout()
        self._compute_btn = QPushButton("Compare across groups")
        self._compute_btn.clicked.connect(self._on_compute)
        self._compute_btn.setEnabled(False)
        button_row.addWidget(self._compute_btn)
        button_row.addStretch()
        outer.addLayout(button_row)

        # ---- 3. Result panel -----------------------------------------
        self._result_label = QLabel(
            "<i>Assign a group label to at least two datasets, then click "
            "<b>Compare across groups</b>.</i>"
        )
        self._result_label.setWordWrap(True)
        self._result_label.setStyleSheet("padding: 8px;")
        outer.addWidget(self._result_label)

        self._group_stats_table = QTableWidget(0, 5, self)
        self._group_stats_table.setHorizontalHeaderLabels(
            ["Group", "n", "Mean", "SD", "Normal (p)"]
        )
        self._group_stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._group_stats_table.setAlternatingRowColors(True)
        self._group_stats_table.verticalHeader().setVisible(False)
        self._group_stats_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        outer.addWidget(self._group_stats_table)

    # ------------------------------------------------------------------
    # Workspace sync
    # ------------------------------------------------------------------
    def refresh_workspace(self) -> None:
        # Rebuild section list (union across datasets)
        prev_sec = self._section_combo.currentText()
        section_names = sorted(
            {sec.name for ds in self._main_window._datasets for sec in ds.data.sections}
        )
        self._section_combo.blockSignals(True)
        self._section_combo.clear()
        for name in section_names:
            self._section_combo.addItem(name)
        if prev_sec in section_names:
            self._section_combo.setCurrentIndex(self._section_combo.findText(prev_sec))
        self._section_combo.blockSignals(False)

        # Re-key the group labels by current dataset index. We use the
        # dataset NAME as the persistence key so closing+reopening a
        # file keeps its assignment.
        new_label_by_idx: dict[int, str] = {}
        old_label_by_name = {
            self._main_window._datasets[i].name: lbl
            for i, lbl in self._group_by_idx.items()
            if i < len(self._main_window._datasets)
        }
        for i, ds in enumerate(self._main_window._datasets):
            new_label_by_idx[i] = old_label_by_name.get(ds.name, self.DEFAULT_GROUP)
        self._group_by_idx = new_label_by_idx

        # Auto-populate from saved groups: if a dataset's name appears in
        # a saved group's members list, pre-fill its label with that
        # group name (only when current label is empty — never overwrite
        # user-typed ad-hoc labels).
        saved = self._load_saved_groups()
        for i, ds in enumerate(self._main_window._datasets):
            if not self._group_by_idx[i]:
                for grp_name, grp_data in saved.items():
                    if ds.name in (grp_data.get("members") or []):
                        self._group_by_idx[i] = grp_name
                        break

        # Repopulate the assignment table
        self._assign_table.blockSignals(True)
        self._assign_table.setRowCount(0)
        for i, ds in enumerate(self._main_window._datasets):
            row = self._assign_table.rowCount()
            self._assign_table.insertRow(row)
            name_item = QTableWidgetItem(ds.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self._assign_table.setItem(row, 0, name_item)
            self._assign_table.setItem(row, 1, QTableWidgetItem(self._group_by_idx[i]))
        self._assign_table.blockSignals(False)
        self._refresh_saved_groups_combo()
        self._refresh_compute_enabled()
        self._refresh_save_as_enabled()

    def _load_saved_groups(self) -> dict[str, dict]:
        """Project-aware reuse of gui.persistence.load_groups."""
        from rrational.gui.persistence import load_groups as _lg

        proj = getattr(self._main_window, "_project", None)
        project_path = proj.project_path if proj is not None else None
        return _lg(project_path=project_path) or {}

    def refresh_saved_groups(self) -> None:
        """Called by MainWindow when Setup's GroupsPane has persisted edits."""
        self._refresh_saved_groups_combo()

    def _refresh_saved_groups_combo(self) -> None:
        prev = self._saved_groups_combo.currentText()
        saved = self._load_saved_groups()
        self._saved_groups_combo.blockSignals(True)
        self._saved_groups_combo.clear()
        for name, data in saved.items():
            display = (
                f"{name}  ({len(data.get('members') or [])} members)"
                if data.get("members")
                else name
            )
            self._saved_groups_combo.addItem(display, name)
        if prev:
            idx = self._saved_groups_combo.findText(prev)
            if idx >= 0:
                self._saved_groups_combo.setCurrentIndex(idx)
        self._saved_groups_combo.blockSignals(False)
        self._apply_saved_btn.setEnabled(self._saved_groups_combo.count() > 0)

    def _on_apply_saved(self) -> None:
        """Apply the picked saved group's members → assignment table."""
        idx = self._saved_groups_combo.currentIndex()
        if idx < 0:
            return
        group_name = self._saved_groups_combo.itemData(idx)
        saved = self._load_saved_groups()
        members = set(saved.get(group_name, {}).get("members") or [])
        # Assign group_name to every workspace dataset whose name is in
        # the group's member list. Leave others unchanged so the user
        # can chain multiple applies (e.g. apply Control first, then
        # apply Music to fill in the rest).
        self._assign_table.blockSignals(True)
        for i, ds in enumerate(self._main_window._datasets):
            if ds.name in members:
                self._group_by_idx[i] = group_name
                if i < self._assign_table.rowCount():
                    self._assign_table.setItem(i, 1, QTableWidgetItem(group_name))
        self._assign_table.blockSignals(False)
        self._refresh_compute_enabled()
        self._refresh_save_as_enabled()
        self._main_window.statusBar().showMessage(
            f"Applied saved group '{group_name}' to {sum(1 for ds in self._main_window._datasets if ds.name in members)} dataset(s)",
            4000,
        )

    def _refresh_save_as_enabled(self) -> None:
        """Save-as button needs at least 1 non-empty label."""
        has_labels = any(lbl for lbl in self._group_by_idx.values())
        self._save_as_group_btn.setEnabled(has_labels)

    def _on_save_as_group(self) -> None:
        """Persist current ad-hoc assignment as named groups in groups.yml."""
        from qtpy.QtWidgets import QMessageBox

        from rrational.gui.persistence import load_groups, save_groups

        # Build per-label member list from current assignment
        members_by_label: dict[str, list[str]] = {}
        for i, ds in enumerate(self._main_window._datasets):
            lbl = self._group_by_idx.get(i, "")
            if lbl:
                members_by_label.setdefault(lbl, []).append(ds.name)
        if not members_by_label:
            return

        proj = getattr(self._main_window, "_project", None)
        project_path = proj.project_path if proj is not None else None
        existing = load_groups(project_path=project_path) or {}

        # Conflict check
        conflicts = [lbl for lbl in members_by_label if lbl in existing]
        if conflicts and not self._main_window.test_mode:
            reply = QMessageBox.question(
                self,
                "Overwrite existing groups",
                "These groups already exist: "
                + ", ".join(conflicts)
                + "\n\nOverwrite their member lists with the current assignment?",
            )
            if reply != QMessageBox.Yes:
                return

        for lbl, members in members_by_label.items():
            existing[lbl] = {
                "label": (existing.get(lbl, {}) or {}).get("label", lbl),
                "description": (existing.get(lbl, {}) or {}).get("description", ""),
                "members": members,
                "expected_events": (existing.get(lbl, {}) or {}).get(
                    "expected_events", {}
                ),
                "selected_sections": (existing.get(lbl, {}) or {}).get(
                    "selected_sections", []
                ),
            }
        save_groups(existing, project_path=project_path)
        # Refresh the Setup tab's GroupsPane + our own combo
        setup_groups = getattr(self._main_window._setup_tab, "_groups_pane", None)
        if setup_groups is not None and hasattr(setup_groups, "refresh_from_workspace"):
            setup_groups.refresh_from_workspace()
        self._refresh_saved_groups_combo()
        self._main_window.statusBar().showMessage(
            f"Saved {len(members_by_label)} group(s) to groups.yml", 4000
        )

    def _on_assignment_changed(self, item: QTableWidgetItem) -> None:
        # Only react to edits in the "Group" column.
        if item.column() != 1:
            return
        self._group_by_idx[item.row()] = item.text().strip()
        self._refresh_compute_enabled()
        self._refresh_save_as_enabled()

    def _refresh_compute_enabled(self) -> None:
        """Compute is enabled iff ≥2 distinct non-empty group labels exist
        AND the section combo has at least one entry."""
        labels = {lbl for lbl in self._group_by_idx.values() if lbl}
        self._compute_btn.setEnabled(
            len(labels) >= 2 and self._section_combo.count() > 0
        )

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    def _on_compute(self) -> None:
        from rrational.analysis.group_statistics import compare_groups

        sec_name = self._section_combo.currentText()
        metric = self._metric_combo.currentText()
        if not sec_name or not metric:
            return

        # Build {group_label: [metric_value_per_dataset]}
        values_per_group: dict[str, list[float]] = {}
        for i, ds in enumerate(self._main_window._datasets):
            label = self._group_by_idx.get(i, "")
            if not label:
                continue
            rr = _slice_section(ds.data, sec_name)
            if rr is None or len(rr) == 0:
                continue
            metrics = _compute_metrics(rr)
            value = metrics.get(metric)
            if value is None or (isinstance(value, float) and math.isnan(value)):
                continue
            values_per_group.setdefault(label, []).append(float(value))

        # Need ≥2 groups WITH data
        non_empty = {k: v for k, v in values_per_group.items() if v}
        if len(non_empty) < 2:
            self._result_label.setText(
                "<span style='color:#d62728'><b>Need ≥2 groups with at least "
                "1 valid value each.</b></span> Assign labels in the table above."
            )
            self._group_stats_table.setRowCount(0)
            return

        try:
            result = compare_groups(
                non_empty,
                metric=metric,
                section=sec_name,
            )
        except Exception as e:
            self._result_label.setText(
                f"<span style='color:#d62728'>Comparison failed: {e}</span>"
            )
            return

        # Render
        sig_color = "#2ca02c" if result.p_value < 0.05 else "#555"
        effect_str = (
            f" · {result.effect_size_name} = <b>{result.effect_size:.3f}</b>"
            if result.effect_size is not None
            else ""
        )
        self._result_label.setText(
            f"<b>{result.test_name}</b> on <b>{metric}</b> in section "
            f"<b>{sec_name}</b><br>"
            f"statistic = <b>{result.statistic:.3f}</b>, "
            f"<span style='color:{sig_color}'>"
            f"p = <b>{result.p_value:.4f}</b> {result.significance}</span>"
            f"{effect_str}<br>"
            f"<small style='color:#777'>"
            f"{'parametric' if result.is_parametric else 'non-parametric'} test"
            f"{(' · ' + result.note) if result.note else ''}</small>"
        )

        self._group_stats_table.setRowCount(0)
        for group_name in result.groups:
            row = self._group_stats_table.rowCount()
            self._group_stats_table.insertRow(row)
            self._group_stats_table.setItem(row, 0, QTableWidgetItem(group_name))
            self._group_stats_table.setItem(
                row, 1, QTableWidgetItem(str(result.n_per_group[group_name]))
            )
            self._group_stats_table.setItem(
                row,
                2,
                QTableWidgetItem(_format_metric(result.means[group_name])),
            )
            self._group_stats_table.setItem(
                row,
                3,
                QTableWidgetItem(_format_metric(result.sds[group_name])),
            )
            norm_p = result.normality_p.get(group_name)
            self._group_stats_table.setItem(
                row,
                4,
                QTableWidgetItem(_format_metric(norm_p) if norm_p else "—"),
            )

        # Push into the central results store; Results tab picks it up.
        from rrational.inspector.results_store import GroupTestRow

        self._main_window._results_store.add_group_test_row(
            GroupTestRow(
                section=sec_name,
                metric=metric,
                test_name=result.test_name,
                statistic=float(result.statistic),
                p_value=float(result.p_value),
                effect_size_name=result.effect_size_name,
                effect_size=(
                    None if result.effect_size is None else float(result.effect_size)
                ),
                is_parametric=bool(result.is_parametric),
                groups=tuple(result.groups),
                n_per_group=dict(result.n_per_group),
            )
        )
        self._main_window._results_tab.refresh_results()


class _SequenceComparisonPane(QWidget):
    """Repeated-measures analysis across an ordered Sequence of sections.

    Pick a saved Sequence (defined in Setup tab), pick a metric, pick
    parametric/non-parametric — the pane computes the metric per section
    per dataset, then runs Friedman (default) or RM-ANOVA, plus all-pairwise
    post-hoc with Holm correction, plus a line chart of the per-dataset
    trajectories.
    """

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self._main_window = main_window

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        # ---- Inputs --------------------------------------------------
        form_box = QGroupBox("Inputs")
        form = QFormLayout(form_box)
        self._sequence_combo = QComboBox()
        self._sequence_combo.currentIndexChanged.connect(self._on_sequence_changed)
        self._metric_combo = QComboBox()
        for m in _DEFAULT_METRICS:
            self._metric_combo.addItem(m)
        from qtpy.QtWidgets import QCheckBox

        self._prefer_parametric = QCheckBox(
            "Prefer parametric (RM-ANOVA) when normality + n >= 10"
        )
        form.addRow("Sequence:", self._sequence_combo)
        form.addRow("Metric:", self._metric_combo)
        form.addRow("", self._prefer_parametric)
        outer.addWidget(form_box)

        # Sequence preview label — shows the chain of section names
        self._sequence_preview = QLabel("<i>No sequence selected.</i>")
        self._sequence_preview.setWordWrap(True)
        self._sequence_preview.setStyleSheet("color: #666; padding: 4px;")
        outer.addWidget(self._sequence_preview)

        button_row = QHBoxLayout()
        self._compute_btn = QPushButton("Run repeated-measures comparison")
        self._compute_btn.clicked.connect(self._on_compute)
        self._compute_btn.setEnabled(False)
        button_row.addWidget(self._compute_btn)
        button_row.addStretch()
        outer.addLayout(button_row)

        # ---- Result label (omnibus test summary) ---------------------
        self._result_label = QLabel(
            "<i>Define a sequence in the Setup tab, then pick it above + click Compute.</i>"
        )
        self._result_label.setWordWrap(True)
        self._result_label.setStyleSheet("padding: 8px;")
        outer.addWidget(self._result_label)

        # ---- Per-section descriptives --------------------------------
        outer.addWidget(QLabel("<b>Per-section descriptives</b>"))
        self._section_stats_table = QTableWidget(0, 5, self)
        self._section_stats_table.setHorizontalHeaderLabels(
            ["Section", "n", "Mean", "SD", "Normality (p)"]
        )
        self._section_stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._section_stats_table.setAlternatingRowColors(True)
        self._section_stats_table.verticalHeader().setVisible(False)
        self._section_stats_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self._section_stats_table.setMaximumHeight(180)
        outer.addWidget(self._section_stats_table)

        # ---- Per-dataset line chart ----------------------------------
        outer.addWidget(QLabel("<b>Per-dataset trajectories</b>"))
        import pyqtgraph as pg

        self._plot_widget = pg.PlotWidget(background="w")
        self._plot_widget.setMinimumHeight(220)
        self._plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self._plot_widget.getAxis("left").setPen("k")
        self._plot_widget.getAxis("bottom").setPen("k")
        outer.addWidget(self._plot_widget, 1)

        # ---- Post-hoc table ------------------------------------------
        outer.addWidget(QLabel("<b>Post-hoc pairwise comparisons (Holm-corrected)</b>"))
        self._post_hoc_table = QTableWidget(0, 6, self)
        self._post_hoc_table.setHorizontalHeaderLabels(
            ["Section A", "Section B", "Test", "Statistic", "p (raw)", "p (Holm)"]
        )
        self._post_hoc_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._post_hoc_table.setAlternatingRowColors(True)
        self._post_hoc_table.verticalHeader().setVisible(False)
        self._post_hoc_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        outer.addWidget(self._post_hoc_table)

        # Initial population
        self.refresh_sequences()

    # ------------------------------------------------------------------
    # Workspace + sequences sync
    # ------------------------------------------------------------------
    def refresh_sequences(self) -> None:
        """Reload the dropdown from disk + setup-tab pane.

        We prefer the live in-memory list from the SetupTab's
        SequencesPane (so unsaved edits would show through too), but
        fall back to loading from disk if the setup tab isn't built yet.
        """
        prev = self._sequence_combo.currentText()
        setup_pane = getattr(self._main_window._setup_tab, "_sequences_pane", None)
        if setup_pane is not None:
            seqs = setup_pane.sequences
        else:
            from rrational.inspector.persistence import load_sequences

            seqs = load_sequences()

        self._sequence_combo.blockSignals(True)
        self._sequence_combo.clear()
        for s in seqs:
            self._sequence_combo.addItem(s.name, s)
        if prev:
            idx = self._sequence_combo.findText(prev)
            if idx >= 0:
                self._sequence_combo.setCurrentIndex(idx)
        self._sequence_combo.blockSignals(False)
        self._on_sequence_changed(self._sequence_combo.currentIndex())

    def refresh_workspace(self) -> None:
        # The compute button depends on having datasets loaded.
        self._refresh_compute_enabled()

    def _on_sequence_changed(self, _idx: int) -> None:
        seq = self._sequence_combo.currentData()
        if seq is None:
            self._sequence_preview.setText("<i>No sequence selected.</i>")
        else:
            self._sequence_preview.setText(
                "<b>Sections:</b> " + " → ".join(seq.sections)
            )
        self._refresh_compute_enabled()

    def _refresh_compute_enabled(self) -> None:
        has_seq = self._sequence_combo.currentData() is not None
        has_data = len(self._main_window._datasets) > 0
        self._compute_btn.setEnabled(has_seq and has_data)

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    def _on_compute(self) -> None:
        from rrational.analysis.sequence_statistics import analyze_sequence
        from rrational.inspector.results_store import SequenceTestRow

        seq = self._sequence_combo.currentData()
        metric = self._metric_combo.currentText()
        if seq is None or not metric:
            return

        # Build {section: [per-subject metric values]} — subject order
        # = dataset order so subject i is dataset i across every section.
        values_per_section: dict[str, list[float]] = {s: [] for s in seq.sections}
        for ds in self._main_window._datasets:
            for s in seq.sections:
                rr = _slice_section(ds.data, s)
                if rr is None or len(rr) == 0:
                    values_per_section[s].append(float("nan"))
                    continue
                metrics = _compute_metrics(rr)
                v = metrics.get(metric)
                values_per_section[s].append(
                    float("nan")
                    if v is None or (isinstance(v, float) and math.isnan(v))
                    else float(v)
                )

        try:
            result = analyze_sequence(
                values_per_section,
                sequence_name=seq.name,
                metric=metric,
                sections=list(seq.sections),
                prefer_parametric=self._prefer_parametric.isChecked(),
            )
        except Exception as e:
            self._result_label.setText(
                f"<span style='color:#d62728'>Analysis failed: {e}</span>"
            )
            return

        self._render_result(result, values_per_section)

        # Push into central results store
        self._main_window._results_store.add_sequence_test_row(
            SequenceTestRow(
                sequence_name=result.sequence_name,
                metric=result.metric,
                sections=tuple(result.sections),
                n_complete_subjects=result.n_complete_subjects,
                test_name=result.test_name,
                statistic=float(result.statistic)
                if not math.isnan(result.statistic)
                else float("nan"),
                p_value=float(result.p_value)
                if not math.isnan(result.p_value)
                else float("nan"),
                effect_size_name=result.effect_size_name,
                effect_size=float(result.effect_size)
                if not math.isnan(result.effect_size)
                else float("nan"),
                is_parametric=bool(result.is_parametric),
            )
        )
        self._main_window._results_tab.refresh_results()

    def _render_result(
        self, result, values_per_section: dict[str, list[float]]
    ) -> None:
        # ----- Omnibus result label -----
        if math.isnan(result.p_value):
            sig_color = "#888"
            p_str = "—"
        else:
            sig_color = "#2ca02c" if result.p_value < 0.05 else "#555"
            p_str = f"{result.p_value:.4f}"

        if math.isnan(result.effect_size):
            effect_str = ""
        else:
            effect_str = (
                f" · {result.effect_size_name} = <b>{result.effect_size:.3f}</b>"
            )

        df_str = ""
        if isinstance(result.df, tuple):
            df_str = f"<small> (df={int(result.df[0])}, {int(result.df[1])})</small>"
        elif result.df:
            df_str = f"<small> (df={int(result.df)})</small>"

        self._result_label.setText(
            f"<b>{result.test_name}</b> on <b>{result.metric}</b> across "
            f"<b>{result.sequence_name}</b> "
            f"({result.n_complete_subjects} complete subjects"
            f"{', ' + str(result.n_excluded_subjects) + ' excluded' if result.n_excluded_subjects else ''})"
            f"<br>statistic = <b>{result.statistic:.3f}</b>{df_str}, "
            f"<span style='color:{sig_color}'>p = <b>{p_str}</b> {result.significance}</span>"
            f"{effect_str}<br>"
            f"<small style='color:#777'>"
            f"{'parametric' if result.is_parametric else 'non-parametric'} test"
            f"{(' · ' + result.note) if result.note else ''}</small>"
        )

        # ----- Per-section descriptives table -----
        self._section_stats_table.setRowCount(0)
        for s in result.sections:
            row = self._section_stats_table.rowCount()
            self._section_stats_table.insertRow(row)
            n = sum(
                1
                for v in values_per_section[s]
                if not (v is None or (isinstance(v, float) and math.isnan(v)))
            )
            self._section_stats_table.setItem(row, 0, QTableWidgetItem(s))
            self._section_stats_table.setItem(row, 1, QTableWidgetItem(str(n)))
            self._section_stats_table.setItem(
                row, 2, QTableWidgetItem(_format_metric(result.means.get(s)))
            )
            self._section_stats_table.setItem(
                row, 3, QTableWidgetItem(_format_metric(result.sds.get(s)))
            )
            norm_p = result.normality_p.get(s)
            self._section_stats_table.setItem(
                row,
                4,
                QTableWidgetItem(_format_metric(norm_p) if norm_p else "—"),
            )

        # ----- Line chart -----
        import pyqtgraph as pg

        self._plot_widget.clear()
        n_subjects = max((len(vals) for vals in values_per_section.values()), default=0)
        # X positions = 1..len(sections); tick labels = section names
        x_positions = list(range(1, len(result.sections) + 1))
        ax = self._plot_widget.getAxis("bottom")
        ax.setTicks([list(zip(x_positions, result.sections))])
        # One curve per dataset (subject). Use a colormap to distinguish.
        colormap = pg.colormap.get("CET-C7")  # smooth perceptual
        for i in range(n_subjects):
            ys = []
            xs = []
            for j, s in enumerate(result.sections):
                vals = values_per_section[s]
                if i < len(vals):
                    v = vals[i]
                    if not (v is None or (isinstance(v, float) and math.isnan(v))):
                        ys.append(v)
                        xs.append(x_positions[j])
            if not ys:
                continue
            color = colormap.map(i / max(1, n_subjects - 1), mode="qcolor")
            name = (
                self._main_window._datasets[i].name
                if i < len(self._main_window._datasets)
                else f"S{i}"
            )
            self._plot_widget.plot(
                xs,
                ys,
                pen=pg.mkPen(color, width=2),
                symbol="o",
                symbolBrush=color,
                symbolSize=7,
                name=name,
            )
        self._plot_widget.setLabel("left", f"{result.metric}")
        self._plot_widget.setLabel("bottom", "Section (in sequence order)")

        # ----- Post-hoc table -----
        self._post_hoc_table.setRowCount(0)
        for pair in result.post_hoc:
            row = self._post_hoc_table.rowCount()
            self._post_hoc_table.insertRow(row)
            self._post_hoc_table.setItem(row, 0, QTableWidgetItem(pair.section_a))
            self._post_hoc_table.setItem(row, 1, QTableWidgetItem(pair.section_b))
            self._post_hoc_table.setItem(row, 2, QTableWidgetItem(pair.test_name))
            self._post_hoc_table.setItem(
                row, 3, QTableWidgetItem(_format_metric(pair.statistic))
            )
            self._post_hoc_table.setItem(
                row, 4, QTableWidgetItem(_format_metric(pair.p_value_raw))
            )
            self._post_hoc_table.setItem(
                row, 5, QTableWidgetItem(_format_metric(pair.p_value_corrected))
            )


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
        self._mode_combo.addItem("Group comparison", "group")
        self._mode_combo.addItem("Sequence Comparison", "sequence")
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._mode_combo)
        mode_row.addStretch()
        outer.addLayout(mode_row)

        self._stack = QStackedWidget(self)
        self._single_pane = _SingleParticipantPane(main_window, self)
        self._repeating_pane = _RepeatingSectionPane(main_window, self)
        self._group_pane = _GroupComparisonPane(main_window, self)
        self._sequence_pane = _SequenceComparisonPane(main_window, self)
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
        self._group_pane.refresh_workspace()
        self._sequence_pane.refresh_workspace()

    def on_active_dataset_changed(self, data: "InspectorData | None") -> None:
        # Single-Participant pane defaults to whatever's currently active;
        # easiest is to re-sync from the workspace each time.
        self._single_pane.refresh_workspace()
        if data is not None:
            idx = self._main_window._active_idx
            if idx is not None:
                self._single_pane._dataset_combo.setCurrentIndex(idx)
