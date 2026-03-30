"""Analysis modules for Music HRV."""

from rrational.analysis.music_sections import (
    ProtocolConfig,
    MusicSection,
    MusicSectionAnalysis,
    DurationMismatchStrategy,
    extract_music_sections,
    get_sections_by_music_type,
    get_sections_by_phase,
)

from rrational.analysis.hrv_metrics import (
    ParticipantSectionResult,
    HRV_METRICS_CATALOG,
    HRV_METRIC_PRESETS,
    ALL_HRV_METRICS,
    HRV_REFERENCE_VALUES,
    MIN_BEATS_TIME_DOMAIN,
    MIN_BEATS_FREQUENCY_DOMAIN,
    MIN_DURATION_FREQUENCY_DOMAIN_SEC,
    get_metric_info,
    format_power,
    format_duration,
    generate_overlapping_windows_time,
    generate_overlapping_windows_beats,
    generate_overlapping_windows,
    aggregate_hrv_results,
)

from rrational.analysis.hrv_compute import (
    calculate_hrv_metrics,
    results_to_long_df,
    results_to_wide_df,
    calculate_group_stats,
)

__all__ = [
    # music_sections
    "ProtocolConfig",
    "MusicSection",
    "MusicSectionAnalysis",
    "DurationMismatchStrategy",
    "extract_music_sections",
    "get_sections_by_music_type",
    "get_sections_by_phase",
    # hrv_metrics
    "ParticipantSectionResult",
    "HRV_METRICS_CATALOG",
    "HRV_METRIC_PRESETS",
    "ALL_HRV_METRICS",
    "HRV_REFERENCE_VALUES",
    "MIN_BEATS_TIME_DOMAIN",
    "MIN_BEATS_FREQUENCY_DOMAIN",
    "MIN_DURATION_FREQUENCY_DOMAIN_SEC",
    "get_metric_info",
    "format_power",
    "format_duration",
    "generate_overlapping_windows_time",
    "generate_overlapping_windows_beats",
    "generate_overlapping_windows",
    "aggregate_hrv_results",
    # hrv_compute
    "calculate_hrv_metrics",
    "results_to_long_df",
    "results_to_wide_df",
    "calculate_group_stats",
]
