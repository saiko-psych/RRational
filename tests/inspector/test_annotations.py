"""Phase 20 — free-text annotation tests."""

from __future__ import annotations


import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def _isolate_settings(qapp, tmp_path, monkeypatch):
    from rrational.inspector import annotation_persistence as ap
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    ap.set_annotation_config_dir(tmp_path / "annotations")
    yield
    ap.set_annotation_config_dir(None)


def _make_synthetic(name: str = "S01", n: int = 200):
    from rrational.inspector.data_loader import (
        Dataset,
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    base = 1_700_000_000
    t = base + np.arange(n, dtype=np.float64)
    v = 800 + 50 * np.sin(np.linspace(0, np.pi, n))
    data = InspectorData(
        t=t,
        v=v,
        sections=[
            SectionMeta(
                name="rec", t_start=float(t[0]), t_end=float(t[-1]), beat_count=n
            )
        ],
        events=[EventMeta(label="start", t=float(t[0]))],
    )
    return Dataset(name=f"{name}.csv", data=data)


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


@pytest.fixture
def panel(main_window):
    """Active panel with one dataset already loaded."""
    main_window.add_dataset(_make_synthetic("S01"))
    main_window.set_active_dataset(0)
    return main_window._browse_tab._preprocessing_panel


# ---------------------------------------------------------------------
# Dataclass round-trip
# ---------------------------------------------------------------------
def test_annotation_create_stamps_created_at():
    from rrational.inspector.annotations import Annotation

    a = Annotation.create(t=1.5, text="hello")
    assert a.t == 1.5
    assert a.text == "hello"
    assert a.created_at  # ISO timestamp present


def test_annotation_dict_roundtrip():
    from rrational.inspector.annotations import Annotation

    a = Annotation(t=12.5, text="cough", created_at="2026-01-01T00:00:00")
    d = a.to_dict()
    b = Annotation.from_dict(d)
    assert (b.t, b.text, b.created_at) == (a.t, a.text, a.created_at)


# ---------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------
def test_save_then_load_annotations_roundtrip(tmp_path):
    from rrational.inspector.annotation_persistence import (
        load_annotations,
        save_annotations,
    )
    from rrational.inspector.annotations import Annotation

    items = [
        Annotation.create(t=10.0, text="first"),
        Annotation.create(t=42.0, text="second"),
    ]
    save_annotations("S01", items)
    loaded = load_annotations("S01")
    assert [(a.t, a.text) for a in loaded] == [(10.0, "first"), (42.0, "second")]


def test_load_returns_empty_when_file_missing():
    from rrational.inspector.annotation_persistence import load_annotations

    assert load_annotations("NEVER_EXISTED") == []


def test_save_overwrites_previous_state():
    from rrational.inspector.annotation_persistence import (
        load_annotations,
        save_annotations,
    )
    from rrational.inspector.annotations import Annotation

    save_annotations("S01", [Annotation.create(t=1.0, text="a")])
    save_annotations("S01", [])  # delete all
    assert load_annotations("S01") == []


def test_save_routes_to_project_processed_dir(tmp_path):
    from rrational.inspector.annotation_persistence import (
        annotations_path,
        save_annotations,
    )
    from rrational.inspector.annotations import Annotation

    proj = tmp_path / "Proj"
    (proj / "data" / "processed").mkdir(parents=True)
    save_annotations("S01", [Annotation.create(t=1.0, text="x")], project_path=proj)
    expected = proj / "data" / "processed" / "S01_annotations.yml"
    assert expected.exists()
    assert annotations_path("S01", project_path=proj) == expected


# ---------------------------------------------------------------------
# Click-to-add via signal
# ---------------------------------------------------------------------
def test_plot_clicked_in_annotation_mode_adds_marker(panel):
    panel._toggle_annotation_mode.setChecked(True)
    plot = panel._main_window._browse_tab._plot
    assert plot.is_annotation_mode() is True

    # Simulate the plot's signal emission (the panel listens on plot_clicked).
    plot.plot_clicked.emit(1_700_000_010.0)

    assert len(panel._annotations) == 1
    assert len(plot.annotation_markers()) == 1
    assert panel._annotations[0].t == 1_700_000_010.0


def test_plot_clicked_outside_annotation_mode_does_nothing(panel):
    # Mode OFF; click should be ignored even if signal fires.
    panel._toggle_annotation_mode.setChecked(False)
    plot = panel._main_window._browse_tab._plot
    plot.plot_clicked.emit(1_700_000_010.0)
    assert panel._annotations == []
    assert plot.annotation_markers() == []


def test_add_annotation_persists_to_disk(panel):
    from rrational.inspector.annotation_persistence import load_annotations

    panel._toggle_annotation_mode.setChecked(True)
    plot = panel._main_window._browse_tab._plot
    plot.plot_clicked.emit(1_700_000_011.0)

    pid = "S01"
    stored = load_annotations(pid)
    assert len(stored) == 1
    assert stored[0].t == 1_700_000_011.0


# ---------------------------------------------------------------------
# Edit + delete
# ---------------------------------------------------------------------
def test_edit_annotation_updates_text_and_marker(panel):
    from rrational.inspector.annotation_persistence import load_annotations

    panel._toggle_annotation_mode.setChecked(True)
    plot = panel._main_window._browse_tab._plot
    plot.plot_clicked.emit(1_700_000_020.0)
    ann = panel._annotations[0]

    panel.edit_annotation(ann)  # test_mode appends " (edited)"

    assert "edited" in panel._annotations[0].text
    # On-disk reflects the edit
    stored = load_annotations("S01")
    assert "edited" in stored[0].text
    # Marker tooltip updated
    marker = plot.annotation_markers()[0]
    assert "edited" in marker.annotation_text


def test_delete_annotation_drops_marker_and_disk_row(panel):
    from rrational.inspector.annotation_persistence import load_annotations

    panel._toggle_annotation_mode.setChecked(True)
    plot = panel._main_window._browse_tab._plot
    plot.plot_clicked.emit(1_700_000_030.0)
    ann = panel._annotations[0]

    panel.delete_annotation(ann)

    assert panel._annotations == []
    assert plot.annotation_markers() == []
    assert load_annotations("S01") == []


# ---------------------------------------------------------------------
# Auto-restore on dataset switch
# ---------------------------------------------------------------------
def test_annotations_auto_restore_on_dataset_reopen(main_window):
    ds1 = _make_synthetic("S01")
    main_window.add_dataset(ds1)
    main_window.set_active_dataset(0)
    panel = main_window._browse_tab._preprocessing_panel
    panel._toggle_annotation_mode.setChecked(True)
    plot = main_window._browse_tab._plot
    plot.plot_clicked.emit(1_700_000_040.0)
    plot.plot_clicked.emit(1_700_000_050.0)
    assert len(panel._annotations) == 2

    # Close + reopen — annotations should reload from disk.
    main_window.close_all_datasets()
    assert panel._annotations == []

    main_window.add_dataset(_make_synthetic("S01"))
    main_window.set_active_dataset(0)
    assert len(panel._annotations) == 2
    assert len(main_window._browse_tab._plot.annotation_markers()) == 2


def test_annotations_isolated_per_pid(main_window):
    main_window.add_dataset(_make_synthetic("S01"))
    main_window.add_dataset(_make_synthetic("S02"))
    panel = main_window._browse_tab._preprocessing_panel

    main_window.set_active_dataset(0)
    panel._toggle_annotation_mode.setChecked(True)
    plot = main_window._browse_tab._plot
    plot.plot_clicked.emit(1_700_000_100.0)
    assert len(panel._annotations) == 1

    main_window.set_active_dataset(1)
    # S02 has no saved annotations — panel resets.
    assert panel._annotations == []
    assert plot.annotation_markers() == []
