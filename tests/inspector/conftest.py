"""Pytest fixtures for the PyQtGraph inspector tests.

We piggy-back on ``pytest-qt``'s ``qtbot`` fixture for keypress/event
simulation. The headless-display setup is handled by ``pytest-qt``
itself — on Linux CI the offscreen QPA platform is selected via
``QT_QPA_PLATFORM=offscreen`` (set by the test runner or CI config).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pytest


@pytest.fixture
def synthetic_section():
    """A 300-second synthetic RR section used by most tests.

    Returns ``(timestamps, rr_ms)`` where:
    - ``timestamps`` are 300 ``datetime`` objects, one per second
    - ``rr_ms`` is a sine wave around 800 ms with 50 ms amplitude

    Picked to be long enough that the default ``set_data`` view (60 s)
    is clearly a SUBSET of the full signal — so any "show full range"
    bug is visible from a single viewRange assertion.
    """
    n = 300
    base = datetime(2026, 1, 1, 12, 0, 0)
    timestamps = [base + timedelta(seconds=i) for i in range(n)]
    rr_ms = (800 + 50 * np.sin(np.linspace(0, 6 * np.pi, n))).tolist()
    return timestamps, rr_ms
