from rrational.cleaning.rr import CleaningConfig, clean_rr_intervals, clean_rr_intervals_with_flags, rr_summary
from rrational.io.hrv_logger import RRInterval


def build_samples():
    return [
        RRInterval(timestamp=None, rr_ms=650, elapsed_ms=0),
        RRInterval(timestamp=None, rr_ms=120, elapsed_ms=650),
        RRInterval(timestamp=None, rr_ms=640, elapsed_ms=1290),
        RRInterval(timestamp=None, rr_ms=8000, elapsed_ms=1930),
        RRInterval(timestamp=None, rr_ms=630, elapsed_ms=2560),
    ]


def test_clean_rr_intervals_filters_outliers():
    samples = build_samples()
    cleaned, stats = clean_rr_intervals(samples, CleaningConfig(rr_min_ms=300, rr_max_ms=2000))

    assert len(cleaned) == 3
    assert stats.total_samples == 5
    assert stats.removed_samples == 2
    assert stats.reasons["out_of_range"] == 2
    assert stats.reasons["sudden_change"] == 0


def test_rr_summary_reports_min_max_mean_duration():
    samples = build_samples()
    cleaned, _ = clean_rr_intervals(samples, CleaningConfig(rr_min_ms=300, rr_max_ms=2000))
    summary = rr_summary(cleaned)

    assert summary["min"] == 630.0
    assert summary["max"] == 650.0
    # Duration calculated by summing RR intervals: 650 + 640 + 630 = 1920 ms = 1.92 s
    assert summary["duration_s"] == (650 + 640 + 630) / 1000


def test_clean_rr_intervals_with_flags_keeps_all():
    """Test that clean_rr_intervals_with_flags keeps all intervals but flags problematic ones."""
    samples = build_samples()
    flagged, stats = clean_rr_intervals_with_flags(samples, CleaningConfig(rr_min_ms=300, rr_max_ms=2000))

    # All 5 intervals should be returned (not removed)
    assert len(flagged) == 5

    # Stats should match regular clean_rr_intervals
    assert stats.total_samples == 5
    assert stats.removed_samples == 2
    assert stats.retained_samples == 3
    assert stats.reasons["out_of_range"] == 2

    # Check which ones are flagged
    flags = [f.is_flagged for f in flagged]
    assert flags == [False, True, False, True, False]  # 120 and 8000 are out of range

    # Flagged intervals should have reasons
    assert flagged[1].flag_reason == "out_of_range"
    assert flagged[3].flag_reason == "out_of_range"

    # Non-flagged should have no reason
    assert flagged[0].flag_reason is None
    assert flagged[2].flag_reason is None


def _series(*rr):
    return [RRInterval(timestamp=None, rr_ms=r, elapsed_ms=None) for r in rr]


def test_default_sudden_change_filter_is_disabled():
    """100 % (the default) means disabled, as the GUI slider help and the
    pipeline docs state: large jumps such as a missed beat (2x) are left for
    artifact detection, where Lipponen-Tarvainen correction splits them and
    they count toward the artifact rate. Previously 100 % still deleted any
    beat > 2x the previous one before detection could see it."""
    for series in ([800, 800, 1601, 800], [700, 700, 1700, 700], [800, 800, 399, 800, 800]):
        kept, stats = clean_rr_intervals(_series(*series))
        assert [s.rr_ms for s in kept] == series
        assert stats.reasons["sudden_change"] == 0
        flagged, fstats = clean_rr_intervals_with_flags(_series(*series))
        assert not any(f.is_flagged for f in flagged)


def test_thresholds_at_or_above_100_percent_are_disabled():
    # app.py's auto-load passed 100 (i.e. 10000 %): same meaning, disabled.
    for pct in (1.0, 1.5, 100):
        kept, _ = clean_rr_intervals(_series(800, 800, 1601, 800), CleaningConfig(sudden_change_pct=pct))
        assert len(kept) == 4


def test_explicit_threshold_removes_long_jumps():
    kept, stats = clean_rr_intervals(
        _series(800, 800, 1601, 800), CleaningConfig(sudden_change_pct=0.95)
    )
    assert [s.rr_ms for s in kept] == [800, 800, 800]
    assert stats.reasons["sudden_change"] == 1


def test_explicit_threshold_is_asymmetric_for_short_beats():
    """Documents current behaviour, not an endorsement: the rule
    |rr - prev| / prev > t can never fire for a SHORT beat when t >= ~0.5,
    so a premature 399 ms beat after 800 ms is kept and the healthy 800 ms
    beat after it is removed instead (800 / 399 > 1.95). If the rule is
    changed on purpose, update this test and processing-pipeline.md."""
    kept, stats = clean_rr_intervals(
        _series(800, 800, 399, 800, 800), CleaningConfig(sudden_change_pct=0.95)
    )
    assert [s.rr_ms for s in kept] == [800, 800, 399, 800]
    assert stats.reasons["sudden_change"] == 1
