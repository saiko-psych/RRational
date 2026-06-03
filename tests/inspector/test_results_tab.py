"""Tests for the Results tab + ResultsStore (Phase 4e)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path):
    from rrational.inspector import persistence, settings

    settings.enable_test_mode(tmp_path)
    persistence.set_inspector_config_dir(tmp_path)
    yield
    persistence.set_inspector_config_dir(None)


def _make_data(section_names: list[str], beats_per_section: int = 250):
    from rrational.inspector.data_loader import (
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    base = 1_700_000_000
    n = beats_per_section * len(section_names)
    rng = np.random.default_rng(seed=7)
    rr_ms = 800 + 30 * rng.standard_normal(n)
    t = base + np.cumsum(rr_ms) / 1000.0

    sections = []
    events = []
    for i, name in enumerate(section_names):
        start_idx = i * beats_per_section
        end_idx = (i + 1) * beats_per_section - 1
        sections.append(
            SectionMeta(
                name=name,
                t_start=float(t[start_idx]),
                t_end=float(t[end_idx]),
                beat_count=beats_per_section,
            )
        )
        events.append(EventMeta(label=f"{name}_start", t=float(t[start_idx])))
    return InspectorData(t=t, v=rr_ms, sections=sections, events=events)


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
# ResultsStore (pure data, no UI)
# ---------------------------------------------------------------------
def test_results_store_starts_empty(main_window):
    store = main_window._results_store
    assert store.metric_rows == []
    assert store.group_test_rows == []


def test_results_store_add_and_clear():
    from rrational.inspector.results_store import (
        GroupTestRow,
        MetricRow,
        ResultsStore,
    )

    s = ResultsStore()
    s.add_metric_row(
        MetricRow(
            mode="single",
            dataset="A",
            section="rest",
            n_beats=100,
            metrics={"RMSSD": 42.0},
        )
    )
    s.add_group_test_row(
        GroupTestRow(
            section="rest",
            metric="RMSSD",
            test_name="Welch t",
            statistic=1.5,
            p_value=0.04,
            effect_size_name="Cohen's d",
            effect_size=0.8,
            is_parametric=True,
            groups=("A", "B"),
            n_per_group={"A": 5, "B": 5},
        )
    )
    assert len(s.metric_rows) == 1
    assert len(s.group_test_rows) == 1
    s.clear()
    assert s.metric_rows == []
    assert s.group_test_rows == []


# ---------------------------------------------------------------------
# Results tab shell
# ---------------------------------------------------------------------
def test_results_tab_has_three_subtabs(main_window):
    results = main_window._results_tab
    titles = [results._subtabs.tabText(i) for i in range(results._subtabs.count())]
    assert titles == ["HRV metrics", "Group tests", "Sequence tests"]


def test_export_button_disabled_when_empty(main_window):
    results = main_window._results_tab
    assert results._export_metrics_btn.isEnabled() is False
    assert results._export_group_btn.isEnabled() is False


# ---------------------------------------------------------------------
# Single compute → metric row
# ---------------------------------------------------------------------
def test_single_compute_appends_metric_row(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(["rest"])))
    main_window.set_active_dataset(0)

    pane = main_window._analysis_tab._single_pane
    pane._on_compute()

    store = main_window._results_store
    assert len(store.metric_rows) == 1
    row = store.metric_rows[0]
    assert row.mode == "single"
    assert row.dataset == "A"
    assert row.section == "rest"
    assert row.n_beats > 0
    assert "RMSSD" in row.metrics

    # Results tab should now show one row + enabled export
    results = main_window._results_tab
    assert results._metrics_table.rowCount() == 1
    assert results._export_metrics_btn.isEnabled() is True


# ---------------------------------------------------------------------
# Repeating compute → one row per matching dataset
# ---------------------------------------------------------------------
def test_repeating_compute_appends_one_row_per_dataset(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(["rest", "a_only"])))
    main_window.add_dataset(Dataset(name="B", data=_make_data(["rest"])))
    main_window.add_dataset(Dataset(name="C", data=_make_data(["other"])))
    main_window.set_active_dataset(0)

    pane = main_window._analysis_tab._repeating_pane
    pane._section_combo.setCurrentIndex(pane._section_combo.findText("rest"))
    pane._on_compute()

    store = main_window._results_store
    # A + B have "rest", C doesn't → 2 rows
    assert len(store.metric_rows) == 2
    assert {r.dataset for r in store.metric_rows} == {"A", "B"}
    assert all(r.mode == "repeating" for r in store.metric_rows)

    results = main_window._results_tab
    assert results._metrics_table.rowCount() == 2


# ---------------------------------------------------------------------
# Group compute → group test row
# ---------------------------------------------------------------------
def test_group_compute_appends_group_test_row(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A1", data=_make_data(["rest"])))
    main_window.add_dataset(Dataset(name="A2", data=_make_data(["rest"])))
    main_window.add_dataset(Dataset(name="B1", data=_make_data(["rest"])))
    main_window.add_dataset(Dataset(name="B2", data=_make_data(["rest"])))
    main_window.set_active_dataset(0)

    pane = main_window._analysis_tab._group_pane
    pane._group_by_idx = {0: "ctrl", 1: "ctrl", 2: "music", 3: "music"}
    pane._refresh_compute_enabled()
    pane._section_combo.setCurrentIndex(pane._section_combo.findText("rest"))
    pane._metric_combo.setCurrentIndex(pane._metric_combo.findText("RMSSD"))
    pane._on_compute()

    store = main_window._results_store
    assert len(store.group_test_rows) == 1
    row = store.group_test_rows[0]
    assert row.section == "rest"
    assert row.metric == "RMSSD"
    assert set(row.groups) == {"ctrl", "music"}
    assert row.n_per_group["ctrl"] == 2
    assert row.n_per_group["music"] == 2

    results = main_window._results_tab
    assert results._group_tests_table.rowCount() == 1
    assert results._export_group_btn.isEnabled() is True


# ---------------------------------------------------------------------
# Clear buttons
# ---------------------------------------------------------------------
def test_clear_button_wipes_metrics_pane(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_data(["rest"])))
    main_window.set_active_dataset(0)
    main_window._analysis_tab._single_pane._on_compute()

    results = main_window._results_tab
    assert results._metrics_table.rowCount() == 1

    results._metrics_pane._on_clear()
    assert results._metrics_table.rowCount() == 0
    assert main_window._results_store.metric_rows == []
    assert results._export_metrics_btn.isEnabled() is False


# ---------------------------------------------------------------------
# Numeric sorting (the _NumericItem invariant)
# ---------------------------------------------------------------------
def test_metric_column_sorts_numerically_not_lexically(main_window):
    """Beats column should sort 100 < 1000, not 1000 < 100 ('1' < '2')."""
    from rrational.inspector.results_store import MetricRow

    store = main_window._results_store
    # Same beat count differ — pick 100 vs 1000 (lex-sort would put 1000 first)
    for n in [1000, 100, 500]:
        store.add_metric_row(
            MetricRow(
                mode="single",
                dataset=f"d{n}",
                section="x",
                n_beats=n,
                metrics={"RMSSD": float(n)},
            )
        )
    results = main_window._results_tab
    results.refresh_results()
    table = results._metrics_table

    from qtpy.QtCore import Qt

    table.sortItems(3, Qt.AscendingOrder)
    sorted_beats = [int(table.item(i, 3).text()) for i in range(table.rowCount())]
    assert sorted_beats == [100, 500, 1000]


# ---------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------
def test_csv_export_writes_header_and_rows(main_window, tmp_path, monkeypatch):
    """Patch the file-dialog so the export goes to a known path; verify content."""
    from rrational.inspector.data_loader import Dataset
    from rrational.inspector.tabs import results_tab as rt

    main_window.add_dataset(Dataset(name="A", data=_make_data(["rest"])))
    main_window.set_active_dataset(0)
    main_window._analysis_tab._single_pane._on_compute()

    out_path = tmp_path / "out.csv"
    monkeypatch.setattr(rt, "_ask_csv_path", lambda *args, **kwargs: out_path)

    main_window._results_tab._metrics_pane._on_export()

    assert out_path.exists()
    text = out_path.read_text(encoding="utf-8")
    # Header
    assert "Mode" in text and "Dataset" in text and "RMSSD" in text
    # The data row
    assert "single" in text
    assert "A" in text
    assert "rest" in text
