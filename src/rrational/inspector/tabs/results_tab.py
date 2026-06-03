"""Results tab — computed metric tables + export (Phase 4e).

Currently a placeholder. Will display the most recent analysis output
as a sortable table (RMSSD, SDNN, LF, HF, LF/HF, pNN50, ...), with:

- Per-row export to CSV / Excel
- Filtering by group / section / metric
- Inline plot of any column (boxplot across groups, line across sections)

Backed by the same group_analysis_results.yml cache the Streamlit app
uses, so the results survive across sessions and are interchangeable
between the two front-ends.
"""

from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel, QVBoxLayout

from rrational.inspector.tabs.base import InspectorTab


class ResultsTab(InspectorTab):
    TAB_LABEL = "Results"

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(main_window, parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        label = QLabel(
            "<h2>Results</h2>"
            "<p style='color:#555'>Computed metrics · Export · Inline plots</p>"
            "<p style='color:#888; max-width:600px'>"
            "Sortable + exportable table of every HRV metric that the "
            "Analysis tab has produced. Backed by the same "
            "<code>group_analysis_results.yml</code> cache the Streamlit "
            "app uses, so results round-trip between the two UIs.</p>"
            "<p style='color:#aaa'>Coming in Phase 4e.</p>"
        )
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
