"""Regression tests for LFn/HFn in Kubios mode and the inclusive HF band.

Round 30 fixed two related defects in ``_compute_kubios_frequency_powers``:

1. ``LFn``/``HFn`` (normalized units, Task Force 1996 §3.2.3) were declared in
   the metric catalog but never written in the Kubios branch, so users selecting
   them silently received ``None``.
2. The HF band upper bound was integrated with a strict ``< 0.40 Hz`` mask,
   dropping the spectral bin landing exactly on 0.40 Hz. Task Force (1996)
   Table 2 defines HF as 0.15-0.40 Hz *inclusive*, so the highest band now uses
   ``<=``.

These tests fail against the pre-Round-30 behavior (None LFn/HFn, dropped edge
bin) and pass against the current implementation.
"""

import numpy as np
import pytest

from rrational.analysis.hrv_compute import (
    calculate_hrv_metrics,
    _compute_kubios_frequency_powers,
    KUBIOS_BAND_HF,
    FREQ_METHOD_KUBIOS,
)


def _make_lf_hf_rr(n: int = 400, mean_ms: float = 800.0, seed: int = 7) -> list[float]:
    """Synthetic NN series with genuine LF and HF oscillations.

    ~300+ beats around 800 ms gives enough duration (~5 min) for the Welch PSD.
    Injecting a 0.10 Hz (LF) and 0.25 Hz (HF) component guarantees both bands
    carry power so the LFn/HFn normalization is well defined.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(n) * mean_ms / 1000.0
    lf = 30.0 * np.sin(2 * np.pi * 0.10 * t)
    hf = 20.0 * np.sin(2 * np.pi * 0.25 * t)
    noise = rng.normal(0.0, 20.0, n)
    return (mean_ms + lf + hf + noise).tolist()


class TestKubiosNormalizedUnits:
    def test_lfn_hfn_present_in_powers_dict(self):
        """The Kubios power dict must expose LFn and HFn as non-None floats."""
        rr = _make_lf_hf_rr()
        powers = _compute_kubios_frequency_powers(rr)

        assert "LFn" in powers and "HFn" in powers
        assert isinstance(powers["LFn"], float)
        assert isinstance(powers["HFn"], float)
        assert not np.isnan(powers["LFn"])
        assert not np.isnan(powers["HFn"])

    def test_lfn_hfn_sum_to_100(self):
        """LFn + HFn are complementary normalized units and sum to ~100."""
        rr = _make_lf_hf_rr()
        powers = _compute_kubios_frequency_powers(rr)

        assert powers["LFn"] + powers["HFn"] == pytest.approx(100.0, abs=1e-6)

    def test_calculate_hrv_metrics_returns_lfn_hfn(self):
        """Selecting LFn/HFn via the public API must not silently yield None.

        This is the user-facing regression: before Round 30 the Kubios branch
        never wrote LFn/HFn, so ``metrics['LFn']`` came back as ``None``.
        """
        rr = _make_lf_hf_rr()
        metrics, std, n_win = calculate_hrv_metrics(
            rr,
            use_windows=False,
            selected_metrics=["LFn", "HFn"],
            freq_method=FREQ_METHOD_KUBIOS,
        )

        assert n_win == 1
        assert metrics["LFn"] is not None, "Kubios LFn must not be None"
        assert metrics["HFn"] is not None, "Kubios HFn must not be None"
        assert isinstance(metrics["LFn"], float)
        assert isinstance(metrics["HFn"], float)
        assert metrics["LFn"] + metrics["HFn"] == pytest.approx(100.0, abs=1e-6)


class TestInclusiveHfBand:
    def test_hf_band_includes_upper_bound(self, monkeypatch):
        """HF integration must include the bin landing exactly on 0.40 Hz.

        We monkeypatch ``scipy.signal.welch`` to return a deterministic PSD on a
        grid whose top bin sits exactly on the HF upper bound (0.40 Hz). With the
        pre-Round-30 strict ``< 0.40`` mask that bin is dropped; the current
        inclusive ``<= 0.40`` mask keeps it, yielding strictly more HF power.
        """
        lo, hi = KUBIOS_BAND_HF  # (0.15, 0.40)
        # Grid with interior HF points AND the exact upper-bound bin at ``hi``.
        freqs = np.array([0.00, 0.05, 0.10, 0.20, 0.30, hi])
        psd = np.array([0.0, 1.0, 1.0, 2.0, 3.0, 5.0])

        def fake_welch(*args, **kwargs):
            return freqs, psd

        import scipy.signal as scipy_signal

        monkeypatch.setattr(scipy_signal, "welch", fake_welch)

        # Constant RR keeps interpolation/detrending trivial; welch is faked.
        rr = [800.0] * 400
        powers = _compute_kubios_frequency_powers(rr)

        inclusive_mask = (freqs >= lo) & (freqs <= hi)
        strict_mask = (freqs >= lo) & (freqs < hi)
        expected_inclusive = float(
            np.trapezoid(psd[inclusive_mask], freqs[inclusive_mask])
        )
        buggy_strict = float(np.trapezoid(psd[strict_mask], freqs[strict_mask]))

        assert powers["HF"] == pytest.approx(expected_inclusive)
        assert powers["HF"] > buggy_strict, (
            "HF band must include the 0.40 Hz edge bin (Task Force 1996 Table 2)"
        )
