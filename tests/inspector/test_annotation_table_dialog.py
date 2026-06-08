"""Tests for the cross-recording AnnotationTableDialog.

Covers:
- Aggregation across multiple datasets from disk
- CSV export contains the expected columns + values
- CSV import creates Annotation objects on disk for matched recordings
- Delete-selected removes rows on disk
- Inline label edit persists
- Round-trip: export then re-import yields the same on-disk content
"""

from __future__ import annotations

import csv

import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def _isolate_settings(qapp, tmp_path):
    from rrational.inspector import annotation_persistence as ap
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    ap.set_annotation_config_dir(tmp_path / "annotations")
    yield
    ap.set_annotation_config_dir(None)


def _make_synthetic(name: str = "S01", n: int = 200):
    from rrational.inspector.data_loader import (
        Dataset,
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    base = 1_700_000_000
    t = base + np.arange(n, dtype=np.float64)
    v = 800 + 50 * np.sin(np.linspace(0, np.pi, n))
    data = InspectorData(
        t=t,
        v=v,
        sections=[
            SectionMeta(
                name="rec", t_start=float(t[0]), t_end=float(t[-1]), beat_count=n
            )
        ],
        events=[EventMeta(label="start", t=float(t[0]))],
    )
    return Dataset(name=f"{name}.csv", data=data)


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


def _persist_annotations(pid: str, items: list[tuple[float, str]]) -> None:
    """Write a YAML annotation file for ``pid`` via the public API."""
    from rrational.inspector.annotation_persistence import save_annotations
    from rrational.inspector.annotations import Annotation

    save_annotations(
        pid,
        [Annotation.create(t=t, text=text) for t, text in items],
    )


def _open_dialog(main_window):
    from rrational.inspector.annotation_table_dialog import AnnotationTableDialog

    dlg = AnnotationTableDialog(main_window, parent=main_window)
    return dlg


# ---------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------
def test_dialog_lists_all_annotations_across_datasets(main_window):
    """Two datasets with three annotations each → six rows."""
    main_window.add_dataset(_make_synthetic("S01"))
    main_window.add_dataset(_make_synthetic("S02"))
    _persist_annotations(
        "S01",
        [(10.0, "a1"), (20.0, "a2"), (30.0, "a3")],
    )
    _persist_annotations(
        "S02",
        [(11.0, "b1"), (22.0, "b2"), (33.0, "b3")],
    )

    dlg = _open_dialog(main_window)

    assert dlg._table.rowCount() == 6
    # Both recordings represented.
    rec_names = {
        dlg._table.item(r, dlg.COL_RECORDING).text()
        for r in range(dlg._table.rowCount())
    }
    assert rec_names == {"S01.csv", "S02.csv"}


def test_dialog_empty_when_no_datasets(main_window):
    dlg = _open_dialog(main_window)
    assert dlg._table.rowCount() == 0


def test_dialog_skips_datasets_with_no_saved_annotations(main_window):
    main_window.add_dataset(_make_synthetic("S01"))
    main_window.add_dataset(_make_synthetic("S02"))
    _persist_annotations("S01", [(5.0, "only-one")])

    dlg = _open_dialog(main_window)

    assert dlg._table.rowCount() == 1
    assert dlg._table.item(0, dlg.COL_RECORDING).text() == "S01.csv"


# ---------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------
def test_csv_export_round_trips(tmp_path, main_window):
    """Export visible rows to CSV; the file has matching columns + values."""
    from rrational.inspector.annotation_table_dialog import CSV_FIELDS

    main_window.add_dataset(_make_synthetic("S01"))
    _persist_annotations("S01", [(12.5, "first"), (44.25, "second")])

    dlg = _open_dialog(main_window)
    out = tmp_path / "export.csv"
    written = dlg.export_to_csv(out)

    assert written == 2
    assert out.exists()
    with out.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        assert tuple(reader.fieldnames) == CSV_FIELDS
        rows = list(reader)
    assert len(rows) == 2
    by_label = {r["label"]: r for r in rows}
    assert set(by_label) == {"first", "second"}
    assert by_label["first"]["recording"] == "S01.csv"
    assert float(by_label["first"]["start_s"]) == pytest.approx(12.5)
    assert float(by_label["first"]["end_s"]) == pytest.approx(12.5)
    assert by_label["first"]["source"] == "manual"


# ---------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------
def test_csv_import_creates_annotations(tmp_path, main_window):
    """Import a CSV file → annotation YAML on disk for matched recordings."""
    from rrational.inspector.annotation_persistence import load_annotations

    main_window.add_dataset(_make_synthetic("S01"))
    main_window.add_dataset(_make_synthetic("S02"))

    csv_path = tmp_path / "incoming.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["recording", "start_s", "end_s", "label", "source"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "recording": "S01.csv",
                "start_s": "15.0",
                "end_s": "15.0",
                "label": "imported one",
                "source": "manual",
            }
        )
        writer.writerow(
            {
                "recording": "S02",  # stem-style match should also work
                "start_s": "27.5",
                "end_s": "27.5",
                "label": "imported two",
                "source": "manual",
            }
        )

    dlg = _open_dialog(main_window)
    imported, recordings = dlg.import_from_csv(csv_path)

    assert imported == 2
    assert recordings == {"S01", "S02"}
    s01 = load_annotations("S01")
    s02 = load_annotations("S02")
    assert len(s01) == 1 and s01[0].text == "imported one"
    assert s01[0].t == pytest.approx(15.0)
    assert len(s02) == 1 and s02[0].text == "imported two"
    assert s02[0].t == pytest.approx(27.5)
    # Table refreshed automatically.
    assert dlg._table.rowCount() == 2


def test_csv_import_skips_rows_for_unloaded_recordings(tmp_path, main_window):
    from rrational.inspector.annotation_persistence import load_annotations

    main_window.add_dataset(_make_synthetic("S01"))

    csv_path = tmp_path / "incoming.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["recording", "start_s", "end_s", "label", "source"]
        )
        writer.writeheader()
        writer.writerow(
            {
                "recording": "S01.csv",
                "start_s": "1.0",
                "end_s": "1.0",
                "label": "kept",
                "source": "manual",
            }
        )
        writer.writerow(
            {
                "recording": "S99-unknown.csv",
                "start_s": "2.0",
                "end_s": "2.0",
                "label": "dropped",
                "source": "manual",
            }
        )

    dlg = _open_dialog(main_window)
    imported, recordings = dlg.import_from_csv(csv_path)

    assert imported == 1
    assert recordings == {"S01"}
    assert load_annotations("S99-unknown") == []
    assert [a.text for a in load_annotations("S01")] == ["kept"]


def test_csv_import_then_export_roundtrip(tmp_path, main_window):
    """Import N rows, then export — the export contains the same labels."""
    main_window.add_dataset(_make_synthetic("S01"))

    csv_in = tmp_path / "in.csv"
    with csv_in.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["recording", "start_s", "end_s", "label", "source"]
        )
        writer.writeheader()
        for t, label in [(1.0, "alpha"), (2.0, "beta"), (3.0, "gamma")]:
            writer.writerow(
                {
                    "recording": "S01.csv",
                    "start_s": str(t),
                    "end_s": str(t),
                    "label": label,
                    "source": "manual",
                }
            )

    dlg = _open_dialog(main_window)
    dlg.import_from_csv(csv_in)

    csv_out = tmp_path / "out.csv"
    dlg.export_to_csv(csv_out)
    with csv_out.open("r", encoding="utf-8", newline="") as f:
        labels = [r["label"] for r in csv.DictReader(f)]
    assert sorted(labels) == ["alpha", "beta", "gamma"]


# ---------------------------------------------------------------------
# Delete + inline edit
# ---------------------------------------------------------------------
def test_delete_selected_removes_rows_from_disk(main_window):
    from rrational.inspector.annotation_persistence import load_annotations

    main_window.add_dataset(_make_synthetic("S01"))
    _persist_annotations("S01", [(10.0, "a"), (20.0, "b"), (30.0, "c")])

    dlg = _open_dialog(main_window)
    assert dlg._table.rowCount() == 3

    # Select the row whose label is "b" — find it deterministically.
    target_row = None
    for r in range(dlg._table.rowCount()):
        if dlg._table.item(r, dlg.COL_LABEL).text() == "b":
            target_row = r
            break
    assert target_row is not None
    dlg._table.selectRow(target_row)
    dlg._on_delete_selected()

    remaining = load_annotations("S01")
    assert sorted(a.text for a in remaining) == ["a", "c"]
    assert dlg._table.rowCount() == 2


def test_inline_label_edit_persists(main_window):
    from rrational.inspector.annotation_persistence import load_annotations

    main_window.add_dataset(_make_synthetic("S01"))
    _persist_annotations("S01", [(12.0, "original")])

    dlg = _open_dialog(main_window)
    assert dlg._table.rowCount() == 1
    label_item = dlg._table.item(0, dlg.COL_LABEL)
    label_item.setText("edited via table")

    stored = load_annotations("S01")
    assert len(stored) == 1
    assert stored[0].text == "edited via table"
    assert stored[0].t == pytest.approx(12.0)


# ---------------------------------------------------------------------
# Tools-menu wiring
# ---------------------------------------------------------------------
def test_tools_menu_exposes_annotations_action(main_window):
    """The Annotations action exists, is enabled, and opens the dialog."""
    from rrational.inspector.annotation_table_dialog import AnnotationTableDialog

    act = main_window._annotation_table_act
    assert act is not None
    assert act.isEnabled()

    main_window._on_show_annotation_table()
    dlg = main_window._annotation_table_dialog
    assert isinstance(dlg, AnnotationTableDialog)
    dlg.close()
