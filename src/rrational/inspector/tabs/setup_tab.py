"""Setup tab — events / sections / groups / sequences (Phase 4b).

Currently a placeholder. The real implementation will mirror the
Streamlit Setup tab's four sub-panes:

- Events: define + name the timestamps that bound each section
- Sections: per-participant section list with overrides
- Groups: condition assignment (control / intervention / etc.)
- Sequences: ordered chains of sections for the Sequence Comparison
  analysis mode

The widgets here will reuse ``rrational.gui.persistence`` for the
YAML round-trip; that module already handles ``event_sequences.yml``,
``condition_labels.yml`` etc. — we just need a Qt-native editor on top.
"""

from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel, QVBoxLayout

from rrational.inspector.tabs.base import InspectorTab


class SetupTab(InspectorTab):
    TAB_LABEL = "Setup"

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(main_window, parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        label = QLabel(
            "<h2>Setup</h2>"
            "<p style='color:#555'>Events · Sections · Groups · Sequences</p>"
            "<p style='color:#888; max-width:600px'>"
            "This tab will host the same setup workflow as RRational's "
            "Streamlit Setup tab — define which timestamps mark section "
            "boundaries, assign participants to groups, and chain sections "
            "into ordered sequences for comparative analysis.</p>"
            "<p style='color:#aaa'>Coming in Phase 4b.</p>"
        )
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
