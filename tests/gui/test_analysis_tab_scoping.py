"""Scoping regression test for gui/tabs/analysis.py."""

from __future__ import annotations


def test_path_is_not_shadowed_in_single_participant_analysis():
    """A ``from pathlib import Path`` inside _render_single_participant_analysis
    made ``Path`` a LOCAL name for the whole function, so the earlier VNS
    re-discovery (``Path(st.session_state.data_dir)``, ready-file branch)
    raised UnboundLocalError. The module-level import must be used."""
    from rrational.gui.tabs import analysis

    code = analysis._render_single_participant_analysis.__code__
    assert "Path" not in code.co_varnames
