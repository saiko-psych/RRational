"""Tests for the persistent right-side InfoDock (Cluster C5)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pytestqt")

from rrational.inspector.data_loader import EventMeta, InspectorData, SectionMeta
from rrational.inspector.history import HistoryRecorder, LoadRecording
from rrational.inspector.info_dock import (
    InfoDock,
    _approx_sfreq_hz,
    _format_duration,
)


def _make_data(n: int = 100) -> InspectorData:
    """Return a small InspectorData covering 100 RR intervals ~ 850 ms."""
    rr_ms = np.full(n, 850.0)
    # Cumulative seconds; first sample at t=0.
    t = np.cumsum(np.concatenate(([0.0], rr_ms[:-1] / 1000.0)))
    section = SectionMeta(
        name="rest", t_start=float(t[0]), t_end=float(t[-1]), beat_count=n
    )
    event = EventMeta(label="start", t=float(t[0]))
    return InspectorData(t=t, v=rr_ms, sections=[section], events=[event])


def test_format_duration_handles_minutes_and_hours():
    assert _format_duration(0) == "00:00"
    assert _format_duration(75) == "01:15"
    assert _format_duration(3661) == "01:01:01"
    assert _format_duration(float("nan")) == "—"
    assert _format_duration(-5) == "—"


def test_approx_sfreq_uses_60000_over_mean_rr():
    data = _make_data()  # mean RR = 850 ms → 60000/850 ≈ 70.59 Hz proxy
    sf = _approx_sfreq_hz(data)
    assert sf is not None
    assert sf == pytest.approx(60000.0 / 850.0, rel=1e-6)


def test_approx_sfreq_returns_none_for_all_nan():
    data = InspectorData(t=np.array([0.0, 1.0]), v=np.array([np.nan, np.nan]))
    assert _approx_sfreq_hz(data) is None


def test_info_dock_constructs(qtbot):
    dock = InfoDock()
    qtbot.addWidget(dock)
    assert dock.objectName() == "InfoDock"
    # All labels start at the em-dash placeholder.
    assert dock._sfreq_label.text() == "—"
    assert dock._length_label.text() == "—"
    assert dock._windows_label.text() == "—"


def test_info_dock_set_dataset_populates_rows(qtbot):
    dock = InfoDock()
    qtbot.addWidget(dock)
    recorder = HistoryRecorder()
    recorder.record(LoadRecording(path="/tmp/demo.csv"))

    data = _make_data()
    dock.set_dataset(
        data,
        filename="demo.rrational",
        recorder=recorder,
        n_exclusions=2,
        n_annotations=3,
    )

    assert dock._file_label.text() == "demo.rrational"
    # Single section → "Windows: 1"
    assert dock._windows_label.text() == "1"
    assert dock._exclusions_label.text() == "2"
    assert dock._annotations_label.text() == "3"
    # Approximate sf string contains "Hz"
    assert "Hz" in dock._sfreq_label.text()
    # Chain contains the LoadRecording action tag.
    assert "LoadRecording" in dock._chain_label.text()


def test_info_dock_set_dataset_none_clears(qtbot):
    dock = InfoDock()
    qtbot.addWidget(dock)
    dock.set_dataset(_make_data(), filename="x.csv")
    assert dock._file_label.text() == "x.csv"
    dock.set_dataset(None)
    assert dock._file_label.text() == "—"
    assert dock._chain_label.text() == "—"


def test_info_dock_chain_handles_empty_recorder(qtbot):
    dock = InfoDock()
    qtbot.addWidget(dock)
    dock.set_dataset(_make_data(), recorder=HistoryRecorder())
    assert dock._chain_label.text() == "—"
