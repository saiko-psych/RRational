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
