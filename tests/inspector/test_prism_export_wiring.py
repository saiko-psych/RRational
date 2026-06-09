"""Menu-level wiring for the PRISM Studio biometrics export.

Verifies Tools -> Export to PRISM biometrics... is present, runs in
test_mode without dialogs, writes a TSV + JSON sidecar against the
active dataset, and stays a no-op when nothing is loaded.
"""

from __future__ import annotations

import json

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

    # Long enough so the HRV compute returns non-trivial values for
    # every domain (>= 300 beats for frequency-domain estimates).
    t = np.arange(0, 360, 0.8) + 1_700_000_000
    v = 800 + 30 * np.sin(np.linspace(0, np.pi * 12, len(t)))
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
    win._test_prism_dir = tmp_path / "prism_out"
    qtbot.addWidget(win)
    return win


def test_tools_menu_has_prism_export_action(main_window):
    assert hasattr(main_window, "_prism_export_act")
    assert "PRISM" in main_window._prism_export_act.text()


def test_prism_export_writes_files_in_test_mode(main_window):
    main_window.add_dataset(_synthetic_dataset())
    main_window.set_active_dataset(0)
    main_window._prism_export_act.trigger()

    paths = main_window._latest_prism_paths
    assert paths.tsv.exists()
    assert paths.json.exists()
    assert "biometrics-hrv" in paths.tsv.name
    assert paths.tsv.name.endswith("_biometrics.tsv")


def test_prism_export_sidecar_carries_software_platform(main_window):
    main_window.add_dataset(_synthetic_dataset())
    main_window.set_active_dataset(0)
    main_window._prism_export_act.trigger()

    sidecar = json.loads(main_window._latest_prism_paths.json.read_text())
    assert sidecar["Technical"]["SoftwarePlatform"] == "RRational"
    assert sidecar["Technical"]["Equipment"] == "Polar H10"


def test_prism_export_tsv_contains_hrv_columns(main_window):
    main_window.add_dataset(_synthetic_dataset())
    main_window.set_active_dataset(0)
    main_window._prism_export_act.trigger()

    import csv

    with main_window._latest_prism_paths.tsv.open("r", encoding="utf-8") as f:
        rows = list(csv.reader(f, delimiter="\t"))
    header = rows[0]
    # Time-domain + frequency-domain + Poincare metrics are all present.
    for expected in (
        "rmssd_ms",
        "sdnn_ms",
        "mean_hr_bpm",
        "lf_ms2",
        "hf_ms2",
        "sd1_ms",
    ):
        assert expected in header, f"Missing {expected} column"


def test_prism_export_noop_without_dataset(main_window):
    main_window._prism_export_act.trigger()
    assert not hasattr(main_window, "_latest_prism_paths")
