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


# ---------------------------------------------------------------------
# Lipponen-Tarvainen: corrected series with its own (longer) time axis
# ---------------------------------------------------------------------
def test_slice_section_selects_corrected_beats_by_their_own_time():
    from rrational.inspector.tabs.analysis_tab import _corrected_kwargs

    ds = _one_section_dataset(12)
    t = ds.data.t
    # A missed beat split in two: one extra corrected beat at t[5] - 0.5 s.
    corr_t = np.sort(np.append(t, t[5] - 0.5))
    corr_v = np.full(len(corr_t), 400.0)
    ds.corrected_v, ds.corrected_t, ds.use_corrected = corr_v, corr_t, True

    rr = _slice_section(ds.data, "all", **_corrected_kwargs(ds))
    assert len(rr) == 13 and np.all(rr == 400.0)


def test_corrected_kwargs_are_empty_when_not_using_corrected():
    from rrational.inspector.tabs.analysis_tab import _corrected_kwargs

    ds = _one_section_dataset(12)
    ds.corrected_v = ds.data.v.copy()
    assert _corrected_kwargs(ds) == {"corrected_v": None, "corrected_t": None}


def test_export_writes_lt_corrected_series_with_its_own_length():
    """A missed beat split by L&T adds one NN interval to the section export;
    timestamps come from the corrected time axis and the corrections point at
    the raw beat that was split."""
    ds = _one_section_dataset(20)
    t, v = ds.data.t, ds.data.v.copy()
    v[10] = 1600.0
    ds.data.v[:] = v
    corr_t = np.sort(np.append(t, t[10] - 0.8))
    corr_v = np.full(len(corr_t), 800.0)
    flags = np.zeros(len(corr_t), dtype=bool)
    flags[[10, 11]] = True  # the two halves of the split beat
    pre = PreprocessingResult(
        indices=np.array([10], dtype=np.int64),
        by_type={"missed": 1},
        total=1,
        rate=0.05,
        corrected_v=corr_v,
        corrected_t=corr_t,
        corrected_flags=flags,
        n_inserted=1,
        grade="good",
        recommendation="",
    )
    exp = build_v2_export(ds.data, participant_id="P01", preprocessing=pre)
    nn = exp.sections["all"].nn_intervals
    assert len(nn.data) == 21
    assert [row[2] for row in nn.data].count(True) == 2
    assert {c["raw_idx"] for c in nn.corrections} == {10}
    assert all(c["original_rr_ms"] == 1600.0 for c in nn.corrections)
    ts_ms = [row[0] for row in nn.data]
    assert ts_ms[0] == 0 and all(a < b for a, b in zip(ts_ms, ts_ms[1:]))


# ---------------------------------------------------------------------
# Moderate (> 5 % artifacts) = time domain only, per section
# ---------------------------------------------------------------------
def test_section_artifact_rate_uses_detected_indices_in_section():
    from rrational.inspector.tabs.analysis_tab import _section_artifact_rate

    ds = _one_section_dataset(20)
    assert _section_artifact_rate(ds, "all") is None  # no detection yet
    ds.artifact_indices = np.array([2, 5, 30], dtype=np.int64)  # 30 is outside
    assert _section_artifact_rate(ds, "all") == 2 / 20
    assert _section_artifact_rate(ds, "missing") is None


def test_compute_withholds_frequency_metrics_above_five_percent():
    from rrational.inspector.tabs.analysis_tab import _compute_metrics_with_settings

    rng = np.random.default_rng(0)
    t = np.arange(900)
    rr = 800 + 40 * np.sin(t / 5) + 24 * np.sin(t / 23 + 1) + rng.normal(0, 15, 900)
    ok, _ = _compute_metrics_with_settings(rr, None, artifact_rate=0.03)
    gated, _ = _compute_metrics_with_settings(rr, None, artifact_rate=0.08)
    freq = [m for m in ok if m in ("LF", "HF", "LF_HF", "VLF", "TP")]
    assert freq, "default metric set should contain frequency metrics"
    assert all(np.isfinite(ok[m]) for m in freq)
    assert all(gated[m] is None or not np.isfinite(gated[m]) for m in freq)
    assert np.isfinite(gated["RMSSD"])
