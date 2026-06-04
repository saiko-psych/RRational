"""Tests for Phase 15 — Exclusion zones (drag-select + persistence)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path, monkeypatch):
    """Redirect every persistence layer to a tmp_path-only sandbox."""
    from rrational.gui import persistence as gui_persistence
    from rrational.inspector import exclusion_persistence
    from rrational.inspector import persistence as inspector_persistence
    from rrational.inspector import results_persistence as rp
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    inspector_persistence.set_inspector_config_dir(tmp_path)
    exclusion_persistence.set_exclusion_config_dir(tmp_path / "excl_global")
    monkeypatch.setattr(gui_persistence, "CONFIG_DIR", tmp_path / "gui_config")
    monkeypatch.setattr(
        gui_persistence, "SETTINGS_FILE", tmp_path / "gui_config" / "settings.yml"
    )
    monkeypatch.setattr(rp, "_DEFAULT_DIR", tmp_path / "inspector_global")
    yield
    inspector_persistence.set_inspector_config_dir(None)
    exclusion_persistence.set_exclusion_config_dir(None)


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


def _synthetic_dataset(name: str = "SUBJ_001.csv"):
    """Build a 5-minute synthetic dataset with two named sections."""
    from rrational.inspector.data_loader import (
        Dataset,
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    t0 = 1_700_000_000.0
    # 600 beats at ~500 ms apart => ~300 s of data.
    rng = np.random.default_rng(0)
    rr_ms = 500 + 30 * rng.standard_normal(600)
    t = t0 + np.cumsum(rr_ms) / 1000.0
    v = np.full(600, 800.0)  # constant ms so RMSSD is well-defined

    mid_t = float(t[299])
    sections = [
        SectionMeta(name="rest", t_start=float(t[0]), t_end=mid_t, beat_count=300),
        SectionMeta(name="music", t_start=mid_t, t_end=float(t[-1]), beat_count=300),
    ]
    events = [
        EventMeta(label="rest_start", t=float(t[0])),
        EventMeta(label="music_start", t=mid_t),
    ]
    return Dataset(
        name=name, data=InspectorData(t=t, v=v, sections=sections, events=events)
    )


# ---------------------------------------------------------------------
# Persistence roundtrip
# ---------------------------------------------------------------------
def test_persistence_roundtrip(tmp_path):
    """Save → load returns the same zones in the same order."""
    from rrational.inspector.exclusion_persistence import (
        ExclusionZone,
        load_exclusion_zones,
        save_exclusion_zones,
    )

    z1 = ExclusionZone(
        start_t=1_700_000_010.0,
        end_t=1_700_000_020.0,
        reason="motion artifact",
        start_beat_idx=10,
        end_beat_idx=22,
    )
    z2 = ExclusionZone(start_t=1_700_000_100.0, end_t=1_700_000_120.0, reason="cough")
    save_exclusion_zones("P01", [z1, z2])
    loaded = load_exclusion_zones("P01")
    assert len(loaded) == 2
    assert loaded[0].start_t == pytest.approx(z1.start_t)
    assert loaded[0].end_t == pytest.approx(z1.end_t)
    assert loaded[0].reason == "motion artifact"
    assert loaded[0].start_beat_idx == 10
    assert loaded[0].end_beat_idx == 22
    assert loaded[1].reason == "cough"


def test_delete_removes_file(tmp_path):
    from rrational.inspector.exclusion_persistence import (
        ExclusionZone,
        _zones_path,
        delete_exclusion_zones,
        save_exclusion_zones,
    )

    z = ExclusionZone(start_t=1.0, end_t=2.0, reason="x")
    save_exclusion_zones("P02", [z])
    p = _zones_path("P02", None)
    assert p.exists()
    delete_exclusion_zones("P02")
    assert not p.exists()
    # No-op when missing
    delete_exclusion_zones("P02")


def test_load_missing_returns_empty(tmp_path):
    from rrational.inspector.exclusion_persistence import load_exclusion_zones

    assert load_exclusion_zones("NEVER_SAVED") == []


# ---------------------------------------------------------------------
# Drag-create + UI integration
# ---------------------------------------------------------------------
def test_drag_creates_zone(main_window):
    """Simulating a drag in exclusion mode adds a zone to the plot."""
    ds = _synthetic_dataset()
    main_window.add_dataset(ds)
    main_window.set_active_dataset(0)

    panel = main_window._browse_tab._preprocessing_panel
    panel._toggle_exclusion_mode.setChecked(True)

    plot = main_window._browse_tab._plot
    t0 = ds.data.t[50]
    t1 = ds.data.t[100]
    # Simulate the ViewBox's drag-finished signal — the same path the
    # mouse event would take, sans Qt input plumbing.
    plot._on_exclusion_drag_finished(float(t0), float(t1))

    assert len(plot._exclusion_zones) == 1
    z = plot._exclusion_zones[0]
    assert z.start_t == pytest.approx(float(t0))
    assert z.end_t == pytest.approx(float(t1))


def test_drag_below_min_width_ignored(main_window):
    """A near-zero drag (jitter from a click) MUST NOT make a zone."""
    ds = _synthetic_dataset()
    main_window.add_dataset(ds)
    main_window.set_active_dataset(0)

    plot = main_window._browse_tab._plot
    panel = main_window._browse_tab._preprocessing_panel
    panel._toggle_exclusion_mode.setChecked(True)

    t = float(ds.data.t[10])
    plot._on_exclusion_drag_finished(t, t + 0.01)
    assert plot._exclusion_zones == []


def test_drag_creates_zone_autosaves(main_window, tmp_path):
    """A new zone is immediately persisted to disk."""
    from rrational.inspector.exclusion_persistence import load_exclusion_zones

    ds = _synthetic_dataset()
    main_window.add_dataset(ds)
    main_window.set_active_dataset(0)
    plot = main_window._browse_tab._plot
    t0 = float(ds.data.t[50])
    t1 = float(ds.data.t[100])
    plot._on_exclusion_drag_finished(t0, t1)

    pid = Path(ds.name).stem
    loaded = load_exclusion_zones(pid)
    assert len(loaded) == 1
    assert loaded[0].start_t == pytest.approx(t0)


def test_edit_reason_persists(main_window):
    """update_exclusion_reason updates the model AND triggers auto-save."""
    from rrational.inspector.exclusion_persistence import load_exclusion_zones

    ds = _synthetic_dataset()
    main_window.add_dataset(ds)
    main_window.set_active_dataset(0)
    plot = main_window._browse_tab._plot
    plot._on_exclusion_drag_finished(float(ds.data.t[10]), float(ds.data.t[40]))
    plot.update_exclusion_reason(0, "ECG lead detached")

    pid = Path(ds.name).stem
    loaded = load_exclusion_zones(pid)
    assert loaded and loaded[0].reason == "ECG lead detached"


def test_delete_zone_removes_from_disk(main_window):
    """remove_exclusion_zone updates the model + writes an empty file."""
    from rrational.inspector.exclusion_persistence import load_exclusion_zones

    ds = _synthetic_dataset()
    main_window.add_dataset(ds)
    main_window.set_active_dataset(0)
    plot = main_window._browse_tab._plot
    plot._on_exclusion_drag_finished(float(ds.data.t[10]), float(ds.data.t[40]))
    assert len(plot._exclusion_zones) == 1
    plot.remove_exclusion_zone(0)
    assert plot._exclusion_zones == []

    pid = Path(ds.name).stem
    loaded = load_exclusion_zones(pid)
    assert loaded == []


# ---------------------------------------------------------------------
# Auto-restore
# ---------------------------------------------------------------------
def test_restore_on_dataset_switch(main_window):
    """Closing + reopening the same dataset re-loads zones from disk."""
    ds = _synthetic_dataset()
    main_window.add_dataset(ds)
    main_window.set_active_dataset(0)
    plot = main_window._browse_tab._plot
    plot._on_exclusion_drag_finished(float(ds.data.t[10]), float(ds.data.t[40]))
    assert len(plot._exclusion_zones) == 1

    main_window.close_all_datasets()
    assert plot._exclusion_zones == []

    # Re-add the same-name dataset; pid resolves to the same yml.
    main_window.add_dataset(_synthetic_dataset())
    main_window.set_active_dataset(0)
    assert len(plot._exclusion_zones) == 1


# ---------------------------------------------------------------------
# HRV compute integration
# ---------------------------------------------------------------------
def test_slice_section_filters_excluded_beats():
    """_slice_section drops every beat inside any supplied zone."""
    from rrational.inspector.exclusion_persistence import ExclusionZone
    from rrational.inspector.tabs.analysis_tab import _slice_section

    ds = _synthetic_dataset()
    # Exclude a wide chunk of the "rest" section.
    z = ExclusionZone(start_t=float(ds.data.t[50]), end_t=float(ds.data.t[150]))
    full = _slice_section(ds.data, "rest", exclusions=None)
    pruned = _slice_section(ds.data, "rest", exclusions=[z])
    assert pruned is not None
    assert len(pruned) < len(full)
    # Roughly 100 beats removed
    assert len(full) - len(pruned) >= 99


def test_compute_uses_exclusion_zones(main_window):
    """The Single Participant pane respects the active exclusion zones."""
    ds = _synthetic_dataset()
    main_window.add_dataset(ds)
    main_window.set_active_dataset(0)
    plot = main_window._browse_tab._plot

    # Mark almost the entire "rest" section as excluded.
    plot._on_exclusion_drag_finished(float(ds.data.t[1]), float(ds.data.t[295]))

    # Switch to Single Participant pane + compute.
    single = main_window._analysis_tab._single_pane
    single.refresh_workspace()
    single._section_combo.setCurrentText("rest")
    single._on_compute()
    # n_beats reported in the meta row should be much smaller than 300
    n_beats_item = single._result_table.item(1, 1)
    assert n_beats_item is not None
    n_beats = int(n_beats_item.text())
    assert n_beats < 10  # near-total exclusion


# ---------------------------------------------------------------------
# Project-scope routing
# ---------------------------------------------------------------------
def test_project_routing(main_window, tmp_path):
    """When a project is open, the YAML lands in project/data/processed/."""
    from rrational.gui.project import ProjectManager
    from rrational.inspector import exclusion_persistence

    # Disable the global test override so the project_path argument
    # actually drives the path resolution.
    exclusion_persistence.set_exclusion_config_dir(None)

    pm = ProjectManager.create_project(tmp_path / "ProjX", name="ProjX")
    main_window.set_active_project(pm)
    ds = _synthetic_dataset(name="P77.csv")
    main_window.add_dataset(ds)
    main_window.set_active_dataset(0)
    plot = main_window._browse_tab._plot
    plot._on_exclusion_drag_finished(float(ds.data.t[5]), float(ds.data.t[20]))

    expected = pm.project_path / "data" / "processed" / "P77_exclusions.yml"
    assert expected.exists()
