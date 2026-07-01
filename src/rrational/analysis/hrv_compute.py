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
    MIN_BEATS_TIME_DOMAIN,
    ParticipantSectionResult,
    generate_overlapping_windows_beats,
)


def _get_neurokit():
    """Lazy import NeuroKit2."""
    import neurokit2 as nk

    return nk


FREQ_METHOD_NEUROKIT = "neurokit"
FREQ_METHOD_KUBIOS = "kubios"
VALID_FREQ_METHODS = (FREQ_METHOD_NEUROKIT, FREQ_METHOD_KUBIOS)

# Kubios HRV Scientific defaults (Tarvainen et al. 2014)
KUBIOS_INTERP_FS = 4.0
KUBIOS_SP_LAMBDA = 500
KUBIOS_WELCH_WINDOW_S = 180
# Task Force (1996) standard VLF band starts at 0.0033 Hz (~5 min cycle);
# anything below that is ULF/DC and should not contribute to VLF power.
# Kubios HRV Scientific (Tarvainen et al. 2014) follows the same convention.
KUBIOS_BAND_VLF = (0.0033, 0.04)
KUBIOS_BAND_LF = (0.04, 0.15)
KUBIOS_BAND_HF = (0.15, 0.40)


def _warn_time_domain_underpowered(
    min_beats: int, n_under: int, n_total: int = 1
) -> None:
    """Round 30 (G3) — flag time-domain windows below Quigley's 100-beat floor.

    We still compute the metrics (the user chose "warn but compute"), but a
    window with fewer than ``MIN_BEATS_TIME_DOMAIN`` beats gives unstable
    RMSSD/SDNN estimates (Quigley et al. 2024). One aggregated warning per
    compute keeps the log readable.
    """
    import logging

    logging.getLogger("rrational.analysis.hrv_compute").warning(
        "Time-domain metrics computed on %d/%d window(s) below the "
        "recommended %d-beat minimum (smallest = %d beats); RMSSD/SDNN may "
        "be unstable (Quigley et al. 2024).",
        n_under,
        n_total,
        MIN_BEATS_TIME_DOMAIN,
        min_beats,
    )


def _hrv_frequency_kwargs(freq_method: str) -> dict:
    """Kwargs forwarded to NK2 nk.hrv_frequency for the requested method.

    For FREQ_METHOD_KUBIOS we still use NK2 for the high-level interface (band
    extraction) but ALSO call _compute_kubios_frequency_powers as a more
    accurate replacement when freq_method == KUBIOS. The kwargs returned here
    align NK2's defaults as close as possible to Kubios.
    """
    if freq_method == FREQ_METHOD_KUBIOS:
        return {
            "normalize": False,
            "interpolation_rate": int(KUBIOS_INTERP_FS),
            "psd_method": "welch",
            "vlf": KUBIOS_BAND_VLF,
            "lf": KUBIOS_BAND_LF,
            "hf": KUBIOS_BAND_HF,
        }
    return {}


def _compute_kubios_frequency_powers(
    rr_ms: list[float],
    fs: float = KUBIOS_INTERP_FS,
    lam: int = KUBIOS_SP_LAMBDA,
    welch_window_s: float = KUBIOS_WELCH_WINDOW_S,
    overlap_frac: float = 0.5,
) -> dict:
    """Compute frequency-domain HRV with Kubios-aligned pipeline.

    Pipeline matches Kubios HRV Scientific (Tarvainen et al. 2014):
    1. Cubic spline interpolation of NN intervals to uniform fs Hz
    2. Smoothness Priors detrending (Tarvainen et al. 2002, regularization=lam)
    3. Welch PSD: 180 s Hann window, 50% overlap, scaling='density'
    4. Band integration (trapezoidal): VLF/LF/HF/TP/LF_HF

    Returns dict with VLF, LF, HF, TP (ms^2) and LF_HF ratio. Raises ValueError
    when input is too short to interpolate.
    """
    nk = _get_neurokit()
    from scipy.interpolate import CubicSpline
    from scipy import signal as sig

    rr = np.asarray(rr_ms, dtype=np.float64)
    if len(rr) < 30:
        raise ValueError(f"Need at least 30 NN intervals for PSD, got {len(rr)}")

    t_rr = np.cumsum(rr) / 1000.0
    t_rr = t_rr - t_rr[0]
    t_uniform = np.arange(0.0, t_rr[-1], 1.0 / fs)
    cs = CubicSpline(t_rr, rr)
    rr_uniform = cs(t_uniform)

    rr_detrended = nk.signal_detrend(
        rr_uniform, method="tarvainen2002", regularization=lam
    )

    nperseg = min(int(welch_window_s * fs), len(rr_detrended))
    noverlap = int(nperseg * overlap_frac)
    # Round 30 (G1) — reproducibility warning: when the segment is too
    # short to fit >= 2 Welch averaging windows, the PSD is effectively a
    # single periodogram with no variance reduction, so LF/HF are far less
    # reliable (Task Force 1996 recommends >= 5 min for LF). We still
    # compute (user chose "warn but compute"), but flag it so short-window
    # estimates aren't silently trusted.
    step = max(1, nperseg - noverlap)
    n_welch_windows = 1 + (len(rr_detrended) - nperseg) // step
    if n_welch_windows < 2:
        import logging

        logging.getLogger("rrational.analysis.hrv_compute").warning(
            "Kubios PSD on a short segment: only %d Welch averaging window(s) "
            "(%d samples at %.1f Hz, nperseg=%d). LF/HF have high variance and "
            "low reproducibility; interpret with caution.",
            n_welch_windows,
            len(rr_detrended),
            fs,
            nperseg,
        )
    freqs, psd = sig.welch(
        rr_detrended,
        fs=fs,
        window="hann",
        nperseg=nperseg,
        noverlap=noverlap,
        detrend=False,
        scaling="density",
    )

    def band_power(f1: float, f2: float) -> float:
        mask = (freqs >= f1) & (freqs < f2)
        if not np.any(mask):
            return 0.0
        return float(np.trapezoid(psd[mask], freqs[mask]))

    vlf = band_power(*KUBIOS_BAND_VLF)
    lf = band_power(*KUBIOS_BAND_LF)
    # Round 30 — HF upper bound INCLUSIVE per Task Force 1996 Table 2
    # (HF = 0.15–0.40 Hz inclusive). The standard band_power uses
    # strict ``< f2`` so the bin landing exactly on 0.40 Hz was being
    # dropped; for the highest band specifically we widen to <=.
    hf_mask = (freqs >= KUBIOS_BAND_HF[0]) & (freqs <= KUBIOS_BAND_HF[1])
    hf = float(np.trapezoid(psd[hf_mask], freqs[hf_mask])) if np.any(hf_mask) else 0.0
    tp = vlf + lf + hf
    lfn = 100.0 * lf / (lf + hf) if (lf + hf) > 0 else float("nan")
    hfn = 100.0 * hf / (lf + hf) if (lf + hf) > 0 else float("nan")
    return {
        "VLF": vlf,
        "LF": lf,
        "HF": hf,
        # Round 30 — LFn/HFn (normalized units per Task Force 1996 §3.2.3)
        # were declared in the metric catalog but never written in the
        # Kubios branch, so users selecting them silently got None.
        "LFn": lfn,
        "HFn": hfn,
        "TP": tp,
        "LF_HF": lf / hf if hf > 0 else float("nan"),
    }


def calculate_hrv_metrics(
    nn_ms_list: list[float],
    use_windows: bool = True,
    window_beats: int = 300,
    overlap_pct: float = 75.0,
    selected_metrics: list[str] | None = None,
    window_s: float | None = None,
    segments: list | None = None,
    freq_method: str = FREQ_METHOD_NEUROKIT,
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
        freq_method: Frequency-domain pipeline. "neurokit" uses NK2 defaults
            (normalized PSD, 100 Hz interpolation). "kubios" matches Kubios
            HRV Scientific (absolute ms², 4 Hz interpolation, bands
            VLF 0.0033-0.04, LF 0.04-0.15, HF 0.15-0.40 Hz). The VLF
            lower bound deliberately excludes the ULF band per Task Force
            1996 — earlier docstring incorrectly said "VLF 0-0.04".

    Returns:
        (metrics_dict, std_dict_or_None, n_windows)
    """
    if freq_method not in VALID_FREQ_METHODS:
        raise ValueError(
            f"freq_method must be one of {VALID_FREQ_METHODS}, got {freq_method!r}"
        )

    nk = _get_neurokit()
    freq_kwargs = _hrv_frequency_kwargs(freq_method)

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
                        # Round 30 — Mean HR here is derived from mean NN
                        # (HR = 60000 / MeanNN). By Jensen's inequality this
                        # differs from the mean of instantaneous HR
                        # (mean of 60000/rr_i) which is always >= the
                        # NN-derived value. Both conventions appear in the
                        # HRV literature; we keep the NN-derived one for
                        # Kubios compatibility (Tarvainen et al. 2014).
                        mean_nn = hrv_time.get("HRV_MeanNN", [None])[0]
                        result["MeanHR"] = (
                            60000 / mean_nn if mean_nn and mean_nn > 0 else None
                        )
                    else:
                        result[m] = hrv_time.get(f"HRV_{m}", [None])[0]
                for m in selected_set & time_extended:
                    result[m] = hrv_time.get(f"HRV_{m}", [None])[0]
            except Exception:
                for m in selected_set & (time_basic | time_extended):
                    result[m] = None

        if need_freq and len(rr_list) >= MIN_BEATS_FREQUENCY_DOMAIN:
            try:
                if freq_method == FREQ_METHOD_KUBIOS:
                    powers = _compute_kubios_frequency_powers(rr_list)
                    for m in selected_set & frequency:
                        result[m] = powers.get(m)
                else:
                    hrv_freq = nk.hrv_frequency(
                        peaks, sampling_rate=1000, show=False, **freq_kwargs
                    )
                    for m in selected_set & frequency:
                        if m == "LF_HF":
                            result["LF_HF"] = hrv_freq.get("HRV_LFHF", [None])[0]
                        elif m == "TP":
                            vlf = hrv_freq.get("HRV_VLF", [0])[0] or 0
                            lf = hrv_freq.get("HRV_LF", [0])[0] or 0
                            hf = hrv_freq.get("HRV_HF", [0])[0] or 0
                            result["TP"] = vlf + lf + hf if any([vlf, lf, hf]) else None
                        elif m in ("LFn", "HFn"):
                            # Round 30 — compute normalized units OURSELVES so
                            # both freq_methods agree. NK2's HRV_LFn is LF/TP
                            # (0-1, includes VLF in the denominator) whereas the
                            # metric catalog labels LFn as "n.u." — Task Force
                            # 1996 §3.2.3 defines n.u. as component/(LF+HF)*100.
                            # The Kubios branch already uses that convention; if
                            # we passed NK2's HRV_LFn through here the SAME metric
                            # would mean two different things depending on
                            # freq_method (e.g. 62 n.u. vs 0.58 fraction).
                            lf = hrv_freq.get("HRV_LF", [None])[0]
                            hf = hrv_freq.get("HRV_HF", [None])[0]
                            if lf is not None and hf is not None and (lf + hf) > 0:
                                num = lf if m == "LFn" else hf
                                result[m] = 100.0 * num / (lf + hf)
                            else:
                                result[m] = None
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
        if need_time and len(nn_ms_list) < MIN_BEATS_TIME_DOMAIN:
            _warn_time_domain_underpowered(len(nn_ms_list), 1, 1)
        return compute_hrv(nn_ms_list), None, 1

    # Build window slices from segments, time-based, or beat-based
    window_slices: list[list[float]] = []

    if segments is not None:
        nn_array = np.asarray(nn_ms_list, dtype=np.float64)
        for seg in segments:
            if getattr(seg, "included", True):
                sliced = nn_array[seg.beat_start : seg.beat_end]
                if len(sliced) >= 30:
                    window_slices.append(sliced.tolist())

    elif window_s is not None:
        from rrational.gui.segmentation import generate_segments

        nn_array = np.asarray(nn_ms_list, dtype=np.float64)
        segs = generate_segments(nn_array, window_s=window_s, overlap_pct=overlap_pct)
        for seg in segs:
            sliced = nn_array[seg.beat_start : seg.beat_end]
            if len(sliced) >= 30:
                window_slices.append(sliced.tolist())

    else:
        min_beats = min(window_beats, len(nn_ms_list))
        if len(nn_ms_list) < min_beats:
            return compute_hrv(nn_ms_list), None, 1
        step_beats = max(1, int(window_beats * (1 - overlap_pct / 100)))
        windows = generate_overlapping_windows_beats(
            nn_ms_list, window_beats, step_beats
        )
        window_slices = [w_rr for _, _, w_rr in windows]

    if not window_slices:
        return compute_hrv(nn_ms_list), None, 1

    if need_time:
        under = [len(w) for w in window_slices if len(w) < MIN_BEATS_TIME_DOMAIN]
        if under:
            _warn_time_domain_underpowered(min(under), len(under), len(window_slices))

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
            participants[r.participant_id] = {
                "participant_id": r.participant_id,
                "group": r.group,
            }
        prefix = r.section_name.replace(" ", "_").lower()
        for key, value in r.hrv_metrics.items():
            participants[r.participant_id][f"{prefix}_{key.lower()}"] = value
        participants[r.participant_id][f"{prefix}_n_beats"] = r.n_beats
        participants[r.participant_id][f"{prefix}_quality"] = r.quality_grade
        participants[r.participant_id][f"{prefix}_data_source"] = r.data_source
    return pd.DataFrame(list(participants.values()))


def calculate_group_stats(long_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate descriptive statistics per group and section."""
    exclude_cols = {
        "participant_id",
        "group",
        "section",
        "data_source",
        "n_beats",
        "duration_s",
        "quality",
        "artifact_rate",
        "n_windows",
    }
    metrics = [
        col
        for col in long_df.columns
        if col not in exclude_cols and not col.endswith("_sd")
    ]

    rows = []
    for (group, section), group_df in long_df.groupby(["group", "section"]):
        for metric in metrics:
            if metric not in group_df.columns:
                continue
            values = group_df[metric].dropna()
            if len(values) == 0:
                continue
            rows.append(
                {
                    "group": group,
                    "section": section,
                    "metric": metric.upper(),
                    "n": len(values),
                    "mean": round(values.mean(), 2),
                    "sd": round(values.std(), 2) if len(values) > 1 else 0.0,
                    "min": round(values.min(), 2),
                    "max": round(values.max(), 2),
                }
            )
    return pd.DataFrame(rows)
