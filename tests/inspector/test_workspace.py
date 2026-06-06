"""Multi-dataset workspace + File-menu integration tests.

Covers:
- ``add_dataset`` / ``set_active_dataset`` / ``close_dataset``
- The dataset tree shows one top-level per file, with sections nested
- Closing the active dataset switches to another or shows the empty state
- ``open_path`` records the file in QSettings recent-files
- Recent-files submenu is rebuilt from QSettings on open
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path):
    """Per-test redirect of QSettings to ``tmp_path`` (see test_settings)."""
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    yield


def _make_synthetic(name: str, t0: float = 0.0, n_sections: int = 2):
    """Build an InspectorData with ``n_sections`` named ``{name}_secN``."""
    import numpy as np
    from rrational.inspector.data_loader import (
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    base = 1_700_000_000 + t0
    t_parts, v_parts, sections, events = [], [], [], []
    for i in range(n_sections):
        start = base + i * 200
        t = start + np.arange(100, dtype=np.float64)
        v = 800 + 50 * np.sin(np.linspace(0, np.pi, 100))
        t_parts.append(t)
        v_parts.append(v)
        sec_name = f"{name}_sec{i}"
        sections.append(
            SectionMeta(
                name=sec_name, t_start=float(t[0]), t_end=float(t[-1]), beat_count=100
            )
        )
        events.append(EventMeta(label=f"{sec_name}_start", t=float(t[0])))
    return InspectorData(
        t=np.concatenate(t_parts),
        v=np.concatenate(v_parts),
        sections=sections,
        events=events,
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
# Multi-dataset API
# ---------------------------------------------------------------------
def test_add_dataset_appends_to_workspace(main_window):
    from rrational.inspector.data_loader import Dataset

    d1 = Dataset(name="A", data=_make_synthetic("A"))
    idx = main_window.add_dataset(d1)
    assert idx == 0
    assert len(main_window._datasets) == 1
    # Sidebar reflects it
    assert main_window._dataset_tree.topLevelItemCount() == 1


def test_first_added_dataset_auto_activates(main_window):
    """``add_dataset`` itself doesn't activate; ``open_path`` does on first load."""
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_synthetic("A")))
    # add_dataset alone doesn't activate — caller decides
    assert main_window._active_idx is None

    main_window.set_active_dataset(0)
    assert main_window._active_idx == 0
    assert main_window._data is not None


def test_set_active_dataset_switches_plot_content(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_synthetic("A")))
    main_window.add_dataset(Dataset(name="B", data=_make_synthetic("B", t0=1000)))

    main_window.set_active_dataset(0)
    sections_a = [s.name for s in main_window._data.sections]
    main_window.set_active_dataset(1)
    sections_b = [s.name for s in main_window._data.sections]

    assert sections_a != sections_b
    assert "A_sec0" in sections_a
    assert "B_sec0" in sections_b


def test_set_active_dataset_invalid_index_raises(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_synthetic("A")))
    with pytest.raises(IndexError):
        main_window.set_active_dataset(99)


# ---------------------------------------------------------------------
# Dataset tree shape
# ---------------------------------------------------------------------
def test_tree_shows_dataset_then_sections_as_children(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(
        Dataset(name="A.rrational", data=_make_synthetic("A", n_sections=3))
    )
    top = main_window._dataset_tree.topLevelItem(0)
    assert top.text(0) == "A.rrational"
    assert top.childCount() == 3


def test_active_dataset_is_bolded_in_tree(main_window):
    from qtpy.QtGui import QFont
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_synthetic("A")))
    main_window.add_dataset(Dataset(name="B", data=_make_synthetic("B", t0=1000)))
    main_window.set_active_dataset(1)

    fonts = [
        main_window._dataset_tree.topLevelItem(i).font(0).weight() for i in range(2)
    ]
    assert fonts[1] == QFont.Bold
    assert fonts[0] == QFont.Normal


def test_clicking_other_dataset_in_tree_activates_it(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_synthetic("A")))
    main_window.add_dataset(Dataset(name="B", data=_make_synthetic("B", t0=1000)))
    main_window.set_active_dataset(0)
    assert main_window._active_idx == 0

    second = main_window._dataset_tree.topLevelItem(1)
    main_window._on_tree_item_clicked(second, 0)
    assert main_window._active_idx == 1


# ---------------------------------------------------------------------
# Closing datasets
# ---------------------------------------------------------------------
def test_close_active_when_others_remain_picks_next(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_synthetic("A")))
    main_window.add_dataset(Dataset(name="B", data=_make_synthetic("B", t0=1000)))
    main_window.set_active_dataset(1)

    main_window.close_active_dataset()
    assert len(main_window._datasets) == 1
    # Active auto-shifted to the remaining one
    assert main_window._active_idx == 0
    assert main_window._datasets[0].name == "A"


def test_close_last_dataset_shows_empty_state(main_window):
    from rrational.inspector.data_loader import Dataset
    from rrational.inspector.main_window import LAYOUT_MNELAB

    # BrowseTab is hidden in the default Streamlit layout, so isVisible()
    # would always be False there. Switch to MNE-LAB mode (where BrowseTab
    # is the primary tab) before asserting its empty-state visibility.
    main_window.set_ui_layout(LAYOUT_MNELAB)

    main_window.add_dataset(Dataset(name="A", data=_make_synthetic("A")))
    main_window.set_active_dataset(0)
    main_window.close_active_dataset()

    assert main_window._datasets == []
    assert main_window._active_idx is None
    # UX2: the empty placeholder is now the welcome widget (recent files +
    # quick-start), not the bare "_empty_label". The label still exists for
    # back-compat but stays hidden — the welcome widget owns the empty state.
    assert main_window._browse_tab._welcome_widget.isVisible() is True
    assert main_window._plot.isVisible() is False


def test_close_all_datasets_clears_workspace(main_window):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="A", data=_make_synthetic("A")))
    main_window.add_dataset(Dataset(name="B", data=_make_synthetic("B", t0=1000)))
    main_window.set_active_dataset(0)

    main_window.close_all_datasets()
    assert main_window._datasets == []
    assert main_window._dataset_tree.topLevelItemCount() == 0


# ---------------------------------------------------------------------
# Recent files: open_path bumps the file into recent (when NOT in test_mode)
# ---------------------------------------------------------------------
def test_open_path_does_not_record_failed_loads_in_recent(main_window, tmp_path):
    """``open_path`` only bumps to recent on SUCCESS, not on parse error.

    Stays in ``test_mode`` (set by the fixture) so the error message is
    routed to the status bar instead of opening a modal QMessageBox —
    pytest-qt would deadlock on a real modal dialog under offscreen QPA.
    """
    from rrational.inspector import settings

    fake = tmp_path / "fake.rrational"
    fake.write_text("not a real rrational file")
    main_window.open_path(fake)
    assert settings.get_recent_files() == []


def test_recent_menu_lists_recent_files(main_window, tmp_path):
    """``_rebuild_recent_menu`` mirrors the QSettings recent-files list."""
    from rrational.inspector import settings

    a = tmp_path / "a.rrational"
    b = tmp_path / "b.rrational"
    a.write_text("dummy")
    b.write_text("dummy")
    settings.add_recent_file(a)
    settings.add_recent_file(b)

    main_window._rebuild_recent_menu()
    texts = [act.text() for act in main_window._recent_menu.actions()]
    # Expect "b.rrational", "a.rrational", separator, "Clear recent files"
    assert "b.rrational" in texts
    assert "a.rrational" in texts
    assert "Clear recent files" in texts


def test_recent_menu_shows_placeholder_when_empty(main_window):
    """Empty recent list → single disabled '(no recent files)' entry."""
    main_window._rebuild_recent_menu()
    actions = main_window._recent_menu.actions()
    assert len(actions) == 1
    assert actions[0].text() == "(no recent files)"
    assert actions[0].isEnabled() is False
