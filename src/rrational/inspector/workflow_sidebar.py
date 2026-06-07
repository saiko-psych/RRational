"""Phase 22.4: Persistent left-column workflow sidebar (QDockWidget).

Mirrors the Streamlit step-by-step guided workflow inside the Qt
Inspector as a vertical dock anchored on the left side of the
``MainWindow``. Each step is a large clickable button rendered in one
of three visual states - ``done`` / ``active`` / ``locked`` - using
the exact same colour palette and unicode prefixes as the existing
``WorkflowStepper`` so the two widgets read as a unit.

The seven steps mirror the canonical RR-analysis pipeline:

    1. Open data
    2. Inspect timeline
    3. Detect artifacts
    4. Define structure
    5. Assign participants
    6. Run analysis
    7. Export results

Clicking a button does two things:

* Emits :pyattr:`step_clicked` with the 1-based step index. External
  wiring (added in a follow-up phase) decides whether to switch tabs.
* Switches the central ``QTabWidget`` to the matching tab and shows a
  short hint on the main window's status bar.

Per ``CLAUDE.md`` we use unicode glyphs only - no emoji.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QDockWidget,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from rrational.inspector.main_window import MainWindow


# 1-based step index -> human-readable label shown on the button.
STEP_LABELS: dict[int, str] = {
    1: "1. Open data",
    2: "2. Inspect timeline",
    3: "3. Detect artifacts",
    4: "4. Define structure",
    5: "5. Assign participants",
    6: "6. Run analysis",
    7: "7. Export results",
}

# 1-based step index -> 0-based index in MainWindow._tabs.
# Browse=0, Setup=1, Participants=2, Analysis=3, Results=4.
_STEP_TO_TAB_INDEX: dict[int, int] = {
    1: 0,  # Open data lives in Browse
    2: 0,  # Inspect timeline = Browse
    3: 0,  # Detect artifacts = Browse (preprocessing dock)
    4: 1,  # Define structure = Setup
    5: 2,  # Assign participants = Participants
    6: 3,  # Run analysis = Analysis
    7: 4,  # Export results = Results
}

# Status-bar hint shown when each step button is clicked. Kept short
# so the message fits in the status bar without truncation.
_STEP_HINTS: dict[int, str] = {
    1: "Step 1: open a .rrational file or BIDS folder from the File menu",
    2: "Step 2: scroll the timeline in the Browse tab to inspect the recording",
    3: "Step 3: click 'Detect artifacts' in the Preprocessing panel on the right",
    4: "Step 4: define events, sections, groups, sequences or protocol in Setup",
    5: "Step 5: add or import participants in the Participants tab",
    6: "Step 6: configure metrics and run analyses in the Analysis tab",
    7: "Step 7: export tables and reports from the Results tab",
}

_VALID_STATES = frozenset({"done", "active", "locked"})

# Per-state stylesheet snippets - colours match WorkflowStepper exactly
# so a user looking at both widgets perceives a single state machine.
_STYLE: dict[str, str] = {
    "done": (
        "QPushButton { background-color: #2ca02c; color: white; "
        "border: 1px solid #1f7a1f; border-radius: 4px; "
        "padding: 10px 12px; font-weight: bold; text-align: left; }"
    ),
    "active": (
        "QPushButton { background-color: #5b8def; color: white; "
        "border: 1px solid #3060c0; border-radius: 4px; "
        "padding: 10px 12px; font-weight: bold; text-align: left; }"
    ),
    "locked": (
        "QPushButton { background-color: #e0e0e0; color: #888; "
        "border: 1px solid #c0c0c0; border-radius: 4px; "
        "padding: 10px 12px; text-align: left; }"
    ),
}

# Unicode glyph prefixes - matches WorkflowStepper. No emoji.
_PREFIX: dict[str, str] = {
    "done": "✓ ",  # check mark
    "active": "▶ ",  # black right-pointing triangle
    "locked": "· ",  # middle dot
}

_LOCKED_TOOLTIP = "Complete the previous steps first"


class WorkflowSidebar(QDockWidget):
    """Persistent left-column workflow guide for the Inspector.

    Holds one large button per step. Buttons emit
    :pyattr:`step_clicked` (1-based index) regardless of state - the
    sidebar always tries to switch to the matching tab and post a
    status-bar hint so the user gets feedback even when they click a
    locked step.
    """

    step_clicked = Signal(int)

    def __init__(
        self, main_window: "MainWindow", parent: QWidget | None = None
    ) -> None:
        super().__init__("Workflow", parent)
        # Cache the main window so refresh_from_main_window can probe
        # its tabs / datasets without having to walk parent() chains.
        self._main_window = main_window

        # Dock should sit on the left, the user can detach/reattach but
        # not close it accidentally (toggle wiring is a separate phase).
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setFeatures(
            QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
        )

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._buttons: dict[int, QPushButton] = {}
        self._states: dict[int, str] = {}

        for step in sorted(STEP_LABELS.keys()):
            btn = QPushButton(STEP_LABELS[step], container)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.setMinimumHeight(44)
            # Capture step index via default arg so the lambda binds early.
            btn.clicked.connect(lambda _checked, s=step: self._on_step_clicked(s))
            self._buttons[step] = btn
            layout.addWidget(btn)

        layout.addStretch(1)
        self.setWidget(container)

        # Initial state: only step 1 is active until a dataset loads.
        self.set_step_states(
            {
                1: "active",
                2: "locked",
                3: "locked",
                4: "locked",
                5: "locked",
                6: "locked",
                7: "locked",
            }
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_step_states(self, states: dict[int, str]) -> None:
        """Apply per-step visual state.

        ``states`` maps 1-based step index to one of ``done``,
        ``active``, ``locked``. Unknown states raise ``ValueError`` to
        surface typos. Indices not present in the dict are untouched.
        """
        for step, state in states.items():
            if state not in _VALID_STATES:
                raise ValueError(
                    f"Invalid step state {state!r}; "
                    f"expected one of {sorted(_VALID_STATES)}"
                )
            btn = self._buttons.get(step)
            if btn is None:
                continue
            btn.setStyleSheet(_STYLE[state])
            btn.setText(_PREFIX[state] + STEP_LABELS[step])
            btn.setToolTip(_LOCKED_TOOLTIP if state == "locked" else STEP_LABELS[step])
            self._states[step] = state

    def state_for(self, step: int) -> str | None:
        """Return the current state for ``step`` (1-based) or None."""
        return self._states.get(step)

    def button_for(self, step: int) -> QPushButton | None:
        """Return the QPushButton for ``step`` (1-based) - for tests."""
        return self._buttons.get(step)

    def refresh_from_main_window(self) -> None:
        """Recompute every step's state from the live MainWindow state.

        Probing is deliberately lenient (``getattr`` + ``or []``) so the
        sidebar still works during early init / teardown when not every
        attribute is wired up yet.
        """
        mw = self._main_window

        has_dataset = bool(getattr(mw, "_datasets", []) or [])

        has_detection = False
        browse = getattr(mw, "_browse_tab", None)
        if browse is not None:
            panel = getattr(browse, "_preprocessing_panel", None)
            if panel is not None and getattr(panel, "_last_result", None) is not None:
                has_detection = True

        has_structure = False
        setup = getattr(mw, "_setup_tab", None)
        if setup is not None:
            groups_pane = getattr(setup, "_groups_pane", None)
            if groups_pane is not None and getattr(groups_pane, "groups", None):
                has_structure = True
            seq_pane = getattr(setup, "_sequences_pane", None)
            if seq_pane is not None and getattr(seq_pane, "sequences", None):
                has_structure = True

        has_participants = False
        parts = getattr(mw, "_participants_tab", None)
        if parts is not None:
            pmap = getattr(parts, "_participants", None)
            if pmap:
                has_participants = True

        has_results = False
        store = getattr(mw, "_results_store", None)
        if store is not None:
            for attr in ("metric_rows", "group_test_rows", "sequence_test_rows"):
                if getattr(store, attr, None):
                    has_results = True
                    break

        states = self._compute_states(
            has_dataset=has_dataset,
            has_detection=has_detection,
            has_structure=has_structure,
            has_participants=has_participants,
            has_results=has_results,
        )
        self.set_step_states(states)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_states(
        *,
        has_dataset: bool,
        has_detection: bool,
        has_structure: bool,
        has_participants: bool,
        has_results: bool,
    ) -> dict[int, str]:
        """Translate workspace booleans into a 7-step state dict.

        Rules:
          - Step 1 (Open data) is "done" once any dataset is loaded,
            else "active".
          - Step 2 (Inspect timeline) unlocks once a dataset is loaded;
            it becomes "done" once detection has run.
          - Step 3 (Detect artifacts) unlocks once a dataset is loaded;
            "done" once detection has run.
          - Step 4 (Define structure) unlocks once a dataset is loaded
            (the user may legitimately work on structure before
            detection); "done" once any group or sequence exists.
          - Step 5 (Assign participants) unlocks once a dataset is
            loaded; "done" once any participant has been added.
          - Step 6 (Run analysis) unlocks once a dataset AND
            participants exist; "done" once any result row exists.
          - Step 7 (Export results) unlocks once results exist.

        The current "active" step is the lowest-numbered unlocked step
        that isn't already done - i.e. the next thing the user should
        click. If everything is done, step 7 remains "done".
        """
        states: dict[int, str] = {}

        states[1] = "done" if has_dataset else "active"
        if has_dataset:
            states[2] = "done" if has_detection else "locked"
            states[3] = "done" if has_detection else "locked"
            states[4] = "done" if has_structure else "locked"
            states[5] = "done" if has_participants else "locked"
        else:
            states[2] = "locked"
            states[3] = "locked"
            states[4] = "locked"
            states[5] = "locked"

        if has_dataset and has_participants:
            states[6] = "done" if has_results else "locked"
        else:
            states[6] = "locked"

        states[7] = "done" if has_results else "locked"

        # Promote the first non-done step to "active". Step 1 already
        # handles its own active flag above when no dataset is loaded.
        if has_dataset:
            for step in sorted(states.keys()):
                if states[step] != "done":
                    states[step] = "active"
                    break

        return states

    def _on_step_clicked(self, step: int) -> None:
        """Emit the signal, switch tabs, and post a status-bar hint."""
        self.step_clicked.emit(step)

        mw = self._main_window
        tab_idx = _STEP_TO_TAB_INDEX.get(step)
        tabs_widget = getattr(mw, "_tabs_widget", None)
        if tab_idx is not None and tabs_widget is not None:
            try:
                tabs_widget.setCurrentIndex(tab_idx)
            except Exception:
                # Be defensive: a partially-initialised MainWindow in
                # tests may not have a fully usable tab widget yet.
                pass

        hint = _STEP_HINTS.get(step)
        if hint:
            try:
                mw.statusBar().showMessage(hint, 5000)
            except Exception:
                pass
