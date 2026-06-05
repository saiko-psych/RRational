"""Phase 24B — modal dialog to import Group / Sequence mappings from CSV.

Mirrors ``rrational.gui.tabs.data`` lines 884-1147: the user picks a CSV
file, the dialog shows a preview, three QComboBoxes let them map
"Participant ID" / "Group" / "Sequence" columns, and clicking Apply
merges the assignments into ``participants.yml`` via
:func:`rrational.gui.persistence.save_participants`. Missing groups /
sequences are auto-created via :func:`save_groups` /
:func:`save_event_sequences` so the inspector stays in lock-step with
the Streamlit storage layout.

Returns an ``ImportResult`` summary from :meth:`run_import` for callers
that want to show "Updated N participants, created M groups" toasts.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from qtpy.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


@dataclass
class ImportResult:
    """Summary of an import-mapping run, for status-bar messages."""

    updated_participants: int = 0
    created_groups: list[str] = field(default_factory=list)
    created_sequences: list[str] = field(default_factory=list)
    not_found_ids: list[str] = field(default_factory=list)

    def summary(self) -> str:
        parts = [f"Updated {self.updated_participants} participant(s)"]
        if self.created_groups:
            parts.append(f"created {len(self.created_groups)} group(s)")
        if self.created_sequences:
            parts.append(f"created {len(self.created_sequences)} sequence(s)")
        return ", ".join(parts) + "."


def _read_csv_rows(csv_path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Return ``(columns, rows)`` from a CSV.

    Tolerates BOM via utf-8-sig and falls back to latin-1 on decode
    errors. The first row is treated as the header.
    """
    encodings = ("utf-8-sig", "utf-8", "latin-1")
    last_err: Exception | None = None
    for enc in encodings:
        try:
            with csv_path.open("r", newline="", encoding=enc) as f:
                reader = csv.DictReader(f)
                rows = [dict(r) for r in reader]
                cols = list(reader.fieldnames or [])
                return cols, rows
        except (UnicodeDecodeError, OSError) as e:
            last_err = e
            continue
    if last_err is not None:
        raise last_err
    return [], []


class ImportParticipantMappingDialog(QDialog):
    """Modal: pick a CSV, map columns, merge into participants.yml."""

    def __init__(
        self,
        main_window,
        parent=None,
        csv_path: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import Group / Sequence mapping from CSV")
        self.setMinimumWidth(720)
        self.setMinimumHeight(480)

        self._main_window = main_window
        self._csv_path: Path | None = csv_path
        self._columns: list[str] = []
        self._rows: list[dict[str, str]] = []
        self._result: ImportResult | None = None

        outer = QVBoxLayout(self)

        # ---- File picker ----
        file_row = QHBoxLayout()
        self._path_label = QLabel("<i>No file chosen</i>")
        self._path_label.setWordWrap(True)
        file_row.addWidget(self._path_label, stretch=1)
        self._pick_btn = QPushButton("Choose CSV...")
        self._pick_btn.setToolTip(
            "Pick a CSV with one row per participant. Mapping happens in the "
            "dropdowns below."
        )
        self._pick_btn.clicked.connect(self._on_pick_file)
        file_row.addWidget(self._pick_btn)
        outer.addLayout(file_row)

        # ---- Column mapping dropdowns ----
        form = QFormLayout()
        self._id_combo = QComboBox()
        self._id_combo.setToolTip("CSV column containing the participant ID")
        form.addRow("Participant ID column:", self._id_combo)
        self._group_combo = QComboBox()
        self._group_combo.setToolTip(
            "CSV column containing the group label (leave as '(none)' to skip)"
        )
        form.addRow("Group column:", self._group_combo)
        self._sequence_combo = QComboBox()
        self._sequence_combo.setToolTip(
            "CSV column containing the sequence label (leave as '(none)' to skip)"
        )
        form.addRow("Sequence column:", self._sequence_combo)
        outer.addLayout(form)

        # ---- Preview table ----
        outer.addWidget(QLabel("<b>Preview (first 20 rows)</b>"))
        self._preview = QTableWidget(0, 0, self)
        self._preview.setEditTriggers(QTableWidget.NoEditTriggers)
        self._preview.setSelectionBehavior(QTableWidget.SelectRows)
        self._preview.setSelectionMode(QAbstractItemView.SingleSelection)
        self._preview.setAlternatingRowColors(True)
        outer.addWidget(self._preview, stretch=1)

        # ---- Button box ----
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._apply_btn = bb.button(QDialogButtonBox.Ok)
        self._apply_btn.setText("Apply")
        self._apply_btn.setToolTip(
            "Merge the column assignments into participants.yml and auto-create "
            "missing groups / sequences"
        )
        self._apply_btn.setEnabled(False)
        bb.accepted.connect(self._on_apply)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)

        if csv_path is not None:
            self._load_csv(csv_path)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def result(self) -> ImportResult | None:
        return self._result

    def set_csv_for_test(self, csv_path: Path) -> None:
        """Programmatic CSV load used by tests (bypasses the file dialog)."""
        self._load_csv(csv_path)

    def set_column_mapping(
        self,
        id_col: str,
        group_col: str | None = None,
        sequence_col: str | None = None,
    ) -> None:
        """Set the combo selections (test helper)."""
        idx = self._id_combo.findText(id_col)
        if idx >= 0:
            self._id_combo.setCurrentIndex(idx)
        if group_col is not None:
            i = self._group_combo.findText(group_col)
            if i >= 0:
                self._group_combo.setCurrentIndex(i)
        if sequence_col is not None:
            i = self._sequence_combo.findText(sequence_col)
            if i >= 0:
                self._sequence_combo.setCurrentIndex(i)

    # ------------------------------------------------------------------
    # File loading
    # ------------------------------------------------------------------
    def _on_pick_file(self) -> None:
        start_dir = ""
        if self._csv_path is not None:
            start_dir = str(self._csv_path.parent)
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Pick participant mapping CSV",
            start_dir,
            "CSV files (*.csv);;All files (*)",
        )
        if not path_str:
            return
        self._load_csv(Path(path_str))

    def _load_csv(self, csv_path: Path) -> None:
        try:
            cols, rows = _read_csv_rows(csv_path)
        except Exception as e:  # pragma: no cover - error path
            QMessageBox.warning(
                self, "Could not read CSV", f"Failed to parse {csv_path}:\n{e}"
            )
            return
        if not cols:
            QMessageBox.warning(self, "Empty CSV", f"No columns found in {csv_path}.")
            return
        self._csv_path = csv_path
        self._columns = cols
        self._rows = rows
        self._path_label.setText(
            f"<b>{csv_path.name}</b> — {len(rows)} rows, {len(cols)} columns"
        )

        # Populate combos. The first option is "(none)" for group/sequence
        # so users can import groups only or sequences only.
        self._id_combo.clear()
        for c in cols:
            self._id_combo.addItem(c)
        for combo in (self._group_combo, self._sequence_combo):
            combo.clear()
            combo.addItem("(none)")
            for c in cols:
                combo.addItem(c)

        # Heuristic defaults — match common column names from the
        # Streamlit data tab.
        for guess in ("code", "id", "participant", "participant_id"):
            i = self._id_combo.findText(guess)
            if i >= 0:
                self._id_combo.setCurrentIndex(i)
                break
        for guess in ("group", "Group", "condition"):
            i = self._group_combo.findText(guess)
            if i >= 0:
                self._group_combo.setCurrentIndex(i)
                break
        for guess in ("sequence", "Sequence", "playlist", "order"):
            i = self._sequence_combo.findText(guess)
            if i >= 0:
                self._sequence_combo.setCurrentIndex(i)
                break

        # Preview — first 20 rows, all columns.
        self._preview.clear()
        self._preview.setColumnCount(len(cols))
        self._preview.setHorizontalHeaderLabels(cols)
        preview_rows = rows[:20]
        self._preview.setRowCount(len(preview_rows))
        for r, row in enumerate(preview_rows):
            for c, col in enumerate(cols):
                self._preview.setItem(
                    r, c, QTableWidgetItem(str(row.get(col, "") or ""))
                )
        self._preview.resizeColumnsToContents()

        self._apply_btn.setEnabled(bool(rows))

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------
    def _project_path(self):
        proj = getattr(self._main_window, "_project", None)
        return proj.project_path if proj is not None else None

    def _on_apply(self) -> None:
        self._result = self._apply_mapping()
        self.accept()

    def _apply_mapping(self) -> ImportResult:
        """Merge the CSV → participants / groups / sequences. Pure-ish: it
        writes to disk but is otherwise testable in isolation."""
        from rrational.gui.persistence import (
            load_event_sequences,
            load_groups,
            load_participants,
            save_event_sequences,
            save_groups,
            save_participants,
        )

        result = ImportResult()
        id_col = self._id_combo.currentText()
        group_col = self._group_combo.currentText()
        seq_col = self._sequence_combo.currentText()
        if not id_col:
            return result

        has_group = group_col and group_col != "(none)"
        has_seq = seq_col and seq_col != "(none)"

        proj_path = self._project_path()
        participants = load_participants(project_path=proj_path) or {}
        groups = load_groups(project_path=proj_path) or {}
        sequences = load_event_sequences(project_path=proj_path) or {}

        # First pass: collect all distinct group/sequence labels so we
        # auto-create the missing ones up front.
        wanted_groups: set[str] = set()
        wanted_sequences: set[str] = set()
        for row in self._rows:
            if has_group:
                g = str(row.get(group_col, "") or "").strip()
                if g:
                    wanted_groups.add(g)
            if has_seq:
                s = str(row.get(seq_col, "") or "").strip()
                if s:
                    wanted_sequences.add(s)
        for g in sorted(wanted_groups):
            if g not in groups:
                groups[g] = {"label": g, "events": []}
                result.created_groups.append(g)
        for s in sorted(wanted_sequences):
            if s not in sequences:
                sequences[s] = {
                    "label": s,
                    "condition_order": ["condition_a", "condition_b", "condition_c"],
                }
                result.created_sequences.append(s)

        # Second pass: assign group / sequence per row. We DON'T require
        # the participant to already exist in participants.yml — if the
        # ID is new we just create an entry with empty event_order +
        # manual_events so it matches the Streamlit schema.
        for row in self._rows:
            pid = str(row.get(id_col, "") or "").strip()
            if not pid:
                continue
            existing = participants.get(pid)
            if existing is None:
                existing = {"event_order": [], "manual_events": []}
                participants[pid] = existing
            if has_group:
                g = str(row.get(group_col, "") or "").strip()
                if g:
                    existing["group"] = g
            if has_seq:
                s = str(row.get(seq_col, "") or "").strip()
                if s:
                    existing["sequence"] = s
            result.updated_participants += 1

        save_groups(groups, project_path=proj_path)
        save_event_sequences(sequences, project_path=proj_path)
        save_participants(participants, project_path=proj_path)

        # Refresh inspector tabs so the new state is reflected.
        for tab_attr in (
            "_participants_tab",
            "_setup_tab",
            "_data_tab",
            "_analysis_tab",
        ):
            tab = getattr(self._main_window, tab_attr, None)
            if tab is None:
                continue
            refresher = getattr(tab, "on_workspace_changed", None) or getattr(
                tab, "refresh_from_workspace", None
            )
            if callable(refresher):
                try:
                    refresher()
                except Exception:  # pragma: no cover - defensive
                    continue
        return result
