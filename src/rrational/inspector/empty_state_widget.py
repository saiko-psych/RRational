"""Reusable empty-state widget with drop-target affordance (Cluster C4).

Replaces the bare ``QLabel`` placeholders previously scattered through
the inspector with a single dashed-border widget that ships a large
icon and a friendly message. Inspired by Streamlit's ``st.file_uploader``
empty-state and VS Code's "no file open" panel.

The widget exposes a small public surface — message + icon — so callers
just wire ``setVisible`` to dataset-loaded state. Drop-target wiring
(``setAcceptDrops``) is plumbed but the actual file-open handler is the
host's responsibility; the widget emits ``files_dropped`` with the
list of dropped paths.
"""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QDragEnterEvent, QDropEvent, QIcon, QPixmap
from qtpy.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget


_DASHED_QSS = """
QFrame#emptyStateFrame {
    border: 2px dashed #b0b8c1;
    border-radius: 12px;
    background: #fafbfc;
    padding: 32px;
}
QFrame#emptyStateFrame[dragOver="true"] {
    border-color: #2E86AB;
    background: #eaf2f7;
}
QLabel#emptyStateMessage {
    color: #586069;
    font-size: 14px;
}
QLabel#emptyStateIcon {
    padding-bottom: 12px;
}
"""


class EmptyStateWidget(QWidget):
    """Dashed-border placeholder shown when no dataset is loaded.

    ``files_dropped`` carries the absolute paths of files the user
    dropped onto the widget. The host hooks it up to the regular
    file-open routine to provide a one-step "drag-to-open" affordance.
    """

    files_dropped = Signal(list)

    def __init__(self, message: str, icon: QIcon | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setAlignment(Qt.AlignCenter)

        self._frame = QFrame(self)
        self._frame.setObjectName("emptyStateFrame")
        self._frame.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self._frame.setStyleSheet(_DASHED_QSS)

        frame_layout = QVBoxLayout(self._frame)
        frame_layout.setAlignment(Qt.AlignCenter)

        self._icon_label = QLabel()
        self._icon_label.setObjectName("emptyStateIcon")
        self._icon_label.setAlignment(Qt.AlignCenter)
        if icon is not None:
            pixmap: QPixmap = icon.pixmap(64, 64)
            self._icon_label.setPixmap(pixmap)
        frame_layout.addWidget(self._icon_label)

        self._message_label = QLabel(message)
        self._message_label.setObjectName("emptyStateMessage")
        self._message_label.setAlignment(Qt.AlignCenter)
        self._message_label.setWordWrap(True)
        frame_layout.addWidget(self._message_label)

        outer.addWidget(self._frame)

    # ------------------------------------------------------------------
    # Mutators
    # ------------------------------------------------------------------
    def set_message(self, message: str) -> None:
        self._message_label.setText(message)

    def set_icon(self, icon: QIcon) -> None:
        self._icon_label.setPixmap(icon.pixmap(64, 64))

    # ------------------------------------------------------------------
    # Drag + drop
    # ------------------------------------------------------------------
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._frame.setProperty("dragOver", True)
            self._frame.style().unpolish(self._frame)
            self._frame.style().polish(self._frame)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._frame.setProperty("dragOver", False)
        self._frame.style().unpolish(self._frame)
        self._frame.style().polish(self._frame)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        paths: list[Path] = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                paths.append(Path(url.toLocalFile()))
        self._frame.setProperty("dragOver", False)
        self._frame.style().unpolish(self._frame)
        self._frame.style().polish(self._frame)
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
