"""Horizontal workflow stepper for the Kubios-style HRV workflow.

Renders four clickable steps across the top of the PreprocessingPanel:

    [1. Load raw] -> [2. Detect artifacts] -> [3. Review & correct] -> [4. Save .rrational]

Each step is a ``QPushButton`` in one of three visual states:

* ``done``    - completed (filled, green checkmark prefix)
* ``active``  - the current actionable step (filled, accent color)
* ``locked``  - not yet reachable (grey, disabled-looking but still clickable
  so we can show the "complete the previous step first" tooltip)

The widget is purely presentational - state transitions are driven by
the parent ``PreprocessingPanel`` via :meth:`set_step_states`. Clicking
an enabled step emits :pyattr:`step_clicked` with the 1-based step
index; the panel decides what to do (e.g. step 2 -> run detect).
"""

from __future__ import annotations

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)


# Visible button labels — kept short so all four fit the narrow
# preprocessing dock without ellipsising. Numeric prefix is dropped
# because left-to-right placement already conveys the sequence; the
# state-prefix glyph (check / triangle / dot) communicates progress.
# The longer descriptive version lives in STEP_TOOLTIPS and shows
# on hover.
STEP_LABELS: dict[int, str] = {
    1: "Load",
    2: "Detect",
    3: "Review",
    4: "Save",
}

# Long-form hover text — explains what each step actually does.
STEP_TOOLTIPS: dict[int, str] = {
    1: "Load raw recording — opens a participant file from disk",
    2: "Detect artifacts — runs the NeuroKit2 Lipponen 2019 algorithm",
    3: "Review & correct — inspect markers, manually toggle outliers",
    4: "Save .rrational — export the corrected segment as a v2 file",
}

# Allowed states - kept as a frozen set so typos surface in tests.
_VALID_STATES = frozenset({"done", "active", "locked"})

# Per-state stylesheet snippets. The palette mirrors the "Refined
# Laboratory" QSS theme tokens in rrational.inspector.style.theme so
# the stepper feels visually continuous with the rest of the chrome
# instead of breaking into web-stock primary blues/greens. The hex
# codes here are intentionally inlined rather than imported — the
# stepper is constructed before the theme module touches the
# application, so a circular import would be easy to introduce.
#   done    = jade success
#   active  = amber accent
#   locked  = muted graphite
_STYLE: dict[str, str] = {
    "done": (
        "QPushButton { background-color: #5ab896; color: #1a1d22; "
        "border: 1px solid #4a9d80; border-radius: 4px; padding: 6px 10px; "
        "font-weight: 600; letter-spacing: 0.3px; }"
    ),
    "active": (
        "QPushButton { background-color: #e8a13a; color: #1a1d22; "
        "border: 1px solid #c98a2a; border-radius: 4px; padding: 6px 10px; "
        "font-weight: 600; letter-spacing: 0.3px; }"
    ),
    # Round 33 (W1) — the locked state uses palette() roles (resolved by Qt
    # at render time from the app palette, no import needed) so it stays
    # legible in BOTH themes. The old hardcoded dark-surface hex rendered as
    # dark-on-dark and became invisible under the light preset. The done /
    # active states keep their brand accent hex (jade / amber) — those are
    # identical in both themes and their dark #1a1d22 text reads on both.
    "locked": (
        "QPushButton { background-color: palette(button); color: palette(mid); "
        "border: 1px solid palette(midlight); border-radius: 4px; padding: 6px 10px; "
        "letter-spacing: 0.3px; }"
    ),
}

# Plain unicode prefixes - per CLAUDE.md no-emoji rule we stick to
# checkmark / bullet glyphs from the base Unicode plane.
_PREFIX: dict[str, str] = {
    "done": "✓ ",  # check mark
    "active": "▶ ",  # black right-pointing triangle
    "locked": "· ",  # middle dot
}

_LOCKED_TOOLTIP = "Complete the previous step first"


class WorkflowStepper(QWidget):
    """Horizontal four-step workflow header for the PreprocessingPanel.

    Emits :pyattr:`step_clicked` with the 1-based step index whenever
    any step button is pressed (including locked ones - the panel
    decides whether to act or show a "locked" message).
    """

    step_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(2)

        # Map step index -> button so set_step_states can find them.
        self._buttons: dict[int, QPushButton] = {}
        # Map step index -> current state, used by query helpers in tests.
        self._states: dict[int, str] = {}

        sorted_steps = sorted(STEP_LABELS.keys())
        for i, step in enumerate(sorted_steps):
            btn = QPushButton(STEP_LABELS[step], self)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            # Width pinned so the short label + state prefix never
            # ellipsises in the narrow preprocessing dock.
            btn.setMinimumWidth(78)
            btn.setToolTip(STEP_TOOLTIPS[step])
            # Use lambda default-arg trick to capture the step index.
            btn.clicked.connect(lambda _checked, s=step: self.step_clicked.emit(s))
            self._buttons[step] = btn
            layout.addWidget(btn, 1)

            # Insert an arrow between steps (not after the last).
            if i < len(sorted_steps) - 1:
                sep = QLabel("→", self)  # right arrow
                sep.setAlignment(Qt.AlignCenter)
                # Theme-aware muted glyph via the global "muted" QSS property.
                sep.setProperty("muted", True)
                layout.addWidget(sep, 0)

        # Default state: step 1 active, rest locked.
        self.set_step_states({1: "active", 2: "locked", 3: "locked", 4: "locked"})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_step_states(self, states: dict[int, str]) -> None:
        """Set each step's visual state.

        ``states`` maps 1-based step index -> one of ``done``, ``active``,
        ``locked``. Steps not present in the dict are left unchanged.
        Invalid states raise ``ValueError`` so callers can't silently
        break the stepper.
        """
        for step, state in states.items():
            if state not in _VALID_STATES:
                raise ValueError(
                    f"Invalid step state {state!r}; "
                    f"expected one of {sorted(_VALID_STATES)}"
                )
            if step not in self._buttons:
                continue
            btn = self._buttons[step]
            btn.setStyleSheet(_STYLE[state])
            btn.setText(_PREFIX[state] + STEP_LABELS[step])
            # Locked steps stay clickable so the panel can show the
            # "complete the previous step first" hint via tooltip /
            # status bar. We just toggle the tooltip text instead.
            if state == "locked":
                btn.setToolTip(_LOCKED_TOOLTIP)
            else:
                btn.setToolTip(STEP_TOOLTIPS[step])
            self._states[step] = state

    def state_for(self, step: int) -> str | None:
        """Return the current state of ``step`` (1-based) or None."""
        return self._states.get(step)

    def button_for(self, step: int) -> QPushButton | None:
        """Return the QPushButton for ``step`` (1-based) - for tests."""
        return self._buttons.get(step)
