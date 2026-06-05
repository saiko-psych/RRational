"""Tests for :class:`rrational.inspector.workflow_sidebar.WorkflowSidebar`.

The sidebar is a presentational widget: it builds 7 large buttons,
applies styled states via ``set_step_states``, emits ``step_clicked``
when any button is pressed, and recomputes its own state from a
``MainWindow``-shaped object via ``refresh_from_main_window``.

We exercise each surface in isolation:

* :func:`test_instantiates` - the widget builds without a real
  MainWindow (using a tiny stub) and exposes 7 buttons.
* :func:`test_set_step_states_accepts_dict` - the public state setter
  takes a partial dict, ignores unknown indices, and rejects bad
  states.
* :func:`test_step_clicked_signal_fires` - pressing a button emits the
  signal with the right 1-based step index.
* :func:`test_refresh_computes_states` - feeding a mocked MainWindow
  with varying workspace contents produces the expected per-step
  states.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")


# ---------------------------------------------------------------------------
# Tiny stub - lets us instantiate the sidebar without spinning up a real
# MainWindow (which would drag the full Qt + project stack into the test).
# ---------------------------------------------------------------------------


class _StubTabsWidget:
    def __init__(self):
        self.current_index = 0

    def setCurrentIndex(self, idx):  # noqa: N802 - Qt API name
        self.current_index = idx


class _StubStatusBar:
    def __init__(self):
        self.messages: list[tuple[str, int]] = []

    def showMessage(self, text, timeout=0):  # noqa: N802 - Qt API name
        self.messages.append((text, timeout))


class _StubPreprocessing:
    def __init__(self, last_result=None):
        self._last_result = last_result


class _StubBrowseTab:
    def __init__(self, last_result=None):
        self._preprocessing_panel = _StubPreprocessing(last_result)


class _StubGroupsPane:
    def __init__(self, groups=None):
        self.groups = groups or []


class _StubSequencesPane:
    def __init__(self, sequences=None):
        self.sequences = sequences or []


class _StubSetupTab:
    def __init__(self, groups=None, sequences=None):
        self._groups_pane = _StubGroupsPane(groups)
        self._sequences_pane = _StubSequencesPane(sequences)


class _StubParticipantsTab:
    def __init__(self, participants=None):
        self._participants = participants or {}


class _StubResultsStore:
    def __init__(self, metric_rows=None, group_test_rows=None, sequence_test_rows=None):
        self.metric_rows = metric_rows or []
        self.group_test_rows = group_test_rows or []
        self.sequence_test_rows = sequence_test_rows or []


class _StubMainWindow:
    """Quacks like :class:`MainWindow` enough for the sidebar."""

    def __init__(
        self,
        *,
        datasets=None,
        last_result=None,
        groups=None,
        sequences=None,
        participants=None,
        metric_rows=None,
    ):
        self._datasets = datasets or []
        self._browse_tab = _StubBrowseTab(last_result)
        self._setup_tab = _StubSetupTab(groups, sequences)
        self._participants_tab = _StubParticipantsTab(participants)
        self._results_store = _StubResultsStore(metric_rows=metric_rows)
        self._tabs_widget = _StubTabsWidget()
        self._status_bar = _StubStatusBar()

    def statusBar(self):  # noqa: N802 - Qt API name
        return self._status_bar


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sidebar(qtbot):
    """A WorkflowSidebar bound to an empty stub MainWindow."""
    from rrational.inspector.workflow_sidebar import WorkflowSidebar

    mw = _StubMainWindow()
    bar = WorkflowSidebar(mw)
    qtbot.addWidget(bar)
    return bar


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_instantiates(sidebar):
    """The sidebar builds 7 buttons (one per step) and has the right title."""
    from rrational.inspector.workflow_sidebar import STEP_LABELS

    assert sidebar.windowTitle() == "Workflow"
    assert len(STEP_LABELS) == 7
    for step in range(1, 8):
        btn = sidebar.button_for(step)
        assert btn is not None, f"missing button for step {step}"
        # Each label text contains the human-readable step name (after
        # the state-prefix glyph) so the user can read them.
        assert STEP_LABELS[step] in btn.text()


def test_default_state_is_step_one_active(sidebar):
    """Fresh sidebar shows step 1 active, all others locked."""
    assert sidebar.state_for(1) == "active"
    for step in range(2, 8):
        assert sidebar.state_for(step) == "locked"


def test_set_step_states_accepts_dict(sidebar):
    """Partial dicts apply and unknown indices are silently ignored."""
    sidebar.set_step_states({1: "done", 3: "active", 7: "done"})

    assert sidebar.state_for(1) == "done"
    assert sidebar.state_for(3) == "active"
    assert sidebar.state_for(7) == "done"

    # Unspecified steps keep their previous (initial) state.
    assert sidebar.state_for(2) == "locked"
    assert sidebar.state_for(4) == "locked"

    # Unknown indices are ignored without raising.
    sidebar.set_step_states({99: "done"})


def test_set_step_states_rejects_invalid_state(sidebar):
    """Unknown state strings raise ValueError so typos surface in tests."""
    with pytest.raises(ValueError, match="Invalid step state"):
        sidebar.set_step_states({1: "completed"})


def test_step_clicked_signal_fires(sidebar, qtbot):
    """Pressing button 3 emits ``step_clicked(3)``."""
    btn = sidebar.button_for(3)
    assert btn is not None

    with qtbot.waitSignal(sidebar.step_clicked, timeout=1000) as blocker:
        btn.click()
    assert blocker.args == [3]


def test_click_switches_tab_and_posts_hint(qtbot):
    """Clicking step 4 switches the tab widget and shows a status hint."""
    from rrational.inspector.workflow_sidebar import WorkflowSidebar

    mw = _StubMainWindow(datasets=["d1"])
    bar = WorkflowSidebar(mw)
    qtbot.addWidget(bar)

    bar.button_for(4).click()
    # Step 4 (Define structure) maps to the Setup tab at index 1.
    assert mw._tabs_widget.current_index == 1
    assert mw._status_bar.messages, "expected a status-bar hint to be posted"
    text, _timeout = mw._status_bar.messages[-1]
    assert "Step 4" in text


def test_refresh_no_dataset_locks_everything_but_step_one(qtbot):
    from rrational.inspector.workflow_sidebar import WorkflowSidebar

    mw = _StubMainWindow()
    bar = WorkflowSidebar(mw)
    qtbot.addWidget(bar)

    bar.refresh_from_main_window()
    assert bar.state_for(1) == "active"
    for step in range(2, 8):
        assert bar.state_for(step) == "locked"


def test_refresh_with_dataset_unlocks_step_two(qtbot):
    from rrational.inspector.workflow_sidebar import WorkflowSidebar

    mw = _StubMainWindow(datasets=["d1"])
    bar = WorkflowSidebar(mw)
    qtbot.addWidget(bar)

    bar.refresh_from_main_window()
    assert bar.state_for(1) == "done"
    # Step 2 is the next un-done step, so it becomes "active".
    assert bar.state_for(2) == "active"
    assert bar.state_for(3) == "locked"


def test_refresh_with_detection_marks_steps_two_and_three_done(qtbot):
    from rrational.inspector.workflow_sidebar import WorkflowSidebar

    mw = _StubMainWindow(datasets=["d1"], last_result=object())
    bar = WorkflowSidebar(mw)
    qtbot.addWidget(bar)

    bar.refresh_from_main_window()
    assert bar.state_for(1) == "done"
    assert bar.state_for(2) == "done"
    assert bar.state_for(3) == "done"
    # Step 4 (structure) is next.
    assert bar.state_for(4) == "active"


def test_refresh_full_workflow_marks_everything_done(qtbot):
    from rrational.inspector.workflow_sidebar import WorkflowSidebar

    mw = _StubMainWindow(
        datasets=["d1"],
        last_result=object(),
        groups=[{"name": "g"}],
        sequences=[{"name": "s"}],
        participants={"p01": {}},
        metric_rows=[object()],
    )
    bar = WorkflowSidebar(mw)
    qtbot.addWidget(bar)

    bar.refresh_from_main_window()
    for step in range(1, 8):
        assert bar.state_for(step) == "done", f"step {step} not done"


def test_refresh_results_without_participants_keeps_step_six_locked(qtbot):
    """Results without participants is a degenerate state - sidebar should
    still mark step 7 (export) done but keep step 6 (run analysis) locked
    if participants are missing."""
    from rrational.inspector.workflow_sidebar import WorkflowSidebar

    mw = _StubMainWindow(
        datasets=["d1"],
        metric_rows=[object()],
    )
    bar = WorkflowSidebar(mw)
    qtbot.addWidget(bar)

    bar.refresh_from_main_window()
    assert bar.state_for(6) == "locked"
    # Step 7 is "done" because results exist.
    assert bar.state_for(7) == "done"
