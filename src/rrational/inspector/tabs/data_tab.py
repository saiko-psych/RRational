"""Data tab - workspace overview (Phase 22.1).

Streamlit-style "Data" tab that mirrors ``rrational.gui.tabs.data``. The
goal is a single landing pane where the user can see:

1. The active project (or "no project — global config").
2. The data-source subfolders detected under ``project/data/raw/`` plus
   raw-file counts per source (hrv_logger, vns, etc.).
3. A read-only participant table — one row per ``participants.yml``
   entry, columns: ID / Group / Sequence / Section count / Has
   artifacts / Has NN intervals.
4. Bulk-action buttons (Import all from raw, Auto-assign from
   workspace, Export all to .rrational v2).

The tab is workspace-level: ``on_active_dataset_changed`` is a no-op.
``on_workspace_changed`` rebuilds the participants table + the
data-source list so the view stays in sync when datasets are opened or
the active project is swapped.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from rrational.inspector.tabs.base import InspectorTab

if TYPE_CHECKING:
    from rrational.inspector.data_loader import InspectorData

# Folder-name → recording-app label. Mirrors the Streamlit detection
# table in ``rrational.gui.tabs.data.RECORDING_APP_DETECTION`` but kept
# inline here so the inspector tab has no Streamlit import dependency.
_RECORDING_APP_FOLDERS: dict[str, str] = {
    "hrv_logger": "HRV Logger",
    "hrv-logger": "HRV Logger",
    "vns_analyse": "VNS Analyse",
    "vns-analyse": "VNS Analyse",
    "vns": "VNS Analyse",
    "elite_hrv": "Elite HRV",
    "elite-hrv": "Elite HRV",
    "elitehrv": "Elite HRV",
    "polar": "Polar",
    "polar_flow": "Polar",
    "empatica": "Empatica",
    "e4": "Empatica",
    "kubios": "Kubios",
}

# Extensions the raw-file count considers. Matches the Streamlit
# behaviour where only CSV / TXT / DAT files are treated as data.
_RAW_FILE_EXTS = {".csv", ".txt", ".dat"}


def _detect_source_label(folder_name: str) -> str:
    """Best-effort recording-app label for a ``data/raw`` subfolder name."""
    key = folder_name.lower()
    if key in _RECORDING_APP_FOLDERS:
        return _RECORDING_APP_FOLDERS[key]
    for pattern, label in _RECORDING_APP_FOLDERS.items():
        if key.startswith(pattern):
            return label
    return "Unknown format"


def _count_raw_files(folder: Path) -> int:
    """Count CSV / TXT / DAT files directly inside ``folder``."""
    if not folder.is_dir():
        return 0
    total = 0
    for entry in folder.iterdir():
        if entry.is_file() and entry.suffix.lower() in _RAW_FILE_EXTS:
            total += 1
    return total


def _scan_data_sources(raw_dir: Path) -> list[dict]:
    """Return ``[{folder, label, count}]`` for each subdir of ``raw_dir``.

    Falls back to a single ``{"folder": raw_dir.name, ...}`` row when
    the raw dir itself holds data files (flat layout — no subdirs).
    """
    if not raw_dir.is_dir():
        return []
    subdirs = sorted(p for p in raw_dir.iterdir() if p.is_dir())
    rows: list[dict] = []
    for sub in subdirs:
        rows.append(
            {
                "folder": sub.name,
                "label": _detect_source_label(sub.name),
                "count": _count_raw_files(sub),
                "path": sub,
            }
        )
    if not rows:
        flat = _count_raw_files(raw_dir)
        if flat > 0:
            rows.append(
                {
                    "folder": raw_dir.name,
                    "label": _detect_source_label(raw_dir.name),
                    "count": flat,
                    "path": raw_dir,
                }
            )
    return rows


class DataTab(InspectorTab):
    """Workspace-overview "Data" tab.

    Replaces the bare empty-state of the Browse tab with a richer
    landing view inspired by the Streamlit ``Data`` tab — project info,
    data sources, participants table, bulk actions.
    """

    TAB_LABEL = "Data"

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(main_window, parent)
        self._build()
        self.on_workspace_changed()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        outer.addWidget(self._build_project_block())

        # Two side-by-side blocks: Raw data (left) + Processed data (right).
        # Both list the actual files in the project so the user sees the
        # state at a glance and clicks any file to open it.
        files_row = QHBoxLayout()
        files_row.setSpacing(8)
        files_row.addWidget(self._build_sources_block(), stretch=1)
        files_row.addWidget(self._build_processed_block(), stretch=1)
        outer.addLayout(files_row, stretch=1)

        # Participants block stretches to consume vertical space — it's
        # the centerpiece of the tab.
        self._participants_group = self._build_participants_block()
        outer.addWidget(self._participants_group, stretch=1)

        outer.addWidget(self._build_bulk_actions_block())

    def _build_processed_block(self) -> QGroupBox:
        """List every .rrational v2 file in the project's data/processed/.

        Each entry is a clickable button that opens the file. Without a
        project, shows an info text.
        """
        from qtpy.QtWidgets import QListWidget

        box = QGroupBox("Processed data (data/processed/*.rrational)")
        layout = QVBoxLayout(box)
        layout.setSpacing(4)

        self._processed_info = QLabel()
        self._processed_info.setStyleSheet("color: #666;")
        self._processed_info.setWordWrap(True)
        layout.addWidget(self._processed_info)

        self._processed_list = QListWidget()
        self._processed_list.itemDoubleClicked.connect(
            self._on_processed_file_double_clicked
        )
        self._processed_list.setAlternatingRowColors(True)
        layout.addWidget(self._processed_list, stretch=1)

        btn_row = QHBoxLayout()
        self._open_selected_btn = QPushButton("Open selected")
        self._open_selected_btn.setToolTip(
            "Open the highlighted .rrational file in the Browse/Participant tab"
        )
        self._open_selected_btn.clicked.connect(self._on_open_selected_processed)
        self._open_all_btn = QPushButton("Open all")
        self._open_all_btn.setToolTip(
            "Open every .rrational file from data/processed/ at once"
        )
        self._open_all_btn.clicked.connect(self._on_open_all_processed)
        btn_row.addWidget(self._open_selected_btn)
        btn_row.addWidget(self._open_all_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return box

    def _on_processed_file_double_clicked(self, item) -> None:
        path = item.data(Qt.UserRole)
        if path:
            self._main_window.open_path(Path(path))

    def _on_open_selected_processed(self) -> None:
        for item in self._processed_list.selectedItems():
            path = item.data(Qt.UserRole)
            if path:
                self._main_window.open_path(Path(path))

    def _on_open_all_processed(self) -> None:
        for i in range(self._processed_list.count()):
            item = self._processed_list.item(i)
            path = item.data(Qt.UserRole)
            if path:
                self._main_window.open_path(Path(path))

    def _refresh_processed_list(self) -> None:
        """Re-scan data/processed/ for the active project."""
        from qtpy.QtWidgets import QListWidgetItem

        self._processed_list.clear()
        pm = getattr(self._main_window, "_project", None)
        if pm is None:
            self._processed_info.setText(
                "<i>No project active. Open or create a project to see "
                "its processed files here.</i>"
            )
            self._open_selected_btn.setEnabled(False)
            self._open_all_btn.setEnabled(False)
            return
        processed_dir = pm.get_processed_dir()
        files = sorted(processed_dir.glob("*.rrational"))
        if not files:
            self._processed_info.setText(
                f"<i>No .rrational v2 exports yet in <code>{processed_dir}</code>. "
                "Use the Browse / Participant tab to load raw data, run "
                "preprocessing, then Save as .rrational.</i>"
            )
            self._open_selected_btn.setEnabled(False)
            self._open_all_btn.setEnabled(False)
            return
        self._processed_info.setText(
            f"<b>{len(files)}</b> processed file(s) in "
            f"<code>{processed_dir}</code>. Double-click to open."
        )
        for fp in files:
            it = QListWidgetItem(fp.name)
            it.setData(Qt.UserRole, str(fp))
            it.setToolTip(str(fp))
            self._processed_list.addItem(it)
        self._open_selected_btn.setEnabled(True)
        self._open_all_btn.setEnabled(True)

    def _build_project_block(self) -> QGroupBox:
        box = QGroupBox("Project")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        self._project_label = QLabel()
        self._project_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._project_label.setWordWrap(True)
        layout.addWidget(self._project_label)

        self._project_path_label = QLabel()
        self._project_path_label.setStyleSheet("color: #666;")
        self._project_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._project_path_label.setWordWrap(True)
        layout.addWidget(self._project_path_label)

        btn_row = QHBoxLayout()
        self._open_project_btn = QPushButton("Open project...")
        self._open_project_btn.clicked.connect(self._on_open_project_clicked)
        btn_row.addWidget(self._open_project_btn)

        self._new_project_btn = QPushButton("Create new project...")
        self._new_project_btn.clicked.connect(self._on_new_project_clicked)
        btn_row.addWidget(self._new_project_btn)

        self._close_project_btn = QPushButton("Close project")
        self._close_project_btn.clicked.connect(self._on_close_project_clicked)
        btn_row.addWidget(self._close_project_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)
        return box

    def _build_sources_block(self) -> QGroupBox:
        box = QGroupBox("Data sources (data/raw/)")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        self._sources_label = QLabel()
        self._sources_label.setStyleSheet("color: #666;")
        self._sources_label.setWordWrap(True)
        layout.addWidget(self._sources_label)

        self._sources_table = QTableWidget(0, 3, self)
        self._sources_table.setHorizontalHeaderLabels(
            ["Subfolder", "Detected as", "Raw files"]
        )
        self._sources_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._sources_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._sources_table.setAlternatingRowColors(True)
        self._sources_table.verticalHeader().setVisible(False)
        hdr = self._sources_table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
        hdr.setStretchLastSection(True)
        # Keep the sources table compact — it's an overview, not the
        # main attraction. Cap its height to ~5 rows of content.
        self._sources_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._sources_table.setMaximumHeight(160)
        layout.addWidget(self._sources_table)

        btn_row = QHBoxLayout()
        self._open_recording_btn = QPushButton("Open recording...")
        self._open_recording_btn.clicked.connect(self._on_open_recording_clicked)
        btn_row.addWidget(self._open_recording_btn)

        self._open_folder_btn = QPushButton("Open folder...")
        self._open_folder_btn.clicked.connect(self._on_open_folder_clicked)
        btn_row.addWidget(self._open_folder_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)
        return box

    def _build_participants_block(self) -> QGroupBox:
        box = QGroupBox("Participants")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        self._participants_summary = QLabel()
        self._participants_summary.setStyleSheet("color: #666;")
        layout.addWidget(self._participants_summary)

        self._participants_table = QTableWidget(0, 6, self)
        self._participants_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Group",
                "Sequence",
                "Section count",
                "Has artifacts",
                "Has NN intervals",
            ]
        )
        self._participants_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._participants_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._participants_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._participants_table.setAlternatingRowColors(True)
        self._participants_table.verticalHeader().setVisible(False)
        self._participants_table.setSortingEnabled(True)
        hdr = self._participants_table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.ResizeToContents)
        hdr.setStretchLastSection(True)
        layout.addWidget(self._participants_table, stretch=1)
        return box

    def _build_bulk_actions_block(self) -> QFrame:
        frame = QFrame()
        frame.setFrameShape(QFrame.NoFrame)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)

        self._bulk_import_btn = QPushButton("Import all from project/data/raw/")
        self._bulk_import_btn.setToolTip(
            "Open every supported recording inside the active project's "
            "data/raw/ tree as a new dataset."
        )
        self._bulk_import_btn.clicked.connect(self._on_bulk_import_clicked)
        layout.addWidget(self._bulk_import_btn)

        self._bulk_assign_btn = QPushButton("Auto-assign participants from workspace")
        self._bulk_assign_btn.setToolTip(
            "Create a participants.yml entry for every loaded dataset whose "
            "stem isn't already registered (delegates to the Participants tab)."
        )
        self._bulk_assign_btn.clicked.connect(self._on_bulk_assign_clicked)
        layout.addWidget(self._bulk_assign_btn)

        self._bulk_export_btn = QPushButton("Export all to .rrational v2")
        self._bulk_export_btn.setToolTip(
            "Save every loaded dataset as a .rrational v2 file under "
            "project/data/processed/ (when a project is active)."
        )
        self._bulk_export_btn.clicked.connect(self._on_bulk_export_clicked)
        layout.addWidget(self._bulk_export_btn)

        layout.addStretch()
        return frame

    # ------------------------------------------------------------------
    # InspectorTab hooks
    # ------------------------------------------------------------------
    def on_workspace_changed(self) -> None:
        """Refresh everything: project info, sources, processed list,
        participants table."""
        self._refresh_project_block()
        self._refresh_sources_block()
        self._refresh_processed_list()
        self._refresh_participants_table()
        self._refresh_bulk_buttons()

    # MainWindow.set_active_project calls this name; provide as alias.
    refresh_from_workspace = on_workspace_changed

    def on_active_dataset_changed(self, _data: "InspectorData | None") -> None:
        # Workspace-level tab — the active selection doesn't matter here.
        # We deliberately do NOT rebuild the participants table on every
        # active-dataset change to keep selection / sort state stable.
        pass

    def tab_label_state(self) -> str:
        n_participants = len(self._collect_participants())
        n_datasets = len(self._main_window._datasets)
        if n_participants == 0 and n_datasets == 0:
            return "(empty)"
        return (
            f"({n_participants} participant{'s' if n_participants != 1 else ''}, "
            f"{n_datasets} dataset{'s' if n_datasets != 1 else ''})"
        )

    # ------------------------------------------------------------------
    # Refresh helpers
    # ------------------------------------------------------------------
    def _refresh_project_block(self) -> None:
        proj = getattr(self._main_window, "_project", None)
        if proj is None:
            self._project_label.setText(
                "<b>No project active</b> — using global ~/.rrational config."
            )
            self._project_path_label.setText("")
            self._close_project_btn.setEnabled(False)
        else:
            name = (
                proj.metadata.name
                if proj.metadata is not None
                else proj.project_path.name
            )
            self._project_label.setText(f"<b>{name}</b>")
            self._project_path_label.setText(str(proj.project_path))
            self._close_project_btn.setEnabled(True)

    def _refresh_sources_block(self) -> None:
        raw_dir = self._project_raw_dir()
        self._sources_table.setRowCount(0)
        if raw_dir is None:
            self._sources_label.setText(
                "Open a project to scan its <code>data/raw/</code> tree."
            )
            return
        if not raw_dir.exists():
            self._sources_label.setText(
                f"<i>data/raw/ does not exist at {raw_dir}.</i>"
            )
            return

        rows = _scan_data_sources(raw_dir)
        self._sources_label.setText(f"Scanning <code>{raw_dir}</code>")
        if not rows:
            # Still show the path label, just an empty table.
            return
        for row in rows:
            r = self._sources_table.rowCount()
            self._sources_table.insertRow(r)
            self._sources_table.setItem(r, 0, QTableWidgetItem(str(row["folder"])))
            self._sources_table.setItem(r, 1, QTableWidgetItem(str(row["label"])))
            count_item = QTableWidgetItem(str(row["count"]))
            count_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._sources_table.setItem(r, 2, count_item)

    def _refresh_participants_table(self) -> None:
        # Disable sorting during populate — otherwise inserting cells
        # while sorting is on shuffles rows mid-fill.
        self._participants_table.setSortingEnabled(False)
        self._participants_table.setRowCount(0)
        participants = self._collect_participants()
        for pid in sorted(participants.keys()):
            data = participants[pid] or {}
            dataset = self._find_dataset_for(pid)
            section_count = len(dataset.data.sections) if dataset is not None else 0
            has_artifacts = self._dataset_has_artifacts(dataset)
            has_nn = self._dataset_has_nn(dataset)

            r = self._participants_table.rowCount()
            self._participants_table.insertRow(r)
            self._participants_table.setItem(r, 0, QTableWidgetItem(pid))
            self._participants_table.setItem(
                r, 1, QTableWidgetItem(str(data.get("group") or ""))
            )
            self._participants_table.setItem(
                r, 2, QTableWidgetItem(str(data.get("sequence") or ""))
            )
            count_item = QTableWidgetItem(str(section_count))
            count_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._participants_table.setItem(r, 3, count_item)
            self._participants_table.setItem(
                r, 4, QTableWidgetItem("Yes" if has_artifacts else "No")
            )
            self._participants_table.setItem(
                r, 5, QTableWidgetItem("Yes" if has_nn else "No")
            )
        self._participants_table.setSortingEnabled(True)

        n_participants = len(participants)
        n_datasets = len(self._main_window._datasets)
        self._participants_summary.setText(
            f"{n_participants} participant(s) registered · "
            f"{n_datasets} dataset(s) loaded in workspace."
        )

    def _refresh_bulk_buttons(self) -> None:
        raw_dir = self._project_raw_dir()
        has_raw_files = False
        if raw_dir is not None and raw_dir.exists():
            sources = _scan_data_sources(raw_dir)
            has_raw_files = any(s["count"] > 0 for s in sources)
        self._bulk_import_btn.setEnabled(has_raw_files)
        self._bulk_assign_btn.setEnabled(len(self._main_window._datasets) > 0)
        self._bulk_export_btn.setEnabled(len(self._main_window._datasets) > 0)

    # ------------------------------------------------------------------
    # Data accessors
    # ------------------------------------------------------------------
    def _project_raw_dir(self) -> Path | None:
        proj = getattr(self._main_window, "_project", None)
        if proj is None:
            return None
        try:
            return proj.get_data_dir()
        except AttributeError:  # pragma: no cover - defensive
            return None

    def _collect_participants(self) -> dict[str, dict]:
        """Pull participants from the ParticipantsTab (single source of truth)."""
        pt = getattr(self._main_window, "_participants_tab", None)
        if pt is None:
            return {}
        try:
            return pt.participants
        except AttributeError:  # pragma: no cover - defensive
            return {}

    def _find_dataset_for(self, pid: str):
        """Return the workspace Dataset whose filename stem matches ``pid``."""
        for ds in self._main_window._datasets:
            stem = Path(ds.name).stem
            if stem == pid or ds.name == pid:
                return ds
        return None

    @staticmethod
    def _dataset_has_artifacts(dataset) -> bool:
        if dataset is None:
            return False
        # Two places artifact info typically lives:
        # 1. dataset.data.artifacts (per-section flags on InspectorData)
        # 2. an "artifact_indices" attribute attached at load-time
        data = getattr(dataset, "data", None)
        if data is None:
            return False
        if getattr(data, "artifacts", None):
            return True
        for sec in getattr(data, "sections", []) or []:
            if getattr(sec, "artifact_indices", None):
                return True
            if getattr(sec, "has_artifacts", False):
                return True
        return False

    @staticmethod
    def _dataset_has_nn(dataset) -> bool:
        if dataset is None:
            return False
        data = getattr(dataset, "data", None)
        if data is None:
            return False
        # An InspectorData built from .rrational always has a t/v vector;
        # a non-empty length means NN intervals are present.
        t = getattr(data, "t", None)
        if t is None:
            return False
        try:
            return len(t) > 0
        except TypeError:  # pragma: no cover - defensive
            return False

    # ------------------------------------------------------------------
    # Button handlers (delegate to MainWindow where possible)
    # ------------------------------------------------------------------
    def _on_open_project_clicked(self) -> None:
        handler = getattr(self._main_window, "_on_open_project_clicked", None)
        if handler is not None:
            handler()
        self.on_workspace_changed()

    def _on_new_project_clicked(self) -> None:
        handler = getattr(self._main_window, "_on_new_project_clicked", None)
        if handler is not None:
            handler()
        self.on_workspace_changed()

    def _on_close_project_clicked(self) -> None:
        handler = getattr(self._main_window, "close_project", None)
        if handler is not None:
            handler()
        self.on_workspace_changed()

    def _on_open_recording_clicked(self) -> None:
        handler = getattr(self._main_window, "_on_open_clicked", None)
        if handler is not None:
            handler()
        self.on_workspace_changed()

    def _on_open_folder_clicked(self) -> None:
        handler = getattr(self._main_window, "_on_open_folder_clicked", None)
        if handler is not None:
            handler()
        self.on_workspace_changed()

    def _on_bulk_import_clicked(self) -> None:
        raw_dir = self._project_raw_dir()
        if raw_dir is None or not raw_dir.exists():
            return
        # Reuse MainWindow.open_folder so we get the BIDS-aware loader
        # path for free. The folder loader skips its own info dialog
        # under test_mode, so this stays headless-safe.
        open_folder = getattr(self._main_window, "open_folder", None)
        if open_folder is None:
            return
        loaded_before = len(self._main_window._datasets)
        # Open each detected source folder so flat-source projects
        # (one folder per app) all get scanned. Falls back to the raw
        # dir itself when no subdirs exist.
        sources = _scan_data_sources(raw_dir)
        scan_targets = [s["path"] for s in sources] if sources else [raw_dir]
        for target in scan_targets:
            try:
                open_folder(target)
            except Exception:  # pragma: no cover - defensive
                continue
        loaded_after = len(self._main_window._datasets)
        self.on_workspace_changed()
        delta = loaded_after - loaded_before
        msg = f"Imported {delta} dataset(s) from {raw_dir}."
        self._main_window.statusBar().showMessage(msg, 4000)

    def _on_bulk_assign_clicked(self) -> None:
        pt = getattr(self._main_window, "_participants_tab", None)
        if pt is None:
            return
        # Delegate to the ParticipantsTab's existing implementation so
        # we share the "skip existing" logic + persistence path.
        importer = getattr(pt, "_on_import_workspace", None)
        if importer is None:
            return
        importer()
        self.on_workspace_changed()

    def _on_bulk_export_clicked(self) -> None:
        if not self._main_window._datasets:
            return
        proj = getattr(self._main_window, "_project", None)
        if proj is not None:
            try:
                out_dir = proj.get_processed_dir()
            except AttributeError:  # pragma: no cover - defensive
                out_dir = None
        else:
            out_dir = None
        if out_dir is None:
            if getattr(self._main_window, "test_mode", False):
                self._main_window.statusBar().showMessage(
                    "Bulk export: no project — would prompt for folder.", 3000
                )
                return
            chosen = QFileDialog.getExistingDirectory(
                self, "Choose folder for .rrational exports"
            )
            if not chosen:
                return
            out_dir = Path(chosen)
        # Defer the actual writer import — it's heavy and many tests
        # don't exercise it.
        try:
            from rrational.io.rrational_writer import write_rrational
        except Exception:
            write_rrational = None
        written = 0
        for ds in self._main_window._datasets:
            stem = Path(ds.name).stem or "dataset"
            out_path = Path(out_dir) / f"{stem}.rrational"
            if write_rrational is None:
                # Writer unavailable — at minimum record the intended
                # target so the user can see what would happen.
                continue
            try:
                write_rrational(ds.data, out_path)
                written += 1
            except Exception:  # pragma: no cover - defensive
                continue
        if write_rrational is None and not getattr(
            self._main_window, "test_mode", False
        ):
            QMessageBox.information(
                self,
                "Bulk export",
                "RRational v2 writer is not available in this build.",
            )
            return
        self._main_window.statusBar().showMessage(
            f"Exported {written} dataset(s) to {out_dir}.", 4000
        )
