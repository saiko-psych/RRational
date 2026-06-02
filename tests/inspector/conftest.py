"""Pytest fixtures for the PyQtGraph inspector tests.

We piggy-back on ``pytest-qt``'s ``qtbot`` fixture for keypress/event
simulation. The headless-display setup is handled by ``pytest-qt``
itself — on Linux CI the offscreen QPA platform is selected via
``QT_QPA_PLATFORM=offscreen`` (set by the test runner or CI config).
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest


# Anchor timestamp used by every synthetic fixture so tests don't drift
# with the wall-clock. Picked to be far enough in the future that any
# bug printing "current time" would stand out, and aligned to a minute
# boundary for easier debugging.
_T0 = datetime(2026, 1, 1, 12, 0, 0).timestamp()


@pytest.fixture
def synthetic_inspector_data():
    """A 3-section synthetic ``InspectorData`` for navigation tests.

    Layout (seconds since _T0):
        [0,   300]   "rest_pre"        300 beats
        [300, 1200]  "music_block"     900 beats — touches rest_pre
        [1300, 1600] "rest_post"       300 beats — 100 s gap before it

    Total span: 1600 s. The mid-recording gap forces a NaN sample in
    the concatenated timeline (data_loader inserts one), so tests
    implicitly exercise the NaN-aware finite-mask code in
    ``jump_start`` / ``jump_end``.
    """
    from rrational.inspector.data_loader import (
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    def _ramp(n_seconds: int, t_offset: float):
        t = _T0 + t_offset + np.arange(n_seconds, dtype=np.float64)
        v = 800 + 50 * np.sin(np.linspace(0, 6 * np.pi, n_seconds))
        return t, v

    t1, v1 = _ramp(300, 0)
    t2, v2 = _ramp(900, 300)
    t3, v3 = _ramp(300, 1300)

    # Mimic data_loader: insert a NaN gap between sections that aren't
    # contiguous (gap between t2[-1] = T0+1199 and t3[0] = T0+1300).
    gap_t = (t2[-1] + t3[0]) / 2.0
    t_full = np.concatenate([t1, t2, [gap_t], t3])
    v_full = np.concatenate([v1, v2, [np.nan], v3])

    sections = [
        SectionMeta(
            name="rest_pre", t_start=float(t1[0]), t_end=float(t1[-1]), beat_count=300
        ),
        SectionMeta(
            name="music_block",
            t_start=float(t2[0]),
            t_end=float(t2[-1]),
            beat_count=900,
        ),
        SectionMeta(
            name="rest_post", t_start=float(t3[0]), t_end=float(t3[-1]), beat_count=300
        ),
    ]
    events = [
        EventMeta(label="rest_pre_start", t=float(t1[0])),
        EventMeta(label="music_start", t=float(t2[0])),
        EventMeta(label="music_end", t=float(t2[-1])),
        EventMeta(label="rest_post_start", t=float(t3[0])),
    ]
    return InspectorData(t=t_full, v=v_full, sections=sections, events=events)
