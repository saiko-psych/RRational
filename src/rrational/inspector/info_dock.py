"""Persistent right-side info panel (Cluster C5).

A dockable, MNE-LAB-style metadata sidebar that summarises the active
``InspectorData`` at a glance: filename, approximate mean heart rate
(BPM), length, window count, exclusions, annotations and the
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


def _approx_hr_bpm(data: InspectorData) -> float | None:
    """Approximate mean heart rate (BPM) from mean RR (ms): ``HR = 60000 / mean_RR_ms``.

    RR series are unevenly sampled by nature; HR is the meaningful
    sanity-check metric (e.g. ~75 BPM for resting adults).
    Returns None when no finite values are available.

    Earlier builds shipped this as ``_approx_sfreq_hz`` and labelled
    the value "Hz" — that was a unit mislabel: 60000/mean_RR yields
    beats per minute, not samples per second. RR-derived sampling
    frequency would be ``1000 / mean_RR_ms``.
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
        self._full_text = ""
        self._label = QLabel(_EMPTY, self)
        self._label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        # Round 29 — Don't allow the label to push the layout wider than
        # the dock; let Qt elide visually instead. Round 28 visual review
        # caught the filename "negative_rr.csv" rendering as "negative_r".
        self._label.setMinimumWidth(0)
        # paintEvent below handles eliding; the label text stays the
        # full string so selection-copy still gives the user the
        # unabbreviated name.

        self._copy_btn = QPushButton("⧉", self)
        self._copy_btn.setFlat(True)
        self._copy_btn.setFixedWidth(22)
        self._copy_btn.setFixedHeight(22)
        self._copy_btn.setToolTip("Copy filename to clipboard")
        # Round 30 — screen readers announce the raw "⧉" codepoint without
        # setAccessibleName. setToolTip is a sighted-user affordance; AT
        # relies on the accessible-name tree separately.
        self._copy_btn.setAccessibleName("Copy filename to clipboard")
        self._copy_btn.setVisible(False)
        self._copy_btn.clicked.connect(self._on_copy)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self._label, 1)
        layout.addWidget(self._copy_btn, 0, Qt.AlignRight)

    def setText(self, text: str) -> None:  # noqa: N802 - Qt convention
        self._full_text = text
        self._refresh_display()
        # Round 29 — tooltip carries the FULL filename so users can hover
        # to see what the elided label truncated.
        self.setToolTip(text if text and text != _EMPTY else "")
        self._copy_btn.setVisible(bool(text) and text != _EMPTY)

    def text(self) -> str:
        return self._full_text or self._label.text()

    def _refresh_display(self) -> None:
        """Elide ``self._full_text`` to fit the label's current width."""
        from qtpy.QtGui import QFontMetrics

        if not self._full_text or self._full_text == _EMPTY:
            self._label.setText(_EMPTY)
            return
        # Leave room for the copy-button column when computing available width.
        avail = max(40, self._label.width() - 4)
        fm = QFontMetrics(self._label.font())
        elided = fm.elidedText(self._full_text, Qt.ElideMiddle, avail)
        self._label.setText(elided)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt convention
        # Re-elide on dock resize so the filename keeps using all the
        # space that's available without overflowing.
        self._refresh_display()
        super().resizeEvent(event)

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
            # Round 30 — copy the FULL filename, not the elided display
            # string. R29 changed `_label.setText` to hold the elided text
            # for visual rendering, but the copy handler still read from
            # `_label.text()` and was silently copying "negative_r…csv"
            # instead of the real filename.
            clipboard.setText(self._full_text)


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
        container.setObjectName("InfoDockContent")
        outer = QVBoxLayout(container)
        # Round 29 — more breathing room around the edges so the rows
        # don't kiss the dock frame; the previous 8px felt cramped at
        # the slim widths.
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(10)

        # ---- "Dataset" section header -----------------------------------
        dataset_header = QLabel("Dataset", container)
        dataset_header.setObjectName("infoSectionHeader")
        dataset_header.setStyleSheet(
            "QLabel#infoSectionHeader { "
            "font-weight: bold; "
            "padding-bottom: 2px; "
            "border-bottom: 1px solid palette(mid); "
            "}"
        )
        outer.addWidget(dataset_header)

        # ---- Form rows --------------------------------------------------
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFormAlignment(Qt.AlignTop | Qt.AlignLeft)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(7)

        self._file_label = _CopyableLabel(container)
        form.addRow("File:", self._file_label)

        self._hr_label = QLabel(_EMPTY, container)
        form.addRow("Approx. HR:", self._hr_label)

        self._length_label = QLabel(_EMPTY, container)
        form.addRow("Length:", self._length_label)

        self._windows_label = QLabel(_EMPTY, container)
        form.addRow("Windows:", self._windows_label)

        self._exclusions_label = QLabel(_EMPTY, container)
        form.addRow("Exclusions:", self._exclusions_label)

        self._annotations_label = QLabel(_EMPTY, container)
        form.addRow("Annotations:", self._annotations_label)

        outer.addLayout(form)

        # ---- Visual divider before chain block --------------------------
        outer.addSpacing(8)

        # ---- Preprocessing chain header --------------------------------
        chain_title = QLabel("Pre-processing chain", container)
        chain_title.setObjectName("infoSectionHeader")
        chain_title.setStyleSheet(
            "QLabel#infoSectionHeader { "
            "font-weight: bold; "
            "padding-bottom: 2px; "
            "border-bottom: 1px solid palette(mid); "
            "}"
        )
        outer.addWidget(chain_title)

        self._chain_label = QLabel(_EMPTY, container)
        self._chain_label.setWordWrap(True)
        self._chain_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._chain_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        # Muted styling so the empty-state em-dash doesn't shout louder
        # than the actual data above it.
        self._chain_label.setProperty("muted", True)
        outer.addWidget(self._chain_label, 1)

        outer.addStretch(0)
        # Round 29 — slightly wider min so medium filenames (e.g.
        # "negative_rr.csv", "0405SAAD_170325_MEL_0.00-0.40_RRIntervals.csv")
        # have enough room to elide reasonably without dropping every
        # information-bearing character. Users can still drag the dock
        # to a wider split if they need the full path visible.
        container.setMinimumWidth(220)
        container.setMaximumWidth(320)
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

        # Mean-HR approximation (60000 / mean_RR_ms).
        hr = _approx_hr_bpm(data)
        if hr is None:
            self._hr_label.setText(_EMPTY)
        else:
            self._hr_label.setText(f"{hr:.1f} BPM")

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
        self._hr_label.setText(_EMPTY)
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
