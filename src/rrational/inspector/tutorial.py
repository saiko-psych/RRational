"""Interactive coach-mark tutorial for the Inspector.

Unlike the read-through ``walkthrough`` wizard, this drives the user through
the real UI: a translucent overlay spotlights the actual widget for each step,
shows an instruction bubble, and — for action steps — waits for the user's real
action, detects completion, and auto-advances. A synthetic demo recording is
loaded on start so every step has real content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np
from qtpy.QtCore import QObject, QRect, QRectF, Qt, QTimer, Signal
from qtpy.QtGui import QColor, QPainter, QPainterPath
from qtpy.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rrational.inspector.data_loader import (
    Dataset,
    EventMeta,
    InspectorData,
    SectionMeta,
)


@dataclass(frozen=True)
class SignalCompletion:
    """Advance when ``target_attr``'s ``signal_name`` fires (discrete action)."""

    target_attr: str
    signal_name: str


@dataclass(frozen=True)
class PredicateCompletion:
    """Advance when ``predicate(main_window)`` first returns True (derived state)."""

    predicate: Callable[[object], bool]
    poll_ms: int = 250


@dataclass(frozen=True)
class TutorialStep:
    """One declarative step: what to highlight, how to prepare, how it completes."""

    key: str
    title: str
    instruction_html: str
    target: Optional[str] = None  # dotted attr path from MainWindow
    setup: Optional[Callable[[object], None]] = None
    completion: "SignalCompletion | PredicateCompletion | None" = None


def resolve_attr(root: object, dotted: Optional[str]) -> Optional[object]:
    """Walk a dotted attribute path from ``root``; None on any miss / None input."""
    if not dotted:
        return None
    cur: object = root
    for part in dotted.split("."):
        cur = getattr(cur, part, None)
        if cur is None:
            return None
    return cur


def build_tutorial_dataset() -> Dataset:
    """Build the self-contained synthetic recording the tutorial operates on.

    ~300 beats around 800 ms, two injected short-interval artifacts so the
    Kubios detector finds work, split into three sections with start events.
    """
    n = 300
    rng = np.random.default_rng(20260701)
    base = 1_700_000_000
    t = base + np.cumsum(np.full(n, 0.8))
    v = 800.0 + 20.0 * rng.standard_normal(n)
    for idx in (n // 4, n // 2):
        v[idx] = 300.0  # clear artifacts

    thirds = n // 3
    sections = [
        SectionMeta(
            name="rest_pre",
            t_start=float(t[0]),
            t_end=float(t[thirds - 1]),
            beat_count=thirds,
        ),
        SectionMeta(
            name="music",
            t_start=float(t[thirds]),
            t_end=float(t[2 * thirds - 1]),
            beat_count=thirds,
        ),
        SectionMeta(
            name="rest_post",
            t_start=float(t[2 * thirds]),
            t_end=float(t[-1]),
            beat_count=n - 2 * thirds,
        ),
    ]
    events = [
        EventMeta(label="rest_pre_start", t=float(t[0])),
        EventMeta(label="music_start", t=float(t[thirds])),
        EventMeta(label="rest_post_start", t=float(t[2 * thirds])),
    ]
    data = InspectorData(t=t, v=v, sections=sections, events=events)
    return Dataset(name="TUTORIAL_demo.csv", data=data, path=None)


# ---------------------------------------------------------------------
# Step setup helpers (idempotent, self-guarding).
# ---------------------------------------------------------------------
def _ensure_demo_loaded(mw) -> None:
    """Load the tutorial demo dataset if the workspace doesn't already have it.

    Resets the demo's corrected-flag on (re)use so a second tutorial run in the
    same session starts the "Use corrected" step from a clean, un-toggled state
    instead of instantly auto-advancing on stale ``use_corrected == True``.
    """
    datasets = getattr(mw, "_datasets", None)
    if datasets is None:
        return
    for i, d in enumerate(datasets):
        if getattr(d, "name", "") == "TUTORIAL_demo.csv":
            d.use_corrected = False
            d.corrected_v = None
            mw.set_active_dataset(i)
            return
    ds = build_tutorial_dataset()
    ds.use_corrected = False
    mw.add_dataset(ds)
    mw.set_active_dataset(len(mw._datasets) - 1)


def _switch_to_tab(mw, tab_attr: str) -> None:
    """Make the tab held at ``mw.<tab_attr>`` current, if it exists + is visible."""
    tabs = getattr(mw, "_tabs_widget", None)
    tab = getattr(mw, tab_attr, None)
    if tabs is None or tab is None:
        return
    idx = tabs.indexOf(tab)
    if idx >= 0 and (not hasattr(tabs, "isTabVisible") or tabs.isTabVisible(idx)):
        tabs.setCurrentIndex(idx)


def _active_ds(mw):
    datasets = getattr(mw, "_datasets", None) or []
    idx = getattr(mw, "_active_idx", None)
    if idx is not None and 0 <= idx < len(datasets):
        return datasets[idx]
    return None


STEPS: tuple[TutorialStep, ...] = (
    TutorialStep(
        key="welcome",
        title="Welcome to the interactive tour",
        instruction_html=(
            "<p>This tour walks you through a full HRV workflow on a built-in "
            "demo recording. On the highlighted steps, just do the action and "
            "the tour advances by itself.</p>"
            "<p>Click <b>Next</b> to load the demo recording.</p>"
        ),
        setup=_ensure_demo_loaded,
    ),
    TutorialStep(
        key="timeline",
        title="The timeline",
        instruction_html=(
            "<p>This is the RR tachogram. The coloured bands are the three "
            "sections of the recording. Click <b>Next</b> to continue.</p>"
        ),
        target="_browse_tab._plot",
    ),
    TutorialStep(
        key="detect",
        title="Detect artifacts",
        instruction_html=(
            "<p>Click <b>Detect artifacts</b> to run the Kubios detector. The "
            "tour continues as soon as it finishes.</p>"
        ),
        target="_browse_tab._preprocessing_panel._detect_btn",
        completion=SignalCompletion(
            "_browse_tab._preprocessing_panel._detect_btn", "clicked"
        ),
    ),
    TutorialStep(
        key="corrected",
        title="Use corrected values",
        instruction_html=(
            "<p>Tick <b>Use corrected RR values</b>. The plot switches to the "
            "interpolated series and — new in this build — the analysis will "
            "use it too.</p>"
        ),
        target="_browse_tab._preprocessing_panel._toggle_use_corrected",
        completion=PredicateCompletion(
            lambda mw: bool(getattr(_active_ds(mw), "use_corrected", False))
        ),
    ),
    TutorialStep(
        key="exclusion",
        title="Exclusion zones (optional)",
        instruction_html=(
            "<p>Enable <b>Exclusion mode</b> and drag over any noisy stretch to "
            "drop it from analysis. Or click <b>Skip</b> to move on.</p>"
        ),
        target="_browse_tab._preprocessing_panel._toggle_exclusion_mode",
        completion=SignalCompletion(
            "_browse_tab._preprocessing_panel._toggle_exclusion_mode", "toggled"
        ),
    ),
    TutorialStep(
        key="setup_events",
        title="Setup: events",
        instruction_html=(
            "<p>The <b>Setup</b> tab defines your study structure. Start with "
            "<b>Events</b> — canonical names for the markers in your recordings. "
            "Click <b>Next</b>.</p>"
        ),
        target="_setup_tab",
        setup=lambda mw: _switch_to_tab(mw, "_setup_tab"),
    ),
    TutorialStep(
        key="setup_sections",
        title="Setup: sections",
        instruction_html=(
            "<p><b>Sections</b> are time ranges between two events "
            "(e.g. <i>rest_pre</i>). Deleting a section now cleanly removes it "
            "from every sequence. Click <b>Next</b>.</p>"
        ),
        target="_setup_tab",
        setup=lambda mw: _switch_to_tab(mw, "_setup_tab"),
    ),
    TutorialStep(
        key="setup_groups",
        title="Setup: groups",
        instruction_html=(
            "<p><b>Groups</b> collect participants sharing a condition. A group "
            "must have at least one member to be used in a comparison. "
            "Click <b>Next</b>.</p>"
        ),
        target="_setup_tab",
        setup=lambda mw: _switch_to_tab(mw, "_setup_tab"),
    ),
    TutorialStep(
        key="setup_sequences",
        title="Setup: sequences",
        instruction_html=(
            "<p><b>Sequences</b> are ordered lists of sections for "
            "repeated-measures analysis. Click <b>Next</b>.</p>"
        ),
        target="_setup_tab",
        setup=lambda mw: _switch_to_tab(mw, "_setup_tab"),
    ),
    TutorialStep(
        key="analysis",
        title="Analysis",
        instruction_html=(
            "<p>The <b>Analysis</b> tab computes HRV metrics. Pick a metric "
            "preset in the settings bar, then click <b>Next</b>.</p>"
        ),
        target="_analysis_tab",
        setup=lambda mw: _switch_to_tab(mw, "_analysis_tab"),
    ),
    TutorialStep(
        key="compute",
        title="Compute HRV",
        instruction_html=(
            "<p>Click <b>Compute</b> in the Single-Participant pane. The tour "
            "advances once a result row appears.</p>"
        ),
        target="_analysis_tab._single_pane._compute_btn",
        # Advance on the actual Compute click (like the Detect step). The
        # earlier ``len(results_store.metric_rows) > 0`` predicate skipped this
        # step instantly for a returning user whose store already held rows.
        completion=SignalCompletion(
            "_analysis_tab._single_pane._compute_btn", "clicked"
        ),
    ),
    TutorialStep(
        key="results",
        title="Results",
        instruction_html=(
            "<p>Every computed metric lands here, sortable and exportable to CSV "
            "or a publication-ready HTML/Markdown report. That's the full loop — "
            "click <b>Next</b> to finish.</p>"
        ),
        target="_results_tab",
        setup=lambda mw: _switch_to_tab(mw, "_results_tab"),
    ),
)


class CoachOverlay(QWidget):
    """Translucent full-parent overlay: dims everything, cuts a spotlight around
    the target, and shows an interactive instruction bubble.

    Mouse model: the overlay CAPTURES mouse events over the dimmed area and the
    bubble, so the bubble's Exit / Skip / Next buttons actually receive clicks.
    A previous version set ``WA_TransparentForMouseEvents`` on the whole
    overlay, which made every click — including the bubble's buttons — fall
    through to the UI behind it, so the tutorial could never be advanced.

    To still let the user perform the real action on an action step (e.g. click
    the highlighted *Detect* button), the spotlight rectangle is punched out of
    the overlay's input mask via :meth:`setMask`, so clicks inside the spotlight
    reach the real widget while everything else is captured.
    """

    next_clicked = Signal()
    skip_clicked = Signal()
    exit_clicked = Signal()

    def __init__(self, parent: QWidget, mode: str = "dark") -> None:
        super().__init__(parent)
        self._spotlight: QRect | None = None
        # NOTE: deliberately NOT WA_TransparentForMouseEvents — the overlay must
        # capture clicks so the bubble buttons work. Click-through to the real
        # highlighted widget is handled selectively by masking out the spotlight
        # hole (see _apply_input_mask), not by making the whole overlay
        # transparent.
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.resize(parent.size())

        # ---- Interactive bubble ----------------------------------------
        # The app themes via QSS, NOT the QPalette, so ``palette(window)`` here
        # would resolve to Qt's DEFAULT (white) palette — a white bubble with
        # the QSS's light text on top = unreadable in dark mode. Pull the real
        # theme colours explicitly instead.
        from rrational.inspector.style.theme import palette_tokens

        tok = palette_tokens(mode)
        bubble_bg = tok["bg_surface"]
        text_col = tok["text_primary"]
        muted_col = tok.get("text_secondary", text_col)
        border_col = tok["accent"]

        self.bubble = QFrame(self)
        self.bubble.setObjectName("tutorialBubble")
        self.bubble.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.bubble.setStyleSheet(
            f"QFrame#tutorialBubble {{ background-color: {bubble_bg}; "
            f"border: 1px solid {border_col}; border-radius: 8px; }}"
            f"QFrame#tutorialBubble QLabel {{ color: {text_col}; "
            "background: transparent; }"
        )
        self.bubble.setFixedWidth(360)
        b = QVBoxLayout(self.bubble)
        b.setContentsMargins(14, 12, 14, 12)
        b.setSpacing(8)

        self._counter = QLabel("", self.bubble)
        self._counter.setStyleSheet(f"color: {muted_col}; background: transparent;")
        b.addWidget(self._counter)

        self._body = QLabel("", self.bubble)
        self._body.setWordWrap(True)
        self._body.setTextFormat(Qt.RichText)
        self._body.setStyleSheet(f"color: {text_col}; background: transparent;")
        b.addWidget(self._body)

        row = QHBoxLayout()
        self._exit_btn = QPushButton("Exit", self.bubble)
        self._exit_btn.setToolTip("Close the tutorial.")
        self._exit_btn.clicked.connect(self.exit_clicked)
        row.addWidget(self._exit_btn)
        row.addStretch()
        self._skip_btn = QPushButton("Skip", self.bubble)
        self._skip_btn.setToolTip("Skip this step.")
        self._skip_btn.clicked.connect(self.skip_clicked)
        row.addWidget(self._skip_btn)
        self._next_btn = QPushButton("Next", self.bubble)
        self._next_btn.setToolTip("Advance to the next step.")
        self._next_btn.setProperty("primary", True)
        self._next_btn.clicked.connect(self.next_clicked)
        row.addWidget(self._next_btn)
        b.addLayout(row)

        self.bubble.adjustSize()

    # ------------------------------------------------------------------
    def set_target(self, rect: QRect | None) -> None:
        self._spotlight = rect
        self._reposition_bubble()
        self._apply_input_mask()
        self.update()

    def _apply_input_mask(self) -> None:
        """Punch the spotlight rect out of the overlay's input area so clicks
        there reach the real highlighted widget, while the dim + bubble still
        capture everything else. No spotlight -> capture the whole surface
        (welcome/summary steps only need the bubble's Next button)."""
        from qtpy.QtGui import QRegion

        if self._spotlight is not None and not self._spotlight.isNull():
            self.setMask(QRegion(self.rect()) - QRegion(self._spotlight))
        else:
            self.clearMask()

    def set_bubble(
        self, html: str, step_idx: int, n_steps: int, can_advance: bool
    ) -> None:
        self._counter.setText(f"Step {step_idx + 1} of {n_steps}")
        self._body.setText(html)
        self._next_btn.setEnabled(can_advance)
        self.bubble.adjustSize()
        self._reposition_bubble()

    # ------------------------------------------------------------------
    def _reposition_bubble(self) -> None:
        """Place the bubble under the spotlight if there's room, else centre it."""
        self.bubble.adjustSize()
        bw, bh = self.bubble.width(), self.bubble.height()
        pw, ph = self.width(), self.height()
        if self._spotlight is not None:
            x = min(max(0, self._spotlight.center().x() - bw // 2), pw - bw)
            below = self._spotlight.bottom() + 12
            y = below if below + bh <= ph else max(0, self._spotlight.top() - bh - 12)
        else:
            x = (pw - bw) // 2
            y = (ph - bh) // 2
        self.bubble.move(max(0, x), max(0, y))

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._reposition_bubble()
        self._apply_input_mask()
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        dim = QColor(0, 0, 0, 140)
        full = QPainterPath()
        full.addRect(0, 0, self.width(), self.height())
        if self._spotlight is not None:
            hole = QPainterPath()
            # QPainterPath.addRoundedRect requires QRectF (not QRect) in
            # PySide6, so wrap the padded spotlight rect explicitly.
            r = QRectF(self._spotlight.adjusted(-6, -6, 6, 6))
            hole.addRoundedRect(r, 6.0, 6.0)
            full = full.subtracted(hole)
        painter.fillPath(full, dim)
        if self._spotlight is not None:
            painter.setPen(QColor("#e8a13a"))  # amber accent border
            painter.drawRoundedRect(
                QRectF(self._spotlight.adjusted(-6, -6, 6, 6)), 6.0, 6.0
            )
        painter.end()


class TutorialController(QObject):
    """Drives the ordered ``STEPS`` over a live MainWindow with a CoachOverlay."""

    def __init__(self, main_window, steps: "tuple[TutorialStep, ...]" = STEPS) -> None:
        super().__init__(main_window)
        self._mw = main_window
        self._steps = list(steps)
        self._idx = -1
        self._active = False
        self._overlay: CoachOverlay | None = None
        self._prev_layout: str | None = None
        self._poll: QTimer | None = None
        self._signal_conn = None  # (bound_signal, slot) for teardown

    # -- public --------------------------------------------------------
    def is_active(self) -> bool:
        return self._active

    def current_index(self) -> int:
        return self._idx

    def start(self) -> None:
        # Targets assume the mnelab layout (Browse + preprocessing visible).
        self._prev_layout = getattr(self._mw, "_ui_layout", None)
        try:
            self._mw.set_ui_layout("mnelab")
        except Exception:  # pragma: no cover - defensive
            pass
        central = self._mw.centralWidget() or self._mw
        # Resolve the active theme mode so the bubble uses matching colours
        # (the app themes via QSS, so palette() roles can't be trusted here).
        try:
            from rrational.inspector.app import _resolve_theme_mode

            mode = _resolve_theme_mode()
        except Exception:  # pragma: no cover - defensive
            mode = "dark"
        self._overlay = CoachOverlay(central, mode=mode)
        self._overlay.resize(central.size())
        self._overlay.next_clicked.connect(self._advance)
        self._overlay.skip_clicked.connect(self._advance)
        self._overlay.exit_clicked.connect(self.exit)
        self._overlay.show()
        self._overlay.raise_()
        self._active = True
        self._enter_step(0)

    def exit(self) -> None:
        self._teardown_completion()
        if self._overlay is not None:
            self._overlay.hide()
            self._overlay.deleteLater()
            self._overlay = None
        if self._prev_layout:
            try:
                self._mw.set_ui_layout(self._prev_layout)
            except Exception:  # pragma: no cover - defensive
                pass
        self._active = False

    def finish(self) -> None:
        self.exit()

    # -- internals -----------------------------------------------------
    def _enter_step(self, i: int) -> None:
        self._teardown_completion()
        self._idx = i
        step = self._steps[i]
        if step.setup is not None:
            try:
                step.setup(self._mw)
            except Exception:  # pragma: no cover - defensive
                import logging

                logging.getLogger("rrational.inspector.tutorial").warning(
                    "tutorial step %s setup failed", step.key, exc_info=True
                )
        self._refresh_spotlight(step)
        # On action steps Next is disabled (do the real action / Skip).
        can_advance = step.completion is None
        if self._overlay is not None:
            self._overlay.set_bubble(
                step.instruction_html, i, len(self._steps), can_advance
            )
        self._wire_completion(step)

    def _refresh_spotlight(self, step: "TutorialStep") -> None:
        if self._overlay is None:
            return
        widget = resolve_attr(self._mw, step.target)
        rect = None
        if widget is not None and widget.isVisible():
            top_left = widget.mapTo(
                self._overlay.parentWidget(), widget.rect().topLeft()
            )
            rect = QRect(top_left, widget.size())
        self._overlay.set_target(rect)

    def _wire_completion(self, step: "TutorialStep") -> None:
        comp = step.completion
        if comp is None:
            return
        if isinstance(comp, SignalCompletion):
            owner = resolve_attr(self._mw, comp.target_attr)
            sig = getattr(owner, comp.signal_name, None) if owner is not None else None
            if sig is not None:
                slot = lambda *a: self._advance()  # noqa: E731
                sig.connect(slot)
                self._signal_conn = (sig, slot)
            return
        # PredicateCompletion — poll.
        self._poll = QTimer(self)
        self._poll.setInterval(comp.poll_ms)
        self._poll.timeout.connect(
            lambda: self._advance() if comp.predicate(self._mw) else None
        )
        self._poll.start()

    def _teardown_completion(self) -> None:
        if self._signal_conn is not None:
            sig, slot = self._signal_conn
            try:
                sig.disconnect(slot)
            except (TypeError, RuntimeError):  # pragma: no cover - defensive
                pass
            self._signal_conn = None
        if self._poll is not None:
            self._poll.stop()
            self._poll.deleteLater()
            self._poll = None

    def _advance(self) -> None:
        if not self._active:
            return
        nxt = self._idx + 1
        if nxt >= len(self._steps):
            self.finish()
            return
        self._enter_step(nxt)


def show_tutorial(main_window) -> TutorialController:
    """Construct + start the interactive tutorial. Returns the controller."""
    ctl = TutorialController(main_window)
    ctl.start()
    return ctl
