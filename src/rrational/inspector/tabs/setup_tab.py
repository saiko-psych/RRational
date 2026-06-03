"""Setup tab — events / sections / groups / sequences.

Replaces the Phase 4a placeholder with four sub-panes that mirror the
Streamlit Setup tab. For Phase 4b step 1 we render the active dataset's
events and sections as sortable tables; Groups/Sequences (which are
project-level rather than dataset-level) get scaffold panes until the
project-management layer is ported.

All four panes update via ``on_active_dataset_changed`` — switching the
active dataset in BrowseTab reflects through the same notification
plumbing the rest of the inspector uses.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from qtpy.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from rrational.inspector.persistence import (
    Sequence,
    load_sequences,
    save_sequences,
)
from rrational.inspector.tabs.base import InspectorTab

if TYPE_CHECKING:
    from rrational.inspector.data_loader import InspectorData


def _fmt_time(t: float) -> str:
    """seconds-since-epoch → HH:MM:SS for human-readable tables."""
    return datetime.fromtimestamp(t).strftime("%H:%M:%S")


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f} s"
    minutes, secs = divmod(seconds, 60)
    return f"{int(minutes)}:{int(secs):02d}"


class _ReadOnlyTable(QTableWidget):
    """QTableWidget subclass with sensible defaults for our read-only views."""

    def __init__(self, headers: list[str], parent=None) -> None:
        super().__init__(0, len(headers), parent)
        self.setHorizontalHeaderLabels(headers)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)


class _EventsPane(QWidget):
    """Lists every EventMeta from the active dataset."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self._table = _ReadOnlyTable(["Label", "Time", "Epoch (s)"])
        layout.addWidget(self._table)

    def update_from(self, data: "InspectorData | None") -> None:
        self._table.setRowCount(0)
        if data is None:
            return
        for ev in data.events:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(ev.label))
            self._table.setItem(row, 1, QTableWidgetItem(_fmt_time(ev.t)))
            self._table.setItem(row, 2, QTableWidgetItem(f"{ev.t:.1f}"))


class _SectionsPane(QWidget):
    """Lists every SectionMeta from the active dataset."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self._table = _ReadOnlyTable(["Name", "Start", "End", "Duration", "Beats"])
        layout.addWidget(self._table)

    def update_from(self, data: "InspectorData | None") -> None:
        self._table.setRowCount(0)
        if data is None:
            return
        for sec in data.sections:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(sec.name))
            self._table.setItem(row, 1, QTableWidgetItem(_fmt_time(sec.t_start)))
            self._table.setItem(row, 2, QTableWidgetItem(_fmt_time(sec.t_end)))
            self._table.setItem(
                row, 3, QTableWidgetItem(_fmt_duration(sec.t_end - sec.t_start))
            )
            self._table.setItem(row, 4, QTableWidgetItem(str(sec.beat_count)))


class _GroupsPane(QWidget):
    """Shows all loaded datasets with their (currently unset) group label."""

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self._main_window = main_window
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self._info = QLabel(
            "<i>Group assignment edits coming in Phase 4b step 2 — "
            "ported from <code>gui.persistence.condition_labels</code>.</i>"
        )
        self._info.setWordWrap(True)
        layout.addWidget(self._info)
        self._table = _ReadOnlyTable(["Dataset", "Sections", "Group (read-only)"])
        layout.addWidget(self._table)

    def refresh_from_workspace(self) -> None:
        self._table.setRowCount(0)
        for ds in self._main_window._datasets:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(ds.name))
            self._table.setItem(row, 1, QTableWidgetItem(str(len(ds.data.sections))))
            self._table.setItem(row, 2, QTableWidgetItem("—"))


class _SequenceEditDialog(QDialog):
    """Modal dialog for creating / editing one Sequence.

    Two list widgets side-by-side:
    - left: available sections (union across loaded datasets, minus
      what's already in the sequence)
    - right: the sequence being built, ordered

    Up/Down buttons reorder the sequence; Add/Remove move items between
    the two lists.
    """

    def __init__(
        self,
        available_sections: list[str],
        initial: Sequence | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit sequence" if initial else "New sequence")
        self.resize(620, 400)

        outer = QVBoxLayout(self)

        # Name row
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Name:"))

        self._name_edit = QLineEdit(initial.name if initial else "")
        name_row.addWidget(self._name_edit)
        outer.addLayout(name_row)

        # Two-list editor
        lists_row = QHBoxLayout()

        # Left: available sections
        left_col = QVBoxLayout()
        left_col.addWidget(QLabel("Available sections:"))
        self._avail_list = QListWidget()
        self._avail_list.setSelectionMode(QAbstractItemView.SingleSelection)
        left_col.addWidget(self._avail_list)
        lists_row.addLayout(left_col, 1)

        # Middle: Add/Remove buttons
        mid_col = QVBoxLayout()
        mid_col.addStretch()
        self._add_btn = QPushButton("Add  >")
        self._add_btn.clicked.connect(self._on_add)
        self._remove_btn = QPushButton("<  Remove")
        self._remove_btn.clicked.connect(self._on_remove)
        mid_col.addWidget(self._add_btn)
        mid_col.addWidget(self._remove_btn)
        mid_col.addStretch()
        lists_row.addLayout(mid_col)

        # Right: sequence in order
        right_col = QVBoxLayout()
        right_col.addWidget(QLabel("Sequence (ordered):"))
        self._seq_list = QListWidget()
        self._seq_list.setSelectionMode(QAbstractItemView.SingleSelection)
        right_col.addWidget(self._seq_list)

        # Up/Down under the sequence list
        order_row = QHBoxLayout()
        self._up_btn = QPushButton("Move up")
        self._up_btn.clicked.connect(self._on_up)
        self._down_btn = QPushButton("Move down")
        self._down_btn.clicked.connect(self._on_down)
        order_row.addWidget(self._up_btn)
        order_row.addWidget(self._down_btn)
        right_col.addLayout(order_row)
        lists_row.addLayout(right_col, 1)

        outer.addLayout(lists_row)

        # OK / Cancel
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._on_accept)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)

        # Initial population
        initial_sections = list(initial.sections) if initial else []
        for s in initial_sections:
            self._seq_list.addItem(QListWidgetItem(s))
        for s in sorted(set(available_sections) - set(initial_sections)):
            self._avail_list.addItem(QListWidgetItem(s))

    # ----- list manipulation -----
    def _on_add(self) -> None:
        item = self._avail_list.currentItem()
        if item is None:
            return
        text = item.text()
        self._avail_list.takeItem(self._avail_list.row(item))
        self._seq_list.addItem(QListWidgetItem(text))

    def _on_remove(self) -> None:
        item = self._seq_list.currentItem()
        if item is None:
            return
        text = item.text()
        self._seq_list.takeItem(self._seq_list.row(item))
        # Re-insert into available, keeping it sorted
        self._avail_list.addItem(QListWidgetItem(text))
        self._avail_list.sortItems()

    def _on_up(self) -> None:
        row = self._seq_list.currentRow()
        if row <= 0:
            return
        item = self._seq_list.takeItem(row)
        self._seq_list.insertItem(row - 1, item)
        self._seq_list.setCurrentRow(row - 1)

    def _on_down(self) -> None:
        row = self._seq_list.currentRow()
        if row < 0 or row >= self._seq_list.count() - 1:
            return
        item = self._seq_list.takeItem(row)
        self._seq_list.insertItem(row + 1, item)
        self._seq_list.setCurrentRow(row + 1)

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(
                self, "Missing name", "Please give the sequence a name."
            )
            return
        if self._seq_list.count() < 2:
            QMessageBox.warning(
                self,
                "Too few sections",
                "A sequence needs at least 2 sections for repeated-measures analysis.",
            )
            return
        self.accept()

    def result_sequence(self) -> Sequence:
        return Sequence(
            name=self._name_edit.text().strip(),
            sections=[
                self._seq_list.item(i).text() for i in range(self._seq_list.count())
            ],
        )


class _SequencesPane(QWidget):
    """List + add/edit/remove for named ordered section sequences."""

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self._main_window = main_window
        # Loaded once on construction; mutations save back to disk.
        self._sequences: list[Sequence] = load_sequences()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        info = QLabel(
            "<i>Sequences are saved to "
            "<code>~/.rrational/inspector/sequences.yml</code> and "
            "available to the Analysis tab's Sequence-Comparison mode.</i>"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #777;")
        outer.addWidget(info)

        # Buttons
        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add sequence…")
        self._add_btn.clicked.connect(self._on_add)
        self._edit_btn = QPushButton("Edit…")
        self._edit_btn.clicked.connect(self._on_edit)
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.clicked.connect(self._on_remove)
        self._duplicate_btn = QPushButton("Duplicate")
        self._duplicate_btn.clicked.connect(self._on_duplicate)
        for b in (self._add_btn, self._edit_btn, self._remove_btn, self._duplicate_btn):
            btn_row.addWidget(b)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        self._table = QTableWidget(0, 3, self)
        self._table.setHorizontalHeaderLabels(["Name", "Length", "Sections"])
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.itemSelectionChanged.connect(self._refresh_buttons)
        outer.addWidget(self._table)

        self._refresh_table()
        self._refresh_buttons()

    # ------------------------------------------------------------------
    # Public API used by tests + other tabs
    # ------------------------------------------------------------------
    @property
    def sequences(self) -> list[Sequence]:
        return list(self._sequences)

    def _available_sections(self) -> list[str]:
        """Union of section names across every loaded dataset."""
        return sorted(
            {sec.name for ds in self._main_window._datasets for sec in ds.data.sections}
        )

    def refresh_workspace(self) -> None:
        # Sections might have changed; no need to rebuild the table
        # itself, just re-enable buttons.
        self._refresh_buttons()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _refresh_table(self) -> None:
        self._table.setRowCount(0)
        for seq in self._sequences:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(seq.name))
            self._table.setItem(row, 1, QTableWidgetItem(str(len(seq.sections))))
            self._table.setItem(row, 2, QTableWidgetItem(" → ".join(seq.sections)))

    def _refresh_buttons(self) -> None:
        has_selection = self._table.currentRow() >= 0
        self._edit_btn.setEnabled(has_selection)
        self._remove_btn.setEnabled(has_selection)
        self._duplicate_btn.setEnabled(has_selection)

    def _persist(self) -> None:
        save_sequences(self._sequences)
        # Notify the rest of the app so the Analysis tab can pick up the
        # new sequence list without the user having to click "refresh".
        notify = getattr(self._main_window, "_on_sequences_changed", None)
        if callable(notify):
            notify()

    # ----- button handlers -----
    def _on_add(self) -> None:
        available = self._available_sections()
        if not available:
            QMessageBox.information(
                self,
                "No sections available",
                "Load at least one .rrational file before defining a sequence — "
                "the editor populates available sections from the workspace.",
            )
            return
        dlg = _SequenceEditDialog(available_sections=available, parent=self)
        if dlg.exec() != QDialog.Accepted:
            return
        seq = dlg.result_sequence()
        if any(s.name == seq.name for s in self._sequences):
            QMessageBox.warning(
                self, "Duplicate name", f"A sequence named '{seq.name}' already exists."
            )
            return
        self._sequences.append(seq)
        self._persist()
        self._refresh_table()

    def _on_edit(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        # Available sections = workspace sections ∪ current sequence sections
        # (so the user can keep a section that no longer exists in any
        # loaded file — useful when partway through loading data).
        current = self._sequences[row]
        available = sorted(set(self._available_sections()) | set(current.sections))
        dlg = _SequenceEditDialog(
            available_sections=available, initial=current, parent=self
        )
        if dlg.exec() != QDialog.Accepted:
            return
        new_seq = dlg.result_sequence()
        # Name-conflict check (allow keeping the same name)
        if new_seq.name != current.name and any(
            s.name == new_seq.name for s in self._sequences
        ):
            QMessageBox.warning(
                self,
                "Duplicate name",
                f"A sequence named '{new_seq.name}' already exists.",
            )
            return
        self._sequences[row] = new_seq
        self._persist()
        self._refresh_table()

    def _on_remove(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        name = self._sequences[row].name
        if (
            QMessageBox.question(
                self,
                "Remove sequence",
                f"Delete sequence '{name}'? This cannot be undone.",
            )
            != QMessageBox.Yes
        ):
            return
        del self._sequences[row]
        self._persist()
        self._refresh_table()

    def _on_duplicate(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        src = self._sequences[row]
        # Suggest a new name with an "(copy)" suffix the user can edit
        new_name, ok = QInputDialog.getText(
            self,
            "Duplicate sequence",
            "Name for the copy:",
            text=f"{src.name} (copy)",
        )
        if not ok or not new_name.strip():
            return
        new_name = new_name.strip()
        if any(s.name == new_name for s in self._sequences):
            QMessageBox.warning(
                self, "Duplicate name", f"A sequence named '{new_name}' already exists."
            )
            return
        self._sequences.append(Sequence(name=new_name, sections=list(src.sections)))
        self._persist()
        self._refresh_table()


class SetupTab(InspectorTab):
    """Inspector Setup tab — sub-tabs for events / sections / groups / sequences."""

    TAB_LABEL = "Setup"

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(main_window, parent)

        self._subtabs = QTabWidget(self)
        self._subtabs.setDocumentMode(True)

        self._events_pane = _EventsPane(self)
        self._sections_pane = _SectionsPane(self)
        self._groups_pane = _GroupsPane(main_window, self)
        self._sequences_pane = _SequencesPane(main_window, self)

        self._subtabs.addTab(self._events_pane, "Events")
        self._subtabs.addTab(self._sections_pane, "Sections")
        self._subtabs.addTab(self._groups_pane, "Groups")
        self._subtabs.addTab(self._sequences_pane, "Sequences")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._subtabs)

    # ------------------------------------------------------------------
    # Notification hooks
    # ------------------------------------------------------------------
    def on_workspace_changed(self) -> None:
        self._groups_pane.refresh_from_workspace()
        self._sequences_pane.refresh_workspace()

    def on_active_dataset_changed(self, data: "InspectorData | None") -> None:
        self._events_pane.update_from(data)
        self._sections_pane.update_from(data)
        # Groups list depends on the whole workspace, refresh anyway in
        # case the active change came alongside a workspace change.
        self._groups_pane.refresh_from_workspace()
        self._sequences_pane.refresh_workspace()
