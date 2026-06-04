"""Non-modal QDialog wrappers for the inspector's plot widgets.

Each helper opens a dialog containing one of the pyqtgraph-backed
plots from ``rrational.inspector.plots``, plus a toolbar with a
``Save as PNG...`` action. Returned dialogs are non-modal so the user
can keep multiple plots open at once and continue interacting with the
main window.

The PNG export uses ``pyqtgraph.exporters.ImageExporter`` directly on
the underlying ``PlotItem`` — no Plotly/Kaleido in sight.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from qtpy.QtGui import QAction
from qtpy.QtWidgets import (
    QDialog,
    QFileDialog,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from rrational.gui.color_scheme import ColorScheme
from rrational.inspector.plots import (
    GroupBarChart,
    GroupBoxPlot,
    GroupViolinPlot,
    HRDistributionPlot,
    PoincarePlot,
    PSDPlot,
    SD1SD2Scatter,
    TachogramPlot,
)


class _PlotDialog(QDialog):
    """Reusable dialog: toolbar + plot widget + PNG export.

    Non-modal so the user can open several plots in parallel. The
    ``Save as PNG...`` toolbar action wires up an ImageExporter on the
    plot's underlying ``PlotItem``.
    """

    def __init__(
        self,
        plot_widget: QWidget,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        # Pass parent=None so the dialog isn't auto-modal under PySide6's
        # default WindowFlags.
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(False)
        self.resize(720, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        toolbar = QToolBar(self)
        layout.addWidget(toolbar)

        save_act = QAction("Save as PNG...", self)
        save_act.setToolTip("Export the current plot as a PNG image")
        save_act.triggered.connect(self._on_save)
        toolbar.addAction(save_act)

        self._plot_widget = plot_widget
        layout.addWidget(plot_widget, 1)

    def _on_save(self) -> None:
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save plot as PNG",
            "plot.png",
            "PNG image (*.png);;All files (*)",
        )
        if not path_str:
            return
        self.export_png(Path(path_str))

    def export_png(self, path: Path) -> bool:
        """Write the plot to ``path`` (PNG). Returns True on success."""
        import pyqtgraph as pg
        from pyqtgraph.exporters import ImageExporter

        # ``plot_widget`` is a QWidget with one nested pg.PlotWidget; the
        # ImageExporter wants the PlotItem inside that PlotWidget.
        pw = getattr(self._plot_widget, "plot_widget", None)
        if pw is None and isinstance(self._plot_widget, pg.PlotWidget):
            pw = self._plot_widget
        if pw is None:
            return False
        plot_item = pw.getPlotItem()
        exporter = ImageExporter(plot_item)
        exporter.export(str(path))
        return path.exists() and path.stat().st_size > 0


# ---------------------------------------------------------------------
# Single-participant dialogs
# ---------------------------------------------------------------------
def show_tachogram_dialog(
    parent: QWidget | None,
    rr_intervals,
    section_label: str = "",
    artifact_indices: list[int] | None = None,
    color_scheme: ColorScheme | None = None,
    test_mode: bool = False,
) -> _PlotDialog:
    """Open a non-modal tachogram dialog. Returns the dialog instance."""
    widget = TachogramPlot(
        rr_intervals,
        section_label=section_label,
        artifact_indices=artifact_indices,
        color_scheme=color_scheme,
    )
    dlg = _PlotDialog(widget, "Tachogram", parent=parent)
    if not test_mode:
        dlg.show()
    return dlg


def show_poincare_dialog(
    parent: QWidget | None,
    rr_intervals,
    section_label: str = "",
    color_scheme: ColorScheme | None = None,
    test_mode: bool = False,
) -> _PlotDialog:
    widget = PoincarePlot(
        rr_intervals,
        section_label=section_label,
        color_scheme=color_scheme,
    )
    dlg = _PlotDialog(widget, "Poincare plot", parent=parent)
    if not test_mode:
        dlg.show()
    return dlg


def show_psd_dialog(
    parent: QWidget | None,
    rr_intervals,
    section_label: str = "",
    sampling_rate: int = 4,
    color_scheme: ColorScheme | None = None,
    test_mode: bool = False,
) -> _PlotDialog:
    widget = PSDPlot(
        rr_intervals,
        section_label=section_label,
        sampling_rate=sampling_rate,
        color_scheme=color_scheme,
    )
    dlg = _PlotDialog(widget, "Power spectral density", parent=parent)
    if not test_mode:
        dlg.show()
    return dlg


def show_hr_distribution_dialog(
    parent: QWidget | None,
    rr_intervals,
    section_label: str = "",
    color_scheme: ColorScheme | None = None,
    test_mode: bool = False,
) -> _PlotDialog:
    widget = HRDistributionPlot(
        rr_intervals,
        section_label=section_label,
        color_scheme=color_scheme,
    )
    dlg = _PlotDialog(widget, "Heart rate distribution", parent=parent)
    if not test_mode:
        dlg.show()
    return dlg


# ---------------------------------------------------------------------
# Group-comparison dialog
# ---------------------------------------------------------------------
def show_group_chart_dialog(
    parent: QWidget | None,
    plot_type: str,
    long_df: pd.DataFrame,
    metric: str = "RMSSD",
    error_bar_type: str = "SD",
    log_y: bool | None = None,
    show_points: bool = False,
    color_scheme: ColorScheme | None = None,
    color_by: str = "group",
    test_mode: bool = False,
) -> _PlotDialog:
    """Open a non-modal dialog for one of the group-comparison plots.

    Args:
        plot_type: ``"bar" | "box" | "violin" | "sd1_sd2"``.
        long_df: Long-format DataFrame (one row per participant/section).
        metric: HRV metric to plot (ignored for ``sd1_sd2``).
        error_bar_type, log_y, show_points: passed through to GroupBarChart.
        color_by: column used for the SD1/SD2 scatter colouring.
    """
    pt = plot_type.lower()
    if pt == "bar":
        widget = GroupBarChart(
            metric=metric,
            long_df=long_df,
            error_bar_type=error_bar_type,
            log_y=log_y,
            show_points=show_points,
            color_scheme=color_scheme,
        )
        title = f"Bar chart — {metric}"
    elif pt == "box":
        widget = GroupBoxPlot(
            metric=metric,
            long_df=long_df,
            color_scheme=color_scheme,
        )
        title = f"Box plot — {metric}"
    elif pt == "violin":
        widget = GroupViolinPlot(
            metric=metric,
            long_df=long_df,
            color_scheme=color_scheme,
        )
        title = f"Violin plot — {metric}"
    elif pt in ("sd1_sd2", "sd1-sd2", "sd1sd2"):
        widget = SD1SD2Scatter(
            long_df=long_df,
            color_by=color_by,
            color_scheme=color_scheme,
        )
        title = "SD1 vs SD2 scatter"
    else:
        raise ValueError(f"Unknown plot_type: {plot_type!r}")

    dlg = _PlotDialog(widget, title, parent=parent)
    if not test_mode:
        dlg.show()
    return dlg
