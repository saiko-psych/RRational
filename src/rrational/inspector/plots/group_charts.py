"""Group-comparison chart widgets for the inspector.

Reimplements the Streamlit group-plot helpers (Plotly Bar / Box /
Violin / SD1-vs-SD2 scatter) on top of pyqtgraph. Each widget consumes
a long-format ``pandas.DataFrame`` with columns

    participant_id, group, section, <metric_lowercase> ...

— the same shape ``rrational.analysis.hrv_compute.results_to_long_df``
emits. A convenience function ``results_store_to_long_df`` builds the
same shape from an inspector ``ResultsStore``.

Pyqtgraph has no native box / violin primitive; we draw five-number-
summary box outlines + outlier scatter, and KDE-shaded violins via
``FillBetweenItem``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pyqtgraph as pg
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QVBoxLayout, QWidget

from rrational.analysis.group_statistics import should_log_transform
from rrational.gui.color_scheme import ColorScheme
from rrational.inspector.results_store import ResultsStore


# ---------------------------------------------------------------------
# ResultsStore -> long-format DataFrame
# ---------------------------------------------------------------------
def results_store_to_long_df(
    store: ResultsStore,
    group_label_by_dataset: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Flatten an inspector ``ResultsStore`` into a long-format DataFrame.

    Every ``MetricRow`` becomes one row. ``group`` is taken from
    ``group_label_by_dataset`` (the Analysis tab's per-dataset group
    assignment) when present; falls back to ``"(unassigned)"``.

    The returned columns match what the group-plot widgets expect:
    ``participant_id``, ``group``, ``section``, plus one lowercase
    column per metric.
    """
    rows: list[dict[str, object]] = []
    assign = group_label_by_dataset or {}
    for r in store.metric_rows:
        row: dict[str, object] = {
            "participant_id": r.dataset,
            "group": assign.get(r.dataset, "(unassigned)") or "(unassigned)",
            "section": r.section,
            "n_beats": int(r.n_beats),
        }
        for key, val in (r.metrics or {}).items():
            row[key.lower()] = val
        rows.append(row)
    return pd.DataFrame(rows)


def _palette(scheme: ColorScheme | None) -> list[str]:
    return (scheme or ColorScheme()).group_palette


def _safe_metric_col(df: pd.DataFrame, metric: str) -> str | None:
    """Return the lowercase column name for ``metric`` if present."""
    lower = metric.lower()
    if lower in df.columns:
        return lower
    return None


# ---------------------------------------------------------------------
# Bar chart
# ---------------------------------------------------------------------
class GroupBarChart(QWidget):
    """Grouped bar chart: bars per (group, section), with error bars.

    Args:
        metric: HRV metric to plot (e.g. "RMSSD", "LF").
        long_df: Long-format DataFrame (one row per participant/section).
        error_bar_type: "SD" | "SEM" | "CI95" | "None".
        log_y: If ``None``, auto-enable for log-normal metrics (LF/HF/...).
        show_points: Overlay individual participant points (jittered).
        color_scheme: ColorScheme — section colours come from group_palette.
        section_order: Optional explicit ordering for sections.
    """

    def __init__(
        self,
        metric: str,
        long_df: pd.DataFrame,
        error_bar_type: str = "SD",
        log_y: bool | None = None,
        show_points: bool = False,
        color_scheme: ColorScheme | None = None,
        section_order: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._color_scheme = color_scheme or ColorScheme()
        self._metric = metric.upper()
        self._error_bar_type = error_bar_type
        # Auto-log-y for log-normal HRV metrics (LF/HF/VLF/TP/LF_HF/LFN/HFN).
        self._log_y = should_log_transform(metric) if log_y is None else bool(log_y)
        self._bar_count = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._pw = pg.PlotWidget()
        self._pw.setMinimumHeight(360)
        self._pw.showGrid(x=True, y=True, alpha=0.3)
        self._pw.setLabel("bottom", "Group")
        self._pw.setLabel("left", self._metric)
        self._pw.setTitle(f"{self._metric} by group and section")
        layout.addWidget(self._pw, 1)

        metric_col = _safe_metric_col(long_df, self._metric)
        if metric_col is None or long_df.empty:
            return

        # Filter to rows that have a finite metric value AND a group label.
        df = long_df[long_df[metric_col].notna()].copy()
        df = df[df["group"].astype(str).str.len() > 0]
        if df.empty:
            return

        groups = sorted(df["group"].unique().tolist())
        sections = section_order or sorted(df["section"].unique().tolist())
        n_sections = max(1, len(sections))
        palette = _palette(self._color_scheme)

        # Each (group, section) gets a bar at x = group_idx + section_offset.
        # bar_width is small enough that adjacent groups don't overlap.
        bar_width_fraction = 0.75
        slot = bar_width_fraction / n_sections
        bar_width = slot * 0.9

        rng = np.random.default_rng(42)

        for s_idx, section in enumerate(sections):
            offset = (s_idx - (n_sections - 1) / 2.0) * slot
            xs: list[float] = []
            heights: list[float] = []
            err_lo: list[float] = []
            err_hi: list[float] = []
            for g_idx, group in enumerate(groups):
                vals = df[(df["group"] == group) & (df["section"] == section)][
                    metric_col
                ].to_numpy()
                vals = vals[np.isfinite(vals)]
                if len(vals) == 0:
                    continue
                mean = float(np.mean(vals))
                sd = float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0
                err = _error_magnitude(sd, len(vals), error_bar_type)
                xs.append(g_idx + offset)
                heights.append(mean)
                err_lo.append(err)
                err_hi.append(err)

                # Individual point overlay
                if show_points and len(vals) > 0:
                    jitter = rng.uniform(-slot * 0.15, slot * 0.15, size=len(vals))
                    pts_x = (g_idx + offset) + jitter
                    # Theme-aware point overlay: pure black is invisible on
                    # the dark theme. Use the foreground colour pyqtgraph
                    # picks up from the global config so the point dots
                    # contrast with whichever background the user has set.
                    fg = pg.getConfigOption("foreground")
                    scatter = pg.ScatterPlotItem(
                        x=pts_x,
                        y=vals,
                        size=4,
                        brush=pg.mkBrush(pg.mkColor(fg)),
                        pen=pg.mkPen(None),
                    )
                    self._pw.addItem(scatter)

            if not xs:
                continue
            color = palette[s_idx % len(palette)]
            bars = pg.BarGraphItem(
                x=xs,
                height=heights,
                width=bar_width,
                brush=pg.mkBrush(color),
                pen=pg.mkPen(color),
                name=section,
            )
            self._pw.addItem(bars)
            self._bar_count += len(xs)

            if error_bar_type != "None":
                # Error bar pen matches foreground so it stays visible
                # against either dark or light backgrounds (previously
                # hardcoded "#333", invisible on the dark theme).
                err_item = pg.ErrorBarItem(
                    x=np.asarray(xs, dtype=float),
                    y=np.asarray(heights, dtype=float),
                    top=np.asarray(err_hi, dtype=float),
                    bottom=np.asarray(err_lo, dtype=float),
                    pen=pg.mkPen(pg.getConfigOption("foreground"), width=1),
                    beam=bar_width * 0.4,
                )
                self._pw.addItem(err_item)

        # X-axis ticks: group labels at integer positions.
        ax = self._pw.getAxis("bottom")
        ax.setTicks([list(zip(range(len(groups)), groups))])
        self._pw.setXRange(-0.5, len(groups) - 0.5, padding=0.05)

        if self._log_y:
            self._pw.setLogMode(x=False, y=True)

    # ------------------------------------------------------------------
    @property
    def plot_widget(self) -> pg.PlotWidget:
        return self._pw

    @property
    def bar_count(self) -> int:
        return self._bar_count

    def is_log_y(self) -> bool:
        return self._log_y


def _error_magnitude(sd: float, n: int, error_type: str) -> float:
    """Convert SD + n into the error-bar half-width for the chosen type."""
    import math

    if error_type == "None" or n < 1 or sd is None or not np.isfinite(sd):
        return 0.0
    if error_type == "SD":
        return float(sd)
    sem = float(sd) / math.sqrt(n) if n > 0 else 0.0
    if error_type == "SEM":
        return sem
    if error_type == "CI95":
        return 1.96 * sem
    return float(sd)


# ---------------------------------------------------------------------
# Box plot (5-number summary)
# ---------------------------------------------------------------------
class GroupBoxPlot(QWidget):
    """Custom box plot: Q1 / median / Q3 outlines + whiskers + outliers.

    Args:
        metric: HRV metric.
        long_df: Long-format DataFrame.
        color_scheme: ColorScheme — group_palette colours by section.
        section_order: Explicit section ordering.
    """

    def __init__(
        self,
        metric: str,
        long_df: pd.DataFrame,
        color_scheme: ColorScheme | None = None,
        section_order: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._color_scheme = color_scheme or ColorScheme()
        self._metric = metric.upper()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._pw = pg.PlotWidget()
        self._pw.setMinimumHeight(360)
        self._pw.showGrid(x=True, y=True, alpha=0.3)
        self._pw.setLabel("bottom", "Group")
        self._pw.setLabel("left", self._metric)
        self._pw.setTitle(f"{self._metric} distribution by group")
        layout.addWidget(self._pw, 1)

        metric_col = _safe_metric_col(long_df, self._metric)
        if metric_col is None or long_df.empty:
            return
        df = long_df[long_df[metric_col].notna()].copy()
        df = df[df["group"].astype(str).str.len() > 0]
        if df.empty:
            return

        groups = sorted(df["group"].unique().tolist())
        sections = section_order or sorted(df["section"].unique().tolist())
        n_sections = max(1, len(sections))
        palette = _palette(self._color_scheme)
        slot = 0.75 / n_sections
        box_width = slot * 0.6

        for s_idx, section in enumerate(sections):
            color = palette[s_idx % len(palette)]
            for g_idx, group in enumerate(groups):
                vals = df[(df["group"] == group) & (df["section"] == section)][
                    metric_col
                ].to_numpy()
                vals = vals[np.isfinite(vals)]
                if len(vals) < 1:
                    continue
                center_x = g_idx + (s_idx - (n_sections - 1) / 2.0) * slot
                self._draw_box(center_x, vals, box_width, color)

        ax = self._pw.getAxis("bottom")
        ax.setTicks([list(zip(range(len(groups)), groups))])
        self._pw.setXRange(-0.5, len(groups) - 0.5, padding=0.05)

    def _draw_box(
        self,
        center_x: float,
        vals: np.ndarray,
        width: float,
        color: str,
    ) -> None:
        q1, median, q3 = np.percentile(vals, [25, 50, 75])
        iqr = q3 - q1
        lo_whisker = max(float(np.min(vals)), float(q1 - 1.5 * iqr))
        hi_whisker = min(float(np.max(vals)), float(q3 + 1.5 * iqr))
        outliers = vals[(vals < lo_whisker) | (vals > hi_whisker)]

        pen = pg.mkPen(color, width=2)

        # Box body (rectangle): left + right vertical, top + bottom horizontal.
        x0 = center_x - width / 2.0
        x1 = center_x + width / 2.0
        # bottom (Q1)
        self._pw.plot([x0, x1], [q1, q1], pen=pen)
        # top (Q3)
        self._pw.plot([x0, x1], [q3, q3], pen=pen)
        # left
        self._pw.plot([x0, x0], [q1, q3], pen=pen)
        # right
        self._pw.plot([x1, x1], [q1, q3], pen=pen)
        # median
        median_pen = pg.mkPen(color, width=3)
        self._pw.plot([x0, x1], [median, median], pen=median_pen)
        # whiskers (vertical line + cap)
        self._pw.plot([center_x, center_x], [lo_whisker, q1], pen=pen)
        self._pw.plot([center_x, center_x], [q3, hi_whisker], pen=pen)
        cap_w = width * 0.5
        self._pw.plot(
            [center_x - cap_w / 2.0, center_x + cap_w / 2.0],
            [lo_whisker, lo_whisker],
            pen=pen,
        )
        self._pw.plot(
            [center_x - cap_w / 2.0, center_x + cap_w / 2.0],
            [hi_whisker, hi_whisker],
            pen=pen,
        )
        # Outliers
        if len(outliers) > 0:
            scatter = pg.ScatterPlotItem(
                x=[center_x] * len(outliers),
                y=outliers,
                size=6,
                symbol="o",
                brush=pg.mkBrush(color),
                pen=pg.mkPen(color),
            )
            self._pw.addItem(scatter)

    @property
    def plot_widget(self) -> pg.PlotWidget:
        return self._pw


# ---------------------------------------------------------------------
# Violin plot (KDE via FillBetweenItem)
# ---------------------------------------------------------------------
class GroupViolinPlot(QWidget):
    """KDE-based violin per (group, section)."""

    def __init__(
        self,
        metric: str,
        long_df: pd.DataFrame,
        color_scheme: ColorScheme | None = None,
        section_order: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._color_scheme = color_scheme or ColorScheme()
        self._metric = metric.upper()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._pw = pg.PlotWidget()
        self._pw.setMinimumHeight(360)
        self._pw.showGrid(x=True, y=True, alpha=0.3)
        self._pw.setLabel("bottom", "Group")
        self._pw.setLabel("left", self._metric)
        self._pw.setTitle(f"{self._metric} violin by group")
        layout.addWidget(self._pw, 1)

        metric_col = _safe_metric_col(long_df, self._metric)
        if metric_col is None or long_df.empty:
            return
        df = long_df[long_df[metric_col].notna()].copy()
        df = df[df["group"].astype(str).str.len() > 0]
        if df.empty:
            return

        try:
            from scipy import stats as _stats
        except ImportError:
            return

        groups = sorted(df["group"].unique().tolist())
        sections = section_order or sorted(df["section"].unique().tolist())
        n_sections = max(1, len(sections))
        palette = _palette(self._color_scheme)
        slot = 0.75 / n_sections
        max_half_width = slot * 0.45

        for s_idx, section in enumerate(sections):
            color = palette[s_idx % len(palette)]
            for g_idx, group in enumerate(groups):
                vals = df[(df["group"] == group) & (df["section"] == section)][
                    metric_col
                ].to_numpy()
                vals = vals[np.isfinite(vals)]
                if len(vals) < 2 or np.std(vals) == 0:
                    continue
                center_x = g_idx + (s_idx - (n_sections - 1) / 2.0) * slot
                try:
                    kde = _stats.gaussian_kde(vals)
                except Exception:
                    continue
                y_grid = np.linspace(float(np.min(vals)), float(np.max(vals)), 100)
                density = kde(y_grid)
                if density.max() <= 0:
                    continue
                half_w = density / density.max() * max_half_width
                left = center_x - half_w
                right = center_x + half_w
                left_curve = pg.PlotCurveItem(
                    x=left, y=y_grid, pen=pg.mkPen(color, width=1)
                )
                right_curve = pg.PlotCurveItem(
                    x=right, y=y_grid, pen=pg.mkPen(color, width=1)
                )
                self._pw.addItem(left_curve)
                self._pw.addItem(right_curve)
                fill = pg.FillBetweenItem(
                    left_curve,
                    right_curve,
                    brush=pg.mkBrush(_with_alpha(color, 80)),
                )
                self._pw.addItem(fill)
                # Median tick line across the violin
                median = float(np.median(vals))
                self._pw.plot(
                    [center_x - max_half_width * 0.4, center_x + max_half_width * 0.4],
                    [median, median],
                    pen=pg.mkPen(color, width=2),
                )

        ax = self._pw.getAxis("bottom")
        ax.setTicks([list(zip(range(len(groups)), groups))])
        self._pw.setXRange(-0.5, len(groups) - 0.5, padding=0.05)

    @property
    def plot_widget(self) -> pg.PlotWidget:
        return self._pw


def _with_alpha(color: str, alpha: int):
    qc = pg.mkColor(color)
    qc.setAlpha(alpha)
    return qc


# ---------------------------------------------------------------------
# SD1 vs SD2 scatter
# ---------------------------------------------------------------------
class SD1SD2Scatter(QWidget):
    """SD2 (x) vs SD1 (y) scatter with the SD1 = SD2 reference line.

    Args:
        long_df: Long-format DataFrame; must contain ``sd1`` and ``sd2``.
        color_by: Column whose unique values map to different palette
            colours (default ``"group"``).
        color_scheme: ColorScheme — group_palette is the colour source.
    """

    def __init__(
        self,
        long_df: pd.DataFrame,
        color_by: str = "group",
        color_scheme: ColorScheme | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._color_scheme = color_scheme or ColorScheme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._pw = pg.PlotWidget()
        self._pw.setMinimumHeight(360)
        self._pw.showGrid(x=True, y=True, alpha=0.3)
        self._pw.setLabel("bottom", "SD2 (ms) — long-term")
        self._pw.setLabel("left", "SD1 (ms) — short-term")
        self._pw.setTitle("Poincare-derived: SD1 vs SD2")
        layout.addWidget(self._pw, 1)

        if (
            long_df.empty
            or "sd1" not in long_df.columns
            or "sd2" not in long_df.columns
        ):
            return
        df = long_df[long_df["sd1"].notna() & long_df["sd2"].notna()].copy()
        if df.empty:
            return

        palette = _palette(self._color_scheme)
        if color_by not in df.columns:
            color_by = "group"
        categories = sorted(df[color_by].astype(str).unique().tolist())
        for i, cat in enumerate(categories):
            subset = df[df[color_by].astype(str) == cat]
            # Drop the white separator pen — invisible in light theme.
            # The category-coloured brush already discriminates clusters.
            scatter = pg.ScatterPlotItem(
                x=subset["sd2"].to_numpy(dtype=float),
                y=subset["sd1"].to_numpy(dtype=float),
                size=10,
                brush=pg.mkBrush(palette[i % len(palette)]),
                pen=pg.mkPen(None),
                name=str(cat),
            )
            self._pw.addItem(scatter)

        # Reference line: SD1 = SD2.
        max_val = float(max(df["sd1"].max(), df["sd2"].max())) * 1.1
        self._pw.plot(
            [0, max_val],
            [0, max_val],
            pen=pg.mkPen("#888", width=1, style=Qt.DashLine),
            name="SD1 = SD2",
        )
        self._pw.getViewBox().setAspectLocked(True, ratio=1.0)

    @property
    def plot_widget(self) -> pg.PlotWidget:
        return self._pw
