"""Tests for the multi-tab shell + cross-tab notifications.

Covers:
- All four top-level tabs exist with the right labels
- Switching tabs preserves the workspace + active dataset
- on_workspace_changed / on_active_dataset_changed reach every tab
- The MainWindow backward-compat proxy properties still work after the
  widgets moved into BrowseTab
"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path):
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    yield


def _make_data():
    from rrational.inspector.data_loader import (
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    base = 1_700_000_000
    t = base + np.arange(120, dtype=np.float64)
    v = 800 + 50 * np.sin(np.linspace(0, 2 * np.pi, 120))
    return InspectorData(
        t=t,
        v=v,
        sections=[
            SectionMeta(
                name="sec1", t_start=float(t[0]), t_end=float(t[-1]), beat_count=120
            )
        ],
        events=[EventMeta(label="ev1", t=float(t[60]))],
    )


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
# Tab shell
# ---------------------------------------------------------------------
def test_five_top_level_tabs_exist(main_window):
    """Phase 11 added the Participants tab between Setup and Analysis."""
    titles = [
        main_window._tabs_widget.tabText(i)
        for i in range(main_window._tabs_widget.count())
    ]
    assert titles == ["Browse", "Setup", "Participants", "Analysis", "Results"]


def test_browse_is_initial_active_tab(main_window):
    assert main_window._tabs_widget.currentWidget() is main_window._browse_tab


def test_switching_tab_preserves_workspace(main_window):
    """Loading data + switching tabs must not lose the dataset."""
    main_window.load_data(_make_data())
    assert main_window._data is not None

    main_window._tabs_widget.setCurrentWidget(main_window._analysis_tab)
    assert main_window._data is not None  # workspace unchanged

    main_window._tabs_widget.setCurrentWidget(main_window._browse_tab)
    assert main_window._data is not None


# ---------------------------------------------------------------------
# Notification fan-out
# ---------------------------------------------------------------------
def test_load_data_notifies_every_tab(main_window):
    """All four tabs' on_active_dataset_changed must fire on load."""
    seen_data: dict[str, object] = {}

    def make_recorder(name):
        def _recorder(data):
            seen_data[name] = data

        return _recorder

    for tab, label in zip(
        [
            main_window._browse_tab,
            main_window._setup_tab,
            main_window._analysis_tab,
            main_window._results_tab,
        ],
        ["browse", "setup", "analysis", "results"],
    ):
        tab.on_active_dataset_changed = make_recorder(label)

    data = _make_data()
    main_window.load_data(data)

    for name in ("browse", "setup", "analysis", "results"):
        assert seen_data.get(name) is data, f"{name} tab did not see new data"


def test_close_all_notifies_every_tab_with_none(main_window):
    seen_data: dict[str, object] = {}

    def make_recorder(name):
        def _recorder(data):
            seen_data[name] = data

        return _recorder

    for tab, label in zip(
        [
            main_window._browse_tab,
            main_window._setup_tab,
            main_window._analysis_tab,
            main_window._results_tab,
        ],
        ["browse", "setup", "analysis", "results"],
    ):
        tab.on_active_dataset_changed = make_recorder(label)

    main_window.load_data(_make_data())
    main_window.close_all_datasets()

    for name in ("browse", "setup", "analysis", "results"):
        assert seen_data.get(name) is None, f"{name} tab did not see None"


# ---------------------------------------------------------------------
# Backward-compat proxies (widget moved into BrowseTab)
# ---------------------------------------------------------------------
def test_main_window_dataset_tree_proxy_returns_browse_widget(main_window):
    assert main_window._dataset_tree is main_window._browse_tab._dataset_tree


def test_main_window_plot_proxy_returns_browse_widget(main_window):
    assert main_window._plot is main_window._browse_tab._plot


def test_main_window_overview_bar_proxy_returns_browse_widget(main_window):
    assert main_window._overview_bar is main_window._browse_tab._overview_bar


def test_load_data_still_renders_in_browse_tab(main_window):
    """After load_data, the BrowseTab plot must have the new times array.

    Regression net: if a tab-refactor broke the notification wiring,
    the plot would stay empty even though the workspace has data.
    """
    main_window.load_data(_make_data())
    assert main_window._browse_tab._plot._times is not None
    assert len(main_window._browse_tab._plot._times) > 0
