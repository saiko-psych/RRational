"""Menu-level wiring for the BIDS-physio export.

Verifies that Tools -> Export to BIDS-physio... is present, opens the
exporter against the currently-active dataset in test_mode (no file
dialogs), writes valid files, and stays a no-op when no dataset is
loaded.
"""

from __future__ import annotations


import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def _isolated_settings(qapp, tmp_path):
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    yield


def _synthetic_dataset(name: str = "0001CTRL.csv"):
    from rrational.inspector.data_loader import (
        Dataset,
        InspectorData,
        SectionMeta,
    )

    t = np.arange(0, 60, 0.8) + 1_700_000_000
    v = 800 + 30 * np.sin(np.linspace(0, np.pi, len(t)))
    sections = [
        SectionMeta(
            name="rest",
            t_start=float(t[0]),
            t_end=float(t[-1]),
            beat_count=len(t),
        )
    ]
    data = InspectorData(t=t, v=v, sections=sections, device="Polar H10")
    return Dataset(name=name, data=data, path=None)


@pytest.fixture
def main_window(qtbot, tmp_path):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    win._test_bids_dir = tmp_path / "bids_out"
    qtbot.addWidget(win)
    return win


def test_tools_menu_has_bids_export_action(main_window):
    assert hasattr(main_window, "_bids_export_act")
    assert main_window._bids_export_act.text() == "Export to &BIDS-physio…"


def test_bids_export_writes_files_in_test_mode(main_window, tmp_path):
    main_window.add_dataset(_synthetic_dataset())
    main_window.set_active_dataset(0)
    main_window._bids_export_act.trigger()

    paths = main_window._latest_bids_paths
    assert paths.tsv_gz.exists()
    assert paths.json.exists()
    assert "sub-0001CTRL" in paths.tsv_gz.name
    assert "task-rest" in paths.tsv_gz.name
    assert "recording-cardiac" in paths.tsv_gz.name


def test_bids_export_noop_without_dataset(main_window):
    main_window._bids_export_act.trigger()
    assert not hasattr(main_window, "_latest_bids_paths")


def test_bids_export_strips_punctuation_from_default_pid(main_window):
    # Filename with dashes / underscores → BIDS-clean pid.
    main_window.add_dataset(_synthetic_dataset(name="0001-CTRL_v2.csv"))
    main_window.set_active_dataset(0)
    main_window._bids_export_act.trigger()
    paths = main_window._latest_bids_paths
    # All non-alphanumerics are dropped.
    assert "sub-0001CTRLv2" in paths.tsv_gz.name
