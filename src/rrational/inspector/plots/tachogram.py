"""Tachogram widget: RR vs beat-index with mean and SD bands.

Mirrors the science of
``rrational.gui.plots.analysis_plots.create_professional_tachogram`` —
mean, +/-1 SD and +/-2 SD bands, plus optional artifact markers — but
renders via pyqtgraph for the inspector. Plotly's HTML pipeline is
disallowed (CLAUDE.md "NEVER use Plotly JSON serialization").

Downsamples to ``MAX_POINTS`` beats before rendering per CLAUDE.md
performance rules; statistics are always computed on the full input.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QVBoxLayout, QWidget

from rrational.gui.color_scheme import ColorScheme

# Per CLAUDE.md: downsample plot data above 5000 points.
MAX_POINTS = 5000


def _qcolor_with_alpha(color: str, alpha: int) -> pg.QtGui.QColor:
    """Return a ``QColor`` for ``color`` (hex or rgb/rgba string) with ``alpha``."""
    qc = pg.mkColor(color)
    qc.setAlpha(alpha)
    return qc


def _downsample_indices(n_beats: int, max_points: int = MAX_POINTS) -> np.ndarray:
    """Return evenly-spaced indices into a length-``n_beats`` array.

    No-op when ``n_beats <= max_points``; otherwise picks ``max_points``
    indices via ``np.linspace`` (rounded). Statistics consumers ignore
    these indices — they're for rendering only.
    """
    if n_beats <= max_points:
        return np.arange(n_beats)
    return np.linspace(0, n_beats - 1, max_points, dtype=int)


class TachogramPlot(QWidget):
    """RR-interval plot with mean and SD bands.

    Args:
        rr_intervals: RR intervals in milliseconds.
        section_label: Title text shown above the plot.
        artifact_indices: Optional indices into ``rr_intervals`` to mark
            with the artifact colour.
        color_scheme: ColorScheme to draw with (defaults to scientific).
    """

    def __init__(
        self,
        rr_intervals,
        section_label: str = "",
        artifact_indices: list[int] | None = None,
        color_scheme: ColorScheme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._color_scheme = color_scheme or ColorScheme()
        rr = np.asarray(list(rr_intervals), dtype=float)
        self._rr = rr
        self._artifact_indices = [
            int(i) for i in (artifact_indices or []) if 0 <= int(i) < len(rr)
        ]
        n_beats = len(rr)

        # Stats computed on the FULL input — downsampling is render-only.
        if n_beats == 0:
            self.stats: dict[str, object] = {"N beats": 0}
        else:
            mean_rr = float(np.mean(rr))
            std_rr = float(np.std(rr))
            min_rr = float(np.min(rr))
            max_rr = float(np.max(rr))
            mean_hr = 60000.0 / mean_rr if mean_rr > 0 else float("nan")
            self.stats = {
                "N beats": n_beats,
                "Mean RR": f"{mean_rr:.1f} ms",
                "SD": f"{std_rr:.1f} ms",
                "Mean HR": f"{mean_hr:.1f} bpm",
                "Range": f"{min_rr:.0f} - {max_rr:.0f} ms",
            }
            if self._artifact_indices:
                self.stats["Artifacts"] = len(self._artifact_indices)

        # ---- Plot widget setup ------------------------------------------
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._pw = pg.PlotWidget(background="w")
        self._pw.setMinimumHeight(320)
        self._pw.showGrid(x=True, y=True, alpha=0.3)
        self._pw.setLabel("bottom", "Beat number")
        self._pw.setLabel("left", "RR interval (ms)")
        if section_label:
            self._pw.setTitle(f"Tachogram — {section_label}")
        else:
            self._pw.setTitle("Tachogram")
        layout.addWidget(self._pw, 1)

        if n_beats == 0:
            return

        # ---- Render -----------------------------------------------------
        idx = _downsample_indices(n_beats)
        rr_render = rr[idx]
        x = idx.astype(float)

        # SD bands rendered as FillBetweenItem between two horizontal lines.
        full_x = np.array([0.0, max(1.0, float(n_beats - 1))])
        band_alpha2 = _qcolor_with_alpha(self._color_scheme.rr_line, 32)
        band_alpha1 = _qcolor_with_alpha(self._color_scheme.rr_line, 56)

        top2 = pg.PlotCurveItem(full_x, [mean_rr + 2 * std_rr] * 2, pen=pg.mkPen(None))
        bot2 = pg.PlotCurveItem(full_x, [mean_rr - 2 * std_rr] * 2, pen=pg.mkPen(None))
        self._pw.addItem(top2)
        self._pw.addItem(bot2)
        band2 = pg.FillBetweenItem(top2, bot2, brush=band_alpha2)
        self._pw.addItem(band2)

        top1 = pg.PlotCurveItem(full_x, [mean_rr + std_rr] * 2, pen=pg.mkPen(None))
        bot1 = pg.PlotCurveItem(full_x, [mean_rr - std_rr] * 2, pen=pg.mkPen(None))
        self._pw.addItem(top1)
        self._pw.addItem(bot1)
        band1 = pg.FillBetweenItem(top1, bot1, brush=band_alpha1)
        self._pw.addItem(band1)

        # Mean line
        mean_pen = pg.mkPen(self._color_scheme.exclusion, width=2, style=Qt.DashLine)
        self._pw.plot(
            full_x,
            [mean_rr, mean_rr],
            pen=mean_pen,
            name=f"Mean ({mean_rr:.0f} ms)",
        )

        # RR curve
        rr_pen = pg.mkPen(self._color_scheme.rr_line, width=1)
        self._pw.plot(
            x,
            rr_render,
            pen=rr_pen,
            symbol=None,
            name="RR intervals",
        )

        # Artifact markers (small scatter, X symbol). Drawn last so
        # they sit on top of the line.
        if self._artifact_indices:
            ai = np.array(self._artifact_indices, dtype=int)
            scatter = pg.ScatterPlotItem(
                x=ai.astype(float),
                y=rr[ai],
                symbol="x",
                size=10,
                brush=pg.mkBrush(self._color_scheme.artifact),
                pen=pg.mkPen(self._color_scheme.artifact, width=2),
                name=f"Artifacts ({len(self._artifact_indices)})",
            )
            self._artifact_scatter = scatter
            self._pw.addItem(scatter)

    # ------------------------------------------------------------------
    # Test-facing accessors
    # ------------------------------------------------------------------
    @property
    def plot_widget(self) -> pg.PlotWidget:
        return self._pw

    def artifact_marker_count(self) -> int:
        scatter = getattr(self, "_artifact_scatter", None)
        if scatter is None:
            return 0
        return len(scatter.data)
