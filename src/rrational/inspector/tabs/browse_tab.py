"""Browse tab — dataset tree + overview bar + main timeline plot.

This is the Phase 2/3 inspector UI moved into its own QWidget so the
MainWindow can host multiple tabs (Setup, Analysis, Results) alongside
it. All the widget objects (``_dataset_tree``, ``_plot``,
``_overview_bar``, ``_empty_label``) live HERE now; the MainWindow
exposes proxy properties so existing tests don't need to change.

The tab pulls workspace state from its ``self._main_window`` reference
(``_datasets`` and ``_active_idx``). The MainWindow notifies the tab
when those change via ``on_workspace_changed`` / ``on_active_dataset_changed``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtGui import QFont
from qtpy.QtWidgets import (
    QDockWidget,
    QLabel,
    QMainWindow,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rrational.inspector.overview_bar import OverviewBar
from rrational.inspector.plot_widget import RRPlotWidget
from rrational.inspector.tabs.base import InspectorTab

if TYPE_CHECKING:
    from qtpy.QtCore import QByteArray

    from rrational.inspector.data_loader import Dataset, InspectorData

# UserRole payload tags so itemClicked can distinguish "dataset node"
# from "section node" without sniffing the parent.
ROLE_DATASET_IDX = Qt.UserRole + 1
ROLE_SECTION_NAME = Qt.UserRole + 2


class BrowseTab(InspectorTab):
    """The main timeline-browsing tab."""

    TAB_LABEL = "Browse"

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(main_window, parent)
        self._build()

    def _build(self) -> None:
        # Phase 20: replace the old QSplitter with a nested QMainWindow
        # so we can host real QDockWidgets — that gives the user
        # tear-off panels (drag-undock) plus saveState/restoreState
        # geometry persistence à la MNE-LAB.
        self._dock_host = QMainWindow(self)
        # Without this, the inner QMainWindow draws its own frame inside
        # the parent tab, which looks like a window-in-a-window.
        self._dock_host.setWindowFlags(Qt.Widget)

        self._dataset_tree = QTreeWidget()
        self._dataset_tree.setHeaderHidden(True)
        self._dataset_tree.setIndentation(14)
        self._dataset_tree.itemClicked.connect(self._on_tree_item_clicked)
        # Width is now governed by the dock — no maximum cap.

        self._plot = RRPlotWidget()
        self._plot.setFocusPolicy(Qt.StrongFocus)

        self._overview_bar = OverviewBar()
        self._overview_bar.link_to(self._plot)

        self._empty_label = QLabel(
            "No .rrational file loaded.\n\n"
            "Use File → Open .rrational… (Ctrl+O) to load a v2.0 export,\n"
            "or File → Open folder… to load every .rrational in a directory."
        )
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #666; font-size: 14px;")

        # Right-side preprocessing panel (artifact detection + summary).
        # Defer the import so importing browse_tab.py at module load
        # time doesn't drag in NeuroKit2 (which preprocessing_panel
        # uses transitively).
        from rrational.inspector.tabs.preprocessing_panel import PreprocessingPanel

        self._preprocessing_panel = PreprocessingPanel(self._main_window, self)

        # ----- Central widget: plot + overview + empty-state label --------
        middle_pane = QWidget()
        middle_layout = QVBoxLayout(middle_pane)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.addWidget(self._empty_label)
        middle_layout.addWidget(self._overview_bar)
        middle_layout.addWidget(self._plot)
        self._plot.setVisible(False)
        self._overview_bar.setVisible(False)
        self._dock_host.setCentralWidget(middle_pane)

        # ----- Left dock: dataset tree ------------------------------------
        self._datasets_dock = QDockWidget("Datasets", self._dock_host)
        self._datasets_dock.setObjectName("BrowseTab.DatasetsDock")
        self._datasets_dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        self._datasets_dock.setWidget(self._dataset_tree)
        self._dock_host.addDockWidget(Qt.LeftDockWidgetArea, self._datasets_dock)

        # ----- Right dock: preprocessing panel ----------------------------
        self._preprocessing_dock = QDockWidget("Preprocessing", self._dock_host)
        self._preprocessing_dock.setObjectName("BrowseTab.PreprocessingDock")
        self._preprocessing_dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        self._preprocessing_dock.setWidget(self._preprocessing_panel)
        self._dock_host.addDockWidget(Qt.RightDockWidgetArea, self._preprocessing_dock)

        # The tab's own QWidget hosts the dock-host through a VBoxLayout.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._dock_host)

    # ------------------------------------------------------------------
    # Phase 20: dock visibility helpers (wired to MainWindow's View menu)
    # ------------------------------------------------------------------
    def set_datasets_dock_visible(self, visible: bool) -> None:
        self._datasets_dock.setVisible(bool(visible))

    def set_preprocessing_dock_visible(self, visible: bool) -> None:
        self._preprocessing_dock.setVisible(bool(visible))

    def datasets_dock_visible(self) -> bool:
        return self._datasets_dock.isVisible()

    def preprocessing_dock_visible(self) -> bool:
        return self._preprocessing_dock.isVisible()

    def save_dock_state(self) -> "QByteArray":
        return self._dock_host.saveState()

    def restore_dock_state(self, state) -> bool:
        if state is None:
            return False
        try:
            return bool(self._dock_host.restoreState(state))
        except (TypeError, ValueError):  # pragma: no cover - defensive
            return False

    # ------------------------------------------------------------------
    # Notification hooks from MainWindow
    # ------------------------------------------------------------------
    def on_workspace_changed(self) -> None:
        """Dataset list changed: rebuild the sidebar tree."""
        self._dataset_tree.clear()
        for i, ds in enumerate(self._main_window._datasets):
            self._add_dataset_to_tree(i, ds)
        if not self._main_window._datasets:
            self._show_empty_state()

    def on_active_dataset_changed(self, data: "InspectorData | None") -> None:
        if data is None:
            # Inform the panel first when there's no data — it clears
            # toggles and disables Detect immediately.
            self._preprocessing_panel.on_active_dataset_changed(data)
            self._show_empty_state()
            return
        idx = self._main_window._active_idx
        if idx is None or not (0 <= idx < len(self._main_window._datasets)):
            return
        ds = self._main_window._datasets[idx]
        # Render the plot + overlays BEFORE the panel runs — _render_dataset
        # calls plot.set_data which resets the artifact overlay, and the
        # panel's on_active_dataset_changed (Phase 12) auto-restores
        # cached artifacts onto the overlay. Order matters.
        self._render_dataset(ds)
        self._update_tree_active_marker()
        self._preprocessing_panel.on_active_dataset_changed(data)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _render_dataset(self, ds: "Dataset") -> None:
        self._empty_label.setVisible(False)
        self._plot.setVisible(True)
        self._plot.set_data(ds.data)
        for meta in ds.data.sections:
            self._plot.add_section_region(meta)
        for ev in ds.data.events:
            self._plot.add_event_marker(ev)

        self._overview_bar.set_data(ds.data.t, ds.data.v)
        # Visibility depends on the View-menu toggle, which lives on
        # MainWindow. Read its current checked state without poking at
        # widget-level visibility ourselves.
        toggle = getattr(self._main_window, "_toggle_overview_act", None)
        if toggle is None or toggle.isChecked():
            self._overview_bar.setVisible(True)

        self._main_window.statusBar().showMessage(
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

    # ------------------------------------------------------------------
    # Sidebar tree management
    # ------------------------------------------------------------------
    def _add_dataset_to_tree(self, idx: int, ds: "Dataset") -> None:
        top = QTreeWidgetItem(self._dataset_tree, [ds.name])
        top.setData(0, ROLE_DATASET_IDX, idx)
        top.setToolTip(0, str(ds.path) if ds.path else "(synthetic)")
        for meta in ds.data.sections:
            label = f"{meta.name}  ({meta.beat_count} beats, {meta.t_end - meta.t_start:.0f}s)"
            child = QTreeWidgetItem(top, [label])
            child.setData(0, ROLE_DATASET_IDX, idx)
            child.setData(0, ROLE_SECTION_NAME, meta.name)
        top.setExpanded(True)
        self._update_tree_active_marker()

    def _update_tree_active_marker(self) -> None:
        active = self._main_window._active_idx
        for i in range(self._dataset_tree.topLevelItemCount()):
            top = self._dataset_tree.topLevelItem(i)
            font = top.font(0)
            font.setBold(i == active)
            font.setWeight(QFont.Bold if i == active else QFont.Normal)
            top.setFont(0, font)

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        idx = item.data(0, ROLE_DATASET_IDX)
        section_name = item.data(0, ROLE_SECTION_NAME)
        if idx is None:
            return

        if self._main_window._active_idx != idx:
            self._main_window.set_active_dataset(idx)

        if section_name is None:
            return  # top-level click is just an activation

        ds = self._main_window._datasets[idx]
        meta = next((s for s in ds.data.sections if s.name == section_name), None)
        if meta is None:
            return
        self._plot.zoom_to_range(meta.t_start, meta.t_end, padding_frac=0.02)
        self._plot.highlight_section(section_name)
        self._plot.setFocus()
        self._main_window.statusBar().showMessage(
            f"Section '{section_name}': {meta.beat_count} beats, "
            f"{meta.t_end - meta.t_start:.1f}s",
            3000,
        )
