"""Tests for batch-apply preprocessing across multiple loaded datasets.

Covers:
- ``PreprocessingPanel.apply_to_recordings`` returns one BatchResult per ds
- ``process_single`` is robust to empty / degenerate datasets
- ``MainWindow._on_batch_preprocess_clicked`` populates the triage dialog
- The Tools menu actions are wired up
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path, monkeypatch):
    """Same isolation pattern as test_manual_artifacts to keep on-disk
    persistence out of the developer's real ~/.rrational/."""
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
    # Route .rrational exports into tmp_path too (export path falls back
    # to settings.last_dir when no project is open).
    settings.write_setting("last_dir", str(tmp_path))
    yield
    inspector_persistence.set_inspector_config_dir(None)


def _synthetic_dataset(name: str, n: int = 200, seed: int = 42):
    """Build an InspectorData with ``n`` mostly-clean beats + one big spike."""
    from rrational.inspector.data_loader import (
        Dataset,
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    rng = np.random.default_rng(seed)
    base = 1_700_000_000
    t = base + np.cumsum(np.full(n, 0.8))  # ~80 bpm
    v = 800 + 20 * rng.standard_normal(n)
    # Inject a couple of clear artifacts so the detector has work to do.
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
    return Dataset(name=name, data=data, path=None)


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
# PreprocessingPanel.apply_to_recordings + process_single
# ---------------------------------------------------------------------
def test_apply_to_recordings_processes_all_and_returns_per_ds_result(main_window):
    """Three synthetic datasets → three BatchResult rows with finite grades."""
    from rrational.inspector.quality_triage_dialog import BatchResult

    datasets = [
        _synthetic_dataset("a.csv", seed=1),
        _synthetic_dataset("b.csv", seed=2),
        _synthetic_dataset("c.csv", seed=3),
    ]
    panel = main_window._browse_tab._preprocessing_panel
    results = panel.apply_to_recordings(datasets, save_export=False)

    assert len(results) == 3
    for r, ds in zip(results, datasets, strict=True):
        assert isinstance(r, BatchResult)
        assert r.name == ds.name
        assert r.n_beats == len(ds.data.v)
        # Grade is one of the Quigley letters.
        assert r.grade in ("A", "B", "C", "D", "?")
        # Rate is a finite fraction.
        assert 0.0 <= r.artifact_rate <= 1.0
        assert r.n_artifacts >= 0
        # save_export=False → no on-disk write.
        assert r.saved_path is None


def test_apply_to_recordings_invokes_progress_callback(main_window):
    """progress_cb fires once per dataset, in order."""
    datasets = [
        _synthetic_dataset("p1.csv", seed=10),
        _synthetic_dataset("p2.csv", seed=11),
    ]
    panel = main_window._browse_tab._preprocessing_panel
    calls: list[tuple[int, int, str]] = []
    panel.apply_to_recordings(
        datasets,
        progress_cb=lambda i, total, name: calls.append((i, total, name)),
        save_export=False,
    )
    assert calls == [(0, 2, "p1.csv"), (1, 2, "p2.csv")]


def test_process_single_handles_empty_dataset(main_window):
    """A zero-length dataset → BatchResult with grade '?' (no crash)."""
    from rrational.inspector.data_loader import (
        Dataset,
        InspectorData,
    )

    empty = Dataset(
        name="empty.csv",
        data=InspectorData(
            t=np.array([], dtype=np.float64),
            v=np.array([], dtype=np.float64),
        ),
        path=None,
    )
    panel = main_window._browse_tab._preprocessing_panel
    r = panel.process_single(empty, save_export=False)
    assert r.name == "empty.csv"
    assert r.n_beats == 0
    assert r.grade == "?"
    assert r.artifact_rate == 0.0


def test_process_single_with_export_writes_rrational_file(main_window, tmp_path):
    """save_export=True → BatchResult.saved_path points at a real .rrational."""
    from rrational.gui.rrational_export import load_rrational_v2

    ds = _synthetic_dataset("saveme.csv", seed=99)
    panel = main_window._browse_tab._preprocessing_panel
    r = panel.process_single(ds, save_export=True)
    assert r.saved_path is not None
    from pathlib import Path

    out = Path(r.saved_path)
    assert out.exists()
    loaded = load_rrational_v2(out)
    # source_app is whatever the export layer writes — assert it just
    # contains "RRational" so this test isn't brittle to the export
    # banner being renamed.
    assert "RRational" in loaded.metadata.source_app


# ---------------------------------------------------------------------
# MainWindow integration: Tools menu entries + triage dialog
# ---------------------------------------------------------------------
def test_tools_menu_has_batch_and_triage_actions(main_window):
    assert hasattr(main_window, "_batch_preprocess_act")
    assert hasattr(main_window, "_quality_triage_act")
    assert main_window._batch_preprocess_act.text().startswith(
        "Run preprocessing on all loaded recordings"
    )
    assert main_window._quality_triage_act.text().startswith("Quality triage")


def test_batch_preprocess_with_no_datasets_is_a_noop(main_window):
    """No datasets loaded → status-bar message, no dialog."""
    main_window._on_batch_preprocess_clicked()
    assert "no datasets loaded" in main_window.statusBar().currentMessage().lower()


def test_batch_preprocess_populates_quality_triage_dialog(main_window):
    """End-to-end: add 3 synthetic datasets, click batch, verify dialog state."""
    for ds in (
        _synthetic_dataset("e1.csv", seed=7),
        _synthetic_dataset("e2.csv", seed=8),
        _synthetic_dataset("e3.csv", seed=9),
    ):
        main_window.add_dataset(ds)
    # Pre-activate the first so on_active_dataset_changed fires once.
    main_window.set_active_dataset(0)

    main_window._on_batch_preprocess_clicked()
    dlg = getattr(main_window, "_latest_triage_dialog", None)
    assert dlg is not None
    # Three rows, six columns.
    assert dlg._table.rowCount() == 3
    assert dlg._table.columnCount() == 6
    # Each row's "Name" cell matches one of the loaded datasets.
    names_in_table = {dlg._table.item(i, 0).text() for i in range(3)}
    assert names_in_table == {"e1.csv", "e2.csv", "e3.csv"}


def test_quality_triage_action_skips_save_export(main_window, tmp_path):
    """Tools → Quality triage must NOT write .rrational files (recompute only)."""
    from pathlib import Path

    main_window.add_dataset(_synthetic_dataset("triage_only.csv", seed=12))
    main_window.set_active_dataset(0)
    # Sanity: tmp_path starts empty of .rrational files.
    before = list(Path(tmp_path).glob("*.rrational"))
    main_window._on_quality_triage_clicked()
    after = list(Path(tmp_path).glob("*.rrational"))
    assert before == after  # no new exports
    # But a dialog WAS built.
    dlg = getattr(main_window, "_latest_triage_dialog", None)
    assert dlg is not None
    assert dlg._table.rowCount() == 1


def test_quality_triage_dialog_activate_dataset_round_trip(main_window):
    """Emitting open_recording activates the matching dataset by name."""
    main_window.add_dataset(_synthetic_dataset("first.csv", seed=5))
    main_window.add_dataset(_synthetic_dataset("second.csv", seed=6))
    main_window.set_active_dataset(0)
    main_window._on_quality_triage_clicked()
    dlg = main_window._latest_triage_dialog
    dlg.open_recording.emit("second.csv")
    assert main_window._datasets[main_window._active_idx].name == "second.csv"
