"""Reusable help widgets for the inspector tabs.

Phase 24A: introduces ``HelpExpander``, a tiny QGroupBox-with-checkable
header that wraps a rich-text ``QLabel`` body. Used across DataTab,
ParticipantTab, SetupTab panes, AnalysisTab, ResultsTab to surface
in-app help without forcing the user to dig through menus or docs.

The expander honours a global QSettings key
``help_expanders_default_open`` (defaults to ``False``) so a
power-user can opt in once and have every help block start expanded
on launch.
"""

from __future__ import annotations

from qtpy.QtCore import Qt, QSettings
from qtpy.QtWidgets import (
    QGroupBox,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


_DEFAULT_OPEN_KEY = "help_expanders_default_open"


def help_expanders_default_open() -> bool:
    """Return the persisted global "always-expand-help" preference.

    Reads via raw ``QSettings`` rather than ``inspector.settings`` so we
    don't have to register the key in that module's ``_DEFAULTS`` table —
    the help expanders are independent of the rest of the inspector
    configuration and the only fallback we need is a plain ``False``.
    """
    raw = QSettings().value(_DEFAULT_OPEN_KEY, False)
    if isinstance(raw, str):
        return raw.lower() == "true"
    return bool(raw)


def set_help_expanders_default_open(value: bool) -> None:
    """Persist the global "always-expand-help" preference."""
    QSettings().setValue(_DEFAULT_OPEN_KEY, bool(value))


class HelpExpander(QGroupBox):
    """A collapsible help block with a checkable "Show help" header.

    The header (the QGroupBox checkbox) toggles a rich-text body label
    below it. Defaults to collapsed unless the global
    ``help_expanders_default_open`` setting is on.
    """

    def __init__(
        self,
        title: str,
        body_html: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        # GroupBox title shows the topic + a hint that it's interactive.
        self.setTitle(f"Help: {title}")
        self.setToolTip("Click to show or hide the help text for this section.")

        self._body = QLabel(body_html, self)
        self._body.setWordWrap(True)
        self._body.setTextFormat(Qt.RichText)
        self._body.setTextInteractionFlags(
            Qt.TextBrowserInteraction | Qt.LinksAccessibleByMouse
        )
        self._body.setOpenExternalLinks(True)
        self._body.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.addWidget(self._body)

        # Initial state — collapsed unless the global pref is set.
        initial_open = help_expanders_default_open()
        self.setChecked(initial_open)
        self._body.setVisible(initial_open)
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        self._body.setVisible(checked)

    # Useful for tests / programmatic control.
    def is_open(self) -> bool:
        return self.isChecked() and self._body.isVisible()

    def body_label(self) -> QLabel:
        return self._body
