"""Cross-recording annotation table (MNELAB "Markers"-style).

The PreprocessingPanel-bound annotation UI only sees the *active*
recording. This dialog aggregates every loaded dataset's on-disk
annotation file into one table the user can sort, filter, edit-in-place,
delete from, and round-trip via CSV.

Columns
-------
Recording  Start (s)  End (s)  Duration (s)  Label  Source

The :class:`Annotation` dataclass currently stores a single instant
(``t``) plus free-text (``text``). The dialog therefore renders ``End``
identical to ``Start`` and ``Duration`` as 0.0 — but the CSV schema is
deliberately written with separate ``start_s`` / ``end_s`` columns so
future range-annotations land in place without breaking exports.

CSV schema (UTF-8, comma-separated)::

    recording,start_s,end_s,label,source
    S01.csv,12.50,12.50,subject coughed,manual

The ``source`` column is informational only — every persisted
annotation is currently treated as ``manual``.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtGui import QAction
from qtpy.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from rrational.inspector.annotation_persistence import (
    load_annotations,
    save_annotations,
)
from rrational.inspector.annotations import Annotation
from rrational.inspector.history import AddAnnotation

if TYPE_CHECKING:  # pragma: no cover - typing only
    from rrational.inspector.main_window import MainWindow


# Public so tests + import code can reuse the exact field names.
CSV_FIELDS: tuple[str, ...] = ("recording", "start_s", "end_s", "label", "source")

# Default value stamped onto every persisted annotation (the dataclass
# itself does not carry a source field today).
DEFAULT_SOURCE = "manual"


class AnnotationTableDialog(QDialog):
    """Modal cross-recording annotation table with CSV import / export."""

    HEADERS = ("Recording", "Start (s)", "End (s)", "Duration (s)", "Label", "Source")

    # Column indices used by the slots below — keep in sync with HEADERS.
    COL_RECORDING = 0
    COL_START = 1
    COL_END = 2
    COL_DURATION = 3
    COL_LABEL = 4
    COL_SOURCE = 5

    # Role we tuck the source-marker on each row so the filter combobox
    # can hide rows without re-reading from disk on every change.
    _ROLE_SOURCE = Qt.UserRole + 1

    def __init__(self, main_window: "MainWindow", parent=None) -> None:
        super().__init__(parent)
        self._main = main_window
        self.setWindowTitle("Annotations")
        self.resize(720, 480)

        # ----- Toolbar (top row) ----------------------------------------
        toolbar = QHBoxLayout()
        self._import_btn = QPushButton("Import CSV…", self)
        self._import_btn.setToolTip("Append annotations from a CSV file")
        self._import_btn.clicked.connect(self._on_import_csv)
        toolbar.addWidget(self._import_btn)

        self._export_btn = QPushButton("Export CSV…", self)
        self._export_btn.setToolTip("Save the current table to a CSV file")
        self._export_btn.clicked.connect(self._on_export_csv)
        toolbar.addWidget(self._export_btn)

        self._delete_btn = QPushButton("Delete selected", self)
        self._delete_btn.setToolTip("Remove the selected annotations from disk")
        self._delete_btn.clicked.connect(self._on_delete_selected)
        toolbar.addWidget(self._delete_btn)

        toolbar.addStretch(1)

        toolbar.addWidget(QLabel("Show:", self))
        self._filter_combo = QComboBox(self)
        self._filter_combo.addItems(["All", "Only manual", "Only auto"])
        self._filter_combo.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self._filter_combo)

        close_btn = QPushButton("Close", self)
        close_btn.clicked.connect(self.accept)
        toolbar.addWidget(close_btn)

        # ----- Table ----------------------------------------------------
        self._table = QTableWidget(0, len(self.HEADERS), self)
        self._table.setHorizontalHeaderLabels(list(self.HEADERS))
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._table.setSortingEnabled(True)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)
        # Label gets the leftover space — it's the only free-text column.
        header.setSectionResizeMode(self.COL_LABEL, QHeaderView.Stretch)
        self._table.itemChanged.connect(self._on_item_changed)

        # ----- Empty-state hint (shown when no rows) ----------------------
        self._empty_hint = QLabel(
            "<p style='color:#888;'>"
            "<b>No annotations yet.</b><br><br>"
            "Add them inline by switching to <i>Annotation mode</i> in the "
            "Preprocessing panel and clicking a beat on the plot,<br>"
            "or import a CSV via <b>Import CSV...</b> above. The expected "
            "columns are <code>recording,start_s,end_s,label,source</code>."
            "</p>",
            self,
        )
        self._empty_hint.setTextFormat(Qt.RichText)
        self._empty_hint.setAlignment(Qt.AlignCenter)
        self._empty_hint.setWordWrap(True)

        # Stack the table over the hint so we can swap based on row count.
        self._body_stack = QStackedWidget(self)
        self._body_stack.addWidget(self._table)
        self._body_stack.addWidget(self._empty_hint)

        # ----- Layout ---------------------------------------------------
        root = QVBoxLayout(self)
        root.addLayout(toolbar)
        root.addWidget(self._body_stack)

        # Initial population.
        self._suspend_item_signal = False
        self._refresh()

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------
    def _project_path(self) -> Path | None:
        proj = getattr(self._main, "_project", None)
        return proj.project_path if proj is not None else None

    def _pid_for_dataset(self, ds) -> str:
        return Path(ds.name).stem

    def _collect_all_annotations(self) -> list[tuple[str, str, Annotation]]:
        """Return ``(recording_name, pid, annotation)`` for every dataset.

        Reads each dataset's on-disk file fresh so closing + reopening
        the dialog always reflects the persisted truth (the
        PreprocessingPanel's in-memory list covers the active dataset
        only).
        """
        project_path = self._project_path()
        rows: list[tuple[str, str, Annotation]] = []
        for ds in getattr(self._main, "_datasets", []) or []:
            pid = self._pid_for_dataset(ds)
            try:
                stored = load_annotations(pid, project_path=project_path)
            except Exception:  # pragma: no cover - defensive
                stored = []
            for ann in stored:
                rows.append((ds.name, pid, ann))
        return rows

    # ------------------------------------------------------------------
    # Render
    # ------------------------------------------------------------------
    def _refresh(self) -> None:
        """Wipe + repopulate the table from disk."""
        rows = self._collect_all_annotations()
        self._suspend_item_signal = True
        try:
            # Sorting must be off while we batch-insert or QTableWidget
            # re-shuffles items mid-loop and the row indices we just
            # populated go stale.
            self._table.setSortingEnabled(False)
            self._table.setRowCount(0)
            for recording, pid, ann in rows:
                self._append_row(recording, pid, ann, source=DEFAULT_SOURCE)
            self._table.setSortingEnabled(True)
        finally:
            self._suspend_item_signal = False
        self._apply_filter()
        # Swap to the empty-state hint when there is nothing to show.
        # Index 0 is the table, index 1 is the hint label.
        self._body_stack.setCurrentIndex(0 if rows else 1)
        # Bulk-action buttons are useless without rows — hide them too.
        self._export_btn.setEnabled(bool(rows))
        self._delete_btn.setEnabled(bool(rows))

    def _append_row(
        self,
        recording: str,
        pid: str,
        ann: Annotation,
        source: str = DEFAULT_SOURCE,
    ) -> int:
        """Add one row with all six columns populated. Returns row index."""
        r = self._table.rowCount()
        self._table.insertRow(r)

        # Recording — read-only, carries the pid in UserRole for delete /
        # edit dispatch and the annotation t (the only stable key today).
        rec_item = QTableWidgetItem(recording)
        rec_item.setFlags(rec_item.flags() & ~Qt.ItemIsEditable)
        rec_item.setData(Qt.UserRole, pid)
        rec_item.setData(self._ROLE_SOURCE, source)
        self._table.setItem(r, self.COL_RECORDING, rec_item)

        # Numeric columns — read-only display. We do not let the user
        # retime an annotation via this table; that's the job of the
        # plot click + edit dialog in PreprocessingPanel.
        start = float(ann.t)
        end = float(ann.t)  # point-like, no end-time on Annotation today
        duration = end - start

        for col, val in (
            (self.COL_START, start),
            (self.COL_END, end),
            (self.COL_DURATION, duration),
        ):
            item = QTableWidgetItem()
            # ``EditRole`` numeric value gives QTableWidget proper numeric
            # sorting even though the display text is fixed-precision.
            item.setData(Qt.EditRole, float(val))
            item.setData(Qt.DisplayRole, f"{val:.3f}")
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self._table.setItem(r, col, item)

        # Label — the only editable column.
        label_item = QTableWidgetItem(str(ann.text))
        label_item.setData(Qt.UserRole, float(ann.t))  # original t for lookup
        self._table.setItem(r, self.COL_LABEL, label_item)

        # Source — read-only badge.
        src_item = QTableWidgetItem(str(source))
        src_item.setFlags(src_item.flags() & ~Qt.ItemIsEditable)
        self._table.setItem(r, self.COL_SOURCE, src_item)
        return r

    # ------------------------------------------------------------------
    # Filter combobox
    # ------------------------------------------------------------------
    def _apply_filter(self, *_args) -> None:
        choice = self._filter_combo.currentText()
        for r in range(self._table.rowCount()):
            src_item = self._table.item(r, self.COL_RECORDING)
            source = (
                str(src_item.data(self._ROLE_SOURCE))
                if src_item is not None
                else DEFAULT_SOURCE
            )
            if choice == "All":
                show = True
            elif choice == "Only manual":
                show = source == "manual"
            elif choice == "Only auto":
                show = source == "auto"
            else:
                show = True
            self._table.setRowHidden(r, not show)

    # ------------------------------------------------------------------
    # Inline label edit
    # ------------------------------------------------------------------
    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._suspend_item_signal:
            return
        if item.column() != self.COL_LABEL:
            return
        row = item.row()
        new_text = item.text()
        original_t = float(item.data(Qt.UserRole))
        rec_item = self._table.item(row, self.COL_RECORDING)
        if rec_item is None:
            return
        pid = str(rec_item.data(Qt.UserRole))
        self._update_label_on_disk(pid, original_t, new_text)
        self._sync_active_panel_if_needed(pid)

    def _update_label_on_disk(self, pid: str, t: float, new_text: str) -> None:
        project = self._project_path()
        items = load_annotations(pid, project_path=project)
        changed = False
        for ann in items:
            if abs(ann.t - t) < 1e-6:
                ann.text = new_text
                changed = True
                break
        if changed:
            save_annotations(pid, items, project_path=project)

    # ------------------------------------------------------------------
    # Delete selected
    # ------------------------------------------------------------------
    def _selected_rows(self) -> list[int]:
        rows = {idx.row() for idx in self._table.selectedIndexes()}
        return sorted(rows)

    def _on_delete_selected(self) -> None:
        rows = self._selected_rows()
        if not rows:
            return
        if not getattr(self._main, "test_mode", False):
            res = QMessageBox.question(
                self,
                "Delete annotations",
                f"Delete {len(rows)} annotation(s)? This cannot be undone.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if res != QMessageBox.Yes:
                return

        # Group deletions by pid so we read+write each YAML once.
        by_pid: dict[str, list[float]] = {}
        for r in rows:
            rec_item = self._table.item(r, self.COL_RECORDING)
            label_item = self._table.item(r, self.COL_LABEL)
            if rec_item is None or label_item is None:
                continue
            pid = str(rec_item.data(Qt.UserRole))
            t = float(label_item.data(Qt.UserRole))
            by_pid.setdefault(pid, []).append(t)

        project = self._project_path()
        affected_pids: list[str] = []
        for pid, ts in by_pid.items():
            items = load_annotations(pid, project_path=project)
            kept = [a for a in items if not any(abs(a.t - t) < 1e-6 for t in ts)]
            if len(kept) != len(items):
                save_annotations(pid, kept, project_path=project)
                affected_pids.append(pid)

        for pid in affected_pids:
            self._sync_active_panel_if_needed(pid)
        self._refresh()

    # ------------------------------------------------------------------
    # Active-panel sync
    # ------------------------------------------------------------------
    def _sync_active_panel_if_needed(self, pid: str) -> None:
        """If ``pid`` is the active dataset, re-render its plot markers.

        Cross-recording edits made here for inactive datasets simply
        persist; they'll be picked up next time the user switches to
        that dataset (``_restore_annotations`` fires on activation).
        """
        active_idx = getattr(self._main, "_active_idx", None)
        datasets = getattr(self._main, "_datasets", []) or []
        if active_idx is None or active_idx >= len(datasets):
            return
        active_pid = self._pid_for_dataset(datasets[active_idx])
        if active_pid != pid:
            return
        panel = None
        try:
            panel = self._main._browse_tab._preprocessing_panel
        except AttributeError:  # pragma: no cover - layouts without browse tab
            return
        if panel is not None and hasattr(panel, "_restore_annotations"):
            try:
                panel._restore_annotations()
            except Exception:  # pragma: no cover - defensive
                pass

    # ------------------------------------------------------------------
    # CSV export
    # ------------------------------------------------------------------
    def _on_export_csv(self) -> None:
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export annotations",
            "annotations.csv",
            "CSV (*.csv)",
        )
        if not path_str:
            return
        self.export_to_csv(Path(path_str))

    def export_to_csv(self, path: Path) -> int:
        """Write every CURRENTLY VISIBLE row to ``path``. Returns row count."""
        path = Path(path)
        rows_written = 0
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(CSV_FIELDS))
            writer.writeheader()
            for r in range(self._table.rowCount()):
                if self._table.isRowHidden(r):
                    continue
                rec_item = self._table.item(r, self.COL_RECORDING)
                start_item = self._table.item(r, self.COL_START)
                end_item = self._table.item(r, self.COL_END)
                label_item = self._table.item(r, self.COL_LABEL)
                src_item = self._table.item(r, self.COL_SOURCE)
                if None in (rec_item, start_item, end_item, label_item, src_item):
                    continue
                writer.writerow(
                    {
                        "recording": rec_item.text(),
                        "start_s": f"{float(start_item.data(Qt.EditRole)):.6f}",
                        "end_s": f"{float(end_item.data(Qt.EditRole)):.6f}",
                        "label": label_item.text(),
                        "source": src_item.text(),
                    }
                )
                rows_written += 1
        return rows_written

    # ------------------------------------------------------------------
    # CSV import
    # ------------------------------------------------------------------
    def _on_import_csv(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Import annotations",
            "",
            "CSV (*.csv)",
        )
        if not path_str:
            return
        try:
            imported, recordings = self.import_from_csv(Path(path_str))
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.warning(
                self,
                "Import failed",
                f"Could not import annotations:\n{exc}",
            )
            return
        if not getattr(self._main, "test_mode", False):
            QMessageBox.information(
                self,
                "Import complete",
                f"Imported {imported} annotation(s) across "
                f"{len(recordings)} recording(s).",
            )
        else:  # pragma: no cover - test side-effect convenience
            self._main.statusBar().showMessage(
                f"Imported {imported} annotation(s) across "
                f"{len(recordings)} recording(s).",
                3000,
            )

    def import_from_csv(self, path: Path) -> tuple[int, set[str]]:
        """Parse + persist every row in ``path``. Returns (count, pids).

        Rows whose ``recording`` does not match a loaded dataset (by
        file name OR file stem) are silently skipped — the user can
        load that dataset and re-import. We do this rather than
        creating ghost YAML files because the inspector keys every
        side-car on the loaded dataset's pid.
        """
        path = Path(path)
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ValueError("CSV file is empty.")
            missing = [
                c
                for c in ("recording", "start_s", "label")
                if c not in reader.fieldnames
            ]
            if missing:
                raise ValueError(
                    f"CSV is missing required column(s): {', '.join(missing)}"
                )
            parsed = list(reader)

        # Build a lookup of all loaded datasets keyed by name AND by stem,
        # so the CSV's ``recording`` field can match either style.
        ds_by_key: dict[str, str] = {}  # key -> pid
        for ds in getattr(self._main, "_datasets", []) or []:
            pid = self._pid_for_dataset(ds)
            ds_by_key[ds.name] = pid
            ds_by_key[pid] = pid

        project = self._project_path()

        # Group new annotations by pid so we make ONE save per recording.
        new_by_pid: dict[str, list[Annotation]] = {}
        skipped = 0
        for row in parsed:
            rec = (row.get("recording") or "").strip()
            if not rec:
                skipped += 1
                continue
            pid = ds_by_key.get(rec)
            if pid is None:
                # Try stripping the extension if the user typed e.g. "S01.csv"
                pid = ds_by_key.get(Path(rec).stem)
            if pid is None:
                skipped += 1
                continue
            try:
                t = float(row.get("start_s") or 0.0)
            except (TypeError, ValueError):
                skipped += 1
                continue
            text = (row.get("label") or "").strip()
            ann = Annotation.create(t=t, text=text)
            new_by_pid.setdefault(pid, []).append(ann)

        imported = 0
        history = getattr(self._main, "history", None)
        for pid, new_items in new_by_pid.items():
            existing = load_annotations(pid, project_path=project)
            merged = existing + new_items
            save_annotations(pid, merged, project_path=project)
            imported += len(new_items)
            # Record one history action per imported annotation so the
            # generated recipe replays the same per-row attachments. We
            # swallow recorder exceptions per-row — a logging glitch
            # must not abort a 1000-row import.
            if history is not None:
                for ann in new_items:
                    try:
                        history.record(
                            AddAnnotation(pid=pid, t=float(ann.t), label=str(ann.text))
                        )
                    except Exception:  # pragma: no cover - defensive
                        pass
            self._sync_active_panel_if_needed(pid)

        self._refresh()
        return imported, set(new_by_pid.keys())

    # ------------------------------------------------------------------
    # Right-click context menu (small UX nicety)
    # ------------------------------------------------------------------
    def contextMenuEvent(self, event) -> None:  # noqa: N802 - Qt API name
        if not self._selected_rows():
            return
        menu = QMenu(self)
        del_act = QAction("Delete selected", self)
        del_act.triggered.connect(self._on_delete_selected)
        menu.addAction(del_act)
        menu.exec(event.globalPos())
