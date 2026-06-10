"""Persistent status-bar context widget (Cluster A8).

Sits as a permanent widget on the right edge of the inspector's
status bar between the cursor-readout and the project badge. Always
shows the current interaction mode, the count of exclusion zones,
the count of annotations, and the active dataset's short label so
the user can answer "what am I editing right now?" without hunting
through the toolbar.

The widget is deliberately passive: it exposes a small ``update_*``
API surface that the MainWindow / PreprocessingPanel call from their
existing handlers. There is no observer plumbing — the inspector's
mode toggles and dataset selection already fan out to a small set of
call-sites, so explicit refresh calls keep the data flow obvious
without inventing a new signal bus.
"""

from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel


# Mode-string labels (English, user-facing). Ordering reflects the
# preprocessing-panel checkbox order so the readout matches the UI.
_MODE_LABELS = {
    "normal": "Mode: Normal",
    "exclusion": "Mode: Exclusion",
    "annotation": "Mode: Annotation",
    "manual_mark": "Mode: Manual mark",
    "section_edit": "Mode: Section edit",
}


class StatusBarContext(QLabel):
    """Single-line context label for the status bar.

    Stores the last known values for each field independently so a
    refresh that only knows about one of them (e.g. mode toggled, but
    no dataset switch) does not blow away the others. Use
    ``set_*`` setters one at a time, or ``refresh_all`` from a place
    that has the full snapshot.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("statusBarContext")
        self.setTextFormat(Qt.PlainText)
        self.setMinimumWidth(280)
        # Match the cursor readout's right-edge alignment for visual
        # parity in the status bar.
        self.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self._mode: str = "normal"
        self._dataset: str = "—"
        self._n_annotations: int = 0
        self._n_exclusions: int = 0
        self._render()

    # ------------------------------------------------------------------
    # Public setters — each refreshes the label after updating state.
    # ------------------------------------------------------------------
    def set_mode(self, mode: str) -> None:
        """Set the interaction mode. Unknown modes fall back to Normal."""
        self._mode = mode if mode in _MODE_LABELS else "normal"
        self._render()

    def set_dataset_label(self, label: str | None) -> None:
        self._dataset = label or "—"
        self._render()

    def set_annotation_count(self, n: int) -> None:
        self._n_annotations = max(0, int(n))
        self._render()

    def set_exclusion_count(self, n: int) -> None:
        self._n_exclusions = max(0, int(n))
        self._render()

    def refresh_all(
        self,
        *,
        mode: str,
        dataset: str | None,
        n_annotations: int,
        n_exclusions: int,
    ) -> None:
        """Refresh every field in one call (use when full snapshot known)."""
        self._mode = mode if mode in _MODE_LABELS else "normal"
        self._dataset = dataset or "—"
        self._n_annotations = max(0, int(n_annotations))
        self._n_exclusions = max(0, int(n_exclusions))
        self._render()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _render(self) -> None:
        # Pipe separators read more cleanly than commas in a narrow
        # status bar and let the eye skim segments.
        self.setText(
            f"{_MODE_LABELS[self._mode]}  |  "
            f"Annotations: {self._n_annotations}  |  "
            f"Exclusions: {self._n_exclusions}  |  "
            f"Active: {self._dataset}"
        )
