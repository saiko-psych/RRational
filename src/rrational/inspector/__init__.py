"""PyQtGraph-based signal inspector for HRV data.

Standalone PyQt6 desktop app for fluid per-beat browsing of RR-interval
recordings. Lives alongside the Streamlit web app (`rrational.gui`); both
share the analysis / cleaning / io / segments backend.

Entry points:
    python -m rrational.inspector <project_path>
    rrational inspect <project_path>   (after CLI integration)

Optional dependency group: ``pip install rrational[inspector]``
(installs pyqtgraph, pyside6, qtpy).
"""

from __future__ import annotations

__all__ = ["main"]


def main() -> int:
    """Entry point. Lazy-imports Qt so that importing rrational.inspector
    on a Streamlit-only install does not pull in the 60 MB Qt stack.
    """
    from rrational.inspector.app import run

    return run()
