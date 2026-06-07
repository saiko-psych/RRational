"""Tests for Phase 22.2 — Participant tab (per-subject deep-dive).

The ParticipantTab is built as a standalone widget — it isn't auto-
registered in MainWindow's tab list (that's a separate worktree).
These tests instantiate the tab directly with a live MainWindow as
its workspace anchor, then drive it through the same notification
hooks the MainWindow would.
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


def _make_data(n_sections=2):
    from rrational.inspector.data_loader import (
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    n_beats = max(300, n_sections * 100 + 10)
    base = 1_700_000_000
    t = base + np.arange(n_beats, dtype=np.float64)
    v = 800 + 10 * np.sin(np.linspace(0, 2 * np.pi, n_beats))
    sections = [
        SectionMeta(
            name=f"sec{i}",
            t_start=float(t[i * 100]),
            t_end=float(t[(i + 1) * 100 - 1]),
            beat_count=100,
        )
        for i in range(n_sections)
    ]
    events = [EventMeta(label=f"ev{i}", t=float(t[i * 50])) for i in range(n_sections)]
    return InspectorData(t=t, v=v, sections=sections, events=events)


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
def participant_tab(main_window, qtbot):
    from rrational.inspector.tabs.participant_tab import ParticipantTab

    tab = ParticipantTab(main_window)
    qtbot.addWidget(tab)
    tab.show()
    qtbot.waitExposed(tab)
    return tab


# ---------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------
def test_tab_instantiates_with_correct_label(participant_tab):
    assert participant_tab.TAB_LABEL == "Participant"


def test_tab_has_plot_and_preprocessing_panel(participant_tab):
    """ParticipantTab must REUSE RRPlotWidget + PreprocessingPanel (not duplicate)."""
    from rrational.inspector.plot_widget import RRPlotWidget
    from rrational.inspector.tabs.preprocessing_panel import PreprocessingPanel

    assert isinstance(participant_tab._plot, RRPlotWidget)
    assert isinstance(participant_tab._preprocessing_panel, PreprocessingPanel)


def test_starts_in_empty_state(participant_tab):
    assert participant_tab._participant_combo.count() == 0
    assert participant_tab._sections_list.count() == 0
    assert "No participants" in participant_tab._status_label.text()
    assert not participant_tab._prev_btn.isEnabled()
    assert not participant_tab._next_btn.isEnabled()


# ---------------------------------------------------------------------
# Tab label state badge
# ---------------------------------------------------------------------
def test_tab_label_state_empty(participant_tab):
    assert participant_tab.tab_label_state() == "(none selected)"


def test_tab_label_state_with_active_dataset(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="0012MEBE.rrational", data=_make_data()))
    main_window.set_active_dataset(0)
    # MainWindow doesn't know about this tab, so notify it manually:
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)
    # Phase 23B: no group assigned → just the stem in parens.
    assert participant_tab.tab_label_state() == "(0012MEBE)"


# ---------------------------------------------------------------------
# Dropdown populates from the workspace
# ---------------------------------------------------------------------
def test_dropdown_populates_from_workspace(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    for n in ("0012MEBE.rrational", "0105LYMA.rrational", "0211ABCD.rrational"):
        main_window.add_dataset(Dataset(name=n, data=_make_data()))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)

    assert participant_tab._participant_combo.count() == 3
    items = [
        participant_tab._participant_combo.itemText(i)
        for i in range(participant_tab._participant_combo.count())
    ]
    assert items == ["0012MEBE", "0105LYMA", "0211ABCD"]


def test_dropdown_stem_uses_path_stem_when_available(
    main_window, participant_tab, tmp_path
):
    from rrational.inspector.data_loader import Dataset

    p = tmp_path / "P099XYZ.rrational"
    p.write_text("dummy")
    main_window.add_dataset(Dataset(name=p.name, data=_make_data(), path=p))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    assert participant_tab._participant_combo.itemText(0) == "P099XYZ"


# ---------------------------------------------------------------------
# Dropdown triggers set_active_dataset
# ---------------------------------------------------------------------
def test_dropdown_pick_calls_set_active_dataset(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    for n in ("0012MEBE.rrational", "0105LYMA.rrational"):
        main_window.add_dataset(Dataset(name=n, data=_make_data()))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()

    calls: list[int] = []
    original = main_window.set_active_dataset

    def spy(idx: int) -> None:
        calls.append(idx)
        original(idx)

    main_window.set_active_dataset = spy
    # User picks the second participant via the dropdown.
    participant_tab._participant_combo.setCurrentIndex(1)
    assert 1 in calls
    assert main_window._active_idx == 1


# ---------------------------------------------------------------------
# Prev / Next arrow buttons
# ---------------------------------------------------------------------
def test_next_button_advances_active(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    for n in ("A.rrational", "B.rrational", "C.rrational"):
        main_window.add_dataset(Dataset(name=n, data=_make_data()))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)

    participant_tab._on_next_clicked()
    # The tab isn't registered on MainWindow in this test, so we relay
    # the notification by hand — in production, _notify_tabs_active_changed
    # would call this for us.
    participant_tab.on_active_dataset_changed(main_window._data)
    assert main_window._active_idx == 1
    participant_tab._on_next_clicked()
    participant_tab.on_active_dataset_changed(main_window._data)
    assert main_window._active_idx == 2
    # Disabled at the end.
    assert not participant_tab._next_btn.isEnabled()


def test_prev_button_goes_back(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    for n in ("A.rrational", "B.rrational"):
        main_window.add_dataset(Dataset(name=n, data=_make_data()))
    main_window.set_active_dataset(1)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)

    participant_tab._on_prev_clicked()
    participant_tab.on_active_dataset_changed(main_window._data)
    assert main_window._active_idx == 0
    assert not participant_tab._prev_btn.isEnabled()


def test_status_label_reflects_position(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    for n in ("A.rrational", "B.rrational", "C.rrational"):
        main_window.add_dataset(Dataset(name=n, data=_make_data()))
    main_window.set_active_dataset(1)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)
    assert "2 of 3" in participant_tab._status_label.text()


# ---------------------------------------------------------------------
# Section list shows section names + plot renders
# ---------------------------------------------------------------------
def test_sections_list_shows_section_names(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="P1.rrational", data=_make_data(n_sections=3)))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)

    assert participant_tab._sections_list.count() == 3
    # The UserRole payload carries the section name (the visible widget
    # is a rich-text row composed inside _rebuild_sections_list).
    from rrational.inspector.tabs.participant_tab import _ROLE_SECTION_NAME

    names = [
        participant_tab._sections_list.item(i).data(_ROLE_SECTION_NAME)
        for i in range(participant_tab._sections_list.count())
    ]
    assert names == ["sec0", "sec1", "sec2"]


def test_plot_renders_active_dataset(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    data = _make_data(n_sections=2)
    main_window.add_dataset(Dataset(name="P1.rrational", data=data))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)

    assert participant_tab._plot._times is not None
    assert len(participant_tab._plot._times) == len(data.t)


def test_section_click_zooms_plot(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    data = _make_data(n_sections=2)
    main_window.add_dataset(Dataset(name="P1.rrational", data=data))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)

    item = participant_tab._sections_list.item(1)
    participant_tab._on_section_clicked(item)

    # The view-range should now overlap section 1's [t_start, t_end] window
    # rather than the full recording.
    sec = data.sections[1]
    x0, x1 = participant_tab._plot.getViewBox().viewRange()[0]
    assert x0 <= sec.t_start + 1  # padding allowed
    assert x1 >= sec.t_end - 1


# ---------------------------------------------------------------------
# Empty-state recovery
# ---------------------------------------------------------------------
def test_closing_all_clears_tab(main_window, participant_tab):
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="P1.rrational", data=_make_data()))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)
    assert participant_tab._sections_list.count() > 0

    main_window.close_all_datasets()
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(None)
    assert participant_tab._sections_list.count() == 0
    assert participant_tab._participant_combo.count() == 0


# ---------------------------------------------------------------------
# NN summary line at the bottom
# ---------------------------------------------------------------------
def test_nn_summary_initial_text(participant_tab):
    assert "No artifact detection" in participant_tab._nn_summary.text()


def test_nn_summary_updates_after_preprocessing_result(main_window, participant_tab):
    """Simulate a panel result; the bottom summary line reads from it."""
    from rrational.inspector.data_loader import Dataset
    from rrational.inspector.preprocessing import PreprocessingResult

    main_window.add_dataset(Dataset(name="P1.rrational", data=_make_data()))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)

    # Inject a fake result onto the panel and refresh.
    participant_tab._preprocessing_panel._last_result = PreprocessingResult(
        indices=np.array([1, 2, 5, 7], dtype=np.int64),
        total=200,
        rate=0.02,
        grade="good",
    )
    participant_tab._refresh_nn_summary()
    text = participant_tab._nn_summary.text()
    assert "4 corrected" in text
    assert "200 total" in text
    assert "2.00%" in text


# ---------------------------------------------------------------------
# Phase 23B — header metrics + section validation persistence
# ---------------------------------------------------------------------
def _seed_participant_meta(main_window, pid: str, **overrides):
    """Populate ParticipantsTab._participants with one entry."""
    pt = main_window._participants_tab
    pt._participants[pid] = {
        "label": overrides.get("label", ""),
        "group": overrides.get("group", ""),
        "sequence": overrides.get("sequence", ""),
        "event_order": [],
        "manual_events": [],
    }


def test_header_metrics_show_group_and_sequence(main_window, participant_tab):
    """Header row pulls group + sequence from the ParticipantsTab."""
    from rrational.inspector.data_loader import Dataset

    pid = "0012MEBE"
    main_window.add_dataset(
        Dataset(name=f"{pid}.rrational", data=_make_data(n_sections=2))
    )
    _seed_participant_meta(main_window, pid, group="MAR", sequence="R1")
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)

    assert participant_tab._hdr_participant_value.text() == pid
    assert participant_tab._hdr_group_value.text() == "MAR"
    assert participant_tab._hdr_sequence_value.text() == "R1"
    # Beats / duration / duplicates derive from the dataset arrays.
    beats_text = participant_tab._hdr_beats_value.text()
    assert "retained" in beats_text
    assert participant_tab._hdr_duration_value.text().endswith("min")
    assert participant_tab._hdr_duplicates_value.text() == "0"


def test_tab_label_state_shows_group_and_sequence(main_window, participant_tab):
    """tab_label_state composes stem / group / sequence when all present."""
    from rrational.inspector.data_loader import Dataset

    pid = "0012MEBE"
    main_window.add_dataset(
        Dataset(name=f"{pid}.rrational", data=_make_data(n_sections=2))
    )
    _seed_participant_meta(main_window, pid, group="MAR", sequence="R1")
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)
    assert participant_tab.tab_label_state() == f"({pid} / MAR / R1)"


def test_validate_section_writes_yaml(main_window, participant_tab, tmp_path):
    """_on_validate_section persists to {pid}_section_validations.yml."""
    import yaml
    from rrational.inspector.data_loader import Dataset

    pid = "0012MEBE"
    main_window.add_dataset(
        Dataset(name=f"{pid}.rrational", data=_make_data(n_sections=2))
    )
    _seed_participant_meta(main_window, pid, group="MAR", sequence="R1")
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)

    # Drive the validate handler directly — test_mode skips the modal.
    participant_tab._on_validate_section("sec0")

    # The persistence layer writes to ~/.rrational/exports/ when no
    # project is open (CONFIG_DIR / "exports"). We isolated CONFIG_DIR
    # via the autouse fixture so the file lives under tmp_path.
    from rrational.gui import persistence as gui_persistence

    target = gui_persistence.CONFIG_DIR / "exports" / f"{pid}_section_validations.yml"
    assert target.exists(), f"Expected {target} to exist after validation"
    payload = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert payload["participant_id"] == pid
    assert payload["group"] == "MAR"
    assert "sec0" in payload["sections"]
    assert payload["sections"]["sec0"]["validator"] == "inspector"
    assert "validated_at" in payload["sections"]["sec0"]


def test_validations_reload_on_dataset_switch(main_window, participant_tab, tmp_path):
    """Switching datasets reloads {pid}_section_validations.yml for the new pid."""
    from rrational.gui.persistence import save_section_validations
    from rrational.inspector.data_loader import Dataset

    pid_a = "AAA"
    pid_b = "BBB"
    main_window.add_dataset(
        Dataset(name=f"{pid_a}.rrational", data=_make_data(n_sections=2))
    )
    main_window.add_dataset(
        Dataset(name=f"{pid_b}.rrational", data=_make_data(n_sections=2))
    )
    _seed_participant_meta(main_window, pid_a, group="G1")
    _seed_participant_meta(main_window, pid_b, group="G2")

    # Pre-seed pid_b's YAML on disk; pid_a has nothing.
    save_section_validations(
        participant_id=pid_b,
        group="G2",
        section_validations={
            "sec1": {"validated_at": "2026-01-01T00:00:00", "validator": "inspector"}
        },
    )

    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)
    assert participant_tab._section_validations == {}

    main_window.set_active_dataset(1)
    participant_tab.on_active_dataset_changed(main_window._data)
    assert "sec1" in participant_tab._section_validations
    # And the section list row reflects the validated state via the
    # check-mark prefix in the visible widget.
    item = participant_tab._sections_list.item(1)
    row_widget = participant_tab._sections_list.itemWidget(item)
    # The first child of the row layout is the QLabel with the name.
    from qtpy.QtWidgets import QLabel as _QLabel

    label = row_widget.findChild(_QLabel)
    assert "✓" in label.text()


def test_clear_validation_removes_from_yaml(main_window, participant_tab):
    """_clear_validation drops the section from the YAML payload."""
    import yaml
    from rrational.inspector.data_loader import Dataset

    pid = "PXYZ"
    main_window.add_dataset(
        Dataset(name=f"{pid}.rrational", data=_make_data(n_sections=2))
    )
    _seed_participant_meta(main_window, pid, group="GZ")
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)

    # Validate two sections, then clear one and confirm the file no
    # longer mentions it.
    participant_tab._on_validate_section("sec0")
    participant_tab._on_validate_section("sec1")
    assert set(participant_tab._section_validations.keys()) == {"sec0", "sec1"}

    participant_tab._clear_validation("sec0")
    assert "sec0" not in participant_tab._section_validations
    assert "sec1" in participant_tab._section_validations

    from rrational.gui import persistence as gui_persistence

    target = gui_persistence.CONFIG_DIR / "exports" / f"{pid}_section_validations.yml"
    payload = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert "sec0" not in payload["sections"]
    assert "sec1" in payload["sections"]


# ---------------------------------------------------------------------
# Phase 24C-retry: quality-issue detectors + listings
# ---------------------------------------------------------------------
def test_detect_time_gaps_finds_synthetic_gap():
    """A 10-second gap inserted into an otherwise-uniform timestamp
    series surfaces as exactly one entry, with the correct duration."""
    from rrational.inspector.tabs.participant_tab import _detect_time_gaps

    t = np.arange(0, 200, 1.0, dtype=np.float64)
    # Push everything from index 100 onward 10 s into the future so the
    # diff at index 99 jumps from 1.0 s to 11.0 s.
    t[100:] += 10.0
    gaps = _detect_time_gaps(t, threshold_s=5.0)
    assert len(gaps) == 1
    gap_s, gap_t_start, gap_t_end = gaps[0]
    assert gap_s == pytest.approx(11.0)
    assert gap_t_start == pytest.approx(99.0)
    assert gap_t_end == pytest.approx(110.0)


def test_detect_high_variability_segments_flags_spiky_data():
    """A synthetic recording that's calm for the first half and very
    spiky in the second half should produce at least one CV segment."""
    from rrational.inspector.tabs.participant_tab import (
        _detect_high_variability_segments,
    )

    rng = np.random.default_rng(seed=7)
    n = 200
    t = np.arange(n, dtype=np.float64)
    # Calm half: tight RR around 800 ms. Spiky half: huge swings that
    # push the rolling CV well past 0.30.
    calm = 800.0 + 5.0 * rng.standard_normal(n // 2)
    spiky = 800.0 + 600.0 * rng.standard_normal(n // 2)
    v = np.concatenate([calm, spiky])
    segments = _detect_high_variability_segments(t, v, window=30, cv_threshold=0.30)
    assert len(segments) >= 1
    # Every reported segment's CV must clear the threshold.
    for _t_start, _t_end, cv in segments:
        assert cv > 0.30


def test_quality_lists_populate_on_dataset_load(participant_tab, main_window):
    """Loading a dataset with a manufactured gap fills the gaps list."""
    from rrational.inspector.data_loader import Dataset
    from rrational.inspector.tabs.participant_tab import _ROLE_QUALITY_RANGE

    data = _make_data(n_sections=2)
    # Inject a 7-second gap so the gap detector has something to find.
    data.t[150:] += 7.0
    main_window.add_dataset(Dataset(name="quality_demo", data=data))
    main_window.set_active_dataset(0)
    # Force a render path so the lists get rebuilt.
    participant_tab.on_active_dataset_changed(data)

    assert participant_tab._quality_gaps_list.count() >= 1
    first = participant_tab._quality_gaps_list.item(0)
    assert first.text().startswith("Gap")
    rng = first.data(_ROLE_QUALITY_RANGE)
    assert rng is not None
    assert len(rng) == 2


# ---------------------------------------------------------------------
# F1 — Repetitive events generator
# ---------------------------------------------------------------------
def test_repetitive_events_generator_creates_n_events(main_window, participant_tab):
    """Filling 3 repetitions x 2 events appends 6 EventMetas to the dataset.

    Drives the RepetitiveEventsDialog through its test-mode entry point
    (open_repetitive_events_dialog + _apply_repetitive_events) so the
    modal exec() loop is bypassed and the table can be pre-filled
    programmatically.
    """
    from rrational.inspector.data_loader import Dataset

    pid = "RPT"
    data = _make_data(n_sections=2)
    main_window.add_dataset(Dataset(name=f"{pid}.rrational", data=data))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)

    n_before = len(data.events)

    # Construct the dialog without exec()ing it, pre-fill 3x[rest 5s,
    # music 10s], and apply.
    dlg = participant_tab.open_repetitive_events_dialog()
    assert dlg is not None
    dlg.set_repetitions(3)
    dlg.set_sequence([("rest", 5.0), ("music", 10.0)])

    ds = main_window._datasets[0]
    n_added = participant_tab._apply_repetitive_events(dlg, ds)

    assert n_added == 6
    assert len(data.events) == n_before + 6

    # The newly-appended events are the last 6 entries in insertion order.
    new = data.events[-6:]
    labels = [ev.label for ev in new]
    assert labels == ["rest", "music"] * 3

    # Timestamps step by per-row duration: cumulative offsets
    # 0, 5, 15, 20, 30, 35 from the dialog's default start.
    start = dlg._start_spin.value()
    offsets = [ev.t - start for ev in new]
    assert offsets == pytest.approx([0.0, 5.0, 15.0, 20.0, 30.0, 35.0])


def test_repetitive_events_preview_label_reports_counts(participant_tab, main_window):
    """The dialog's preview label reflects the current sequence + reps."""
    from rrational.inspector.data_loader import Dataset

    main_window.add_dataset(Dataset(name="PRV.rrational", data=_make_data()))
    main_window.set_active_dataset(0)
    participant_tab.on_workspace_changed()
    participant_tab.on_active_dataset_changed(main_window._data)

    dlg = participant_tab.open_repetitive_events_dialog()
    assert dlg is not None
    dlg.set_repetitions(4)
    dlg.set_sequence([("a", 7.0), ("b", 13.0)])
    # 4 * 2 = 8 events, total span 4 * 20.0 = 80.0 s.
    txt = dlg._preview_label.text()
    assert "8 events" in txt
    assert "80.0" in txt


def test_repetitive_events_button_present_in_tab(participant_tab):
    """The 'Add repetitive sequence…' button must be wired up."""
    assert participant_tab._add_repetitive_btn is not None
    assert "repetitive" in participant_tab._add_repetitive_btn.text().lower()
