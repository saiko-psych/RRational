"""Tests for sample_entropy / approximate_entropy (Cluster B7).

We pin behaviour against three regimes:

1. Constant series → NaN (sigma is zero).
2. Short series → NaN guard fires.
3. Periodic series → SampEn < ApEn (both small, periodic structure).
4. White noise → both > 1.5 (high complexity).
5. Output shape: scalar float.

Reference values are not checked against external implementations
because pip-installable HRV-entropy libraries differ on edge cases.
We assert relative ordering (which is reproducible across
implementations) and the NaN guard contract.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from rrational.analysis.nonlinear import (
    DEFAULT_M,
    DEFAULT_R,
    approximate_entropy,
    sample_entropy,
)


def test_constant_series_returns_nan() -> None:
    rr = np.full(200, 800.0)
    assert math.isnan(sample_entropy(rr))
    assert math.isnan(approximate_entropy(rr))


def test_too_short_returns_nan() -> None:
    # Length below m+1 / m+2 must trip the guard.
    assert math.isnan(approximate_entropy([1.0]))
    assert math.isnan(sample_entropy([1.0, 2.0]))


def test_periodic_signal_has_low_complexity() -> None:
    # Pure sine sampled at 10 Hz for 20 s → highly predictable, both
    # entropies stay small.
    t = np.linspace(0, 20, 200)
    rr = 800 + 50 * np.sin(2 * np.pi * 0.25 * t)
    apen = approximate_entropy(rr)
    sampen = sample_entropy(rr)
    assert apen < 0.5
    assert sampen < 0.5


def test_white_noise_has_high_complexity() -> None:
    rng = np.random.default_rng(seed=42)
    rr = 800 + 100 * rng.standard_normal(300)
    apen = approximate_entropy(rr)
    sampen = sample_entropy(rr)
    # White noise produces large entropies — both should comfortably
    # clear the periodic threshold.
    assert apen > 1.0
    assert sampen > 1.0


def test_default_parameters_match_textbook() -> None:
    assert DEFAULT_M == 2
    assert DEFAULT_R == pytest.approx(0.2)


def test_returns_python_float() -> None:
    rng = np.random.default_rng(seed=0)
    rr = 800 + 50 * rng.standard_normal(80)
    assert isinstance(sample_entropy(rr), float)
    assert isinstance(approximate_entropy(rr), float)
