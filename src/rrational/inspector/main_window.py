"""Top-level QMainWindow for the RR inspector.

Phase 2 UX: ONE continuous timeline is rendered on file load — every
section in the .rrational v2 file is concatenated into a single
tachogram with NaN gaps for breaks, colored ``SectionRegion`` bands
mark the section spans, and ``EventMarker`` lines stand at each
section-boundary event.

The sidebar still lists sections (now sorted by start time), but
clicking one no longer swaps the plot data — it zooms the viewport
to that section's time range and highlights its band. This mirrors
mne-qt-browser's "channels list + main plot" interaction model.

Architectural choices borrowed from mne-qt-browser:
- one shared state container (here: ``InspectorData`` from data_loader)
- overlays as separate graphic items with strong Python refs
- public navigation API on MainWindow so toolbar + key filter share it
- test_mode flag so non-modal dialogs don't block pytest-qt runs
"""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import QEvent, QObject, Qt
from qtpy.QtGui import QAction, QKeySequence
from qtpy.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from rrational.inspector.data_loader import InspectorData, load_inspector_data
from rrational.inspector.plot_widget import RRPlotWidget


class _GlobalKeyFilter(QObject):
    """Application-wide event filter that routes Home/End to the plot.

    QListWidget (sidebar) consumes Home/End for its own list navigation,
    and QGraphicsView (PlotWidget's base class) consumes them for its
    scroll-area handling. Both swallow the event before any QShortcut
    — even one with ApplicationShortcut context — can fire. An
    eventFilter installed on QApplication sees every key press FIRST,
    so we can intercept Home/End no matter which widget has the focus.
    """

    def __init__(self, window: "MainWindow") -> None:
        super().__init__()
        self._window = window

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 — Qt API name
        if event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Home:
                self._window.jump_to_start()
                return True
            if key == Qt.Key_End:
                self._window.jump_to_end()
                return True
        return False


class MainWindow(QMainWindow):
    """Inspector main window: sidebar + toolbar + continuous timeline plot."""

    def __init__(self, initial_path: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("RRational Inspector")
        self.resize(1400, 700)

        # Flipped on by pytest fixtures so modal QMessageBox calls don't
        # block headless test runs. Same convention as mne-qt-browser's
        # ``test_mode`` flag.
        self.test_mode = False

        # Currently-loaded data (None until the user opens a file).
        self._data: InspectorData | None = None
        self._loaded_path: Path | None = None

        self._build_central_widget()
        self._build_menu()
        self._build_toolbar()
        self.setStatusBar(QStatusBar())

        self._key_filter = _GlobalKeyFilter(self)
        QApplication.instance().installEventFilter(self._key_filter)

        if initial_path is not None:
            self._open_path(initial_path)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_central_widget(self) -> None:
        self._section_list = QListWidget()
        self._section_list.itemClicked.connect(self._on_section_clicked)
        self._section_list.setMaximumWidth(280)

        self._plot = RRPlotWidget()
        self._plot.setFocusPolicy(Qt.StrongFocus)

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

    def _build_toolbar(self) -> None:
        """Toolbar with discoverable navigation buttons.

        Home/End/arrows work via keyboard, but surfacing them as
        clickable buttons makes the feature discoverable for users
        who don't read the docstring.
        """
        tb = QToolBar("Navigation", self)
        tb.setMovable(False)
        self.addToolBar(tb)

        home_act = QAction("Start (Home)", self)
        home_act.setToolTip("Jump to beginning of signal (Home)")
        home_act.triggered.connect(self.jump_to_start)
        tb.addAction(home_act)

        end_act = QAction("End (End)", self)
        end_act.setToolTip("Jump to end of signal (End)")
        end_act.triggered.connect(self.jump_to_end)
        tb.addAction(end_act)

        tb.addSeparator()

        pan_l = QAction("Pan left", self)
        pan_l.setToolTip("Pan left (Left arrow)")
        pan_l.triggered.connect(
            lambda: self._with_feedback(self._plot.pan_left, "Pan left")
        )
        tb.addAction(pan_l)

        pan_r = QAction("Pan right", self)
        pan_r.setToolTip("Pan right (Right arrow)")
        pan_r.triggered.connect(
            lambda: self._with_feedback(self._plot.pan_right, "Pan right")
        )
        tb.addAction(pan_r)

        tb.addSeparator()

        zoom_in = QAction("Zoom in", self)
        zoom_in.setToolTip("Zoom in (Down arrow)")
        zoom_in.triggered.connect(
            lambda: self._with_feedback(self._plot.zoom_in, "Zoom in")
        )
        tb.addAction(zoom_in)

        zoom_out = QAction("Zoom out", self)
        zoom_out.setToolTip("Zoom out (Up arrow)")
        zoom_out.triggered.connect(
            lambda: self._with_feedback(self._plot.zoom_out, "Zoom out")
        )
        tb.addAction(zoom_out)

        tb.addSeparator()

        fit_all = QAction("Fit all", self)
        fit_all.setToolTip("Zoom out to show the entire recording")
        fit_all.triggered.connect(self.fit_all)
        tb.addAction(fit_all)

    # ------------------------------------------------------------------
    # Public navigation API
    # ------------------------------------------------------------------
    def jump_to_start(self) -> None:
        if self._plot._times is None:
            self.statusBar().showMessage("Home: no file loaded", 2000)
            return
        self._plot.jump_start()
        self.statusBar().showMessage("Jumped to start of signal", 2000)

    def jump_to_end(self) -> None:
        if self._plot._times is None:
            self.statusBar().showMessage("End: no file loaded", 2000)
            return
        self._plot.jump_end()
        self.statusBar().showMessage("Jumped to end of signal", 2000)

    def fit_all(self) -> None:
        """Zoom the X-axis out to the full recording span."""
        if self._data is None:
            self.statusBar().showMessage("Fit all: no file loaded", 2000)
            return
        self._plot.zoom_to_range(
            self._data.t_start, self._data.t_end, padding_frac=0.01
        )
        self.statusBar().showMessage("Showing full recording", 1500)

    def _with_feedback(self, action, label: str) -> None:
        action()
        self.statusBar().showMessage(label, 1500)

    # ------------------------------------------------------------------
    # File loading
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
            self._warn("Not found", f"{path} does not exist.")
            return
        try:
            data = load_inspector_data(path)
        except Exception as e:
            self._critical("Could not load", str(e))
            return

        if len(data.t) == 0:
            self._info(
                "No sections",
                f"{path.name} contains no sections with NN data to display.",
            )
            return

        self.load_data(data, source_path=path)

    # ------------------------------------------------------------------
    # Public data API — used directly by tests so they can inject
    # synthetic InspectorData without round-tripping through a real file.
    # ------------------------------------------------------------------
    def load_data(self, data: InspectorData, source_path: Path | None = None) -> None:
        """Render an ``InspectorData`` instance in the plot."""
        self._data = data
        self._loaded_path = source_path

        # 1. Render the continuous timeline
        self._empty_label.setVisible(False)
        self._plot.setVisible(True)
        self._plot.set_data(data)

        # 2. Overlay section bands
        for meta in data.sections:
            self._plot.add_section_region(meta)

        # 3. Overlay event markers
        for ev in data.events:
            self._plot.add_event_marker(ev)

        # 4. Populate sidebar (sorted by start time, same order as overlays)
        self._section_list.clear()
        for meta in data.sections:
            duration = meta.t_end - meta.t_start
            label = f"{meta.name}  ({meta.beat_count} beats, {duration:.0f}s)"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, meta.name)
            self._section_list.addItem(item)

        # 5. Status bar summary
        msg = (
            f"{source_path.name if source_path else 'Data'} — "
            f"{len(data.sections)} section(s), "
            f"{len(data.events)} event(s), "
            f"{data.t_end - data.t_start:.0f}s total"
        )
        self.statusBar().showMessage(msg)

        self._plot.setFocus()

    def _on_section_clicked(self, item: QListWidgetItem) -> None:
        """Zoom the plot to the clicked section and highlight its band."""
        name = item.data(Qt.UserRole)
        if self._data is None:
            return
        meta = next((s for s in self._data.sections if s.name == name), None)
        if meta is None:
            return
        self._plot.zoom_to_range(meta.t_start, meta.t_end, padding_frac=0.02)
        self._plot.highlight_section(name)
        self._plot.setFocus()
        self.statusBar().showMessage(
            f"Section '{name}': {meta.beat_count} beats, "
            f"{meta.t_end - meta.t_start:.1f}s",
            3000,
        )

    # ------------------------------------------------------------------
    # Dialog helpers — silenced in test_mode so pytest-qt doesn't block.
    # ------------------------------------------------------------------
    def _warn(self, title: str, msg: str) -> None:
        if self.test_mode:
            self.statusBar().showMessage(f"{title}: {msg}")
            return
        QMessageBox.warning(self, title, msg)

    def _critical(self, title: str, msg: str) -> None:
        if self.test_mode:
            self.statusBar().showMessage(f"{title}: {msg}")
            return
        QMessageBox.critical(self, title, msg)

    def _info(self, title: str, msg: str) -> None:
        if self.test_mode:
            self.statusBar().showMessage(f"{title}: {msg}")
            return
        QMessageBox.information(self, title, msg)
