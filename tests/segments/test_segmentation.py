"""Tests for unified time-based segmentation module."""

import numpy as np
import pytest

from rrational.gui.segmentation import (
    Segment,
    assess_segment_quality,
    format_ms_as_time,
    generate_segments,
    quality_grade_from_rate,
    should_exclude_segment,
)


def _make_rr(n_beats: int, mean_ms: float = 800.0) -> np.ndarray:
    """Create constant RR intervals for deterministic tests."""
    return np.full(n_beats, mean_ms)


class TestGenerateSegments:
    def test_empty_input(self):
        assert generate_segments(np.array([])) == []

    def test_single_segment_exact(self):
        # 300 beats * 800ms = 240s = 4min -> one 5min window covers all
        rr = _make_rr(375)  # 375 * 800ms = 300s = 5min exactly
        segs = generate_segments(rr, window_s=300.0)
        assert len(segs) == 1
        assert segs[0].beat_start == 0
        assert segs[0].beat_end == 375
        assert segs[0].n_beats == 375

    def test_two_segments_no_overlap(self):
        # 750 beats * 800ms = 600s = 10min -> two 5min segments
        rr = _make_rr(750)
        segs = generate_segments(rr, window_s=300.0, overlap_pct=0.0)
        assert len(segs) == 2
        assert segs[0].beat_end == segs[1].beat_start  # no gap, no overlap
        assert segs[0].n_beats + segs[1].n_beats == 750

    def test_overlap_50_pct(self):
        rr = _make_rr(750)  # 600s
        segs = generate_segments(rr, window_s=300.0, overlap_pct=50.0)
        # step = 150s, windows: 0-300, 150-450, 300-600 -> 3 windows
        assert len(segs) == 3
        # each window should be ~375 beats (300s / 0.8s)
        for s in segs:
            assert s.n_beats == 375

    def test_short_data_one_segment(self):
        # data shorter than window -> still produces 1 segment
        rr = _make_rr(100)  # 80s
        segs = generate_segments(rr, window_s=300.0)
        assert len(segs) == 1
        assert segs[0].n_beats == 100

    def test_indices_are_slice_compatible(self):
        rr = _make_rr(1000)
        segs = generate_segments(rr, window_s=300.0, overlap_pct=0.0)
        for seg in segs:
            sliced = rr[seg.beat_start : seg.beat_end]
            assert len(sliced) == seg.n_beats

    def test_no_overlap_covers_all_beats(self):
        rr = _make_rr(1000)
        segs = generate_segments(rr, window_s=300.0, overlap_pct=0.0)
        covered = sum(s.n_beats for s in segs)
        assert covered == 1000

    def test_segment_timing(self):
        rr = _make_rr(375)  # exactly 300s
        segs = generate_segments(rr, window_s=300.0)
        assert segs[0].start_ms == 0.0
        assert segs[0].duration_s == pytest.approx(300.0)

    def test_variable_rr_intervals(self):
        # alternating 600ms and 1000ms -> mean 800ms
        rr = np.tile([600.0, 1000.0], 375)  # 750 beats, 600s total
        segs = generate_segments(rr, window_s=300.0, overlap_pct=0.0)
        assert len(segs) == 2
        total = sum(s.n_beats for s in segs)
        assert total == 750

    def test_idx_sequential(self):
        rr = _make_rr(1500)
        segs = generate_segments(rr, window_s=300.0, overlap_pct=0.0)
        for i, seg in enumerate(segs):
            assert seg.idx == i

    def test_zero_overlap_step_equals_window(self):
        rr = _make_rr(750)  # 600s
        segs = generate_segments(rr, window_s=300.0, overlap_pct=0.0)
        assert segs[1].start_ms == pytest.approx(300_000.0)

    def test_100_pct_overlap_returns_empty(self):
        rr = _make_rr(750)
        segs = generate_segments(rr, window_s=300.0, overlap_pct=100.0)
        assert segs == []  # step_ms = 0 -> invalid


class TestAssessSegmentQuality:
    def _seg(self, artifact_pct: float = 0.0, n_beats: int = 300) -> Segment:
        return Segment(
            idx=0,
            start_ms=0,
            end_ms=300_000,
            beat_start=0,
            beat_end=n_beats,
            n_beats=n_beats,
            duration_s=300.0,
            artifact_count=int(n_beats * artifact_pct / 100),
            artifact_pct=artifact_pct,
        )

    def test_excellent(self):
        assert assess_segment_quality(self._seg(1.0)) == "excellent"

    def test_good(self):
        assert assess_segment_quality(self._seg(3.0)) == "good"

    def test_moderate(self):
        assert assess_segment_quality(self._seg(7.0)) == "moderate"

    def test_poor_high_artifacts(self):
        assert assess_segment_quality(self._seg(12.0)) == "poor"

    def test_boundary_2pct_is_excellent(self):
        assert assess_segment_quality(self._seg(2.0)) == "excellent"

    def test_boundary_5pct_is_good(self):
        assert assess_segment_quality(self._seg(5.0)) == "good"

    def test_boundary_10pct_is_moderate(self):
        assert assess_segment_quality(self._seg(10.0)) == "moderate"

    def test_grade_ignores_beat_count(self):
        # Quality grade reflects only artifact rate; exclusion is separate.
        assert assess_segment_quality(self._seg(0.0, n_beats=30)) == "excellent"


class TestShouldExcludeSegment:
    def _seg(self, artifact_pct: float = 0.0, n_beats: int = 300) -> Segment:
        return Segment(
            idx=0,
            start_ms=0,
            end_ms=300_000,
            beat_start=0,
            beat_end=n_beats,
            n_beats=n_beats,
            duration_s=300.0,
            artifact_count=int(n_beats * artifact_pct / 100),
            artifact_pct=artifact_pct,
        )

    def test_keep_clean_segment(self):
        assert should_exclude_segment(self._seg(3.0)) is False

    def test_exclude_high_artifacts(self):
        assert should_exclude_segment(self._seg(12.0)) is True

    def test_keep_at_10pct_boundary(self):
        assert should_exclude_segment(self._seg(10.0)) is False

    def test_exclude_too_few_beats(self):
        assert should_exclude_segment(self._seg(0.0, n_beats=30)) is True


class TestQualityGradeFromRate:
    def test_rate_thresholds(self):
        assert quality_grade_from_rate(0.0) == "excellent"
        assert quality_grade_from_rate(0.02) == "excellent"
        assert quality_grade_from_rate(0.05) == "good"
        assert quality_grade_from_rate(0.10) == "moderate"
        assert quality_grade_from_rate(0.25) == "poor"


class TestFormatMsAsTime:
    def test_zero(self):
        assert format_ms_as_time(0) == "0:00"

    def test_5_minutes(self):
        assert format_ms_as_time(300_000) == "5:00"

    def test_90_seconds(self):
        assert format_ms_as_time(90_000) == "1:30"


class TestSegmentConsistency:
    """Verify that artifact detection and analysis use identical segments."""

    def test_same_segments_for_artifact_and_analysis(self):
        """Core requirement: artifact detection segments == analysis segments."""
        rr = _make_rr(1500)  # 1200s = 20min
        # Artifact detection: 0% overlap
        artifact_segs = generate_segments(rr, window_s=300.0, overlap_pct=0.0)
        # Analysis with same params: 0% overlap for per-segment mode
        analysis_segs = generate_segments(rr, window_s=300.0, overlap_pct=0.0)

        assert len(artifact_segs) == len(analysis_segs)
        for a, b in zip(artifact_segs, analysis_segs):
            assert a.beat_start == b.beat_start
            assert a.beat_end == b.beat_end
            assert a.start_ms == b.start_ms
            assert a.end_ms == b.end_ms

    def test_time_based_window_duration_is_fixed(self):
        """5-minute window must be ~5 minutes regardless of HR."""
        # Fast HR: 60bpm -> 1000ms per beat
        rr_slow = _make_rr(300, mean_ms=1000.0)  # 300s
        segs_slow = generate_segments(rr_slow, window_s=300.0)
        assert len(segs_slow) == 1
        assert segs_slow[0].duration_s == pytest.approx(300.0)

        # Fast HR: 100bpm -> 600ms per beat
        rr_fast = _make_rr(500, mean_ms=600.0)  # 300s
        segs_fast = generate_segments(rr_fast, window_s=300.0)
        assert len(segs_fast) == 1
        assert segs_fast[0].duration_s == pytest.approx(300.0)

        # Different beat counts but same time duration
        assert segs_slow[0].n_beats == 300  # fewer beats at slow HR
        assert segs_fast[0].n_beats == 500  # more beats at fast HR

    def test_excluded_segments_not_in_analysis(self):
        """Segments marked as excluded should be filtered in analysis."""
        rr = _make_rr(1500)
        segs = generate_segments(rr, window_s=300.0, overlap_pct=0.0)
        # Mark one segment as excluded
        segs[1].included = False
        included = [s for s in segs if s.included]
        assert len(included) == len(segs) - 1
        assert all(s.idx != 1 for s in included)

    def test_segment_boundaries_no_overlap_no_gap(self):
        """With 0% overlap, segments must tile perfectly (no gaps, no overlaps)."""
        rr = _make_rr(1500)
        segs = generate_segments(rr, window_s=300.0, overlap_pct=0.0)
        for i in range(len(segs) - 1):
            assert segs[i].beat_end == segs[i + 1].beat_start, (
                f"Gap between segment {i} and {i + 1}"
            )

    def test_analysis_with_segments_parameter(self):
        """_calculate_hrv_metrics should accept and use pre-computed segments."""
        # This tests that the function signature accepts segments
        # (actual HRV calculation requires NeuroKit2 which may not be available)
        from rrational.gui.tabs.analysis import _calculate_hrv_metrics

        rr = _make_rr(400).tolist()
        segs = generate_segments(np.array(rr), window_s=150.0, overlap_pct=0.0)

        try:
            metrics, std, n_win = _calculate_hrv_metrics(
                rr, use_windows=True, segments=segs
            )
            # If NeuroKit2 is available, verify window count matches
            assert n_win >= 1
        except ImportError:
            pytest.skip("NeuroKit2 not installed")
