"""Participant tab — per-subject deep-dive (Phase 22.2).

Streamlit-style focused per-participant view. Mirrors the workflow of
``src/rrational/gui/tabs/participant.py`` (Streamlit reference) but in
the PyQt inspector shell:

- Top bar: a participant dropdown listing every loaded dataset's stem,
  plus Previous / Next arrow buttons and a "Showing X of Y" status.
- Left dock: a vertical list of the active participant's sections.
  Clicking a row zooms the plot to that section; the per-row
  "Validate" button shows a brief status-bar acknowledgement.
- Center: the same ``RRPlotWidget`` the Browse tab uses (timeline +
  overlays + crosshair + keyboard nav).
- Right dock: the same ``PreprocessingPanel`` the Browse tab uses
  (workflow stepper + detect / correct / save buttons + Phase 14
  manual marking + Phase 15 exclusion zones + Phase 16 section edit
  mode + Phase 20 annotations).
- Bottom: an NN-intervals summary line — "X corrected of Y total NN
  intervals, artifact rate Z%" — refreshed after every preprocessing
  result.

Splits the monolithic Browse tab into a single-participant focus mode
without duplicating the heavy widgets. The dropdown drives the
workspace's active dataset via ``main_window.set_active_dataset(idx)``;
all the other tabs (and the original Browse tab itself) stay in lock-
step because they share the same notification fan-out.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rrational.inspector.plot_widget import RRPlotWidget
from rrational.inspector.tabs.base import InspectorTab

if TYPE_CHECKING:
    from rrational.inspector.data_loader import Dataset, InspectorData

# UserRole tag so list rows know which section they map to without
# leaning on row index (which is brittle if rows are ever reordered).
_ROLE_SECTION_NAME = Qt.UserRole + 1


class ParticipantTab(InspectorTab):
    """Single-participant deep-dive: dropdown + plot + sections + preprocessing."""

    TAB_LABEL = "Participant"

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(main_window, parent)
        self._build()
        # Populate from whatever the workspace currently holds (the tab
        # may be constructed AFTER datasets have been loaded, e.g. when
        # the user adds the tab partway through a session).
        self.on_workspace_changed()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build(self) -> None:
        # Mirror BrowseTab's nested QMainWindow trick so we can host
        # real QDockWidgets — gives users tear-off panels and Qt's
        # built-in saveState / restoreState geometry persistence.
        self._dock_host = QMainWindow(self)
        self._dock_host.setWindowFlags(Qt.Widget)

        # ----- Top bar: participant picker + arrows + status --------------
        top_bar = QWidget()
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(8, 4, 8, 4)

        top_layout.addWidget(QLabel("<b>Participant:</b>"))

        self._participant_combo = QComboBox()
        self._participant_combo.setMinimumWidth(200)
        self._participant_combo.setToolTip(
            "Choose which loaded recording to inspect. The arrow buttons "
            "step through participants in workspace order."
        )
        # currentIndexChanged fires on both programmatic AND user-driven
        # changes; we filter out the programmatic ones via a guard flag
        # so rebuilding the dropdown doesn't bounce the active dataset.
        self._suppress_combo_signal = False
        self._participant_combo.currentIndexChanged.connect(self._on_combo_changed)
        top_layout.addWidget(self._participant_combo)

        self._prev_btn = QPushButton("<- Previous participant")
        self._prev_btn.setToolTip("Switch to the previous loaded recording")
        self._prev_btn.clicked.connect(self._on_prev_clicked)
        top_layout.addWidget(self._prev_btn)

        self._next_btn = QPushButton("Next participant ->")
        self._next_btn.setToolTip("Switch to the next loaded recording")
        self._next_btn.clicked.connect(self._on_next_clicked)
        top_layout.addWidget(self._next_btn)

        self._status_label = QLabel("No participants loaded.")
        self._status_label.setStyleSheet("color: #555; padding-left: 12px;")
        top_layout.addWidget(self._status_label)
        top_layout.addStretch()

        # ----- Plot + bottom NN summary in the center --------------------
        self._plot = RRPlotWidget()
        self._plot.setFocusPolicy(Qt.StrongFocus)

        self._nn_summary = QLabel("No artifact detection run yet on this participant.")
        self._nn_summary.setStyleSheet(
            "color: #555; padding: 4px 8px; background: #f4f4f4; "
            "border-top: 1px solid #ccc;"
        )
        self._nn_summary.setWordWrap(True)

        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.addWidget(top_bar)
        center_layout.addWidget(self._plot, stretch=1)
        center_layout.addWidget(self._nn_summary)
        self._dock_host.setCentralWidget(center)

        # ----- Left dock: sections list ----------------------------------
        self._sections_list = QListWidget()
        self._sections_list.setToolTip(
            "Click a section to zoom the plot to it. Use the per-row "
            "Validate button to mark the section as reviewed."
        )
        self._sections_list.itemClicked.connect(self._on_section_clicked)

        sections_container = QWidget()
        sections_layout = QVBoxLayout(sections_container)
        sections_layout.setContentsMargins(4, 4, 4, 4)
        sections_layout.addWidget(QLabel("<b>Sections</b>"))
        sections_layout.addWidget(self._sections_list)

        self._sections_dock = QDockWidget("Sections", self._dock_host)
        self._sections_dock.setObjectName("ParticipantTab.SectionsDock")
        self._sections_dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        self._sections_dock.setWidget(sections_container)
        self._dock_host.addDockWidget(Qt.LeftDockWidgetArea, self._sections_dock)

        # ----- Right dock: preprocessing panel ---------------------------
        # Deferred import to keep importing participant_tab.py cheap and
        # to dodge the NeuroKit2 transitive dependency at module-load
        # time. The panel reads ``parent._plot`` to wire its plot
        # signals, so passing ``self`` (where ``self._plot`` is already
        # live) is sufficient.
        from rrational.inspector.tabs.preprocessing_panel import PreprocessingPanel

        self._preprocessing_panel = PreprocessingPanel(self._main_window, self)

        # Wrap a refresh of the bottom summary around the panel's
        # detect-result hook. We monkey-style-wrap by listening to the
        # same attribute the panel itself updates — _last_result — but
        # to keep things simple we just re-render after every plot
        # mutation the panel could trigger. The cheapest hook is the
        # exclusion_zones_changed signal which the panel fires on most
        # of its UI actions; combined with our own re-render in
        # ``on_active_dataset_changed`` that covers every transition.
        self._plot.exclusion_zones_changed.connect(self._refresh_nn_summary)

        self._preprocessing_dock = QDockWidget("Preprocessing", self._dock_host)
        self._preprocessing_dock.setObjectName("ParticipantTab.PreprocessingDock")
        self._preprocessing_dock.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        self._preprocessing_dock.setWidget(self._preprocessing_panel)
        self._dock_host.addDockWidget(Qt.RightDockWidgetArea, self._preprocessing_dock)

        # ----- Outer layout: just hosts the dock-host --------------------
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._dock_host)

    # ------------------------------------------------------------------
    # InspectorTab hooks
    # ------------------------------------------------------------------
    def tab_label_state(self) -> str:
        idx = self._main_window._active_idx
        datasets = self._main_window._datasets
        if not datasets:
            return "(none selected)"
        if idx is None or not (0 <= idx < len(datasets)):
            return "(none selected)"
        stem = self._stem_for(datasets[idx])
        return f"(showing {stem})"

    def on_workspace_changed(self) -> None:
        """Rebuild the dropdown from ``main_window._datasets``."""
        datasets = self._main_window._datasets
        self._suppress_combo_signal = True
        try:
            self._participant_combo.clear()
            for ds in datasets:
                self._participant_combo.addItem(self._stem_for(ds))
            # Re-sync the dropdown to the active dataset (if any) so the
            # user doesn't see a stale selection after a workspace edit.
            idx = self._main_window._active_idx
            if idx is not None and 0 <= idx < self._participant_combo.count():
                self._participant_combo.setCurrentIndex(idx)
        finally:
            self._suppress_combo_signal = False
        self._refresh_buttons_and_status()
        # If there's no active dataset (workspace empty) clear the
        # downstream UI so we don't leave stale section rows / plot
        # curves around.
        if not datasets or self._main_window._active_idx is None:
            self._clear_for_empty_state()

    def on_active_dataset_changed(self, data: "InspectorData | None") -> None:
        # Always notify the panel — it has bookkeeping that runs even
        # when ``data is None`` (clearing toggles, disabling Detect).
        self._preprocessing_panel.on_active_dataset_changed(data)
        if data is None:
            self._clear_for_empty_state()
            return
        idx = self._main_window._active_idx
        datasets = self._main_window._datasets
        if idx is None or not (0 <= idx < len(datasets)):
            return
        ds = datasets[idx]
        # Keep the dropdown in sync with whoever else may have changed
        # the active dataset (e.g. the Browse tab tree).
        self._suppress_combo_signal = True
        try:
            self._participant_combo.setCurrentIndex(idx)
        finally:
            self._suppress_combo_signal = False
        self._render_dataset(ds)
        self._refresh_buttons_and_status()
        self._refresh_nn_summary()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _render_dataset(self, ds: "Dataset") -> None:
        """Push the dataset onto the plot + rebuild the section list."""
        self._plot.set_data(ds.data)
        for meta in ds.data.sections:
            self._plot.add_section_region(meta)
        for ev in ds.data.events:
            self._plot.add_event_marker(ev)
        self._rebuild_sections_list(ds)
        self._plot.setFocus()

    def _rebuild_sections_list(self, ds: "Dataset") -> None:
        self._sections_list.clear()
        for meta in ds.data.sections:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(4, 2, 4, 2)
            label = QLabel(
                f"{meta.name}  "
                f"<span style='color:#888;'>"
                f"({meta.beat_count} beats, "
                f"{meta.t_end - meta.t_start:.0f}s)</span>"
            )
            label.setTextFormat(Qt.RichText)
            row_layout.addWidget(label, stretch=1)
            validate_btn = QPushButton("Validate")
            validate_btn.setToolTip(
                f"Mark section '{meta.name}' as reviewed (status bar acknowledgement)."
            )
            # Default-arg binds the CURRENT name so a future rename
            # doesn't shadow the closure variable.
            validate_btn.clicked.connect(
                lambda _checked=False, name=meta.name: self._on_validate_section(name)
            )
            row_layout.addWidget(validate_btn)

            item = QListWidgetItem(self._sections_list)
            item.setData(_ROLE_SECTION_NAME, meta.name)
            item.setSizeHint(row_widget.sizeHint())
            self._sections_list.addItem(item)
            self._sections_list.setItemWidget(item, row_widget)

    def _clear_for_empty_state(self) -> None:
        """Wipe plot + sections list when there's no active dataset."""
        self._plot.clear_overlays()
        self._plot._curve.clear()
        self._plot._times = None
        self._plot._values = None
        self._sections_list.clear()
        self._nn_summary.setText("No artifact detection run yet on this participant.")

    def _refresh_buttons_and_status(self) -> None:
        datasets = self._main_window._datasets
        n = len(datasets)
        idx = self._main_window._active_idx
        self._prev_btn.setEnabled(n > 1 and idx is not None and idx > 0)
        self._next_btn.setEnabled(n > 1 and idx is not None and idx < n - 1)
        self._participant_combo.setEnabled(n > 0)
        if n == 0:
            self._status_label.setText("No participants loaded.")
        elif idx is None:
            self._status_label.setText(f"Showing none of {n}")
        else:
            self._status_label.setText(f"Showing participant {idx + 1} of {n}")

    def _refresh_nn_summary(self) -> None:
        """Update the bottom NN-intervals summary from the panel's result."""
        result = getattr(self._preprocessing_panel, "_last_result", None)
        if result is None:
            self._nn_summary.setText(
                "No artifact detection run yet on this participant."
            )
            return
        # ``total`` is the number of NN intervals examined; ``len(indices)``
        # is the number of beats flagged + (optionally) corrected by the
        # Kubios algorithm. ``rate`` is already 0.0-1.0.
        total = int(getattr(result, "total", 0))
        corrected = int(len(getattr(result, "indices", [])))
        rate_pct = float(getattr(result, "rate", 0.0)) * 100.0
        self._nn_summary.setText(
            f"{corrected} corrected of {total} total NN intervals, "
            f"artifact rate {rate_pct:.2f}%"
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _stem_for(ds: "Dataset") -> str:
        """Streamlit-style stem: drop any file suffix, fall back to ds.name."""
        if ds.path is not None:
            return ds.path.stem
        # Synthetic / unsaved datasets carry a name like "0012MEBE.rrational";
        # strip the last suffix so the dropdown reads like the participant ID.
        name = ds.name
        if "." in name:
            return name.rsplit(".", 1)[0]
        return name

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_combo_changed(self, idx: int) -> None:
        if self._suppress_combo_signal:
            return
        if idx < 0:
            return
        if not (0 <= idx < len(self._main_window._datasets)):
            return
        if self._main_window._active_idx == idx:
            return
        self._main_window.set_active_dataset(idx)

    def _on_prev_clicked(self) -> None:
        idx = self._main_window._active_idx
        if idx is None or idx <= 0:
            return
        self._main_window.set_active_dataset(idx - 1)

    def _on_next_clicked(self) -> None:
        idx = self._main_window._active_idx
        datasets = self._main_window._datasets
        if idx is None or idx >= len(datasets) - 1:
            return
        self._main_window.set_active_dataset(idx + 1)

    def _on_section_clicked(self, item: QListWidgetItem) -> None:
        name = item.data(_ROLE_SECTION_NAME)
        if name is None:
            return
        idx = self._main_window._active_idx
        if idx is None:
            return
        ds = self._main_window._datasets[idx]
        meta = next((s for s in ds.data.sections if s.name == name), None)
        if meta is None:
            return
        self._plot.zoom_to_range(meta.t_start, meta.t_end, padding_frac=0.02)
        self._plot.highlight_section(name)
        self._plot.setFocus()
        self._main_window.statusBar().showMessage(
            f"Section '{name}': {meta.beat_count} beats, "
            f"{meta.t_end - meta.t_start:.1f}s",
            3000,
        )

    def _on_validate_section(self, name: str) -> None:
        """Acknowledge a section validation through the status bar.

        Phase 22.2 keeps validation lightweight — the heavyweight
        review flow (boundary editing, manual marks) is already
        exposed through the PreprocessingPanel + plot overlays. This
        button just records that the user has eyeballed the section
        and gives them visible feedback.
        """
        self._main_window.statusBar().showMessage(
            f"Section '{name}' marked as validated.", 3000
        )
