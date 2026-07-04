"""Tests for the interactive coach-mark tutorial."""

from __future__ import annotations

import numpy as np

from rrational.inspector.tutorial import build_tutorial_dataset


def test_build_tutorial_dataset_shape():
    ds = build_tutorial_dataset()
    assert ds.name == "TUTORIAL_demo.csv"
    assert ds.path is None
    data = ds.data
    assert data.t.shape == data.v.shape
    assert data.t.shape[0] >= 200
    # Three named sections the Setup/Analysis steps rely on.
    names = [s.name for s in data.sections]
    assert names == ["rest_pre", "music", "rest_post"]
    # At least one clear artifact so the Detect step finds work.
    assert float(np.nanmin(data.v)) < 400.0


from rrational.inspector.tutorial import (  # noqa: E402
    STEPS,
    PredicateCompletion,
    SignalCompletion,
    TutorialStep,
    resolve_attr,
)


def test_step_is_frozen():
    step = TutorialStep(key="k", title="t", instruction_html="<p>x</p>")
    try:
        step.title = "new"  # type: ignore[misc]
    except Exception:
        pass
    else:  # pragma: no cover
        raise AssertionError("TutorialStep should be frozen")


def test_steps_keys_and_order():
    keys = [s.key for s in STEPS]
    assert keys == [
        "welcome",
        "datasets",
        "timeline",
        "detect",
        "corrected",
        "exclusion",
        "setup_events",
        "setup_sections",
        "setup_groups",
        "setup_sequences",
        "participants",
        "analysis",
        "compute",
        "results",
    ]
    for s in STEPS:
        assert s.title and s.instruction_html


def test_action_steps_have_completion():
    by_key = {s.key: s for s in STEPS}
    assert isinstance(by_key["detect"].completion, SignalCompletion)
    assert isinstance(by_key["corrected"].completion, PredicateCompletion)
    # compute advances on the real Compute click (not a results-count predicate,
    # which would instantly skip the step for a user with prior results).
    assert isinstance(by_key["compute"].completion, SignalCompletion)


def test_resolve_attr_walks_and_guards():
    class B:
        x = 42

    class A:
        b = B()

    root = A()
    assert resolve_attr(root, "b.x") == 42
    assert resolve_attr(root, "b.missing") is None
    assert resolve_attr(root, None) is None
    assert resolve_attr(root, "nope.at.all") is None


import pytest  # noqa: E402

pytest.importorskip("pytestqt")

from qtpy.QtCore import QRect  # noqa: E402
from qtpy.QtWidgets import QWidget  # noqa: E402

from rrational.inspector.tutorial import CoachOverlay  # noqa: E402


def test_overlay_constructs_and_updates(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.resize(800, 600)
    ov = CoachOverlay(parent)
    ov.set_target(QRect(100, 100, 120, 40))
    ov.set_bubble("<p>hello</p>", step_idx=0, n_steps=12, can_advance=True)
    assert ov.bubble is not None
    assert ov._next_btn.isEnabled() is True
    ov.set_bubble("<p>last</p>", step_idx=11, n_steps=12, can_advance=False)
    assert ov._next_btn.isEnabled() is False


def test_overlay_buttons_emit(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    ov = CoachOverlay(parent)
    with qtbot.waitSignal(ov.skip_clicked, timeout=1000):
        ov._skip_btn.click()
    with qtbot.waitSignal(ov.exit_clicked, timeout=1000):
        ov._exit_btn.click()


def test_overlay_bubble_uses_theme_colors_not_default_palette(qtbot):
    """Regression: the bubble used palette(window), which resolves to Qt's
    DEFAULT (white) palette because the app themes via QSS (not QPalette) —
    a white bubble with the QSS's light text = unreadable in dark mode.

    The bubble must instead pull explicit theme colours: a DARK surface with
    LIGHT text in dark mode, and a LIGHT surface with DARK text in light mode.
    """
    parent = QWidget()
    qtbot.addWidget(parent)

    dark = CoachOverlay(parent, mode="dark")
    assert "#232830" in dark.bubble.styleSheet()  # bg_surface (dark)
    assert "#eaecef" in dark._body.styleSheet()  # text_primary (light)
    assert "palette(" not in dark.bubble.styleSheet()  # no unthemed palette roles

    light = CoachOverlay(parent, mode="light")
    assert "#ffffff" in light.bubble.styleSheet()  # bg_surface (light)
    assert "#1f2228" in light._body.styleSheet()  # text_primary (dark)


def test_overlay_captures_mouse_so_bubble_is_clickable(qtbot):
    """Regression: the overlay set WA_TransparentForMouseEvents on itself, so
    EVERY click — including the bubble's Next/Skip/Exit buttons — fell through
    to the UI behind it and the tutorial could never be advanced.

    The overlay must NOT be mouse-transparent; click-through to the real
    highlighted widget is handled by masking out the spotlight hole instead.
    """
    from qtpy.QtCore import Qt

    parent = QWidget()
    qtbot.addWidget(parent)
    ov = CoachOverlay(parent)
    assert ov.testAttribute(Qt.WA_TransparentForMouseEvents) is False


def test_next_button_click_emits_signal(qtbot):
    """A real mouse click on Next (not just a manual signal emit) must fire the
    overlay's next_clicked — proves the button wiring survives the overlay."""
    from qtpy.QtCore import Qt

    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()
    ov = CoachOverlay(parent)
    ov.set_bubble("<p>hi</p>", step_idx=0, n_steps=12, can_advance=True)
    ov.show()
    with qtbot.waitSignal(ov.next_clicked, timeout=1000):
        qtbot.mouseClick(ov._next_btn, Qt.LeftButton)


def test_spotlight_is_masked_out_for_clickthrough(qtbot):
    """With a spotlight set, the overlay masks out that rect so clicks there
    reach the real widget; with no spotlight it captures the whole surface."""
    from qtpy.QtCore import QRect

    parent = QWidget()
    qtbot.addWidget(parent)
    parent.resize(800, 600)
    ov = CoachOverlay(parent)
    ov.resize(800, 600)
    spot = QRect(100, 100, 120, 40)
    ov.set_target(spot)
    mask = ov.mask()
    assert not mask.isEmpty()
    # A point inside the spotlight is NOT part of the overlay (click passes
    # through to the real widget); a point outside it IS (dim captures it).
    assert not mask.contains(spot.center())
    assert mask.contains(QRect(0, 0, 800, 600).center())  # (400, 300), outside
    # No spotlight -> mask cleared, so the whole surface captures input again.
    ov.set_target(None)
    assert ov.mask().isEmpty()


from rrational.inspector.tutorial import TutorialController  # noqa: E402


@pytest.fixture
def mw(qtbot, tmp_path):
    from rrational.inspector import settings
    from rrational.inspector.main_window import MainWindow

    settings.enable_test_mode(tmp_path)
    w = MainWindow()
    w.test_mode = True
    w.set_ui_layout("mnelab")
    qtbot.addWidget(w)
    w.show()
    qtbot.waitExposed(w)
    return w


def _tut_panel(w):
    return w._browse_tab._preprocessing_panel


def test_start_loads_demo_and_shows_step_zero(mw):
    ctl = TutorialController(mw)
    ctl.start()
    assert ctl.is_active()
    assert ctl.current_index() == 0
    assert any(d.name == "TUTORIAL_demo.csv" for d in mw._datasets)


def _goto(ctl, key):
    """Drive the tour forward to the step with ``key`` (robust to reordering)."""
    target = next(i for i, s in enumerate(ctl._steps) if s.key == key)
    guard = 0
    while ctl.current_index() < target and ctl.is_active() and guard < 50:
        ctl._overlay.next_clicked.emit()
        guard += 1
    assert ctl.current_index() == target
    return target


def test_next_advances_from_welcome(mw):
    ctl = TutorialController(mw)
    ctl.start()
    ctl._overlay.next_clicked.emit()
    assert ctl.current_index() == 1  # first step after welcome (datasets)


def test_detect_click_auto_advances(mw):
    ctl = TutorialController(mw)
    ctl.start()
    detect_idx = _goto(ctl, "detect")
    _tut_panel(mw)._detect_btn.click()  # real action
    assert ctl.current_index() == detect_idx + 1  # auto-advanced to corrected


def test_corrected_toggle_auto_advances(qtbot, mw):
    ctl = TutorialController(mw)
    ctl.start()
    corrected_idx = _goto(ctl, "corrected")
    _tut_panel(mw)._detect_btn.click()  # enables the toggle
    _tut_panel(mw)._toggle_use_corrected.setChecked(True)  # real action
    qtbot.waitUntil(lambda: ctl.current_index() == corrected_idx + 1, timeout=2000)


def test_skip_and_exit(mw):
    ctl = TutorialController(mw)
    ctl.start()
    ctl._overlay.skip_clicked.emit()
    assert ctl.current_index() == 1
    ctl._overlay.exit_clicked.emit()
    assert not ctl.is_active()


def test_full_run_through_finishes(qtbot, mw):
    ctl = TutorialController(mw)
    ctl.start()
    for _ in range(len(ctl._steps) + 2):
        if not ctl.is_active():
            break
        ctl._overlay.skip_clicked.emit()
    assert not ctl.is_active()  # finished, overlay gone


def test_menu_action_starts_tutorial(mw):
    assert hasattr(mw, "_on_interactive_tutorial")
    mw._on_interactive_tutorial()
    ctl = getattr(mw, "_tutorial_controller", None)
    assert ctl is not None and ctl.is_active()
    ctl.exit()


def test_compute_step_does_not_autoskip_with_prior_results(mw):
    # Pre-populate the results store (as a returning user would have).
    from rrational.inspector.results_store import MetricRow

    mw._results_store.add_metric_row(
        MetricRow(mode="single", dataset="x", section="s", n_beats=100, metrics={})
    )
    ctl = TutorialController(mw)
    ctl.start()
    # Jump straight to the compute step and assert it did NOT auto-advance
    # despite the store already having a row (the old predicate bug).
    compute_idx = next(i for i, s in enumerate(ctl._steps) if s.key == "compute")
    ctl._enter_step(compute_idx)
    assert ctl.current_index() == compute_idx
    # The real Compute click advances it.
    mw._analysis_tab._single_pane._compute_btn.click()
    assert ctl.current_index() == compute_idx + 1
    ctl.exit()
