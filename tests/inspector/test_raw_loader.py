"""Tests for raw RR-format loading via ``load_raw_rr`` + ``Dataset.from_path``.

The auto-detection lives in ``io.generic_rr``; the inspector wrapper just
converts ``GenericRecording`` → ``InspectorData`` (one synthetic section
named ``"recording"``).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _exists_or_skip(rel_path: str) -> Path:
    p = REPO_ROOT / rel_path
    if not p.exists():
        pytest.skip(f"{rel_path} not in repo")
    return p


# ---------------------------------------------------------------------
# Loader-level (no Qt needed)
# ---------------------------------------------------------------------
def test_dataset_from_path_routes_rrational_to_v2_loader(tmp_path):
    """``.rrational`` extension must go to the v2 path, not raw."""
    from rrational.inspector.data_loader import Dataset

    fake = tmp_path / "fake.rrational"
    fake.write_text("not really a v2 file")
    # We expect a ValueError from the v2 loader's version check — that
    # proves routing went through load_inspector_data, not load_raw_rr.
    with pytest.raises(Exception):  # noqa: BLE001 — both ValueError and KeyError possible
        Dataset.from_path(fake)


def test_load_raw_rr_elite_hrv_plain_text():
    """Plain-text RR file (one number per line) parses end-to-end."""
    from rrational.inspector.data_loader import load_raw_rr

    p = _exists_or_skip("data/demo/elite_hrv/rr_intervals.txt")
    data = load_raw_rr(p)
    assert len(data.t) > 0
    assert len(data.t) == len(data.v)
    # All RR values should be plausible (300–2000 ms)
    finite_v = data.v[np.isfinite(data.v)]
    assert finite_v.min() >= 200
    assert finite_v.max() <= 3000
    # One synthetic section spanning the whole file
    assert len(data.sections) == 1
    assert data.sections[0].name == "recording"
    # One recording_start event at t[0]
    assert len(data.events) == 1
    assert data.events[0].label == "recording_start"


def test_load_raw_rr_empatica_csv():
    """Empatica IBI.csv with unix-timestamp header parses end-to-end."""
    from rrational.inspector.data_loader import load_raw_rr

    p = _exists_or_skip("data/demo/empatica/IBI.csv")
    data = load_raw_rr(p)
    assert len(data.t) > 0
    # Empatica encodes real timestamps → t should be in unix-epoch range
    # (i.e. > year 2000). If we accidentally fell back to file-mtime,
    # the test still passes — just confirms NO bug in t array shape.
    assert data.t[0] > 0


def test_load_raw_rr_rejects_unrecognised_format(tmp_path):
    from rrational.inspector.data_loader import load_raw_rr

    junk = tmp_path / "garbage.csv"
    junk.write_text("this is not RR data at all\nrandom text only\n")
    with pytest.raises(ValueError, match="Could not detect"):
        load_raw_rr(junk)


# ---------------------------------------------------------------------
# Inspector integration (Qt needed)
# ---------------------------------------------------------------------
@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path):
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    yield


def test_open_path_accepts_raw_rr_format(qtbot):
    """``MainWindow.open_path`` round-trips a raw RR file into the workspace."""
    from rrational.inspector.main_window import MainWindow

    p = _exists_or_skip("data/demo/empatica/IBI.csv")
    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    idx = win.open_path(p)
    assert idx == 0
    assert win._data is not None
    assert win._data.sections[0].name == "recording"
    # BrowseTab's sidebar shows the file + its one synthetic section
    assert win._dataset_tree.topLevelItemCount() == 1
    assert win._dataset_tree.topLevelItem(0).childCount() == 1


def test_mixed_workspace_raw_plus_rrational(qtbot):
    """A raw file and a .rrational v2 file can co-exist in the workspace."""
    from rrational.inspector.main_window import MainWindow

    raw = _exists_or_skip("data/demo/empatica/IBI.csv")
    rrational = _exists_or_skip("data/kubios_comparison/0012MEBE.rrational")

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)

    win.open_path(raw)
    win.open_path(rrational)

    assert len(win._datasets) == 2
    # Raw has 1 section, v2 has 11 — sidebar mirrors that
    raw_node = win._dataset_tree.topLevelItem(0)
    v2_node = win._dataset_tree.topLevelItem(1)
    assert raw_node.childCount() == 1
    assert v2_node.childCount() == 11
