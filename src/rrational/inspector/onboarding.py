"""UX5: first-run welcome dialog + onboarded-marker management.

Shows a one-time modal walkthrough on first launch explaining the
inspector's five tabs. The user can dismiss it forever via a
"Don't show again" checkbox, which writes a marker file under
``~/.rrational/inspector/onboarded`` (project-INDEPENDENT — onboarding
is a user-level preference).

The walkthrough dialog can be reopened from Help → Show welcome dialog
again.
"""

from __future__ import annotations

from pathlib import Path

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

_MARKER_DIR = Path.home() / ".rrational" / "inspector"
_MARKER_FILE = _MARKER_DIR / "onboarded"


_TAB_DESCRIPTIONS: list[tuple[str, str]] = [
    (
        "Browse",
        "Load a recording (raw .csv/.txt or .rrational v2) and inspect the timeline. "
        "Right-side Preprocessing panel runs artifact detection and lets you save "
        "the cleaned data as .rrational v2.",
    ),
    (
        "Setup",
        "Define groups, events, sections, sequences, and protocol — saved in the "
        "active project's config/ folder (or globally if no project is open). "
        "Shared with the Streamlit app.",
    ),
    (
        "Participants",
        "Link participant IDs to groups and sequences. Import all currently-loaded "
        "datasets as participants in one click.",
    ),
    (
        "Analysis",
        "Compute HRV metrics in 4 modes — Single Participant, Repeating Section, "
        "Group Comparison, Sequence Comparison. Statistics use Friedman + RM-ANOVA "
        "+ Holm-corrected post-hoc.",
    ),
    (
        "Results",
        "Every computed metric in a sortable table. Export as CSV, HTML or Markdown "
        "report with embedded plots and DOI-linked references.",
    ),
]


def is_onboarded() -> bool:
    """Return True if the marker file exists (user dismissed dialog)."""
    return _MARKER_FILE.exists()


def mark_onboarded() -> None:
    """Create the marker file so the welcome dialog is suppressed."""
    _MARKER_DIR.mkdir(parents=True, exist_ok=True)
    _MARKER_FILE.touch()


def reset_onboarded() -> None:
    """Delete the marker file (Help → Show welcome dialog again)."""
    if _MARKER_FILE.exists():
        _MARKER_FILE.unlink()


def show_welcome_dialog(parent: QWidget | None = None) -> None:
    """Open the welcome dialog (modal). Honours "Don't show again"."""
    dlg = WelcomeDialog(parent)
    dlg.exec()


class WelcomeDialog(QDialog):
    """One-time welcome walkthrough listing the inspector's 5 tabs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Welcome to RRational Inspector")
        self.setMinimumWidth(560)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 18, 20, 14)
        outer.setSpacing(14)

        intro = QLabel(
            "<h2>Welcome!</h2>"
            "<p>The Inspector is organised into five tabs. Here's what each one "
            "does — you can return to this overview anytime from "
            "<i>Help → Show welcome dialog again</i>.</p>"
        )
        intro.setWordWrap(True)
        outer.addWidget(intro)

        for name, desc in _TAB_DESCRIPTIONS:
            row = QLabel(f"<b>{name}.</b> {desc}")
            row.setWordWrap(True)
            row.setTextFormat(Qt.RichText)
            outer.addWidget(row)

        self._dont_show_check = QCheckBox("Don't show this again on startup")
        self._dont_show_check.setChecked(True)
        outer.addWidget(self._dont_show_check)

        bb = QDialogButtonBox(QDialogButtonBox.Ok)
        bb.accepted.connect(self._on_ok)
        outer.addWidget(bb)

    def _on_ok(self) -> None:
        if self._dont_show_check.isChecked():
            try:
                mark_onboarded()
            except OSError:  # pragma: no cover - defensive
                pass
        self.accept()
