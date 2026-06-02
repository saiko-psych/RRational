"""Top-level QMainWindow for the inspector.

Phase 1 spike: just enough to open a .rrational file, render its first
section's RR tachogram, and let the user scroll around. Sections list,
event markers, artifact editing, and project loading land in later phases.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from qtpy.QtGui import QKeySequence, QAction
from qtpy.QtWidgets import (
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QWidget,
    QVBoxLayout,
    QLabel,
)
from qtpy.QtCore import Qt

from rrational.inspector.plot_widget import RRPlotWidget


def _load_rrational_sections(filepath: Path) -> dict:
    """Read a .rrational v2 file and return ``{section_name: (timestamps, rr_ms)}``.

    Imports are deferred so the inspector module stays importable in
    environments that don't have NeuroKit2 installed (Streamlit-only setups).
    """
    from rrational.gui.rrational_export import (
        load_rrational_v2,
        get_rrational_version,
        RRATIONAL_VERSION_V2,
    )

    version = get_rrational_version(filepath)
    if version != RRATIONAL_VERSION_V2:
        raise ValueError(
            f"Inspector currently supports v2.0 .rrational files only "
            f"(got v{version} for {filepath.name}). Export a v2.0 file via "
            "the Streamlit app's 'Save All Validated Sections' button."
        )

    data = load_rrational_v2(filepath)
    sections: dict[str, tuple[list[datetime], list[float]]] = {}
    for sec_name, sec in data.sections.items():
        if not sec.nn_intervals or not sec.nn_intervals.data:
            continue
        # nn_intervals.data is a list of [timestamp_ms_offset, rr_ms, is_corrected]
        # Convert offsets back to absolute datetimes using the section's start.
        start_ts_str = sec.validation.start_event.timestamp if sec.validation else None
        if not start_ts_str:
            continue
        start_dt = datetime.fromisoformat(start_ts_str)
        timestamps: list[datetime] = []
        rr_ms: list[float] = []
        for row in sec.nn_intervals.data:
            offset_ms, rr, _ = row
            timestamps.append(start_dt + timedelta(milliseconds=offset_ms))
            rr_ms.append(float(rr))
        sections[sec_name] = (timestamps, rr_ms)
    return sections


class MainWindow(QMainWindow):
    def __init__(self, initial_path: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("RRational Inspector")
        self.resize(1400, 700)

        # ----- Central widget: section list (left) + plot (right) ---------
        self._sections: dict = {}
        self._section_list = QListWidget()
        self._section_list.itemClicked.connect(self._on_section_selected)
        self._section_list.setMaximumWidth(260)

        self._plot = RRPlotWidget()
        self._plot.setFocusPolicy(Qt.StrongFocus)  # so it receives keyboard events

        self._empty_label = QLabel(
            "No .rrational file loaded.\n\n"
            "Use File → Open .rrational… (Ctrl+O) to load a v2.0 export."
        )
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #666; font-size: 14px;")

        center = QSplitter(Qt.Horizontal)
        center.addWidget(self._section_list)

        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self._empty_label)
        right_layout.addWidget(self._plot)
        self._plot.setVisible(False)
        center.addWidget(right_pane)
        center.setStretchFactor(0, 0)
        center.setStretchFactor(1, 1)

        self.setCentralWidget(center)

        # ----- Menu & status bar ------------------------------------------
        self._build_menu()
        self.setStatusBar(QStatusBar())

        # ----- Optionally open a file at startup --------------------------
        if initial_path is not None:
            self._open_path(initial_path)

    # ------------------------------------------------------------------
    def _build_menu(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")

        open_act = QAction("Open .rrational…", self)
        open_act.setShortcut(QKeySequence.Open)  # Ctrl+O / Cmd+O
        open_act.triggered.connect(self._on_open_clicked)
        file_menu.addAction(open_act)

        file_menu.addSeparator()

        quit_act = QAction("Quit", self)
        quit_act.setShortcut(QKeySequence.Quit)  # Ctrl+Q / Cmd+Q
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

    # ------------------------------------------------------------------
    def _on_open_clicked(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open .rrational",
            str(Path.cwd()),
            "RRational v2.0 (*.rrational);;All files (*.*)",
        )
        if path_str:
            self._open_path(Path(path_str))

    def _open_path(self, path: Path) -> None:
        if not path.exists():
            QMessageBox.warning(self, "Not found", f"{path} does not exist.")
            return
        try:
            self._sections = _load_rrational_sections(path)
        except Exception as e:
            QMessageBox.critical(self, "Could not load", str(e))
            return

        self._section_list.clear()
        for name, (ts, rr) in self._sections.items():
            label = (
                f"{name}  ({len(rr)} beats, {(ts[-1] - ts[0]).total_seconds():.0f}s)"
            )
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, name)
            self._section_list.addItem(item)

        self.statusBar().showMessage(
            f"Loaded {path.name} — {len(self._sections)} section(s) with NN data"
        )
        # Auto-select the first section
        if self._section_list.count() > 0:
            self._section_list.setCurrentRow(0)
            self._on_section_selected(self._section_list.item(0))
        else:
            QMessageBox.information(
                self,
                "No sections",
                f"{path.name} contains no sections with NN data to display.",
            )

    def _on_section_selected(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.UserRole)
        if name not in self._sections:
            return
        timestamps, rr_ms = self._sections[name]
        self._empty_label.setVisible(False)
        self._plot.setVisible(True)
        self._plot.set_data(timestamps, rr_ms)
        self._plot.setFocus()  # so keyboard nav works immediately after click
        self.statusBar().showMessage(
            f"Section '{name}': {len(rr_ms)} beats, "
            f"{(timestamps[-1] - timestamps[0]).total_seconds():.1f}s"
        )
