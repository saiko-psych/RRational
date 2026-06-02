"""Phase 2 tests: continuous-timeline overlays and sidebar interaction.

Covers:
- ``SectionRegion`` is added for every section with correct bounds
- ``EventMarker`` is added for every event at the right timestamp
- Sidebar click zooms the plot to the chosen section's time range
- ``highlight_section`` exclusively highlights the selected band
- ``clear_overlays`` removes all items and drops the lookup table
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture
def main_window(qtbot, synthetic_inspector_data):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.load_data(synthetic_inspector_data)
    win.show()
    qtbot.waitExposed(win)
    return win


# ---------------------------------------------------------------------
# Overlay rendering
# ---------------------------------------------------------------------
def test_load_creates_one_section_region_per_section(
    main_window, synthetic_inspector_data
):
    """``load_data`` must spawn exactly N region items, one per section."""
    regions = main_window._plot._section_regions
    assert len(regions) == len(synthetic_inspector_data.sections)


def test_section_region_bounds_match_metadata(main_window, synthetic_inspector_data):
    """Each SectionRegion's (t_start, t_end) must match its source meta."""
    regions_by_label = main_window._plot._sections_by_label
    for meta in synthetic_inspector_data.sections:
        region = regions_by_label[meta.name]
        lo, hi = region.getRegion()
        assert lo == pytest.approx(meta.t_start, abs=0.5)
        assert hi == pytest.approx(meta.t_end, abs=0.5)


def test_load_creates_one_marker_per_event(main_window, synthetic_inspector_data):
    """Same count check for ``EventMarker``."""
    markers = main_window._plot._event_markers
    assert len(markers) == len(synthetic_inspector_data.events)


def test_event_marker_x_matches_event_timestamp(main_window, synthetic_inspector_data):
    """Each EventMarker must sit at exactly its event's timestamp."""
    markers = main_window._plot._event_markers
    expected_xs = sorted(ev.t for ev in synthetic_inspector_data.events)
    actual_xs = sorted(m.value() for m in markers)
    for exp, act in zip(expected_xs, actual_xs):
        assert act == pytest.approx(exp, abs=0.5)


def test_event_marker_labels_round_trip(main_window, synthetic_inspector_data):
    """``event_label`` attribute on each marker must echo the source label."""
    actual = {m.event_label for m in main_window._plot._event_markers}
    expected = {ev.label for ev in synthetic_inspector_data.events}
    assert actual == expected


# ---------------------------------------------------------------------
# Sidebar interaction
# ---------------------------------------------------------------------
def test_sidebar_click_zooms_to_section(main_window, synthetic_inspector_data):
    """Clicking a section in the sidebar must zoom to that section's span."""
    from qtpy.QtCore import Qt

    target = synthetic_inspector_data.sections[1]  # "music_block", 900 s

    # Find the sidebar item for that section
    item = next(
        main_window._section_list.item(i)
        for i in range(main_window._section_list.count())
        if main_window._section_list.item(i).data(Qt.UserRole) == target.name
    )
    main_window._on_section_clicked(item)

    xmin, xmax = main_window._plot.getViewBox().viewRange()[0]
    # padding_frac=0.02 means up to ±2% beyond the meta range
    section_span = target.t_end - target.t_start
    assert (xmax - xmin) == pytest.approx(section_span * 1.04, rel=0.05)
    assert xmin <= target.t_start
    assert xmax >= target.t_end


def test_sidebar_click_highlights_only_clicked_section(
    main_window, synthetic_inspector_data
):
    """``highlight_section`` must boost the alpha of exactly one band."""
    from qtpy.QtCore import Qt
    from rrational.inspector.graphic_items import SECTION_ALPHA

    target = synthetic_inspector_data.sections[1]
    item = next(
        main_window._section_list.item(i)
        for i in range(main_window._section_list.count())
        if main_window._section_list.item(i).data(Qt.UserRole) == target.name
    )
    main_window._on_section_clicked(item)

    for name, region in main_window._plot._sections_by_label.items():
        alpha = region.brush.color().alpha()
        if name == target.name:
            assert alpha > SECTION_ALPHA, f"selected section {name} not highlighted"
        else:
            assert alpha == SECTION_ALPHA, f"non-selected section {name} bumped"


# ---------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------
def test_clear_overlays_removes_all_items(main_window):
    """``clear_overlays`` empties both lists and the lookup dict."""
    main_window._plot.clear_overlays()
    assert main_window._plot._section_regions == []
    assert main_window._plot._event_markers == []
    assert main_window._plot._sections_by_label == {}


def test_reloading_data_replaces_overlays(main_window, synthetic_inspector_data):
    """Calling ``load_data`` twice must not duplicate overlays.

    Regression net for the mne-qt-browser ``#136`` pattern: re-rendering
    accumulates plot items if the old ones aren't explicitly cleared.
    """
    before = len(main_window._plot._section_regions)
    main_window.load_data(synthetic_inspector_data)
    after = len(main_window._plot._section_regions)
    assert before == after
