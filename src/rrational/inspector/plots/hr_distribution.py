"""Heart-rate distribution widget: histogram + KDE + mean line.

Mirrors ``rrational.gui.plots.analysis_plots.create_hr_distribution_plot``
but rendered via pyqtgraph. Counts are kept on the same axis as the
KDE (scaled so the area under the curve matches the histogram's total
count) — same approach as the Streamlit plot.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QVBoxLayout, QWidget

from rrational.gui.color_scheme import ColorScheme


class HRDistributionPlot(QWidget):
    """Histogram of instantaneous HR (bpm) with KDE overlay.

    Args:
        rr_intervals: RR intervals (ms). HR = 60 000 / RR.
        section_label: Title text.
        bins: Histogram bin count.
        color_scheme: ColorScheme.
    """

    def __init__(
        self,
        rr_intervals,
        section_label: str = "",
        bins: int = 30,
        color_scheme: ColorScheme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._color_scheme = color_scheme or ColorScheme()
        rr = np.asarray(list(rr_intervals), dtype=float)
        rr = rr[rr > 0]  # guard against division by zero

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # Background follows the global pyqtgraph config (dark/light theme).
        self._pw = pg.PlotWidget()
        self._pw.setMinimumHeight(320)
        self._pw.showGrid(x=True, y=True, alpha=0.3)
        self._pw.setLabel("bottom", "Heart rate (bpm)")
        self._pw.setLabel("left", "Count")
        if section_label:
            self._pw.setTitle(f"Heart rate distribution — {section_label}")
        else:
            self._pw.setTitle("Heart rate distribution")
        layout.addWidget(self._pw, 1)

        if len(rr) == 0:
            self.stats: dict[str, object] = {"N beats": 0}
            return

        hr = 60000.0 / rr
        mean_hr = float(np.mean(hr))
        std_hr = float(np.std(hr))
        min_hr = float(np.min(hr))
        max_hr = float(np.max(hr))
        self.stats = {
            "Mean HR": f"{mean_hr:.1f} bpm",
            "SD": f"{std_hr:.1f} bpm",
            "Min": f"{min_hr:.0f} bpm",
            "Max": f"{max_hr:.0f} bpm",
            "Range": f"{max_hr - min_hr:.0f} bpm",
        }

        # ---- Histogram (BarGraphItem) -----------------------------------
        counts, edges = np.histogram(hr, bins=bins)
        widths = np.diff(edges)
        centers = edges[:-1] + widths / 2.0
        bars = pg.BarGraphItem(
            x=centers,
            height=counts,
            width=widths * 0.95,
            brush=pg.mkBrush(self._color_scheme.rr_line),
            pen=pg.mkPen(None),
        )
        self._pw.addItem(bars)

        # ---- KDE overlay (scipy.gaussian_kde) ---------------------------
        if len(hr) >= 2 and np.std(hr) > 0:
            try:
                from scipy import stats as _stats

                kde = _stats.gaussian_kde(hr)
                x_kde = np.linspace(min_hr - 5, max_hr + 5, 300)
                y_kde = kde(x_kde)
                # Scale so the integral matches the histogram's total count.
                bin_width = float(np.mean(widths))
                y_kde_scaled = y_kde * float(len(hr)) * bin_width
                self._pw.plot(
                    x_kde,
                    y_kde_scaled,
                    pen=pg.mkPen(self._color_scheme.nn_line, width=3),
                    name="Density",
                )
            except Exception:  # pragma: no cover - scipy missing
                pass

        # ---- Mean line --------------------------------------------------
        mean_line = pg.InfiniteLine(
            pos=mean_hr,
            angle=90,
            pen=pg.mkPen(self._color_scheme.exclusion, width=2, style=Qt.DashLine),
            label=f"Mean: {mean_hr:.1f}",
            labelOpts={"position": 0.9, "color": self._color_scheme.exclusion},
        )
        self._pw.addItem(mean_line)

    # ------------------------------------------------------------------
    @property
    def plot_widget(self) -> pg.PlotWidget:
        return self._pw
