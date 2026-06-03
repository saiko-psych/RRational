"""Shared base class for inspector tabs.

Each tab inherits from ``InspectorTab`` (which is itself a thin QWidget
wrapper) and implements the two notification hooks:

- ``on_workspace_changed()`` — fired when the dataset list itself
  changes (a file was opened/closed). Used by tabs that show a
  per-dataset list (the Browse tab's sidebar tree).
- ``on_active_dataset_changed(data)`` — fired when the user picks a
  different dataset to focus on. The Browse tab re-renders the plot;
  Analysis re-runs metrics on the new data; etc.

Default implementations are no-ops so subclasses only override what
they care about.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtWidgets import QWidget

if TYPE_CHECKING:
    from rrational.inspector.data_loader import InspectorData
    from rrational.inspector.main_window import MainWindow


class InspectorTab(QWidget):
    """Base class for every top-level tab inside the inspector."""

    # Human-readable label shown on the tab. Subclasses override.
    TAB_LABEL: str = "Untitled"

    def __init__(self, main_window: "MainWindow", parent=None) -> None:
        super().__init__(parent)
        self._main_window = main_window

    # ------------------------------------------------------------------
    # Notification hooks (default no-ops)
    # ------------------------------------------------------------------
    def on_workspace_changed(self) -> None:
        """The list of loaded datasets changed (file added or removed)."""

    def on_active_dataset_changed(self, data: "InspectorData | None") -> None:
        """A different dataset is now active; re-render UI as needed."""
