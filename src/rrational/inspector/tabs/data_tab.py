"""Data tab - workspace overview (Phase 22.1 + Phase 23A).

Streamlit-style "Data" tab that mirrors ``rrational.gui.tabs.data``. The
goal is a single landing pane where the user can see:

1. The active project (or "no project — global config").
2. The data-source subfolders detected under ``project/data/raw/`` plus
   raw-file counts per source (hrv_logger, vns, etc.).
3. A read-only participant table — one row per ``participants.yml``
   entry, columns: ID / Group / Sequence / Beats / Duration / RR mean /
   Retained / Artifacts % / Duplicates / RR range / Events / Sections /
   Has artifacts / Has NN / Quality.
4. Bulk-action buttons (Import all from raw, Auto-assign from
   workspace, Export all to .rrational v2).

Phase 23A adds a "Cleaning thresholds" block between the Project block
and the side-by-side raw/processed blocks. The user can tune
``rr_min_ms`` / ``rr_max_ms`` / ``sudden_change_pct`` and the
participants table updates with retained/artifact stats from the
shared ``rrational.prep.summaries.PreparationSummary`` pipeline.

The tab is workspace-level: ``on_active_dataset_changed`` is a no-op.
``on_workspace_changed`` rebuilds the participants table + the
data-source list so the view stays in sync when datasets are opened or
the active project is swapped.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from rrational.cleaning.rr import CleaningConfig
from rrational.inspector.prep_summary import (
    compute_inspector_summary,
    invalidate_cache,
)
from rrational.inspector.settings import read_setting, write_setting
from rrational.inspector.tabs.base import InspectorTab
from rrational.inspector.tabs.import_mapping_dialog import (
    ImportParticipantMappingDialog,
)

if TYPE_CHECKING:
    from rrational.inspector.data_loader import InspectorData


# ----------------------------------------------------------------------
# Phase 23A — Cleaning thresholds form defaults + helpers
# ----------------------------------------------------------------------
# Defaults match what ``rrational.inspector.settings`` registers for
# the new keys (cleaning_min_rr_ms / cleaning_max_rr_ms /
# cleaning_sudden_change_pct). Keep these in sync.
_CLEANING_DEFAULT_MIN_MS = 300.0
_CLEANING_DEFAULT_MAX_MS = 2000.0
_CLEANING_DEFAULT_SUDDEN_PCT = 20.0


def _read_cleaning_setting(key: str, default: float) -> float:
    """Read a cleaning threshold from QSettings as a float.

    QSettings returns strings on some platforms — coerce safely.
    """
    raw = read_setting(key)
    if raw is None or raw == "":
        return float(default)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(default)


def _current_cleaning_config() -> CleaningConfig:
    """Build a ``CleaningConfig`` from the persisted QSettings values."""
    min_ms = _read_cleaning_setting("cleaning_min_rr_ms", _CLEANING_DEFAULT_MIN_MS)
    max_ms = _read_cleaning_setting("cleaning_max_rr_ms", _CLEANING_DEFAULT_MAX_MS)
    sudden_pct = _read_cleaning_setting(
        "cleaning_sudden_change_pct", _CLEANING_DEFAULT_SUDDEN_PCT
    )
    return CleaningConfig(
        rr_min_ms=int(min_ms),
        rr_max_ms=int(max_ms),
        sudden_change_pct=float(sudden_pct) / 100.0,
    )


def _persist_cleaning_config(min_ms: float, max_ms: float, sudden_pct: float) -> None:
    """Write the user's cleaning thresholds back to QSettings."""
    write_setting("cleaning_min_rr_ms", float(min_ms))
    write_setting("cleaning_max_rr_ms", float(max_ms))
    write_setting("cleaning_sudden_change_pct", float(sudden_pct))


# ----------------------------------------------------------------------
# Phase 24B — participant ID pattern picker helpers
# ----------------------------------------------------------------------
def _read_id_pattern() -> str:
    """Return the persisted participant ID regex, or the DEFAULT."""
    from rrational.io import DEFAULT_ID_PATTERN as _DEFAULT

    raw = read_setting("participant_id_pattern")
    if raw is None or raw == "":
        return _DEFAULT
    return str(raw)


def extract_participant_id(file_path: Path, pattern: str | None = None) -> str:
    """Apply the configured regex to ``file_path.stem`` and return the
    captured ``participant`` group.

    Falls back to ``Path.stem`` if the pattern doesn't match or is
    invalid — keeps the inspector usable even when the user types
    nonsense into the picker.
    """
    import re as _re

    if pattern is None:
        pattern = _read_id_pattern()
    if not pattern:
        return file_path.stem
    try:
        compiled = _re.compile(pattern)
    except _re.error:
        return file_path.stem
    m = compiled.search(file_path.name)
    if m is None:
        return file_path.stem
    try:
        return m.group("participant")
    except IndexError:
        return m.group(0)


# ----------------------------------------------------------------------
# Participants-table column layout — single source of truth
# ----------------------------------------------------------------------
_PARTICIPANTS_TABLE_HEADERS: tuple[str, ...] = (
    "ID",
    "Group",
    "Sequence",
    "Beats",
    "Duration (min)",
    "RR mean (ms)",
    "Retained",
    "Artifacts %",
    "Duplicates",
    "RR range",
    "Events",
    "Sections",
    "Has artifacts",
    "Has NN",
    "Quality",
)
COL_ID = 0
COL_GROUP = 1
COL_SEQUENCE = 2
COL_BEATS = 3
COL_DURATION = 4
COL_RR_MEAN = 5
COL_RETAINED = 6
COL_ARTIFACT_PCT = 7
COL_DUPLICATES = 8
COL_RR_RANGE = 9
COL_EVENTS = 10
COL_SECTIONS = 11
COL_HAS_ARTIFACTS = 12
COL_HAS_NN = 13
COL_QUALITY = 14


# Phase 23A Quality-badge thresholds (artifact_ratio). Mirrors the
# Streamlit colour coding: green <5%, yellow <15%, red otherwise.
_QUALITY_GOOD_MAX = 0.05
_QUALITY_OK_MAX = 0.15

# Quality badge colours: chosen to remain readable on alternating-row
# backgrounds (avoid super-pale shades that wash out).
_QUALITY_COLOURS: dict[str, QColor] = {
    "Good": QColor(0, 128, 0),
    "OK": QColor(184, 134, 11),
    "Poor": QColor(178, 34, 34),
}


def _quality_for(artifact_ratio: float) -> tuple[str, QColor]:
    """Map a 0-1 artifact ratio to a (label, colour) badge."""
    if artifact_ratio < _QUALITY_GOOD_MAX:
        label = "Good"
    elif artifact_ratio < _QUALITY_OK_MAX:
        label = "OK"
    else:
        label = "Poor"
    return label, _QUALITY_COLOURS[label]


# ----------------------------------------------------------------------
# Raw-data-source detection (unchanged from Phase 22.1)
# ----------------------------------------------------------------------
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
    cleaning thresholds, data sources, participants table, bulk actions.
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
        # Phase 24A: in-tab help expanders. Imported here so a fresh
        # ``import data_tab`` doesn't pay the cost when the widget isn't
        # constructed (the optional-tab gate in main_window).
        from rrational.inspector.help_widgets import HelpExpander

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(12)

        outer.addWidget(
            HelpExpander(
                "What is this tab for?",
                (
                    "<p>The <b>Data</b> tab is your workspace overview. It shows the "
                    "active project, the raw data sources detected under "
                    "<code>data/raw/</code>, every <code>.rrational</code> export under "
                    "<code>data/processed/</code>, and a per-participant summary "
                    "table.</p>"
                    "<p>Start by opening a project (<i>File &rarr; Open project</i>), "
                    "then double-click any raw file or use <i>Load selected source</i> "
                    "to bulk-load all files from a folder.</p>"
                ),
            )
        )
        outer.addWidget(
            HelpExpander(
                "What do the columns mean?",
                (
                    "<p>Each row of the participants table summarises one loaded "
                    "recording.</p>"
                    "<ul>"
                    "<li><b>Beats / Duration / RR mean</b> — basic counts and "
                    "averages after duplicate removal.</li>"
                    "<li><b>Retained</b> — fraction of intervals inside the "
                    "min/max RR window above.</li>"
                    "<li><b>Artifacts %</b> — fraction flagged as ectopic / "
                    "extra / missed by the Lipponen 2019 (Kubios) algorithm.</li>"
                    "<li><b>Duplicates</b> — repeated timestamps from the recorder.</li>"
                    "<li><b>Quality</b> — green &lt;5%, yellow &lt;15%, red otherwise. "
                    "Use this to triage which recordings deserve manual review on "
                    "the <i>Participant</i> tab.</li>"
                    "</ul>"
                ),
            )
        )

        outer.addWidget(self._build_project_block())

        # Phase 23A: cleaning thresholds form sits between Project and
        # the raw/processed file lists so the user sees what the
        # downstream metrics are computed against before they look at
        # the participants table.
        outer.addWidget(self._build_cleaning_block())

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

    def _build_cleaning_block(self) -> QGroupBox:
        """Tiny form for ``CleaningConfig`` thresholds (Phase 23A) + a
        Phase 24B ID-pattern picker sub-group.

        Two min/max RR spin-boxes + one sudden-change-% spin-box +
        Apply button. Values persist to QSettings; Apply invalidates the
        per-dataset summary cache and refreshes the participants table.
        The ID-pattern picker writes its choice to QSettings under
        ``participant_id_pattern``.
        """
        from qtpy.QtWidgets import QComboBox as _Combo
        from qtpy.QtWidgets import QLineEdit as _LineEdit

        from rrational.io import (
            DEFAULT_ID_PATTERN as _DEFAULT_ID,
        )
        from rrational.io import (
            PREDEFINED_PATTERNS as _PATTERNS,
        )

        box = QGroupBox("Cleaning thresholds & participant ID")
        outer = QVBoxLayout(box)
        outer.setSpacing(6)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self._cleaning_min_spin = QDoubleSpinBox()
        self._cleaning_min_spin.setRange(0.0, 5000.0)
        self._cleaning_min_spin.setDecimals(0)
        self._cleaning_min_spin.setSingleStep(10.0)
        self._cleaning_min_spin.setSuffix(" ms")
        self._cleaning_min_spin.setValue(
            _read_cleaning_setting("cleaning_min_rr_ms", _CLEANING_DEFAULT_MIN_MS)
        )
        form.addRow("Min RR:", self._cleaning_min_spin)

        self._cleaning_max_spin = QDoubleSpinBox()
        self._cleaning_max_spin.setRange(0.0, 5000.0)
        self._cleaning_max_spin.setDecimals(0)
        self._cleaning_max_spin.setSingleStep(10.0)
        self._cleaning_max_spin.setSuffix(" ms")
        self._cleaning_max_spin.setValue(
            _read_cleaning_setting("cleaning_max_rr_ms", _CLEANING_DEFAULT_MAX_MS)
        )
        form.addRow("Max RR:", self._cleaning_max_spin)

        self._cleaning_sudden_spin = QDoubleSpinBox()
        self._cleaning_sudden_spin.setRange(0.0, 100.0)
        self._cleaning_sudden_spin.setDecimals(1)
        self._cleaning_sudden_spin.setSingleStep(1.0)
        self._cleaning_sudden_spin.setSuffix(" %")
        self._cleaning_sudden_spin.setValue(
            _read_cleaning_setting(
                "cleaning_sudden_change_pct", _CLEANING_DEFAULT_SUDDEN_PCT
            )
        )
        form.addRow("Sudden change:", self._cleaning_sudden_spin)

        # Phase 24B: participant ID regex picker. The combo lists the
        # canned PREDEFINED_PATTERNS + "Custom"; switching to Custom
        # enables the regex line edit so the user can type their own.
        self._id_pattern_combo = _Combo()
        self._pattern_names: list[str] = list(_PATTERNS.keys())
        for name in self._pattern_names:
            self._id_pattern_combo.addItem(name, _PATTERNS[name])
        self._id_pattern_combo.addItem("Custom pattern...", None)
        self._id_pattern_combo.setToolTip(
            "Pick a canned regex or 'Custom' to type your own. The captured "
            "'participant' group becomes the participant ID for new files."
        )
        form.addRow("ID pattern preset:", self._id_pattern_combo)

        self._id_pattern_edit = _LineEdit()
        self._id_pattern_edit.setPlaceholderText(_DEFAULT_ID)
        self._id_pattern_edit.setToolTip(
            "Regex with a (?P<participant>...) named group. Falls back to "
            "Path.stem when the pattern doesn't match a filename."
        )
        current_pattern = _read_id_pattern()
        self._id_pattern_edit.setText(current_pattern)
        # Pick the matching preset in the combo, falling back to Custom.
        sel_idx = self._id_pattern_combo.count() - 1
        for i, name in enumerate(self._pattern_names):
            if _PATTERNS[name] == current_pattern:
                sel_idx = i
                break
        self._id_pattern_combo.setCurrentIndex(sel_idx)
        form.addRow("ID pattern:", self._id_pattern_edit)

        self._id_pattern_status = QLabel("")
        self._id_pattern_status.setStyleSheet("color: #555;")
        form.addRow("", self._id_pattern_status)

        self._id_pattern_combo.currentIndexChanged.connect(
            self._on_id_pattern_preset_changed
        )
        self._id_pattern_edit.textChanged.connect(self._on_id_pattern_text_changed)
        # Initial enable + validation
        self._on_id_pattern_preset_changed(self._id_pattern_combo.currentIndex())

        outer.addLayout(form)

        btn_row = QHBoxLayout()
        self._cleaning_apply_btn = QPushButton("Apply & refresh")
        self._cleaning_apply_btn.setToolTip(
            "Persist these thresholds and re-compute the per-participant "
            "summary metrics (Retained / Artifacts % / RR range / Quality)."
        )
        self._cleaning_apply_btn.clicked.connect(self._on_apply_cleaning_clicked)
        btn_row.addWidget(self._cleaning_apply_btn)
        btn_row.addStretch()
        outer.addLayout(btn_row)
        return box

    # ------------------------------------------------------------------
    # Phase 24B — ID pattern picker callbacks
    # ------------------------------------------------------------------
    def _on_id_pattern_preset_changed(self, idx: int) -> None:
        """When the user picks a preset, copy the regex into the edit
        field; when they pick Custom, leave the edit field editable."""
        data = self._id_pattern_combo.itemData(idx)
        is_custom = data is None
        self._id_pattern_edit.setEnabled(True)  # always editable
        if not is_custom:
            self._id_pattern_edit.blockSignals(True)
            self._id_pattern_edit.setText(str(data))
            self._id_pattern_edit.blockSignals(False)
        # Persist + validate
        self._on_id_pattern_text_changed(self._id_pattern_edit.text())

    def _on_id_pattern_text_changed(self, text: str) -> None:
        """Persist the regex and update the live-match counter."""
        import re as _re

        text = (text or "").strip()
        write_setting("participant_id_pattern", text or "")
        # Validate + count matches against raw filenames in the project.
        try:
            compiled = _re.compile(text) if text else None
        except _re.error as e:
            self._id_pattern_status.setText(
                f"<span style='color:#b22222'>Invalid regex: {e}</span>"
            )
            return
        files = self._collect_raw_filenames()
        if not files:
            self._id_pattern_status.setText(
                "<i>No raw files in project — pattern saved.</i>"
            )
            return
        if compiled is None:
            self._id_pattern_status.setText("<i>(empty pattern — fallback to stem)</i>")
            return
        matched = sum(1 for fn in files if compiled.search(fn) is not None)
        self._id_pattern_status.setText(f"Matches {matched} / {len(files)} files")

    def _collect_raw_filenames(self) -> list[str]:
        """List every raw filename under the project's data/raw/ tree.

        Used for live regex validation. Returns the bare name (no path)
        so the regex can target the same string we'd use at load time.
        """
        raw_dir = self._project_raw_dir()
        if raw_dir is None or not raw_dir.exists():
            return []
        names: list[str] = []
        for sub in raw_dir.iterdir():
            if sub.is_file() and sub.suffix.lower() in _RAW_FILE_EXTS:
                names.append(sub.name)
            elif sub.is_dir():
                try:
                    for fp in sub.iterdir():
                        if fp.is_file() and fp.suffix.lower() in _RAW_FILE_EXTS:
                            names.append(fp.name)
                except OSError:
                    continue
        return names

    def _on_apply_cleaning_clicked(self) -> None:
        """Persist the spin-box values, drop the cache, refresh table."""
        _persist_cleaning_config(
            self._cleaning_min_spin.value(),
            self._cleaning_max_spin.value(),
            self._cleaning_sudden_spin.value(),
        )
        invalidate_cache()
        self._refresh_participants_table()

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
        self._open_project_btn.setToolTip("Open an existing RRational project folder.")
        self._open_project_btn.clicked.connect(self._on_open_project_clicked)
        btn_row.addWidget(self._open_project_btn)

        self._new_project_btn = QPushButton("Create new project...")
        self._new_project_btn.setToolTip(
            "Create a new project folder with the standard subdirectories."
        )
        self._new_project_btn.clicked.connect(self._on_new_project_clicked)
        btn_row.addWidget(self._new_project_btn)

        self._close_project_btn = QPushButton("Close project")
        self._close_project_btn.setToolTip(
            "Close the active project and fall back to global config."
        )
        self._close_project_btn.clicked.connect(self._on_close_project_clicked)
        btn_row.addWidget(self._close_project_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)
        return box

    def _build_sources_block(self) -> QGroupBox:
        """Raw-data block, mirrors Streamlit's Data tab "Detected Data Sources"
        + "Folder Structure" expander.

        QTreeWidget: each source folder is a top-level row showing
        "subfolder -> detected app (N files)"; expanding shows the actual
        files. Double-click a file to open it. Each top-level row has a
        context-menu action "Load all from this source".
        """
        from qtpy.QtWidgets import QTreeWidget

        box = QGroupBox("Raw data (data/raw/)")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        self._sources_label = QLabel()
        self._sources_label.setStyleSheet("color: #666;")
        self._sources_label.setWordWrap(True)
        layout.addWidget(self._sources_label)

        self._sources_tree = QTreeWidget()
        self._sources_tree.setHeaderLabels(["Folder / File", "Type", "Size"])
        self._sources_tree.setRootIsDecorated(True)
        self._sources_tree.setAlternatingRowColors(True)
        self._sources_tree.setUniformRowHeights(True)
        self._sources_tree.itemDoubleClicked.connect(
            self._on_source_item_double_clicked
        )
        self._sources_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._sources_tree.customContextMenuRequested.connect(
            self._on_source_context_menu
        )
        hdr = self._sources_tree.header()
        hdr.setStretchLastSection(False)
        hdr.setSectionResizeMode(0, hdr.ResizeMode.Stretch)
        hdr.setSectionResizeMode(1, hdr.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, hdr.ResizeMode.ResizeToContents)
        layout.addWidget(self._sources_tree, stretch=1)

        btn_row = QHBoxLayout()
        self._load_selected_source_btn = QPushButton("Load selected source")
        self._load_selected_source_btn.setToolTip(
            "Bulk-load every raw file from the highlighted source folder"
        )
        self._load_selected_source_btn.clicked.connect(self._on_load_selected_source)
        btn_row.addWidget(self._load_selected_source_btn)

        self._open_recording_btn = QPushButton("Open recording...")
        self._open_recording_btn.setToolTip(
            "Open a single recording file (any supported format)."
        )
        self._open_recording_btn.clicked.connect(self._on_open_recording_clicked)
        btn_row.addWidget(self._open_recording_btn)

        self._open_folder_btn = QPushButton("Open folder...")
        self._open_folder_btn.setToolTip("Open every recording inside a chosen folder.")
        self._open_folder_btn.clicked.connect(self._on_open_folder_clicked)
        btn_row.addWidget(self._open_folder_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)
        return box

    # ------------------------------------------------------------------
    # Sources tree handlers
    # ------------------------------------------------------------------
    def _on_source_item_double_clicked(self, item, _column) -> None:
        path_str = item.data(0, Qt.UserRole)
        if not path_str:
            return
        path = Path(path_str)
        if path.is_file():
            self._main_window.open_path(path)
        elif path.is_dir():
            item.setExpanded(not item.isExpanded())

    def _on_source_context_menu(self, pos) -> None:
        item = self._sources_tree.itemAt(pos)
        if item is None:
            return
        path_str = item.data(0, Qt.UserRole)
        if not path_str:
            return
        path = Path(path_str)
        from qtpy.QtWidgets import QMenu

        menu = QMenu(self._sources_tree)
        if path.is_dir():
            menu.addAction(
                "Load all from this source",
                lambda: self._load_folder_recursively(path),
            )
        else:
            menu.addAction("Open this file", lambda: self._main_window.open_path(path))
        menu.exec(self._sources_tree.viewport().mapToGlobal(pos))

    def _on_load_selected_source(self) -> None:
        item = self._sources_tree.currentItem()
        if item is None:
            return
        path_str = item.data(0, Qt.UserRole)
        if not path_str:
            return
        path = Path(path_str)
        if path.is_dir():
            self._load_folder_recursively(path)
        elif path.is_file():
            self._main_window.open_path(path)

    def _load_folder_recursively(self, folder: Path) -> None:
        """Open every raw file under ``folder`` (one level deep).

        Mirrors Streamlit's "Load Selected Sources" bulk action.
        """
        if not folder.is_dir():
            return
        files = [p for p in sorted(folder.iterdir()) if p.is_file()]
        loaded = 0
        for fp in files:
            try:
                self._main_window.open_path(fp)
                loaded += 1
            except Exception:
                # Skip unreadable files — open_path already shows an error
                # for the first failure; keep going for the rest.
                continue
        self._main_window.statusBar().showMessage(
            f"Loaded {loaded} / {len(files)} files from {folder.name}", 5000
        )

    def _build_participants_block(self) -> QGroupBox:
        box = QGroupBox("Participants")
        layout = QVBoxLayout(box)
        layout.setSpacing(6)

        self._participants_summary = QLabel()
        self._participants_summary.setStyleSheet("color: #666;")
        layout.addWidget(self._participants_summary)

        # Phase 24B — Issues Summary row sits above the table. Each
        # metric is a clickable link that filters the table to those
        # rows; clicking the "show all" link resets the filter.
        self._issues_label = QLabel("")
        self._issues_label.setStyleSheet("color: #555;")
        self._issues_label.setTextFormat(Qt.RichText)
        self._issues_label.setOpenExternalLinks(False)
        self._issues_label.linkActivated.connect(self._on_issues_link)
        self._issues_label.setToolTip(
            "Counts mirror the Streamlit Data tab. Click a link to filter the "
            "table; click 'show all' to reset."
        )
        layout.addWidget(self._issues_label)

        # The active filter, applied after every refresh. None == show all.
        self._issues_filter: str | None = None

        # 15 columns — Streamlit-parity metrics from PreparationSummary
        # (Phase 23A added Retained / Artifacts % / Duplicates / RR
        # range + a trailing Quality badge).
        self._participants_table = QTableWidget(
            0, len(_PARTICIPANTS_TABLE_HEADERS), self
        )
        self._participants_table.setHorizontalHeaderLabels(
            list(_PARTICIPANTS_TABLE_HEADERS)
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

        # Phase 24B — participants CSV export
        self._export_participants_csv_btn = QPushButton("Export participants CSV...")
        self._export_participants_csv_btn.setToolTip(
            "Write the live participants table (ID / Group / Sequence / Beats / "
            "Duration / Artifacts % / Duplicates / Quality) to a CSV file."
        )
        self._export_participants_csv_btn.clicked.connect(
            self._on_export_participants_csv_clicked
        )
        layout.addWidget(self._export_participants_csv_btn)

        # Phase 24B — Group / Sequence CSV importer
        self._import_mapping_btn = QPushButton("Import Group/Sequence CSV...")
        self._import_mapping_btn.setToolTip(
            "Open a CSV with one row per participant and map its columns to "
            "Group / Sequence. Missing groups + sequences are auto-created."
        )
        self._import_mapping_btn.clicked.connect(self._on_import_mapping_clicked)
        layout.addWidget(self._import_mapping_btn)

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
        """Re-scan data/raw/ and rebuild the QTreeWidget.

        Top level = source folder ("hrv_logger -> HRV Logger  22 files").
        Children  = individual files with detected type + size.
        """
        from qtpy.QtWidgets import QTreeWidgetItem

        raw_dir = self._project_raw_dir()
        self._sources_tree.clear()
        if raw_dir is None:
            self._sources_label.setText(
                "<i>Open a project to scan its <code>data/raw/</code> tree.</i>"
            )
            self._load_selected_source_btn.setEnabled(False)
            return
        if not raw_dir.exists():
            self._sources_label.setText(
                f"<i>data/raw/ does not exist at <code>{raw_dir}</code>.</i>"
            )
            self._load_selected_source_btn.setEnabled(False)
            return

        rows = _scan_data_sources(raw_dir)
        if not rows:
            self._sources_label.setText(
                f"<i>No raw data found under <code>{raw_dir}</code>. "
                "Drop your Polar/Empatica/Kubios/HRV-Logger files into "
                "subfolders here and reopen the project.</i>"
            )
            self._load_selected_source_btn.setEnabled(False)
            return

        total = sum(r["count"] for r in rows)
        self._sources_label.setText(
            f"<b>{total}</b> raw file(s) across <b>{len(rows)}</b> source(s) "
            f"in <code>{raw_dir}</code>. Double-click a file to open, "
            "right-click a folder for bulk-load."
        )
        for row in rows:
            folder_path = row.get("path", raw_dir / row["folder"])
            top = QTreeWidgetItem(
                [
                    f"{row['folder']}/",
                    str(row["label"]),
                    f"{row['count']} file(s)",
                ]
            )
            top.setData(0, Qt.UserRole, str(folder_path))
            top.setToolTip(0, str(folder_path))
            # Children: actual files (best-effort, skip on permission errors).
            try:
                files = sorted(p for p in folder_path.iterdir() if p.is_file())
            except OSError:
                files = []
            for fp in files:
                try:
                    size = fp.stat().st_size
                except OSError:
                    size = 0
                size_str = (
                    f"{size:,} B"
                    if size < 1024
                    else f"{size / 1024:,.1f} KB"
                    if size < 1024 * 1024
                    else f"{size / (1024 * 1024):,.1f} MB"
                )
                child = QTreeWidgetItem(
                    [fp.name, fp.suffix.lstrip(".") or "-", size_str]
                )
                child.setData(0, Qt.UserRole, str(fp))
                child.setToolTip(0, str(fp))
                top.addChild(child)
            self._sources_tree.addTopLevelItem(top)
        # Expand all sources by default so the user sees the files.
        self._sources_tree.expandAll()
        self._load_selected_source_btn.setEnabled(True)

    def _refresh_participants_table(self) -> None:
        # Disable sorting during populate — otherwise inserting cells
        # while sorting is on shuffles rows mid-fill.
        import numpy as np

        self._participants_table.setSortingEnabled(False)
        self._participants_table.setRowCount(0)
        participants = self._collect_participants()
        cleaning_cfg = _current_cleaning_config()
        n_with_metrics = 0
        # Phase 24B — per-row issue tags so we can filter + count issues
        self._row_issue_tags: list[set[str]] = []
        for pid in sorted(participants.keys()):
            data = participants[pid] or {}
            dataset = self._find_dataset_for(pid)
            section_count = len(dataset.data.sections) if dataset is not None else 0
            has_artifacts = self._dataset_has_artifacts(dataset)
            has_nn = self._dataset_has_nn(dataset)

            # Streamlit-parity metrics: only computable when the dataset
            # is actually loaded in the workspace (we don't pre-scan raw
            # files to keep the table fast — user loads what they want
            # from the Raw-data tree, then metrics appear here).
            beats_str = "-"
            duration_str = "-"
            rr_mean_str = "-"
            events_str = "-"
            retained_str = "-"
            artifact_pct_str = "-"
            duplicates_str = "-"
            rr_range_str = "-"
            quality_label = "-"
            quality_colour: QColor | None = None
            # Phase 24B — per-participant issue tags, kept in sync with
            # the table row order so the filter / link counters work.
            row_tags: set[str] = set()
            n_events_int = 0

            if dataset is not None:
                d = dataset.data
                finite = np.isfinite(d.v) if d.v is not None else None
                if finite is not None and finite.any():
                    beats = int(finite.sum())
                    beats_str = str(beats)
                    duration_min = (d.t_end - d.t_start) / 60.0
                    duration_str = f"{duration_min:.1f}"
                    rr_mean_str = f"{float(d.v[finite].mean()):.0f}"
                    n_with_metrics += 1
                n_events_int = len(d.events)
                events_str = str(n_events_int)
                if n_events_int == 0:
                    row_tags.add("no_events")

                # Pull PreparationSummary (cached per id(dataset) +
                # cleaning-config signature). Returns None when the
                # dataset has nothing finite to clean.
                summary = compute_inspector_summary(dataset, cleaning_cfg)
                if summary is not None:
                    retained_str = str(summary.retained_beats)
                    artifact_pct_str = f"{summary.artifact_ratio * 100:.1f}%"
                    duplicates_str = str(summary.duplicate_rr_intervals)
                    rr_range_str = (
                        f"{int(summary.rr_min_ms)}-{int(summary.rr_max_ms)} ms"
                    )
                    quality_label, quality_colour = _quality_for(summary.artifact_ratio)
                    if summary.artifact_ratio > 0.15:
                        row_tags.add("high_artifact")
                    if summary.duplicate_rr_intervals > 0:
                        row_tags.add("duplicates")

            self._row_issue_tags.append(row_tags)
            r = self._participants_table.rowCount()
            self._participants_table.insertRow(r)
            self._participants_table.setItem(r, COL_ID, QTableWidgetItem(pid))
            self._participants_table.setItem(
                r, COL_GROUP, QTableWidgetItem(str(data.get("group") or ""))
            )
            self._participants_table.setItem(
                r, COL_SEQUENCE, QTableWidgetItem(str(data.get("sequence") or ""))
            )
            for col, txt in (
                (COL_BEATS, beats_str),
                (COL_DURATION, duration_str),
                (COL_RR_MEAN, rr_mean_str),
                (COL_RETAINED, retained_str),
                (COL_ARTIFACT_PCT, artifact_pct_str),
                (COL_DUPLICATES, duplicates_str),
                (COL_RR_RANGE, rr_range_str),
                (COL_EVENTS, events_str),
                (COL_SECTIONS, str(section_count)),
            ):
                it = QTableWidgetItem(txt)
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self._participants_table.setItem(r, col, it)
            self._participants_table.setItem(
                r,
                COL_HAS_ARTIFACTS,
                QTableWidgetItem("Yes" if has_artifacts else "No"),
            )
            self._participants_table.setItem(
                r, COL_HAS_NN, QTableWidgetItem("Yes" if has_nn else "No")
            )
            quality_item = QTableWidgetItem(quality_label)
            quality_item.setTextAlignment(Qt.AlignCenter)
            if quality_colour is not None:
                quality_item.setForeground(quality_colour)
            self._participants_table.setItem(r, COL_QUALITY, quality_item)
        self._participants_table.setSortingEnabled(True)

        n_participants = len(participants)
        n_datasets = len(self._main_window._datasets)
        suffix = ""
        if n_datasets > 0 and n_with_metrics < n_datasets:
            # Highlight that some loaded datasets had no usable RR data.
            suffix = f" · {n_with_metrics} with usable metrics"
        elif n_datasets > 0:
            suffix = " · metrics from loaded datasets"
        self._participants_summary.setText(
            f"{n_participants} participant(s) registered · "
            f"{n_datasets} dataset(s) loaded{suffix}. "
            "<i>Beats / Duration / RR mean / Retained / Artifacts % populate "
            "as you load files from the Raw-data tree above. Adjust "
            "thresholds and click Apply &amp; refresh to recompute.</i>"
        )

        # Phase 24B — issues summary banner + active-filter application.
        self._refresh_issues_label()
        self._apply_issues_filter()

    def _refresh_issues_label(self) -> None:
        """Mirror Streamlit Data tab lines 810-839: count rows per issue."""
        n_high_artifact = sum(
            1 for tags in self._row_issue_tags if "high_artifact" in tags
        )
        n_duplicates = sum(1 for tags in self._row_issue_tags if "duplicates" in tags)
        n_no_events = sum(1 for tags in self._row_issue_tags if "no_events" in tags)
        bits: list[str] = []
        if n_high_artifact:
            bits.append(
                f"<a href='high_artifact'>{n_high_artifact} with &gt;15% artifacts</a>"
            )
        if n_duplicates:
            bits.append(f"<a href='duplicates'>{n_duplicates} with duplicates</a>")
        if n_no_events:
            bits.append(f"<a href='no_events'>{n_no_events} with no events</a>")
        if not bits:
            self._issues_label.setText(
                "<b>Issues:</b> <span style='color:#1a7a1a'>none detected</span>"
            )
        else:
            text = "<b>Issues:</b> " + " | ".join(bits)
            if self._issues_filter is not None:
                text += " &middot; <a href='clear'>show all</a>"
            self._issues_label.setText(text)

    def _apply_issues_filter(self) -> None:
        """Hide rows that don't carry the active filter tag."""
        if self._issues_filter is None:
            for r in range(self._participants_table.rowCount()):
                self._participants_table.setRowHidden(r, False)
            return
        for r, tags in enumerate(self._row_issue_tags):
            self._participants_table.setRowHidden(r, self._issues_filter not in tags)

    def _on_issues_link(self, href: str) -> None:
        """A filter link was clicked — apply it (or clear)."""
        if href == "clear":
            self._issues_filter = None
        else:
            self._issues_filter = href
        # Refresh summary so the "show all" hint toggles.
        self._refresh_issues_label()
        self._apply_issues_filter()

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

    # ------------------------------------------------------------------
    # Phase 24B — participants CSV download
    # ------------------------------------------------------------------
    def _suggested_participants_csv_name(self) -> str:
        proj = getattr(self._main_window, "_project", None)
        if proj is not None and proj.metadata is not None:
            stem = proj.metadata.name
        elif proj is not None:
            stem = proj.project_path.name
        else:
            stem = "workspace"
        return f"participants_{stem}.csv"

    # Public hook the tests use to bypass QFileDialog.
    def export_participants_csv(self, out_path: Path) -> int:
        """Write the live participants table as a CSV. Returns row count.

        Includes a fixed column set inspired by the Streamlit
        download_button: ID / Group / Sequence / Beats / Duration /
        Artifacts % / Duplicates / Quality. We pull cell text directly
        so the file matches what the user sees.
        """
        import csv as _csv

        cols = [
            (COL_ID, "ID"),
            (COL_GROUP, "Group"),
            (COL_SEQUENCE, "Sequence"),
            (COL_BEATS, "Beats"),
            (COL_DURATION, "Duration (min)"),
            (COL_ARTIFACT_PCT, "Artifacts %"),
            (COL_DUPLICATES, "Duplicates"),
            (COL_QUALITY, "Quality"),
        ]
        rows_written = 0
        with out_path.open("w", newline="", encoding="utf-8") as fh:
            writer = _csv.writer(fh)
            writer.writerow([h for _i, h in cols])
            for r in range(self._participants_table.rowCount()):
                row_cells: list[str] = []
                for col_idx, _h in cols:
                    item = self._participants_table.item(r, col_idx)
                    row_cells.append(item.text() if item is not None else "")
                writer.writerow(row_cells)
                rows_written += 1
        return rows_written

    def _on_export_participants_csv_clicked(self) -> None:
        suggested = self._suggested_participants_csv_name()
        if getattr(self._main_window, "test_mode", False):
            # In test mode just emit a status — tests call
            # export_participants_csv directly to verify the writer.
            self._main_window.statusBar().showMessage(
                f"Participants CSV: would write {suggested}", 3000
            )
            return
        from rrational.inspector import settings as _settings

        start_dir = _settings.read_setting("last_dir") or str(Path.cwd())
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export participants CSV",
            str(Path(start_dir) / suggested),
            "CSV files (*.csv)",
        )
        if not path_str:
            return
        try:
            n = self.export_participants_csv(Path(path_str))
        except OSError as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        self._main_window.statusBar().showMessage(
            f"Exported {n} participant(s) to {path_str}", 4000
        )

    # ------------------------------------------------------------------
    # Phase 24B — Group / Sequence mapping CSV importer
    # ------------------------------------------------------------------
    def _on_import_mapping_clicked(self) -> None:
        dlg = ImportParticipantMappingDialog(self._main_window, parent=self)
        if dlg.exec() != dlg.Accepted:
            return
        result = dlg.result
        if result is None:
            return
        self.on_workspace_changed()
        self._main_window.statusBar().showMessage(result.summary(), 5000)
