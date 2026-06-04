"""Tests for Phase 13 — results cache persistence + autosave/autoload."""

from __future__ import annotations

import math

import numpy as np
import pytest

from rrational.inspector.results_persistence import (
    INSPECTOR_RESULTS_FILENAME,
    _resolve_path,
    clear_results,
    load_results,
    save_results,
)
from rrational.inspector.results_store import (
    GroupTestRow,
    MetricRow,
    ResultsStore,
    SequenceTestRow,
)

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
    # Redirect the GLOBAL fallback path so an empty project_path lands
    # under tmp_path instead of the user's real home.
    monkeypatch.setattr(rp, "_DEFAULT_DIR", tmp_path / "inspector_global")
    yield
    inspector_persistence.set_inspector_config_dir(None)


# ---------------------------------------------------------------------
# Pure persistence (no UI)
# ---------------------------------------------------------------------
def test_save_then_load_roundtrips_all_three_row_types():
    store = ResultsStore()
    store.add_metric_row(
        MetricRow(
            mode="single",
            dataset="A",
            section="rest",
            n_beats=300,
            metrics={"RMSSD": 42.5, "SDNN": 80.1},
        )
    )
    store.add_group_test_row(
        GroupTestRow(
            section="rest",
            metric="RMSSD",
            test_name="Welch t",
            statistic=2.1,
            p_value=0.04,
            effect_size_name="Cohen's d",
            effect_size=0.8,
            is_parametric=True,
            groups=("A", "B"),
            n_per_group={"A": 5, "B": 5},
        )
    )
    store.add_sequence_test_row(
        SequenceTestRow(
            sequence_name="protocol",
            metric="RMSSD",
            sections=("pre", "stim", "post"),
            n_complete_subjects=4,
            test_name="Friedman",
            statistic=6.5,
            p_value=0.04,
            effect_size_name="Kendall's W",
            effect_size=0.45,
            is_parametric=False,
        )
    )

    out = save_results(store)
    assert out.name == INSPECTOR_RESULTS_FILENAME

    loaded = load_results()
    assert len(loaded.metric_rows) == 1
    assert loaded.metric_rows[0].metrics["RMSSD"] == 42.5
    assert len(loaded.group_test_rows) == 1
    assert loaded.group_test_rows[0].test_name == "Welch t"
    assert loaded.group_test_rows[0].groups == ("A", "B")
    assert len(loaded.sequence_test_rows) == 1
    assert loaded.sequence_test_rows[0].sequence_name == "protocol"
    assert loaded.sequence_test_rows[0].sections == ("pre", "stim", "post")


def test_load_returns_empty_store_when_file_missing():
    loaded = load_results()
    assert loaded.metric_rows == []
    assert loaded.group_test_rows == []
    assert loaded.sequence_test_rows == []


def test_clear_results_removes_file():
    store = ResultsStore()
    store.add_metric_row(
        MetricRow(mode="single", dataset="A", section="s", n_beats=100, metrics={})
    )
    save_results(store)
    assert _resolve_path(None).exists()
    assert clear_results() is True
    assert not _resolve_path(None).exists()
    # Second clear: no-op, returns False
    assert clear_results() is False


def test_nan_values_round_trip_as_none():
    """YAML can't represent NaN; the loader has to tolerate the conversion."""
    store = ResultsStore()
    store.add_group_test_row(
        GroupTestRow(
            section="rest",
            metric="RMSSD",
            test_name="t",
            statistic=float("nan"),
            p_value=float("nan"),
            effect_size_name=None,
            effect_size=None,
            is_parametric=False,
            groups=("A", "B"),
            n_per_group={"A": 1, "B": 1},
        )
    )
    save_results(store)
    loaded = load_results()
    assert math.isnan(loaded.group_test_rows[0].statistic)
    assert math.isnan(loaded.group_test_rows[0].p_value)


def test_load_survives_corrupted_yaml(tmp_path):
    """Garbled YAML must NEVER raise — corrupted cache shouldn't brick the app."""
    target = _resolve_path(None)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("this is :: not :: yaml", encoding="utf-8")
    store = load_results()
    assert isinstance(store, ResultsStore)
    assert store.metric_rows == []


# ---------------------------------------------------------------------
# Project-scope routing
# ---------------------------------------------------------------------
def test_project_path_routes_to_data_processed(tmp_path):
    from rrational.gui.project import ProjectManager

    pm = ProjectManager.create_project(tmp_path / "Proj", name="Proj")
    store = ResultsStore()
    store.add_metric_row(
        MetricRow(mode="single", dataset="A", section="s", n_beats=10, metrics={})
    )
    out = save_results(store, project_path=pm.project_path)
    expected = pm.project_path / "data" / "processed" / INSPECTOR_RESULTS_FILENAME
    assert out == expected
    assert expected.exists()


# ---------------------------------------------------------------------
# MainWindow auto-load + auto-save integration
# ---------------------------------------------------------------------
@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


def _make_data(section_names: list[str], beats_per_section: int = 250):
    from rrational.inspector.data_loader import (
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    base = 1_700_000_000
    n = beats_per_section * len(section_names)
    rng = np.random.default_rng(seed=11)
    rr_ms = 800 + 30 * rng.standard_normal(n)
    t = base + np.cumsum(rr_ms) / 1000.0
    sections = []
    events = []
    for i, name in enumerate(section_names):
        s = i * beats_per_section
        e = (i + 1) * beats_per_section - 1
        sections.append(
            SectionMeta(
                name=name,
                t_start=float(t[s]),
                t_end=float(t[e]),
                beat_count=beats_per_section,
            )
        )
        events.append(EventMeta(label=f"{name}_start", t=float(t[s])))
    return InspectorData(t=t, v=rr_ms, sections=sections, events=events)


def test_compute_autosaves_to_disk(main_window):
    """A successful Single-Participant compute writes inspector_results.yml.

    Catches a regression: numpy.float64 from NK2's HRV computation must
    survive YAML serialization via _sanitize → Python-native conversion.
    """
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(["rest"])))
    main_window.set_active_dataset(0)
    main_window._analysis_tab._single_pane._on_compute()

    assert len(main_window._results_store.metric_rows) >= 1
    assert _resolve_path(None).exists()
    loaded = load_results()
    assert len(loaded.metric_rows) >= 1
    assert loaded.metric_rows[0].dataset == "A"


def test_open_project_autoloads_prior_results(main_window, qtbot, tmp_path):
    """When a project has a cached inspector_results.yml, opening it
    populates the in-memory store."""
    from rrational.gui.project import ProjectManager

    pm = ProjectManager.create_project(tmp_path / "Cached", name="Cached")
    pre_store = ResultsStore()
    pre_store.add_metric_row(
        MetricRow(
            mode="repeating",
            dataset="legacy",
            section="rest_pre",
            n_beats=200,
            metrics={"RMSSD": 55.0},
        )
    )
    save_results(pre_store, project_path=pm.project_path)

    main_window.set_active_project(pm)
    assert len(main_window._results_store.metric_rows) == 1
    assert main_window._results_store.metric_rows[0].dataset == "legacy"


def test_clear_cache_button_wipes_in_memory_and_disk(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(["rest"])))
    main_window.set_active_dataset(0)
    main_window._analysis_tab._single_pane._on_compute()
    assert _resolve_path(None).exists()
    assert len(main_window._results_store.metric_rows) >= 1

    # Trigger via the public method (what the Results-tab button calls)
    removed = main_window.clear_results_cache()
    assert removed is True
    assert not _resolve_path(None).exists()
    assert main_window._results_store.metric_rows == []


def test_reload_from_disk_replaces_in_memory_store(main_window, tmp_path):
    """Pre-write a cache file, then reload — in-memory must match disk."""
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(["rest"])))
    main_window.set_active_dataset(0)

    # Stash a pre-built store on disk; verify in-memory is empty first
    assert len(main_window._results_store.metric_rows) == 0
    pre_store = ResultsStore()
    pre_store.add_metric_row(
        MetricRow(
            mode="single",
            dataset="from_disk",
            section="rest",
            n_beats=42,
            metrics={"RMSSD": 99.9},
        )
    )
    save_results(pre_store)

    main_window._load_results_cache()
    assert len(main_window._results_store.metric_rows) == 1
    assert main_window._results_store.metric_rows[0].dataset == "from_disk"


def test_results_tab_has_cache_toolbar_buttons(main_window):
    """Phase 13 added a cache toolbar to the Results tab."""
    tab = main_window._results_tab
    assert hasattr(tab, "_save_now_btn")
    assert hasattr(tab, "_reload_btn")
    assert hasattr(tab, "_clear_cache_btn")
    assert tab._save_now_btn.isEnabled() is True
    assert tab._reload_btn.isEnabled() is True
    assert tab._clear_cache_btn.isEnabled() is True
