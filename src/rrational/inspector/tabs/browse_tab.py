"""Browse tab — dataset tree + overview bar + main timeline plot.

All the widget objects (``_dataset_tree``, ``_plot``, ``_overview_bar``,
``_empty_label``) live HERE; the MainWindow exposes proxy properties so
external callers can keep reaching them on MainWindow.

The tab pulls workspace state from its ``self._main_window`` reference
(``_datasets`` and ``_active_idx``). The MainWindow notifies the tab
when those change via ``on_workspace_changed`` / ``on_active_dataset_changed``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QDockWidget,
    QMainWindow,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rrational.inspector.empty_state_widget import EmptyStateWidget
from rrational.inspector.overview_bar import OverviewBar
from rrational.inspector.plot_widget import RRPlotWidget
from rrational.inspector.tabs.base import InspectorTab
from rrational.inspector.workspace_tree import (
    ROLE_DATASET_IDX,
    ROLE_SECTION_NAME,
    WorkspaceItem,
    WorkspaceTreeWidget,
)

if TYPE_CHECKING:
    from qtpy.QtCore import QByteArray

    from rrational.inspector.data_loader import Dataset, InspectorData


class BrowseTab(InspectorTab):
    """The main timeline-browsing tab."""

    TAB_LABEL = "Browse"

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(main_window, parent)
        self._build()

    def _build(self) -> None:
        # Use a nested QMainWindow so we can host real QDockWidgets —
        # that gives the user tear-off panels (drag-undock) plus
        # saveState/restoreState geometry persistence à la MNE-LAB.
        self._dock_host = QMainWindow(self)
        # Without this, the inner QMainWindow draws its own frame inside
        # the parent tab, which looks like a window-in-a-window.
        self._dock_host.setWindowFlags(Qt.Widget)

        # Cluster-C6 sidebar: tree with status-pill badges + theme-aware
        # delegate. ``WorkspaceTreeWidget`` is a QTreeWidget subclass so
        # external callers (proxy properties, navigation helpers, tests)
        # that talk QTreeWidget API keep working without changes.
        self._dataset_tree = WorkspaceTreeWidget()
        self._dataset_tree.itemClicked.connect(self._on_tree_item_clicked)
        # Width is now governed by the dock — no maximum cap.

        self._plot = RRPlotWidget()
        self._plot.setFocusPolicy(Qt.StrongFocus)
        # Bug B4: lock in a sane minimum so the dock layout cannot squeeze
        # the central plot down to a sliver when both side docks claim
        # space. Without this, the snapshot harness occasionally captured
        # the plot at ~400 px wide on first paint before the layout had
        # a chance to settle.
        # Modest plot floor so the Browse dock host — and thus the whole
        # window — can shrink; 300 px still shows a usable tachogram.
        self._plot.setMinimumSize(300, 260)

        self._overview_bar = OverviewBar()
        self._overview_bar.link_to(self._plot)

        # Actionable WelcomeWidget — 4 large action buttons +
        # recent-files list — primary empty-state UI. The EmptyStateWidget
        # below provides the drag-and-drop affordance: it sits inside the
        # WelcomeWidget area as a secondary drop target, surfaces a clear
        # call-to-action ("Drop files here"), and forwards dropped paths
        # to ``MainWindow.open_path``.
        from rrational.inspector.assets import app_icon
        from rrational.inspector.welcome_widget import WelcomeWidget

        self._welcome_widget = WelcomeWidget(self._main_window, parent=self)

        # Cluster-C4 drop target. ``files_dropped`` carries Path objects;
        # we route them one-by-one to the canonical ``open_path`` handler
        # so the same code path that powers File-Open also serves drag-drop.
        self._empty_state = EmptyStateWidget(
            message="Drop RR or .rrational files here",
            icon=app_icon(),
            parent=self,
        )
        self._empty_state.files_dropped.connect(self._on_files_dropped)
        self._empty_state.setVisible(False)

        # Back-compat alias: callers used to flip ``_empty_label.setVisible``
        # on / off — that no-op fallback is preserved through this alias.
        self._empty_label = self._empty_state

        # Right-side preprocessing panel (artifact detection + summary).
        # Defer the import so importing browse_tab.py at module load
        # time doesn't drag in NeuroKit2 (which preprocessing_panel
        # uses transitively).
        from rrational.inspector.tabs.preprocessing_panel import PreprocessingPanel

        self._preprocessing_panel = PreprocessingPanel(self._main_window, self)

        # ----- Central widget: welcome / plot / overview ----------------
        middle_pane = QWidget()
        middle_layout = QVBoxLayout(middle_pane)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        # Round 22 — without an explicit ``stretch`` factor on the plot,
        # the VBoxLayout split the available height evenly across welcome
        # widget, empty label, overview bar and plot. When welcome +
        # empty hide on first load, the layout *kept* their reserved
        # vertical slots and squeezed the plot down to a thin band that
        # rendered as a totally black middle pane in user reports.
        # Giving the plot stretch=1 (welcome stretch=0) makes it consume
        # all leftover height the moment the welcome widget hides.
        middle_layout.addWidget(self._welcome_widget, 0)
        middle_layout.addWidget(self._empty_label, 0)
        middle_layout.addWidget(self._overview_bar, 0)
        middle_layout.addWidget(self._plot, 1)
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
        # Bug B4: hint the dock area to give the sidebar a fixed-ish slice
        # rather than the default 50/50 split, so the central plot keeps
        # the bulk of the horizontal real estate.
        self._dataset_tree.setMinimumWidth(170)
        self._dataset_tree.setMaximumWidth(320)
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
        # Bug B4: same width cap as the left dock — keeps the central
        # plot from being squeezed when both side docks are visible.
        self._preprocessing_panel.setMinimumWidth(260)
        self._preprocessing_panel.setMaximumWidth(360)
        self._dock_host.addDockWidget(Qt.RightDockWidgetArea, self._preprocessing_dock)

        # The tab's own QWidget hosts the dock-host through a VBoxLayout.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._dock_host)

    # ------------------------------------------------------------------
    # Dock visibility helpers (wired to MainWindow's View menu)
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
    # Tab-label state badge
    # ------------------------------------------------------------------
    def tab_label_state(self) -> str:
        """Round 16 — unified format ``(N)``; empty workspace shows no
        suffix at all so the tab label reads as plain "Browse" instead
        of the louder "(empty)" hint."""
        n = len(self._main_window._datasets)
        return f"({n})" if n else ""

    # ------------------------------------------------------------------
    # Notification hooks from MainWindow
    # ------------------------------------------------------------------
    def on_workspace_changed(self) -> None:
        """Dataset list changed: rebuild the sidebar tree."""
        items = [
            self._build_workspace_item(i, ds)
            for i, ds in enumerate(self._main_window._datasets)
        ]
        self._dataset_tree.set_items(items)
        self._update_tree_active_marker()
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
        # panel's on_active_dataset_changed auto-restores cached artifacts
        # onto the overlay. Order matters.
        self._render_dataset(ds)
        self._update_tree_active_marker()
        self._preprocessing_panel.on_active_dataset_changed(data)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _render_dataset(self, ds: "Dataset") -> None:
        # Hide welcome widget when actual data is shown.
        self._welcome_widget.setVisible(False)
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
        # Drop target is part of the empty-state UI — show it so drag-drop
        # delivers files to ``MainWindow.open_path``.
        self._empty_state.setVisible(True)
        # Welcome widget replaces the bare empty label.
        self._welcome_widget.setVisible(True)
        self._welcome_widget.refresh()  # refresh recent-files list

    # ------------------------------------------------------------------
    # Sidebar tree management
    # ------------------------------------------------------------------
    def _build_workspace_item(self, idx: int, ds: "Dataset") -> WorkspaceItem:
        """Translate one Dataset into a tree-ready WorkspaceItem with badges."""
        children: list[WorkspaceItem] = []
        for meta in ds.data.sections:
            label = (
                f"{meta.name}  ({meta.beat_count} beats, "
                f"{meta.t_end - meta.t_start:.0f}s)"
            )
            children.append(
                WorkspaceItem(
                    name=label,
                    dataset_idx=idx,
                    section_name=meta.name,
                )
            )
        return WorkspaceItem(
            name=ds.name,
            dataset_idx=idx,
            badges=self._compute_badges_for(ds),
            tooltip=str(ds.path) if ds.path else "(synthetic)",
            children=children,
        )

    def _compute_badges_for(self, ds: "Dataset") -> list[str]:
        """Derive status-pill tags for one dataset row.

        Heuristic-driven so missing optional attributes never raise; the
        sidebar is a status surface, not a strict spec.

        Tags
        ----
        ``PROC``    — preprocessing has run (cached artifacts present).
        ``SECTIONS`` — recording has more than one named section.
        ``BAD-Q``   — artifact ratio above the 5% triage threshold.
        ``KUBIOS``  — recording originated from a Kubios-format source.
        ``BIDS``    — file path matches the BIDS physio naming convention.
        """
        badges: list[str] = []

        # PROC — any cached artifact result attached to the dataset?
        has_proc = (
            getattr(ds, "preprocessing_result", None) is not None
            or getattr(ds, "artifact_indices", None) is not None
            or getattr(ds.data, "preprocessing_result", None) is not None
        )
        if has_proc:
            badges.append("PROC")

        # SECTIONS — only badge multi-section recordings; single-section is
        # the uninteresting common case. "SECTIONS" replaced the cryptic
        # "N-WIN" (which implied analysis *windows*, not sections) after a
        # naive-user dogfooding pass flagged it as unreadable.
        n_sections = len(getattr(ds.data, "sections", []) or [])
        if n_sections > 1:
            badges.append("SECTIONS")

        # BAD-Q — artifact ratio from cache or NaN-fraction in the timeline
        # as a coarse fallback (full preprocessing summary lives elsewhere).
        ratio = getattr(ds, "artifact_ratio", None)
        if ratio is None:
            v = getattr(ds.data, "v", None)
            if v is not None and len(v) > 0:
                try:
                    ratio = float(np.isnan(v).sum()) / float(len(v))
                except (TypeError, ValueError):  # pragma: no cover - defensive
                    ratio = None
        if ratio is not None and ratio > 0.05:
            badges.append("BAD-Q")

        # KUBIOS — explicit source-app marker on either the dataset or the
        # underlying recording metadata.
        source_app = getattr(ds, "source_app", "") or getattr(ds.data, "source_app", "")
        if isinstance(source_app, str) and "kubios" in source_app.lower():
            badges.append("KUBIOS")

        # BIDS — recognise BIDS-physio TSVs by their canonical suffix.
        path = getattr(ds, "path", None)
        if path is not None and str(path).endswith("_recording-cardiac_physio.tsv.gz"):
            badges.append("BIDS")

        return badges

    def _add_dataset_to_tree(self, idx: int, ds: "Dataset") -> None:
        """Append a single Dataset to the sidebar tree.

        Kept for backward compatibility with any caller / test that still
        invokes it directly. The new code path rebuilds the tree wholesale
        via :meth:`on_workspace_changed`.
        """
        self._dataset_tree.add_item(self._build_workspace_item(idx, ds))
        self._update_tree_active_marker()

    def _update_tree_active_marker(self) -> None:
        self._dataset_tree.set_active_index(self._main_window._active_idx)

    def _on_files_dropped(self, paths: list) -> None:
        """Route drag-and-drop file paths through ``MainWindow.open_path``.

        ``paths`` arrives as a list of ``pathlib.Path``. We open each in
        turn — the canonical handler already manages dedup, error
        dialogs, and the recent-files MRU list.
        """
        from pathlib import Path

        open_path = getattr(self._main_window, "open_path", None)
        if open_path is None:  # pragma: no cover - defensive
            return
        for raw in paths:
            try:
                open_path(Path(raw))
            except Exception as exc:  # noqa: BLE001 - keep loop going
                self._main_window.statusBar().showMessage(
                    f"Could not open {raw}: {exc}", 4000
                )

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
