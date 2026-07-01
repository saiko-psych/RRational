"""Results tab — accumulated HRV results + CSV export.

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

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
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


def _empty_state_stack(table: QTableWidget, hint_text: str) -> QStackedWidget:
    """Wrap ``table`` in a [hint, table] stack. Defaults to the hint."""
    label = QLabel(hint_text)
    label.setAlignment(Qt.AlignCenter)
    label.setWordWrap(True)
    label.setTextFormat(Qt.RichText)
    # Round 30 — theme-aware muted text via QSS [muted="true"] rule.
    label.setStyleSheet("QLabel { font-size: 13px; padding: 32px; }")
    label.setProperty("muted", True)
    stack = QStackedWidget()
    stack.addWidget(label)
    stack.addWidget(table)
    stack.setCurrentIndex(0)
    return stack


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

    # Fixed leading columns; the metric columns are appended dynamically
    # in ``refresh()`` from the union of metric keys across all rows, so
    # custom presets (e.g. "Nonlinear only") display their actual
    # computed values instead of empty default columns.
    FIXED_HEADERS = ["Mode", "Dataset", "Section", "Beats"]

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self._main_window = main_window
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        bar = QHBoxLayout()
        self._info = QLabel("0 row(s)")
        self._info.setProperty("muted", True)
        bar.addWidget(self._info)
        bar.addStretch()
        self._export_btn = QPushButton("Export CSV…")
        self._export_btn.setToolTip(
            "Export the current long-format table (one row per dataset/section) to CSV."
        )
        self._export_btn.clicked.connect(self._on_export)
        self._export_btn.setEnabled(False)
        bar.addWidget(self._export_btn)
        # Wide-format export (one row per participant, columns pivoted
        # by section_metric).
        self._export_wide_btn = QPushButton("Export wide format…")
        self._export_wide_btn.setToolTip(
            "Export the same metrics in wide format (one row per participant, "
            "columns named '<section>_<metric>'). Mirrors the Streamlit Group "
            "Analysis download."
        )
        self._export_wide_btn.clicked.connect(self._on_export_wide)
        self._export_wide_btn.setEnabled(False)
        bar.addWidget(self._export_wide_btn)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setToolTip("Remove every row from this table.")
        self._clear_btn.clicked.connect(self._on_clear)
        self._clear_btn.setEnabled(False)
        bar.addWidget(self._clear_btn)
        outer.addLayout(bar)

        # Initial column set: fixed leading columns + default metrics so
        # the empty table has a sensible width. refresh() rebuilds the
        # metric columns from each compute's actual key set.
        self._metric_cols: list[str] = list(_DEFAULT_METRICS)
        headers = [*self.FIXED_HEADERS, *self._metric_cols]
        self._table = QTableWidget(0, len(headers), self)
        self._table.setHorizontalHeaderLabels(headers)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self._table.setSortingEnabled(True)
        self._stack = _empty_state_stack(
            self._table,
            "Compute results in the <b>Analysis</b> tab to populate this view.",
        )
        outer.addWidget(self._stack)

    def refresh(self) -> None:
        rows = self._main_window._results_store.metric_rows
        # Disable sorting during rebuild — otherwise inserting rows
        # one-by-one re-sorts after every cell write and the result is
        # garbage.
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)

        # Rebuild metric columns from the union of keys across all rows,
        # preserving the default order for known metrics and appending
        # unknown ones at the end.
        seen: list[str] = []
        seen_set: set[str] = set()
        for r in rows:
            for m in r.metrics.keys():
                if m not in seen_set:
                    seen.append(m)
                    seen_set.add(m)
        default_order = [m for m in _DEFAULT_METRICS if m in seen_set]
        extras = [m for m in seen if m not in default_order]
        self._metric_cols = default_order + extras if seen else list(_DEFAULT_METRICS)
        headers = [*self.FIXED_HEADERS, *self._metric_cols]
        self._table.setColumnCount(len(headers))
        self._table.setHorizontalHeaderLabels(headers)

        for r in rows:
            i = self._table.rowCount()
            self._table.insertRow(i)
            self._table.setItem(i, 0, QTableWidgetItem(r.mode))
            self._table.setItem(i, 1, QTableWidgetItem(r.dataset))
            self._table.setItem(i, 2, QTableWidgetItem(r.section))
            self._table.setItem(i, 3, _NumericItem(r.n_beats, display=str(r.n_beats)))
            for col, m in enumerate(self._metric_cols, start=len(self.FIXED_HEADERS)):
                self._table.setItem(i, col, _NumericItem(r.metrics.get(m)))
        self._table.setSortingEnabled(True)
        self._info.setText(f"{len(rows)} row(s)")
        has_rows = len(rows) > 0
        self._export_btn.setEnabled(has_rows)
        self._export_wide_btn.setEnabled(has_rows)
        self._clear_btn.setEnabled(has_rows)
        self._stack.setCurrentIndex(1 if has_rows else 0)

    # Wide-format export. Public helper so tests can drive it without
    # dialog mocking; ``_on_export_wide`` wraps it with a file-picker.
    def build_wide_rows(self) -> tuple[list[str], list[list]]:
        """Return ``(headers, rows)`` for the wide CSV.

        One row per (mode, dataset) pair. Columns are ordered as
        participant_id, mode, then ``<section>_<metric>`` for every
        observed (section, metric) combination. Mirrors
        :func:`rrational.analysis.hrv_compute.results_to_wide_df` but
        sources data from the inspector's own ``ResultsStore``.
        """
        rows = self._main_window._results_store.metric_rows
        # Track keys in insertion order so the CSV columns are stable.
        section_metrics: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        per_row: dict[tuple[str, str], dict[tuple[str, str], object]] = {}
        for r in rows:
            key = (r.mode, r.dataset)
            row_dict = per_row.setdefault(key, {})
            section = (r.section or "").replace(" ", "_").lower()
            for metric, value in r.metrics.items():
                col_key = (section, metric.lower())
                if col_key not in seen:
                    seen.add(col_key)
                    section_metrics.append(col_key)
                row_dict[col_key] = value
            # Always include n_beats per section so users can re-derive
            # quality on the consumer side.
            beats_key = (section, "n_beats")
            if beats_key not in seen:
                seen.add(beats_key)
                section_metrics.append(beats_key)
            row_dict[beats_key] = r.n_beats
        headers = ["participant_id", "mode"] + [
            f"{sec}_{met}" for sec, met in section_metrics
        ]
        out_rows: list[list] = []
        for (mode, dataset), payload in per_row.items():
            row = [dataset, mode]
            for key in section_metrics:
                value = payload.get(key, "")
                row.append("" if value is None else value)
            out_rows.append(row)
        return headers, out_rows

    def _on_export_wide(self) -> None:
        if not self._main_window._results_store.metric_rows:
            return
        path = _ask_csv_path(self, "hrv_wide")
        if path is None:
            return
        headers, rows = self.build_wide_rows()
        try:
            with path.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(headers)
                for row in rows:
                    w.writerow(row)
        except OSError as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        self._main_window.statusBar().showMessage(
            f"Exported {len(rows)} wide-format row(s) to {path}", 4000
        )

    def _on_export(self) -> None:
        rows = self._main_window._results_store.metric_rows
        if not rows:
            return
        path = _ask_csv_path(self, "hrv_metrics")
        if path is None:
            return
        # Use whatever metric columns the visible table currently shows
        # so the CSV layout matches what the user is looking at.
        metric_cols = self._metric_cols
        try:
            with path.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow([*self.FIXED_HEADERS, *metric_cols])
                for r in rows:
                    w.writerow(
                        [
                            r.mode,
                            r.dataset,
                            r.section,
                            r.n_beats,
                            *[r.metrics.get(m, "") for m in metric_cols],
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
        self._info.setProperty("muted", True)
        bar.addWidget(self._info)
        bar.addStretch()
        self._export_btn = QPushButton("Export CSV…")
        self._export_btn.setToolTip("Save the current table as a CSV file.")
        self._export_btn.clicked.connect(self._on_export)
        self._export_btn.setEnabled(False)
        bar.addWidget(self._export_btn)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setToolTip("Remove every row from this table.")
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
        self._stack = _empty_state_stack(
            self._table,
            "Run <b>Group comparison</b> in the Analysis tab to populate this view.",
        )
        outer.addWidget(self._stack)

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
        self._stack.setCurrentIndex(1 if has_rows else 0)

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
        self._info.setProperty("muted", True)
        bar.addWidget(self._info)
        bar.addStretch()
        self._export_btn = QPushButton("Export CSV…")
        self._export_btn.setToolTip("Save the current table as a CSV file.")
        self._export_btn.clicked.connect(self._on_export)
        self._export_btn.setEnabled(False)
        bar.addWidget(self._export_btn)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setToolTip("Remove every row from this table.")
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
        self._stack = _empty_state_stack(
            self._table,
            "Run <b>Sequence comparison</b> in the Analysis tab to populate this view.",
        )
        outer.addWidget(self._stack)

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
        self._stack.setCurrentIndex(1 if has_rows else 0)

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
        from rrational.inspector.help_widgets import HelpExpander

        super().__init__(main_window, parent)

        self._help_expander = HelpExpander(
            "How to interpret these results",
            (
                "<p>The <b>HRV metrics</b> sub-tab shows every metric "
                "computation as one row. Click any column header to sort. "
                "Export the table as CSV with the button below.</p>"
                "<p>The <b>Group tests</b> and <b>Sequence tests</b> sub-tabs "
                "list Friedman / RM-ANOVA + Holm-corrected post-hoc results "
                "from the Analysis tab's Group / Sequence modes.</p>"
                "<p><b>Quality reminders</b> (Quigley 2024):</p>"
                "<ul>"
                "<li>Time-domain metrics tolerate &lt;36% artifacts.</li>"
                "<li>Frequency-domain metrics need &lt;2% artifacts.</li>"
                "<li>Always report artifact rate in publications.</li>"
                "</ul>"
                "<p>For a full publication-ready bundle use "
                "<i>File &rarr; Export report</i> (HTML or Markdown).</p>"
            ),
        )

        self._subtabs = QTabWidget(self)
        self._subtabs.setDocumentMode(True)

        self._metrics_pane = _MetricsPane(main_window, self)
        self._group_tests_pane = _GroupTestsPane(main_window, self)
        self._sequence_tests_pane = _SequenceTestsPane(main_window, self)

        self._subtabs.addTab(self._metrics_pane, "HRV metrics")
        self._subtabs.addTab(self._group_tests_pane, "Group tests")
        self._subtabs.addTab(self._sequence_tests_pane, "Sequence tests")

        # ---- Cache toolbar (Save / Reload / Clear) ----------------------
        cache_bar = QHBoxLayout()
        cache_label = QLabel("<b>Cache:</b>")
        # Round 30 — muted secondary text + hint-level tertiary text via
        # theme properties; previous #555/#888 were near-invisible in dark.
        cache_label.setStyleSheet("padding-left: 6px;")
        cache_label.setProperty("muted", True)
        self._cache_status = QLabel("autosaves after every compute")
        self._cache_status.setProperty("hint", True)
        self._save_now_btn = QPushButton("Save now")
        self._save_now_btn.setToolTip(
            "Manually write inspector_results.yml. Autosave already runs "
            "after every Compute — use this only if you want a forced flush."
        )
        self._save_now_btn.clicked.connect(self._on_save_now)
        self._reload_btn = QPushButton("Reload from disk")
        self._reload_btn.setToolTip(
            "Discard the in-memory store and re-read inspector_results.yml. "
            "Useful after editing the file externally or switching projects."
        )
        self._reload_btn.clicked.connect(self._on_reload_from_disk)
        self._clear_cache_btn = QPushButton("Clear cache")
        self._clear_cache_btn.setToolTip(
            "Wipe both the in-memory store AND the on-disk cache file."
        )
        self._clear_cache_btn.clicked.connect(self._on_clear_cache)
        cache_bar.addWidget(cache_label)
        cache_bar.addWidget(self._cache_status, 1)
        cache_bar.addWidget(self._save_now_btn)
        cache_bar.addWidget(self._reload_btn)
        cache_bar.addWidget(self._clear_cache_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._help_expander)
        layout.addWidget(self._subtabs)
        layout.addLayout(cache_bar)

    # ------------------------------------------------------------------
    # Notification hooks — the Results tab refreshes itself whenever a
    # tab notification fires. The Analysis tab calls refresh_results()
    # directly after every Compute, but listening to workspace changes
    # too means closing a dataset that contributed metrics flips the
    # Clear/Export buttons correctly.
    # ------------------------------------------------------------------
    def refresh_results(self) -> None:
        """Re-pull from the store. Called by Analysis after each Compute.

        Also triggers an autosave so the cache stays current without
        per-call-site sprinkling.
        """
        self._metrics_pane.refresh()
        self._group_tests_pane.refresh()
        self._sequence_tests_pane.refresh()
        autosave = getattr(self._main_window, "autosave_results", None)
        if callable(autosave):
            autosave()
        self._refresh_cache_status()

    # ------------------------------------------------------------------
    # Manual cache controls
    # ------------------------------------------------------------------
    def _refresh_cache_status(self) -> None:
        from rrational.inspector.results_persistence import _resolve_path

        proj_path = (
            self._main_window._project.project_path
            if getattr(self._main_window, "_project", None) is not None
            else None
        )
        target = _resolve_path(proj_path)
        if target.exists():
            self._cache_status.setText(f"cache: <code>{target}</code>")
        else:
            self._cache_status.setText("no cache file yet")

    def _on_save_now(self) -> None:
        save = getattr(self._main_window, "save_results_cache", None)
        if callable(save):
            save()
            self._main_window.statusBar().showMessage("Results cache written.", 3000)
        self._refresh_cache_status()

    def _on_reload_from_disk(self) -> None:
        loader = getattr(self._main_window, "_load_results_cache", None)
        if callable(loader):
            loader()
            self._main_window.statusBar().showMessage(
                "Results reloaded from disk.", 3000
            )

    def _on_clear_cache(self) -> None:
        clear = getattr(self._main_window, "clear_results_cache", None)
        if callable(clear):
            removed = clear()
            self._main_window.statusBar().showMessage(
                "Cache cleared" + (" (file deleted)" if removed else ""),
                3000,
            )
        self._refresh_cache_status()

    def tab_label_state(self) -> str:
        """Round 16 — unified ``(N)`` format; sums the three result row
        types into one integer so every top-level tab speaks the same
        counter dialect."""
        store = self._main_window._results_store
        n = (
            len(store.metric_rows)
            + len(store.group_test_rows)
            + len(store.sequence_test_rows)
        )
        return f"({n})" if n else ""

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

    @property
    def _export_metrics_wide_btn(self):
        return self._metrics_pane._export_wide_btn
