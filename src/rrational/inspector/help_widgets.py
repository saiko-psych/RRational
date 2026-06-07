"""Reusable in-app help widgets — MNE-LAB style.

``HelpExpander`` is a thin, single-button row showing a small ``ⓘ Help``
button. Clicking opens a focused popup with the help text. ``InfoButton``
exposes the same icon for callers that want the inline button without
the wrapping QGroupBox semantics.

This mirrors MNE-LAB's "compact UI + focused docs popup" approach
rather than always-visible inline documentation.
"""

from __future__ import annotations

from qtpy.QtCore import Qt, QSettings
from qtpy.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


_DEFAULT_OPEN_KEY = "help_expanders_default_open"


def help_expanders_default_open() -> bool:
    """Persisted "auto-open help popups on launch" preference (default False).

    Retained for API-compat with older callers even though the
    popup-style help no longer needs to track open/closed state across
    tabs.
    """
    raw = QSettings().value(_DEFAULT_OPEN_KEY, False)
    if isinstance(raw, str):
        return raw.lower() == "true"
    return bool(raw)


def set_help_expanders_default_open(value: bool) -> None:
    QSettings().setValue(_DEFAULT_OPEN_KEY, bool(value))


class _HelpPopup(QDialog):
    """Modeless popup that renders one help topic."""

    def __init__(
        self, title: str, body_html: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Help — {title}")
        self.setMinimumWidth(520)
        self.setModal(False)

        layout = QVBoxLayout(self)
        label = QLabel(body_html, self)
        label.setWordWrap(True)
        label.setTextFormat(Qt.RichText)
        label.setTextInteractionFlags(
            Qt.TextBrowserInteraction | Qt.LinksAccessibleByMouse
        )
        label.setOpenExternalLinks(True)
        label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        layout.addWidget(label)

        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.close)
        bb.accepted.connect(self.close)
        layout.addWidget(bb)


class InfoButton(QToolButton):
    """Small ``ⓘ`` button that opens a focused help popup on click."""

    def __init__(
        self,
        title: str,
        body_html: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._body_html = body_html
        # Unicode 'circled information source' — readable, no emoji.
        self.setText("ⓘ Help")
        self.setToolTip(f"Show help: {title}")
        self.setAutoRaise(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.clicked.connect(self._open_popup)

    def _open_popup(self) -> None:
        # Re-create on each click so re-styling / parent-changes work.
        popup = _HelpPopup(self._title, self._body_html, self.window())
        popup.show()


class HelpExpander(QWidget):
    """Thin info-button row that opens a popup with the help text.

    The "Show help" header + expandable body has been replaced by an
    :class:`InfoButton`. Callers that depended on the older GroupBox API
    still get a working widget via the compat methods below.
    """

    def __init__(
        self,
        title: str,
        body_html: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._body_html = body_html

        self._button = InfoButton(title, body_html, self)
        # Keep a hidden QLabel for the body so ``body_label()`` callers
        # still get a real widget (test compat).
        self._body = QLabel(body_html, self)
        self._body.setVisible(False)
        self._body.setTextFormat(Qt.RichText)
        self._body.setWordWrap(True)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(self._button)
        row.addStretch()

    # ------------------------------------------------------------------
    # Compatibility API for older callers expecting a checkable expander
    # ------------------------------------------------------------------
    def is_open(self) -> bool:
        """Always False — popups are transient, not persistent."""
        return False

    def setChecked(self, value: bool) -> None:  # noqa: N802 — Qt-style API
        # Legacy callers might still toggle this. We honour the call by
        # opening the popup once, but don't keep state.
        if value:
            self._button._open_popup()

    def isChecked(self) -> bool:  # noqa: N802
        return False

    def body_label(self) -> QLabel:
        return self._body

    def title(self) -> str:
        return self._title
