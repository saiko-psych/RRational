"""Dialog for the Tools -> Compare HRV curves... entry (Cluster B1).

Lets the user partition the open datasets into named groups, pick a
confidence level, and renders the resulting overlay via
``compare_hrv_curves``. The grouping UI is intentionally minimal — two
slots ("Group A", "Group B") with a checkable dataset list each — so
the common 2-group comparison is one click.
"""

from __future__ import annotations

from collections.abc import Sequence

from qtpy.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
)

from rrational.inspector.data_loader import Dataset
from rrational.inspector.plots.compare_curves import compare_hrv_curves


class CompareCurvesDialog(QDialog):
    """Picker + viewer for cross-dataset HRV-curve comparisons."""

    def __init__(self, datasets: Sequence[Dataset], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Compare HRV curves")
        self.resize(900, 560)

        self._datasets = list(datasets)

        outer = QVBoxLayout(self)

        # Two-group pickers side-by-side. Each list shows every loaded
        # dataset; the user checks the ones that belong to that group.
        pickers = QHBoxLayout()
        self._group_a = self._make_group_picker("Group A")
        self._group_b = self._make_group_picker("Group B")
        pickers.addLayout(self._group_a["layout"])
        pickers.addLayout(self._group_b["layout"])
        outer.addLayout(pickers)

        # CI knob.
        form = QFormLayout()
        self._ci_spin = QDoubleSpinBox()
        self._ci_spin.setRange(0.50, 0.999)
        self._ci_spin.setDecimals(3)
        self._ci_spin.setSingleStep(0.01)
        self._ci_spin.setValue(0.95)
        form.addRow("Confidence level", self._ci_spin)
        outer.addLayout(form)

        # The plot widget is created on first "Plot" press and swapped
        # in below. Until then we show a placeholder so the dialog has
        # consistent dimensions.
        self._plot_holder = QVBoxLayout()
        placeholder = QLabel("Pick datasets for at least one group, then press Plot.")
        # Round 20: muted-text colour pulled from the active theme so the
        # placeholder reads correctly in dark + light modes instead of
        # always rendering at the legacy ``#888`` mid-grey.
        placeholder.setProperty("muted", True)
        placeholder.setStyleSheet("padding: 24px;")
        self._plot_holder.addWidget(placeholder)
        outer.addLayout(self._plot_holder, stretch=1)
        self._plot_widget = None

        # Buttons: Plot (reusable), Close.
        btns = QDialogButtonBox()
        plot_btn = btns.addButton("Plot", QDialogButtonBox.ActionRole)
        plot_btn.clicked.connect(self._on_plot_clicked)
        btns.addButton(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        outer.addWidget(btns)

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------
    def _make_group_picker(self, label: str) -> dict:
        """Return the layout + the QListWidget so the caller can read selections."""
        layout = QVBoxLayout()
        layout.addWidget(QLabel(label))
        listw = QListWidget()
        listw.setSelectionMode(QAbstractItemView.MultiSelection)
        for ds in self._datasets:
            item = QListWidgetItem(ds.name)
            listw.addItem(item)
        layout.addWidget(listw)
        return {"layout": layout, "list": listw}

    # ------------------------------------------------------------------
    # Plot wiring
    # ------------------------------------------------------------------
    def _collect_group(self, picker: dict) -> list:
        """Pull the RR arrays for the checked datasets in one picker."""
        listw: QListWidget = picker["list"]
        out = []
        for row in range(listw.count()):
            item = listw.item(row)
            if item.isSelected():
                ds = self._datasets[row]
                # InspectorData exposes RR-ms in the ``.v`` array (NaN
                # at section gaps). Drop NaNs so the bootstrap CI isn't
                # dragged toward zero by gap-padding.
                import numpy as np

                rr = np.asarray(getattr(ds.data, "v", []), dtype=float)
                rr = rr[np.isfinite(rr)]
                if len(rr) > 0:
                    out.append(rr)
        return out

    def _on_plot_clicked(self) -> None:
        groups = {}
        a = self._collect_group(self._group_a)
        b = self._collect_group(self._group_b)
        if a:
            groups["Group A"] = a
        if b:
            groups["Group B"] = b
        if not groups:
            QMessageBox.information(
                self, "Compare HRV curves", "Select at least one dataset per group."
            )
            return

        new_widget = compare_hrv_curves(groups, ci=float(self._ci_spin.value()))
        # Swap out the placeholder / previous plot.
        while self._plot_holder.count():
            item = self._plot_holder.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        self._plot_holder.addWidget(new_widget)
        self._plot_widget = new_widget
