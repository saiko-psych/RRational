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
from qtpy.QtGui import QAction, QKeySequence
from qtpy.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QToolBar,
)

from rrational.gui.project import (
    ProjectManager,
    add_recent_project,
    get_recent_projects,
    remove_recent_project,
)
from rrational.inspector import persistence, settings
from rrational.inspector.data_loader import Dataset, InspectorData
from rrational.inspector.results_store import ResultsStore
from rrational.inspector.tabs import (
    AnalysisTab,
    BrowseTab,
    ParticipantsTab,
    ResultsTab,
    SetupTab,
)

# Phase 22.3: optional Streamlit-mode tabs. Other agents are adding
# DataTab + ParticipantTab in parallel; defer their imports so this
# module still loads if either class is missing in the current branch.
try:
    from rrational.inspector.tabs.data_tab import DataTab  # type: ignore
except ImportError:  # pragma: no cover - depends on parallel work
    DataTab = None  # type: ignore[assignment]

try:
    from rrational.inspector.tabs.participant_tab import ParticipantTab  # type: ignore
except ImportError:  # pragma: no cover - depends on parallel work
    ParticipantTab = None  # type: ignore[assignment]

# Valid values for the ``ui_layout`` setting.
LAYOUT_STREAMLIT = "streamlit"
LAYOUT_MNELAB = "mnelab"
_VALID_LAYOUTS = (LAYOUT_STREAMLIT, LAYOUT_MNELAB)

# Re-exported for older tests that import them from here. New code
# should import from ``inspector.tabs.browse_tab``.
from rrational.inspector.tabs.browse_tab import (  # noqa: F401
    ROLE_DATASET_IDX as _ROLE_DATASET_IDX,
)
from rrational.inspector.tabs.browse_tab import (  # noqa: F401
    ROLE_SECTION_NAME as _ROLE_SECTION_NAME,
)


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

        # All HRV results accumulated this session. The Analysis tab
        # appends; the Results tab reads.
        self._results_store = ResultsStore()

        # Currently-open project (or None for the global / "ad-hoc" workspace).
        # When set, the persistence layer redirects sequence/group state into
        # the project's config/ folder and Open/Save dialogs default to its
        # data/ folders.
        self._project: ProjectManager | None = None

        # Recent-projects submenu handle, rebuilt on File-menu open.
        self._recent_project_menu = None

        # Recent-files actions get rebuilt every time the File menu
        # opens, so we keep a handle on the submenu itself.
        self._recent_menu = None

        # Phase 14: Edit-menu undo / redo for manual artifact marking.
        # Populated by _build_menu; referenced by PreprocessingPanel to
        # enable / disable as the stacks fill and drain.
        self._undo_action = None
        self._redo_action = None

        self._build_central_widget()
        # Apply the user's saved color scheme to the plot before the menu
        # / toolbar are built so any toolbar repaint uses the right pen.
        from rrational.inspector.color_scheme_persistence import load_color_scheme

        self._color_preset, self._color_scheme = load_color_scheme()
        self._plot.set_color_scheme(self._color_scheme)

        self._build_menu()
        self._build_toolbar()
        self.setStatusBar(QStatusBar())
        # UX1: a permanent project badge on the left of the status bar.
        # Always visible so the user can tell at a glance which project
        # is active (window title alone gets lost in tab clutter).
        # Built BEFORE the cursor readout so it sits to its LEFT.
        self._project_badge = QLabel("")
        self._project_badge.setObjectName("projectBadge")
        self._project_badge.setCursor(Qt.PointingHandCursor)
        self._project_badge.setToolTip(
            "Click to open a project (or manage the current one)"
        )
        self._project_badge.mousePressEvent = self._on_project_badge_clicked
        self.statusBar().addPermanentWidget(self._project_badge)
        self._refresh_project_badge()
        # Permanent (always-visible) widget on the right side of the
        # status bar. addPermanentWidget keeps it visible even when
        # showMessage() displays a transient message on the left.
        self.statusBar().addPermanentWidget(self._cursor_readout)

        self._key_filter = _GlobalKeyFilter(self)
        QApplication.instance().installEventFilter(self._key_filter)

        # Phase 20: restore window + BrowseTab dock layout from QSettings
        # so user-adjusted geometry survives across runs.
        self._restore_window_state()

        # UX4: initial tab-label refresh once everything is wired up.
        self._refresh_tab_labels()

        # UX5: first-run onboarding dialog (non-blocking, skipped in test_mode).
        if not self.test_mode:
            from rrational.inspector.onboarding import (
                is_onboarded,
                show_welcome_dialog,
            )

            if not is_onboarded():
                show_welcome_dialog(self)

        if initial_path is not None:
            self.open_path(initial_path)

    # ------------------------------------------------------------------
    # Phase 20: window + dock state persistence
    # ------------------------------------------------------------------
    def _restore_window_state(self) -> None:
        """Reapply QMainWindow geometry + BrowseTab dock layout if cached."""
        try:
            geom = settings.read_setting("geometry")
            if geom is not None:
                self.restoreGeometry(geom)
        except (KeyError, TypeError):  # pragma: no cover - defensive
            pass
        try:
            win_state = settings.read_setting("window_state")
            if win_state is not None:
                self.restoreState(win_state)
        except (KeyError, TypeError):  # pragma: no cover - defensive
            pass
        try:
            dock_state = settings.read_setting("browse_dock_state")
        except (KeyError, TypeError):  # pragma: no cover - defensive
            dock_state = None
        if dock_state is not None:
            try:
                self._browse_tab.restore_dock_state(dock_state)
            except Exception:  # pragma: no cover - defensive
                pass

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API name
        """Persist window + dock geometry before the inspector closes.

        Skipped in test_mode so pytest-qt runs don't write to the user's
        real QSettings; tests that explicitly want to exercise the save
        path can call ``_save_window_state`` directly.
        """
        if not self.test_mode:
            self._save_window_state()
        super().closeEvent(event)

    def _save_window_state(self) -> None:
        """Write QMainWindow geometry + BrowseTab dock state to QSettings."""
        try:
            settings.save_window_state(self.saveGeometry(), self.saveState())
        except Exception:  # pragma: no cover - defensive
            pass
        try:
            settings.write_setting(
                "browse_dock_state", self._browse_tab.save_dock_state()
            )
        except Exception:  # pragma: no cover - defensive
            pass

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
        """Construct the central QTabWidget + each top-level tab.

        Browse owns the timeline/sidebar/overview widgets we used to
        host directly on MainWindow; Setup/Analysis/Results are
        placeholders until Phase 4b/c/d wire them up. The active tab
        is also where Pan/Zoom/Home/End make sense — the global key
        filter still routes them to the Browse plot regardless of which
        tab is visible, since the user expects keyboard nav to "always
        affect the timeline."
        """
        self._tabs_widget = QTabWidget(self)
        self._tabs_widget.setDocumentMode(True)
        self._tabs_widget.setMovable(False)

        # Phase 22.3: ALWAYS construct every tab — the layout switcher
        # toggles visibility, not existence, so cross-tab state stays
        # consistent regardless of which mode the user picks. DataTab /
        # ParticipantTab may still be None if the parallel work that
        # introduces them hasn't landed yet; in that case they're skipped
        # from the tab strip entirely (and the Streamlit mode degrades
        # gracefully to whatever IS available).
        self._browse_tab = BrowseTab(self)
        self._data_tab = DataTab(self) if DataTab is not None else None
        self._participant_tab = (
            ParticipantTab(self) if ParticipantTab is not None else None
        )
        self._setup_tab = SetupTab(self)
        self._participants_tab = ParticipantsTab(self)
        self._analysis_tab = AnalysisTab(self)
        self._results_tab = ResultsTab(self)

        # The full ordered list used for active-set notifications etc.
        # ``None`` entries from optional tabs are dropped. The visible
        # subset (and order) is controlled by ``_apply_layout_mode``.
        self._tabs = [
            t
            for t in (
                self._browse_tab,
                self._data_tab,
                self._participant_tab,
                self._setup_tab,
                self._participants_tab,
                self._analysis_tab,
                self._results_tab,
            )
            if t is not None
        ]
        for tab in self._tabs:
            self._tabs_widget.addTab(tab, tab.TAB_LABEL)
        # UX4: deferred — _refresh_tab_labels called below once everything
        # else (results store, project, etc.) is initialised.

        # Phase 22.3: load the persisted layout mode and apply it before
        # the window is shown. Falls back to "streamlit" for new users.
        try:
            stored = settings.read_setting("ui_layout")
        except KeyError:  # pragma: no cover - defensive: settings key missing
            stored = LAYOUT_STREAMLIT
        if stored not in _VALID_LAYOUTS:
            stored = LAYOUT_STREAMLIT
        self._ui_layout: str = stored
        self._apply_layout_mode(self._ui_layout)

        self.setCentralWidget(self._tabs_widget)

        # ----- Cursor readout (permanent status-bar widget) ---------------
        # The plot lives inside BrowseTab now; we hook into its signals
        # from here so the readout stays on the MainWindow's status bar
        # regardless of which tab is active.
        self._cursor_readout = QLabel("")
        self._cursor_readout.setStyleSheet("color: #555; padding-right: 8px;")
        self._browse_tab._plot.cursor_moved.connect(self._update_cursor_readout)
        self._browse_tab._plot.cursor_left.connect(self._clear_cursor_readout)

        # Phase 16: section-edit signal wiring. The plot emits each event
        # from its SectionRegion children; MainWindow mutates the active
        # dataset's SectionMeta + persists via gui.persistence.save_sections.
        self._browse_tab._plot.sigSectionEdited.connect(self._on_section_edited)
        self._browse_tab._plot.sigSectionRenameRequested.connect(
            self._on_section_rename_requested
        )
        self._browse_tab._plot.sigSectionDeleteRequested.connect(
            self._on_section_delete_requested
        )
        self._browse_tab._plot.sigSectionSplitRequested.connect(
            self._on_section_split_requested
        )

    # ------------------------------------------------------------------
    # Backward-compat proxies — tests + earlier-phase code still reach
    # for widgets that now live inside BrowseTab. Forward the access so
    # nothing has to change at call sites.
    # ------------------------------------------------------------------
    @property
    def _dataset_tree(self):
        return self._browse_tab._dataset_tree

    @property
    def _plot(self):
        return self._browse_tab._plot

    @property
    def _overview_bar(self):
        return self._browse_tab._overview_bar

    @property
    def _empty_label(self):
        return self._browse_tab._empty_label

    def _on_tree_item_clicked(self, item, column) -> None:
        """Forward sidebar clicks to BrowseTab (kept as a method for
        tests that call ``main_window._on_tree_item_clicked(item, 0)``).
        """
        self._browse_tab._on_tree_item_clicked(item, column)

    def _build_menu(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")

        # ----- Project block (mirrors MNE-LAB's project menu) -------------
        new_proj_act = QAction("&New project…", self)
        new_proj_act.setShortcut("Ctrl+Shift+N")
        new_proj_act.setStatusTip(
            "Create a new RRational project (folder + project.rrational manifest)"
        )
        new_proj_act.triggered.connect(self._on_new_project_clicked)
        file_menu.addAction(new_proj_act)

        open_proj_act = QAction("Open &project…", self)
        open_proj_act.setShortcut("Ctrl+Shift+P")
        open_proj_act.setStatusTip("Open an existing RRational project folder")
        open_proj_act.triggered.connect(self._on_open_project_clicked)
        file_menu.addAction(open_proj_act)

        self._recent_project_menu = file_menu.addMenu("Open recent p&roject")

        close_proj_act = QAction("Close project", self)
        close_proj_act.setStatusTip(
            "Close the current project (datasets stay loaded; persistence "
            "reverts to the global ~/.rrational store)"
        )
        close_proj_act.triggered.connect(self.close_project)
        file_menu.addAction(close_proj_act)

        file_menu.addSeparator()

        # UX2: "Open recording..." catch-all is the PRIMARY entry point.
        # Polar / Empatica / Kubios / Elite HRV / plain text / .rrational
        # all selectable through the dialog's file-type filter.
        open_act = QAction("&Open recording…", self)
        open_act.setShortcut(QKeySequence.Open)  # Ctrl+O / Cmd+O
        open_act.setStatusTip(
            "Open a recording — .rrational v2 or raw (Polar/Empatica/Kubios/Elite HRV/plain text)"
        )
        open_act.triggered.connect(self._on_open_clicked)
        file_menu.addAction(open_act)

        open_v2_act = QAction("Open .rrational v2 only…", self)
        open_v2_act.setShortcut("Ctrl+Shift+R")
        open_v2_act.setStatusTip(
            "Open only RRational v2 exports (filtered file dialog)"
        )
        open_v2_act.triggered.connect(self._on_open_rrational_only_clicked)
        file_menu.addAction(open_v2_act)

        open_folder_act = QAction("Open &folder…", self)
        open_folder_act.setShortcut("Ctrl+Shift+O")
        open_folder_act.setStatusTip("Load every recording inside a chosen folder")
        open_folder_act.triggered.connect(self._on_open_folder_clicked)
        file_menu.addAction(open_folder_act)

        self._recent_menu = file_menu.addMenu("Open &recent")
        # Rebuild the recent list every time the user opens File menu
        # (so deletions made outside the app are reflected).
        file_menu.aboutToShow.connect(self._rebuild_recent_menu)
        file_menu.aboutToShow.connect(self._rebuild_recent_project_menu)
        self._rebuild_recent_menu()
        self._rebuild_recent_project_menu()

        file_menu.addSeparator()

        # ----- Report export ---------------------------------------------
        export_html_act = QAction("Export report (&HTML)…", self)
        export_html_act.setStatusTip(
            "Save the current results as a self-contained HTML report"
        )
        export_html_act.triggered.connect(self._on_export_report_html_clicked)
        file_menu.addAction(export_html_act)

        export_md_act = QAction("Export report (&Markdown)…", self)
        export_md_act.setStatusTip(
            "Save the current results as a Markdown report (GitHub-flavoured)"
        )
        export_md_act.triggered.connect(self._on_export_report_markdown_clicked)
        file_menu.addAction(export_md_act)
        # Stash handles so tests can find/trigger the actions without
        # walking the menu hierarchy.
        self._export_html_act = export_html_act
        self._export_md_act = export_md_act

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

        # Phase 20: dockable BrowseTab panels (Datasets + Preprocessing).
        view_menu.addSeparator()
        self._toggle_datasets_dock_act = self._make_view_toggle(
            view_menu,
            "Show &Datasets panel",
            settings_key="show_datasets_dock"
            if "show_datasets_dock" in settings._DEFAULTS
            else None,
            on_change=self._browse_tab.set_datasets_dock_visible,
            default=True,
        )
        self._toggle_preprocessing_dock_act = self._make_view_toggle(
            view_menu,
            "Show &Preprocessing panel",
            settings_key="show_preprocessing_dock"
            if "show_preprocessing_dock" in settings._DEFAULTS
            else None,
            on_change=self._browse_tab.set_preprocessing_dock_visible,
            default=True,
        )

        # Phase 22.3: View → Layout submenu (Streamlit / MNE-LAB modes).
        # QActionGroup with exclusive=True gives the entries radio
        # behaviour — Qt automatically unchecks the other one when the
        # user picks a mode.
        from qtpy.QtGui import QActionGroup

        view_menu.addSeparator()
        layout_menu = view_menu.addMenu("&Layout")
        self._layout_action_group = QActionGroup(self)
        self._layout_action_group.setExclusive(True)

        self._layout_streamlit_act = QAction(
            "Streamlit mode (Data / Participant / Setup / Analysis / Results)",
            self,
        )
        self._layout_streamlit_act.setCheckable(True)
        self._layout_streamlit_act.setChecked(self._ui_layout == LAYOUT_STREAMLIT)
        self._layout_streamlit_act.setStatusTip(
            "Streamlit-style tabs: Data / Participant / Setup / Analysis / Results"
        )
        self._layout_streamlit_act.triggered.connect(
            lambda checked=False: checked and self.set_ui_layout(LAYOUT_STREAMLIT)
        )
        self._layout_action_group.addAction(self._layout_streamlit_act)
        layout_menu.addAction(self._layout_streamlit_act)

        self._layout_mnelab_act = QAction(
            "MNE-LAB mode (Browse / Setup / Analysis / Results, dock-heavy)",
            self,
        )
        self._layout_mnelab_act.setCheckable(True)
        self._layout_mnelab_act.setChecked(self._ui_layout == LAYOUT_MNELAB)
        self._layout_mnelab_act.setStatusTip(
            "Single-window dock-based layout (Browse / Setup / Participants / Analysis / Results)"
        )
        self._layout_mnelab_act.triggered.connect(
            lambda checked=False: checked and self.set_ui_layout(LAYOUT_MNELAB)
        )
        self._layout_action_group.addAction(self._layout_mnelab_act)
        layout_menu.addAction(self._layout_mnelab_act)

        # ----- Edit menu --------------------------------------------------
        edit_menu = menubar.addMenu("&Edit")

        # Phase 14: undo / redo for manual artifact marking. Disabled
        # until the PreprocessingPanel populates its undo stack.
        self._undo_action = QAction("&Undo manual mark", self)
        self._undo_action.setShortcut(QKeySequence.Undo)  # Ctrl+Z / Cmd+Z
        self._undo_action.setStatusTip("Reverse the last manual artifact mark / unmark")
        self._undo_action.setEnabled(False)
        self._undo_action.triggered.connect(self._on_undo_clicked)
        edit_menu.addAction(self._undo_action)

        self._redo_action = QAction("&Redo manual mark", self)
        self._redo_action.setShortcut(QKeySequence.Redo)  # Ctrl+Y / Cmd+Shift+Z
        self._redo_action.setStatusTip("Re-apply the last undone manual artifact mark")
        self._redo_action.setEnabled(False)
        self._redo_action.triggered.connect(self._on_redo_clicked)
        edit_menu.addAction(self._redo_action)

        edit_menu.addSeparator()

        prefs_act = QAction("&Preferences…", self)
        prefs_act.setShortcut("Ctrl+,")
        prefs_act.setStatusTip("Inspector preferences (color scheme, etc.)")
        prefs_act.triggered.connect(self._on_preferences_clicked)
        edit_menu.addAction(prefs_act)

        tools_menu = menubar.addMenu("&Tools")

        # ----- UX2: Import from <source>... submenu ---------------------
        import_menu = tools_menu.addMenu("&Import from")
        for label, source_filter in [
            ("Polar (CSV)…", "Polar (*.csv)"),
            ("Empatica (CSV)…", "Empatica (*.csv)"),
            ("Kubios (TXT)…", "Kubios (*.txt)"),
            ("Elite HRV (CSV)…", "Elite HRV (*.csv)"),
            ("Plain text (TXT/DAT)…", "Plain text (*.txt *.dat)"),
        ]:
            act = QAction(label, self)
            act.setStatusTip(f"Open a recording with the {label} file filter")
            act.triggered.connect(
                lambda _checked=False, f=source_filter: self._on_import_clicked(f)
            )
            import_menu.addAction(act)
        tools_menu.addSeparator()

        # ----- Tools: visualisation submenu (Phase 17) -------------------
        # All four actions are dataset-aware; toggled by
        # ``_refresh_visualisation_actions`` on workspace changes.
        tools_menu.addSeparator()
        self._tachogram_act = QAction("&Tachogram…", self)
        self._tachogram_act.setStatusTip(
            "Open a tachogram (RR vs beat) of the active dataset's first section"
        )
        self._tachogram_act.triggered.connect(self._on_tachogram_clicked)
        tools_menu.addAction(self._tachogram_act)

        self._poincare_act = QAction("&Poincare plot…", self)
        self._poincare_act.setStatusTip("Open a Poincare plot of the active dataset")
        self._poincare_act.triggered.connect(self._on_poincare_clicked)
        tools_menu.addAction(self._poincare_act)

        self._psd_act = QAction("&PSD plot…", self)
        self._psd_act.setStatusTip("Open a power spectral density plot")
        self._psd_act.triggered.connect(self._on_psd_clicked)
        tools_menu.addAction(self._psd_act)

        self._hr_dist_act = QAction("&HR distribution…", self)
        self._hr_dist_act.setStatusTip("Open a heart rate distribution histogram + KDE")
        self._hr_dist_act.triggered.connect(self._on_hr_distribution_clicked)
        tools_menu.addAction(self._hr_dist_act)
        self._visualisation_actions = [
            self._tachogram_act,
            self._poincare_act,
            self._psd_act,
            self._hr_dist_act,
        ]
        self._refresh_visualisation_actions()

        # ----- Help menu --------------------------------------------------
        help_menu = menubar.addMenu("&Help")
        # UX5: workflow-walkthrough is the FIRST help entry — most useful for new users.
        walkthrough_act = QAction("&Workflow walkthrough…", self)
        walkthrough_act.setStatusTip(
            "Show the end-to-end workflow (raw → detect → review → save → setup → analyze → export)"
        )
        walkthrough_act.triggered.connect(self._show_workflow_walkthrough)
        help_menu.addAction(walkthrough_act)

        reshow_welcome_act = QAction("Show &welcome dialog again", self)
        reshow_welcome_act.setStatusTip(
            "Reopen the first-run welcome dialog (5-tab overview)"
        )
        reshow_welcome_act.triggered.connect(self._reshow_welcome_dialog)
        help_menu.addAction(reshow_welcome_act)

        help_menu.addSeparator()

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
        """Open the Preferences dialog (suppressed in test_mode)."""
        if self.test_mode:
            self.statusBar().showMessage("Preferences dialog (test_mode: suppressed)")
            return
        from rrational.inspector.preferences_dialog import PreferencesDialog

        dlg = PreferencesDialog(
            self,
            current_preset=self._color_preset,
            current_scheme=self._color_scheme,
            apply_callback=self._apply_color_scheme,
        )
        dlg.exec()

    def _apply_color_scheme(self, preset_name: str, scheme) -> None:
        """Persist preferences callback: cache + re-skin the plot."""
        self._color_preset = preset_name
        self._color_scheme = scheme
        self._plot.set_color_scheme(scheme)

    # ------------------------------------------------------------------
    # Phase 14: Undo / Redo wiring (delegated to the preprocessing panel)
    # ------------------------------------------------------------------
    def _on_undo_clicked(self) -> None:
        panel = getattr(self._browse_tab, "_preprocessing_panel", None)
        if panel is None:
            return
        if not panel.undo():
            self.statusBar().showMessage("Nothing to undo", 1500)

    def _on_redo_clicked(self) -> None:
        panel = getattr(self._browse_tab, "_preprocessing_panel", None)
        if panel is None:
            return
        if not panel.redo():
            self.statusBar().showMessage("Nothing to redo", 1500)

    def _show_workflow_walkthrough(self) -> None:
        """UX5: end-to-end workflow help (modeless)."""
        if self.test_mode:
            self.statusBar().showMessage("Workflow walkthrough (test_mode: suppressed)")
            return
        text = (
            "<h3>RRational Inspector — typical workflow</h3>"
            "<ol>"
            "<li><b>Open a recording</b> via <i>File → Open recording</i> "
            "(or the welcome screen). Accepts .rrational, Polar/Empatica CSV, "
            "Kubios/Elite HRV/plain text.</li>"
            "<li><b>Detect artifacts</b> in the right-side Preprocessing panel "
            "(Browse tab). NK2 Kubios algorithm; results are persisted automatically.</li>"
            "<li><b>Review &amp; correct</b>: enable <i>Use corrected RR values</i>, "
            "or use <i>Manual mark mode</i> to click directly on beats. "
            "<i>Exclusion mode</i> drags out time ranges to skip.</li>"
            "<li><b>Save as .rrational v2</b> with the right-panel button — "
            "open-exchange format with all the corrections preserved.</li>"
            "<li><b>Setup tab</b>: define your groups, sections, sequences, protocol.</li>"
            "<li><b>Participants tab</b>: link datasets to groups + sequences "
            "(or import-from-workspace for a quick start).</li>"
            "<li><b>Analysis tab</b>: pick a mode (Single / Repeating / Group / "
            "Sequence) and Compute.</li>"
            "<li><b>Results tab</b>: every metric in a sortable table. "
            "Export as CSV, or generate a full HTML/Markdown report via "
            "<i>File → Export report</i>.</li>"
            "</ol>"
            "<p><i>Tip: open a Project (File → Open project) to persist groups, "
            "events, sequences, etc. across sessions and share state with the "
            "Streamlit app.</i></p>"
        )
        QMessageBox.information(self, "Workflow walkthrough", text)

    def _reshow_welcome_dialog(self) -> None:
        """UX5: re-open the first-run welcome dialog on demand."""
        if self.test_mode:
            self.statusBar().showMessage("Welcome dialog (test_mode: suppressed)")
            return
        from rrational.inspector.onboarding import show_welcome_dialog

        show_welcome_dialog(self)

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
    # Project lifecycle
    # ------------------------------------------------------------------
    def _on_new_project_clicked(self) -> None:
        from rrational.inspector.project_dialogs import NewProjectDialog

        if self.test_mode:
            self.statusBar().showMessage("New project dialog (test_mode: suppressed)")
            return
        default_parent_str = settings.read_setting("last_dir") or str(Path.home())
        dlg = NewProjectDialog(self, default_parent_dir=Path(default_parent_str))
        if dlg.exec() != dlg.Accepted:
            return
        pm = dlg.project_manager()
        if pm is None:
            return
        self.set_active_project(pm)
        self.statusBar().showMessage(
            f"Created project '{pm.metadata.name}' at {pm.project_path}", 5000
        )

    def _on_open_project_clicked(self) -> None:
        if self.test_mode:
            self.statusBar().showMessage("Open project dialog (test_mode: suppressed)")
            return
        default_dir = settings.read_setting("last_dir") or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(
            self, "Open project folder", default_dir
        )
        if not chosen:
            return
        self.open_project_path(Path(chosen))

    def open_project_path(self, path: Path) -> bool:
        """Open the project at ``path``. Returns True on success."""
        valid, issues = ProjectManager.is_valid_project(path)
        if not valid:
            self._warn(
                "Not a project",
                f"{path} is not a valid RRational project:\n\n"
                + "\n".join(f"• {i}" for i in issues),
            )
            return False
        try:
            pm = ProjectManager.open_project(path)
        except (FileNotFoundError, ValueError) as e:
            self._critical("Could not open project", str(e))
            return False
        self.set_active_project(pm)
        return True

    def set_active_project(self, pm: ProjectManager | None) -> None:
        """Switch the active project. ``None`` closes the current one."""
        self._project = pm
        if pm is None:
            persistence.set_active_project_config_dir(None)
        else:
            persistence.set_active_project_config_dir(pm.get_config_dir())
            if not self.test_mode:
                add_recent_project(pm.project_path, pm.metadata.name)
                settings.write_setting("last_dir", str(pm.project_path))
            # NOTE: do NOT auto-load every .rrational from data/processed/
            # on project open — overwhelms the user with random files.
            # The DataTab shows a clear overview of available raw +
            # processed files; user picks what to open. (Previous behaviour
            # caused "loaded a project and it instantly opened a random
            # .rrational file" complaint.)
        # Tell every persistence-aware tab to re-read.
        sequences_pane = getattr(self._setup_tab, "_sequences_pane", None)
        if sequences_pane is not None:
            from rrational.inspector.persistence import load_sequences as _load

            sequences_pane._sequences = _load()
            sequences_pane._refresh_table()
        analysis_seq_pane = getattr(self._analysis_tab, "_sequence_pane", None)
        if analysis_seq_pane is not None and hasattr(
            analysis_seq_pane, "refresh_sequences"
        ):
            analysis_seq_pane.refresh_sequences()
        # Auto-load the per-project results cache (Phase 13). The store
        # is replaced wholesale so closing a project + reopening another
        # never bleeds rows between them.
        self._load_results_cache()
        self._update_window_title()
        self._refresh_project_badge()
        # After opening a project, jump to the Data tab (Streamlit mode)
        # or Browse tab (MNE-LAB mode) so the user sees the project
        # overview immediately. Also refresh DataTab so its raw +
        # processed lists reflect the just-opened project.
        if pm is not None:
            data_tab = getattr(self, "_data_tab", None)
            if data_tab is not None and hasattr(data_tab, "refresh_from_workspace"):
                data_tab.refresh_from_workspace()
            target = data_tab or getattr(self, "_browse_tab", None)
            if target is not None:
                idx = self._tabs_widget.indexOf(target)
                if idx >= 0 and self._tabs_widget.isTabVisible(idx):
                    self._tabs_widget.setCurrentIndex(idx)

    def close_project(self) -> None:
        """Close the current project (datasets stay loaded)."""
        if self._project is None:
            self.statusBar().showMessage("No project open", 2000)
            return
        name = self._project.metadata.name if self._project.metadata else "(unnamed)"
        self.set_active_project(None)
        self.statusBar().showMessage(f"Closed project '{name}'", 3000)

    def _rebuild_recent_project_menu(self) -> None:
        if self._recent_project_menu is None:
            return
        self._recent_project_menu.clear()
        recents = get_recent_projects()
        if not recents:
            empty = QAction("(no recent projects)", self)
            empty.setEnabled(False)
            self._recent_project_menu.addAction(empty)
            return
        for entry in recents:
            path = Path(entry["path"])
            label = f"{entry.get('name', path.name)}  ({path})"
            act = QAction(label, self)
            act.triggered.connect(
                lambda _checked=False, p=path: self._open_recent_project(p)
            )
            self._recent_project_menu.addAction(act)

    def _open_recent_project(self, path: Path) -> None:
        if not path.exists():
            self._warn(
                "Project not found",
                f"{path} no longer exists. Removed from recent list.",
            )
            remove_recent_project(path)
            self._rebuild_recent_project_menu()
            return
        self.open_project_path(path)

    # ------------------------------------------------------------------
    # UX1: project badge in the status bar
    # ------------------------------------------------------------------
    def _refresh_project_badge(self) -> None:
        """Update the permanent status-bar badge to reflect ``self._project``."""
        badge = getattr(self, "_project_badge", None)
        if badge is None:
            return
        if self._project is None:
            badge.setText("No project active — using global config")
            badge.setStyleSheet(
                "QLabel#projectBadge { "
                "color: #777; font-style: italic; padding: 0 8px; "
                "}"
            )
        else:
            name = (
                self._project.metadata.name
                if self._project.metadata is not None
                else "(unnamed)"
            )
            badge.setText(f"Project: {name}")
            badge.setStyleSheet(
                "QLabel#projectBadge { "
                "color: #1f6feb; font-weight: bold; padding: 0 8px; "
                "}"
            )

    def _on_project_badge_clicked(self, event) -> None:
        """Click handler for the permanent project badge.

        - No project active → open the Open Project dialog.
        - Project active → pop a small menu (close / open folder / info).
        """
        from qtpy.QtWidgets import QMenu

        if self._project is None:
            self._on_open_project_clicked()
            return
        menu = QMenu(self)
        close_act = menu.addAction("Close project")
        open_folder_act = menu.addAction("Open project folder in explorer")
        info_act = menu.addAction("Show project info")
        chosen = menu.exec(event.globalPos()) if not self.test_mode else None
        if chosen is close_act:
            self.close_project()
        elif chosen is open_folder_act:
            self._open_project_folder_in_explorer()
        elif chosen is info_act:
            self._show_project_info_dialog()

    def _open_project_folder_in_explorer(self) -> None:
        if self._project is None:
            return
        from qtpy.QtCore import QUrl
        from qtpy.QtGui import QDesktopServices

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._project.project_path)))

    def _show_project_info_dialog(self) -> None:
        if self._project is None:
            return
        meta = self._project.metadata
        name = meta.name if meta is not None else "(unnamed)"
        desc = (meta.description if meta is not None else "") or ""
        text = (
            f"<b>{name}</b><br><i>{desc}</i><br><br>Path: {self._project.project_path}"
        )
        self._info("Project info", text)

    def _update_window_title(self) -> None:
        """Title format: 'project_name — dataset_name' or 'dataset_name' alone."""
        ds_part = None
        if self._active_idx is not None:
            ds_part = self._datasets[self._active_idx].name
        proj_part = None
        if self._project is not None and self._project.metadata is not None:
            proj_part = self._project.metadata.name
        if proj_part and ds_part:
            self.setWindowTitle(f"RRational Inspector — [{proj_part}] {ds_part}")
        elif proj_part:
            self.setWindowTitle(f"RRational Inspector — [{proj_part}]")
        elif ds_part:
            self.setWindowTitle(f"RRational Inspector — {ds_part}")
        else:
            self.setWindowTitle("RRational Inspector")

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
    def _open_dialog_default_dir(self) -> str:
        """Open-file dialogs default to project/data/raw if a project is active."""
        if self._project is not None:
            raw_dir = self._project.get_data_dir()
            if raw_dir.exists():
                return str(raw_dir)
        return settings.read_setting("last_dir") or str(Path.cwd())

    def _on_open_clicked(self) -> None:
        last_dir = self._open_dialog_default_dir()
        # Filter offers .rrational v2 exports AND every raw format the
        # io.generic_rr parser supports. "All RR files" first so the
        # default file-picker shows them all without the user having to
        # switch filters.
        file_filter = (
            "All RR files (*.rrational *.csv *.txt *.dat);;"
            "RRational v2.0 (*.rrational);;"
            "Polar / Empatica / Plain CSV (*.csv);;"
            "Kubios / Elite HRV / Plain text (*.txt *.dat);;"
            "All files (*.*)"
        )
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Open recording", last_dir, file_filter
        )
        for path_str in paths:
            self.open_path(Path(path_str))

    def _on_open_rrational_only_clicked(self) -> None:
        """UX2: filtered-only RRational v2 dialog (still accessible via main Open)."""
        last_dir = self._open_dialog_default_dir()
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Open RRational v2 file", last_dir, "RRational v2.0 (*.rrational)"
        )
        for path_str in paths:
            self.open_path(Path(path_str))

    def _on_import_clicked(self, source_filter: str) -> None:
        """UX2: source-specific Import-from submenu entries.

        Opens a QFileDialog pre-selecting the given file-type filter
        (e.g. ``"Polar (*.csv)"``) so the user sees only matching files.
        Falls back to the same ``open_path`` loader once a file is chosen
        (which auto-detects the actual format via ``generic_rr``).
        """
        last_dir = self._open_dialog_default_dir()
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import recording", last_dir, source_filter
        )
        for path_str in paths:
            self.open_path(Path(path_str))

    def _on_open_folder_clicked(self) -> None:
        last_dir = self._open_dialog_default_dir()
        folder_str = QFileDialog.getExistingDirectory(
            self, "Open folder containing recordings", last_dir
        )
        if not folder_str:
            return
        self.open_folder(Path(folder_str))

    def open_folder(self, folder: Path) -> None:
        """Open every recording in ``folder``.

        Phase 20: detects BIDS-style layouts (``participants.tsv`` at the
        root + ``sub-*/`` subdirs) and routes them through
        :meth:`_load_bids_folder` instead of the flat glob.
        """
        # Phase 20: BIDS-formatted recording trees take priority over
        # the flat glob — they carry per-subject metadata that the
        # ParticipantsTab can pre-populate.
        if self._is_bids_folder(folder):
            self._load_bids_folder(folder)
            return

        # Try .rrational first; if none, glob for raw RR file extensions.
        # We deliberately don't mix the two — a folder is either a project
        # export directory or a raw-data dump, not both.
        files = sorted(folder.glob("*.rrational"))
        if not files:
            raw_files: list[Path] = []
            for ext in ("*.csv", "*.txt", "*.dat"):
                raw_files.extend(folder.glob(ext))
            files = sorted(raw_files)
        if not files:
            self._info(
                "No files found",
                f"No .rrational, .csv, .txt or .dat files in {folder.name}.",
            )
            return
        for p in files:
            self.open_path(p)

    # ------------------------------------------------------------------
    # Phase 20: BIDS folder detection + loader
    # ------------------------------------------------------------------
    @staticmethod
    def _is_bids_folder(folder: Path) -> bool:
        """A BIDS root has both ``participants.tsv`` AND at least one
        ``sub-*`` subdirectory."""
        if not folder.is_dir():
            return False
        if not (folder / "participants.tsv").exists():
            return False
        return any(p.is_dir() and p.name.startswith("sub-") for p in folder.iterdir())

    def _parse_participants_tsv(self, tsv_path: Path) -> list[dict]:
        """Return ordered list of dicts (one per row) from ``participants.tsv``."""
        import csv

        rows: list[dict] = []
        try:
            with tsv_path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    rows.append(dict(row))
        except (OSError, csv.Error):
            return []
        return rows

    def _load_bids_folder(self, folder: Path) -> None:
        """Walk a BIDS root, loading every recording under each ``sub-*``.

        For each row in ``participants.tsv`` we:
        1. Open every supported recording inside ``sub-{id}/`` (recursive).
        2. Add a Participants tab entry (id = ``participant_id`` column).
        Existing participants are not overwritten — re-running is safe.
        """
        rows = self._parse_participants_tsv(folder / "participants.tsv")
        # Filter rows that map to an existing subdir.
        sub_recordings: dict[str, list[Path]] = {}
        order: list[str] = []
        recording_exts = {".rrational", ".csv", ".txt", ".dat"}
        for row in rows:
            pid_raw = row.get("participant_id") or row.get("participant") or ""
            if not pid_raw:
                continue
            # BIDS participant IDs are stored with the "sub-" prefix; strip
            # for the in-memory id but keep it for the folder name lookup.
            pid = pid_raw[4:] if pid_raw.startswith("sub-") else pid_raw
            sub_dir = folder / (
                pid_raw if pid_raw.startswith("sub-") else f"sub-{pid_raw}"
            )
            if not sub_dir.is_dir():
                continue
            recs = sorted(
                p
                for p in sub_dir.rglob("*")
                if p.is_file() and p.suffix.lower() in recording_exts
            )
            if not recs:
                continue
            order.append(pid)
            sub_recordings[pid] = recs

        if not sub_recordings:
            self._info(
                "Empty BIDS folder",
                f"{folder.name} has participants.tsv but no recordings under any sub-*.",
            )
            return

        # One-shot info dialog (test_mode silences the popup but still loads).
        if not self.test_mode:
            self._info(
                "BIDS layout detected",
                f"Detected BIDS layout — loading {len(sub_recordings)} participants.",
            )

        for pid in order:
            for path in sub_recordings[pid]:
                self.open_path(path)

        # Pre-populate ParticipantsTab entries (id = pid, label = any
        # additional column from the TSV).
        self._add_bids_participants(rows, sub_recordings.keys())

    def _add_bids_participants(self, rows: list[dict], loaded_ids) -> None:
        """Inject one ParticipantsTab entry per loaded BIDS subject."""
        from rrational.gui.persistence import (
            load_participants as _lp,
        )
        from rrational.gui.persistence import (
            save_participants as _sp,
        )

        proj = getattr(self, "_project", None)
        project_path = proj.project_path if proj is not None else None
        existing = _lp(project_path=project_path) or {}
        loaded_set = set(loaded_ids)
        for row in rows:
            pid_raw = row.get("participant_id") or row.get("participant") or ""
            if not pid_raw:
                continue
            pid = pid_raw[4:] if pid_raw.startswith("sub-") else pid_raw
            if pid not in loaded_set:
                continue
            if pid in existing:
                continue
            # Carry through any optional columns as a free-text label.
            label_bits = [
                f"{k}={v}"
                for k, v in row.items()
                if k not in ("participant_id", "participant") and v
            ]
            existing[pid] = {
                "label": "; ".join(label_bits),
                "event_order": [],
                "manual_events": [],
            }
        _sp(existing, project_path=project_path)
        # Notify the ParticipantsTab so its table refreshes.
        pt = getattr(self, "_participants_tab", None)
        if pt is not None:
            pt.on_workspace_changed()

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
        self._notify_tabs_workspace_changed()
        return len(self._datasets) - 1

    def set_active_dataset(self, idx: int) -> None:
        """Switch which dataset is currently rendered in the plot."""
        if not (0 <= idx < len(self._datasets)):
            raise IndexError(f"invalid dataset index: {idx}")
        self._active_idx = idx
        self._update_window_title()
        self._notify_tabs_active_changed()

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

        self._notify_tabs_workspace_changed()

        if not self._datasets:
            self._update_window_title()
            self.statusBar().clearMessage()
            self._notify_tabs_active_changed()  # data=None
        elif self._active_idx is None:
            self.set_active_dataset(0)
        else:
            self._notify_tabs_active_changed()

    def close_all_datasets(self) -> None:
        self._datasets.clear()
        self._active_idx = None
        self._update_window_title()
        self.statusBar().clearMessage()
        self._notify_tabs_workspace_changed()
        self._notify_tabs_active_changed()

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
    # Tab notification helpers
    # ------------------------------------------------------------------
    def _notify_tabs_workspace_changed(self) -> None:
        for tab in self._tabs:
            tab.on_workspace_changed()
        self._refresh_visualisation_actions()
        self._refresh_tab_labels()

    def _refresh_tab_labels(self) -> None:
        """UX4: refresh top-tab labels with live state badges so the user
        can SEE what's in each tab without clicking through them."""
        for i, tab in enumerate(self._tabs):
            base = tab.TAB_LABEL
            state = ""
            if hasattr(tab, "tab_label_state"):
                try:
                    s = tab.tab_label_state()
                    if s:
                        state = f"  {s}"
                except Exception:  # pragma: no cover - defensive
                    state = ""
            self._tabs_widget.setTabText(i, f"{base}{state}")

    # ------------------------------------------------------------------
    # Phase 22.3: Layout switcher (Streamlit / MNE-LAB modes)
    # ------------------------------------------------------------------
    def _layout_visible_tabs(self, mode: str) -> set:
        """Return the SET of tab widgets that should be visible in ``mode``.

        Streamlit mode hides BrowseTab and shows the data-centric tabs
        (Data + Participant) when they exist. MNE-LAB mode hides those
        and shows BrowseTab + the global ParticipantsTab. Optional tabs
        that weren't constructed (DataTab / ParticipantTab) are silently
        omitted — the layout still works, just with fewer entries.
        """
        if mode == LAYOUT_STREAMLIT:
            wanted = [
                self._data_tab,
                self._participant_tab,
                self._setup_tab,
                # The global "Participants Mgmt" table is redundant in
                # Streamlit mode (DataTab + ParticipantTab cover that
                # workflow) so we hide it unless DataTab is absent.
                self._participants_tab if self._data_tab is None else None,
                self._analysis_tab,
                self._results_tab,
            ]
        elif mode == LAYOUT_MNELAB:
            wanted = [
                self._browse_tab,
                self._setup_tab,
                self._participants_tab,
                self._analysis_tab,
                self._results_tab,
            ]
        else:  # pragma: no cover - guarded by _VALID_LAYOUTS check
            wanted = list(self._tabs)
        return {t for t in wanted if t is not None}

    def _apply_layout_mode(self, mode: str) -> None:
        """Toggle each tab's visibility to match ``mode``.

        Idempotent — safe to call as often as the layout actions fire.
        After flipping visibility we always jump the current tab to the
        first visible one for the new mode, so e.g. switching from
        Streamlit (current = Data) to MNE-LAB lands the user on Browse
        (the natural starting point) rather than wherever they happened
        to be in the old layout.
        """
        if mode not in _VALID_LAYOUTS:
            mode = LAYOUT_STREAMLIT
        self._ui_layout = mode
        visible = self._layout_visible_tabs(mode)
        first_visible_idx: int | None = None
        for i, tab in enumerate(self._tabs):
            is_visible = tab in visible
            self._tabs_widget.setTabVisible(i, is_visible)
            if is_visible and first_visible_idx is None:
                first_visible_idx = i
        # Always select the first visible tab for the new mode. This
        # keeps the QTabWidget pointing at a meaningful pane both on
        # initial construction AND after a live mode switch.
        if first_visible_idx is not None:
            self._tabs_widget.setCurrentIndex(first_visible_idx)

    def set_ui_layout(self, mode: str) -> None:
        """Public entry point — switch layout, persist, sync menu state.

        Called by the View → Layout actions AND usable from tests. The
        choice is written to QSettings (unless ``test_mode`` is on) so
        the next ``MainWindow`` constructed reads it back.
        """
        if mode not in _VALID_LAYOUTS:
            mode = LAYOUT_STREAMLIT
        self._apply_layout_mode(mode)
        if not self.test_mode:
            try:
                settings.write_setting("ui_layout", mode)
            except Exception:  # pragma: no cover - defensive
                pass
        # Keep the View menu's radio actions in sync if the caller
        # bypassed them (e.g. test code calling set_ui_layout directly).
        act = getattr(self, "_layout_streamlit_act", None)
        if act is not None:
            act.blockSignals(True)
            act.setChecked(mode == LAYOUT_STREAMLIT)
            act.blockSignals(False)
        act = getattr(self, "_layout_mnelab_act", None)
        if act is not None:
            act.blockSignals(True)
            act.setChecked(mode == LAYOUT_MNELAB)
            act.blockSignals(False)

    # ------------------------------------------------------------------
    # Phase 17: visualisation dialogs (Tachogram / Poincare / PSD / HR)
    # ------------------------------------------------------------------
    def _refresh_visualisation_actions(self) -> None:
        """Enable plot menu entries only when a dataset is loaded."""
        actions = getattr(self, "_visualisation_actions", None)
        if not actions:
            return
        enabled = self._data is not None
        for act in actions:
            act.setEnabled(enabled)

    def _active_first_section_rr(self) -> tuple[list[float], str] | None:
        """Helper: RR (ms) for the first finite-data section of active dataset."""
        import numpy as np

        if self._data is None:
            return None
        data = self._data
        for sec in data.sections:
            in_section = (data.t >= sec.t_start) & (data.t <= sec.t_end)
            finite = np.isfinite(data.v)
            rr = data.v[in_section & finite]
            if len(rr) > 0:
                return list(map(float, rr)), sec.name
        return None

    def _on_tachogram_clicked(self) -> None:
        from rrational.inspector.plot_dialogs import show_tachogram_dialog

        slice_ = self._active_first_section_rr()
        if slice_ is None:
            self._info("Tachogram", "No data available in active dataset.")
            return
        rr, section_label = slice_
        dlg = show_tachogram_dialog(
            self,
            rr,
            section_label=section_label,
            color_scheme=self._color_scheme,
            test_mode=self.test_mode,
        )
        self._latest_visualisation_dialog = dlg

    def _on_poincare_clicked(self) -> None:
        from rrational.inspector.plot_dialogs import show_poincare_dialog

        slice_ = self._active_first_section_rr()
        if slice_ is None:
            self._info("Poincare", "No data available in active dataset.")
            return
        rr, section_label = slice_
        dlg = show_poincare_dialog(
            self,
            rr,
            section_label=section_label,
            color_scheme=self._color_scheme,
            test_mode=self.test_mode,
        )
        self._latest_visualisation_dialog = dlg

    def _on_psd_clicked(self) -> None:
        from rrational.inspector.plot_dialogs import show_psd_dialog

        slice_ = self._active_first_section_rr()
        if slice_ is None:
            self._info("PSD", "No data available in active dataset.")
            return
        rr, section_label = slice_
        dlg = show_psd_dialog(
            self,
            rr,
            section_label=section_label,
            color_scheme=self._color_scheme,
            test_mode=self.test_mode,
        )
        self._latest_visualisation_dialog = dlg

    def _on_hr_distribution_clicked(self) -> None:
        from rrational.inspector.plot_dialogs import show_hr_distribution_dialog

        slice_ = self._active_first_section_rr()
        if slice_ is None:
            self._info("HR distribution", "No data available in active dataset.")
            return
        rr, section_label = slice_
        dlg = show_hr_distribution_dialog(
            self,
            rr,
            section_label=section_label,
            color_scheme=self._color_scheme,
            test_mode=self.test_mode,
        )
        self._latest_visualisation_dialog = dlg

    def _on_sequences_changed(self) -> None:
        """Called by Setup tab after persisting a sequence edit.

        The Analysis tab's sequence pane re-reads from disk so its
        dropdown stays in sync without the user clicking refresh.
        """
        pane = getattr(self._analysis_tab, "_sequence_pane", None)
        if pane is not None and hasattr(pane, "refresh_sequences"):
            pane.refresh_sequences()

    def _on_groups_changed(self) -> None:
        """Called by Setup tab after persisting a group edit.

        The Analysis tab's group-comparison pane re-reads groups.yml so
        its saved-groups dropdown stays in sync.
        """
        pane = getattr(self._analysis_tab, "_group_pane", None)
        if pane is not None and hasattr(pane, "refresh_saved_groups"):
            pane.refresh_saved_groups()

    # ------------------------------------------------------------------
    # Phase 13: Results cache (autosave / autoload / clear)
    # ------------------------------------------------------------------
    def _project_path_for_cache(self):
        return self._project.project_path if self._project is not None else None

    def _load_results_cache(self) -> None:
        """Replace the in-memory ResultsStore with whatever's on disk."""
        from rrational.inspector.results_persistence import load_results

        self._results_store = load_results(project_path=self._project_path_for_cache())
        if hasattr(self, "_results_tab"):
            self._results_tab.refresh_results()

    def save_results_cache(self) -> None:
        """Write the current ResultsStore to disk.

        Called automatically after every Analysis-tab Compute via
        :meth:`autosave_results`. Manual save is via the Results tab.
        """
        from rrational.inspector.results_persistence import save_results

        save_results(
            self._results_store,
            project_path=self._project_path_for_cache(),
        )

    def autosave_results(self) -> None:
        """Safe wrapper used by Analysis-tab callbacks — never raises."""
        try:
            self.save_results_cache()
        except Exception:  # pragma: no cover - autosave must not crash compute
            pass

    def clear_results_cache(self) -> bool:
        """Wipe the in-memory store AND delete the on-disk file."""
        from rrational.inspector.results_persistence import clear_results

        self._results_store.clear()
        if hasattr(self, "_results_tab"):
            self._results_tab.refresh_results()
        return clear_results(project_path=self._project_path_for_cache())

    def _notify_tabs_active_changed(self) -> None:
        data = self._data  # None when no active dataset
        for tab in self._tabs:
            tab.on_active_dataset_changed(data)

    # ------------------------------------------------------------------
    # Phase 18: Report export (HTML / Markdown)
    # ------------------------------------------------------------------
    def _report_default_dir(self) -> Path:
        """Choose a sensible default directory for report exports.

        Prefers the project's ``analysis/`` folder when a project is
        open, otherwise the last directory the user opened a file from.
        """
        if self._project is not None:
            analysis_dir = self._project.project_path / "analysis"
            if analysis_dir.exists():
                return analysis_dir
            return self._project.project_path
        last = settings.read_setting("last_dir")
        if last:
            return Path(last)
        return Path.cwd()

    def _on_export_report_html_clicked(self) -> None:
        from rrational.inspector.report import ReportBuilder

        builder = ReportBuilder(self)
        default_dir = self._report_default_dir()
        suggested = str(default_dir / "rrational_report.html")

        if self.test_mode:
            out_path_str = suggested
        else:
            out_path_str, _ = QFileDialog.getSaveFileName(
                self,
                "Export report (HTML)",
                suggested,
                "HTML files (*.html *.htm);;All files (*.*)",
            )
        if not out_path_str:
            return
        out_path = Path(out_path_str)
        try:
            out_path.write_text(builder.build_html(), encoding="utf-8")
        except OSError as e:
            self._critical("Export failed", f"Could not write report:\n\n{e}")
            return
        self.statusBar().showMessage(f"Wrote HTML report → {out_path.name}", 4000)

    def _on_export_report_markdown_clicked(self) -> None:
        from rrational.inspector.report import ReportBuilder

        builder = ReportBuilder(self)
        default_dir = self._report_default_dir()
        suggested = str(default_dir / "rrational_report.md")

        if self.test_mode:
            out_path_str = suggested
        else:
            out_path_str, _ = QFileDialog.getSaveFileName(
                self,
                "Export report (Markdown)",
                suggested,
                "Markdown files (*.md *.markdown);;All files (*.*)",
            )
        if not out_path_str:
            return
        out_path = Path(out_path_str)
        try:
            out_path.write_text(builder.build_markdown(), encoding="utf-8")
        except OSError as e:
            self._critical("Export failed", f"Could not write report:\n\n{e}")
            return
        self.statusBar().showMessage(f"Wrote Markdown report → {out_path.name}", 4000)

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

    # ------------------------------------------------------------------
    # Phase 16: Section boundary editing
    # ------------------------------------------------------------------
    def _project_path_for_sections(self):
        return self._project.project_path if self._project is not None else None

    def _persist_sections_yaml(self, sections_yaml: dict) -> None:
        """Write the sections.yml back via gui.persistence.save_sections."""
        from rrational.gui.persistence import save_sections

        save_sections(sections_yaml, project_path=self._project_path_for_sections())

    def _load_sections_yaml(self) -> dict:
        from rrational.gui.persistence import load_sections

        return load_sections(project_path=self._project_path_for_sections()) or {}

    def _active_data(self):
        """Return the active dataset's InspectorData or None."""
        if self._active_idx is None:
            return None
        if not (0 <= self._active_idx < len(self._datasets)):
            return None
        return self._datasets[self._active_idx].data

    def _on_section_edited(self, name: str, t_start: float, t_end: float) -> None:
        """Drag finished on a region — update the in-memory SectionMeta
        AND persist the new bounds into sections.yml."""
        data = self._active_data()
        if data is None:
            return
        # Mutate the in-memory section boundary.
        for sec in data.sections:
            if sec.name == name:
                sec.t_start = float(t_start)
                sec.t_end = float(t_end)
                break
        # Persist into sections.yml — preserve any existing definition
        # fields (label, start_events, end_events, description) and only
        # update t_start / t_end. Sections that were never defined in the
        # YAML are created with just the boundary fields.
        sections_yaml = self._load_sections_yaml()
        entry = dict(sections_yaml.get(name) or {})
        entry["t_start"] = float(t_start)
        entry["t_end"] = float(t_end)
        sections_yaml[name] = entry
        self._persist_sections_yaml(sections_yaml)
        self.statusBar().showMessage(f"Updated section '{name}' boundaries", 3000)

    def _on_section_rename_requested(self, old_name: str) -> None:
        """Right-click → Rename. Prompts for a new label + renames in-memory
        + renames in sections.yml (preserving payload), then re-renders the
        plot so the SectionRegion picks up the new label."""
        from qtpy.QtWidgets import QInputDialog

        data = self._active_data()
        if data is None:
            return
        if self.test_mode:
            # In test_mode the test installs its own monkeypatch for
            # QInputDialog.getText; the dialog still executes but returns
            # whatever the patched function says.
            pass
        new_name, ok = QInputDialog.getText(
            self,
            "Rename section",
            "New section name:",
            text=old_name,
        )
        if not ok:
            return
        new_name = (new_name or "").strip()
        if not new_name or new_name == old_name:
            return
        # Update in-memory SectionMeta.
        for sec in data.sections:
            if sec.name == old_name:
                sec.name = new_name
                break
        # Update sections.yml — move the entry under the new key and
        # also update its "label" field if it matches the old name.
        sections_yaml = self._load_sections_yaml()
        if old_name in sections_yaml:
            entry = dict(sections_yaml.pop(old_name))
        else:
            # Section was only known via the .rrational; create an entry
            # so the rename is preserved across reload.
            entry = {}
        # Mirror the new name onto the YAML's "label" field if the user
        # had been keeping label == old_name (the most common case).
        if entry.get("label", old_name) == old_name:
            entry["label"] = new_name
        sections_yaml[new_name] = entry
        self._persist_sections_yaml(sections_yaml)
        # Re-render so the plot's SectionRegion picks up the new name.
        self._browse_tab.on_active_dataset_changed(data)
        self.statusBar().showMessage(
            f"Renamed section '{old_name}' to '{new_name}'", 3000
        )

    def _on_section_delete_requested(self, name: str) -> None:
        """Right-click → Delete. Drops the section from the dataset AND
        from sections.yml, then re-renders."""
        data = self._active_data()
        if data is None:
            return
        data.sections = [s for s in data.sections if s.name != name]
        sections_yaml = self._load_sections_yaml()
        sections_yaml.pop(name, None)
        self._persist_sections_yaml(sections_yaml)
        self._browse_tab.on_active_dataset_changed(data)
        self.statusBar().showMessage(f"Deleted section '{name}'", 3000)

    def _on_section_split_requested(self, name: str, t_split: float) -> None:
        """Right-click → Split. Splits ``name`` at ``t_split`` into
        ``{name}_a`` and ``{name}_b`` with the cursor as the new
        boundary, then persists + re-renders."""
        from rrational.inspector.data_loader import SectionMeta

        data = self._active_data()
        if data is None:
            return
        target = next((s for s in data.sections if s.name == name), None)
        if target is None:
            return
        # Clamp the split point inside the section's range and snap to a beat.
        snapped = float(self._browse_tab._plot._snap_to_beat(float(t_split)))
        if snapped <= target.t_start or snapped >= target.t_end:
            self.statusBar().showMessage(
                f"Split point outside section '{name}' — ignored", 3000
            )
            return
        name_a = f"{name}_a"
        name_b = f"{name}_b"
        # Estimate beat counts proportionally to time (cheap; the actual
        # NN array isn't held by SectionMeta).
        total_dur = target.t_end - target.t_start
        frac_a = (snapped - target.t_start) / total_dur if total_dur > 0 else 0.5
        n_a = max(1, int(round(target.beat_count * frac_a)))
        n_b = max(1, target.beat_count - n_a)
        new_a = SectionMeta(
            name=name_a,
            t_start=target.t_start,
            t_end=snapped,
            beat_count=n_a,
        )
        new_b = SectionMeta(
            name=name_b,
            t_start=snapped,
            t_end=target.t_end,
            beat_count=n_b,
        )
        # Replace the old section with the two halves at the same position.
        idx = data.sections.index(target)
        data.sections[idx : idx + 1] = [new_a, new_b]
        # sections.yml update — keep any existing payload as a template.
        sections_yaml = self._load_sections_yaml()
        template = dict(sections_yaml.pop(name, {}))
        a_entry = dict(template)
        a_entry["t_start"] = target.t_start
        a_entry["t_end"] = snapped
        b_entry = dict(template)
        b_entry["t_start"] = snapped
        b_entry["t_end"] = target.t_end
        sections_yaml[name_a] = a_entry
        sections_yaml[name_b] = b_entry
        self._persist_sections_yaml(sections_yaml)
        self._browse_tab.on_active_dataset_changed(data)
        self.statusBar().showMessage(
            f"Split '{name}' into '{name_a}' / '{name_b}'", 3000
        )
