"""Tab-pane modules for the inspector's central QTabWidget.

Each tab is a self-contained QWidget. The MainWindow instantiates one
of each and registers them with the central QTabWidget. Cross-tab
state (loaded datasets, active selection) lives on the MainWindow and
tabs read it via the reference passed to their constructor.

Notification flow:
- When MainWindow's active dataset changes, it calls
  ``tab.on_active_dataset_changed(data)`` on every registered tab.
- When a tab needs MainWindow services (e.g. status-bar messages or
  dialog boxes), it calls back through its ``self._main_window``
  reference.
"""

from rrational.inspector.tabs.analysis_tab import AnalysisTab
from rrational.inspector.tabs.base import InspectorTab
from rrational.inspector.tabs.browse_tab import BrowseTab
from rrational.inspector.tabs.results_tab import ResultsTab
from rrational.inspector.tabs.setup_tab import SetupTab

__all__ = [
    "InspectorTab",
    "BrowseTab",
    "SetupTab",
    "AnalysisTab",
    "ResultsTab",
]
