"""Integration tests for the File -> Save recipe... feature.

Verifies:
- ``MainWindow.history`` exists and starts empty.
- ``open_path`` pushes a ``LoadRecording`` action.
- ``set_active_project`` pushes an ``OpenProject`` action.
- The PreprocessingPanel records ``DetectArtifacts`` /
  ``SaveRRationalExport``.
- ``_on_save_recipe_clicked`` writes a file whose contents parse as
  valid Python and contain the expected recipe entries.
"""

from __future__ import annotations

import ast
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path, monkeypatch):
    """Mirror the test_batch_preprocess isolation pattern."""
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
    settings.write_setting("last_dir", str(tmp_path))
    yield
    inspector_persistence.set_inspector_config_dir(None)


def _synthetic_dataset(name: str = "synth.csv", n: int = 200):
    """Build an in-memory Dataset with ``n`` mostly-clean beats."""
    from rrational.inspector.data_loader import (
        Dataset,
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    rng = np.random.default_rng(42)
    base = 1_700_000_000
    t = base + np.cumsum(np.full(n, 0.8))  # ~80 bpm
    v = 800 + 20 * rng.standard_normal(n)
    # A handful of clear artifacts so detect_artifacts has work to do.
    for idx in (n // 4, n // 2):
        if 0 <= idx < n:
            v[idx] = 200.0
    data = InspectorData(
        t=t,
        v=v,
        sections=[
            SectionMeta(
                name="full",
                t_start=float(t[0]),
                t_end=float(t[-1]),
                beat_count=n,
            )
        ],
        events=[EventMeta(label="start", t=float(t[0]))],
    )
    return Dataset(name=name, data=data, path=Path(f"/tmp/{name}"))


def _add_synth_via_open_path(
    main_window, tmp_path: Path, monkeypatch, name: str = "synth.csv"
) -> Path:
    """Inject a synthetic dataset AND fire the recipe-recording hook.

    ``open_path`` reads from disk via ``Dataset.from_path`` (which needs
    a real parseable file) AND it checks ``path.exists()`` first. The
    tests touch a dummy file at ``tmp_path`` so the existence-check
    passes, and monkeypatch ``Dataset.from_path`` to return a synthetic
    in-memory Dataset — that way the full ``open_path`` code path runs
    end-to-end and the LoadRecording hook fires.
    """
    from rrational.inspector import main_window as _mw

    ds = _synthetic_dataset(name)
    target = tmp_path / name
    target.write_text("placeholder", encoding="utf-8")

    def _fake_from_path(path):
        ds.path = Path(path)
        ds.name = Path(path).name
        return ds

    class _Patched:
        @classmethod
        def from_path(cls, path):
            return _fake_from_path(path)

    monkeypatch.setattr(_mw, "Dataset", _Patched)
    main_window.open_path(target)
    return target


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    win.set_ui_layout("mnelab")
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


# ---------------------------------------------------------------------
# MainWindow.history bootstrap
# ---------------------------------------------------------------------
def test_mainwindow_has_empty_history_on_construction(main_window):
    from rrational.inspector.history import HistoryRecorder

    assert isinstance(main_window.history, HistoryRecorder)
    assert len(main_window.history) == 0


def test_file_menu_has_save_recipe_action(main_window):
    assert hasattr(main_window, "_save_recipe_act")
    assert "recipe" in main_window._save_recipe_act.text().lower()


# ---------------------------------------------------------------------
# Action recording on the high-traffic hook sites
# ---------------------------------------------------------------------
def test_open_path_records_load_recording_action(main_window, tmp_path, monkeypatch):
    from rrational.inspector.history import LoadRecording

    target = _add_synth_via_open_path(
        main_window, tmp_path, monkeypatch, name="rec1.csv"
    )
    loads = [a for a in main_window.history if isinstance(a, LoadRecording)]
    assert len(loads) == 1
    assert loads[0].path == str(target)


def test_open_path_failure_does_not_record(main_window, tmp_path):
    """open_path bails when the file is missing — no recipe entry."""
    main_window.open_path(tmp_path / "does_not_exist.csv")
    assert len(main_window.history) == 0


def test_set_active_project_records_open_project_action(main_window, tmp_path):
    """ProjectManager-based open emits a single OpenProject entry."""
    from rrational.gui.project import ProjectManager
    from rrational.inspector.history import OpenProject

    proj_root = tmp_path / "demo_project"
    pm = ProjectManager.create_project(
        proj_root, name="Demo", description="recipe test"
    )
    main_window.set_active_project(pm)
    opens = [a for a in main_window.history if isinstance(a, OpenProject)]
    assert len(opens) == 1
    assert opens[0].path == str(pm.project_path)


def test_detect_records_detect_artifacts(main_window, tmp_path, monkeypatch):
    """Clicking Detect on a loaded dataset pushes a DetectArtifacts entry."""
    from rrational.inspector.history import DetectArtifacts

    _add_synth_via_open_path(main_window, tmp_path, monkeypatch, name="detect_me.csv")
    panel = main_window._browse_tab._preprocessing_panel
    panel._on_detect_clicked()
    detects = [a for a in main_window.history if isinstance(a, DetectArtifacts)]
    assert len(detects) == 1
    assert detects[0].method == "lipponen2019"


def test_export_records_save_rrational_export(main_window, tmp_path, monkeypatch):
    """Saving a .rrational via the panel pushes a SaveRRationalExport."""
    from rrational.inspector.history import SaveRRationalExport

    _add_synth_via_open_path(main_window, tmp_path, monkeypatch, name="exportme.csv")
    panel = main_window._browse_tab._preprocessing_panel
    # test_mode short-circuits the QInputDialog / QFileDialog prompts so
    # the export runs end-to-end into ``settings.last_dir`` (=tmp_path).
    panel._on_export_clicked()
    saves = [a for a in main_window.history if isinstance(a, SaveRRationalExport)]
    assert len(saves) == 1
    assert saves[0].pid == "exportme"
    assert saves[0].out_path.endswith("exportme.rrational")
    assert saves[0].n_beats > 0


# ---------------------------------------------------------------------
# _on_save_recipe_clicked end-to-end
# ---------------------------------------------------------------------
def test_save_recipe_writes_runnable_script(main_window, tmp_path, monkeypatch):
    """The on-disk recipe is valid Python and references each recorded
    action."""
    _add_synth_via_open_path(
        main_window, tmp_path, monkeypatch, name="recipe_target.csv"
    )
    panel = main_window._browse_tab._preprocessing_panel
    panel._on_detect_clicked()

    # test_mode → no QFileDialog; defaults to <report_default_dir>/rrational_recipe.py.
    main_window._on_save_recipe_clicked()

    recipe = main_window._report_default_dir() / "rrational_recipe.py"
    assert recipe.exists(), f"recipe missing: {recipe}"
    src = recipe.read_text(encoding="utf-8")
    ast.parse(src)
    assert "recipe_target.csv" in src
    assert "clean_rr_intervals" in src


def test_save_recipe_with_empty_history_still_writes(main_window):
    """No actions yet → still writes a placeholder-comment script."""
    main_window._on_save_recipe_clicked()
    recipe = main_window._report_default_dir() / "rrational_recipe.py"
    assert recipe.exists()
    src = recipe.read_text(encoding="utf-8")
    assert "No actions recorded" in src
    ast.parse(src)
