"""Tests for Phase 12 — Artifact-correction persistence (Streamlit-shared)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path, monkeypatch):
    from rrational.gui import persistence as gui_persistence
    from rrational.inspector import persistence as inspector_persistence
    from rrational.inspector import results_persistence as rp
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    inspector_persistence.set_inspector_config_dir(tmp_path)
    monkeypatch.setattr(gui_persistence, "CONFIG_DIR", tmp_path / "gui_config")
    monkeypatch.setattr(
        gui_persistence, "SETTINGS_FILE", tmp_path / "gui_config" / "settings.yml"
    )
    monkeypatch.setattr(rp, "_DEFAULT_DIR", tmp_path / "inspector_global")
    yield
    inspector_persistence.set_inspector_config_dir(None)


def _exists_or_skip(rel_path: str) -> Path:
    p = Path(rel_path)
    if not p.exists():
        pytest.skip(f"missing test fixture: {p}")
    return p


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


# ---------------------------------------------------------------------
# Auto-save after detect
# ---------------------------------------------------------------------
def test_detect_autosaves_artifacts_yml(main_window):
    """After clicking Detect, the {pid}_artifacts.yml file lands on disk."""
    from rrational.gui.persistence import load_artifact_corrections

    p = _exists_or_skip("data/demo/empatica/IBI_stress_predict_S10.csv")
    main_window.open_path(p)
    panel = main_window._browse_tab._preprocessing_panel
    panel._on_detect_clicked()

    # pid = filename stem
    pid = Path(p).stem
    loaded = load_artifact_corrections(pid, section_key="_full")
    assert loaded is not None
    # Algorithm-detected indices should be populated (NK2 found at least one)
    assert isinstance(loaded.get("algorithm_artifact_indices"), list)
    # method label matches what we wrote
    assert loaded.get("algorithm_method") == "lipponen2019"


def test_detect_autosave_does_not_crash_on_yaml_unfriendly_types(main_window):
    """NeuroKit2 returns numpy.int64; persisting must convert to native int."""
    p = _exists_or_skip("data/demo/empatica/IBI_stress_predict_S10.csv")
    main_window.open_path(p)
    panel = main_window._browse_tab._preprocessing_panel
    panel._on_detect_clicked()

    # Re-loading should NOT raise yaml.constructor.ConstructorError
    from rrational.gui.persistence import load_artifact_corrections

    pid = Path(p).stem
    loaded = load_artifact_corrections(pid, section_key="_full")
    assert loaded is not None
    # Every index in the list must be a plain Python int
    for idx in loaded.get("algorithm_artifact_indices", []):
        assert type(idx) is int


# ---------------------------------------------------------------------
# Auto-restore on dataset switch
# ---------------------------------------------------------------------
def test_restore_artifacts_on_reopen(main_window, qtbot):
    """After closing and reopening the same recording, _last_result is
    restored from disk without the user having to click Detect again."""
    p = _exists_or_skip("data/demo/empatica/IBI_stress_predict_S10.csv")
    main_window.open_path(p)
    panel = main_window._browse_tab._preprocessing_panel
    panel._on_detect_clicked()
    detected_total = panel._last_result.total
    assert detected_total >= 0  # at minimum NK2 ran

    main_window.close_all_datasets()
    assert panel._last_result is None

    main_window.open_path(p)
    # After reopen, _last_result should be populated from disk
    if detected_total == 0:
        # Nothing was detected → no auto-restore expected
        return
    assert panel._last_result is not None
    assert panel._last_result.total == detected_total


def test_restore_artifacts_renders_overlay(main_window, qtbot):
    """When auto-restoring, the plot overlay must show the artifact dots."""
    p = _exists_or_skip("data/demo/empatica/IBI_stress_predict_S10.csv")
    main_window.open_path(p)
    panel = main_window._browse_tab._preprocessing_panel
    panel._on_detect_clicked()
    if panel._last_result.total == 0:
        pytest.skip("Nothing detected — overlay test needs at least 1 artifact")
    detected_total = panel._last_result.total

    main_window.close_all_datasets()
    main_window.open_path(p)

    overlay = main_window._browse_tab._plot._artifact_overlay
    overlay_x, _ = overlay.getData()
    assert len(overlay_x) == detected_total


def test_restore_only_when_pid_matches(main_window, qtbot):
    """A different dataset shouldn't inherit another's artifacts."""
    p = _exists_or_skip("data/demo/empatica/IBI_stress_predict_S10.csv")
    main_window.open_path(p)
    panel = main_window._browse_tab._preprocessing_panel
    panel._on_detect_clicked()

    main_window.close_all_datasets()

    # Open a synthetic dataset with a DIFFERENT name
    from rrational.inspector.data_loader import (
        Dataset,
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    n = 300
    t = (
        1_700_000_000
        + np.cumsum(800 + 30 * np.random.default_rng(0).standard_normal(n)) / 1000
    )
    data = InspectorData(
        t=t,
        v=np.full(n, 800.0),
        sections=[
            SectionMeta(name="s", t_start=float(t[0]), t_end=float(t[-1]), beat_count=n)
        ],
        events=[EventMeta(label="ev", t=float(t[0]))],
    )
    main_window.add_dataset(Dataset(name="UNRELATED.csv", data=data))
    main_window.set_active_dataset(0)

    # No restore: unrelated pid has no cached file
    assert panel._last_result is None


def test_restore_silent_when_no_file_exists(main_window):
    """First-time load with no cached file leaves _last_result=None."""
    p = _exists_or_skip("data/demo/empatica/IBI_stress_predict_S10.csv")
    main_window.open_path(p)
    panel = main_window._browse_tab._preprocessing_panel
    # We haven't called detect yet → _last_result stays None
    assert panel._last_result is None


# ---------------------------------------------------------------------
# Project-aware routing
# ---------------------------------------------------------------------
def test_artifacts_persist_in_project_processed_folder(main_window, tmp_path):
    """When a project is open, artifacts.yml lives in
    project/data/processed/ — same as Streamlit."""
    from rrational.gui.project import ProjectManager

    pm = ProjectManager.create_project(tmp_path / "Proj", name="Proj")
    main_window.set_active_project(pm)

    p = _exists_or_skip("data/demo/empatica/IBI_stress_predict_S10.csv")
    main_window.open_path(p)
    panel = main_window._browse_tab._preprocessing_panel
    panel._on_detect_clicked()

    pid = Path(p).stem
    expected = pm.project_path / "data" / "processed" / f"{pid}_artifacts.yml"
    assert expected.exists()
