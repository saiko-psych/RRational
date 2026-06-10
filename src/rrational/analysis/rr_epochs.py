"""MNE-style epoch container for RR-interval data (Cluster C1).

``RREpochs`` slices a continuous tachogram into fixed-window segments
anchored on event timestamps -- mirroring ``mne.Epochs`` for HRV. Each
epoch shares the same ``[tmin, tmax]`` window relative to its trigger,
so ``average()``, ``apply_baseline()``, and ``drop_bad()`` work the
same way they do on EEG epochs.

Design notes:
- Time axis is the **wall-clock** seconds (matches ``InspectorData.t``);
  epochs are indexed by the original event timestamp so users can
  re-join epochs to events by exact match.
- Resampling onto a regular grid uses ``np.interp`` with NaN handling
  borrowed from analysis/annotation_filter.py; epochs that fall fully
  inside a gap are dropped automatically and surfaced in ``drop_log``.
- ``metadata`` is a pandas DataFrame keyed by epoch index, identical
  in spirit to ``mne.Epochs.metadata``; subset-by-query is implemented
  via ``DataFrame.query`` for the ``epochs["condition == 'rest'"]``
  pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class RREpochs:
    """Fixed-window epochs over a continuous RR tachogram.

    Parameters
    ----------
    t
        1-D array of wall-clock seconds for the source signal.
    rr
        1-D array of RR-ms aligned to ``t`` (same length).
    events
        1-D array of event timestamps in the same wall-clock frame.
        Each event becomes one epoch (subject to bounds checks).
    tmin, tmax
        Epoch window in seconds relative to each event. Defaults
        match the music-HRV convention (30 s baseline, 120 s post).
    metadata
        Optional pandas DataFrame, one row per event, attached so
        ``epochs["col == 'x'"]`` can subset by condition.
    baseline
        Optional ``(b_tmin, b_tmax)`` tuple (relative to event) that
        ``apply_baseline`` subtracts. Stored for reproducibility.
    """

    t: np.ndarray
    rr: np.ndarray
    events: np.ndarray
    tmin: float = -30.0
    tmax: float = 120.0
    metadata: Optional["pd.DataFrame"] = None  # type: ignore[name-defined]
    baseline: Optional[tuple[float, float]] = None

    # Filled in __post_init__
    _epoch_data: np.ndarray = field(init=False, repr=False)
    _times: np.ndarray = field(init=False, repr=False)
    _drop_mask: np.ndarray = field(init=False, repr=False)
    drop_log: list[tuple[int, str]] = field(default_factory=list, init=False)

    # Output sample rate of the resampled grid (Hz). 4 Hz is the
    # standard HRV-resampling rate for spectral metrics; we reuse it
    # here so downstream PSD/spectral epoch analyses stay drop-in.
    _sample_rate: float = field(default=4.0, init=False)

    def __post_init__(self) -> None:
        if self.tmin >= self.tmax:
            raise ValueError(f"tmin ({self.tmin}) must be < tmax ({self.tmax})")

        n_samples = int(round((self.tmax - self.tmin) * self._sample_rate)) + 1
        self._times = np.linspace(self.tmin, self.tmax, n_samples)

        n_events = len(self.events)
        self._epoch_data = np.full((n_events, n_samples), np.nan, dtype=float)
        self._drop_mask = np.zeros(n_events, dtype=bool)
        self.drop_log = []

        t_arr = np.asarray(self.t, dtype=float)
        rr_arr = np.asarray(self.rr, dtype=float)
        finite = np.isfinite(t_arr) & np.isfinite(rr_arr)
        t_finite = t_arr[finite]
        rr_finite = rr_arr[finite]

        for i, ev_t in enumerate(self.events):
            window_start = ev_t + self.tmin
            window_end = ev_t + self.tmax
            if (
                t_finite.size == 0
                or window_end < t_finite[0]
                or window_start > t_finite[-1]
            ):
                self._drop_mask[i] = True
                self.drop_log.append((i, "OUT_OF_BOUNDS"))
                continue
            in_window = (t_finite >= window_start) & (t_finite <= window_end)
            if not np.any(in_window):
                self._drop_mask[i] = True
                self.drop_log.append((i, "EMPTY_WINDOW"))
                continue
            # Interpolate onto the uniform grid; np.interp clips to the
            # endpoints which would bias gap edges, so we explicitly
            # NaN-mask samples outside the available range.
            grid_t = ev_t + self._times
            interp = np.interp(grid_t, t_finite, rr_finite)
            interp[grid_t < t_finite[0]] = np.nan
            interp[grid_t > t_finite[-1]] = np.nan
            self._epoch_data[i] = interp

    # ------------------------------------------------------------------
    # MNE-like API
    # ------------------------------------------------------------------
    def __len__(self) -> int:
        """Number of *kept* epochs."""
        return int(np.sum(~self._drop_mask))

    @property
    def times(self) -> np.ndarray:
        """Relative-time axis shared by all epochs."""
        return self._times

    def get_data(self) -> np.ndarray:
        """Return the ``(n_epochs, n_samples)`` array of kept epochs."""
        return self._epoch_data[~self._drop_mask]

    def average(self) -> tuple[np.ndarray, np.ndarray]:
        """Return ``(times, mean_rr)`` averaged across kept epochs.

        NaN-aware so partial gap-coverage doesn't drop the whole sample.
        """
        kept = self.get_data()
        if kept.size == 0:
            return self._times.copy(), np.full_like(self._times, np.nan)
        return self._times.copy(), np.nanmean(kept, axis=0)

    def apply_baseline(self, baseline: tuple[float, float]) -> "RREpochs":
        """Subtract the mean of the baseline window from each epoch (in-place)."""
        b_tmin, b_tmax = baseline
        if b_tmin >= b_tmax:
            raise ValueError(f"baseline tmin ({b_tmin}) must be < tmax ({b_tmax})")
        mask = (self._times >= b_tmin) & (self._times <= b_tmax)
        if not np.any(mask):
            raise ValueError(
                f"baseline window {baseline} lies outside epoch range "
                f"[{self.tmin}, {self.tmax}]"
            )
        means = np.nanmean(self._epoch_data[:, mask], axis=1, keepdims=True)
        self._epoch_data = self._epoch_data - means
        self.baseline = (float(b_tmin), float(b_tmax))
        return self

    def drop_bad(self, reject: Optional[dict] = None) -> "RREpochs":
        """Drop epochs whose peak-to-peak amplitude exceeds ``reject['rr']``.

        Mirrors MNE's ``reject={"eeg": 100e-6}`` interface. With no
        ``reject`` dict, this method is a no-op so callers can chain
        ``epochs.drop_bad().average()`` without branching.
        """
        if not reject:
            return self
        threshold = reject.get("rr")
        if threshold is None:
            return self
        for i in range(len(self.events)):
            if self._drop_mask[i]:
                continue
            ep = self._epoch_data[i]
            if np.all(np.isnan(ep)):
                continue
            ptp = float(np.nanmax(ep) - np.nanmin(ep))
            if ptp > threshold:
                self._drop_mask[i] = True
                self.drop_log.append((i, f"PTP>{threshold}"))
        return self

    def to_data_frame(self):
        """Long-format DataFrame: one row per (epoch_idx, time, rr) point."""
        import pandas as pd

        kept_indices = np.where(~self._drop_mask)[0]
        rows = []
        for keep_pos, ev_idx in enumerate(kept_indices):
            ep = self._epoch_data[ev_idx]
            for j, ti in enumerate(self._times):
                rows.append(
                    {
                        "epoch": int(keep_pos),
                        "event_idx": int(ev_idx),
                        "time": float(ti),
                        "rr_ms": float(ep[j]) if np.isfinite(ep[j]) else np.nan,
                    }
                )
        return pd.DataFrame(rows)

    def __getitem__(self, key) -> "RREpochs":
        """Subset by integer index, slice, or pandas-style query string.

        ``epochs[3]``               -> single-epoch view
        ``epochs[0:5]``             -> first 5 epochs
        ``epochs["cond == 'rest'"]`` -> metadata-based subset
        """
        kept_idx = np.where(~self._drop_mask)[0]

        if isinstance(key, str):
            if self.metadata is None:
                raise ValueError("query-string subset requires metadata DataFrame")
            sub = self.metadata.iloc[kept_idx].query(key)
            keep = sub.index.to_numpy()
        elif isinstance(key, slice):
            keep = kept_idx[key]
        elif isinstance(key, (int, np.integer)):
            keep = np.array([kept_idx[int(key)]])
        else:
            keep = np.asarray(kept_idx)[np.asarray(key)]

        new = RREpochs.__new__(RREpochs)
        new.t = self.t
        new.rr = self.rr
        new.events = self.events[keep] if len(keep) > 0 else np.array([])
        new.tmin = self.tmin
        new.tmax = self.tmax
        new.metadata = (
            self.metadata.iloc[keep].reset_index(drop=True)
            if self.metadata is not None and len(keep) > 0
            else None
        )
        new.baseline = self.baseline
        new._sample_rate = self._sample_rate
        new._times = self._times.copy()
        # Pull the per-event rows from the parent's already-computed data
        # rather than recomputing -- preserves apply_baseline state.
        if len(keep) > 0:
            new._epoch_data = self._epoch_data[keep].copy()
            new._drop_mask = np.zeros(len(keep), dtype=bool)
        else:
            new._epoch_data = np.empty((0, len(self._times)))
            new._drop_mask = np.array([], dtype=bool)
        new.drop_log = []
        return new
