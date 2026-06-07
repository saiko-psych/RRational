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


def format_config_path(rel_path: str) -> str:
    """Resolve ``{project}/<rel_path>`` to a display string for UI labels.

    When a project is active, returns its absolute config path wrapped in
    ``<code>``. When no project is open, shows the ``~/.rrational/``
    fallback with an italic hint. The return value is HTML — suitable
    for use inside a ``QLabel``.

    Panes call this on every render (e.g. inside ``refresh_from_workspace``)
    so the displayed path tracks project open/close events.
    """
    from rrational.inspector.persistence import get_active_project_config_dir

    active = get_active_project_config_dir()
    if active is not None:
        return f"<code>{active / rel_path}</code>"
    return f"<code>~/.rrational/{rel_path}</code> <i>(no project open)</i>"


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

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def format_config_path(self, rel_path: str) -> str:
        """Method-form wrapper around :func:`format_config_path`."""
        return format_config_path(rel_path)

    # ------------------------------------------------------------------
    # UX4: live tab-label state badge
    # ------------------------------------------------------------------
    def tab_label_state(self) -> str:
        """Return a short parenthesised state suffix appended to the tab label.

        Default returns empty string (no badge). Subclasses override to
        surface live state (e.g. ``"(3 datasets)"`` on the Browse tab).
        """
        return ""
