"""Round 32 regression tests — corrected-RR analysis flow + manual-mark export.

- PP1: when a Dataset carries a corrected series with ``use_corrected`` set,
  the Analysis tab's _slice_section must analyse the CORRECTED values, not
  the raw ``data.v``. Previously the "Use corrected RR values" toggle only
  redrew the plot while Compute silently ran on raw data.
- PP2: build_v2_export must fold the user's manual artifact edits into the
  exported artifact set: (algorithm ∪ manual_added) − manual_removed.

Pure logic, no Qt.
"""

from __future__ import annotations

import numpy as np

from rrational.inspector.data_loader import Dataset, InspectorData, SectionMeta
from rrational.inspector.export import build_v2_export
from rrational.inspector.preprocessing import PreprocessingResult
from rrational.inspector.tabs.analysis_tab import _corrected_for, _slice_section


def _one_section_dataset(n: int = 12):
    t = 1_700_000_000 + np.arange(n, dtype=float)
    v = np.full(n, 800.0)
    sec = SectionMeta(name="all", t_start=float(t[0]), t_end=float(t[-1]), beat_count=n)
    data = InspectorData(t=t, v=v, sections=[sec], events=[])
    return Dataset(name="P01", data=data)


# ---------------------------------------------------------------------
# PP1 — analysis honours the corrected series
# ---------------------------------------------------------------------
def test_slice_section_uses_raw_by_default():
    ds = _one_section_dataset()
    ds.data.v[5] = 400.0  # an artifact
    rr = _slice_section(ds.data, "all", corrected_v=_corrected_for(ds))
    assert rr[5] == 400.0  # raw value, no correction requested


def test_slice_section_uses_corrected_when_flag_set():
    ds = _one_section_dataset()
    ds.data.v[5] = 400.0
    corrected = ds.data.v.copy()
    corrected[5] = 810.0
    ds.corrected_v = corrected
    ds.use_corrected = True
    rr = _slice_section(ds.data, "all", corrected_v=_corrected_for(ds))
    assert rr[5] == 810.0  # corrected value flows into analysis


def test_corrected_for_respects_flag():
    ds = _one_section_dataset()
    ds.corrected_v = ds.data.v.copy()
    # Flag off -> None (raw), even though corrected_v exists.
    assert _corrected_for(ds) is None
    ds.use_corrected = True
    assert _corrected_for(ds) is not None


def test_slice_section_falls_back_on_length_mismatch():
    ds = _one_section_dataset()
    ds.use_corrected = True
    ds.corrected_v = np.array([1.0, 2.0])  # wrong length
    rr = _slice_section(ds.data, "all", corrected_v=_corrected_for(ds))
    # Defensive fallback to raw (all 800.0), not a crash.
    assert rr is not None and np.allclose(rr, 800.0)


# ---------------------------------------------------------------------
# PP2 — manual marks fold into the export
# ---------------------------------------------------------------------
def _export_indices(manual_added, manual_removed):
    ds = _one_section_dataset(20)
    pre = PreprocessingResult(
        indices=np.array([5], dtype=np.int64),
        by_type={},
        total=1,
        rate=0.05,
        corrected_v=None,
        grade="good",
        recommendation="",
    )
    exp = build_v2_export(
        ds.data,
        participant_id="P01",
        preprocessing=pre,
        manual_added=manual_added,
        manual_removed=manual_removed,
    )
    return sorted(exp.sections["all"].final_artifacts.indices)


def test_export_folds_manual_added_and_removed():
    # algo {5}, add {10}, remove {5} -> {10}
    assert _export_indices({10}, {5}) == [10]


def test_export_keeps_algo_when_no_manual_edits():
    assert _export_indices(set(), set()) == [5]


def test_export_manual_added_only():
    # algo {5} + manual {8, 12} -> {5, 8, 12}
    assert _export_indices({8, 12}, set()) == [5, 8, 12]
