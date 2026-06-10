"""Welcome widget shown in BrowseTab when no datasets are loaded.

Actionable landing screen instead of a bare empty-state label. The
user immediately sees the two most common entry points (open recording
/ open .rrational v2) plus project actions and a clickable recent-files
list.

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

# Stable name used by the File-menu entry, tests and the welcome button
# alike. Centralised so renaming touches one place.
DEMO_DATASET_NAME = "Demo recording (5 min)"


def make_demo_dataset():
    """Build a 5-min synthetic HRV recording with three sections.

    Layout: ``rest_pre`` (1 min) -> ``music`` (3 min) -> ``rest_post``
    (1 min), with realistic mean RR (~830 ms at rest, ~760 ms during
    music) and Gaussian beat-to-beat variability so the plot looks like
    a real recording instead of a flat line. Returned Dataset has no
    ``path`` (it's synthetic), which the inspector handles fine.
    """
    import numpy as np

    from rrational.inspector.data_loader import (
        Dataset,
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    rng = np.random.default_rng(seed=42)
    base = 1_700_000_000.0  # arbitrary epoch anchor
    rr_ms_rest_pre = 830 + 30 * rng.standard_normal(60)
    rr_ms_music = 760 + 25 * rng.standard_normal(180)  # higher HR
    rr_ms_post = 820 + 28 * rng.standard_normal(60)
    rr_ms = np.concatenate([rr_ms_rest_pre, rr_ms_music, rr_ms_post])
    # Cumulative RR sums give a strictly increasing beat-time axis.
    t = base + np.cumsum(rr_ms) / 1000.0

    sections = [
        SectionMeta(
            name="rest_pre",
            t_start=float(t[0]),
            t_end=float(t[59]),
            beat_count=60,
        ),
        SectionMeta(
            name="music",
            t_start=float(t[60]),
            t_end=float(t[239]),
            beat_count=180,
        ),
        SectionMeta(
            name="rest_post",
            t_start=float(t[240]),
            t_end=float(t[-1]),
            beat_count=60,
        ),
    ]
    events = [
        EventMeta(label="rest_pre_start", t=float(t[0])),
        EventMeta(label="music_start", t=float(t[60])),
        EventMeta(label="rest_post_start", t=float(t[240])),
    ]
    data = InspectorData(t=t, v=rr_ms, sections=sections, events=events)
    return Dataset(name=DEMO_DATASET_NAME, data=data)


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
        # Round 16 — equal-weight top + bottom stretchers center the
        # content block vertically. The previous 1:2 ratio lifted the
        # title to the upper-third which the post-R15 visual inspection
        # flagged as "sitting above the optical center" (issue L2).
        root.addStretch(1)

        # ----- Title block -----------------------------------------------
        title = QLabel("RRational")
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
        # "muted" QSS property paints the secondary text colour from the
        # active theme palette — works on both dark and light modes.
        subtitle.setProperty("muted", True)
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
        # The three landing-screen entry buttons are the canonical
        # primary actions of the whole app — flag them as primary so the
        # QSS theme paints them with the amber accent fill.
        self._open_recording_btn = self._make_action_button(
            "Open recording...",
            "Open any supported RR file (.rrational, .csv, .txt, .dat)",
            primary=True,
        )
        self._open_recording_btn.clicked.connect(self._on_open_recording)
        primary_row.addWidget(self._open_recording_btn)

        self._open_rrational_btn = self._make_action_button(
            "Open .rrational v2...",
            "Open only RRational v2 export files",
            primary=True,
        )
        self._open_rrational_btn.clicked.connect(self._on_open_rrational)
        primary_row.addWidget(self._open_rrational_btn)

        self._try_demo_btn = self._make_action_button(
            "Try with sample data",
            "Load a synthetic 5-minute recording so you can explore the inspector "
            "without your own data",
            primary=True,
        )
        self._try_demo_btn.clicked.connect(self._on_try_demo)
        primary_row.addWidget(self._try_demo_btn)
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
        recent_header.setProperty("heading", True)
        recent_header.setAlignment(Qt.AlignCenter)
        root.addWidget(recent_header)

        self._recent_container = QFrame()
        self._recent_layout = QVBoxLayout(self._recent_container)
        self._recent_layout.setContentsMargins(0, 0, 0, 0)
        self._recent_layout.setSpacing(4)
        self._recent_layout.setAlignment(Qt.AlignHCenter)
        root.addWidget(self._recent_container, alignment=Qt.AlignHCenter)

        # Round 16 — italicise + slightly enlarge the empty-state hint
        # so "(no recent files)" reads as a deliberate state rather than
        # an anonymous gap below the header. Colour pulls from the
        # ``hint`` QSS property which is wired to ``text_muted`` in
        # both dark + light themes.
        self._empty_recent_label = QLabel("No recordings opened yet.")
        self._empty_recent_label.setProperty("hint", True)
        self._empty_recent_label.setAlignment(Qt.AlignCenter)
        empty_font = QFont()
        empty_font.setPointSize(11)
        empty_font.setItalic(True)
        self._empty_recent_label.setFont(empty_font)
        root.addWidget(self._empty_recent_label)

        # Equal-weight stretchers above + below the content block
        # vertically center the whole welcome screen. Round 16 (L2).
        root.addStretch(1)

    def _make_action_button(
        self, label: str, tooltip: str, primary: bool = False
    ) -> QPushButton:
        btn = QPushButton(label)
        btn.setToolTip(tooltip)
        btn.setMinimumHeight(40)
        btn.setMinimumWidth(220)
        btn.setCursor(Qt.PointingHandCursor)
        if primary:
            # Re-polish after setProperty so the QSS selector
            # QPushButton[primary="true"] takes effect — Qt only
            # re-evaluates property selectors on a polish pass.
            btn.setProperty("primary", True)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
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
        # Flat buttons get the accent-coloured link styling from the
        # central QSS via the :flat pseudo state — no per-button override.
        btn.setFlat(True)
        btn.setCursor(Qt.PointingHandCursor)
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

    def _on_try_demo(self) -> None:
        """Load a synthetic demo dataset and switch to it."""
        self._main_window.load_demo_dataset()
