"""Tests for extracted HRV computation and result transforms."""

import numpy as np
import pytest

from rrational.analysis.hrv_metrics import ParticipantSectionResult
from rrational.analysis.hrv_compute import (
    calculate_hrv_metrics,
    results_to_long_df,
    results_to_wide_df,
    calculate_group_stats,
    FREQ_METHOD_NEUROKIT,
    FREQ_METHOD_KUBIOS,
    VALID_FREQ_METHODS,
    _hrv_frequency_kwargs,
)


def _make_rr(n: int = 400, ms: float = 800.0) -> list[float]:
    return [ms] * n


def _make_realistic_rr(
    n: int = 400, mean_ms: float = 800.0, sd_ms: float = 50.0
) -> list[float]:
    """Generate realistic RR intervals with variability and HF respiratory component."""
    rng = np.random.default_rng(42)
    t = np.arange(n) * mean_ms / 1000
    # 0.25 Hz HF respiratory variation + Gaussian noise
    hf = 20 * np.sin(2 * np.pi * 0.25 * t)
    noise = rng.normal(0, sd_ms, n)
    return (mean_ms + hf + noise).tolist()


class TestCalculateHrvMetrics:
    def test_basic_metrics(self):
        rr = _make_rr(200)
        metrics, std, n_win = calculate_hrv_metrics(rr, use_windows=False)
        assert "RMSSD" in metrics
        assert "SDNN" in metrics
        assert std is None
        assert n_win == 1

    def test_with_windows(self):
        rr = _make_rr(600)
        metrics, std, n_win = calculate_hrv_metrics(
            rr, use_windows=True, window_beats=200, overlap_pct=50.0
        )
        assert n_win >= 2
        assert std is not None

    def test_short_data_fallback(self):
        rr = _make_rr(50)
        metrics, std, n_win = calculate_hrv_metrics(rr, use_windows=True)
        assert n_win == 1  # too short for windows, falls back to single


class TestFrequencyMethod:
    def test_valid_methods_constant(self):
        assert FREQ_METHOD_NEUROKIT in VALID_FREQ_METHODS
        assert FREQ_METHOD_KUBIOS in VALID_FREQ_METHODS

    def test_neurokit_kwargs_empty(self):
        # Default NK2 path passes no extra kwargs
        assert _hrv_frequency_kwargs(FREQ_METHOD_NEUROKIT) == {}

    def test_kubios_kwargs_contain_kubios_params(self):
        kw = _hrv_frequency_kwargs(FREQ_METHOD_KUBIOS)
        assert kw["normalize"] is False, "Kubios mode must report absolute ms^2"
        assert kw["interpolation_rate"] == 4, "Kubios uses 4 Hz interpolation"
        assert kw["psd_method"] == "welch"
        # Task Force (1996): VLF starts at 0.0033 Hz (~5 min cycle), not 0
        assert kw["vlf"] == (0.0033, 0.04)
        assert kw["lf"] == (0.04, 0.15)
        assert kw["hf"] == (0.15, 0.40)

    def test_invalid_freq_method_raises(self):
        with pytest.raises(ValueError, match="freq_method"):
            calculate_hrv_metrics([800.0] * 100, freq_method="bogus")

    def test_kubios_vlf_band_starts_above_zero(self):
        """Task Force (1996): VLF lower bound is 0.0033 Hz, not 0 Hz.

        Including 0-0.0033 Hz pulls DC/ULF noise into the VLF estimate.
        """
        from rrational.analysis.hrv_compute import KUBIOS_BAND_VLF

        assert KUBIOS_BAND_VLF[0] >= 0.0033, (
            "VLF must not include 0-0.0033 Hz (DC/ULF) per Task Force 1996"
        )
        assert KUBIOS_BAND_VLF == (0.0033, 0.04)

    def test_kubios_mode_produces_absolute_ms2(self):
        """Kubios mode returns LF/HF as absolute ms² (typically > 1, often 100s)
        while NK2 default normalize=True returns small normalized values."""
        rr = _make_realistic_rr(400, mean_ms=800.0, sd_ms=50.0)
        freq_metrics = ["LF", "HF", "LF_HF"]
        m_nk, _, _ = calculate_hrv_metrics(
            rr,
            use_windows=False,
            selected_metrics=freq_metrics,
            freq_method=FREQ_METHOD_NEUROKIT,
        )
        m_k, _, _ = calculate_hrv_metrics(
            rr,
            use_windows=False,
            selected_metrics=freq_metrics,
            freq_method=FREQ_METHOD_KUBIOS,
        )
        # Both should produce non-None values
        assert m_nk["LF"] is not None and m_k["LF"] is not None
        # Kubios absolute ms² should be substantially larger than normalized NK2
        assert m_k["LF"] > m_nk["LF"], (
            f"Kubios LF={m_k['LF']} should exceed normalized NK2 LF={m_nk['LF']}"
        )
        assert m_k["HF"] > m_nk["HF"]

    def test_freq_method_does_not_affect_time_domain(self):
        rr = _make_realistic_rr(400)
        time_metrics = ["RMSSD", "SDNN", "MeanNN"]
        m_nk, _, _ = calculate_hrv_metrics(
            rr,
            use_windows=False,
            selected_metrics=time_metrics,
            freq_method=FREQ_METHOD_NEUROKIT,
        )
        m_k, _, _ = calculate_hrv_metrics(
            rr,
            use_windows=False,
            selected_metrics=time_metrics,
            freq_method=FREQ_METHOD_KUBIOS,
        )
        assert m_nk["RMSSD"] == pytest.approx(m_k["RMSSD"])
        assert m_nk["SDNN"] == pytest.approx(m_k["SDNN"])


class TestResultTransforms:
    def _results(self) -> list[ParticipantSectionResult]:
        return [
            ParticipantSectionResult(
                participant_id="001",
                group="A",
                section_name="rest",
                n_beats=500,
                duration_s=400.0,
                quality_grade="good",
                artifact_rate=0.01,
                hrv_metrics={"RMSSD": 42.0, "SDNN": 55.0},
                hrv_std=None,
                n_windows=1,
            ),
            ParticipantSectionResult(
                participant_id="002",
                group="A",
                section_name="rest",
                n_beats=600,
                duration_s=480.0,
                quality_grade="good",
                artifact_rate=0.02,
                hrv_metrics={"RMSSD": 38.0, "SDNN": 50.0},
                hrv_std=None,
                n_windows=1,
            ),
        ]

    def test_long_df(self):
        df = results_to_long_df(self._results())
        assert len(df) == 2
        assert "rmssd" in df.columns
        assert "participant_id" in df.columns

    def test_wide_df(self):
        df = results_to_wide_df(self._results())
        assert len(df) == 2
        assert "rest_rmssd" in df.columns

    def test_group_stats(self):
        long_df = results_to_long_df(self._results())
        stats = calculate_group_stats(long_df)
        assert len(stats) > 0
        assert "mean" in stats.columns
        assert "sd" in stats.columns
