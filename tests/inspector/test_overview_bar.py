"""Tests for the OverviewBar mini-map and its bidirectional sync.

Covers:
- Loading data populates the overview curve + sizes the viewport region
- Main-plot pan/zoom updates the rectangle in the overview
- Dragging the overview rectangle pans the main plot
- Sync doesn't infinite-loop (state stabilises after one update each way)
- View → Show overview bar toggle hides / re-shows the bar
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path):
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    yield


def _make_data(duration_s: int = 600):
    """Build an InspectorData with one section spanning ``duration_s`` s."""
    from rrational.inspector.data_loader import (
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    base = 1_700_000_000
    t = base + np.arange(duration_s, dtype=np.float64)
    v = 800 + 50 * np.sin(np.linspace(0, 6 * np.pi, duration_s))
    return InspectorData(
        t=t,
        v=v,
        sections=[
            SectionMeta(
                name="sec1",
                t_start=float(t[0]),
                t_end=float(t[-1]),
                beat_count=duration_s,
            )
        ],
        events=[EventMeta(label="ev1", t=float(t[duration_s // 2]))],
    )


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    # Phase 22.3: overview bar lives inside BrowseTab (MNE-LAB mode).
    win.set_ui_layout("mnelab")
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


# ---------------------------------------------------------------------
# Data rendering on the overview
# ---------------------------------------------------------------------
def test_overview_curve_populated_after_load(main_window):
    data = _make_data(600)
    main_window.load_data(data)

    curve_x, _ = main_window._overview_bar._curve.getData()
    assert len(curve_x) == len(data.t)


def test_overview_is_visible_after_load(main_window):
    main_window.load_data(_make_data(600))
    assert main_window._overview_bar.isVisible() is True


def test_overview_hidden_in_empty_state(main_window):
    """No file loaded → overview bar is hidden alongside the main plot."""
    assert main_window._overview_bar.isVisible() is False


# ---------------------------------------------------------------------
# Bidirectional sync
# ---------------------------------------------------------------------
def test_main_pan_updates_overview_region(main_window, qtbot):
    """Pan main → the rectangle in the overview must follow."""
    data = _make_data(600)
    main_window.load_data(data)

    t0 = data.t_start
    main_window._plot.getViewBox().setXRange(t0 + 100, t0 + 200, padding=0)

    lo, hi = main_window._overview_bar._viewport_region.getRegion()
    assert lo == pytest.approx(t0 + 100, abs=1.0)
    assert hi == pytest.approx(t0 + 200, abs=1.0)


def test_overview_region_drag_pans_main_plot(main_window):
    """Programmatically move the rectangle — main plot range must update."""
    data = _make_data(600)
    main_window.load_data(data)

    t0 = data.t_start
    new_lo, new_hi = t0 + 300, t0 + 400
    main_window._overview_bar._viewport_region.setRegion((new_lo, new_hi))

    x0, x1 = main_window._plot.getViewBox().viewRange()[0]
    assert x0 == pytest.approx(new_lo, abs=1.0)
    assert x1 == pytest.approx(new_hi, abs=1.0)


def test_sync_does_not_infinite_loop(main_window):
    """One round-trip (main → overview → main) must converge in finite steps.

    If the syncing guard isn't working, each setXRange would trigger an
    overview update, which would trigger a main update, etc. The pytest
    process would hang. Catching that the test even completes is the
    real assertion; the value check below is just belt-and-braces.
    """
    data = _make_data(600)
    main_window.load_data(data)

    t0 = data.t_start
    for _ in range(5):
        main_window._plot.getViewBox().setXRange(t0, t0 + 50, padding=0)
        main_window._overview_bar._viewport_region.setRegion((t0 + 100, t0 + 150))

    # Final state matches the LAST setRegion call (which won the round)
    x0, _ = main_window._plot.getViewBox().viewRange()[0]
    assert x0 == pytest.approx(t0 + 100, abs=1.0)


# ---------------------------------------------------------------------
# View toggle
# ---------------------------------------------------------------------
def test_view_toggle_hides_overview_bar(main_window):
    main_window.load_data(_make_data(600))
    act = main_window._toggle_overview_act

    assert main_window._overview_bar.isVisible() is True
    act.setChecked(False)
    assert main_window._overview_bar.isVisible() is False
    act.setChecked(True)
    assert main_window._overview_bar.isVisible() is True


# ---------------------------------------------------------------------
# Cluster B2 — mirror stripes for exclusion zones + annotations
# ---------------------------------------------------------------------
def test_set_exclusion_zones_adds_stripes(main_window):
    bar = main_window._overview_bar
    bar.set_exclusion_zones([(100.0, 110.0), (200.0, 220.0)])
    assert len(bar._exclusion_items) == 2


def test_set_exclusion_zones_replaces_previous(main_window):
    bar = main_window._overview_bar
    bar.set_exclusion_zones([(1.0, 2.0)])
    bar.set_exclusion_zones([(5.0, 6.0), (10.0, 11.0)])
    assert len(bar._exclusion_items) == 2


def test_set_annotations_adds_stripes(main_window):
    bar = main_window._overview_bar
    bar.set_annotations([(50.0, 55.0), (100.0, 100.0)])
    assert len(bar._annotation_items) == 2


def test_clear_overlays_removes_both_families(main_window):
    bar = main_window._overview_bar
    bar.set_exclusion_zones([(1.0, 2.0)])
    bar.set_annotations([(3.0, 4.0)])
    bar.clear_overlays()
    assert bar._exclusion_items == []
    assert bar._annotation_items == []


def test_clear_data_also_clears_overlays(main_window):
    bar = main_window._overview_bar
    bar.set_exclusion_zones([(1.0, 2.0)])
    bar.set_annotations([(3.0, 4.0)])
    bar.clear_data()
    assert bar._exclusion_items == []
    assert bar._annotation_items == []


def test_view_toggle_overview_persists(main_window):
    """Toggle state must round-trip through QSettings."""
    from rrational.inspector import settings

    main_window.load_data(_make_data(600))
    main_window.test_mode = False
    try:
        act = main_window._toggle_overview_act
        act.setChecked(False)
        assert settings.read_setting("show_overview_bar") is False
        act.setChecked(True)
        assert settings.read_setting("show_overview_bar") is True
    finally:
        main_window.test_mode = True
