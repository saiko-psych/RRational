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
    """Load the tutorial demo dataset if the workspace doesn't already have it."""
    datasets = getattr(mw, "_datasets", None)
    if datasets is None:
        return
    for i, d in enumerate(datasets):
        if getattr(d, "name", "") == "TUTORIAL_demo.csv":
            mw.set_active_dataset(i)
            return
    mw.add_dataset(build_tutorial_dataset())
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
        completion=PredicateCompletion(
            lambda mw: len(getattr(mw, "_results_store").metric_rows) > 0
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
