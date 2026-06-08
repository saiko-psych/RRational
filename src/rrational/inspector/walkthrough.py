"""Multi-page workflow walkthrough dialog.

A QDialog with a stacked-page wizard that walks a new user through the
end-to-end Inspector workflow: Welcome → Project Setup → Data Loading →
Preprocessing → Setup (events / sections / groups / sequences) →
Analysis → Results → Tips & Tricks.

Each page has a title, a description body (rich HTML), and an optional
"Try it now" button that jumps the user into the relevant tab so they
can immediately apply what they just read. Navigation is
Previous / Next / Close at the bottom with a QProgressBar showing
position.

The dialog is reachable from Help → Workflow walkthrough… AND auto-shown
to first-time users via the existing ``inspector.onboarding`` marker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from rrational.inspector.main_window import MainWindow


@dataclass(frozen=True)
class WalkthroughPage:
    """One page in the walkthrough — title, body HTML, optional target."""

    title: str
    body_html: str
    illustration: str = ""
    # When set, a "Try it now" button is shown that switches the main
    # window to the named tab attribute (e.g. "_data_tab").
    try_target_attr: str | None = None
    try_label: str = "Try it now"


# Page content is intentionally short — the in-tab HelpExpander widgets
# carry the depth. These pages get the user oriented; the expanders
# answer follow-up questions in context.
PAGES: tuple[WalkthroughPage, ...] = (
    WalkthroughPage(
        title="Welcome to RRational",
        illustration="[ Inspector overview ]",
        body_html=(
            "<p>This walkthrough takes you from a fresh project to "
            "publication-ready HRV metrics in a few steps.</p>"
            "<p>The inspector is organised as a sequence of tabs along the "
            "top of the window. Each tab has its own in-place help — open the "
            "<b>Help</b> expander at the top of each tab any time.</p>"
            "<p>Use <b>Next</b> and <b>Previous</b> below to flip through the "
            "pages. You can re-open this walkthrough from "
            "<i>Help &rarr; Workflow walkthrough</i>.</p>"
        ),
    ),
    WalkthroughPage(
        title="1. Project setup",
        illustration="[ Project folder ]",
        body_html=(
            "<p>A <b>project</b> is a folder that holds your raw data, "
            "configuration, and exports. It keeps every study "
            "self-contained and shareable.</p>"
            "<p>From the <i>File</i> menu choose <b>New project…</b> or "
            "<b>Open project…</b>. Recent projects are listed under "
            "<i>File &rarr; Open recent project</i>.</p>"
            "<p>You can also work without a project — settings then "
            "fall back to a global config under <code>~/.rrational/</code>.</p>"
        ),
        try_target_attr="_data_tab",
        try_label="Open the Data tab",
    ),
    WalkthroughPage(
        title="2. Loading data",
        illustration="[ Raw-data tree ]",
        body_html=(
            "<p>Drop your raw recordings under <code>data/raw/</code> "
            "(HRV Logger, VNS Analyse, Polar, Empatica, Kubios, Elite HRV, "
            "plain text — all supported).</p>"
            "<p>The <b>Data</b> tab lists every detected file. Double-click "
            "any row to open it; use <i>Load selected source</i> to bulk-load "
            "a whole folder at once.</p>"
            "<p>Already exported <code>.rrational</code> files live under "
            "<code>data/processed/</code> and are shown side-by-side.</p>"
        ),
        try_target_attr="_data_tab",
        try_label="Open the Data tab",
    ),
    WalkthroughPage(
        title="3. Per-participant review and preprocessing",
        illustration="[ Participant plot + Preprocessing panel ]",
        body_html=(
            "<p>Use the <b>Participant</b> tab to step through each loaded "
            "recording with the previous/next buttons.</p>"
            "<p>On the right, the <b>Preprocessing</b> panel runs the "
            "Lipponen 2019 (Kubios) artifact detector. Click "
            "<b>Detect artifacts</b>, review the orange X markers, then "
            "tick <b>Use corrected RR values</b> to switch the plot to the "
            "interpolated series.</p>"
            "<p>For persistent bad segments, enable "
            "<b>Exclusion mode (drag-select)</b> and drag out a time range. "
            "Exclusions and corrections are saved automatically and "
            "respected by every downstream analysis.</p>"
            "<p><b>Plot keyboard shortcuts:</b> <b>a</b> toggles annotation "
            "mode (drag a range to pin a note), <b>e</b> toggles exclusion "
            "mode, <b>r</b> resets the zoom to the full recording, "
            "<b>1</b> / <b>2</b> / <b>3</b> jump to the last 1 min / 10 min / "
            "full window, and the arrow keys pan / zoom.</p>"
        ),
        try_target_attr="_participant_tab",
        try_label="Open the Participant tab",
    ),
    WalkthroughPage(
        title="4. Study structure: events, sections, groups, sequences",
        illustration="[ Setup sub-tabs ]",
        body_html=(
            "<p>The <b>Setup</b> tab defines your study structure. Build "
            "from the inside out:</p>"
            "<ol>"
            "<li><b>Events</b> — canonical names for the markers in your "
            "recordings (e.g. <i>rest_start</i>, plus any synonyms).</li>"
            "<li><b>Sections</b> — time ranges between two events "
            "(e.g. <i>baseline_rest</i> from <i>rest_start</i> to "
            "<i>rest_end</i>).</li>"
            "<li><b>Groups</b> — collections of participants that share a "
            "condition (e.g. <i>control</i> vs <i>treatment</i>).</li>"
            "<li><b>Sequences</b> — ordered playlists of sections that you "
            "want to compare repeatedly.</li>"
            "<li><b>Protocol</b> — optional global metadata.</li>"
            "</ol>"
            "<p>All of this is stored in the project's <code>config/</code> "
            "folder and is shared with the Streamlit app.</p>"
        ),
        try_target_attr="_setup_tab",
        try_label="Open the Setup tab",
    ),
    WalkthroughPage(
        title="5. Analysis",
        illustration="[ Analysis modes ]",
        body_html=(
            "<p>The <b>Analysis</b> tab computes HRV metrics in four modes:</p>"
            "<ul>"
            "<li><b>Single Participant</b> — one recording, one section.</li>"
            "<li><b>Repeating Section</b> — same section across many "
            "participants.</li>"
            "<li><b>Group comparison</b> — between-group Friedman / "
            "RM-ANOVA with Holm post-hoc.</li>"
            "<li><b>Sequence Comparison</b> — within-subject sequence "
            "playback.</li>"
            "</ul>"
            "<p>The top bar lets you pick a metric preset (time-domain, "
            "frequency-domain, both) and the windowing/correction options. "
            "Click <b>Compute</b> to run.</p>"
        ),
        try_target_attr="_analysis_tab",
        try_label="Open the Analysis tab",
    ),
    WalkthroughPage(
        title="6. Results and export",
        illustration="[ Results table ]",
        body_html=(
            "<p>The <b>Results</b> tab collects every computed metric in a "
            "sortable table. Sort by clicking any header; export to CSV "
            "from the buttons below.</p>"
            "<p>For a publication-ready report use "
            "<i>File &rarr; Export report (HTML / Markdown)</i> — the "
            "exporter embeds the relevant plots and DOI-linked "
            "references.</p>"
            "<p>Cached results live in <code>analysis/inspector_results.yml</code> "
            "so closing and re-opening the project never loses work.</p>"
        ),
        try_target_attr="_results_tab",
        try_label="Open the Results tab",
    ),
    WalkthroughPage(
        title="Tips and tricks",
        illustration="[ Productivity ]",
        body_html=(
            "<ul>"
            "<li><b>Help expanders</b> sit at the top of each tab — open the "
            "one you need, or enable <i>Always show help</i> in Preferences "
            "to keep them open by default.</li>"
            "<li><b>Status bar</b> at the bottom shows context hints as "
            "you switch tabs.</li>"
            "<li><b>F1</b> opens the full keyboard-shortcut reference.</li>"
            "<li><b>Project badge</b> in the bottom-left status bar shows "
            "the active project — click it to swap projects.</li>"
            "<li><b>Workflow stepper</b> on the left sidebar (when shown) "
            "highlights the current stage of the analysis.</li>"
            "</ul>"
            "<p>That's it — close this dialog and start exploring. You can "
            "always come back via <i>Help &rarr; Workflow walkthrough</i>.</p>"
        ),
    ),
)


class WalkthroughDialog(QDialog):
    """Multi-page workflow walkthrough using a QStackedWidget."""

    def __init__(
        self,
        main_window: "MainWindow | None" = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent if parent is not None else main_window)
        self._main_window = main_window
        self.setWindowTitle("RRational — Workflow walkthrough")
        self.setMinimumSize(640, 520)

        self._pages: list[WalkthroughPage] = list(PAGES)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 14)
        outer.setSpacing(12)

        self._progress = QProgressBar(self)
        self._progress.setRange(0, max(1, len(self._pages) - 1))
        self._progress.setValue(0)
        self._progress.setFormat("Page %v of %m")
        outer.addWidget(self._progress)

        self._stack = QStackedWidget(self)
        for page in self._pages:
            self._stack.addWidget(self._build_page(page))
        outer.addWidget(self._stack, stretch=1)

        # ---- Nav row -----------------------------------------------------
        nav = QHBoxLayout()
        self._prev_btn = QPushButton("Previous")
        self._prev_btn.setToolTip("Go back to the previous walkthrough page.")
        self._prev_btn.clicked.connect(self._on_prev)
        nav.addWidget(self._prev_btn)

        self._next_btn = QPushButton("Next")
        self._next_btn.setToolTip("Advance to the next walkthrough page.")
        self._next_btn.clicked.connect(self._on_next)
        nav.addWidget(self._next_btn)

        nav.addStretch()

        self._close_btn = QPushButton("Close")
        self._close_btn.setToolTip("Close the walkthrough dialog.")
        self._close_btn.clicked.connect(self.accept)
        nav.addWidget(self._close_btn)

        outer.addLayout(nav)

        # Force progress + button-state refresh for page 0.
        self._stack.currentChanged.connect(self._on_page_changed)
        self._on_page_changed(0)

    # ------------------------------------------------------------------
    def _build_page(self, page: WalkthroughPage) -> QWidget:
        """Construct a QWidget for a single ``WalkthroughPage`` entry."""
        w = QWidget(self)
        layout = QVBoxLayout(w)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        title = QLabel(f"<h2>{page.title}</h2>")
        title.setWordWrap(True)
        layout.addWidget(title)

        if page.illustration:
            illus = QLabel(page.illustration)
            illus.setAlignment(Qt.AlignCenter)
            illus.setStyleSheet(
                "QLabel { color: #888; background: #f4f4f4; "
                "border: 1px dashed #ccc; padding: 18px; }"
            )
            layout.addWidget(illus)

        body = QLabel(page.body_html)
        body.setWordWrap(True)
        body.setTextFormat(Qt.RichText)
        body.setOpenExternalLinks(True)
        body.setAlignment(Qt.AlignTop)
        layout.addWidget(body, stretch=1)

        if page.try_target_attr is not None:
            try_btn = QPushButton(page.try_label, w)
            try_btn.setToolTip(
                "Jump to the relevant tab in the main window without "
                "closing this walkthrough."
            )
            try_btn.clicked.connect(
                lambda _checked=False, attr=page.try_target_attr: self._on_try(attr)
            )
            row = QHBoxLayout()
            row.addStretch()
            row.addWidget(try_btn)
            layout.addLayout(row)

        return w

    # ------------------------------------------------------------------
    def _on_try(self, target_attr: str) -> None:
        """Switch the main window to ``target_attr`` (e.g. ``"_data_tab"``)."""
        if self._main_window is None:
            return
        target = getattr(self._main_window, target_attr, None)
        if target is None:
            return
        tabs = getattr(self._main_window, "_tabs_widget", None)
        if tabs is None:
            return
        idx = tabs.indexOf(target)
        if idx < 0:
            return
        # Only switch if the tab is currently visible in the active
        # layout mode; otherwise the user would see a blank tab.
        if hasattr(tabs, "isTabVisible") and not tabs.isTabVisible(idx):
            return
        tabs.setCurrentIndex(idx)

    def _on_prev(self) -> None:
        idx = self._stack.currentIndex()
        if idx > 0:
            self._stack.setCurrentIndex(idx - 1)

    def _on_next(self) -> None:
        idx = self._stack.currentIndex()
        if idx < self._stack.count() - 1:
            self._stack.setCurrentIndex(idx + 1)

    def _on_page_changed(self, idx: int) -> None:
        self._progress.setValue(idx)
        self._prev_btn.setEnabled(idx > 0)
        # On the last page the Next button is disabled; encourage Close.
        self._next_btn.setEnabled(idx < self._stack.count() - 1)

    # Convenience for tests.
    def page_count(self) -> int:
        return self._stack.count()

    def current_index(self) -> int:
        return self._stack.currentIndex()


def show_walkthrough(main_window: "MainWindow | None" = None) -> WalkthroughDialog:
    """Open the walkthrough dialog (modal). Returns the dialog instance."""
    dlg = WalkthroughDialog(main_window)
    dlg.exec()
    return dlg
