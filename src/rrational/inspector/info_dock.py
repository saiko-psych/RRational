"""Persistent right-side info panel (Cluster C5).

A dockable, MNE-LAB-style metadata sidebar that summarises the active
``InspectorData`` at a glance: filename, approximate sampling
frequency, length, window count, exclusions, annotations and the
pre-processing chain of recorded :class:`Action` tags.

Why a dock and not a plain widget? The user repeatedly opens datasets
across two layout modes (Streamlit + MNELAB); a ``QDockWidget`` lets
them tear it off, move it to the left or hide it via the View menu
without losing the underlying state. This mirrors the existing
``BrowseTab`` dock pattern (``_datasets_dock`` / ``_preprocessing_dock``).

The widget is intentionally a *passive* view — the host pushes a
fresh snapshot via :meth:`InfoDock.set_dataset` whenever the active
dataset, annotations or exclusions change. We keep no signal wiring
here so the dock stays trivially testable.
"""

from __future__ import annotations

import math
from typing import Iterable

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QDockWidget,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from rrational.inspector.data_loader import InspectorData
from rrational.inspector.history.recorder import HistoryRecorder

# Placeholder shown for every metric when no dataset is loaded.
# Em-dash is preferred over the literal string "N/A" for visual calm.
_EMPTY = "—"


def _approx_sfreq_hz(data: InspectorData) -> float | None:
    """Approximate Hz from mean RR (ms): ``f = 60000 / mean_RR_ms``.

    RR series are unevenly sampled by nature, but a "instantaneous-HR"
    style proxy (60000 / mean) gives the user a familiar number to
    sanity-check device output (e.g. ~1 Hz for resting adults).
    Returns None when no finite values are available.
    """
    import numpy as np

    finite = data.v[np.isfinite(data.v)]
    if finite.size == 0:
        return None
    mean_rr = float(finite.mean())
    if mean_rr <= 0:
        return None
    return 60000.0 / mean_rr


def _format_duration(seconds: float) -> str:
    """Render ``seconds`` as ``MM:SS`` (or ``HH:MM:SS`` past an hour)."""
    if not math.isfinite(seconds) or seconds < 0:
        return _EMPTY
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _action_tags(recorder: HistoryRecorder | None) -> list[str]:
    """Extract a stable, human-readable label per recorded action.

    We use the class name as the tag — matches the dataclass naming
    convention already used in ``rrational.inspector.history.actions``
    (LoadRecording, DetectArtifacts, etc.). The recorder may be empty
    or None; both cases yield an empty list.
    """
    if recorder is None:
        return []
    return [type(act).__name__ for act in recorder]


class _CopyableLabel(QWidget):
    """Filename label + small clipboard copy button.

    The button stays hidden until the user hovers the row, mimicking
    GitHub's filename-copy affordance. We use a hover-aware QWidget
    container instead of a stylesheet-only solution so the click
    target is reliably hittable on all platforms.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label = QLabel(_EMPTY, self)
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self._copy_btn = QPushButton("⧉", self)  # square copy glyph
        self._copy_btn.setFlat(True)
        self._copy_btn.setFixedWidth(24)
        self._copy_btn.setToolTip("Copy filename to clipboard")
        self._copy_btn.setVisible(False)
        self._copy_btn.clicked.connect(self._on_copy)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label, 1)
        layout.addWidget(self._copy_btn, 0, Qt.AlignRight)

    def setText(self, text: str) -> None:  # noqa: N802 - Qt convention
        self._label.setText(text)
        # Only offer copy when there's an actual filename behind it.
        self._copy_btn.setVisible(bool(text) and text != _EMPTY)

    def text(self) -> str:
        return self._label.text()

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt convention
        if self._label.text() and self._label.text() != _EMPTY:
            self._copy_btn.setVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt convention
        self._copy_btn.setVisible(False)
        super().leaveEvent(event)

    def _on_copy(self) -> None:
        from qtpy.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._label.text())


class InfoDock(QDockWidget):
    """Right-docked panel summarising the active dataset.

    Construct once per ``MainWindow``; the host calls
    :meth:`set_dataset` on every dataset switch / annotation edit /
    exclusion edit. The dock owns no business logic — the host
    supplies the counts so cross-cutting state (annotation count,
    exclusion count) can be sourced from whichever persistence layer
    is authoritative at the call site.
    """

    OBJECT_NAME = "InfoDock"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Info", parent)
        self.setObjectName(self.OBJECT_NAME)
        self.setFeatures(
            QDockWidget.DockWidgetMovable
            | QDockWidget.DockWidgetFloatable
            | QDockWidget.DockWidgetClosable
        )
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        container = QWidget(self)
        outer = QVBoxLayout(container)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # ---- Form rows ----------------------------------------------------
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignTop | Qt.AlignLeft)
        form.setSpacing(4)

        self._file_label = _CopyableLabel(container)
        form.addRow("File:", self._file_label)

        self._sfreq_label = QLabel(_EMPTY, container)
        form.addRow("Approx. sf:", self._sfreq_label)

        self._length_label = QLabel(_EMPTY, container)
        form.addRow("Length:", self._length_label)

        self._windows_label = QLabel(_EMPTY, container)
        form.addRow("Windows:", self._windows_label)

        self._exclusions_label = QLabel(_EMPTY, container)
        form.addRow("Exclusions:", self._exclusions_label)

        self._annotations_label = QLabel(_EMPTY, container)
        form.addRow("Annotations:", self._annotations_label)

        outer.addLayout(form)

        # ---- Preprocessing chain (separate block, scrollable label) ------
        chain_title = QLabel("Pre-processing chain", container)
        chain_title.setStyleSheet("font-weight: bold; margin-top: 6px;")
        outer.addWidget(chain_title)

        self._chain_label = QLabel(_EMPTY, container)
        self._chain_label.setWordWrap(True)
        self._chain_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._chain_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        outer.addWidget(self._chain_label, 1)

        outer.addStretch(0)
        # Round 22 — slimmer dock so the inspection plot keeps as much
        # horizontal real estate as possible. Users can still drag the
        # splitter handle to widen it on demand.
        container.setMinimumWidth(170)
        container.setMaximumWidth(280)
        self.setWidget(container)

    # ------------------------------------------------------------------
    # Public API — host pushes a snapshot whenever active state changes.
    # ------------------------------------------------------------------
    def set_dataset(
        self,
        data: InspectorData | None,
        *,
        filename: str | None = None,
        recorder: HistoryRecorder | None = None,
        n_windows: int | None = None,
        n_exclusions: int | None = None,
        n_annotations: int | None = None,
    ) -> None:
        """Refresh every row from a new dataset snapshot.

        ``data=None`` resets every row to the empty placeholder — used
        when the user closes all datasets.

        ``n_windows`` / ``n_exclusions`` / ``n_annotations`` default to
        the section count / 0 / 0 when not supplied, so callers without
        external counters still see something meaningful.
        """
        if data is None:
            self.clear()
            return

        # Filename row — prefer explicit ``filename`` over ``data`` since
        # InspectorData does not carry its source path.
        self._file_label.setText(filename or _EMPTY)

        # Sampling-frequency approximation.
        sfreq = _approx_sfreq_hz(data)
        if sfreq is None:
            self._sfreq_label.setText(_EMPTY)
        else:
            self._sfreq_label.setText(f"{sfreq:.2f} Hz")

        # Length: t_end - t_start in seconds (may be 0 for an
        # all-NaN dataset; the formatter handles that case).
        try:
            duration = max(0.0, data.t_end - data.t_start)
        except Exception:
            duration = float("nan")
        self._length_label.setText(_format_duration(duration))

        n_win = len(data.sections) if n_windows is None else int(n_windows)
        self._windows_label.setText(str(n_win))

        n_excl = 0 if n_exclusions is None else int(n_exclusions)
        self._exclusions_label.setText(str(n_excl))

        n_ann = 0 if n_annotations is None else int(n_annotations)
        self._annotations_label.setText(str(n_ann))

        tags = _action_tags(recorder)
        self._chain_label.setText(self._format_chain(tags))

    def clear(self) -> None:
        """Reset every row to the empty placeholder."""
        self._file_label.setText(_EMPTY)
        self._sfreq_label.setText(_EMPTY)
        self._length_label.setText(_EMPTY)
        self._windows_label.setText(_EMPTY)
        self._exclusions_label.setText(_EMPTY)
        self._annotations_label.setText(_EMPTY)
        self._chain_label.setText(_EMPTY)

    # ------------------------------------------------------------------
    # Formatting helpers (separated for testability).
    # ------------------------------------------------------------------
    @staticmethod
    def _format_chain(tags: Iterable[str]) -> str:
        tags = list(tags)
        if not tags:
            return _EMPTY
        # Round 22 — collapse adjacent duplicate action names with a
        # ``(xN)`` multiplier. Without this the chain shows visual noise
        # for repeated calls (e.g. ``set_active_project`` firing twice
        # during auto-load-then-user-open) and clutters the dock with
        # near-identical lines.
        collapsed: list[str] = []
        for t in tags:
            if collapsed and collapsed[-1].split(" ×")[0] == t:
                head = collapsed[-1].split(" ×")[0]
                count = (
                    int(collapsed[-1].split(" ×")[1]) if " ×" in collapsed[-1] else 1
                )
                collapsed[-1] = f"{head} ×{count + 1}"
            else:
                collapsed.append(t)
        return "\n".join(f"• {t}" for t in collapsed)
