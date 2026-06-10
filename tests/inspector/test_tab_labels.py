"""Round 16 / Sprint 4 — unified tab-counter format.

Every top-level tab speaks the same dialect:

    Tab          -> n == 0  -> "" (no suffix)
    Tab (N)      -> n  > 0  -> "(N)"

The Setup tab sums groups + sequences into a single integer; Results
sums metric + group + sequence test rows. Browse + Analysis use the
loaded-dataset count. DataTab (Streamlit-mode) sums participants +
loaded datasets. ParticipantTab is contextual (active subject ID) so
it stays out of this contract.
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path, monkeypatch):
    from rrational.gui import persistence as gui_persistence
    from rrational.inspector import persistence, settings

    settings.enable_test_mode(tmp_path)
    persistence.set_inspector_config_dir(tmp_path)
    monkeypatch.setattr(gui_persistence, "CONFIG_DIR", tmp_path / "gui_config")
    monkeypatch.setattr(
        gui_persistence, "SETTINGS_FILE", tmp_path / "gui_config" / "settings.yml"
    )
    yield
    persistence.set_inspector_config_dir(None)


def _make_data():
    from rrational.inspector.data_loader import InspectorData

    base = 1_700_000_000
    t = base + np.arange(120, dtype=np.float64)
    v = 800 + 25 * np.sin(np.linspace(0, np.pi, 120))
    return InspectorData(t=t, v=v)


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


def test_browse_tab_label_empty_workspace(main_window):
    """No datasets -> empty suffix (was ``(empty)`` pre-R16)."""
    assert main_window._browse_tab.tab_label_state() == ""


def test_browse_tab_label_with_datasets(main_window):
    from rrational.inspector.data_loader import Dataset

    for n in ("a.csv", "b.csv", "c.csv"):
        main_window.add_dataset(Dataset(name=n, data=_make_data()))
    assert main_window._browse_tab.tab_label_state() == "(3)"


def test_analysis_tab_label_drops_loaded_suffix(main_window):
    """Pre-R16 returned ``(1 loaded)``; now plain ``(1)``."""
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="a.csv", data=_make_data()))
    assert main_window._analysis_tab.tab_label_state() == "(1)"


def test_analysis_tab_label_empty(main_window):
    assert main_window._analysis_tab.tab_label_state() == ""


def test_setup_tab_label_sums_groups_and_sequences(main_window):
    """Round 16 — single integer instead of ``(N groups, M seqs)``."""
    setup = main_window._setup_tab
    # Empty state.
    assert setup.tab_label_state() == ""
    # Inject directly into the pane state to avoid round-tripping
    # through the persistence layer.
    setup._groups_pane._groups = {"G1": {}, "G2": {}, "G3": {}}
    setup._sequences_pane._sequences = [object(), object()]
    assert setup.tab_label_state() == "(5)"


def test_participants_tab_label_uses_unified_format(main_window):
    """Participants tab already used ``(N)`` -- regression guard."""
    pt = main_window._participants_tab
    assert pt.tab_label_state() == ""
    pt._participants = {"S001": {}, "S002": {}}
    assert pt.tab_label_state() == "(2)"


def test_results_tab_label_sums_all_result_rows(main_window):
    """Round 16 — Results carries a unified integer counter too."""
    rt = main_window._results_tab
    assert rt.tab_label_state() == ""
    # Push fake rows into the store directly.
    store = main_window._results_store
    store.metric_rows.append({"id": "m1"})
    store.metric_rows.append({"id": "m2"})
    store.group_test_rows.append({"id": "g1"})
    assert rt.tab_label_state() == "(3)"
