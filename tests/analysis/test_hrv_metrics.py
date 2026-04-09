"""Tests for extracted HRV metric definitions and utilities."""

import pandas as pd
import pytest

from rrational.analysis.hrv_metrics import (
    ALL_HRV_METRICS,
    HRV_METRICS_CATALOG,
    HRV_METRIC_PRESETS,
    HRV_REFERENCE_VALUES,
    MIN_BEATS_FREQUENCY_DOMAIN,
    MIN_BEATS_TIME_DOMAIN,
    ParticipantSectionResult,
    aggregate_hrv_results,
    format_duration,
    format_power,
    generate_overlapping_windows_beats,
    generate_overlapping_windows_time,
    get_metric_info,
)


class TestMetricCatalog:
    def test_all_categories_present(self):
        assert set(HRV_METRICS_CATALOG.keys()) == {"time_basic", "time_extended", "frequency", "nonlinear"}

    def test_all_metrics_flattened(self):
        total = sum(len(cat) for cat in HRV_METRICS_CATALOG.values())
        assert len(ALL_HRV_METRICS) == total

    def test_basic_preset_has_5_metrics(self):
        assert len(HRV_METRIC_PRESETS["Basic"]["metrics"]) == 5

    def test_reference_values_have_required_keys(self):
        for name, ref in HRV_REFERENCE_VALUES.items():
            assert "low" in ref and "normal" in ref and "high" in ref

    def test_get_metric_info_known(self):
        info = get_metric_info("RMSSD")
        assert info["unit"] == "ms"

    def test_get_metric_info_unknown(self):
        info = get_metric_info("NONEXISTENT")
        assert info["label"] == "NONEXISTENT"

    def test_min_beats_constants(self):
        assert MIN_BEATS_TIME_DOMAIN == 100
        assert MIN_BEATS_FREQUENCY_DOMAIN == 300


class TestFormatting:
    def test_format_power_large(self):
        assert format_power(42.0) == "42 ms\u00b2"

    def test_format_power_small(self):
        assert "0.05" in format_power(0.05)

    def test_format_duration_seconds(self):
        assert format_duration(5.0) == "5s"

    def test_format_duration_minutes(self):
        assert format_duration(65.0) == "1m 5s"

    def test_format_duration_hours(self):
        assert format_duration(3665.0) == "1h 1m 5s"

    def test_format_duration_negative(self):
        assert format_duration(-1.0) == "0s"


class TestWindowGeneration:
    def _rr(self, n: int, ms: float = 800.0) -> list[float]:
        return [ms] * n

    def test_time_windows_basic(self):
        rr = self._rr(750)  # 600s
        windows = generate_overlapping_windows_time(rr, 300_000, 150_000)
        assert len(windows) >= 2

    def test_beat_windows_basic(self):
        rr = self._rr(600)
        windows = generate_overlapping_windows_beats(rr, 300, 75)
        assert len(windows) == 5  # starts at 0,75,150,225,300

    def test_empty_input(self):
        assert generate_overlapping_windows_time([], 300_000, 150_000) == []
        assert generate_overlapping_windows_beats([], 300, 75) == []

    def test_aggregate_results(self):
        df1 = pd.DataFrame({"RMSSD": [40.0], "SDNN": [50.0]})
        df2 = pd.DataFrame({"RMSSD": [44.0], "SDNN": [54.0]})
        mean_df, std_df = aggregate_hrv_results([df1, df2])
        assert mean_df["RMSSD"].iloc[0] == pytest.approx(42.0)

    def test_aggregate_empty(self):
        mean_df, std_df = aggregate_hrv_results([])
        assert mean_df.empty


class TestParticipantSectionResult:
    def test_creation(self):
        r = ParticipantSectionResult(
            participant_id="001", group="A", section_name="rest",
            n_beats=500, duration_s=400.0, quality_grade="good",
            artifact_rate=0.01, hrv_metrics={"RMSSD": 42.0},
            hrv_std=None, n_windows=1,
        )
        assert r.data_source == "NN"
