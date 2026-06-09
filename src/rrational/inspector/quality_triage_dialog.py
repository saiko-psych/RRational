"""Cross-recording quality dashboard — MNELAB 'Drop bad epochs' equivalent.

Single view over every recording in the workspace, with per-recording
artifact rate + Quigley-2024 letter grade (A/B/C/D). Sortable by any
column; clicking a row activates the matching dataset in the main window.

Used by both :meth:`MainWindow._on_batch_preprocess_clicked` (popped
automatically after a batch detect+save run) and the standalone
``Tools → Quality triage…`` entry (user can revisit at any time without
re-running detection).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QBrush, QColor
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


@dataclass
class BatchResult:
    """One row of the quality-triage table.

    ``grade`` is the A/B/C/D letter from
    :func:`rrational.inspector.preprocessing._grade_letter_for_rate`
    (``"?"`` when detection failed or the recording is too short).
    ``saved_path`` is the .rrational v2 destination if the batch run
    also exported the dataset, otherwise None.
    """

    name: str
    n_beats: int
    n_artifacts: int
    artifact_rate: float  # 0.0 - 1.0
    grade: str  # A / B / C / D / ?
    saved_path: str | None = None


# Numeric-aware QTableWidgetItem so sorting by Beats / Artifacts / Rate
# orders by value, not by lexicographic string. Without this "100" sorts
# before "9" in the default text comparison.
class _NumericItem(QTableWidgetItem):
    def __init__(self, display: str, sort_value: float) -> None:
        super().__init__(display)
        self._sort_value = float(sort_value)
        # Right-align numbers — easier to scan than left-aligned.
        self.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

    def __lt__(self, other) -> bool:  # noqa: D401 — Qt sort hook
        if isinstance(other, _NumericItem):
            return self._sort_value < other._sort_value
        return super().__lt__(other)


# Grade letter colours — bright and saturated so the A/B/C/D badge
# stands out in the Grade column at a glance. We paint the foreground
# of the grade cell (always reliable across Qt back-ends) rather than
# the row background, which gets overridden by the dark theme's QSS
# on some Qt builds and by the offscreen QPA used in the snapshot
# harness. ``?`` rows fall back to the default text colour.
_GRADE_COLOR = {
    "A": "#5ab896",  # jade
    "B": "#e8a13a",  # amber
    "C": "#d4814a",  # warm orange
    "D": "#d97862",  # coral
}


class QualityTriageDialog(QDialog):
    """Dashboard of per-recording artifact-rates + quality grades."""

    open_recording = Signal(str)  # recording name to open

    HEADERS = ["Name", "Beats", "Artifacts", "Rate %", "Grade", "Saved"]

    def __init__(self, results: list[BatchResult], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Quality triage")
        self.resize(640, 420)

        self._results = list(results)

        layout = QVBoxLayout(self)

        self._summary = QLabel(self._summary_text(self._results))
        self._summary.setTextFormat(Qt.RichText)
        layout.addWidget(self._summary)

        self._table = QTableWidget(len(self._results), len(self.HEADERS), self)
        self._table.setHorizontalHeaderLabels(self.HEADERS)
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QTableWidget.SingleSelection)
        # Per-row brushes carry the grade colour — alternating row
        # stripes would desaturate them, so leave them off here.
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)
        # Sorting added AFTER cells are populated — Qt's setItem path is
        # several times faster when the table isn't actively re-sorting
        # after every insert.
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        for i, r in enumerate(self._results):
            self._populate_row(i, r)

        self._table.setSortingEnabled(True)
        # Default sort: worst grade first so the user lands on the
        # recordings that need attention. Column 4 = Grade.
        self._table.sortItems(4, Qt.DescendingOrder)
        # Double-click a row = "open this recording".
        self._table.itemDoubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self._table)

        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        # "Open selected" lives as an ActionRole button so it sits to
        # the left of Close on every platform's native ordering.
        self._open_btn = bb.addButton("Open selected", QDialogButtonBox.ActionRole)
        self._open_btn.setToolTip(
            "Activate the selected recording in the main window and close this dialog."
        )
        self._open_btn.clicked.connect(self._on_open_selected)
        layout.addWidget(bb)

    # ------------------------------------------------------------------
    # Row population helpers
    # ------------------------------------------------------------------
    def _populate_row(self, row: int, r: BatchResult) -> None:
        from qtpy.QtGui import QFont

        name_item = QTableWidgetItem(r.name)
        beats_item = _NumericItem(str(r.n_beats), r.n_beats)
        arts_item = _NumericItem(str(r.n_artifacts), r.n_artifacts)
        rate_item = _NumericItem(f"{r.artifact_rate * 100:.2f}", r.artifact_rate)

        grade_item = QTableWidgetItem(r.grade)
        grade_item.setTextAlignment(Qt.AlignCenter)
        # Paint the grade letter in its colour + bold so the user can
        # scan the column at a glance. The full-row tint we tried first
        # was silently dropped by the offscreen QPA used in the visual
        # snapshot harness.
        colour = _GRADE_COLOR.get(r.grade)
        if colour is not None:
            grade_item.setForeground(QBrush(QColor(colour)))
            bold = QFont()
            bold.setBold(True)
            bold.setPointSize(bold.pointSize() + 1)
            grade_item.setFont(bold)

        saved_item = QTableWidgetItem("yes" if r.saved_path else "no")
        if r.saved_path:
            saved_item.setToolTip(str(r.saved_path))
        saved_item.setTextAlignment(Qt.AlignCenter)

        items = [name_item, beats_item, arts_item, rate_item, grade_item, saved_item]
        for col, item in enumerate(items):
            self._table.setItem(row, col, item)

    # ------------------------------------------------------------------
    # Summary helpers
    # ------------------------------------------------------------------
    def _summary_text(self, results: list[BatchResult]) -> str:
        c = Counter(r.grade for r in results)
        return (
            f"<b>{len(results)} recordings</b> &mdash; "
            f"A: {c.get('A', 0)}, B: {c.get('B', 0)}, "
            f"C: {c.get('C', 0)}, D: {c.get('D', 0)}"
            + (f", unknown: {c.get('?', 0)}" if c.get("?", 0) else "")
        )

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_open_selected(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        name_item = self._table.item(row, 0)
        if name_item is None:
            return
        self.open_recording.emit(name_item.text())
        self.accept()

    def _on_row_double_clicked(self, item: QTableWidgetItem) -> None:
        row = item.row()
        if row < 0:
            return
        name_item = self._table.item(row, 0)
        if name_item is None:
            return
        self.open_recording.emit(name_item.text())
        self.accept()
