"""Verify BrowseTab wires WorkspaceTreeWidget with status badges.

Round 15 / Sprint 2 — the badge-aware sidebar replaced the bare
``QTreeWidget`` instantiation in ``BrowseTab._build``. These tests
exercise the public effect (badges visible on rows) rather than the
internal delegate paint pipeline, which has its own coverage in
``test_workspace_tree.py``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("pytestqt")

from rrational.inspector.data_loader import Dataset, InspectorData, SectionMeta
from rrational.inspector.workspace_tree import ROLE_BADGES, WorkspaceTreeWidget


@pytest.fixture
def main_window(qtbot):
    """Headless MainWindow for sidebar wiring tests."""
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


def _synthetic_dataset(
    name: str = "demo.rrational",
    *,
    n_sections: int = 1,
    nan_fraction: float = 0.0,
    path: Path | None = None,
) -> Dataset:
    """Build a minimal in-memory dataset for badge-derivation tests."""
    n = 1000
    t = np.linspace(0.0, 600.0, n, dtype=float)
    v = np.full(n, 850.0, dtype=float)
    if nan_fraction > 0.0:
        cutoff = int(n * nan_fraction)
        v[:cutoff] = np.nan
    sections = [
        SectionMeta(
            name=f"section_{i}",
            t_start=float(i * 60),
            t_end=float((i + 1) * 60),
            beat_count=60,
        )
        for i in range(n_sections)
    ]
    data = InspectorData(t=t, v=v, sections=sections, events=[])
    return Dataset(name=name, data=data, path=path)


def test_browse_tab_uses_workspace_tree(main_window, qtbot):
    """The sidebar is now a WorkspaceTreeWidget, not a bare QTreeWidget."""
    bt = main_window._browse_tab
    assert isinstance(bt._dataset_tree, WorkspaceTreeWidget)


def test_browse_tab_renders_badges_for_multi_section_dataset(main_window, qtbot):
    """Multi-section + high-NaN dataset surfaces SECTIONS and BAD-Q badges."""
    bt = main_window._browse_tab
    ds = _synthetic_dataset(n_sections=3, nan_fraction=0.20)
    main_window._datasets.append(ds)
    bt.on_workspace_changed()

    top = bt._dataset_tree.topLevelItem(0)
    assert top is not None
    tags = top.data(0, ROLE_BADGES) or []
    assert "SECTIONS" in tags
    assert "BAD-Q" in tags


def test_browse_tab_kubios_and_bids_badges(main_window, qtbot, tmp_path):
    """source_app=Kubios → KUBIOS badge; BIDS-physio path → BIDS badge."""
    bt = main_window._browse_tab
    p = tmp_path / "sub-01_ses-1_task-rest_recording-cardiac_physio.tsv.gz"
    p.write_bytes(b"")  # name-only check; we don't parse it
    ds = _synthetic_dataset(name=p.name, path=p)
    # Tag the dataset object with the Kubios marker — the badge helper
    # checks getattr(ds, "source_app") first.
    ds.source_app = "Kubios"
    main_window._datasets.append(ds)
    bt.on_workspace_changed()

    top = bt._dataset_tree.topLevelItem(0)
    tags = top.data(0, ROLE_BADGES) or []
    assert "KUBIOS" in tags
    assert "BIDS" in tags


def test_browse_tab_no_badges_for_clean_dataset(main_window, qtbot):
    """A single-section, clean-data dataset shows no badges at all."""
    bt = main_window._browse_tab
    ds = _synthetic_dataset(n_sections=1, nan_fraction=0.0)
    main_window._datasets.append(ds)
    bt.on_workspace_changed()

    top = bt._dataset_tree.topLevelItem(0)
    tags = top.data(0, ROLE_BADGES) or []
    assert tags == []


def test_prev_next_navigation_steps_through_recordings(main_window):
    """The Prev/Next bar steps the active recording and tracks the "X / N"
    counter — the easy way to review every loaded recording in sequence."""
    bt = main_window._browse_tab
    for k in range(3):
        main_window.add_dataset(_synthetic_dataset(f"rec_{k}.rrational"))
    main_window.set_active_dataset(0)

    assert bt._ds_counter.text() == "1 / 3"
    assert not bt._prev_ds_btn.isEnabled()  # at the first
    assert bt._next_ds_btn.isEnabled()

    bt._go_relative(1)
    assert main_window._active_idx == 1
    assert bt._ds_counter.text() == "2 / 3"

    bt._go_relative(1)
    assert main_window._active_idx == 2
    assert not bt._next_ds_btn.isEnabled()  # at the last

    bt._go_relative(1)  # clamp — stays put
    assert main_window._active_idx == 2

    bt._go_relative(-1)
    assert main_window._active_idx == 1
    assert bt._prev_ds_btn.isEnabled()
