"""HRV metric computation and result transformation.

Pure algorithms — no Streamlit dependency. Uses NeuroKit2 for HRV calculation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from rrational.analysis.hrv_metrics import (
    HRV_METRICS_CATALOG,
    HRV_METRIC_PRESETS,
    MIN_BEATS_FREQUENCY_DOMAIN,
    ParticipantSectionResult,
    generate_overlapping_windows_beats,
)


def _get_neurokit():
    """Lazy import NeuroKit2."""
    import neurokit2 as nk
    return nk


def calculate_hrv_metrics(
    nn_ms_list: list[float],
    use_windows: bool = True,
    window_beats: int = 300,
    overlap_pct: float = 75.0,
    selected_metrics: list[str] | None = None,
    window_s: float | None = None,
    segments: list | None = None,
) -> tuple[dict, dict | None, int]:
    """Calculate HRV metrics from NN intervals.

    Args:
        nn_ms_list: NN interval values in ms.
        use_windows: Whether to use overlapping windows.
        window_beats: Beats per window (legacy, prefer window_s).
        overlap_pct: Overlap percentage (0-100).
        selected_metrics: Metric names to calculate (None = basic).
        window_s: Window duration in seconds (time-based).
        segments: Pre-computed Segment objects from artifact detection.

    Returns:
        (metrics_dict, std_dict_or_None, n_windows)
    """
    nk = _get_neurokit()

    if selected_metrics is None:
        selected_metrics = HRV_METRIC_PRESETS["Basic"]["metrics"]

    time_basic = set(HRV_METRICS_CATALOG["time_basic"].keys())
    time_extended = set(HRV_METRICS_CATALOG["time_extended"].keys())
    frequency = set(HRV_METRICS_CATALOG["frequency"].keys())
    nonlinear = set(HRV_METRICS_CATALOG["nonlinear"].keys())

    selected_set = set(selected_metrics)
    need_time = bool(selected_set & (time_basic | time_extended))
    need_freq = bool(selected_set & frequency)
    need_nonlinear = bool(selected_set & nonlinear)

    def compute_hrv(rr_list: list[float]) -> dict:
        """Compute HRV for a single window."""
        result = {}
        peaks = nk.intervals_to_peaks(rr_list, sampling_rate=1000)

        if need_time:
            try:
                hrv_time = nk.hrv_time(peaks, sampling_rate=1000, show=False)
                for m in selected_set & time_basic:
                    if m == "MeanHR":
                        mean_nn = hrv_time.get("HRV_MeanNN", [None])[0]
                        result["MeanHR"] = 60000 / mean_nn if mean_nn and mean_nn > 0 else None
                    else:
                        result[m] = hrv_time.get(f"HRV_{m}", [None])[0]
                for m in selected_set & time_extended:
                    result[m] = hrv_time.get(f"HRV_{m}", [None])[0]
            except Exception:
                for m in selected_set & (time_basic | time_extended):
                    result[m] = None

        if need_freq and len(rr_list) >= MIN_BEATS_FREQUENCY_DOMAIN:
            try:
                hrv_freq = nk.hrv_frequency(peaks, sampling_rate=1000, show=False)
                for m in selected_set & frequency:
                    if m == "LF_HF":
                        result["LF_HF"] = hrv_freq.get("HRV_LFHF", [None])[0]
                    elif m == "TP":
                        vlf = hrv_freq.get("HRV_VLF", [0])[0] or 0
                        lf = hrv_freq.get("HRV_LF", [0])[0] or 0
                        hf = hrv_freq.get("HRV_HF", [0])[0] or 0
                        result["TP"] = vlf + lf + hf if any([vlf, lf, hf]) else None
                    else:
                        result[m] = hrv_freq.get(f"HRV_{m}", [None])[0]
            except Exception:
                for m in selected_set & frequency:
                    result[m] = None
        elif need_freq:
            for m in selected_set & frequency:
                result[m] = None

        if need_nonlinear:
            try:
                hrv_nl = nk.hrv_nonlinear(peaks, sampling_rate=1000, show=False)
                for m in selected_set & nonlinear:
                    result[m] = hrv_nl.get(f"HRV_{m}", [None])[0]
            except Exception:
                for m in selected_set & nonlinear:
                    result[m] = None

        return result

    # Single analysis (no windows)
    if not use_windows:
        return compute_hrv(nn_ms_list), None, 1

    # Build window slices from segments, time-based, or beat-based
    window_slices: list[list[float]] = []

    if segments is not None:
        nn_array = np.asarray(nn_ms_list, dtype=np.float64)
        for seg in segments:
            if getattr(seg, 'included', True):
                sliced = nn_array[seg.beat_start:seg.beat_end]
                if len(sliced) >= 30:
                    window_slices.append(sliced.tolist())

    elif window_s is not None:
        from rrational.gui.segmentation import generate_segments
        nn_array = np.asarray(nn_ms_list, dtype=np.float64)
        segs = generate_segments(nn_array, window_s=window_s, overlap_pct=overlap_pct)
        for seg in segs:
            sliced = nn_array[seg.beat_start:seg.beat_end]
            if len(sliced) >= 30:
                window_slices.append(sliced.tolist())

    else:
        min_beats = min(window_beats, len(nn_ms_list))
        if len(nn_ms_list) < min_beats:
            return compute_hrv(nn_ms_list), None, 1
        step_beats = max(1, int(window_beats * (1 - overlap_pct / 100)))
        windows = generate_overlapping_windows_beats(nn_ms_list, window_beats, step_beats)
        window_slices = [w_rr for _, _, w_rr in windows]

    if not window_slices:
        return compute_hrv(nn_ms_list), None, 1

    window_results = []
    for w_rr in window_slices:
        try:
            window_results.append(compute_hrv(w_rr))
        except Exception:
            continue

    if not window_results:
        return compute_hrv(nn_ms_list), None, 1

    metrics_df = pd.DataFrame(window_results)
    mean_metrics = {}
    std_metrics = {}
    for col in metrics_df.columns:
        values = metrics_df[col].dropna()
        if len(values) > 0:
            mean_metrics[col] = float(values.mean())
            std_metrics[col] = float(values.std()) if len(values) > 1 else 0.0
        else:
            mean_metrics[col] = None
            std_metrics[col] = None

    return mean_metrics, std_metrics, len(window_results)


# =============================================================================
# RESULT TRANSFORMATION
# =============================================================================


def results_to_long_df(results: list[ParticipantSectionResult]) -> pd.DataFrame:
    """Convert analysis results to long-format DataFrame."""
    rows = []
    for r in results:
        row = {
            "participant_id": r.participant_id,
            "group": r.group,
            "section": r.section_name,
            "data_source": r.data_source,
            "n_beats": r.n_beats,
            "duration_s": r.duration_s,
            "quality": r.quality_grade,
            "artifact_rate": r.artifact_rate,
            "n_windows": r.n_windows,
        }
        for key, value in r.hrv_metrics.items():
            row[key.lower()] = value
        if r.hrv_std:
            for key, value in r.hrv_std.items():
                row[f"{key.lower()}_sd"] = value
        rows.append(row)
    return pd.DataFrame(rows)


def results_to_wide_df(results: list[ParticipantSectionResult]) -> pd.DataFrame:
    """Convert analysis results to wide-format DataFrame."""
    participants = {}
    for r in results:
        if r.participant_id not in participants:
            participants[r.participant_id] = {"participant_id": r.participant_id, "group": r.group}
        prefix = r.section_name.replace(" ", "_").lower()
        for key, value in r.hrv_metrics.items():
            participants[r.participant_id][f"{prefix}_{key.lower()}"] = value
        participants[r.participant_id][f"{prefix}_n_beats"] = r.n_beats
        participants[r.participant_id][f"{prefix}_quality"] = r.quality_grade
        participants[r.participant_id][f"{prefix}_data_source"] = r.data_source
    return pd.DataFrame(list(participants.values()))


def calculate_group_stats(long_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate descriptive statistics per group and section."""
    exclude_cols = {"participant_id", "group", "section", "data_source", "n_beats",
                    "duration_s", "quality", "artifact_rate", "n_windows"}
    metrics = [col for col in long_df.columns
               if col not in exclude_cols and not col.endswith("_sd")]

    rows = []
    for (group, section), group_df in long_df.groupby(["group", "section"]):
        for metric in metrics:
            if metric not in group_df.columns:
                continue
            values = group_df[metric].dropna()
            if len(values) == 0:
                continue
            rows.append({
                "group": group, "section": section, "metric": metric.upper(),
                "n": len(values),
                "mean": round(values.mean(), 2),
                "sd": round(values.std(), 2) if len(values) > 1 else 0.0,
                "min": round(values.min(), 2),
                "max": round(values.max(), 2),
            })
    return pd.DataFrame(rows)
