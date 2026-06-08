"""Setup tab — events / sections / groups / sequences.

Four sub-panes mirror the Streamlit Setup tab: events / sections (per
dataset) plus groups / sequences (project-level).

All four panes update via ``on_active_dataset_changed`` — switching the
active dataset in BrowseTab reflects through the same notification
plumbing the rest of the inspector uses.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
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
from rrational.inspector.tabs.base import InspectorTab, format_config_path

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


class _EventDefinitionDialog(QDialog):
    """Modal editor for one event definition.

    Schema (Streamlit-compatible): ``{canonical_name: [synonym1, synonym2, regex_pattern, ...]}``
    Each line in the synonyms text-area becomes one entry. Lines starting
    with ``/`` (e.g. ``/^rest_pre/i``) are stored verbatim as Streamlit's
    regex convention; literal strings work too.
    """

    def __init__(
        self,
        existing_names: list[str],
        initial_name: str | None = None,
        initial_synonyms: list[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit event" if initial_name else "New event")
        self.setMinimumWidth(520)
        self._existing_names = [n for n in existing_names if n != (initial_name or "")]

        outer = QVBoxLayout(self)
        form = QFormLayout()
        self._name_edit = QLineEdit(initial_name or "")
        self._name_edit.setPlaceholderText("Canonical event name (e.g. rest_pre_start)")
        form.addRow("Canonical name *:", self._name_edit)
        outer.addLayout(form)

        help_label = QLabel(
            "Synonyms / regex (one per line). Streamlit format: literal "
            "string OR <code>/pattern/flags</code>."
        )
        help_label.setTextFormat(Qt.RichText)
        outer.addWidget(help_label)
        from qtpy.QtWidgets import QPlainTextEdit

        self._syn_edit = QPlainTextEdit()
        if initial_synonyms:
            self._syn_edit.setPlainText("\n".join(initial_synonyms))
        self._syn_edit.setPlaceholderText("Rest_Pre\nPre_Rest\n/^ruhe.vor/i")
        outer.addWidget(self._syn_edit)

        # Live regex-validation status — flips red on any malformed
        # /pattern/flags line so the user sees the problem before
        # hitting OK. Literal strings (no leading slash) are always OK.
        self._regex_status = QLabel("")
        self._regex_status.setTextFormat(Qt.RichText)
        self._regex_status.setWordWrap(True)
        outer.addWidget(self._regex_status)
        self._syn_edit.textChanged.connect(self._validate_synonyms)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._ok_btn = bb.button(QDialogButtonBox.Ok)
        bb.accepted.connect(self._on_accept)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)

        # Run once so an empty / pre-filled textarea shows the right state.
        self._validate_synonyms()

    @staticmethod
    def _parse_regex_line(line: str) -> tuple[str, str] | None:
        """Return ``(pattern, flags)`` for a ``/pattern/flags`` line, else None.

        A literal synonym (no enclosing slashes) is not a regex and
        returns ``None``. Lines like ``/foo/`` or ``/foo/i`` are.
        """
        if not line.startswith("/"):
            return None
        end = line.rfind("/")
        if end <= 0:  # only one slash, malformed-but-treat-as-literal
            return None
        return line[1:end], line[end + 1 :]

    def _validate_synonyms(self) -> None:
        """Compile every /pattern/flags line and surface the first error.

        Disables OK while any regex line is broken so the user can't
        save a definition the loader will silently skip.
        """
        import re

        lines = self._syn_edit.toPlainText().splitlines()
        errors: list[tuple[int, str, str]] = []  # (line_no, raw, error)
        n_regex = 0
        n_literal = 0
        for i, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line:
                continue
            parsed = self._parse_regex_line(line)
            if parsed is None:
                n_literal += 1
                continue
            pattern, flags_str = parsed
            qt_flags = 0
            for ch in flags_str:
                if ch == "i":
                    qt_flags |= re.IGNORECASE
                elif ch == "m":
                    qt_flags |= re.MULTILINE
                elif ch == "s":
                    qt_flags |= re.DOTALL
                # Other flags (x, a, u) ignored — Streamlit only honours i/m/s.
            try:
                re.compile(pattern, qt_flags)
                n_regex += 1
            except re.error as exc:
                errors.append((i, line, str(exc)))

        if errors:
            line_no, raw, err = errors[0]
            self._regex_status.setText(
                f"<span style='color:#d97862;'>Line {line_no}: "
                f"invalid regex <code>{raw}</code> &mdash; {err}</span>"
            )
            self._ok_btn.setEnabled(False)
        elif n_regex + n_literal == 0:
            self._regex_status.setText(
                "<span style='color:#a8adb5;'>No synonyms yet "
                "(the canonical name will be the only match).</span>"
            )
            self._ok_btn.setEnabled(True)
        else:
            self._regex_status.setText(
                f"<span style='color:#5ab896;'>OK &mdash; "
                f"{n_regex} regex, {n_literal} literal "
                f"{'string' if n_literal == 1 else 'strings'}.</span>"
            )
            self._ok_btn.setEnabled(True)

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Canonical event name required.")
            return
        if name in self._existing_names:
            QMessageBox.warning(self, "Duplicate", f"Event '{name}' already exists.")
            return
        self.accept()

    def result_event(self) -> tuple[str, list[str]]:
        name = self._name_edit.text().strip()
        lines = [
            line.strip()
            for line in self._syn_edit.toPlainText().splitlines()
            if line.strip()
        ]
        return name, lines


class _EventsPane(QWidget):
    """Two stacked sections:

    1. **Defined events** (top) — project-/global-config editor backed by
       ``gui.persistence.save_events``/``load_events``. Each event is a
       canonical name plus a list of synonyms/regex patterns that match
       against raw labels in loaded recordings.
    2. **Found in active dataset** (bottom) — read-only list of the raw
       EventMeta entries from whatever the user is currently looking at,
       so they can see which definitions are actually firing.
    """

    def __init__(self, main_window, parent=None) -> None:
        from rrational.inspector.help_widgets import HelpExpander

        super().__init__(parent)
        self._main_window = main_window
        self._events: dict[str, list[str]] = self._load()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        outer.addWidget(
            HelpExpander(
                "Events",
                (
                    "<p>Events are time-point markers in your recordings "
                    "(e.g. <i>rest_start</i>, <i>music_end</i>). Sections "
                    "below are defined as the range between two events, so "
                    "events are the foundation of every analysis.</p>"
                    "<p>Use <b>Add event</b> to register a canonical name "
                    "plus optional <b>synonyms</b> — the loader fuzzy-matches "
                    "synonym strings against each recording's annotation "
                    "labels, so <i>rest_start</i> can absorb "
                    "<i>Ruhe Start</i>, <i>rest starts</i>, etc.</p>"
                ),
            )
        )

        self._info_label = QLabel(
            f"<b>Defined events</b> (saved to "
            f"{format_config_path('config/events.yml')}, Streamlit-shared)"
        )
        self._info_label.setStyleSheet("color: #777;")
        outer.addWidget(self._info_label)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add event…")
        self._add_btn.setToolTip("Register a new canonical event name with synonyms.")
        self._add_btn.clicked.connect(self._on_add)
        self._edit_btn = QPushButton("Edit…")
        self._edit_btn.setToolTip("Edit the selected event definition.")
        self._edit_btn.clicked.connect(self._on_edit)
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setToolTip("Remove the selected event definition.")
        self._remove_btn.clicked.connect(self._on_remove)
        for b in (self._add_btn, self._edit_btn, self._remove_btn):
            btn_row.addWidget(b)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        self._defs_table = _ReadOnlyTable(
            ["Canonical name", "# synonyms", "Synonyms (first 3)"]
        )
        self._defs_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._defs_table.itemSelectionChanged.connect(self._refresh_buttons)
        outer.addWidget(self._defs_table, 1)

        outer.addSpacing(8)
        outer.addWidget(QLabel("<b>Found in active dataset</b> (read-only)"))
        self._table = _ReadOnlyTable(["Label", "Time", "Epoch (s)"])
        outer.addWidget(self._table, 1)

        self._refresh_defs_table()
        self._refresh_buttons()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _project_path(self):
        proj = getattr(self._main_window, "_project", None)
        return proj.project_path if proj is not None else None

    def _load(self) -> dict[str, list[str]]:
        from rrational.gui.persistence import load_events as _le

        return _le(project_path=self._project_path()) or {}

    def _persist(self) -> None:
        from rrational.gui.persistence import save_events as _se

        _se(self._events, project_path=self._project_path())
        notify = getattr(self._main_window, "_on_events_changed", None)
        if callable(notify):
            notify()

    # ------------------------------------------------------------------
    # API used by SetupTab + tests
    # ------------------------------------------------------------------
    @property
    def events(self) -> dict[str, list[str]]:
        return dict(self._events)

    def refresh_from_workspace(self) -> None:
        """Re-read from disk; called after project open/close."""
        self._events = self._load()
        self._info_label.setText(
            f"<b>Defined events</b> (saved to "
            f"{format_config_path('config/events.yml')}, Streamlit-shared)"
        )
        self._refresh_defs_table()
        self._refresh_buttons()

    def update_from(self, data: "InspectorData | None") -> None:
        """Refresh the bottom read-only table from the active dataset."""
        self._table.setRowCount(0)
        if data is None:
            return
        for ev in data.events:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(ev.label))
            self._table.setItem(row, 1, QTableWidgetItem(_fmt_time(ev.t)))
            self._table.setItem(row, 2, QTableWidgetItem(f"{ev.t:.1f}"))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _refresh_defs_table(self) -> None:
        self._defs_table.setRowCount(0)
        for name, synonyms in self._events.items():
            row = self._defs_table.rowCount()
            self._defs_table.insertRow(row)
            self._defs_table.setItem(row, 0, QTableWidgetItem(name))
            self._defs_table.setItem(row, 1, QTableWidgetItem(str(len(synonyms))))
            preview = ", ".join((synonyms or [])[:3])
            if len(synonyms or []) > 3:
                preview += ", …"
            self._defs_table.setItem(row, 2, QTableWidgetItem(preview))

    def _refresh_buttons(self) -> None:
        has_selection = self._defs_table.currentRow() >= 0
        self._edit_btn.setEnabled(has_selection)
        self._remove_btn.setEnabled(has_selection)

    def _selected_name(self) -> str | None:
        row = self._defs_table.currentRow()
        if row < 0:
            return None
        item = self._defs_table.item(row, 0)
        return item.text() if item is not None else None

    def _on_add(self) -> None:
        dlg = _EventDefinitionDialog(
            existing_names=list(self._events.keys()), parent=self
        )
        if dlg.exec() != QDialog.Accepted:
            return
        name, syns = dlg.result_event()
        self._events[name] = syns
        self._persist()
        self._refresh_defs_table()

    def _on_edit(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        dlg = _EventDefinitionDialog(
            existing_names=list(self._events.keys()),
            initial_name=name,
            initial_synonyms=list(self._events.get(name, [])),
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        new_name, syns = dlg.result_event()
        if new_name != name:
            del self._events[name]
        self._events[new_name] = syns
        self._persist()
        self._refresh_defs_table()

    def _on_remove(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        if (
            QMessageBox.question(
                self,
                "Remove event",
                f"Delete event '{name}'? This cannot be undone.",
            )
            != QMessageBox.Yes
        ):
            return
        del self._events[name]
        self._persist()
        self._refresh_defs_table()


class _SectionDefinitionDialog(QDialog):
    """Modal editor for one section definition.

    Streamlit-compatible schema::

        section_name:
          label: str
          description: str
          start_events: list[str]   # picked from defined events
          end_events: list[str]
    """

    def __init__(
        self,
        available_events: list[str],
        existing_names: list[str],
        initial_name: str | None = None,
        initial: dict | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit section" if initial_name else "New section")
        self.setMinimumWidth(540)
        self._existing_names = [n for n in existing_names if n != (initial_name or "")]

        outer = QVBoxLayout(self)
        form = QFormLayout()
        self._name_edit = QLineEdit(initial_name or "")
        self._name_edit.setPlaceholderText("e.g. rest_pre")
        form.addRow("Section name *:", self._name_edit)
        self._label_edit = QLineEdit(
            (initial or {}).get("label", "") if initial else ""
        )
        form.addRow("Label:", self._label_edit)
        self._desc_edit = QLineEdit(
            (initial or {}).get("description", "") if initial else ""
        )
        form.addRow("Description:", self._desc_edit)
        outer.addLayout(form)

        # Start events
        outer.addWidget(QLabel("<b>Start events</b> (any-of)"))
        self._start_list = QListWidget()
        self._start_list.setSelectionMode(QAbstractItemView.MultiSelection)
        for ev in available_events:
            item = QListWidgetItem(ev)
            self._start_list.addItem(item)
        initial_starts = set((initial or {}).get("start_events", []) if initial else [])
        for i in range(self._start_list.count()):
            it = self._start_list.item(i)
            if it.text() in initial_starts:
                it.setSelected(True)
        outer.addWidget(self._start_list)

        # End events
        outer.addWidget(QLabel("<b>End events</b> (any-of)"))
        self._end_list = QListWidget()
        self._end_list.setSelectionMode(QAbstractItemView.MultiSelection)
        for ev in available_events:
            self._end_list.addItem(QListWidgetItem(ev))
        initial_ends = set((initial or {}).get("end_events", []) if initial else [])
        for i in range(self._end_list.count()):
            it = self._end_list.item(i)
            if it.text() in initial_ends:
                it.setSelected(True)
        outer.addWidget(self._end_list)

        if not available_events:
            note = QLabel(
                "<i>No events defined yet. Add events first (top section of this pane), "
                "then return to define which events bound this section.</i>"
            )
            note.setWordWrap(True)
            note.setStyleSheet("color: #888;")
            outer.addWidget(note)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._on_accept)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Section name required.")
            return
        if name in self._existing_names:
            QMessageBox.warning(self, "Duplicate", f"Section '{name}' already exists.")
            return
        self.accept()

    def result_section(self) -> tuple[str, dict]:
        name = self._name_edit.text().strip()
        payload = {
            "label": self._label_edit.text().strip() or name,
            "description": self._desc_edit.text().strip(),
            "start_events": [
                self._start_list.item(i).text()
                for i in range(self._start_list.count())
                if self._start_list.item(i).isSelected()
            ],
            "end_events": [
                self._end_list.item(i).text()
                for i in range(self._end_list.count())
                if self._end_list.item(i).isSelected()
            ],
        }
        return name, payload


class _SectionsPane(QWidget):
    """Two stacked sections (parallel to _EventsPane):

    1. **Defined sections** (top) — editor backed by
       ``gui.persistence.save_sections``/``load_sections``. Each
       section has a label, description, and lists of start/end events
       (drawn from defined events in the Events pane).
    2. **Found in active dataset** (bottom) — read-only.
    """

    def __init__(self, main_window, parent=None) -> None:
        from rrational.inspector.help_widgets import HelpExpander

        super().__init__(parent)
        self._main_window = main_window
        self._sections: dict[str, dict] = self._load()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        outer.addWidget(
            HelpExpander(
                "Sections",
                (
                    "<p>Sections are time ranges between two events. The HRV "
                    "analysis processes each section as one unit.</p>"
                    "<p>Pick a <b>Start event</b> and <b>End event</b> (defined "
                    "in the Events tab), give the section a <b>Name</b> "
                    "(e.g. <i>baseline_rest</i>) and a human label. Keep the "
                    "name machine-friendly (no spaces) — it's how downstream "
                    "tools key into the data.</p>"
                    "<p><b>Tip:</b> ensure your sections have at least ~100 "
                    "beats for time-domain metrics and ~300 beats for "
                    "frequency-domain metrics (Quigley 2024).</p>"
                ),
            )
        )

        self._info_label = QLabel(
            f"<b>Defined sections</b> (saved to "
            f"{format_config_path('config/sections.yml')}, Streamlit-shared)"
        )
        self._info_label.setStyleSheet("color: #777;")
        outer.addWidget(self._info_label)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add section…")
        self._add_btn.setToolTip("Define a new section by start/end events.")
        self._add_btn.clicked.connect(self._on_add)
        self._edit_btn = QPushButton("Edit…")
        self._edit_btn.setToolTip("Edit the selected section definition.")
        self._edit_btn.clicked.connect(self._on_edit)
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setToolTip("Remove the selected section definition.")
        self._remove_btn.clicked.connect(self._on_remove)
        for b in (self._add_btn, self._edit_btn, self._remove_btn):
            btn_row.addWidget(b)
        btn_row.addStretch()
        outer.addLayout(btn_row)

        self._defs_table = _ReadOnlyTable(
            ["Name", "Label", "Start events", "End events", "Description"]
        )
        self._defs_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._defs_table.itemSelectionChanged.connect(self._refresh_buttons)
        outer.addWidget(self._defs_table, 1)

        outer.addSpacing(8)
        outer.addWidget(QLabel("<b>Found in active dataset</b> (read-only)"))
        self._table = _ReadOnlyTable(["Name", "Start", "End", "Duration", "Beats"])
        outer.addWidget(self._table, 1)

        self._refresh_defs_table()
        self._refresh_buttons()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _project_path(self):
        proj = getattr(self._main_window, "_project", None)
        return proj.project_path if proj is not None else None

    def _load(self) -> dict[str, dict]:
        from rrational.gui.persistence import load_sections as _ls

        return _ls(project_path=self._project_path()) or {}

    def _persist(self) -> None:
        from rrational.gui.persistence import save_sections as _ss

        _ss(self._sections, project_path=self._project_path())
        notify = getattr(self._main_window, "_on_sections_changed", None)
        if callable(notify):
            notify()

    def _available_events(self) -> list[str]:
        """Prefer the live in-memory event list from the sibling EventsPane,
        so unsaved edits propagate; fall back to disk read."""
        setup_tab = getattr(self._main_window, "_setup_tab", None)
        events_pane = getattr(setup_tab, "_events_pane", None) if setup_tab else None
        if events_pane is not None and hasattr(events_pane, "events"):
            return list(events_pane.events.keys())
        from rrational.gui.persistence import load_events as _le

        return list((_le(project_path=self._project_path()) or {}).keys())

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    @property
    def sections(self) -> dict[str, dict]:
        return dict(self._sections)

    def refresh_from_workspace(self) -> None:
        self._sections = self._load()
        self._info_label.setText(
            f"<b>Defined sections</b> (saved to "
            f"{format_config_path('config/sections.yml')}, Streamlit-shared)"
        )
        self._refresh_defs_table()
        self._refresh_buttons()

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

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _refresh_defs_table(self) -> None:
        self._defs_table.setRowCount(0)
        for name, data in self._sections.items():
            row = self._defs_table.rowCount()
            self._defs_table.insertRow(row)
            self._defs_table.setItem(row, 0, QTableWidgetItem(name))
            self._defs_table.setItem(row, 1, QTableWidgetItem(data.get("label", name)))
            self._defs_table.setItem(
                row, 2, QTableWidgetItem(", ".join(data.get("start_events") or []))
            )
            self._defs_table.setItem(
                row, 3, QTableWidgetItem(", ".join(data.get("end_events") or []))
            )
            self._defs_table.setItem(
                row, 4, QTableWidgetItem(data.get("description", ""))
            )

    def _refresh_buttons(self) -> None:
        has_selection = self._defs_table.currentRow() >= 0
        self._edit_btn.setEnabled(has_selection)
        self._remove_btn.setEnabled(has_selection)

    def _selected_name(self) -> str | None:
        row = self._defs_table.currentRow()
        if row < 0:
            return None
        item = self._defs_table.item(row, 0)
        return item.text() if item is not None else None

    def _on_add(self) -> None:
        dlg = _SectionDefinitionDialog(
            available_events=self._available_events(),
            existing_names=list(self._sections.keys()),
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        name, payload = dlg.result_section()
        self._sections[name] = payload
        self._persist()
        self._refresh_defs_table()

    def _on_edit(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        dlg = _SectionDefinitionDialog(
            available_events=self._available_events(),
            existing_names=list(self._sections.keys()),
            initial_name=name,
            initial=self._sections[name],
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        new_name, payload = dlg.result_section()
        if new_name != name:
            del self._sections[name]
        self._sections[new_name] = payload
        self._persist()
        self._refresh_defs_table()

    def _on_remove(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        if (
            QMessageBox.question(
                self,
                "Remove section",
                f"Delete section '{name}'? This cannot be undone.",
            )
            != QMessageBox.Yes
        ):
            return
        del self._sections[name]
        self._persist()
        self._refresh_defs_table()


class _GroupEditDialog(QDialog):
    """Modal editor for a single Group definition.

    Schema (Streamlit-compatible, additive):
        name           # YAML key
        label          # display name
        description    # free text (inspector-specific addition)
        members        # list[str] of dataset names (inspector-specific addition)
        expected_events: {}   # kept empty here, owned by Streamlit
        selected_sections: []  # kept empty here, owned by Streamlit
    """

    def __init__(
        self,
        available_datasets: list[str],
        existing_names: list[str],
        initial: dict | None = None,
        initial_name: str | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit group" if initial else "New group")
        self.setMinimumWidth(540)
        self._existing_names = [n for n in existing_names if n != (initial_name or "")]

        outer = QVBoxLayout(self)

        form = QFormLayout()
        self._name_edit = QLineEdit(initial_name or "")
        self._name_edit.setPlaceholderText("e.g. Music, Control, Treatment_A")
        form.addRow("Name *:", self._name_edit)
        self._label_edit = QLineEdit(
            (initial or {}).get("label", "") if initial else ""
        )
        self._label_edit.setPlaceholderText("Display name (defaults to Name)")
        form.addRow("Label:", self._label_edit)
        self._description_edit = QLineEdit(
            (initial or {}).get("description", "") if initial else ""
        )
        form.addRow("Description:", self._description_edit)
        outer.addLayout(form)

        # Member checkboxes
        members_box = QGroupBox("Members (datasets currently in workspace)")
        members_layout = QVBoxLayout(members_box)
        self._member_checks: dict[str, QCheckBox] = {}
        initial_members = set((initial or {}).get("members", []) if initial else [])
        for ds_name in available_datasets:
            cb = QCheckBox(ds_name)
            cb.setChecked(ds_name in initial_members)
            members_layout.addWidget(cb)
            self._member_checks[ds_name] = cb
        if not available_datasets:
            note = QLabel(
                "<i>No datasets loaded. Members can be assigned later by re-editing "
                "this group with files open.</i>"
            )
            note.setWordWrap(True)
            note.setStyleSheet("color: #888;")
            members_layout.addWidget(note)
        outer.addWidget(members_box)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._on_accept)
        bb.rejected.connect(self.reject)
        outer.addWidget(bb)

    def _on_accept(self) -> None:
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Group name is required.")
            return
        if name in self._existing_names:
            QMessageBox.warning(
                self, "Duplicate name", f"A group named '{name}' already exists."
            )
            return
        self.accept()

    def result_group(self) -> tuple[str, dict]:
        name = self._name_edit.text().strip()
        members = [n for n, cb in self._member_checks.items() if cb.isChecked()]
        payload = {
            "label": self._label_edit.text().strip() or name,
            "description": self._description_edit.text().strip(),
            "members": members,
            "expected_events": {},
            "selected_sections": [],
        }
        return name, payload


class _GroupsPane(QWidget):
    """Editor for Group definitions, backed by ``gui.persistence.save_groups``.

    File location resolves to ``{project}/config/groups.yml`` when a
    project is open, else ``~/.rrational/groups.yml`` (Streamlit-shared
    global location).
    """

    def __init__(self, main_window, parent=None) -> None:
        from rrational.inspector.help_widgets import HelpExpander

        super().__init__(parent)
        self._main_window = main_window
        self._groups: dict[str, dict] = self._load()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(
            HelpExpander(
                "Groups and playlists",
                (
                    "<p>A group is a collection of participants that share a "
                    "condition (e.g. <i>control</i> vs <i>treatment</i>).</p>"
                    "<p>Use <b>Add group</b> to pick a name and assign "
                    "members. The Analysis tab's Group-Comparison mode then "
                    "runs Friedman / RM-ANOVA + Holm post-hoc tests across "
                    "the named groups.</p>"
                    "<p>Members can also be edited later under the "
                    "<b>Participants</b> tab — the assignments are stored in "
                    "<code>config/participants.yml</code> and stay in sync.</p>"
                ),
            )
        )

        self._info_label = QLabel(
            f"<i>Group definitions are saved to "
            f"{format_config_path('config/groups.yml')}. "
            f"Shared with the Streamlit app.</i>"
        )
        self._info_label.setWordWrap(True)
        self._info_label.setStyleSheet("color: #777;")
        layout.addWidget(self._info_label)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add group…")
        self._add_btn.setToolTip("Create a new group and assign members.")
        self._add_btn.clicked.connect(self._on_add)
        self._edit_btn = QPushButton("Edit…")
        self._edit_btn.setToolTip("Edit the selected group's name or members.")
        self._edit_btn.clicked.connect(self._on_edit)
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setToolTip("Delete the selected group definition.")
        self._remove_btn.clicked.connect(self._on_remove)
        for b in (self._add_btn, self._edit_btn, self._remove_btn):
            btn_row.addWidget(b)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._table = _ReadOnlyTable(["Name", "Label", "Members", "Description"])
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.itemSelectionChanged.connect(self._refresh_buttons)
        layout.addWidget(self._table, 1)

        self._refresh_table()
        self._refresh_buttons()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def groups(self) -> dict[str, dict]:
        return dict(self._groups)

    def refresh_from_workspace(self) -> None:
        """Re-read from disk and rebuild — called on workspace/project change."""
        self._groups = self._load()
        self._info_label.setText(
            f"<i>Group definitions are saved to "
            f"{format_config_path('config/groups.yml')}. "
            f"Shared with the Streamlit app.</i>"
        )
        self._refresh_table()
        self._refresh_buttons()

    # ------------------------------------------------------------------
    # Persistence — direct reuse of gui.persistence (no inspector wrapper)
    # ------------------------------------------------------------------
    def _project_path(self):
        proj = getattr(self._main_window, "_project", None)
        return proj.project_path if proj is not None else None

    def _load(self) -> dict[str, dict]:
        from rrational.gui.persistence import load_groups as _lg

        return _lg(project_path=self._project_path()) or {}

    def _persist(self) -> None:
        from rrational.gui.persistence import save_groups as _sg

        _sg(self._groups, project_path=self._project_path())
        # Notify the Analysis tab's Group-Comparison pane so its dropdown
        # picks up the new definitions without manual refresh.
        notify = getattr(self._main_window, "_on_groups_changed", None)
        if callable(notify):
            notify()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _refresh_table(self) -> None:
        self._table.setRowCount(0)
        for name, data in self._groups.items():
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(name))
            self._table.setItem(row, 1, QTableWidgetItem(data.get("label", name)))
            members = data.get("members", []) or []
            self._table.setItem(row, 2, QTableWidgetItem(str(len(members))))
            self._table.setItem(row, 3, QTableWidgetItem(data.get("description", "")))

    def _refresh_buttons(self) -> None:
        has_selection = self._table.currentRow() >= 0
        self._edit_btn.setEnabled(has_selection)
        self._remove_btn.setEnabled(has_selection)

    def _selected_name(self) -> str | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.text() if item is not None else None

    def _workspace_dataset_names(self) -> list[str]:
        return [ds.name for ds in self._main_window._datasets]

    def _on_add(self) -> None:
        dlg = _GroupEditDialog(
            available_datasets=self._workspace_dataset_names(),
            existing_names=list(self._groups.keys()),
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        name, payload = dlg.result_group()
        self._groups[name] = payload
        self._persist()
        self._refresh_table()

    def _on_edit(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        dlg = _GroupEditDialog(
            available_datasets=self._workspace_dataset_names(),
            existing_names=list(self._groups.keys()),
            initial=self._groups[name],
            initial_name=name,
            parent=self,
        )
        if dlg.exec() != QDialog.Accepted:
            return
        new_name, payload = dlg.result_group()
        # Rename if needed
        if new_name != name:
            del self._groups[name]
        self._groups[new_name] = payload
        self._persist()
        self._refresh_table()

    def _on_remove(self) -> None:
        name = self._selected_name()
        if name is None:
            return
        if (
            QMessageBox.question(
                self,
                "Remove group",
                f"Delete group '{name}'? This cannot be undone.",
            )
            != QMessageBox.Yes
        ):
            return
        del self._groups[name]
        self._persist()
        self._refresh_table()


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
        from rrational.inspector.help_widgets import HelpExpander

        super().__init__(parent)
        self._main_window = main_window
        # Loaded once on construction; mutations save back to disk.
        self._sequences: list[Sequence] = load_sequences()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        outer.addWidget(
            HelpExpander(
                "Sequences",
                (
                    "<p>A sequence is an ordered list of section names "
                    "(e.g. <i>baseline &rarr; music &rarr; recovery</i>) used "
                    "by the Analysis tab's <b>Sequence Comparison</b> mode "
                    "for repeated-measures analysis.</p>"
                    "<p>Use <b>Add sequence</b> to pick a name and arrange "
                    "the sections in order. A sequence needs at least 2 "
                    "sections to be statistically meaningful.</p>"
                ),
            )
        )

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
        self._add_btn.setToolTip("Create a new ordered list of section names.")
        self._add_btn.clicked.connect(self._on_add)
        self._edit_btn = QPushButton("Edit…")
        self._edit_btn.setToolTip("Edit the selected sequence's name or order.")
        self._edit_btn.clicked.connect(self._on_edit)
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setToolTip("Delete the selected sequence definition.")
        self._remove_btn.clicked.connect(self._on_remove)
        self._duplicate_btn = QPushButton("Duplicate")
        self._duplicate_btn.setToolTip("Make a copy of the selected sequence.")
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
        outer.addWidget(self._table, 1)

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


class _ProtocolPane(QWidget):
    """Editor for protocol.yml — study-wide timing/threshold parameters.

    Streamlit-compatible schema::

        expected_duration_min: float    # Total session duration
        section_length_min: float       # Duration per condition section
        pre_pause_sections: int         # # sections before pause
        post_pause_sections: int        # # sections after pause
        min_section_duration_min: float
        min_section_beats: int
        mismatch_strategy: str          # 'flag_only' | 'reject' | ...

    All fields are project-wide (one protocol per project / global).
    """

    # Defaults match the Streamlit app defaults
    _DEFAULTS = {
        "expected_duration_min": 90.0,
        "section_length_min": 5.0,
        "pre_pause_sections": 9,
        "post_pause_sections": 9,
        "min_section_duration_min": 4.0,
        "min_section_beats": 100,
        "mismatch_strategy": "flag_only",
    }
    _STRATEGY_CHOICES = ["flag_only", "reject", "auto_fix"]

    def __init__(self, main_window, parent=None) -> None:
        from rrational.inspector.help_widgets import HelpExpander

        super().__init__(parent)
        self._main_window = main_window
        self._protocol: dict = self._load()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        outer.addWidget(
            HelpExpander(
                "Protocol",
                (
                    "<p>The protocol captures study-wide timing assumptions "
                    "used to flag recordings that drift from the expected "
                    "structure.</p>"
                    "<ul>"
                    "<li><b>Expected total duration / section length</b> "
                    "— used for duration sanity checks.</li>"
                    "<li><b>Sections before/after pause</b> — the canonical "
                    "session shape.</li>"
                    "<li><b>Min duration / min beats</b> — sections below "
                    "these limits are excluded from frequency-domain HRV "
                    "(Quigley 2024 recommends 300+ beats / 5+ min).</li>"
                    "<li><b>Mismatch strategy</b> — what to do when "
                    "recordings don't match the expected protocol: flag "
                    "only, reject outright, or attempt auto-fix.</li>"
                    "</ul>"
                ),
            )
        )

        self._info_label = QLabel(
            f"<b>Protocol</b> — study-wide timing + threshold parameters "
            f"(saved to {format_config_path('config/protocol.yml')}, "
            f"Streamlit-shared)."
        )
        self._info_label.setWordWrap(True)
        self._info_label.setStyleSheet("color: #777;")
        outer.addWidget(self._info_label)

        from qtpy.QtWidgets import QDoubleSpinBox, QSpinBox

        form_box = QGroupBox("Session timing + section thresholds")
        form = QFormLayout(form_box)

        self._expected_dur = QDoubleSpinBox()
        self._expected_dur.setRange(0.1, 1000.0)
        self._expected_dur.setDecimals(2)
        self._expected_dur.setSuffix(" min")
        self._expected_dur.setToolTip("Total expected duration of one session.")
        form.addRow("Expected total duration:", self._expected_dur)

        self._section_length = QDoubleSpinBox()
        self._section_length.setRange(0.1, 100.0)
        self._section_length.setDecimals(2)
        self._section_length.setSuffix(" min")
        self._section_length.setToolTip("Expected duration per condition section.")
        form.addRow("Section length:", self._section_length)

        self._pre_pause = QSpinBox()
        self._pre_pause.setRange(0, 200)
        self._pre_pause.setToolTip("Number of sections expected before the pause.")
        form.addRow("Sections before pause:", self._pre_pause)

        self._post_pause = QSpinBox()
        self._post_pause.setRange(0, 200)
        self._post_pause.setToolTip("Number of sections expected after the pause.")
        form.addRow("Sections after pause:", self._post_pause)

        self._min_dur = QDoubleSpinBox()
        self._min_dur.setRange(0.1, 100.0)
        self._min_dur.setDecimals(2)
        self._min_dur.setSuffix(" min")
        self._min_dur.setToolTip("Sections shorter than this are excluded from HRV.")
        form.addRow("Min section duration:", self._min_dur)

        self._min_beats = QSpinBox()
        self._min_beats.setRange(1, 100_000)
        self._min_beats.setToolTip("Sections with fewer beats are excluded from HRV.")
        form.addRow("Min section beats:", self._min_beats)

        self._mismatch = QComboBox()
        for choice in self._STRATEGY_CHOICES:
            self._mismatch.addItem(choice)
        self._mismatch.setToolTip("How to handle recordings that violate the protocol.")
        form.addRow("Mismatch strategy:", self._mismatch)

        outer.addWidget(form_box)

        btn_row = QHBoxLayout()
        self._save_btn = QPushButton("Save protocol")
        self._save_btn.setToolTip("Persist the protocol values to disk.")
        self._save_btn.clicked.connect(self._on_save)
        self._reset_btn = QPushButton("Reset to defaults")
        self._reset_btn.setToolTip("Restore all fields to their built-in defaults.")
        self._reset_btn.clicked.connect(self._on_reset)
        btn_row.addWidget(self._save_btn)
        btn_row.addWidget(self._reset_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)
        outer.addStretch()

        self._apply_to_widgets(self._protocol)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _project_path(self):
        proj = getattr(self._main_window, "_project", None)
        return proj.project_path if proj is not None else None

    def _load(self) -> dict:
        from rrational.gui.persistence import load_protocol as _lp

        loaded = _lp(project_path=self._project_path()) or {}
        # Merge defaults so every field has a value
        merged = dict(self._DEFAULTS)
        merged.update(loaded)
        return merged

    def _persist(self) -> None:
        from rrational.gui.persistence import save_protocol as _sp

        _sp(self._protocol, project_path=self._project_path())

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    @property
    def protocol(self) -> dict:
        return dict(self._protocol)

    def refresh_from_workspace(self) -> None:
        """Re-read protocol.yml after a project open/close."""
        self._protocol = self._load()
        self._info_label.setText(
            f"<b>Protocol</b> — study-wide timing + threshold parameters "
            f"(saved to {format_config_path('config/protocol.yml')}, "
            f"Streamlit-shared)."
        )
        self._apply_to_widgets(self._protocol)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _apply_to_widgets(self, data: dict) -> None:
        self._expected_dur.setValue(float(data.get("expected_duration_min", 90.0)))
        self._section_length.setValue(float(data.get("section_length_min", 5.0)))
        self._pre_pause.setValue(int(data.get("pre_pause_sections", 9)))
        self._post_pause.setValue(int(data.get("post_pause_sections", 9)))
        self._min_dur.setValue(float(data.get("min_section_duration_min", 4.0)))
        self._min_beats.setValue(int(data.get("min_section_beats", 100)))
        strategy = str(data.get("mismatch_strategy", "flag_only"))
        idx = self._mismatch.findText(strategy)
        if idx >= 0:
            self._mismatch.setCurrentIndex(idx)

    def _collect_from_widgets(self) -> dict:
        return {
            "expected_duration_min": float(self._expected_dur.value()),
            "section_length_min": float(self._section_length.value()),
            "pre_pause_sections": int(self._pre_pause.value()),
            "post_pause_sections": int(self._post_pause.value()),
            "min_section_duration_min": float(self._min_dur.value()),
            "min_section_beats": int(self._min_beats.value()),
            "mismatch_strategy": str(self._mismatch.currentText()),
        }

    def _on_save(self) -> None:
        self._protocol = self._collect_from_widgets()
        self._persist()
        self._main_window.statusBar().showMessage(
            "Protocol saved to protocol.yml", 3000
        )

    def _on_reset(self) -> None:
        self._protocol = dict(self._DEFAULTS)
        self._apply_to_widgets(self._protocol)
        self._persist()
        self._main_window.statusBar().showMessage(
            "Protocol reset to defaults + saved", 3000
        )


class SetupTab(InspectorTab):
    """Inspector Setup tab — sub-tabs for events / sections / groups / sequences / protocol."""

    TAB_LABEL = "Setup"

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(main_window, parent)

        self._subtabs = QTabWidget(self)
        self._subtabs.setDocumentMode(True)

        self._events_pane = _EventsPane(main_window, self)
        self._sections_pane = _SectionsPane(main_window, self)
        self._groups_pane = _GroupsPane(main_window, self)
        self._sequences_pane = _SequencesPane(main_window, self)
        self._protocol_pane = _ProtocolPane(main_window, self)

        self._subtabs.addTab(self._events_pane, "Events")
        self._subtabs.addTab(self._sections_pane, "Sections")
        self._subtabs.addTab(self._groups_pane, "Groups")
        self._subtabs.addTab(self._sequences_pane, "Sequences")
        self._subtabs.addTab(self._protocol_pane, "Protocol")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._subtabs, 1)

        # Codebook export action.
        action_row = QHBoxLayout()
        self._export_codebook_btn = QPushButton("Export codebook...")
        self._export_codebook_btn.setToolTip(
            "Write a Markdown codebook listing every defined event, section, "
            "group and sequence. Useful as a study-protocol appendix."
        )
        self._export_codebook_btn.clicked.connect(self._on_export_codebook)
        action_row.addWidget(self._export_codebook_btn)
        action_row.addStretch()
        layout.addLayout(action_row)

    # ------------------------------------------------------------------
    # Tab-label state badge — groups + sequences counts
    # ------------------------------------------------------------------
    def tab_label_state(self) -> str:
        n_groups = len(self._groups_pane.groups)
        n_seqs = len(self._sequences_pane.sequences)
        parts = []
        if n_groups:
            parts.append(f"{n_groups} group{'s' if n_groups != 1 else ''}")
        if n_seqs:
            parts.append(f"{n_seqs} seq{'s' if n_seqs != 1 else ''}")
        if not parts:
            return ""
        return "(" + ", ".join(parts) + ")"

    # ------------------------------------------------------------------
    # Notification hooks
    # ------------------------------------------------------------------
    def on_workspace_changed(self) -> None:
        self._events_pane.refresh_from_workspace()
        self._sections_pane.refresh_from_workspace()
        self._groups_pane.refresh_from_workspace()
        self._sequences_pane.refresh_workspace()
        self._protocol_pane.refresh_from_workspace()

    def on_active_dataset_changed(self, data: "InspectorData | None") -> None:
        self._events_pane.update_from(data)
        self._sections_pane.update_from(data)
        # Groups list depends on the whole workspace, refresh anyway in
        # case the active change came alongside a workspace change.
        self._groups_pane.refresh_from_workspace()
        self._sequences_pane.refresh_workspace()

    # ------------------------------------------------------------------
    # Markdown codebook export
    # ------------------------------------------------------------------
    def build_codebook_markdown(self) -> str:
        """Return a Markdown codebook of every defined event / section /
        group / sequence. Sections appear even when empty so the user
        sees a complete template."""
        events = self._events_pane.events
        sections = self._sections_pane.sections
        groups = self._groups_pane.groups
        sequences = self._sequences_pane.sequences

        lines: list[str] = []
        lines.append("# Study Codebook")
        lines.append("")
        proj = getattr(self._main_window, "_project", None)
        if proj is not None and proj.metadata is not None:
            lines.append(f"**Project:** {proj.metadata.name}")
            lines.append("")

        # Events
        lines.append("## Events")
        lines.append("")
        if events:
            lines.append("| Canonical name | # synonyms | Synonyms |")
            lines.append("|----------------|-----------:|----------|")
            for name, syns in events.items():
                syn_str = ", ".join(syns) if syns else "-"
                lines.append(f"| {name} | {len(syns)} | {syn_str} |")
        else:
            lines.append("_No events defined._")
        lines.append("")

        # Sections
        lines.append("## Sections")
        lines.append("")
        if sections:
            lines.append("| Name | Label | Start events | End events | Description |")
            lines.append("|------|-------|--------------|------------|-------------|")
            for name, data in sections.items():
                start = ", ".join(data.get("start_events") or []) or "-"
                end = ", ".join(data.get("end_events") or []) or "-"
                lines.append(
                    f"| {name} | {data.get('label', name)} | {start} | {end} | "
                    f"{data.get('description', '')} |"
                )
        else:
            lines.append("_No sections defined._")
        lines.append("")

        # Groups
        lines.append("## Groups")
        lines.append("")
        if groups:
            lines.append("| Name | Label | Members | Description |")
            lines.append("|------|-------|--------:|-------------|")
            for name, data in groups.items():
                members = data.get("members") or []
                lines.append(
                    f"| {name} | {data.get('label', name)} | {len(members)} | "
                    f"{data.get('description', '')} |"
                )
        else:
            lines.append("_No groups defined._")
        lines.append("")

        # Sequences
        lines.append("## Sequences")
        lines.append("")
        if sequences:
            lines.append("| Name | Length | Sections (ordered) |")
            lines.append("|------|-------:|---------------------|")
            for seq in sequences:
                lines.append(
                    f"| {seq.name} | {len(seq.sections)} | "
                    f"{' -> '.join(seq.sections)} |"
                )
        else:
            lines.append("_No sequences defined._")
        lines.append("")

        return "\n".join(lines)

    def _on_export_codebook(self) -> None:
        from pathlib import Path

        from qtpy.QtWidgets import QFileDialog as _QFD

        from rrational.inspector import settings as _settings

        text = self.build_codebook_markdown()
        if getattr(self._main_window, "test_mode", False):
            self._main_window.statusBar().showMessage(
                f"Codebook ready ({len(text)} chars).", 3000
            )
            return
        start_dir = _settings.read_setting("last_dir") or str(Path.cwd())
        suggested = str(Path(start_dir) / "codebook.md")
        path_str, _ = _QFD.getSaveFileName(
            self,
            "Export codebook",
            suggested,
            "Markdown (*.md);;All files (*)",
        )
        if not path_str:
            return
        try:
            Path(path_str).write_text(text, encoding="utf-8")
        except OSError as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        self._main_window.statusBar().showMessage(
            f"Exported codebook to {path_str}", 4000
        )
