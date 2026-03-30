"""Tests for extracted HRV computation and result transforms."""

import pandas as pd
import pytest

from rrational.analysis.hrv_metrics import ParticipantSectionResult
from rrational.analysis.hrv_compute import (
    calculate_hrv_metrics,
    results_to_long_df,
    results_to_wide_df,
    calculate_group_stats,
)


def _make_rr(n: int = 400, ms: float = 800.0) -> list[float]:
    return [ms] * n


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


class TestResultTransforms:
    def _results(self) -> list[ParticipantSectionResult]:
        return [
            ParticipantSectionResult(
                participant_id="001", group="A", section_name="rest",
                n_beats=500, duration_s=400.0, quality_grade="good",
                artifact_rate=0.01, hrv_metrics={"RMSSD": 42.0, "SDNN": 55.0},
                hrv_std=None, n_windows=1,
            ),
            ParticipantSectionResult(
                participant_id="002", group="A", section_name="rest",
                n_beats=600, duration_s=480.0, quality_grade="good",
                artifact_rate=0.02, hrv_metrics={"RMSSD": 38.0, "SDNN": 50.0},
                hrv_std=None, n_windows=1,
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
