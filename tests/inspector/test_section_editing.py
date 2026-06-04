"""Tests for Phase 16 — Section boundary editing.

Covers:
- Default state of the edit-mode flag.
- ``set_section_edit_mode`` propagates ``setMovable(True)`` onto every
  existing :class:`SectionRegion`.
- Drag-end on a region updates the in-memory :class:`SectionMeta` AND
  the on-disk ``sections.yml``.
- Right-click context-menu actions (rename / delete / split) mutate
  both the dataset and the YAML.

Isolation: the autouse fixture redirects every persistence path
(``gui.persistence.CONFIG_DIR``, the inspector persistence module,
and the global QSettings store) so nothing leaks to the user's real
``~/.rrational/sections.yml``.
"""

from __future__ import annotations


import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path, monkeypatch):
    """Match the pattern from test_artifact_persistence.py — every
    persistence layer points inside ``tmp_path`` for the duration of
    the test, so writes never reach the developer's real home dir."""
    from rrational.gui import persistence as gui_persistence
    from rrational.inspector import persistence as inspector_persistence
    from rrational.inspector import results_persistence as rp
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    inspector_persistence.set_inspector_config_dir(tmp_path)
    monkeypatch.setattr(gui_persistence, "CONFIG_DIR", tmp_path / "gui_config")
    monkeypatch.setattr(
        gui_persistence,
        "SETTINGS_FILE",
        tmp_path / "gui_config" / "settings.yml",
    )
    monkeypatch.setattr(
        gui_persistence, "SECTIONS_FILE", tmp_path / "gui_config" / "sections.yml"
    )
    monkeypatch.setattr(rp, "_DEFAULT_DIR", tmp_path / "inspector_global")
    yield
    inspector_persistence.set_inspector_config_dir(None)


@pytest.fixture
def main_window(qtbot, synthetic_inspector_data):
    """A MainWindow with the 3-section synthetic dataset loaded."""
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    win.load_data(synthetic_inspector_data)
    return win


# ----------------------------------------------------------------------
# Default state
# ----------------------------------------------------------------------
def test_default_section_edit_mode_off(main_window):
    """The plot's edit-mode flag must be False on a freshly-built widget
    (no surprise: ``add_section_region`` then spawns non-movable regions)."""
    plot = main_window._browse_tab._plot
    assert plot._section_edit_mode is False
    # Each existing SectionRegion should reflect the flag too.
    for region in plot._section_regions:
        assert region.movable is False


# ----------------------------------------------------------------------
# Toggle propagation
# ----------------------------------------------------------------------
def test_set_section_edit_mode_toggles_movability(main_window):
    """Calling ``set_section_edit_mode(True)`` flips every region's
    movability flag (parent and child handle InfiniteLines)."""
    plot = main_window._browse_tab._plot
    assert plot._section_regions, "synthetic data must have at least 1 section"

    plot.set_section_edit_mode(True)
    assert plot._section_edit_mode is True
    for region in plot._section_regions:
        assert region.movable is True
        # The child InfiniteLines are the actual draggable handles.
        for line in region.lines:
            assert line.movable is True

    plot.set_section_edit_mode(False)
    for region in plot._section_regions:
        assert region.movable is False


# ----------------------------------------------------------------------
# Drag → persist
# ----------------------------------------------------------------------
def test_drag_end_persists_section_meta(main_window):
    """Simulating ``sigRegionChangeFinished`` updates the in-memory
    SectionMeta AND writes the new bounds into sections.yml."""
    from rrational.gui.persistence import load_sections

    plot = main_window._browse_tab._plot
    plot.set_section_edit_mode(True)

    data = main_window._data
    target = data.sections[0]  # "rest_pre"
    original_t_end = target.t_end
    new_t_end = original_t_end + 5.0  # 5 seconds later

    region = plot._sections_by_label[target.name]
    # Programmatically move the region's right edge. setRegion fires
    # sigRegionChangeFinished which the plot forwards to MainWindow.
    region.setRegion((target.t_start, new_t_end))

    # In-memory SectionMeta updated.
    refreshed = next(s for s in main_window._data.sections if s.name == target.name)
    assert refreshed.t_end == pytest.approx(new_t_end, abs=1.5)

    # sections.yml round-trips.
    on_disk = load_sections()
    assert target.name in on_disk
    assert "t_end" in on_disk[target.name]
    assert on_disk[target.name]["t_end"] == pytest.approx(new_t_end, abs=1.5)


# ----------------------------------------------------------------------
# Rename
# ----------------------------------------------------------------------
def test_rename_request_via_qinputdialog_persists(main_window, monkeypatch):
    """Emitting ``sigRenameRequested`` opens QInputDialog; mocking it to
    return a new name renames the section in-memory and in sections.yml."""
    from qtpy.QtWidgets import QInputDialog

    from rrational.gui.persistence import load_sections, save_sections

    # Seed sections.yml with an existing entry so we can verify the
    # payload is preserved across the rename.
    save_sections({"rest_pre": {"label": "rest_pre", "description": "baseline"}})

    monkeypatch.setattr(
        QInputDialog, "getText", lambda *a, **kw: ("rest_baseline", True)
    )

    plot = main_window._browse_tab._plot
    plot.set_section_edit_mode(True)
    plot.sigSectionRenameRequested.emit("rest_pre")

    names = [s.name for s in main_window._data.sections]
    assert "rest_baseline" in names
    assert "rest_pre" not in names

    on_disk = load_sections()
    assert "rest_baseline" in on_disk
    assert "rest_pre" not in on_disk
    # The "description" payload survives the rename.
    assert on_disk["rest_baseline"].get("description") == "baseline"


def test_rename_request_cancelled_is_noop(main_window, monkeypatch):
    from qtpy.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **kw: ("ignored", False))

    plot = main_window._browse_tab._plot
    plot.set_section_edit_mode(True)
    before = [s.name for s in main_window._data.sections]
    plot.sigSectionRenameRequested.emit("rest_pre")
    after = [s.name for s in main_window._data.sections]
    assert before == after


# ----------------------------------------------------------------------
# Delete
# ----------------------------------------------------------------------
def test_delete_request_persists(main_window):
    from rrational.gui.persistence import load_sections, save_sections

    # Seed sections.yml with both target + another, so we can verify the
    # delete affects only the chosen one.
    save_sections(
        {
            "rest_pre": {"label": "rest_pre"},
            "music_block": {"label": "music_block"},
        }
    )

    plot = main_window._browse_tab._plot
    plot.set_section_edit_mode(True)
    plot.sigSectionDeleteRequested.emit("rest_pre")

    names = [s.name for s in main_window._data.sections]
    assert "rest_pre" not in names
    # The other in-memory sections survive.
    assert "music_block" in names

    on_disk = load_sections()
    assert "rest_pre" not in on_disk
    assert "music_block" in on_disk  # other sections preserved


# ----------------------------------------------------------------------
# Split
# ----------------------------------------------------------------------
def test_split_request_creates_two_sections(main_window):
    from rrational.gui.persistence import load_sections

    plot = main_window._browse_tab._plot
    plot.set_section_edit_mode(True)

    target = main_window._data.sections[1]  # "music_block"
    original_total = target.t_end - target.t_start
    midpoint = target.t_start + original_total / 2

    plot.sigSectionSplitRequested.emit(target.name, midpoint)

    names = [s.name for s in main_window._data.sections]
    assert f"{target.name}_a" in names
    assert f"{target.name}_b" in names
    assert target.name not in names

    by_name = {s.name: s for s in main_window._data.sections}
    a = by_name[f"{target.name}_a"]
    b = by_name[f"{target.name}_b"]
    # Boundaries: t_start preserved on _a, t_end preserved on _b,
    # the shared boundary == the snapped midpoint.
    assert a.t_start == pytest.approx(target.t_start, abs=1.5)
    assert b.t_end == pytest.approx(target.t_end, abs=1.5)
    assert a.t_end == pytest.approx(b.t_start, abs=1e-6)

    on_disk = load_sections()
    assert f"{target.name}_a" in on_disk
    assert f"{target.name}_b" in on_disk
    assert target.name not in on_disk


def test_split_outside_section_is_noop(main_window):
    """Splitting at a point that lies outside the section's range
    must leave the dataset unchanged (and not crash)."""
    plot = main_window._browse_tab._plot
    plot.set_section_edit_mode(True)

    target = main_window._data.sections[0]  # "rest_pre"
    bad_t = target.t_end + 9999.0  # well past the section's end
    before = [s.name for s in main_window._data.sections]
    plot.sigSectionSplitRequested.emit(target.name, bad_t)
    after = [s.name for s in main_window._data.sections]
    assert before == after
