"""Scoping regression test for gui/tabs/analysis.py."""

from __future__ import annotations


def test_path_is_not_shadowed_in_single_participant_analysis():
    """A ``from pathlib import Path`` inside _render_single_participant_analysis
    made ``Path`` a LOCAL name for the whole function, so the earlier VNS
    re-discovery (``Path(st.session_state.data_dir)``, ready-file branch)
    raised UnboundLocalError. The module-level import must be used."""
    from rrational.gui.tabs import analysis

    code = analysis._render_single_participant_analysis.__code__
    assert "Path" not in code.co_varnames


def test_poor_quality_reason_uses_documented_boundary():
    from rrational.gui.tabs.analysis import _poor_quality_reason

    assert _poor_quality_reason({"artifact_rate": 0.10}) is None  # moderate
    assert _poor_quality_reason({"artifact_rate": 0.1001}).startswith("Excluded: Poor")
    assert _poor_quality_reason({"artifact_rate": 0.25}) == (
        "Excluded: Poor quality (25.0% artifacts)"
    )
    # A known rate wins over a stale grade; without a rate the grade decides.
    assert _poor_quality_reason({"artifact_rate": 0.03, "quality_grade": "poor"}) is None
    assert _poor_quality_reason({"quality_grade": "poor"}) == "Excluded: Poor quality"
    assert _poor_quality_reason({"quality_grade": "raw"}) is None
    assert _poor_quality_reason({}) is None


def test_hrv_freq_kubios_mode_uses_documented_pipeline(monkeypatch):
    """Single-participant Kubios mode must use the validated Kubios-aligned
    pipeline (_compute_kubios_frequency_powers: smoothness-priors detrending,
    180 s Welch), like group/sequence analysis. It called NK2 hrv_frequency
    with Kubios-like kwargs instead (no detrending: VLF ~4x too high)."""
    import neurokit2 as nk
    import numpy as np
    import pytest

    from rrational.analysis.hrv_compute import _compute_kubios_frequency_powers
    from rrational.gui.tabs import analysis

    monkeypatch.setattr(analysis, "_current_freq_method", lambda: "kubios")
    rng = np.random.default_rng(0)
    rr = (800 + rng.normal(0, 40, 600) + np.linspace(-60, 60, 600)).round().tolist()
    peaks = nk.intervals_to_peaks(rr, sampling_rate=1000)
    out = analysis._hrv_freq(peaks)
    ref = _compute_kubios_frequency_powers(np.diff(peaks).tolist())
    for col, key in [("HRV_VLF", "VLF"), ("HRV_LF", "LF"), ("HRV_HF", "HF"),
                     ("HRV_LFHF", "LF_HF"), ("HRV_LFn", "LFn"), ("HRV_HFn", "HFn"),
                     ("HRV_TP", "TP")]:
        assert out[col][0] == pytest.approx(ref[key]), col
