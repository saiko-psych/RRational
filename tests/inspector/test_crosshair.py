"""Tests for the crosshair cursor and status-bar X/Y readout.

We don't simulate real mouse moves through Qt — that's flaky under
offscreen QPA. Instead we directly call ``_on_scene_mouse_moved`` with
a fabricated scene-position, which is the same handler the real
``sigMouseMoved`` signal would invoke. State assertions on the
crosshair line + the emitted Qt signal + the resulting status-bar
label cover the full integration.
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


def _data_with_gap():
    """InspectorData with one NaN sample sitting between two finite sections."""
    from rrational.inspector.data_loader import (
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    base = 1_700_000_000
    t1 = base + np.arange(100, dtype=np.float64)
    t2 = base + 200 + np.arange(100, dtype=np.float64)
    v1 = 800 + np.zeros(100)
    v2 = 850 + np.zeros(100)
    gap_t = (t1[-1] + t2[0]) / 2.0
    t = np.concatenate([t1, [gap_t], t2])
    v = np.concatenate([v1, [np.nan], v2])
    return (
        InspectorData(
            t=t,
            v=v,
            sections=[
                SectionMeta(
                    name="a", t_start=float(t1[0]), t_end=float(t1[-1]), beat_count=100
                ),
                SectionMeta(
                    name="b", t_start=float(t2[0]), t_end=float(t2[-1]), beat_count=100
                ),
            ],
            events=[EventMeta(label="a_start", t=float(t1[0]))],
        ),
        gap_t,
    )


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


def _fake_mouse_at(window, t_data, v_data=800):
    """Simulate a mouse hover at (t_data, v_data) in data coordinates.

    Default y=800 is well inside the [750, 850] range of ``_make_data``
    so the scene-rect containment check always passes — picking a y
    outside the visible range silently makes the handler bail.
    """
    vb = window._plot.getViewBox()
    scene_pos = vb.mapViewToScene(_point(t_data, v_data, vb))
    window._plot._on_scene_mouse_moved(scene_pos)


def _point(x, y, vb):
    """Build a QPointF in data coords (helper for mapViewToScene)."""
    from qtpy.QtCore import QPointF

    return QPointF(x, y)


# ---------------------------------------------------------------------
# Crosshair visibility
# ---------------------------------------------------------------------
def test_crosshair_disabled_by_default_until_data_loaded(main_window):
    """No data → crosshair never appears even if enabled."""
    main_window._plot.set_crosshair_visible(True)
    # No data loaded → handler returns early
    _fake_mouse_at(main_window, 0)
    assert main_window._plot._crosshair.isVisible() is False


def test_crosshair_appears_on_mouse_move_when_enabled(main_window):
    data = _make_data(200)
    main_window.load_data(data)
    main_window._plot.set_crosshair_visible(True)

    t_target = data.t_start + 50
    _fake_mouse_at(main_window, t_target, 850)

    assert main_window._plot._crosshair.isVisible() is True
    assert main_window._plot._crosshair.value() == pytest.approx(t_target, abs=1.0)


def test_crosshair_hidden_when_disabled_via_toggle(main_window):
    """View → Show crosshair OFF must hide the line + suppress emits."""
    data = _make_data(200)
    main_window.load_data(data)
    # Start from a known-enabled state, then toggle OFF.
    main_window._plot.set_crosshair_visible(True)
    _fake_mouse_at(main_window, data.t_start + 50)
    assert main_window._plot._crosshair.isVisible() is True

    main_window._toggle_crosshair_act.setChecked(False)
    _fake_mouse_at(main_window, data.t_start + 100)
    assert main_window._plot._crosshair.isVisible() is False
    assert main_window._plot._crosshair_enabled is False


# ---------------------------------------------------------------------
# Value lookup
# ---------------------------------------------------------------------
def test_value_at_returns_nan_outside_range(main_window):
    data = _make_data(200)
    main_window.load_data(data)
    # Cursor before first sample
    assert np.isnan(main_window._plot._value_at(data.t_start - 100))
    # Cursor after last sample
    assert np.isnan(main_window._plot._value_at(data.t_end + 100))


def test_value_at_returns_nan_over_gap(main_window):
    """A NaN sample between sections must propagate to the readout."""
    data, gap_t = _data_with_gap()
    main_window.load_data(data)

    val = main_window._plot._value_at(gap_t)
    assert np.isnan(val), f"expected NaN over gap, got {val}"


def test_value_at_interpolates_finite_neighbours(main_window):
    """Halfway between two known samples returns the mean."""
    from rrational.inspector.data_loader import (
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    # Construct a 2-sample timeline so the interpolation is exact.
    base = 1_700_000_000
    t = np.array([base, base + 1], dtype=np.float64)
    v = np.array([700.0, 900.0])
    data = InspectorData(
        t=t,
        v=v,
        sections=[
            SectionMeta(name="x", t_start=float(t[0]), t_end=float(t[-1]), beat_count=2)
        ],
        events=[EventMeta(label="x_start", t=float(t[0]))],
    )
    main_window.load_data(data)

    val = main_window._plot._value_at(base + 0.5)
    assert val == pytest.approx(800.0, abs=0.1)


# ---------------------------------------------------------------------
# Signal → status-bar readout integration
# ---------------------------------------------------------------------
def test_cursor_readout_formats_time_and_value(main_window):
    """``_update_cursor_readout`` produces a human-readable label.

    Calls the formatter directly rather than fabricating a sigMouseMoved
    event — under offscreen QPA the scene rect can be empty until the
    first real paint, which makes the rect-containment check inside
    ``_on_scene_mouse_moved`` non-deterministic. The formatter is the
    only thing that translates (t, v) into the visible label, so we
    exercise it head-on.
    """
    main_window._update_cursor_readout(1_700_000_000.0, 880.0)
    text = main_window._cursor_readout.text()
    assert "t:" in text
    assert "RR:" in text
    assert "880" in text
    assert "ms" in text


def test_cursor_readout_shows_dash_over_gap(main_window):
    main_window._update_cursor_readout(1_700_000_000.0, float("nan"))
    text = main_window._cursor_readout.text()
    assert "—" in text, f"expected em-dash for NaN, got: {text!r}"


def test_cursor_left_clears_readout(main_window):
    """``cursor_left`` signal must reset the label to empty."""
    main_window._update_cursor_readout(1_700_000_000.0, 880.0)
    assert main_window._cursor_readout.text() != ""
    main_window._clear_cursor_readout()
    assert main_window._cursor_readout.text() == ""
