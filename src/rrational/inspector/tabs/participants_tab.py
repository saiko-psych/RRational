"""Participants tab — per-subject metadata editor.

Streamlit-shared persistence via ``gui.persistence.save_participants`` /
``load_participants`` (``participants.yml`` in the project's or global
config folder).

Schema (Streamlit-compatible)::

    {participant_id}:
      group: str | null            # link to groups.yml
      sequence: str | null         # link to event_sequences.yml
      label: str | null            # free-text display name
      event_order: list[str]       # user-chosen canonical event sequence
      manual_events: list[dict]    # per-participant event edits

The Inspector treats the dict as the source of truth — add/edit/delete
operations go through the editor and immediately persist.

Cross-tab notifications: a save triggers
``MainWindow._on_participants_changed`` so the Analysis tab's group
pane can pick up new participant-to-group bindings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from rrational.inspector.tabs.base import InspectorTab

if TYPE_CHECKING:
    from rrational.inspector.data_loader import InspectorData


class _ParticipantEditDialog(QDialog):
    """Modal editor for one participant entry.

    Group / sequence dropdowns are populated from the live
    ``groups.yml`` / ``event_sequences.yml`` so the user can't pick
    something that doesn't exist.
    """

    def __init__(
        self,
        existing_ids: list[str],
        available_groups: list[str],
        available_sequences: list[str],
        initial_id: str | None = None,
        initial: dict | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit participant" if initial_id else "New participant")
        self.setMinimumWidth(480)
        self._existing_ids = [i for i in existing_ids if i != (initial_id or "")]

        outer = QVBoxLayout(self)
        form = QFormLayout()
        self._id_edit = QLineEdit(initial_id or "")
        self._id_edit.setPlaceholderText("e.g. 0012MEBE, sub-01, P001")
        form.addRow("Participant ID *:", self._id_edit)

        self._label_edit = QLineEdit(
            (initial or {}).get("label", "") if initial else ""
        )
        self._label_edit.setPlaceholderText("Optional display name")
        form.addRow("Label:", self._label_edit)

        self._group_combo = QComboBox()
        self._group_combo.addItem("(none)", None)
        for grp in available_groups:
            self._group_combo.addItem(grp, grp)
        initial_group = (initial or {}).get("group") if initial else None
        idx = self._group_combo.findData(initial_group) if initial_group else 0
        self._group_combo.setCurrentIndex(idx if idx >= 0 else 0)
        form.addRow("Group:", self._group_combo)

        self._sequence_combo = QComboBox()
        self._sequence_combo.addItem("(none)", None)
        for seq in available_sequences:
            self._sequence_combo.addItem(seq, seq)
        initial_seq = (initial or {}).get("sequence") if initial else None
        idx = self._sequence_combo.findData(initial_seq) if initial_seq else 0
        self._sequence_combo.setCurrentIndex(idx if idx >= 0 else 0)
        form.addRow("Sequence:", self._sequence_combo)

        outer.addLayout(form)

        # Note about event_order / manual_events being managed elsewhere
        note = QLabel(
            "<i>event_order and manual_events are populated by the "
            "Browse/Preprocessing flow when the user inspects a "
            "recording; this dialog only edits the metadata above.</i>"
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #888;")
        outer.addWidget(note)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._on_accept)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)

    def _on_accept(self) -> None:
        pid = self._id_edit.text().strip()
        if not pid:
            QMessageBox.warning(self, "Missing ID", "Participant ID required.")
            return
        if pid in self._existing_ids:
            QMessageBox.warning(
                self, "Duplicate", f"Participant '{pid}' already exists."
            )
            return
        self.accept()

    def result_participant(self) -> tuple[str, dict]:
        pid = self._id_edit.text().strip()
        payload: dict = {
            "label": self._label_edit.text().strip(),
            "group": self._group_combo.currentData(),
            "sequence": self._sequence_combo.currentData(),
            "event_order": [],
            "manual_events": [],
        }
        # Drop None values to keep Streamlit-compat clean
        payload = {k: v for k, v in payload.items() if v not in (None, "")}
        # event_order / manual_events should stay as empty lists by default
        payload.setdefault("event_order", [])
        payload.setdefault("manual_events", [])
        return pid, payload


class ParticipantsTab(InspectorTab):
    """Editor for participants.yml (Streamlit-shared).

    Shows a sortable table (ID, label, group, sequence, # manual events)
    plus Add/Edit/Remove/Import-from-workspace actions.
    """

    TAB_LABEL = "Participants"

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(main_window, parent)
        self._participants: dict[str, dict] = self._load()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        self._info_label = QLabel(
            f"<b>Participants</b> — saved to "
            f"{self.format_config_path('config/participants.yml')} "
            f"(Streamlit-shared). Each entry can be linked to a group "
            f"and to an event sequence."
        )
        self._info_label.setWordWrap(True)
        self._info_label.setStyleSheet("color: #777;")
        outer.addWidget(self._info_label)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add participant…")
        self._add_btn.clicked.connect(self._on_add)
        self._edit_btn = QPushButton("Edit…")
        self._edit_btn.clicked.connect(self._on_edit)
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.clicked.connect(self._on_remove)
        self._import_btn = QPushButton("Import from workspace")
        self._import_btn.setToolTip(
            "Create participant entries for every currently-loaded dataset "
            "(ID = dataset filename stem). Existing entries are skipped."
        )
        self._import_btn.clicked.connect(self._on_import_workspace)
        for b in (self._add_btn, self._edit_btn, self._remove_btn, self._import_btn):
            btn_row.addWidget(b)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        self._table = QTableWidget(0, 5, self)
        self._table.setHorizontalHeaderLabels(
            ["ID", "Label", "Group", "Sequence", "# manual events"]
        )
        self._table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeToContents
        )
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setSortingEnabled(True)
        self._table.itemSelectionChanged.connect(self._refresh_buttons)
        outer.addWidget(self._table)

        self._refresh_table()
        self._refresh_buttons()

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    @property
    def participants(self) -> dict[str, dict]:
        return dict(self._participants)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _project_path(self):
        proj = getattr(self._main_window, "_project", None)
        return proj.project_path if proj is not None else None

    def _load(self) -> dict[str, dict]:
        from rrational.gui.persistence import load_participants as _lp

        return _lp(project_path=self._project_path()) or {}

    def _persist(self) -> None:
        from rrational.gui.persistence import save_participants as _sp

        _sp(self._participants, project_path=self._project_path())
        notify = getattr(self._main_window, "_on_participants_changed", None)
        if callable(notify):
            notify()

    def _available_groups(self) -> list[str]:
        from rrational.gui.persistence import load_groups as _lg

        return list((_lg(project_path=self._project_path()) or {}).keys())

    def _available_sequences(self) -> list[str]:
        """Inspector sequences live in inspector.persistence; not in the
        Streamlit event_sequences.yml (different concepts)."""
        from rrational.inspector.persistence import load_sequences

        return [s.name for s in load_sequences()]

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------
    def tab_label_state(self) -> str:
        n = len(self._participants)
        return f"({n})" if n else ""

    def on_workspace_changed(self) -> None:
        # Re-read in case the project changed
        self._participants = self._load()
        self._info_label.setText(
            f"<b>Participants</b> — saved to "
            f"{self.format_config_path('config/participants.yml')} "
            f"(Streamlit-shared). Each entry can be linked to a group "
            f"and to an event sequence."
        )
        self._refresh_table()
        self._refresh_buttons()

    def on_active_dataset_changed(self, _data: "InspectorData | None") -> None:
        # Participants are workspace-independent, no per-dataset refresh
        pass

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _refresh_table(self) -> None:
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        for pid, data in self._participants.items():
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(pid))
            self._table.setItem(row, 1, QTableWidgetItem(data.get("label", "") or ""))
            self._table.setItem(row, 2, QTableWidgetItem(data.get("group", "") or ""))
            self._table.setItem(
                row, 3, QTableWidgetItem(data.get("sequence", "") or "")
            )
            n_manual = len(data.get("manual_events", []) or [])
            self._table.setItem(row, 4, QTableWidgetItem(str(n_manual)))
        self._table.setSortingEnabled(True)

    def _refresh_buttons(self) -> None:
        has_selection = self._table.currentRow() >= 0
        self._edit_btn.setEnabled(has_selection)
        self._remove_btn.setEnabled(has_selection)
        self._import_btn.setEnabled(len(self._main_window._datasets) > 0)

    def _selected_id(self) -> str | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.text() if item is not None else None

    def _on_add(self) -> None:
        dlg = _ParticipantEditDialog(
            existing_ids=list(self._participants.keys()),
            available_groups=self._available_groups(),
            available_sequences=self._available_sequences(),
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        pid, payload = dlg.result_participant()
        self._participants[pid] = payload
        self._persist()
        self._refresh_table()

    def _on_edit(self) -> None:
        pid = self._selected_id()
        if pid is None:
            return
        dlg = _ParticipantEditDialog(
            existing_ids=list(self._participants.keys()),
            available_groups=self._available_groups(),
            available_sequences=self._available_sequences(),
            initial_id=pid,
            initial=self._participants[pid],
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        new_pid, payload = dlg.result_participant()
        # Preserve existing event_order + manual_events (the dialog
        # doesn't expose them — they're managed by Browse/Preprocessing)
        old = self._participants.get(pid, {})
        payload["event_order"] = old.get("event_order", [])
        payload["manual_events"] = old.get("manual_events", [])
        if new_pid != pid:
            del self._participants[pid]
        self._participants[new_pid] = payload
        self._persist()
        self._refresh_table()

    def _on_remove(self) -> None:
        pid = self._selected_id()
        if pid is None:
            return
        if (
            QMessageBox.question(
                self,
                "Remove participant",
                f"Delete participant '{pid}'? This cannot be undone.",
            )
            != QMessageBox.Yes
        ):
            return
        del self._participants[pid]
        self._persist()
        self._refresh_table()

    def _on_import_workspace(self) -> None:
        """Create one entry per loaded dataset whose stem is not already
        in participants. Skips conflicts silently."""
        from pathlib import Path as _Path

        # Honour the user's ID-pattern picker from the Data tab.
        try:
            from rrational.inspector.tabs.data_tab import extract_participant_id
        except ImportError:  # pragma: no cover - defensive
            extract_participant_id = None

        added = 0
        for ds in self._main_window._datasets:
            if extract_participant_id is not None:
                pid = extract_participant_id(_Path(ds.name))
            else:
                pid = _Path(ds.name).stem
            if pid in self._participants:
                continue
            self._participants[pid] = {
                "label": "",
                "event_order": [],
                "manual_events": [],
            }
            added += 1
        if added == 0:
            self._main_window.statusBar().showMessage(
                "No new participants — all workspace datasets already have entries.",
                3000,
            )
            return
        self._persist()
        self._refresh_table()
        self._main_window.statusBar().showMessage(
            f"Imported {added} participant(s) from the workspace.", 4000
        )
