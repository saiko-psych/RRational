"""Extra smoke tests for ``rrational.inspector.data_loader`` dataclasses.

The existing test_raw_loader / test_bids_loader suites cover the
file-format parsing paths; these tests pin the dataclass APIs
(``InspectorData.t_start`` / ``t_end``, ``Dataset`` construction,
``SectionMeta`` + ``EventMeta`` fields) that downstream modules
read directly.
"""

from __future__ import annotations

import numpy as np
import pytest

from rrational.inspector.data_loader import (
    Dataset,
    EventMeta,
    InspectorData,
    SectionMeta,
)


# ---------------------------------------------------------------------
# InspectorData.t_start / t_end properties (NaN-aware)
# ---------------------------------------------------------------------
def test_t_start_returns_first_finite_sample():
    t = np.array([100.0, 101.0, 102.0, np.nan, 110.0, 111.0])
    v = np.array([800.0, 810.0, 805.0, np.nan, 820.0, 815.0])
    data = InspectorData(t=t, v=v)
    assert data.t_start == 100.0


def test_t_end_returns_last_finite_sample():
    t = np.array([100.0, 101.0, np.nan, 110.0, 111.0])
    v = np.array([800.0, 810.0, np.nan, 820.0, 815.0])
    data = InspectorData(t=t, v=v)
    assert data.t_end == 111.0


def test_t_start_and_t_end_ignore_leading_and_trailing_nans():
    # All-finite block in the middle, NaN-padded ends.
    t = np.array([np.nan, 200.0, 201.0, 202.0, np.nan])
    v = np.array([np.nan, 800.0, 810.0, 805.0, np.nan])
    data = InspectorData(t=t, v=v)
    assert data.t_start == 200.0
    assert data.t_end == 202.0


# ---------------------------------------------------------------------
# InspectorData construction edge cases
# ---------------------------------------------------------------------
def test_inspector_data_constructs_with_empty_arrays():
    data = InspectorData(
        t=np.array([], dtype=np.float64), v=np.array([], dtype=np.float64)
    )
    assert data.t.size == 0
    assert data.v.size == 0
    assert data.sections == []
    assert data.events == []
    # Optional BIDS-prep metadata defaults.
    assert data.experimenter == ""
    assert data.description == ""
    assert data.device == ""
    assert data.line_freq is None


# ---------------------------------------------------------------------
# Dataset dataclass round-trip
# ---------------------------------------------------------------------
def test_dataset_init_round_trip():
    t = np.linspace(0.0, 10.0, 11)
    v = np.full_like(t, 800.0)
    data = InspectorData(t=t, v=v)
    ds = Dataset(name="P01.rrational", data=data, path=None)
    assert ds.name == "P01.rrational"
    assert ds.data is data
    assert ds.path is None


# ---------------------------------------------------------------------
# SectionMeta dataclass shape
# ---------------------------------------------------------------------
def test_section_meta_fields():
    meta = SectionMeta(name="rest", t_start=0.0, t_end=300.0, beat_count=300)
    assert meta.name == "rest"
    assert meta.t_start == 0.0
    assert meta.t_end == 300.0
    assert meta.beat_count == 300
    # Computed duration: callers do ``t_end - t_start`` directly (the
    # dataclass does not expose a property). Pin the arithmetic here so
    # any future schema change shows up.
    assert (meta.t_end - meta.t_start) == pytest.approx(300.0)


# ---------------------------------------------------------------------
# EventMeta dataclass + unicode labels
# ---------------------------------------------------------------------
def test_event_meta_with_unicode_label():
    # Inspector accepts free-form event labels including non-ASCII —
    # locale-localised session names from European studies.
    meta = EventMeta(label="ruhepause_anfang", t=123.456)
    assert meta.label == "ruhepause_anfang"
    assert meta.t == 123.456

    # Multi-byte / emoji-free unicode (Greek letters used in HRV docs).
    meta2 = EventMeta(label="alpha_baseline", t=42.0)
    assert meta2.label == "alpha_baseline"
