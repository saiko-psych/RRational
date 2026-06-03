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

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
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


class _SequencesPane(QWidget):
    """Placeholder for ordered section chains used in Sequence Comparison."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(20, 20, 20, 20)
        label = QLabel(
            "<h3>Sequences</h3>"
            "<p style='color:#888; max-width:500px'>"
            "Ordered chains of sections (e.g. "
            "<code>rest_pre → music_block_1 → pause → music_block_2 → rest_post</code>) "
            "for the Sequence-Comparison analysis mode.</p>"
            "<p style='color:#aaa'>Coming in Phase 4b step 2.</p>"
        )
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)


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
        self._sequences_pane = _SequencesPane(self)

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

    def on_active_dataset_changed(self, data: "InspectorData | None") -> None:
        self._events_pane.update_from(data)
        self._sections_pane.update_from(data)
        # Groups list depends on the whole workspace, refresh anyway in
        # case the active change came alongside a workspace change.
        self._groups_pane.refresh_from_workspace()
