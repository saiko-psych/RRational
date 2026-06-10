"""Group-overlay HRV-curve comparison with bootstrap CI bands (Cluster B1).

Mirrors the spirit of ``mne.viz.plot_compare_evokeds()`` for HRV: take
multiple groups of tachograms (one per subject) and overlay the group
means as solid lines with translucent confidence bands.

Bands are bootstrap-derived (``numpy.random.choice`` with replacement)
rather than parametric SEs so the same code handles short, skewed,
non-Gaussian RR distributions without bolting on per-group assumptions.

Implementation notes:
- Each "subject curve" is a numpy array of RR values (not (t, v) pairs);
  curves of unequal length are zero-padded with NaN to a common length
  and the mean / CI are computed sample-wise ignoring NaNs.
- Colours come from the shared Okabe-Ito palette so this plot agrees
  with the rest of the inspector under colourblind-safe mode.
- The widget is a plain ``pg.PlotWidget`` so callers can embed it in
  any dialog or dock without extra adapter glue.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Optional

import numpy as np
import pyqtgraph as pg
from qtpy.QtGui import QColor

from rrational.inspector.palette import palette

# Bootstrap defaults — 1000 resamples is the canonical "good enough"
# point for 95% CIs on n=10-50 samples; the runtime cost is still well
# under 100 ms even for long curves so we don't expose a knob.
_DEFAULT_N_BOOT = 1000
_BAND_ALPHA = 60  # 0-255; matches OverviewBar viewport fill for visual cohesion


def _pad_to_common_length(curves: Sequence[np.ndarray]) -> np.ndarray:
    """Stack a list of 1-D arrays into a 2-D NaN-padded matrix.

    Returns shape ``(n_curves, max_len)``; shorter curves are
    right-padded with NaN so sample-wise reductions ignore the
    padded tail via ``nanmean`` / ``nanpercentile``.
    """
    if not curves:
        return np.empty((0, 0))
    max_len = max(len(c) for c in curves)
    out = np.full((len(curves), max_len), np.nan, dtype=float)
    for i, c in enumerate(curves):
        out[i, : len(c)] = np.asarray(c, dtype=float)
    return out


def _bootstrap_ci(
    matrix: np.ndarray,
    ci: float,
    n_boot: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sample-wise bootstrap CI from a ``(n_curves, n_samples)`` matrix.

    Returns ``(mean, lower, upper)`` of length ``n_samples``. Resamples
    rows (subjects) with replacement ``n_boot`` times; the percentile
    method gives the band edges.
    """
    n_curves, n_samples = matrix.shape
    if n_curves == 0 or n_samples == 0:
        return np.empty(0), np.empty(0), np.empty(0)

    mean = np.nanmean(matrix, axis=0)
    if n_curves == 1:
        # No CI is meaningful from a single curve — return the curve
        # itself as both bounds so the band collapses to a line.
        return mean, mean.copy(), mean.copy()

    # Resample row indices, average each draw, take percentiles.
    boot_means = np.empty((n_boot, n_samples), dtype=float)
    for b in range(n_boot):
        idx = rng.integers(0, n_curves, size=n_curves)
        boot_means[b] = np.nanmean(matrix[idx], axis=0)
    alpha = (1.0 - ci) / 2.0
    lower = np.nanpercentile(boot_means, 100 * alpha, axis=0)
    upper = np.nanpercentile(boot_means, 100 * (1 - alpha), axis=0)
    return mean, lower, upper


def compare_hrv_curves(
    groups: Mapping[str, Sequence[np.ndarray]],
    ci: float = 0.95,
    n_boot: int = _DEFAULT_N_BOOT,
    seed: Optional[int] = None,
    ax: Optional[pg.PlotWidget] = None,
) -> pg.PlotWidget:
    """Overlay group-mean tachograms with bootstrap CI bands.

    Parameters
    ----------
    groups
        Mapping from group label to a sequence of per-subject RR curves
        (each a 1-D numpy array of RR intervals in ms). Curves can
        differ in length; shorter ones are NaN-padded.
    ci
        Confidence level in (0, 1). Default 0.95.
    n_boot
        Bootstrap resamples per group.
    seed
        Optional seed for reproducible CIs; defaults to OS entropy.
    ax
        Existing ``pg.PlotWidget`` to draw into; a new one is created
        when omitted.

    Returns
    -------
    pg.PlotWidget
        The widget, with one mean line + one CI band per group and a
        legend in the top-left.
    """
    if not 0.0 < ci < 1.0:
        raise ValueError(f"ci must be in (0, 1); got {ci!r}")
    if n_boot < 1:
        raise ValueError(f"n_boot must be >= 1; got {n_boot!r}")

    widget = ax if ax is not None else pg.PlotWidget()
    widget.setBackground("w")
    widget.showGrid(x=True, y=True, alpha=0.3)
    widget.setLabel("left", "RR (ms)")
    widget.setLabel("bottom", "Sample index")
    widget.addLegend(offset=(10, 10))

    rng = np.random.default_rng(seed)
    colours = palette(len(groups))

    for (label, curves), hex_colour in zip(groups.items(), colours):
        matrix = _pad_to_common_length(list(curves))
        if matrix.size == 0:
            continue
        mean, lower, upper = _bootstrap_ci(matrix, ci, n_boot, rng)
        x = np.arange(len(mean), dtype=float)

        base = QColor(hex_colour)
        # Band first so the mean line draws on top.
        fill_colour = QColor(base)
        fill_colour.setAlpha(_BAND_ALPHA)
        lower_item = pg.PlotDataItem(x, lower, pen=pg.mkPen(base, width=0))
        upper_item = pg.PlotDataItem(x, upper, pen=pg.mkPen(base, width=0))
        widget.addItem(lower_item)
        widget.addItem(upper_item)
        band = pg.FillBetweenItem(lower_item, upper_item, brush=fill_colour)
        widget.addItem(band)

        widget.plot(
            x,
            mean,
            pen=pg.mkPen(base, width=2),
            name=f"{label} (n={matrix.shape[0]})",
        )

    return widget
