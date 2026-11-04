"""HRV metrics checked against independent reference values.

Where the reference values come from
------------------------------------
``docs/science/validation.md`` documents (a) the index definitions RRational
follows (Task Force 1996; SDNN on raw NN intervals; pNN50 counts successive
differences strictly > 50 ms), (b) the exact Kubios-aligned pipeline behind
``freq_method="kubios"`` (cubic spline 4 Hz, Smoothness Priors lambda=500,
Welch 180 s / 50 %, absolute ms^2, LF 0.04-0.15 / HF 0.15-0.40 Hz) and (c)
*aggregate* RRational-vs-Kubios agreement on 5 participants.
``docs/kubios_validation_template.md`` lists the acceptable deviations per
metric group (time domain and nonlinear < 1 %, frequency domain 5-15 %).

The per-recording Kubios values behind (c) are not redistributed (identifiable
participant data) and ``docs/kubios_validation_template.csv`` is an empty
template, so there are no tool-generated reference numbers to regression-test
against. Instead these tests compare RRational's output with references that
can be computed independently and exactly:

* time-domain and Poincare indices: the closed-form definitions, recomputed
  with numpy on the same input;
* frequency domain: synthetic RR series with sinusoidal modulation of known
  amplitude A at a known frequency, whose spectral power is A^2 / 2 ms^2
  and must land in the documented band.

Tolerances follow the template: time-domain/nonlinear < 1 % (exact for
integer-ms input), frequency domain well inside the 5-15 % band.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import neurokit2 as nk
import numpy as np
import pytest

from rrational.analysis import hrv_compute
from rrational.analysis.hrv_compute import (
    _compute_kubios_frequency_powers,
    calculate_hrv_metrics,
    calculate_group_stats,
)

pytestmark = pytest.mark.filterwarnings("ignore")

FREQ = ["VLF", "LF", "HF", "LF_HF", "LFn", "HFn", "TP"]


def _rng_nn(n=600, seed=11, sd=35.0, integer=True):
    rr = 800 + np.random.default_rng(seed).normal(0, sd, n)
    return np.round(rr) if integer else rr


def _sine_rr(freqs, amps, duration_s=600.0, base=800.0):
    """RR series sampled at its own beat times: rr_i = base + sum A sin(2 pi f t_i).

    After cubic-spline resampling this is a sinusoid in time with amplitude A,
    whose power (variance) is A^2 / 2 ms^2.
    """
    rr, t = [], 0.0
    while t < duration_s:
        v = base + sum(a * np.sin(2 * np.pi * f * t) for f, a in zip(freqs, amps))
        rr.append(v)
        t += v / 1000.0
    return rr


def _metrics(nn, metrics, **kw):
    m, _, _ = calculate_hrv_metrics(
        list(nn), use_windows=False, selected_metrics=metrics, **kw
    )
    return m


def _time_reference(nn):
    nn = np.asarray(nn, dtype=float)
    d = np.diff(nn)
    mean = nn.mean()
    sdnn = nn.std(ddof=1)
    rmssd = np.sqrt(np.mean(d**2))
    return {
        "MeanNN": mean,
        "MedianNN": np.median(nn),
        "SDNN": sdnn,
        "RMSSD": rmssd,
        "SDSD": d.std(ddof=1),
        # Task Force 1996: NN50 count divided by the total number of NN
        # intervals (NK2 uses the same denominator: len(diff) + 1).
        "pNN50": np.sum(np.abs(d) > 50) / len(nn) * 100,
        "pNN20": np.sum(np.abs(d) > 20) / len(nn) * 100,
        "CVNN": sdnn / mean,
        "CVSD": rmssd / mean,
        "IQRNN": np.percentile(nn, 75) - np.percentile(nn, 25),
        "MeanHR": 60000.0 / mean,
    }


def _poincare_reference(nn):
    nn = np.asarray(nn, dtype=float)
    a, b = nn[:-1], nn[1:]
    sd1 = np.std((a - b) / np.sqrt(2), ddof=1)
    sd2 = np.std((a + b) / np.sqrt(2), ddof=1)
    return {"SD1": sd1, "SD2": sd2, "SD1SD2": sd1 / sd2}


# ---------------------------------------------------------------------------
# Time domain
# ---------------------------------------------------------------------------


class TestTimeDomainReference:
    @pytest.mark.parametrize("seed", [1, 2, 3])
    def test_integer_ms_input_matches_definitions_exactly(self, seed):
        """Integer-ms RR (native resolution of HRV Logger / Polar) round-trips
        through nk.intervals_to_peaks without loss, so every time-domain
        index must equal its closed-form definition to float precision."""
        nn = _rng_nn(seed=seed)
        ref = _time_reference(nn)
        got = _metrics(nn, list(ref))
        for k, v in ref.items():
            assert got[k] == pytest.approx(v, rel=1e-10), k

    def test_fractional_ms_input_within_template_tolerance(self):
        """Corrected beats are averages (e.g. 812.5 ms). intervals_to_peaks
        rounds peak positions to the 1 kHz sample grid, which perturbs each
        interval by < 1 ms. The effect must stay far inside the template's
        < 1 % time-domain tolerance (observed ~0.05 %)."""
        nn = _rng_nn(integer=False)
        ref = _time_reference(nn)
        got = _metrics(nn, ["MeanNN", "SDNN", "RMSSD", "MeanHR"])
        for k in ("MeanNN", "SDNN", "RMSSD", "MeanHR"):
            assert got[k] == pytest.approx(ref[k], rel=2e-3), k

    def test_pnn50_threshold_is_strictly_greater_than_50ms(self):
        exactly_50 = [800, 850] * 50
        just_over = [800, 851] * 50
        assert _metrics(exactly_50, ["pNN50"])["pNN50"] == 0.0
        # 99 qualifying differences / 100 NN intervals (Task Force wording).
        assert _metrics(just_over, ["pNN50"])["pNN50"] == pytest.approx(99.0)

    def test_sdnn_is_task_force_sdnn_on_raw_nn_in_both_freq_methods(self):
        """validation.md: RRational's SDNN is the SD of the raw NN intervals
        (Task Force 1996), not of a detrended signal as in Kubios. A slow
        trend must therefore be fully included, whatever freq_method is."""
        n = 400
        trend = np.linspace(-80, 80, n)
        nn = np.round(800 + trend + _rng_nn(n=n, sd=10) - 800)
        expected = np.std(nn, ddof=1)
        for fm in ("neurokit", "kubios"):
            assert _metrics(nn, ["SDNN"], freq_method=fm)["SDNN"] == pytest.approx(
                expected, rel=1e-10
            )
        # Sanity: the trend dominates, so a detrended SDNN would be far smaller.
        assert expected > 3 * np.std(np.diff(nn), ddof=1) / np.sqrt(2)

    def test_mean_hr_is_derived_from_mean_nn(self):
        nn = [600, 1000] * 100
        hr = _metrics(nn, ["MeanHR"])["MeanHR"]
        assert hr == pytest.approx(60000 / 800)
        # Not the mean of instantaneous HR (which is 80 bpm here).
        assert hr != pytest.approx(np.mean(60000 / np.array(nn)))


# ---------------------------------------------------------------------------
# Nonlinear (Poincare)
# ---------------------------------------------------------------------------


class TestPoincareReference:
    def test_sd1_sd2_match_definitions(self):
        nn = _rng_nn(seed=5)
        ref = _poincare_reference(nn)
        got = _metrics(nn, list(ref))
        for k, v in ref.items():
            assert got[k] == pytest.approx(v, rel=1e-10), k

    def test_sd1_equals_sdsd_over_sqrt2(self):
        """Identity SD1 = SDSD / sqrt(2) (Brennan et al. 2001), holds exactly
        for the ddof=1 estimators used by NK2."""
        nn = _rng_nn(seed=6)
        got = _metrics(nn, ["SD1", "SDSD"])
        assert got["SD1"] == pytest.approx(got["SDSD"] / np.sqrt(2), rel=1e-10)


# ---------------------------------------------------------------------------
# Frequency domain - Kubios-aligned pipeline vs analytic spectra
# ---------------------------------------------------------------------------


class TestKubiosSpectralReference:
    @pytest.mark.parametrize(
        "f_hz,band,others",
        [
            (0.10, "LF", ("VLF", "HF")),
            (0.25, "HF", ("VLF", "LF")),
            (0.20, "HF", ("VLF", "LF")),
            # Near the LF/HF boundary: catches a mis-scaled time axis or
            # shifted band edges that band-centre components would miss.
            (0.135, "LF", ("VLF", "HF")),
            (0.165, "HF", ("VLF", "LF")),
        ],
    )
    def test_sinusoid_power_lands_in_documented_band(self, f_hz, band, others):
        amp = 20.0
        p = _compute_kubios_frequency_powers(_sine_rr([f_hz], [amp]))
        expected = amp**2 / 2  # 200 ms^2
        assert p[band] == pytest.approx(expected, rel=0.03)
        for o in others:
            assert p[o] < 0.01 * expected, o

    def test_lf_hf_mix_ratio_and_normalised_units(self):
        """LF component A=20 (200 ms^2) + HF component A=10 (50 ms^2):
        LF/HF = 4, LFn = 80 n.u., HFn = 20 n.u. (Task Force 1996 n.u. =
        component / (LF + HF) * 100)."""
        p = _compute_kubios_frequency_powers(_sine_rr([0.10, 0.25], [20.0, 10.0]))
        assert p["LF"] == pytest.approx(200, rel=0.03)
        assert p["HF"] == pytest.approx(50, rel=0.03)
        assert p["LF_HF"] == pytest.approx(4.0, rel=0.02)
        assert p["LFn"] == pytest.approx(80.0, abs=0.5)
        assert p["HFn"] == pytest.approx(20.0, abs=0.5)
        assert p["LFn"] + p["HFn"] == pytest.approx(100.0)
        assert p["TP"] == pytest.approx(p["VLF"] + p["LF"] + p["HF"])

    def test_absolute_power_scales_with_amplitude_squared(self):
        """Kubios mode reports absolute ms^2 (normalize=False): doubling the
        modulation amplitude must quadruple the band power."""
        p1 = _compute_kubios_frequency_powers(_sine_rr([0.25], [10.0]))
        p2 = _compute_kubios_frequency_powers(_sine_rr([0.25], [20.0]))
        assert p2["HF"] / p1["HF"] == pytest.approx(4.0, rel=0.01)

    def test_vlf_component_goes_to_vlf(self):
        p = _compute_kubios_frequency_powers(_sine_rr([0.02], [30.0]))
        assert p["VLF"] > 10 * (p["LF"] + p["HF"])
        # TP = VLF + LF + HF must include the (here dominant) VLF power.
        assert p["TP"] == pytest.approx(p["VLF"] + p["LF"] + p["HF"])
        assert p["TP"] > 0.9 * p["VLF"] + p["LF"] + p["HF"]

    def test_end_to_end_kubios_mode_equals_pipeline(self):
        rr = _sine_rr([0.10, 0.25], [20.0, 10.0])
        assert len(rr) >= 300  # frequency domain needs >= 300 beats
        direct = _compute_kubios_frequency_powers(rr)
        got = _metrics(rr, FREQ, freq_method="kubios")
        for k in FREQ:
            assert got[k] == pytest.approx(direct[k], rel=1e-12), k

    def test_too_few_intervals_raises(self):
        with pytest.raises(ValueError, match="at least 30"):
            _compute_kubios_frequency_powers([800.0] * 29)


class TestNeurokitSpectralReference:
    def test_normalised_units_agree_with_kubios_mode(self):
        """NK2's default PSD is normalised, so absolute powers are not
        comparable across freq_methods, but LF/(LF+HF) is scale-free. On the
        analytic 4:1 mix both methods must give ~80/20 n.u. (RRational
        computes n.u. itself in the neurokit branch rather than passing
        through NK2's LF/TP-based HRV_LFn)."""
        rr = _sine_rr([0.10, 0.25], [20.0, 10.0])
        nkm = _metrics(rr, FREQ, freq_method="neurokit")
        assert nkm["LFn"] == pytest.approx(80.0, abs=1.5)
        assert nkm["HFn"] == pytest.approx(20.0, abs=1.5)
        assert nkm["LFn"] + nkm["HFn"] == pytest.approx(100.0)
        assert nkm["LF_HF"] == pytest.approx(4.0, rel=0.05)
        assert nkm["TP"] == pytest.approx(nkm["VLF"] + nkm["LF"] + nkm["HF"])

    def test_frequency_metrics_none_below_300_beats(self):
        got = _metrics(_rng_nn(n=299), ["LF", "HF", "RMSSD"])
        assert got["LF"] is None and got["HF"] is None
        assert got["RMSSD"] is not None


# ---------------------------------------------------------------------------
# Failure handling: a failing NK2 call yields None, never a stale number
# ---------------------------------------------------------------------------


def _boom(*a, **k):
    raise RuntimeError("simulated NeuroKit2 failure")


@pytest.mark.parametrize(
    "nk_func,metrics,freq_method",
    [
        ("hrv_time", ["RMSSD", "SDNN", "SDSD"], "neurokit"),
        ("hrv_frequency", ["LF", "HF", "TP"], "neurokit"),
        ("signal_detrend", ["LF", "HF"], "kubios"),
        ("hrv_nonlinear", ["SD1", "SD2"], "neurokit"),
    ],
)
def test_neurokit_failure_returns_none(monkeypatch, nk_func, metrics, freq_method):
    monkeypatch.setattr(nk, nk_func, _boom)
    got = _metrics(_rng_nn(), metrics, freq_method=freq_method)
    assert all(got[m] is None for m in metrics), got


def test_neurokit_tp_is_none_when_all_bands_missing(monkeypatch):
    import pandas as pd

    monkeypatch.setattr(
        nk, "hrv_frequency", lambda *a, **k: pd.DataFrame({"HRV_LF": [None]})
    )
    got = _metrics(_rng_nn(), ["TP", "LFn", "LF"])
    assert got == {"TP": None, "LFn": None, "LF": None}


# ---------------------------------------------------------------------------
# Windowed aggregation
# ---------------------------------------------------------------------------


class TestWindowedAggregation:
    def test_time_windows_mean_and_sd_match_per_window_reference(self):
        from rrational.gui.segmentation import generate_segments

        nn = _rng_nn(n=900, seed=21)
        mean, sd, n_win = calculate_hrv_metrics(
            list(nn), selected_metrics=["RMSSD", "SDNN"], window_s=120, overlap_pct=50
        )
        segs = [
            s
            for s in generate_segments(nn, window_s=120, overlap_pct=50)
            if s.n_beats >= 30
        ]
        per = [_time_reference(nn[s.beat_start : s.beat_end]) for s in segs]
        assert n_win == len(segs) > 1
        for k in ("RMSSD", "SDNN"):
            vals = np.array([p[k] for p in per])
            assert mean[k] == pytest.approx(vals.mean(), rel=1e-10)
            assert sd[k] == pytest.approx(vals.std(ddof=1), rel=1e-10)

    def test_precomputed_segments_respect_included_flag_and_min_length(self):
        nn = _rng_nn(n=600, seed=22)
        segs = [
            SimpleNamespace(beat_start=0, beat_end=200, included=True),
            SimpleNamespace(beat_start=200, beat_end=400, included=False),
            SimpleNamespace(beat_start=400, beat_end=420, included=True),  # < 30 beats
            SimpleNamespace(beat_start=420, beat_end=600, included=True),
        ]
        mean, _, n_win = calculate_hrv_metrics(
            list(nn), selected_metrics=["RMSSD"], segments=segs
        )
        expected = np.mean(
            [_time_reference(nn[0:200])["RMSSD"], _time_reference(nn[420:600])["RMSSD"]]
        )
        assert n_win == 2
        assert mean["RMSSD"] == pytest.approx(expected, rel=1e-10)

    def test_no_usable_segment_falls_back_to_whole_series(self):
        nn = _rng_nn(n=300, seed=23)
        segs = [SimpleNamespace(beat_start=0, beat_end=10, included=True)]
        mean, sd, n_win = calculate_hrv_metrics(
            list(nn), selected_metrics=["RMSSD"], segments=segs
        )
        assert (n_win, sd) == (1, None)
        assert mean["RMSSD"] == pytest.approx(_time_reference(nn)["RMSSD"], rel=1e-10)

    def test_metric_missing_in_every_window_is_none(self):
        nn = _rng_nn(n=600, seed=24)
        mean, sd, _ = calculate_hrv_metrics(
            list(nn), selected_metrics=["RMSSD", "LF"], window_s=60, overlap_pct=0
        )
        # 60 s windows hold < 300 beats -> no frequency domain anywhere.
        assert mean["LF"] is None and sd["LF"] is None
        assert mean["RMSSD"] is not None

    def test_underpowered_time_windows_are_warned(self, caplog):
        nn = _rng_nn(n=400, seed=25)
        with caplog.at_level(logging.WARNING, logger="rrational.analysis.hrv_compute"):
            calculate_hrv_metrics(
                list(nn), selected_metrics=["RMSSD"], window_s=40, overlap_pct=0
            )
        assert "below the recommended 100-beat minimum" in caplog.text

    def test_failing_window_is_skipped(self, monkeypatch):
        real = nk.intervals_to_peaks

        def flaky(rr, *a, **k):
            if len(rr) < 600:
                raise RuntimeError("window failure")
            return real(rr, *a, **k)

        monkeypatch.setattr(nk, "intervals_to_peaks", flaky)
        nn = _rng_nn(n=600, seed=26)
        mean, sd, n_win = calculate_hrv_metrics(
            list(nn), selected_metrics=["RMSSD"], window_s=60
        )
        # Every window failed -> whole-series fallback, flagged by n_windows=1.
        assert (n_win, sd) == (1, None)
        assert mean["RMSSD"] == pytest.approx(_time_reference(nn)["RMSSD"], rel=1e-10)


def test_group_stats_skip_all_nan_metrics():
    import pandas as pd

    df = pd.DataFrame(
        {
            "participant_id": ["a", "b"],
            "group": ["g", "g"],
            "section": ["s", "s"],
            "rmssd": [30.0, 40.0],
            "lf": [np.nan, np.nan],
        }
    )
    out = calculate_group_stats(df)
    assert list(out["metric"]) == ["RMSSD"]
    row = out.iloc[0]
    assert (row["n"], row["mean"], row["sd"]) == (
        2,
        35.0,
        round(np.std([30, 40], ddof=1), 2),
    )


def test_hrv_compute_uses_lazy_neurokit():
    assert hrv_compute._get_neurokit() is nk
