"""Results tab — accumulated HRV results + CSV export (Phase 4e).

Two sub-tabs:

- **HRV metrics**: one row per (dataset, section) compute from
  Single Participant + Repeating Section modes. Columns: timestamp,
  mode, dataset, section, beats, and the seven default metrics.
- **Group tests**: one row per Group Comparison Compute call.
  Columns: section, metric, test, statistic, p, effect size, n per
  group.

Both tables are sortable (click column header). Each tab has an
**Export CSV…** button that writes whatever's currently visible in
its table — preserves sort order, never includes empty placeholders.

Reads from the :class:`ResultsStore` held by MainWindow; nothing is
computed here, it's a pure view layer.
"""

from __future__ import annotations

import csv
import math
from datetime import datetime
from pathlib import Path

from qtpy.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from rrational.inspector import settings
from rrational.inspector.results_store import GroupTestRow, SequenceTestRow
from rrational.inspector.tabs.base import InspectorTab

_DEFAULT_METRICS = ["RMSSD", "SDNN", "MeanHR", "LF", "HF", "LF_HF", "pNN50"]


def _fmt(value) -> str:
    """Format a numeric value for table display."""
    if value is None:
        return "—"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(f):
        return "—"
    if abs(f) >= 1000 or (f != 0 and abs(f) < 0.01):
        return f"{f:.2e}"
    return f"{f:.3f}"


class _NumericItem(QTableWidgetItem):
    """QTableWidgetItem that sorts by the underlying float, not its display text.

    ``display`` overrides the formatted text — useful for integer counts
    that should sort numerically but render without decimals.
    """

    def __init__(self, value: float | None, display: str | None = None) -> None:
        super().__init__(display if display is not None else _fmt(value))
        # Store the raw value so __lt__ can compare numerically.
        # NaN/None sort to the bottom by mapping to +inf.
        if value is None or (isinstance(value, float) and math.isnan(value)):
            self._sort_key = float("inf")
        else:
            self._sort_key = float(value)

    def __lt__(self, other) -> bool:
        if isinstance(other, _NumericItem):
            return self._sort_key < other._sort_key
        return super().__lt__(other)


class _MetricsPane(QWidget):
    """Table of every (dataset, section) HRV-compute row."""

    HEADERS = ["Mode", "Dataset", "Section", "Beats", *_DEFAULT_METRICS]

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self._main_window = main_window
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        bar = QHBoxLayout()
        self._info = QLabel("0 row(s)")
        self._info.setStyleSheet("color: #666;")
        bar.addWidget(self._info)
        bar.addStretch()
        self._export_btn = QPushButton("Export CSV…")
        self._export_btn.clicked.connect(self._on_export)
        self._export_btn.setEnabled(False)
        bar.addWidget(self._export_btn)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._on_clear)
        self._clear_btn.setEnabled(False)
        bar.addWidget(self._clear_btn)
        outer.addLayout(bar)

        self._table = QTableWidget(0, len(self.HEADERS), self)
        self._table.setHorizontalHeaderLabels(self.HEADERS)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self._table.setSortingEnabled(True)
        outer.addWidget(self._table)

    def refresh(self) -> None:
        rows = self._main_window._results_store.metric_rows
        # Disable sorting during rebuild — otherwise inserting rows
        # one-by-one re-sorts after every cell write and the result is
        # garbage.
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for r in rows:
            i = self._table.rowCount()
            self._table.insertRow(i)
            self._table.setItem(i, 0, QTableWidgetItem(r.mode))
            self._table.setItem(i, 1, QTableWidgetItem(r.dataset))
            self._table.setItem(i, 2, QTableWidgetItem(r.section))
            self._table.setItem(i, 3, _NumericItem(r.n_beats, display=str(r.n_beats)))
            for col, m in enumerate(_DEFAULT_METRICS, start=4):
                self._table.setItem(i, col, _NumericItem(r.metrics.get(m)))
        self._table.setSortingEnabled(True)
        self._info.setText(f"{len(rows)} row(s)")
        has_rows = len(rows) > 0
        self._export_btn.setEnabled(has_rows)
        self._clear_btn.setEnabled(has_rows)

    def _on_export(self) -> None:
        rows = self._main_window._results_store.metric_rows
        if not rows:
            return
        path = _ask_csv_path(self, "hrv_metrics")
        if path is None:
            return
        try:
            with path.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(self.HEADERS)
                for r in rows:
                    w.writerow(
                        [
                            r.mode,
                            r.dataset,
                            r.section,
                            r.n_beats,
                            *[r.metrics.get(m, "") for m in _DEFAULT_METRICS],
                        ]
                    )
        except OSError as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        self._main_window.statusBar().showMessage(
            f"Exported {len(rows)} row(s) to {path}", 4000
        )

    def _on_clear(self) -> None:
        self._main_window._results_store.metric_rows.clear()
        self.refresh()


class _GroupTestsPane(QWidget):
    """Table of every Group-Comparison result row."""

    HEADERS = [
        "Section",
        "Metric",
        "Test",
        "Statistic",
        "p",
        "Effect size",
        "Effect value",
        "Groups",
        "n per group",
    ]

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self._main_window = main_window
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        bar = QHBoxLayout()
        self._info = QLabel("0 row(s)")
        self._info.setStyleSheet("color: #666;")
        bar.addWidget(self._info)
        bar.addStretch()
        self._export_btn = QPushButton("Export CSV…")
        self._export_btn.clicked.connect(self._on_export)
        self._export_btn.setEnabled(False)
        bar.addWidget(self._export_btn)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._on_clear)
        self._clear_btn.setEnabled(False)
        bar.addWidget(self._clear_btn)
        outer.addLayout(bar)

        self._table = QTableWidget(0, len(self.HEADERS), self)
        self._table.setHorizontalHeaderLabels(self.HEADERS)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self._table.setSortingEnabled(True)
        outer.addWidget(self._table)

    @staticmethod
    def _groups_str(row: GroupTestRow) -> str:
        return " vs ".join(row.groups)

    @staticmethod
    def _n_str(row: GroupTestRow) -> str:
        return ", ".join(f"{g}={row.n_per_group[g]}" for g in row.groups)

    def refresh(self) -> None:
        rows = self._main_window._results_store.group_test_rows
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for r in rows:
            i = self._table.rowCount()
            self._table.insertRow(i)
            self._table.setItem(i, 0, QTableWidgetItem(r.section))
            self._table.setItem(i, 1, QTableWidgetItem(r.metric))
            self._table.setItem(i, 2, QTableWidgetItem(r.test_name))
            self._table.setItem(i, 3, _NumericItem(r.statistic))
            self._table.setItem(i, 4, _NumericItem(r.p_value))
            self._table.setItem(i, 5, QTableWidgetItem(r.effect_size_name or "—"))
            self._table.setItem(i, 6, _NumericItem(r.effect_size))
            self._table.setItem(i, 7, QTableWidgetItem(self._groups_str(r)))
            self._table.setItem(i, 8, QTableWidgetItem(self._n_str(r)))
        self._table.setSortingEnabled(True)
        self._info.setText(f"{len(rows)} row(s)")
        has_rows = len(rows) > 0
        self._export_btn.setEnabled(has_rows)
        self._clear_btn.setEnabled(has_rows)

    def _on_export(self) -> None:
        rows = self._main_window._results_store.group_test_rows
        if not rows:
            return
        path = _ask_csv_path(self, "group_tests")
        if path is None:
            return
        try:
            with path.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(self.HEADERS)
                for r in rows:
                    w.writerow(
                        [
                            r.section,
                            r.metric,
                            r.test_name,
                            r.statistic,
                            r.p_value,
                            r.effect_size_name or "",
                            "" if r.effect_size is None else r.effect_size,
                            self._groups_str(r),
                            self._n_str(r),
                        ]
                    )
        except OSError as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        self._main_window.statusBar().showMessage(
            f"Exported {len(rows)} row(s) to {path}", 4000
        )

    def _on_clear(self) -> None:
        self._main_window._results_store.group_test_rows.clear()
        self.refresh()


class _SequenceTestsPane(QWidget):
    """Table of every Sequence Comparison result row."""

    HEADERS = [
        "Sequence",
        "Metric",
        "Test",
        "Statistic",
        "p",
        "Effect size",
        "Effect value",
        "n subjects",
        "Sections",
    ]

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self._main_window = main_window
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        bar = QHBoxLayout()
        self._info = QLabel("0 row(s)")
        self._info.setStyleSheet("color: #666;")
        bar.addWidget(self._info)
        bar.addStretch()
        self._export_btn = QPushButton("Export CSV…")
        self._export_btn.clicked.connect(self._on_export)
        self._export_btn.setEnabled(False)
        bar.addWidget(self._export_btn)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._on_clear)
        self._clear_btn.setEnabled(False)
        bar.addWidget(self._clear_btn)
        outer.addLayout(bar)

        self._table = QTableWidget(0, len(self.HEADERS), self)
        self._table.setHorizontalHeaderLabels(self.HEADERS)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self._table.setSortingEnabled(True)
        outer.addWidget(self._table)

    @staticmethod
    def _sections_str(row: SequenceTestRow) -> str:
        return " → ".join(row.sections)

    def refresh(self) -> None:
        rows = self._main_window._results_store.sequence_test_rows
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for r in rows:
            i = self._table.rowCount()
            self._table.insertRow(i)
            self._table.setItem(i, 0, QTableWidgetItem(r.sequence_name))
            self._table.setItem(i, 1, QTableWidgetItem(r.metric))
            self._table.setItem(i, 2, QTableWidgetItem(r.test_name))
            self._table.setItem(i, 3, _NumericItem(r.statistic))
            self._table.setItem(i, 4, _NumericItem(r.p_value))
            self._table.setItem(i, 5, QTableWidgetItem(r.effect_size_name or "—"))
            self._table.setItem(i, 6, _NumericItem(r.effect_size))
            self._table.setItem(
                i,
                7,
                _NumericItem(r.n_complete_subjects, display=str(r.n_complete_subjects)),
            )
            self._table.setItem(i, 8, QTableWidgetItem(self._sections_str(r)))
        self._table.setSortingEnabled(True)
        self._info.setText(f"{len(rows)} row(s)")
        has_rows = len(rows) > 0
        self._export_btn.setEnabled(has_rows)
        self._clear_btn.setEnabled(has_rows)

    def _on_export(self) -> None:
        rows = self._main_window._results_store.sequence_test_rows
        if not rows:
            return
        path = _ask_csv_path(self, "sequence_tests")
        if path is None:
            return
        try:
            with path.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(self.HEADERS)
                for r in rows:
                    w.writerow(
                        [
                            r.sequence_name,
                            r.metric,
                            r.test_name,
                            r.statistic,
                            r.p_value,
                            r.effect_size_name or "",
                            r.effect_size,
                            r.n_complete_subjects,
                            self._sections_str(r),
                        ]
                    )
        except OSError as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        self._main_window.statusBar().showMessage(
            f"Exported {len(rows)} row(s) to {path}", 4000
        )

    def _on_clear(self) -> None:
        self._main_window._results_store.sequence_test_rows.clear()
        self.refresh()


def _ask_csv_path(parent, default_stem: str) -> Path | None:
    """Open Save-As dialog; return chosen path or None if cancelled."""
    last_dir = settings.read_setting("last_dir") or str(Path.cwd())
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suggested = str(Path(last_dir) / f"{default_stem}_{stamp}.csv")
    path_str, _ = QFileDialog.getSaveFileName(
        parent, "Export to CSV", suggested, "CSV files (*.csv)"
    )
    if not path_str:
        return None
    return Path(path_str)


class ResultsTab(InspectorTab):
    """Results tab — sortable tables of accumulated HRV computations."""

    TAB_LABEL = "Results"

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(main_window, parent)

        self._subtabs = QTabWidget(self)
        self._subtabs.setDocumentMode(True)

        self._metrics_pane = _MetricsPane(main_window, self)
        self._group_tests_pane = _GroupTestsPane(main_window, self)
        self._sequence_tests_pane = _SequenceTestsPane(main_window, self)

        self._subtabs.addTab(self._metrics_pane, "HRV metrics")
        self._subtabs.addTab(self._group_tests_pane, "Group tests")
        self._subtabs.addTab(self._sequence_tests_pane, "Sequence tests")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._subtabs)

    # ------------------------------------------------------------------
    # Notification hooks — the Results tab refreshes itself whenever a
    # tab notification fires. The Analysis tab calls refresh_results()
    # directly after every Compute, but listening to workspace changes
    # too means closing a dataset that contributed metrics flips the
    # Clear/Export buttons correctly.
    # ------------------------------------------------------------------
    def refresh_results(self) -> None:
        """Re-pull from the store. Called by Analysis after each Compute."""
        self._metrics_pane.refresh()
        self._group_tests_pane.refresh()
        self._sequence_tests_pane.refresh()

    def on_workspace_changed(self) -> None:
        # No-op: results are not tied to the workspace. Keeping a row
        # for a dataset the user later closes is intentional — the
        # researcher already computed and may want to export it.
        pass

    # Inspector contract — accept the active-dataset notification but
    # ignore the payload.
    def on_active_dataset_changed(self, _data) -> None:
        pass

    # Convenience for tests that want to reach the underlying QTableWidget.
    @property
    def _metrics_table(self):
        return self._metrics_pane._table

    @property
    def _group_tests_table(self):
        return self._group_tests_pane._table

    @property
    def _export_metrics_btn(self):
        return self._metrics_pane._export_btn

    @property
    def _export_group_btn(self):
        return self._group_tests_pane._export_btn
