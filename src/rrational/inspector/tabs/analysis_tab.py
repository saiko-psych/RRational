"""Analysis tab — HRV metrics computation (Phase 4c/d).

Currently a placeholder. Will host RRational's four analysis modes,
each a sub-pane:

- Single Participant: per-section HRV metrics for one .rrational file
- Repeating Section: cross-participant comparison of one named section
  (e.g. "rest_pre" across all subjects)
- Group: compare metrics between condition groups (control vs.
  intervention) with hypothesis tests + Holm correction
- Sequence Comparison: compare ordered sequences of sections, e.g.
  "music_block_1 → rest → music_block_2" across participants

All four reuse ``rrational.analysis.hrv_compute`` and
``rrational.analysis.hrv_metrics`` — no new computation code needed,
just Qt-native parameter forms + result tables + plot widgets.
"""

from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel, QVBoxLayout

from rrational.inspector.tabs.base import InspectorTab


class AnalysisTab(InspectorTab):
    TAB_LABEL = "Analysis"

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(main_window, parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        label = QLabel(
            "<h2>Analysis</h2>"
            "<p style='color:#555'>Single Participant · Repeating Section · "
            "Group · Sequence Comparison</p>"
            "<p style='color:#888; max-width:600px'>"
            "All four modes from the Streamlit Analysis tab will land here, "
            "reusing the existing HRV compute pipeline "
            "(<code>rrational.analysis.hrv_compute</code>) plus a Qt-native "
            "result table and plot pane.</p>"
            "<p style='color:#aaa'>Single Participant + Repeating Section: Phase 4c.<br>"
            "Group + Sequence Comparison: Phase 4d.</p>"
        )
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
