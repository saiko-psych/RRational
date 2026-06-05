"""Welcome widget shown in BrowseTab when no datasets are loaded.

UX2 fix: replaces the bare "no .rrational loaded" QLabel with an
actionable landing screen. The user immediately sees the two most
common entry points (open recording / open .rrational v2) plus
project actions and a clickable recent-files list.

The widget is wholly stateless — it reads recent files from
``inspector.settings`` on every ``refresh()`` call. Buttons emit
plain Python callables (looked up off the MainWindow) rather than
Qt signals, so wiring stays trivial and tests can intercept them
with monkeypatch.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtGui import QFont
from qtpy.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from rrational.inspector.main_window import MainWindow


class WelcomeWidget(QWidget):
    """Landing screen shown when the BrowseTab has no active dataset."""

    # Cap on the number of recent files shown.
    MAX_RECENT_SHOWN = 5

    def __init__(
        self, main_window: "MainWindow", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._main_window = main_window
        self._recent_buttons: list[QPushButton] = []
        self._build()
        self.refresh()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 30, 40, 30)
        root.setSpacing(20)
        root.addItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))

        # ----- Title block -----------------------------------------------
        title = QLabel("RRational Inspector")
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        root.addWidget(title)

        subtitle = QLabel(
            "Scrollable RR-interval browser for the RRational HRV toolkit"
        )
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: #777; font-size: 12px;")
        root.addWidget(subtitle)

        root.addItem(QSpacerItem(0, 20, QSizePolicy.Minimum, QSizePolicy.Fixed))

        prompt = QLabel("What do you want to do?")
        prompt_font = QFont()
        prompt_font.setPointSize(13)
        prompt.setFont(prompt_font)
        prompt.setAlignment(Qt.AlignCenter)
        root.addWidget(prompt)

        # ----- Primary action row (open recording / open .rrational) -----
        primary_row = QHBoxLayout()
        primary_row.setSpacing(12)
        primary_row.addStretch(1)
        self._open_recording_btn = self._make_action_button(
            "Open recording...",
            "Open any supported RR file (.rrational, .csv, .txt, .dat)",
        )
        self._open_recording_btn.clicked.connect(self._on_open_recording)
        primary_row.addWidget(self._open_recording_btn)

        self._open_rrational_btn = self._make_action_button(
            "Open .rrational v2...",
            "Open only RRational v2 export files",
        )
        self._open_rrational_btn.clicked.connect(self._on_open_rrational)
        primary_row.addWidget(self._open_rrational_btn)
        primary_row.addStretch(1)
        root.addLayout(primary_row)

        # ----- Secondary action row (project) ----------------------------
        secondary_row = QHBoxLayout()
        secondary_row.setSpacing(12)
        secondary_row.addStretch(1)
        self._open_project_btn = self._make_action_button(
            "Open project folder",
            "Open an existing RRational project folder",
        )
        self._open_project_btn.clicked.connect(self._on_open_project)
        secondary_row.addWidget(self._open_project_btn)

        self._new_project_btn = self._make_action_button(
            "Create new project",
            "Create a new RRational project (folder + manifest)",
        )
        self._new_project_btn.clicked.connect(self._on_new_project)
        secondary_row.addWidget(self._new_project_btn)
        secondary_row.addStretch(1)
        root.addLayout(secondary_row)

        # ----- Recent files block ----------------------------------------
        root.addItem(QSpacerItem(0, 20, QSizePolicy.Minimum, QSizePolicy.Fixed))

        recent_header = QLabel(f"Recent files (last {self.MAX_RECENT_SHOWN}):")
        recent_header.setStyleSheet("color: #555; font-weight: bold;")
        recent_header.setAlignment(Qt.AlignCenter)
        root.addWidget(recent_header)

        self._recent_container = QFrame()
        self._recent_layout = QVBoxLayout(self._recent_container)
        self._recent_layout.setContentsMargins(0, 0, 0, 0)
        self._recent_layout.setSpacing(4)
        self._recent_layout.setAlignment(Qt.AlignHCenter)
        root.addWidget(self._recent_container, alignment=Qt.AlignHCenter)

        self._empty_recent_label = QLabel("(no recent files)")
        self._empty_recent_label.setStyleSheet("color: #999; font-style: italic;")
        self._empty_recent_label.setAlignment(Qt.AlignCenter)
        root.addWidget(self._empty_recent_label)

        root.addItem(QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))

    def _make_action_button(self, label: str, tooltip: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setToolTip(tooltip)
        btn.setMinimumHeight(40)
        btn.setMinimumWidth(220)
        btn.setCursor(Qt.PointingHandCursor)
        return btn

    # ------------------------------------------------------------------
    # Recent files
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Rebuild the recent-files list. Cheap; safe to call often."""
        # Clear previous buttons.
        for btn in self._recent_buttons:
            self._recent_layout.removeWidget(btn)
            btn.deleteLater()
        self._recent_buttons.clear()

        from rrational.inspector import settings

        try:
            recents = settings.get_recent_files()
        except Exception:
            recents = []
        recents = recents[: self.MAX_RECENT_SHOWN]

        if not recents:
            self._empty_recent_label.setVisible(True)
            self._recent_container.setVisible(False)
            return

        self._empty_recent_label.setVisible(False)
        self._recent_container.setVisible(True)

        for path in recents:
            self._add_recent_button(path)

    def _add_recent_button(self, path: Path) -> None:
        btn = QPushButton(path.name)
        btn.setToolTip(str(path))
        btn.setFlat(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            "QPushButton { color: #1a5fb4; text-align: left; padding: 2px 8px; }"
            "QPushButton:hover { text-decoration: underline; }"
        )
        btn.clicked.connect(lambda _checked=False, p=path: self._on_recent_clicked(p))
        self._recent_layout.addWidget(btn)
        self._recent_buttons.append(btn)

    # ------------------------------------------------------------------
    # Button handlers — delegate to MainWindow so behaviour stays in one
    # place.
    # ------------------------------------------------------------------
    def _on_open_recording(self) -> None:
        self._main_window._on_open_clicked()

    def _on_open_rrational(self) -> None:
        self._main_window._on_open_rrational_only_clicked()

    def _on_open_project(self) -> None:
        self._main_window._on_open_project_clicked()

    def _on_new_project(self) -> None:
        self._main_window._on_new_project_clicked()

    def _on_recent_clicked(self, path: Path) -> None:
        self._main_window.open_path(path)
