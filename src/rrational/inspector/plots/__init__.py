"""Native PyQtGraph plot widgets for the RRational Inspector.

Streamlit's Plotly-based plots in ``rrational.gui.plots`` are too slow
for interactive use (CLAUDE.md "NEVER use Plotly JSON serialization").
This package re-implements the same visualisations on top of pyqtgraph
so they can be embedded in QDialogs / tab panes without the Plotly
round-trip.

Each widget is a self-contained ``QWidget`` subclass that owns one
``pg.PlotWidget``. Statistics are computed in the constructor and
exposed via ``self.stats`` for test inspection. The widgets reuse the
science (means, SD bands, SD1/SD2, Welch PSD) from the Streamlit
helpers — only the rendering pipeline differs.
"""

from rrational.inspector.plots.group_charts import (
    GroupBarChart,
    GroupBoxPlot,
    GroupViolinPlot,
    SD1SD2Scatter,
    results_store_to_long_df,
)
from rrational.inspector.plots.hr_distribution import HRDistributionPlot
from rrational.inspector.plots.poincare import PoincarePlot
from rrational.inspector.plots.psd import PSDPlot
from rrational.inspector.plots.tachogram import TachogramPlot

__all__ = [
    "TachogramPlot",
    "PoincarePlot",
    "PSDPlot",
    "HRDistributionPlot",
    "GroupBarChart",
    "GroupBoxPlot",
    "GroupViolinPlot",
    "SD1SD2Scatter",
    "results_store_to_long_df",
]
