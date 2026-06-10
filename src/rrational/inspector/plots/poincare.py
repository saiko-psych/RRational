"""Poincare plot widget: RR[n] vs RR[n+1] with SD1/SD2 ellipse.

Mirrors ``rrational.gui.plots.analysis_plots.create_poincare_plot`` but
renders via pyqtgraph. SD1 and SD2 are computed from the FULL input,
even when the scatter is downsampled for rendering.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QVBoxLayout, QWidget

from rrational.gui.color_scheme import ColorScheme
from rrational.inspector.plots.tachogram import MAX_POINTS, _downsample_indices


class PoincarePlot(QWidget):
    """Poincare scatter with SD1/SD2 ellipse.

    Args:
        rr_intervals: RR intervals (ms).
        section_label: Title text.
        color_scheme: ColorScheme to draw with.
    """

    def __init__(
        self,
        rr_intervals,
        section_label: str = "",
        color_scheme: ColorScheme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._color_scheme = color_scheme or ColorScheme()
        rr = np.asarray(list(rr_intervals), dtype=float)
        if len(rr) < 2:
            # Not enough beats — render empty axes and an empty stats dict.
            self.stats: dict[str, object] = {"N pairs": 0}
            self._sd1 = 0.0
            self._sd2 = 0.0
            self._setup_plot(section_label)
            return

        rr_n = rr[:-1]
        rr_n1 = rr[1:]

        diff_rr = rr_n1 - rr_n
        sum_rr = rr_n1 + rr_n
        sd1 = float(np.std(diff_rr) / np.sqrt(2))
        sd2 = float(np.std(sum_rr) / np.sqrt(2))
        sd_ratio = sd1 / sd2 if sd2 > 0 else 0.0

        self._sd1 = sd1
        self._sd2 = sd2
        self.stats = {
            "SD1 (short-term)": f"{sd1:.1f} ms",
            "SD2 (long-term)": f"{sd2:.1f} ms",
            "SD1/SD2": f"{sd_ratio:.2f}",
            "N pairs": int(len(rr_n)),
        }

        self._setup_plot(section_label)

        # ---- Render -----------------------------------------------------
        # Downsample only the scatter; the ellipse, identity line, and
        # SD1/SD2 axes always derive from the full input.
        n_pairs = len(rr_n)
        idx = _downsample_indices(n_pairs, MAX_POINTS)
        x_pts = rr_n[idx]
        y_pts = rr_n1[idx]

        center_x = float(np.mean(rr_n))
        center_y = float(np.mean(rr_n1))

        # Ellipse points rotated 45 deg (semi-major SD2 along identity,
        # semi-minor SD1 perpendicular to it).
        theta = np.linspace(0, 2 * np.pi, 200)
        cos45 = np.cos(np.pi / 4)
        sin45 = np.sin(np.pi / 4)
        ellipse_x = center_x + sd2 * np.cos(theta) * cos45 - sd1 * np.sin(theta) * sin45
        ellipse_y = center_y + sd2 * np.cos(theta) * sin45 + sd1 * np.sin(theta) * cos45

        # Identity line
        all_vals = np.concatenate([rr_n, rr_n1])
        min_val = float(np.min(all_vals)) - 50.0
        max_val = float(np.max(all_vals)) + 50.0
        self._pw.plot(
            [min_val, max_val],
            [min_val, max_val],
            pen=pg.mkPen("#6C757D", width=1, style=Qt.DashLine),
            name="Identity line",
        )

        # Ellipse outline
        self._pw.plot(
            ellipse_x,
            ellipse_y,
            pen=pg.mkPen(self._color_scheme.rr_line, width=2),
            name="SD1/SD2 ellipse",
        )

        # Scatter points
        scatter = pg.ScatterPlotItem(
            x=x_pts,
            y=y_pts,
            size=5,
            brush=pg.mkBrush(pg.mkColor(self._color_scheme.rr_line)),
            pen=pg.mkPen(None),
        )
        self._pw.addItem(scatter)

        # SD1 axis (perpendicular to identity — short-term)
        sd1_x = [center_x - sd1 * sin45, center_x + sd1 * sin45]
        sd1_y = [center_y + sd1 * cos45, center_y - sd1 * cos45]
        self._pw.plot(
            sd1_x,
            sd1_y,
            pen=pg.mkPen("#e74c3c", width=2),
            name=f"SD1 = {sd1:.1f} ms",
        )

        # SD2 axis (along identity — long-term)
        sd2_x = [center_x - sd2 * cos45, center_x + sd2 * cos45]
        sd2_y = [center_y - sd2 * sin45, center_y + sd2 * sin45]
        self._pw.plot(
            sd2_x,
            sd2_y,
            pen=pg.mkPen("#3498db", width=2),
            name=f"SD2 = {sd2:.1f} ms",
        )

        # Center marker
        center_marker = pg.ScatterPlotItem(
            x=[center_x],
            y=[center_y],
            size=12,
            symbol="+",
            brush=pg.mkBrush(self._color_scheme.exclusion),
            pen=pg.mkPen(self._color_scheme.exclusion, width=2),
        )
        self._pw.addItem(center_marker)

        # Lock 1:1 aspect so the ellipse looks like an ellipse.
        self._pw.getViewBox().setAspectLocked(True, ratio=1.0)

    def _setup_plot(self, section_label: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        # Background follows the global pyqtgraph config (dark/light theme).
        self._pw = pg.PlotWidget()
        self._pw.setMinimumHeight(360)
        self._pw.showGrid(x=True, y=True, alpha=0.3)
        self._pw.setLabel("bottom", "RR[n] (ms)")
        self._pw.setLabel("left", "RR[n+1] (ms)")
        if section_label:
            self._pw.setTitle(f"Poincare plot — {section_label}")
        else:
            self._pw.setTitle("Poincare plot")
        layout.addWidget(self._pw, 1)

    # ------------------------------------------------------------------
    @property
    def plot_widget(self) -> pg.PlotWidget:
        return self._pw

    @property
    def sd1(self) -> float:
        return self._sd1

    @property
    def sd2(self) -> float:
        return self._sd2
