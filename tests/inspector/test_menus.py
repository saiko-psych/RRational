"""Tests for the View / Edit / Tools / Help menus.

Covers:
- View-menu checkable toggles change visibility + persist via QSettings
- Tools-menu stubs are present and disabled (until Phase 4 wires them up)
- Help menu shows Shortcuts (F1) and About entries
- Initial check-state is read from QSettings (so persistence round-trips)

Access pattern: we use MainWindow's directly-held QAction references
(``_toggle_sidebar_act`` etc.) rather than walking ``menuBar().actions()
.menu().actions()``. Walking the menubar hands back Python wrappers
around QMenu objects whose C++ owners may be GC'd between assertions —
the strong-ref attributes on MainWindow keep the actions alive for
the full test.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path):
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    yield


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    # Phase 22.3: BrowseTab (and therefore its sidebar) is hidden in
    # Streamlit mode (the new default). The sidebar-toggle assertions
    # here predate the switcher, so force MNE-LAB mode to keep them valid.
    win.set_ui_layout("mnelab")
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


# ---------------------------------------------------------------------
# Menu skeleton
# ---------------------------------------------------------------------
def test_all_top_level_menus_exist(main_window):
    """File, View, Edit, Tools, Help must all be on the menu bar."""
    titles = [a.text().replace("&", "") for a in main_window.menuBar().actions()]
    for expected in ["File", "View", "Edit", "Tools", "Help"]:
        assert expected in titles


def test_view_toggle_actions_are_held_on_window(main_window):
    """All four View toggles must be reachable as MainWindow attributes."""
    assert main_window._toggle_sidebar_act is not None
    assert main_window._toggle_sections_act is not None
    assert main_window._toggle_events_act is not None
    assert main_window._toggle_grid_act is not None
    for act in (
        main_window._toggle_sidebar_act,
        main_window._toggle_sections_act,
        main_window._toggle_events_act,
        main_window._toggle_grid_act,
    ):
        assert act.isCheckable() is True


# ---------------------------------------------------------------------
# View toggles
# ---------------------------------------------------------------------
def test_sidebar_toggle_hides_dataset_tree(main_window):
    act = main_window._toggle_sidebar_act
    assert main_window._dataset_tree.isVisible() is True
    act.setChecked(False)
    assert main_window._dataset_tree.isVisible() is False
    act.setChecked(True)
    assert main_window._dataset_tree.isVisible() is True


def test_sections_toggle_hides_overlays(main_window):
    """``Show section bands`` flips visibility on every SectionRegion."""
    import numpy as np
    from rrational.inspector.data_loader import (
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    t = 1_700_000_000 + np.arange(100, dtype=np.float64)
    v = 800 + 50 * np.sin(np.linspace(0, np.pi, 100))
    data = InspectorData(
        t=t,
        v=v,
        sections=[
            SectionMeta(
                name="sec1", t_start=float(t[0]), t_end=float(t[-1]), beat_count=100
            )
        ],
        events=[EventMeta(label="ev1", t=float(t[50]))],
    )
    main_window.load_data(data)

    act = main_window._toggle_sections_act
    region = main_window._plot._section_regions[0]

    assert region.isVisible() is True
    act.setChecked(False)
    assert region.isVisible() is False
    act.setChecked(True)
    assert region.isVisible() is True


def test_events_toggle_hides_markers(main_window):
    import numpy as np
    from rrational.inspector.data_loader import (
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    t = 1_700_000_000 + np.arange(100, dtype=np.float64)
    v = 800 + 50 * np.sin(np.linspace(0, np.pi, 100))
    data = InspectorData(
        t=t,
        v=v,
        sections=[
            SectionMeta(
                name="sec1", t_start=float(t[0]), t_end=float(t[-1]), beat_count=100
            )
        ],
        events=[EventMeta(label="ev1", t=float(t[50]))],
    )
    main_window.load_data(data)

    act = main_window._toggle_events_act
    marker = main_window._plot._event_markers[0]

    assert marker.isVisible() is True
    act.setChecked(False)
    assert marker.isVisible() is False
    act.setChecked(True)
    assert marker.isVisible() is True


def test_view_toggle_persists_via_qsettings(main_window):
    """Flipping a toggle writes the new state to QSettings immediately."""
    from rrational.inspector import settings

    # Persistence only triggers when test_mode is OFF (see _make_view_toggle).
    main_window.test_mode = False
    try:
        act = main_window._toggle_sidebar_act
        act.setChecked(False)
        assert settings.read_setting("show_sidebar") is False
        act.setChecked(True)
        assert settings.read_setting("show_sidebar") is True
    finally:
        main_window.test_mode = True


def test_view_toggle_initial_state_read_from_qsettings(qtbot):
    """If QSettings says hidden, the toggle must START unchecked + hidden."""
    from rrational.inspector import settings
    from rrational.inspector.main_window import MainWindow

    settings.write_setting("show_sidebar", False)

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    assert win._toggle_sidebar_act.isChecked() is False
    assert win._dataset_tree.isVisible() is False
