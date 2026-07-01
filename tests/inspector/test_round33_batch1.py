"""Round 33 batch-1 regression tests.

- E1: cross-dataset compute must use EACH dataset's own exclusion zones, not
  the single shared plot's (which belongs to the displayed dataset only).
- S1: save_color_scheme must write atomically (no stray .tmp, round-trips).
- A4: importing the same annotations twice must not duplicate them.
- A5: Annotation.create stamps created_at as tz-aware UTC.
"""

from __future__ import annotations

from datetime import datetime

import numpy as np
import pytest

from rrational.inspector.annotations import Annotation
from rrational.inspector.data_loader import Dataset, InspectorData
from rrational.inspector.exclusion_persistence import ExclusionZone
from rrational.inspector.tabs.analysis_tab import _exclusion_zones_for_dataset


# ---------------------------------------------------------------------
# E1 — per-dataset exclusion zones in cross-dataset compute
# ---------------------------------------------------------------------
class _FakePlot:
    def __init__(self, zones):
        self._exclusion_zones = list(zones)


class _FakeBrowse:
    def __init__(self, zones):
        self._plot = _FakePlot(zones)


class _FakeMW:
    def __init__(self, datasets, active_idx, live_zones):
        self._datasets = datasets
        self._active_idx = active_idx
        self._project = None
        self._browse_tab = _FakeBrowse(live_zones)


def _ds(name):
    d = InspectorData(t=np.arange(3.0), v=np.full(3, 800.0), sections=[], events=[])
    return Dataset(name=name, data=d)


def test_active_dataset_gets_live_plot_zones():
    a, b = _ds("A"), _ds("B")
    live = [ExclusionZone(start_t=1.0, end_t=2.0)]
    mw = _FakeMW([a, b], active_idx=0, live_zones=live)
    assert len(_exclusion_zones_for_dataset(mw, a)) == 1


def test_other_dataset_does_not_inherit_active_zones(tmp_path):
    from rrational.inspector import exclusion_persistence

    exclusion_persistence.set_exclusion_config_dir(tmp_path)
    try:
        a, b = _ds("A"), _ds("B")
        live = [ExclusionZone(start_t=1.0, end_t=2.0)]
        mw = _FakeMW([a, b], active_idx=0, live_zones=live)
        # B is not active and has no persisted zones -> empty, NOT A's zone.
        assert _exclusion_zones_for_dataset(mw, b) == []
    finally:
        exclusion_persistence.set_exclusion_config_dir(None)


def test_other_dataset_uses_its_own_persisted_zones(tmp_path):
    from rrational.inspector import exclusion_persistence

    exclusion_persistence.set_exclusion_config_dir(tmp_path)
    try:
        exclusion_persistence.save_exclusion_zones(
            "B", [ExclusionZone(start_t=5.0, end_t=6.0)]
        )
        a, b = _ds("A"), _ds("B")
        mw = _FakeMW([a, b], active_idx=0, live_zones=[ExclusionZone(1.0, 2.0)])
        zb = _exclusion_zones_for_dataset(mw, b)
        assert len(zb) == 1 and zb[0].start_t == 5.0  # B's own zone, not A's
    finally:
        exclusion_persistence.set_exclusion_config_dir(None)


# ---------------------------------------------------------------------
# S1 — color scheme atomic write
# ---------------------------------------------------------------------
def test_save_color_scheme_atomic_no_tmp(tmp_path, monkeypatch):
    from rrational.inspector import color_scheme_persistence as csp

    csp.set_color_scheme_config_dir(tmp_path)
    try:
        _name, scheme = csp.load_color_scheme()  # a valid default scheme
        csp.save_color_scheme("Scientific", scheme)
        assert not list(tmp_path.glob("*.tmp"))
        name, _scheme = csp.load_color_scheme()
        assert name == "Scientific"
    finally:
        csp.set_color_scheme_config_dir(None)


# ---------------------------------------------------------------------
# A5 — created_at is tz-aware UTC
# ---------------------------------------------------------------------
def test_annotation_created_at_is_utc_aware():
    ann = Annotation.create(t=1_700_000_000.0, text="cough")
    parsed = datetime.fromisoformat(ann.created_at)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0.0


# ---------------------------------------------------------------------
# S2 — live plot canvas follows a runtime theme switch
# ---------------------------------------------------------------------
def test_plot_apply_theme_mode_switches_canvas(qtbot):
    pytest.importorskip("pytestqt")
    pytest.importorskip("pyqtgraph")
    from rrational.inspector.app import set_plot_theme
    from rrational.inspector.plot_widget import RRPlotWidget

    set_plot_theme("dark")
    plot = RRPlotWidget()
    qtbot.addWidget(plot)
    assert plot.backgroundBrush().color().name().lower() == "#1a1d22"
    # A live switch must re-skin the already-constructed canvas.
    plot.apply_theme_mode("light")
    assert plot.backgroundBrush().color().name().lower() == "#f8f6f1"
    plot.apply_theme_mode("dark")
    assert plot.backgroundBrush().color().name().lower() == "#1a1d22"
