"""UX3: Horizontal workflow stepper for the Kubios-style HRV workflow.

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


# Step ordering is fixed; these labels show up in the buttons.
STEP_LABELS: dict[int, str] = {
    1: "1. Load raw",
    2: "2. Detect artifacts",
    3: "3. Review & correct",
    4: "4. Save .rrational",
}

# Allowed states - kept as a frozen set so typos surface in tests.
_VALID_STATES = frozenset({"done", "active", "locked"})

# Per-state stylesheet snippets. Kept short so QSS warnings are obvious
# in the test log if Qt complains. Colors chosen to match the existing
# _GRADE_COLOR palette in preprocessing_panel.py for visual cohesion.
_STYLE: dict[str, str] = {
    "done": (
        "QPushButton { background-color: #2ca02c; color: white; "
        "border: 1px solid #1f7a1f; border-radius: 4px; padding: 4px 6px; "
        "font-weight: bold; }"
    ),
    "active": (
        "QPushButton { background-color: #5b8def; color: white; "
        "border: 1px solid #3060c0; border-radius: 4px; padding: 4px 6px; "
        "font-weight: bold; }"
    ),
    "locked": (
        "QPushButton { background-color: #e0e0e0; color: #888; "
        "border: 1px solid #c0c0c0; border-radius: 4px; padding: 4px 6px; }"
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
            # Use lambda default-arg trick to capture the step index.
            btn.clicked.connect(lambda _checked, s=step: self.step_clicked.emit(s))
            self._buttons[step] = btn
            layout.addWidget(btn, 1)

            # Insert an arrow between steps (not after the last).
            if i < len(sorted_steps) - 1:
                sep = QLabel("→", self)  # right arrow
                sep.setAlignment(Qt.AlignCenter)
                sep.setStyleSheet("color: #888; font-weight: bold;")
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
                btn.setToolTip(STEP_LABELS[step])
            self._states[step] = state

    def state_for(self, step: int) -> str | None:
        """Return the current state of ``step`` (1-based) or None."""
        return self._states.get(step)

    def button_for(self, step: int) -> QPushButton | None:
        """Return the QPushButton for ``step`` (1-based) - for tests."""
        return self._buttons.get(step)
