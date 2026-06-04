"""Phase 20 — BIDS folder detection + loader tests."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def _isolate_settings(qapp, tmp_path, monkeypatch):
    from rrational.gui import persistence as gui_persistence
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    monkeypatch.setattr(gui_persistence, "CONFIG_DIR", tmp_path / "gui_config")
    monkeypatch.setattr(
        gui_persistence, "SETTINGS_FILE", tmp_path / "gui_config" / "settings.yml"
    )
    yield


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
# BIDS fixture builder
# ---------------------------------------------------------------------
def _write_simple_polar_csv(path: Path, n: int = 50) -> None:
    """Write an Elite-HRV / plain-text RR file (one ms per line) that
    ``io.generic_rr`` recognises as plaintext."""
    path.write_text("\n".join(["800"] * n), encoding="utf-8")


def _make_bids_fixture(root: Path, n_subjects: int = 2) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    header = "participant_id\tage\tsex\n"
    rows = []
    for i in range(1, n_subjects + 1):
        sub_id = f"sub-{i:02d}"
        sub_dir = root / sub_id
        sub_dir.mkdir(parents=True, exist_ok=True)
        _write_simple_polar_csv(sub_dir / f"{sub_id}_task-rest.csv")
        rows.append(f"{sub_id}\t30\tM\n")
    (root / "participants.tsv").write_text(header + "".join(rows), encoding="utf-8")
    return root


# ---------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------
def test_is_bids_folder_true_for_minimal_bids(tmp_path, main_window):
    root = _make_bids_fixture(tmp_path / "BIDS_minimal", n_subjects=1)
    assert main_window._is_bids_folder(root) is True


def test_is_bids_folder_false_without_participants_tsv(tmp_path, main_window):
    root = tmp_path / "no_tsv"
    (root / "sub-01").mkdir(parents=True)
    assert main_window._is_bids_folder(root) is False


def test_is_bids_folder_false_without_subject_dirs(tmp_path, main_window):
    root = tmp_path / "no_subs"
    root.mkdir()
    (root / "participants.tsv").write_text("participant_id\n", encoding="utf-8")
    assert main_window._is_bids_folder(root) is False


# ---------------------------------------------------------------------
# Full loader integration
# ---------------------------------------------------------------------
def test_open_bids_folder_loads_every_subject_recording(tmp_path, main_window):
    root = _make_bids_fixture(tmp_path / "BIDS", n_subjects=2)
    main_window.open_folder(root)

    assert len(main_window._datasets) == 2
    names = [ds.name for ds in main_window._datasets]
    assert any("sub-01" in n for n in names)
    assert any("sub-02" in n for n in names)


def test_open_bids_folder_adds_participant_entries(tmp_path, main_window):
    from rrational.gui.persistence import load_participants

    root = _make_bids_fixture(tmp_path / "BIDS", n_subjects=2)
    main_window.open_folder(root)
    participants = load_participants()
    # IDs stripped of "sub-" prefix.
    assert "01" in participants
    assert "02" in participants
    # Label carries the optional TSV columns (age + sex).
    assert "age=30" in participants["01"]["label"]
    assert "sex=M" in participants["01"]["label"]


def test_open_bids_folder_skips_existing_participant_entries(tmp_path, main_window):
    from rrational.gui.persistence import load_participants, save_participants

    save_participants(
        {"01": {"label": "manual entry", "event_order": [], "manual_events": []}}
    )

    root = _make_bids_fixture(tmp_path / "BIDS", n_subjects=2)
    main_window.open_folder(root)

    participants = load_participants()
    assert participants["01"]["label"] == "manual entry"  # untouched
    assert "02" in participants  # newly added


def test_open_folder_falls_back_to_flat_glob_when_not_bids(tmp_path, main_window):
    flat = tmp_path / "flat"
    flat.mkdir()
    _write_simple_polar_csv(flat / "a.csv")
    _write_simple_polar_csv(flat / "b.csv")
    main_window.open_folder(flat)
    # Flat glob loads both recordings.
    assert len(main_window._datasets) == 2
