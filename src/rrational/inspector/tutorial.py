"""Interactive coach-mark tutorial for the Inspector.

Unlike the read-through ``walkthrough`` wizard, this drives the user through
the real UI: a translucent overlay spotlights the actual widget for each step,
shows an instruction bubble, and — for action steps — waits for the user's real
action, detects completion, and auto-advances. A synthetic demo recording is
loaded on start so every step has real content.
"""

from __future__ import annotations

import numpy as np

from rrational.inspector.data_loader import (
    Dataset,
    EventMeta,
    InspectorData,
    SectionMeta,
)


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
