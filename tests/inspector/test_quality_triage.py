"""Tests for the QualityTriageDialog (cross-recording quality dashboard).

Covers:
- The summary counts each grade correctly
- Rows are populated with the right text + numeric values
- Sorting is numeric on Beats / Artifacts / Rate columns
- "Open selected" emits open_recording with the highlighted row's name
- A "Saved" tooltip surfaces the .rrational v2 path when present
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


from rrational.inspector.quality_triage_dialog import (
    BatchResult,
    QualityTriageDialog,
)


def _sample_rows() -> list[BatchResult]:
    return [
        BatchResult("a.csv", 1000, 10, 0.01, "A"),
        BatchResult("b.csv", 1000, 50, 0.05, "B", saved_path="/tmp/b.rrational"),
        BatchResult("c.csv", 1000, 60, 0.06, "C"),
        BatchResult("d.csv", 1000, 200, 0.20, "D"),
    ]


def test_dialog_summary_counts_grades_correctly(qtbot):
    rows = [
        BatchResult("a.csv", 1000, 10, 0.01, "A"),
        BatchResult("b.csv", 1000, 50, 0.05, "B"),
        BatchResult("c.csv", 1000, 60, 0.06, "C"),
    ]
    dlg = QualityTriageDialog(rows)
    qtbot.addWidget(dlg)
    txt = dlg._summary_text(rows)
    assert "A: 1" in txt
    assert "B: 1" in txt
    assert "C: 1" in txt
    assert "3 recordings" in txt.replace("<b>", "").replace("</b>", "")


def test_dialog_summary_includes_unknown_when_present(qtbot):
    rows = [
        BatchResult("ok.csv", 200, 1, 0.005, "A"),
        BatchResult("bad.csv", 0, 0, 0.0, "?"),
    ]
    dlg = QualityTriageDialog(rows)
    qtbot.addWidget(dlg)
    txt = dlg._summary_text(rows)
    assert "unknown: 1" in txt


def test_dialog_table_has_one_row_per_result(qtbot):
    rows = _sample_rows()
    dlg = QualityTriageDialog(rows)
    qtbot.addWidget(dlg)
    assert dlg._table.rowCount() == len(rows)
    assert dlg._table.columnCount() == 6


def test_dialog_table_populates_text_correctly(qtbot):
    rows = [BatchResult("a.csv", 1000, 10, 0.01, "A")]
    dlg = QualityTriageDialog(rows)
    qtbot.addWidget(dlg)
    # After construction the table is sorted; find the single row.
    assert dlg._table.item(0, 0).text() == "a.csv"
    assert dlg._table.item(0, 1).text() == "1000"
    assert dlg._table.item(0, 2).text() == "10"
    assert dlg._table.item(0, 3).text() == "1.00"  # 0.01 * 100 = 1.00%
    assert dlg._table.item(0, 4).text() == "A"
    assert dlg._table.item(0, 5).text() == "no"


def test_dialog_saved_path_tooltip_set_when_export_succeeded(qtbot):
    rows = [
        BatchResult("x.csv", 100, 0, 0.0, "A", saved_path="/somewhere/x.rrational"),
    ]
    dlg = QualityTriageDialog(rows)
    qtbot.addWidget(dlg)
    saved_item = dlg._table.item(0, 5)
    assert saved_item.text() == "yes"
    assert saved_item.toolTip() == "/somewhere/x.rrational"


def test_dialog_open_recording_emits_selected_row_name(qtbot):
    rows = _sample_rows()
    dlg = QualityTriageDialog(rows)
    qtbot.addWidget(dlg)
    # Find the row holding "c.csv" regardless of current sort order.
    target_row = None
    for i in range(dlg._table.rowCount()):
        if dlg._table.item(i, 0).text() == "c.csv":
            target_row = i
            break
    assert target_row is not None
    dlg._table.setCurrentCell(target_row, 0)
    emitted: list[str] = []
    dlg.open_recording.connect(emitted.append)
    dlg._on_open_selected()
    assert emitted == ["c.csv"]


def test_dialog_numeric_sort_orders_rate_column_by_value(qtbot):
    """Sorting by rate must use numeric order, not lexicographic string."""
    from qtpy.QtCore import Qt

    rows = [
        BatchResult("ten.csv", 100, 10, 0.10, "C"),
        BatchResult("two.csv", 100, 2, 0.02, "B"),
        BatchResult("nine.csv", 100, 9, 0.09, "C"),
    ]
    dlg = QualityTriageDialog(rows)
    qtbot.addWidget(dlg)
    # Force ascending sort on the Rate column (index 3).
    dlg._table.sortItems(3, Qt.AscendingOrder)
    rate_strings = [dlg._table.item(i, 3).text() for i in range(3)]
    # 2.00 < 9.00 < 10.00 — lexicographic would put "10.00" before "2.00".
    assert rate_strings == ["2.00", "9.00", "10.00"]


def test_dialog_grade_letter_helper_matches_thresholds():
    """The triage dialog's letters mirror the Quigley letter helper."""
    from rrational.inspector.preprocessing import _grade_letter_for_rate

    assert _grade_letter_for_rate(0.01) == "A"
    assert _grade_letter_for_rate(0.03) == "B"
    assert _grade_letter_for_rate(0.07) == "C"
    assert _grade_letter_for_rate(0.15) == "D"
