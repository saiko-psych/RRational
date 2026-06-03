"""Top-level QMainWindow for the RR inspector.

Phase 3a: multi-dataset workspace. The user can open several .rrational
files in parallel; the sidebar becomes a ``QTreeWidget`` with one
top-level node per file and the file's sections as children. Click a
filename to switch the active dataset; click a section to zoom into it.

File menu mirrors MNELAB conventions: Open, Open folder, Recent (with
existence-check + auto-purge), Close current, Close all, Quit. Recent
files persist via ``QSettings`` (Windows registry / macOS plist /
Linux INI).

Backward-compat with Phase 2 tests:
- ``load_data(data, source_path)`` still closes all + loads one
- ``_data`` and ``_loaded_path`` remain readable as the ACTIVE dataset
"""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import QEvent, QObject, Qt
from qtpy.QtGui import QAction, QFont, QKeySequence
from qtpy.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QToolBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rrational.inspector import settings
from rrational.inspector.data_loader import Dataset, InspectorData
from rrational.inspector.overview_bar import OverviewBar
from rrational.inspector.plot_widget import RRPlotWidget

# UserRole payload tags so itemClicked can distinguish "dataset node"
# from "section node" without sniffing the parent.
_ROLE_DATASET_IDX = Qt.UserRole + 1
_ROLE_SECTION_NAME = Qt.UserRole + 2


class _GlobalKeyFilter(QObject):
    """Application-wide event filter that routes Home/End to the plot.

    QTreeWidget (sidebar) consumes Home/End for its own tree navigation,
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
    """Inspector main window: dataset tree + toolbar + continuous timeline."""

    def __init__(self, initial_path: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("RRational Inspector")
        self.resize(1400, 700)

        # Flipped on by pytest fixtures so modal QMessageBox calls don't
        # block headless test runs.
        self.test_mode = False

        # The workspace: every loaded file lives here. Active index
        # points at the one currently rendered in the plot.
        self._datasets: list[Dataset] = []
        self._active_idx: int | None = None

        # Recent-files actions get rebuilt every time the File menu
        # opens, so we keep a handle on the submenu itself.
        self._recent_menu = None

        self._build_central_widget()
        self._build_menu()
        self._build_toolbar()
        self.setStatusBar(QStatusBar())
        # Permanent (always-visible) widget on the right side of the
        # status bar. addPermanentWidget keeps it visible even when
        # showMessage() displays a transient message on the left.
        self.statusBar().addPermanentWidget(self._cursor_readout)

        self._key_filter = _GlobalKeyFilter(self)
        QApplication.instance().installEventFilter(self._key_filter)

        if initial_path is not None:
            self.open_path(initial_path)

    # ------------------------------------------------------------------
    # Backward-compat properties: lots of tests still read ``_data`` /
    # ``_loaded_path``. They map to the ACTIVE dataset now.
    # ------------------------------------------------------------------
    @property
    def _data(self) -> InspectorData | None:
        if self._active_idx is None:
            return None
        return self._datasets[self._active_idx].data

    @property
    def _loaded_path(self) -> Path | None:
        if self._active_idx is None:
            return None
        return self._datasets[self._active_idx].path

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_central_widget(self) -> None:
        self._dataset_tree = QTreeWidget()
        self._dataset_tree.setHeaderHidden(True)
        self._dataset_tree.setIndentation(14)
        self._dataset_tree.itemClicked.connect(self._on_tree_item_clicked)
        self._dataset_tree.setMaximumWidth(320)

        self._plot = RRPlotWidget()
        self._plot.setFocusPolicy(Qt.StrongFocus)

        # Mini-map above the main plot, bound bidirectionally — the
        # rectangle in the overview tracks the main plot's viewport,
        # and dragging the rectangle pans/zooms the main plot.
        self._overview_bar = OverviewBar()
        self._overview_bar.link_to(self._plot)

        # Permanent label on the right side of the status bar — shows
        # the (time, RR) reading under the cursor. Stays alongside the
        # transient status messages from navigation / file ops.
        self._cursor_readout = QLabel("")
        self._cursor_readout.setStyleSheet("color: #555; padding-right: 8px;")
        self._plot.cursor_moved.connect(self._update_cursor_readout)
        self._plot.cursor_left.connect(self._clear_cursor_readout)

        self._empty_label = QLabel(
            "No .rrational file loaded.\n\n"
            "Use File → Open .rrational… (Ctrl+O) to load a v2.0 export,\n"
            "or File → Open folder… to load every .rrational in a directory."
        )
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #666; font-size: 14px;")

        center = QSplitter(Qt.Horizontal)
        center.addWidget(self._dataset_tree)

        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self._empty_label)
        right_layout.addWidget(self._overview_bar)
        right_layout.addWidget(self._plot)
        self._plot.setVisible(False)
        self._overview_bar.setVisible(False)
        center.addWidget(right_pane)
        center.setStretchFactor(0, 0)
        center.setStretchFactor(1, 1)

        self.setCentralWidget(center)

    def _build_menu(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")

        open_act = QAction("&Open .rrational…", self)
        open_act.setShortcut(QKeySequence.Open)  # Ctrl+O / Cmd+O
        open_act.setStatusTip("Open one or more .rrational v2.0 files")
        open_act.triggered.connect(self._on_open_clicked)
        file_menu.addAction(open_act)

        open_folder_act = QAction("Open &folder…", self)
        open_folder_act.setShortcut("Ctrl+Shift+O")
        open_folder_act.setStatusTip(
            "Load every .rrational file inside a chosen folder"
        )
        open_folder_act.triggered.connect(self._on_open_folder_clicked)
        file_menu.addAction(open_folder_act)

        self._recent_menu = file_menu.addMenu("Open &recent")
        # Rebuild the recent list every time the user opens File menu
        # (so deletions made outside the app are reflected).
        file_menu.aboutToShow.connect(self._rebuild_recent_menu)
        self._rebuild_recent_menu()

        file_menu.addSeparator()

        close_act = QAction("&Close current dataset", self)
        close_act.setShortcut("Ctrl+W")
        close_act.triggered.connect(self.close_active_dataset)
        file_menu.addAction(close_act)

        close_all_act = QAction("Close &all datasets", self)
        close_all_act.triggered.connect(self.close_all_datasets)
        file_menu.addAction(close_all_act)

        file_menu.addSeparator()

        quit_act = QAction("&Quit", self)
        quit_act.setShortcut(QKeySequence.Quit)  # Ctrl+Q / Cmd+Q
        quit_act.triggered.connect(self.close)
        file_menu.addAction(quit_act)

        # ----- View menu --------------------------------------------------
        # Checkable toggles that persist via QSettings. Each action's
        # initial check state is read from settings at construction time,
        # and re-saved whenever the user flips it.
        view_menu = menubar.addMenu("&View")

        self._toggle_sidebar_act = self._make_view_toggle(
            view_menu,
            "Show &sidebar",
            settings_key="show_sidebar",
            on_change=self._dataset_tree.setVisible,
        )
        self._toggle_overview_act = self._make_view_toggle(
            view_menu,
            "Show &overview bar",
            settings_key="show_overview_bar",
            on_change=self._set_overview_visible,
        )
        view_menu.addSeparator()
        self._toggle_sections_act = self._make_view_toggle(
            view_menu,
            "Show section &bands",
            settings_key="show_sections",
            on_change=self._plot.set_sections_visible,
        )
        self._toggle_events_act = self._make_view_toggle(
            view_menu,
            "Show &event markers",
            settings_key="show_events",
            on_change=self._plot.set_events_visible,
        )
        self._toggle_grid_act = self._make_view_toggle(
            view_menu,
            "Show &grid",
            settings_key="show_grid" if "show_grid" in settings._DEFAULTS else None,
            on_change=self._plot.set_grid_visible,
            default=True,
        )
        self._toggle_crosshair_act = self._make_view_toggle(
            view_menu,
            "Show &crosshair",
            settings_key="show_crosshair",
            on_change=self._plot.set_crosshair_visible,
        )

        # ----- Edit menu --------------------------------------------------
        edit_menu = menubar.addMenu("&Edit")
        prefs_act = QAction("&Preferences…", self)
        prefs_act.setShortcut("Ctrl+,")
        prefs_act.setStatusTip("Inspector preferences (not yet implemented)")
        prefs_act.triggered.connect(self._on_preferences_clicked)
        edit_menu.addAction(prefs_act)

        # ----- Tools menu — stubs for upcoming Phase 4 features ----------
        tools_menu = menubar.addMenu("&Tools")
        for label, status in [
            ("Compute &HRV metrics…", "Coming in Phase 4"),
            ("Detect &artifacts…", "Coming in Phase 4"),
            ("&Crop section…", "Coming in Phase 4"),
        ]:
            act = QAction(label, self)
            act.setEnabled(False)
            act.setStatusTip(status)
            tools_menu.addAction(act)

        # ----- Help menu --------------------------------------------------
        help_menu = menubar.addMenu("&Help")
        shortcuts_act = QAction("Keyboard &shortcuts", self)
        shortcuts_act.setShortcut("F1")
        shortcuts_act.triggered.connect(self._show_shortcuts_dialog)
        help_menu.addAction(shortcuts_act)

        about_act = QAction("&About RRational Inspector", self)
        about_act.triggered.connect(self._show_about_dialog)
        help_menu.addAction(about_act)

    # ------------------------------------------------------------------
    # View-menu helpers
    # ------------------------------------------------------------------
    def _make_view_toggle(
        self,
        menu,
        label: str,
        settings_key: str | None,
        on_change,
        default: bool = True,
    ) -> QAction:
        """Build a checkable view-menu action that persists via QSettings."""
        act = QAction(label, self)
        act.setCheckable(True)

        if settings_key and settings_key in settings._DEFAULTS:
            initial = settings.read_setting(settings_key)
        else:
            initial = default
        act.setChecked(bool(initial))
        on_change(bool(initial))

        def _on_toggled(checked: bool, key=settings_key):
            on_change(checked)
            if key and not self.test_mode:
                settings.write_setting(key, checked)

        act.toggled.connect(_on_toggled)
        menu.addAction(act)
        return act

    def _update_cursor_readout(self, t: float, v: float) -> None:
        """Format the (time, RR) reading from the plot's cursor signal."""
        from datetime import datetime
        import math

        time_str = datetime.fromtimestamp(t).strftime("%H:%M:%S")
        if math.isnan(v):
            val_str = "—"
        else:
            val_str = f"{v:.1f} ms"
        self._cursor_readout.setText(f"t: {time_str}  ·  RR: {val_str}")

    def _clear_cursor_readout(self) -> None:
        self._cursor_readout.setText("")

    def _set_overview_visible(self, visible: bool) -> None:
        """Show the overview bar only when there's data AND the toggle is on."""
        if visible and self._data is not None:
            self._overview_bar.setVisible(True)
        else:
            self._overview_bar.setVisible(False)

    def _on_preferences_clicked(self) -> None:
        """Stub — real Preferences dialog lands in a later sub-phase."""
        self._info(
            "Preferences",
            "A full Preferences dialog will be added in a follow-up.\n\n"
            "For now, View-menu toggles persist automatically across runs.",
        )

    def _show_shortcuts_dialog(self) -> None:
        """Modeless dialog listing every shortcut the inspector binds."""
        text = (
            "<h3>Keyboard shortcuts</h3>"
            "<table cellpadding='4'>"
            "<tr><td><b>Ctrl+O</b></td><td>Open .rrational file(s)</td></tr>"
            "<tr><td><b>Ctrl+Shift+O</b></td><td>Open folder of files</td></tr>"
            "<tr><td><b>Ctrl+W</b></td><td>Close current dataset</td></tr>"
            "<tr><td><b>Ctrl+Q</b></td><td>Quit</td></tr>"
            "<tr><td><b>Ctrl+,</b></td><td>Preferences</td></tr>"
            "<tr><td colspan='2'><hr></td></tr>"
            "<tr><td><b>Home</b></td><td>Jump to start of recording</td></tr>"
            "<tr><td><b>End</b></td><td>Jump to end of recording</td></tr>"
            "<tr><td><b>Left / Right</b></td><td>Pan 25% of viewport</td></tr>"
            "<tr><td><b>Up / Down</b></td><td>Zoom out / Zoom in</td></tr>"
            "<tr><td><b>Mouse drag</b></td><td>Pan plot</td></tr>"
            "<tr><td><b>Mouse wheel</b></td><td>Zoom around cursor</td></tr>"
            "<tr><td><b>Right-click</b></td><td>Plot context menu</td></tr>"
            "<tr><td colspan='2'><hr></td></tr>"
            "<tr><td><b>F1</b></td><td>This dialog</td></tr>"
            "</table>"
        )
        if self.test_mode:
            self.statusBar().showMessage("Shortcuts dialog (test_mode: suppressed)")
            return
        QMessageBox.information(self, "Keyboard shortcuts", text)

    def _show_about_dialog(self) -> None:
        if self.test_mode:
            self.statusBar().showMessage("About dialog (test_mode: suppressed)")
            return
        QMessageBox.about(
            self,
            "About RRational Inspector",
            "<h3>RRational Inspector</h3>"
            "<p>Scrollable RR-interval browser for the RRational HRV toolkit.</p>"
            "<p>Built with PyQtGraph + PySide6. Architecture inspired by "
            "<a href='https://github.com/mne-tools/mne-qt-browser'>mne-qt-browser</a> "
            "and <a href='https://github.com/cbrnr/mnelab'>MNELAB</a>.</p>"
            "<p>Project: <a href='https://github.com/saiko-psych/rrational'>"
            "github.com/saiko-psych/rrational</a></p>",
        )

    def _build_toolbar(self) -> None:
        """Toolbar with discoverable navigation buttons."""
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
    # Recent files submenu (rebuilt on every File-menu open)
    # ------------------------------------------------------------------
    def _rebuild_recent_menu(self) -> None:
        if self._recent_menu is None:
            return
        self._recent_menu.clear()
        try:
            recents = settings.get_recent_files()
        except Exception:
            recents = []

        if not recents:
            empty = QAction("(no recent files)", self)
            empty.setEnabled(False)
            self._recent_menu.addAction(empty)
            return

        for p in recents:
            # Capture ``p`` by default-argument trick — Python's late
            # binding of for-loop variables would otherwise make every
            # action open the LAST file in the list.
            act = QAction(p.name, self)
            act.setStatusTip(str(p))
            act.triggered.connect(lambda _checked=False, path=p: self.open_path(path))
            self._recent_menu.addAction(act)

        self._recent_menu.addSeparator()
        clear_act = QAction("Clear recent files", self)
        clear_act.triggered.connect(self._clear_recent)
        self._recent_menu.addAction(clear_act)

    def _clear_recent(self) -> None:
        settings.clear_recent_files()
        self._rebuild_recent_menu()

    # ------------------------------------------------------------------
    # Public navigation API (toolbar + key filter share this)
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
    # File dialogs
    # ------------------------------------------------------------------
    def _on_open_clicked(self) -> None:
        last_dir = settings.read_setting("last_dir") or str(Path.cwd())
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open .rrational",
            last_dir,
            "RRational v2.0 (*.rrational);;All files (*.*)",
        )
        for path_str in paths:
            self.open_path(Path(path_str))

    def _on_open_folder_clicked(self) -> None:
        last_dir = settings.read_setting("last_dir") or str(Path.cwd())
        folder_str = QFileDialog.getExistingDirectory(
            self, "Open folder containing .rrational files", last_dir
        )
        if not folder_str:
            return
        folder = Path(folder_str)
        files = sorted(folder.glob("*.rrational"))
        if not files:
            self._info(
                "No files found",
                f"No .rrational files in {folder.name}.",
            )
            return
        for p in files:
            self.open_path(p)

    # ------------------------------------------------------------------
    # Public dataset API
    # ------------------------------------------------------------------
    def open_path(self, path: Path) -> int | None:
        """Load a .rrational file and add it as a new dataset.

        Returns the new dataset's index, or None on failure. Activates
        the new dataset if it's the first one loaded; otherwise leaves
        the active selection alone (the user explicitly switches).
        """
        if not path.exists():
            self._warn("Not found", f"{path} does not exist.")
            return None
        try:
            ds = Dataset.from_path(path)
        except Exception as e:
            self._critical("Could not load", str(e))
            return None

        if len(ds.data.t) == 0:
            self._info(
                "No sections",
                f"{path.name} contains no sections with NN data to display.",
            )
            return None

        # Persist last-dir + bump in recent files (skip during tests so
        # the user's preference history isn't polluted by CI runs).
        if not self.test_mode:
            settings.write_setting("last_dir", str(path.parent))
            settings.add_recent_file(path)

        idx = self.add_dataset(ds)
        if self._active_idx is None:
            self.set_active_dataset(idx)
        return idx

    def add_dataset(self, ds: Dataset) -> int:
        """Append a dataset to the workspace. Returns its index."""
        self._datasets.append(ds)
        self._add_dataset_to_tree(len(self._datasets) - 1, ds)
        return len(self._datasets) - 1

    def set_active_dataset(self, idx: int) -> None:
        """Switch which dataset is currently rendered in the plot."""
        if not (0 <= idx < len(self._datasets)):
            raise IndexError(f"invalid dataset index: {idx}")
        self._active_idx = idx
        ds = self._datasets[idx]
        self._render_dataset(ds)
        self._update_tree_active_marker()
        self.setWindowTitle(f"RRational Inspector — {ds.name}")

    def close_active_dataset(self) -> None:
        """Remove the currently-active dataset from the workspace."""
        if self._active_idx is None:
            self.statusBar().showMessage("Close: no active dataset", 2000)
            return
        self.close_dataset(self._active_idx)

    def close_dataset(self, idx: int) -> None:
        if not (0 <= idx < len(self._datasets)):
            return
        del self._datasets[idx]

        # Re-index the active pointer. Three cases:
        # - closed the active one → activate the next-best, or none
        # - closed one BEFORE the active → shift active down by 1
        # - closed one AFTER the active → no shift
        if self._active_idx is None:
            pass
        elif idx == self._active_idx:
            self._active_idx = None
        elif idx < self._active_idx:
            self._active_idx -= 1

        # Re-render the sidebar from scratch (simpler than fiddling with
        # individual QTreeWidgetItems whose indices have shifted).
        self._rebuild_tree()

        if not self._datasets:
            self._show_empty_state()
        elif self._active_idx is None:
            # Auto-activate first remaining dataset for usability.
            self.set_active_dataset(0)

    def close_all_datasets(self) -> None:
        self._datasets.clear()
        self._active_idx = None
        self._rebuild_tree()
        self._show_empty_state()

    # ------------------------------------------------------------------
    # Phase-2 entry point retained for tests + scripts that don't care
    # about multi-dataset.
    # ------------------------------------------------------------------
    def load_data(self, data: InspectorData, source_path: Path | None = None) -> None:
        """Replace the workspace with ONE dataset built from ``data``."""
        self.close_all_datasets()
        name = source_path.name if source_path else "Untitled"
        idx = self.add_dataset(Dataset(name=name, data=data, path=source_path))
        self.set_active_dataset(idx)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _render_dataset(self, ds: Dataset) -> None:
        self._empty_label.setVisible(False)
        self._plot.setVisible(True)
        self._plot.set_data(ds.data)
        for meta in ds.data.sections:
            self._plot.add_section_region(meta)
        for ev in ds.data.events:
            self._plot.add_event_marker(ev)

        # Mirror the curve onto the overview bar (visibility is
        # controlled separately by the View → Show overview-bar toggle).
        self._overview_bar.set_data(ds.data.t, ds.data.v)
        if self._toggle_overview_act.isChecked():
            self._overview_bar.setVisible(True)

        self.statusBar().showMessage(
            f"{ds.name} — "
            f"{len(ds.data.sections)} section(s), "
            f"{len(ds.data.events)} event(s), "
            f"{ds.data.t_end - ds.data.t_start:.0f}s total"
        )
        self._plot.setFocus()

    def _show_empty_state(self) -> None:
        self._plot.clear_overlays()
        self._plot._curve.clear()
        self._plot._times = None
        self._plot._values = None
        self._plot.setVisible(False)
        self._overview_bar.clear_data()
        self._overview_bar.setVisible(False)
        self._empty_label.setVisible(True)
        self.setWindowTitle("RRational Inspector")
        self.statusBar().clearMessage()

    # ------------------------------------------------------------------
    # Sidebar tree management
    # ------------------------------------------------------------------
    def _add_dataset_to_tree(self, idx: int, ds: Dataset) -> None:
        top = QTreeWidgetItem(self._dataset_tree, [ds.name])
        top.setData(0, _ROLE_DATASET_IDX, idx)
        top.setToolTip(0, str(ds.path) if ds.path else "(synthetic)")
        for meta in ds.data.sections:
            label = f"{meta.name}  ({meta.beat_count} beats, {meta.t_end - meta.t_start:.0f}s)"
            child = QTreeWidgetItem(top, [label])
            child.setData(0, _ROLE_DATASET_IDX, idx)
            child.setData(0, _ROLE_SECTION_NAME, meta.name)
        top.setExpanded(True)
        self._update_tree_active_marker()

    def _rebuild_tree(self) -> None:
        self._dataset_tree.clear()
        for i, ds in enumerate(self._datasets):
            self._add_dataset_to_tree(i, ds)

    def _update_tree_active_marker(self) -> None:
        """Bold the top-level item of the active dataset."""
        for i in range(self._dataset_tree.topLevelItemCount()):
            top = self._dataset_tree.topLevelItem(i)
            font = top.font(0)
            font.setBold(i == self._active_idx)
            font.setWeight(QFont.Bold if i == self._active_idx else QFont.Normal)
            top.setFont(0, font)

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        idx = item.data(0, _ROLE_DATASET_IDX)
        section_name = item.data(0, _ROLE_SECTION_NAME)

        if idx is None:
            return  # unexpected — every item should carry an index

        # Activate the dataset first if the user clicked into a non-active one
        if self._active_idx != idx:
            self.set_active_dataset(idx)

        if section_name is None:
            # Top-level dataset click — already activated, nothing else.
            return

        # Section click — zoom + highlight inside the active dataset
        ds = self._datasets[idx]
        meta = next((s for s in ds.data.sections if s.name == section_name), None)
        if meta is None:
            return
        self._plot.zoom_to_range(meta.t_start, meta.t_end, padding_frac=0.02)
        self._plot.highlight_section(section_name)
        self._plot.setFocus()
        self.statusBar().showMessage(
            f"Section '{section_name}': {meta.beat_count} beats, "
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
