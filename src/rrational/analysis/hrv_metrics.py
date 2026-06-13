"""HRV metric definitions, catalogs, presets, and window generation.

Pure data and algorithms — no Streamlit dependency.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


# =============================================================================
# DATA STRUCTURES
# =============================================================================


@dataclass
class ParticipantSectionResult:
    """Result of HRV analysis for one participant-section combination."""

    participant_id: str
    group: str
    section_name: str
    n_beats: int
    duration_s: float
    quality_grade: str
    artifact_rate: float
    hrv_metrics: dict
    hrv_std: dict | None
    n_windows: int
    data_source: str = "NN"


# =============================================================================
# HRV METRIC CATALOG
# =============================================================================

HRV_METRICS_CATALOG = {
    "time_basic": {
        "RMSSD": {
            "label": "RMSSD",
            "unit": "ms",
            "description": "Root mean square of successive differences",
        },
        "SDNN": {
            "label": "SDNN",
            "unit": "ms",
            "description": "Standard deviation of NN intervals",
        },
        "pNN50": {
            "label": "pNN50",
            "unit": "%",
            "description": "Percentage of successive intervals differing by >50ms",
        },
        "MeanNN": {
            "label": "Mean NN",
            "unit": "ms",
            "description": "Mean of NN intervals",
        },
        "MeanHR": {"label": "Mean HR", "unit": "bpm", "description": "Mean heart rate"},
    },
    "time_extended": {
        "SDSD": {
            "label": "SDSD",
            "unit": "ms",
            "description": "SD of successive differences",
        },
        "pNN20": {
            "label": "pNN20",
            "unit": "%",
            "description": "Percentage of successive intervals differing by >20ms",
        },
        "MedianNN": {
            "label": "Median NN",
            "unit": "ms",
            "description": "Median of NN intervals",
        },
        "CVNN": {
            "label": "CVNN",
            "unit": "",
            "description": "Coefficient of variation (SDNN/MeanNN)",
        },
        "CVSD": {
            "label": "CVSD",
            "unit": "",
            "description": "Coefficient of variation of successive differences",
        },
        "MadNN": {
            "label": "MadNN",
            "unit": "ms",
            "description": "Median absolute deviation of NN intervals",
        },
        "MCVNN": {
            "label": "MCVNN",
            "unit": "",
            "description": "Median-based CV (MadNN/MedianNN)",
        },
        "IQRNN": {
            "label": "IQRNN",
            "unit": "ms",
            "description": "Interquartile range of NN intervals",
        },
        "HTI": {"label": "HTI", "unit": "", "description": "HRV Triangular Index"},
        "TINN": {
            "label": "TINN",
            "unit": "ms",
            "description": "Triangular interpolation of NN histogram",
        },
    },
    "frequency": {
        "VLF": {
            "label": "VLF",
            "unit": "ms\u00b2",
            "description": "Very low frequency power (0.0033-0.04 Hz)",
        },
        "LF": {
            "label": "LF",
            "unit": "ms\u00b2",
            "description": "Low frequency power (0.04-0.15 Hz)",
        },
        "HF": {
            "label": "HF",
            "unit": "ms\u00b2",
            "description": "High frequency power (0.15-0.4 Hz)",
        },
        "LF_HF": {"label": "LF/HF", "unit": "", "description": "LF to HF ratio"},
        "LFn": {
            "label": "LF norm",
            "unit": "n.u.",
            "description": "Normalized LF power",
        },
        "HFn": {
            "label": "HF norm",
            "unit": "n.u.",
            "description": "Normalized HF power",
        },
        "TP": {
            "label": "Total Power",
            "unit": "ms\u00b2",
            "description": "Total spectral power",
        },
    },
    "nonlinear": {
        "SD1": {
            "label": "SD1",
            "unit": "ms",
            "description": "Poincar\u00e9 plot SD perpendicular to identity line",
        },
        "SD2": {
            "label": "SD2",
            "unit": "ms",
            "description": "Poincar\u00e9 plot SD along identity line",
        },
        "SD1SD2": {
            "label": "SD1/SD2",
            "unit": "",
            "description": "Ratio of SD1 to SD2",
        },
        "ApEn": {"label": "ApEn", "unit": "", "description": "Approximate entropy"},
        "SampEn": {"label": "SampEn", "unit": "", "description": "Sample entropy"},
        "DFA_alpha1": {
            "label": "DFA \u03b11",
            "unit": "",
            "description": "Detrended fluctuation analysis short-term",
        },
        "DFA_alpha2": {
            "label": "DFA \u03b12",
            "unit": "",
            "description": "Detrended fluctuation analysis long-term",
        },
    },
}

HRV_METRIC_PRESETS = {
    "Basic": {
        "description": "Essential time-domain metrics for quick analysis",
        "metrics": ["RMSSD", "SDNN", "pNN50", "MeanNN", "MeanHR"],
    },
    "Time + Frequency": {
        "description": "Time-domain and frequency-domain metrics",
        "metrics": [
            "RMSSD",
            "SDNN",
            "pNN50",
            "MeanNN",
            "MeanHR",
            "LF",
            "HF",
            "LF_HF",
            "VLF",
            "TP",
        ],
    },
    "Full (with nonlinear)": {
        "description": "All available metrics including nonlinear analysis",
        "metrics": list(
            {m for cat in HRV_METRICS_CATALOG.values() for m in cat.keys()}
        ),
    },
    "Poincar\u00e9 Focus": {
        "description": "Metrics related to Poincar\u00e9 plot analysis",
        "metrics": ["RMSSD", "SDNN", "SD1", "SD2", "SD1SD2", "MeanNN", "MeanHR"],
    },
    "Custom": {
        "description": "Select metrics manually",
        "metrics": [],
    },
}

ALL_HRV_METRICS = {
    m: info for cat in HRV_METRICS_CATALOG.values() for m, info in cat.items()
}

# Reference values (Shaffer & Ginsberg 2017, Nunan et al. 2010)
HRV_REFERENCE_VALUES = {
    "RMSSD": {
        "low": 20,
        "normal": 42,
        "high": 70,
        "unit": "ms",
        "interpretation": {
            "low": "Reduced parasympathetic activity",
            "normal": "Normal vagal tone",
            "high": "High parasympathetic activity",
        },
    },
    "SDNN": {
        "low": 50,
        "normal": 141,
        "high": 200,
        "unit": "ms",
        "interpretation": {
            "low": "Reduced overall HRV",
            "normal": "Normal overall variability",
            "high": "High overall variability",
        },
    },
    "pNN50": {"low": 3, "normal": 20, "high": 40, "unit": "%"},
    "LF_HF": {"low": 0.5, "normal": 1.5, "high": 3.0, "unit": ""},
}

# Minimum data requirements (Quigley et al. 2024)
MIN_BEATS_TIME_DOMAIN = 100
MIN_BEATS_FREQUENCY_DOMAIN = 300
MIN_DURATION_FREQUENCY_DOMAIN_SEC = 120


def get_metric_info(metric_name: str) -> dict:
    """Get info dict for a metric by name."""
    return ALL_HRV_METRICS.get(
        metric_name, {"label": metric_name, "unit": "", "description": ""}
    )


# =============================================================================
# FORMATTING UTILITIES
# =============================================================================


def format_power(value: float, unit: str = "ms\u00b2") -> str:
    """Format power values — show decimals for small values."""
    if value >= 10:
        return f"{value:.0f} {unit}"
    elif value >= 1:
        return f"{value:.1f} {unit}"
    elif value >= 0.1:
        return f"{value:.2f} {unit}"
    else:
        return f"{value:.3f} {unit}"


def format_duration(seconds: float) -> str:
    """Format seconds to human-readable string (e.g. '1m 5s')."""
    if seconds < 0:
        return "0s"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


# =============================================================================
# OVERLAPPING WINDOW GENERATION
# =============================================================================


def generate_overlapping_windows_time(
    rr_intervals: list,
    window_duration_ms: float,
    step_size_ms: float,
) -> list[tuple[int, float, list]]:
    """Generate overlapping windows from RR intervals (time-based).

    Returns list of (window_idx, window_start_ms, window_rr_list).
    """
    if not rr_intervals:
        return []

    if hasattr(rr_intervals[0], "rr_ms"):
        rr_values = [rr.rr_ms for rr in rr_intervals]
    else:
        rr_values = list(rr_intervals)

    cumulative_time = [0.0]
    for rr in rr_values[:-1]:
        cumulative_time.append(cumulative_time[-1] + rr)

    total_duration_ms = cumulative_time[-1] + rr_values[-1]

    windows = []
    window_idx = 0
    window_start = 0.0

    while window_start + window_duration_ms <= total_duration_ms + step_size_ms / 2:
        window_end = window_start + window_duration_ms
        window_rr = [
            rr
            for elapsed, rr in zip(cumulative_time, rr_values)
            if window_start <= elapsed < window_end
        ]

        if window_rr:
            windows.append((window_idx, window_start, window_rr))
            window_idx += 1

        window_start += step_size_ms
        # Round 28 — was a silent break at 100 windows. A 60 min recording
        # at 30 s windows / 90 % overlap legitimately produces 700+ windows
        # and the cap quietly corrupted the aggregated mean / SD. Log the
        # cap hit so the caller knows truncation occurred; default raised
        # to a much higher bound so typical clinical workflows aren't
        # affected.
        if window_idx > 10_000:
            import logging

            logging.getLogger("rrational.analysis.hrv_metrics").warning(
                "generate_overlapping_windows_time hit the 10000-window "
                "safety cap on a %s ms recording; further windows dropped.",
                int(total_duration_ms),
            )
            break

    return windows


def generate_overlapping_windows_beats(
    rr_intervals: list,
    window_beats: int,
    step_beats: int,
) -> list[tuple[int, int, list]]:
    """Generate overlapping windows from RR intervals (beat-based).

    Returns list of (window_idx, start_beat_idx, window_rr_list).
    """
    if not rr_intervals:
        return []

    if hasattr(rr_intervals[0], "rr_ms"):
        rr_values = [rr.rr_ms for rr in rr_intervals]
    else:
        rr_values = list(rr_intervals)

    total_beats = len(rr_values)
    windows = []
    window_idx = 0
    start_beat = 0

    while start_beat + window_beats <= total_beats:
        end_beat = start_beat + window_beats
        windows.append((window_idx, start_beat, rr_values[start_beat:end_beat]))
        window_idx += 1
        start_beat += step_beats
        # Round 28 — see generate_overlapping_windows_time. Same silent
        # 100-cap promoted to 10 000 with a logged warning.
        if window_idx > 10_000:
            import logging

            logging.getLogger("rrational.analysis.hrv_metrics").warning(
                "generate_overlapping_windows_beats hit the 10000-window "
                "safety cap on %d-beat input; further windows dropped.",
                total_beats,
            )
            break

    return windows


# Backward-compatible alias
def generate_overlapping_windows(
    rr_intervals: list,
    window_duration_ms: float,
    step_size_ms: float,
) -> list[tuple[int, float, list]]:
    """Backward-compatible alias for generate_overlapping_windows_time."""
    return generate_overlapping_windows_time(
        rr_intervals, window_duration_ms, step_size_ms
    )


def aggregate_hrv_results(
    window_results: list[pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aggregate HRV results from multiple overlapping windows.

    Returns (mean_results, std_results) DataFrames.
    """
    if not window_results:
        return pd.DataFrame(), pd.DataFrame()

    all_results = pd.concat(window_results, ignore_index=True)
    mean_results = all_results.mean().to_frame().T
    std_results = all_results.std().to_frame().T
    return mean_results, std_results
