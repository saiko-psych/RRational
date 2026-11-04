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
    empty = {
        "changepoint_indices": [],
        "n_segments": 1,
        "segment_stats": [],
        "quality_score": 100,
    }

    if not available or len(rr_values) < 10:
        return empty

    try:
        rr_array = np.array(rr_values, dtype=float)
        changepoints = nk.signal_changepoints(rr_array, change=change_type, show=False)

        segment_stats = []
        all_indices = [0] + list(changepoints) + [len(rr_array)]
        for i in range(len(all_indices) - 1):
            segment = rr_array[all_indices[i] : all_indices[i + 1]]
            if len(segment) > 0:
                mean = float(np.mean(segment))
                segment_stats.append(
                    {
                        "start_idx": all_indices[i],
                        "end_idx": all_indices[i + 1],
                        "n_beats": len(segment),
                        "mean_rr": mean,
                        "std_rr": float(np.std(segment)),
                        "cv": float(np.std(segment) / mean) if mean > 0 else 0,
                    }
                )

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


def detect_time_gaps(
    timestamps: list, rr_values: list = None, gap_threshold_s: float = 2.0
) -> dict:
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

        # Round 28 — datetime.timestamp() on a naive datetime uses the
        # LOCAL system timezone, so a DST transition can falsely show as
        # a 1-hour gap (or a backward fold producing a negative diff).
        # Use calendar.timegm() for naive datetimes (treats as UTC) and
        # the canonical .timestamp() only for tz-aware inputs.
        import calendar

        def _safe_epoch(t):
            if t is None:
                return np.nan
            if t.tzinfo is not None:
                return t.timestamp()
            return float(calendar.timegm(t.timetuple()))

        ts_seconds = np.array([_safe_epoch(t) for t in timestamps])
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
            gap_duration = (
                float(unexplained_time[idx]) if rr_values else float(ts_diff[idx])
            )
            gaps.append(
                {
                    "start_idx": int(idx),
                    "end_idx": int(idx + 1),
                    "start_time": timestamps[idx],
                    "end_time": timestamps[idx + 1],
                    "duration_s": gap_duration,
                    "timestamp_diff_s": float(ts_diff[idx]),
                }
            )
            total_gap_duration += gap_duration

        total_duration = (
            ts_seconds[-1] - ts_seconds[0] if not np.isnan(ts_seconds[0]) else 0
        )
        gap_ratio = total_gap_duration / total_duration if total_duration > 0 else 0

        return {
            "gaps": gaps,
            "total_gaps": len(gaps),
            "total_gap_duration_s": total_gap_duration,
            "gap_ratio": gap_ratio,
        }
    except (AttributeError, TypeError, ValueError) as exc:
        # Round 28 — bare ``except Exception`` previously hid every
        # bug class including KeyboardInterrupt, NameError, and any
        # future numpy API regression. Narrow to the actual recoverable
        # cases (malformed timestamps / non-numeric values), log the
        # rest so silent corruption stops happening.
        import logging

        logging.getLogger("rrational.cleaning.quality").warning(
            "detect_time_gaps recovered from %s; returning empty result.",
            type(exc).__name__,
            exc_info=True,
        )
        return empty


FIXPEAKS_ARTIFACT_TYPES = ("ectopic", "missed", "extra", "longshort")


def rr_to_peak_indices(rr_values) -> np.ndarray:
    """Peak sample indices (1 kHz) for ``nk.signal_fixpeaks`` from RR in ms.

    Returns ``[0, cumsum(rr)...]`` (length N+1) as int64. Round 28: a plain
    ``astype(int)`` is the platform native int (32-bit on Windows builds),
    which wraps to negative for cumulative totals > 2^31 ms (~25 days).
    """
    peaks = np.cumsum(np.asarray(rr_values, dtype=float)).astype(np.int64)
    return np.insert(peaks, 0, 0)


def _fixpeaks_index_list(value) -> list:
    """NK2 ``info[type]`` as a plain list (non list/array values -> [])."""
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value if isinstance(value, list) else []


def fixpeaks_info_to_rr_indices(info: dict, n_rr: int) -> dict[str, list[int]]:
    """Map NK2 Kubios artifact indices (peaks space) to RR-space indices.

    Round 30 — NK2's Kubios detector (``_find_artifacts``) works on
    ``rr = ediff1d(peaks, to_begin=0)``, which is PEAKS-space: it has the
    same length as the peak array (N+1) and ``rr_nk[i]`` is the interval
    ENDING at peak i, i.e. ``rr_nk[i] == rr_values[i-1]`` (``rr_nk[0]`` is a
    synthetic mean, not a real interval). So an NK2 artifact index k refers
    to ``rr_values[k-1]``. Storing k directly (a) shifts every flagged beat
    one position later and (b) drops a real artifact on the final beat
    (NK2 index N). Verified empirically: an ectopic injected at
    ``rr_values[100]`` is reported by NK2 at index 101.

    Every caller that turns ``signal_fixpeaks`` output into beat positions
    must go through this function; ``gui/app.py`` once kept its own copy of
    the mapping and missed the fix.

    Returns ``{type: sorted unique RR indices}`` for the four Kubios types,
    keeping only indices that are valid positions in an RR array of length
    ``n_rr``. Non-integer entries are ignored.
    """
    out: dict[str, list[int]] = {}
    for key in FIXPEAKS_ARTIFACT_TYPES:
        mapped = set()
        for raw_idx in _fixpeaks_index_list(info.get(key, [])):
            try:
                rr_idx = int(raw_idx) - 1
            except (TypeError, ValueError):
                continue
            if 0 <= rr_idx < n_rr:
                mapped.add(rr_idx)
        out[key] = sorted(mapped)
    return out


def detect_artifacts_fixpeaks(rr_values: list[int], sampling_rate: int = 1000) -> dict:
    """Detect and correct artifacts using NeuroKit2's Kubios algorithm.

    Two-phase approach: detection with iterative=False (comprehensive),
    then in-place interpolation for correction (preserves array length).

    Args:
        rr_values: RR interval values in ms.
        sampling_rate: Sampling rate (1000 for ms intervals).

    Returns:
        dict with the following keys:
            - artifacts: per-type counts (ectopic/missed/extra/longshort)
            - total_artifacts: sum of per-type counts
            - artifact_ratio: total_artifacts / len(rr_values)
            - artifact_indices: sorted list of int indices into ``rr_values``
              where NK2 flagged at least one artifact. Consumers (e.g. the
              inspector overlay) should use this set rather than diffing
              ``corrected_rr - rr_values``, which can miss artifacts that
              happen to interpolate to themselves.
            - corrected_rr: list of in-place interpolated RR values
            - correction_applied: bool
    """
    nk, available = _get_neurokit()
    empty = {
        "artifacts": {"ectopic": 0, "missed": 0, "extra": 0, "longshort": 0},
        "total_artifacts": 0,
        "artifact_ratio": 0.0,
        "artifact_indices": [],
        "corrected_rr": rr_values,
        "correction_applied": False,
    }

    if not available or len(rr_values) < 10:
        return empty

    try:
        rr_array = np.array(rr_values, dtype=float)
        peak_indices = rr_to_peak_indices(rr_array)

        # Detection: iterative=False finds ALL artifacts
        info, _ = nk.signal_fixpeaks(
            peak_indices,
            sampling_rate=sampling_rate,
            iterative=False,
            method="Kubios",
            show=False,
        )

        # Per-type counts are NK2's raw list lengths (unchanged behaviour);
        # beat positions go through the shared peaks -> RR mapping.
        artifacts = {
            key: len(_fixpeaks_index_list(info.get(key, [])))
            for key in FIXPEAKS_ARTIFACT_TYPES
        }
        artifact_indices: set[int] = set()
        for indices in fixpeaks_info_to_rr_indices(info, len(rr_values)).values():
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
                    corrected_rr[idx] = (
                        corrected_rr[idx - 1] + corrected_rr[idx + 1]
                    ) / 2

        return {
            "artifacts": artifacts,
            "total_artifacts": total_artifacts,
            "artifact_ratio": artifact_ratio,
            "artifact_indices": sorted(artifact_indices),
            "corrected_rr": corrected_rr,
            "correction_applied": total_artifacts > 0,
        }
    except Exception:
        return empty


def filter_exclusion_zones(
    rr_intervals, exclusion_zones: list[dict]
) -> tuple[list, dict]:
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
            "n_original": n,
            "n_excluded": 0,
            "n_remaining": n,
            "excluded_duration_ms": 0,
            "zones_applied": 0,
        }

    parsed_zones = []
    for zone in exclusion_zones:
        try:
            start, end = zone.get("start"), zone.get("end")
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
            "n_original": len(rr_intervals),
            "n_excluded": 0,
            "n_remaining": len(rr_intervals),
            "excluded_duration_ms": 0,
            "zones_applied": 0,
        }

    filtered = []
    excluded_duration_ms = 0
    n_excluded = 0

    # Round 30 — tz handling needs to be SYMMETRIC. The earlier code
    # stripped tzinfo on both sides without converting to a common
    # frame first, so a UTC beat compared against a local-tz zone
    # silently shifted by the UTC offset (and across DST in the worst
    # case). We adopt ONE convention: aware datetimes are converted to
    # UTC and made naive; naive datetimes are ASSUMED to already be UTC
    # (consistent with the calendar.timegm treatment elsewhere in this
    # module). Both sides then share the naive-UTC frame. A genuinely
    # naive-LOCAL input cannot be corrected without its tz, which is a
    # data-provenance problem upstream, not something this comparison
    # can recover.
    from datetime import timezone as _tz

    def _to_naive_utc(t):
        if t is None:
            return None
        if hasattr(t, "tzinfo") and t.tzinfo is not None:
            return t.astimezone(_tz.utc).replace(tzinfo=None)
        return t  # assumed already UTC

    normalized_zones = [
        (_to_naive_utc(zs), _to_naive_utc(ze)) for zs, ze in parsed_zones
    ]

    for rr in rr_intervals:
        ts = rr.timestamp
        if ts is None:
            filtered.append(rr)
            continue

        ts_naive_utc = _to_naive_utc(ts)

        is_excluded = False
        for zone_start, zone_end in normalized_zones:
            if zone_start is None or zone_end is None:
                continue
            if zone_start <= ts_naive_utc <= zone_end:
                is_excluded = True
                excluded_duration_ms += rr.rr_ms
                n_excluded += 1
                break

        if not is_excluded:
            filtered.append(rr)

    return filtered, {
        "n_original": len(rr_intervals),
        "n_excluded": n_excluded,
        "n_remaining": len(filtered),
        "excluded_duration_ms": excluded_duration_ms,
        "zones_applied": len(parsed_zones),
    }


# =============================================================================
# Lipponen & Tarvainen (2019) correction with a raw -> corrected beat map
# =============================================================================


def map_raw_range(raw_to_corrected, raw_start: int, raw_end: int) -> tuple[int, int]:
    """Translate a raw beat slice ``[raw_start, raw_end)`` to the corrected series.

    ``raw_to_corrected`` is the boundary map returned by
    :func:`correct_artifacts_lipponen` (length N_raw + 1). Use it as
    ``corrected[cs:ce]`` wherever code previously sliced the corrected array
    with raw beat positions (sections, segments, scopes).
    """
    m = raw_to_corrected
    n = len(m) - 1
    s = min(max(int(raw_start), 0), n)
    e = min(max(int(raw_end), s), n)
    return int(m[s]), int(m[e])


def _epoch_like(values):
    """Timestamps -> (floats, back-converter) or (None, None) if unusable."""
    valid = [v for v in values if v is not None]
    if not valid:
        return None, None
    ref = valid[0]
    if isinstance(ref, (int, float, np.integer, np.floating)):
        return (
            np.array([np.nan if v is None else float(v) for v in values]),
            lambda x: float(x),
        )
    import datetime as _dt

    try:
        secs = np.array(
            [np.nan if v is None else (v - ref).total_seconds() for v in values]
        )
    except (TypeError, AttributeError):
        return None, None
    return secs, lambda x: ref + _dt.timedelta(seconds=float(x))


def _corrected_timestamps(timestamps, raw_peaks, corrected_peaks):
    """Timestamps for corrected beats.

    A corrected beat that ends exactly where a raw beat ends keeps that raw
    beat's original timestamp object; inserted or moved beats are linearly
    interpolated between the raw beat end times.
    """
    if timestamps is None or len(timestamps) != len(raw_peaks) - 1:
        return None
    secs, back = _epoch_like(list(timestamps))
    if secs is None:
        return None
    raw_end = raw_peaks[1:]
    ok = ~np.isnan(secs)
    if ok.sum() < 2:
        return None
    end_to_raw = {int(p): i for i, p in enumerate(raw_end)}
    out = []
    for p in corrected_peaks[1:]:
        i = end_to_raw.get(int(p))
        if i is not None and timestamps[i] is not None:
            out.append(timestamps[i])
        else:
            out.append(back(np.interp(float(p), raw_end[ok], secs[ok])))
    return out


def _beat_correspondence(raw_peaks: np.ndarray, corrected_peaks: np.ndarray):
    """Boundary map, changed-beat flags and inserted/removed counts.

    Peaks present unchanged in both series are anchors. Between two
    consecutive anchors the raw series has ``a`` peaks and the corrected
    series ``c``. If ``a == c`` the peaks were only moved (ectopic /
    long-short) and map one-to-one; otherwise beats were inserted (missed)
    or removed (extra) and boundaries inside that block map by time. Using
    time alone would misread a moved peak that crosses a raw beat boundary
    as one removal plus one insertion.
    """
    _, ri, ci = np.intersect1d(raw_peaks, corrected_peaks, return_indices=True)
    n_raw, n_cor = len(raw_peaks) - 1, len(corrected_peaks) - 1
    peak_map = np.empty(len(raw_peaks), dtype=np.int64)
    inserted = removed = 0

    anchors = list(zip(ri.tolist(), ci.tolist()))
    if not anchors or anchors[0] != (0, 0):
        anchors.insert(0, (0, 0))
    if anchors[-1] != (n_raw, n_cor):
        anchors.append((n_raw, n_cor))

    for (r0, c0), (r1, c1) in zip(anchors, anchors[1:]):
        a, c = r1 - r0, c1 - c0
        peak_map[r0] = c0
        if a == c:
            for k in range(1, a):
                peak_map[r0 + k] = c0 + k
        else:
            inserted += max(0, c - a)
            removed += max(0, a - c)
            inner = corrected_peaks[c0 + 1 : c1]
            for k in range(1, a):
                pos = np.searchsorted(inner, raw_peaks[r0 + k], side="right")
                peak_map[r0 + k] = c0 + int(pos)
    peak_map[n_raw] = n_cor
    peak_map = np.maximum.accumulate(peak_map)

    anchor_set = {int(c): int(r) for r, c in anchors}
    flags = []
    for j in range(n_cor):
        r_a, r_b = anchor_set.get(j), anchor_set.get(j + 1)
        unchanged = (
            r_a is not None
            and r_b is not None
            and r_b - r_a == 1
            and raw_peaks[r_a] == corrected_peaks[j]
            and raw_peaks[r_b] == corrected_peaks[j + 1]
        )
        flags.append(not unchanged)
    return peak_map.tolist(), flags, inserted, removed


def correct_artifacts_lipponen(
    rr_values, timestamps=None, sampling_rate: int = 1000
) -> dict:
    """Detect and correct artifacts per Lipponen & Tarvainen (2019).

    Detection: NK2 Kubios detector, ``iterative=False`` (comprehensive; same
    indices as :func:`detect_artifacts_fixpeaks`). Correction: NK2
    ``signal_fixpeaks(method="Kubios", iterative=True)``, which works in
    PEAK space: extra beats are removed (two short intervals merge), missed
    beats get a peak inserted at the midpoint (a long interval splits), and
    ectopic / long-short beats have their peak moved to the midpoint of its
    neighbours. Recording time is preserved; the number of intervals can
    change, so the corrected series comes with its own timestamps and a map
    back to raw beat positions.

    Known limitation (NK2 0.2.x): adjacent misaligned peaks are each moved
    using the other's uncorrected position, so an ectopic pair is improved
    but not fully equalised.

    Returns dict:
        artifact_indices / indices_by_type: RR indices in RAW space
            (for overlays, counts and quality grades).
        artifacts: per-type counts (NK2 raw list lengths).
        corrected_rr: corrected NN intervals (ms), own length.
        corrected_timestamps: per corrected beat, or None.
        raw_to_corrected: boundary map, length N_raw + 1; slice the corrected
            series for a raw range with :func:`map_raw_range`.
        corrected_flags: per corrected beat, True if it is not an unchanged
            raw beat.
        n_inserted / n_removed: beats added (missed) / removed (extra).
        correction_applied: bool.
    """
    rr_list = list(rr_values)
    n = len(rr_list)
    passthrough = {
        "artifact_indices": [],
        "indices_by_type": {k: [] for k in FIXPEAKS_ARTIFACT_TYPES},
        "artifacts": {k: 0 for k in FIXPEAKS_ARTIFACT_TYPES},
        "corrected_rr": rr_list,
        "corrected_timestamps": list(timestamps) if timestamps is not None else None,
        "raw_to_corrected": list(range(n + 1)),
        "corrected_flags": [False] * n,
        "n_inserted": 0,
        "n_removed": 0,
        "correction_applied": False,
    }
    nk, available = _get_neurokit()
    if not available or n < 10:
        return passthrough

    raw_peaks = rr_to_peak_indices(rr_list)
    info, _ = nk.signal_fixpeaks(
        raw_peaks, sampling_rate=sampling_rate, iterative=False,
        method="Kubios", show=False,
    )
    by_type = fixpeaks_info_to_rr_indices(info, n)
    artifact_indices = sorted({i for v in by_type.values() for i in v})
    counts = {k: len(_fixpeaks_index_list(info.get(k, []))) for k in FIXPEAKS_ARTIFACT_TYPES}
    if not artifact_indices:
        return {**passthrough, "artifacts": counts}

    _, corrected_peaks = nk.signal_fixpeaks(
        raw_peaks, sampling_rate=sampling_rate, iterative=True,
        method="Kubios", show=False,
    )
    corrected_peaks = np.asarray(corrected_peaks, dtype=np.int64)
    corrected_rr = np.diff(corrected_peaks).astype(float).tolist()
    bmap, flags, inserted, removed = _beat_correspondence(raw_peaks, corrected_peaks)

    return {
        "artifact_indices": artifact_indices,
        "indices_by_type": by_type,
        "artifacts": counts,
        "corrected_rr": corrected_rr,
        "corrected_timestamps": _corrected_timestamps(
            timestamps, raw_peaks, corrected_peaks
        ),
        "raw_to_corrected": bmap,
        "corrected_flags": flags,
        "n_inserted": inserted,
        "n_removed": removed,
        "correction_applied": True,
    }
