"""Tests for InspectorData.to_data_frame() + describe() (Cluster B10)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from rrational.inspector.data_loader import InspectorData, SectionMeta


def _make_two_section_data() -> InspectorData:
    # Section A: t=100..130 (30s, 50 beats), Section B: t=140..170.
    # Gap from 130..140 (modelled as NaN).
    t_a = np.linspace(100.0, 130.0, 50)
    v_a = np.linspace(700, 750, 50)
    gap_t = np.array([135.0])
    gap_v = np.array([np.nan])
    t_b = np.linspace(140.0, 170.0, 40)
    v_b = np.linspace(800, 850, 40)
    t = np.concatenate([t_a, gap_t, t_b])
    v = np.concatenate([v_a, gap_v, v_b])
    sections = [
        SectionMeta(name="rest", t_start=100.0, t_end=130.0, beat_count=50),
        SectionMeta(name="stress", t_start=140.0, t_end=170.0, beat_count=40),
    ]
    return InspectorData(t=t, v=v, sections=sections)


def test_to_data_frame_returns_three_columns() -> None:
    data = _make_two_section_data()
    df = data.to_data_frame()
    assert list(df.columns) == ["time", "rr_ms", "section"]


def test_to_data_frame_labels_sections_correctly() -> None:
    data = _make_two_section_data()
    df = data.to_data_frame()
    # First row sits in rest, last row in stress.
    assert df.iloc[0]["section"] == "rest"
    assert df.iloc[-1]["section"] == "stress"
    # Inter-section gap row carries the empty label.
    gap_rows = df[df["section"] == ""]
    assert len(gap_rows) == 1


def test_to_data_frame_preserves_nan_gaps() -> None:
    data = _make_two_section_data()
    df = data.to_data_frame()
    n_nan = df["rr_ms"].isna().sum()
    assert n_nan == 1


def test_describe_returns_per_section_rows() -> None:
    data = _make_two_section_data()
    summary = data.describe()
    assert isinstance(summary, pd.DataFrame)
    assert list(summary.columns) == ["section", "count", "mean", "std", "min", "max"]
    assert set(summary["section"]) == {"rest", "stress"}


def test_describe_counts_finite_samples_only() -> None:
    data = _make_two_section_data()
    summary = data.describe()
    rest_row = summary[summary["section"] == "rest"].iloc[0]
    assert rest_row["count"] == 50
    assert rest_row["min"] == pytest.approx(700)


def test_describe_falls_back_to_all_when_no_sections() -> None:
    t = np.linspace(0, 10, 20)
    v = np.linspace(700, 800, 20)
    data = InspectorData(t=t, v=v, sections=[])
    summary = data.describe()
    assert len(summary) == 1
    assert summary.iloc[0]["section"] == "all"
    assert summary.iloc[0]["count"] == 20
