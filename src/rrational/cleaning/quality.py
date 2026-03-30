"""Signal quality analysis: changepoint detection, time gaps, artifact detection.

Pure algorithms — no Streamlit dependency.
"""

from __future__ import annotations

import numpy as np


def _get_neurokit():
    """Lazy import NeuroKit2. Returns (nk_module, available_bool)."""
    try:
        import neurokit2 as nk
        return nk, True
    except ImportError:
        return None, False


def detect_quality_changepoints(rr_values: list[int], change_type: str = "var") -> dict:
    """Detect quality changepoints in RR interval data using NeuroKit2.

    Uses signal_changepoints() to find where signal properties change,
    which can indicate measurement issues, electrode problems, etc.

    Args:
        rr_values: RR interval values in ms.
        change_type: Type of change to detect ("var", "mean", or "meanvar").

    Returns:
        dict with changepoint_indices, n_segments, segment_stats, quality_score.
    """
    nk, available = _get_neurokit()
    empty = {"changepoint_indices": [], "n_segments": 1, "segment_stats": [], "quality_score": 100}

    if not available or len(rr_values) < 10:
        return empty

    try:
        rr_array = np.array(rr_values, dtype=float)
        changepoints = nk.signal_changepoints(rr_array, change=change_type, show=False)

        segment_stats = []
        all_indices = [0] + list(changepoints) + [len(rr_array)]
        for i in range(len(all_indices) - 1):
            segment = rr_array[all_indices[i]:all_indices[i + 1]]
            if len(segment) > 0:
                mean = float(np.mean(segment))
                segment_stats.append({
                    "start_idx": all_indices[i],
                    "end_idx": all_indices[i + 1],
                    "n_beats": len(segment),
                    "mean_rr": mean,
                    "std_rr": float(np.std(segment)),
                    "cv": float(np.std(segment) / mean) if mean > 0 else 0,
                })

        n = len(changepoints)
        if n == 0:
            quality_score = 100
        elif n <= 2:
            quality_score = 80
        elif n <= 5:
            quality_score = 60
        else:
            quality_score = max(20, 100 - (n * 10))

        return {
            "changepoint_indices": list(changepoints),
            "n_segments": len(segment_stats),
            "segment_stats": segment_stats,
            "quality_score": quality_score,
        }
    except Exception:
        return empty


def get_quality_badge(quality_score: float, artifact_ratio: float) -> str:
    """Return a quality badge based on quality score and artifact ratio.

    Args:
        quality_score: 0-100 from changepoint detection.
        artifact_ratio: 0-1 ratio of removed artifacts.

    Returns:
        Badge string: "[OK]" (good), "[!]" (moderate), "[X]" (poor).
    """
    artifact_score = max(0, min(100, 100 - (artifact_ratio * 200)))
    combined = (quality_score + artifact_score) / 2
    if combined >= 75:
        return "[OK]"
    elif combined >= 50:
        return "[!]"
    return "[X]"


def detect_time_gaps(timestamps: list, rr_values: list = None, gap_threshold_s: float = 2.0) -> dict:
    """Detect time gaps (missing data) between consecutive RR intervals.

    HRV Logger timestamps are per-packet (~1s), not per-beat. A real gap is
    when the timestamp difference significantly exceeds expected RR intervals.

    Args:
        timestamps: Datetime timestamps for each RR interval.
        rr_values: RR interval values in ms (improves detection accuracy).
        gap_threshold_s: Minimum unexplained gap duration to flag.

    Returns:
        dict with gaps, total_gaps, total_gap_duration_s, gap_ratio.
    """
    empty = {"gaps": [], "total_gaps": 0, "total_gap_duration_s": 0.0, "gap_ratio": 0.0}

    if len(timestamps) < 2:
        return empty

    try:
        valid_mask = np.array([t is not None for t in timestamps])
        if not np.any(valid_mask):
            return empty

        ts_seconds = np.array([t.timestamp() if t else np.nan for t in timestamps])
        ts_diff = np.diff(ts_seconds)

        if rr_values is not None and len(rr_values) == len(timestamps):
            rr_array = np.array(rr_values, dtype=float) / 1000.0
            expected_diff = rr_array[1:]
            unexplained_time = ts_diff - expected_diff
            gap_mask = unexplained_time > gap_threshold_s
        else:
            gap_mask = ts_diff > gap_threshold_s
            unexplained_time = ts_diff

        gap_indices = np.where(gap_mask)[0]

        gaps = []
        total_gap_duration = 0.0
        for idx in gap_indices:
            gap_duration = float(unexplained_time[idx]) if rr_values else float(ts_diff[idx])
            gaps.append({
                "start_idx": int(idx),
                "end_idx": int(idx + 1),
                "start_time": timestamps[idx],
                "end_time": timestamps[idx + 1],
                "duration_s": gap_duration,
                "timestamp_diff_s": float(ts_diff[idx]),
            })
            total_gap_duration += gap_duration

        total_duration = ts_seconds[-1] - ts_seconds[0] if not np.isnan(ts_seconds[0]) else 0
        gap_ratio = total_gap_duration / total_duration if total_duration > 0 else 0

        return {
            "gaps": gaps,
            "total_gaps": len(gaps),
            "total_gap_duration_s": total_gap_duration,
            "gap_ratio": gap_ratio,
        }
    except Exception:
        return empty


def detect_artifacts_fixpeaks(rr_values: list[int], sampling_rate: int = 1000) -> dict:
    """Detect and correct artifacts using NeuroKit2's Kubios algorithm.

    Two-phase approach: detection with iterative=False (comprehensive),
    then in-place interpolation for correction (preserves array length).

    Args:
        rr_values: RR interval values in ms.
        sampling_rate: Sampling rate (1000 for ms intervals).

    Returns:
        dict with artifacts, total_artifacts, artifact_ratio, corrected_rr, correction_applied.
    """
    nk, available = _get_neurokit()
    empty = {
        "artifacts": {"ectopic": 0, "missed": 0, "extra": 0, "longshort": 0},
        "total_artifacts": 0, "artifact_ratio": 0.0,
        "corrected_rr": rr_values, "correction_applied": False,
    }

    if not available or len(rr_values) < 10:
        return empty

    try:
        rr_array = np.array(rr_values, dtype=float)
        peak_indices = np.cumsum(rr_array).astype(int)
        peak_indices = np.insert(peak_indices, 0, 0)

        # Detection: iterative=False finds ALL artifacts
        info, _ = nk.signal_fixpeaks(
            peak_indices, sampling_rate=sampling_rate,
            iterative=False, method="Kubios", show=False,
        )

        artifacts = {}
        artifact_indices = set()
        for key in ["ectopic", "missed", "extra", "longshort"]:
            indices = info.get(key, [])
            if isinstance(indices, np.ndarray):
                indices = indices.tolist()
            elif not isinstance(indices, list):
                indices = []
            artifacts[key] = len(indices)
            artifact_indices.update(indices)

        total_artifacts = sum(artifacts.values())
        artifact_ratio = total_artifacts / len(rr_values) if rr_values else 0

        # In-place interpolation (preserves array length unlike NK2's corrected_peaks)
        corrected_rr = list(rr_array)
        for idx in sorted(artifact_indices):
            if 0 <= idx < len(corrected_rr):
                if idx == 0:
                    if len(corrected_rr) > 1:
                        corrected_rr[idx] = corrected_rr[1]
                elif idx == len(corrected_rr) - 1:
                    corrected_rr[idx] = corrected_rr[idx - 1]
                else:
                    corrected_rr[idx] = (corrected_rr[idx - 1] + corrected_rr[idx + 1]) / 2

        return {
            "artifacts": artifacts,
            "total_artifacts": total_artifacts,
            "artifact_ratio": artifact_ratio,
            "corrected_rr": corrected_rr,
            "correction_applied": total_artifacts > 0,
        }
    except Exception:
        return empty


def filter_exclusion_zones(rr_intervals, exclusion_zones: list[dict]) -> tuple[list, dict]:
    """Filter RR intervals to exclude specified time zones.

    Args:
        rr_intervals: RRInterval objects with .timestamp and .rr_ms attributes.
        exclusion_zones: List of dicts with 'start' and 'end' datetime keys.

    Returns:
        (filtered_rr_intervals, stats_dict).
    """
    import pandas as pd

    if not exclusion_zones or not rr_intervals:
        n = len(rr_intervals) if rr_intervals else 0
        return rr_intervals, {
            "n_original": n, "n_excluded": 0, "n_remaining": n,
            "excluded_duration_ms": 0, "zones_applied": 0,
        }

    parsed_zones = []
    for zone in exclusion_zones:
        try:
            start, end = zone.get('start'), zone.get('end')
            if isinstance(start, str):
                start = pd.to_datetime(start)
            if isinstance(end, str):
                end = pd.to_datetime(end)
            if start and end:
                parsed_zones.append((start, end))
        except Exception:
            continue

    if not parsed_zones:
        return rr_intervals, {
            "n_original": len(rr_intervals), "n_excluded": 0,
            "n_remaining": len(rr_intervals),
            "excluded_duration_ms": 0, "zones_applied": 0,
        }

    filtered = []
    excluded_duration_ms = 0
    n_excluded = 0

    for rr in rr_intervals:
        ts = rr.timestamp
        if ts is None:
            filtered.append(rr)
            continue

        ts_naive = ts.replace(tzinfo=None) if hasattr(ts, 'tzinfo') and ts.tzinfo is not None else ts

        is_excluded = False
        for zone_start, zone_end in parsed_zones:
            if hasattr(zone_start, 'tzinfo') and zone_start.tzinfo is not None:
                zone_start = zone_start.replace(tzinfo=None)
            if hasattr(zone_end, 'tzinfo') and zone_end.tzinfo is not None:
                zone_end = zone_end.replace(tzinfo=None)
            if zone_start <= ts_naive <= zone_end:
                is_excluded = True
                excluded_duration_ms += rr.rr_ms
                n_excluded += 1
                break

        if not is_excluded:
            filtered.append(rr)

    return filtered, {
        "n_original": len(rr_intervals), "n_excluded": n_excluded,
        "n_remaining": len(filtered), "excluded_duration_ms": excluded_duration_ms,
        "zones_applied": len(parsed_zones),
    }
