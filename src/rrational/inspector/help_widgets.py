"""Reusable in-app help widgets — MNE-LAB style.

Phase 24A originally shipped ``HelpExpander`` as a checkable GroupBox
that took up permanent vertical space on every tab. User feedback
("die help sections mit checkboxen ist eine schlechte lösung — siehe
wie MNE es gemacht hat") prompted a redesign:

- The new ``HelpExpander`` is a thin, single-button row showing a small
  ``ⓘ Help`` button. Clicking opens a focused popup with the help text.
- API-compatible with Phase 24A: same constructor signature, same
  ``is_open()`` / ``body_label()`` accessors, so the five tab files
  that already use it work without modification.
- Also exposes ``InfoButton`` for new callers who want the inline icon
  without the wrapping QGroupBox semantics.

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

    Retained for API-compat with Phase 24A even though the new
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
    """Phase 24A compatibility shim — renders as a thin info-button row.

    Same constructor signature as the original. The "Show help" header +
    expandable body has been replaced by an :class:`InfoButton` that
    opens a popup. Callers that depended on the GroupBox API still get
    a working widget; the visual chrome differs but nothing breaks.
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
    # Phase 24A compatibility API
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
