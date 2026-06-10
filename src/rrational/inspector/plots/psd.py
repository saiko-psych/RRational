"""Power spectral density widget.

Mirrors the science of
``rrational.gui.plots.analysis_plots.create_frequency_domain_plot``:
RR-tachogram interpolated at ``sampling_rate`` (default 4 Hz), Welch
PSD, integrated VLF/LF/HF band powers, and the spectrum drawn with
coloured band shadings underneath. Rendered via pyqtgraph.

The PSD trace is already heavily smoothed by Welch — no extra
downsampling required.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from qtpy.QtWidgets import QVBoxLayout, QWidget

from rrational.gui.color_scheme import ColorScheme

# Standard HRV frequency band edges (Hz)
VLF_LO, VLF_HI = 0.0033, 0.04
LF_LO, LF_HI = 0.04, 0.15
HF_LO, HF_HI = 0.15, 0.4


def _parse_color(color: str) -> pg.QtGui.QColor:
    """Parse a colour string into a QColor.

    Accepts both standard ``pg.mkColor`` inputs (hex, name) and CSS
    ``rgba(r, g, b, a)`` strings, which ``pg.mkColor`` cannot handle
    directly across all Qt bindings.
    """
    if isinstance(color, str) and color.strip().lower().startswith("rgba"):
        inside = color[color.index("(") + 1 : color.rindex(")")]
        parts = [p.strip() for p in inside.split(",")]
        r = int(float(parts[0]))
        g = int(float(parts[1]))
        b = int(float(parts[2]))
        a = int(round(float(parts[3]) * 255)) if len(parts) > 3 else 255
        return pg.QtGui.QColor(r, g, b, a)
    return pg.mkColor(color)


def _qcolor(color: str) -> pg.QtGui.QColor:
    return _parse_color(color)


def _band_brush(color: str) -> pg.QtGui.QBrush:
    """Make a translucent brush for a frequency-band shading.

    ``ColorScheme.lf_band`` etc. already encode their own alpha (rgba
    strings); we parse those manually since ``pg.mkColor`` does not
    accept the CSS ``rgba(...)`` form across Qt bindings.
    """
    return pg.mkBrush(_parse_color(color))


class PSDPlot(QWidget):
    """RR-interval power spectral density with VLF/LF/HF band shading.

    Args:
        rr_intervals: RR intervals (ms).
        section_label: Title text.
        sampling_rate: Resampling rate (Hz) for the uniform time series
            that Welch operates on. Default 4 Hz (HRV convention).
        color_scheme: ColorScheme — only the band fill colours are used.
    """

    def __init__(
        self,
        rr_intervals,
        section_label: str = "",
        sampling_rate: int = 4,
        color_scheme: ColorScheme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._color_scheme = color_scheme or ColorScheme()
        rr = np.asarray(list(rr_intervals), dtype=float)
        self.stats: dict[str, object] = {}
        self._band_shadings: list[pg.LinearRegionItem] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # Background follows the global pyqtgraph config (dark/light theme).
        self._pw = pg.PlotWidget()
        self._pw.setMinimumHeight(320)
        self._pw.showGrid(x=True, y=True, alpha=0.3)
        self._pw.setLabel("bottom", "Frequency (Hz)")
        self._pw.setLabel("left", "Power (ms^2/Hz)")
        if section_label:
            self._pw.setTitle(f"Power spectral density — {section_label}")
        else:
            self._pw.setTitle("Power spectral density")
        layout.addWidget(self._pw, 1)

        if len(rr) < 16:
            return

        try:
            from scipy import signal as _signal
        except ImportError:
            return

        # Interpolate the irregular RR tachogram onto a uniform grid.
        time_rr = np.cumsum(rr) / 1000.0
        time_rr = time_rr - time_rr[0]
        duration = float(time_rr[-1])
        if duration <= 0:
            return
        time_uniform = np.arange(0, duration, 1.0 / sampling_rate)
        if len(time_uniform) < 16:
            return
        rr_interp = np.interp(time_uniform, time_rr, rr)
        rr_detrend = rr_interp - np.mean(rr_interp)

        nperseg = min(256, len(rr_detrend) // 2)
        if nperseg < 16:
            nperseg = len(rr_detrend)

        freqs, psd = _signal.welch(rr_detrend, fs=sampling_rate, nperseg=nperseg)
        mask = freqs <= 0.5
        freqs = freqs[mask]
        psd = psd[mask]

        # Band integrals (trapezoidal). ``np.trapezoid`` was added in
        # NumPy 2.0; ``trapz`` is deprecated. Use whichever is present.
        try:
            integrate = np.trapezoid
        except AttributeError:  # pragma: no cover - NumPy < 2.0
            integrate = np.trapz

        vlf_mask = (freqs >= VLF_LO) & (freqs < VLF_HI)
        lf_mask = (freqs >= LF_LO) & (freqs < LF_HI)
        hf_mask = (freqs >= HF_LO) & (freqs <= HF_HI)
        vlf_power = (
            float(integrate(psd[vlf_mask], freqs[vlf_mask]))
            if np.any(vlf_mask)
            else 0.0
        )
        lf_power = (
            float(integrate(psd[lf_mask], freqs[lf_mask])) if np.any(lf_mask) else 0.0
        )
        hf_power = (
            float(integrate(psd[hf_mask], freqs[hf_mask])) if np.any(hf_mask) else 0.0
        )
        total = vlf_power + lf_power + hf_power
        lf_hf_ratio = lf_power / hf_power if hf_power > 0 else 0.0

        self.stats = {
            "VLF Power": f"{vlf_power:.1f} ms^2",
            "LF Power": f"{lf_power:.1f} ms^2",
            "HF Power": f"{hf_power:.1f} ms^2",
            "LF/HF Ratio": f"{lf_hf_ratio:.2f}",
            "Total Power": f"{total:.1f} ms^2",
        }

        # ---- Band shadings (3 LinearRegionItem) -------------------------
        for lo, hi, color in (
            (VLF_LO, VLF_HI, self._color_scheme.vlf_band),
            (LF_LO, LF_HI, self._color_scheme.lf_band),
            (HF_LO, HF_HI, self._color_scheme.hf_band),
        ):
            region = pg.LinearRegionItem(
                values=(lo, hi),
                orientation="vertical",
                brush=_band_brush(color),
                movable=False,
            )
            # Reduce the line pens of the region's two InfiniteLines so
            # only the shading is visible.
            for line in region.lines:
                line.setPen(pg.mkPen(None))
            region.setZValue(-10)
            self._pw.addItem(region)
            self._band_shadings.append(region)

        # ---- PSD curve --------------------------------------------------
        self._pw.plot(
            freqs,
            psd,
            pen=pg.mkPen(self._color_scheme.rr_line, width=2),
            name="PSD",
        )
        self._pw.setXRange(0, 0.5, padding=0)
        self._pw.setYRange(0, float(np.max(psd)) * 1.1 if len(psd) else 1.0, padding=0)

    # ------------------------------------------------------------------
    @property
    def plot_widget(self) -> pg.PlotWidget:
        return self._pw

    def band_shading_count(self) -> int:
        return len(self._band_shadings)
