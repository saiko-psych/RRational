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
        "timeline",
        "detect",
        "corrected",
        "exclusion",
        "setup_events",
        "setup_sections",
        "setup_groups",
        "setup_sequences",
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
    assert isinstance(by_key["compute"].completion, PredicateCompletion)


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
