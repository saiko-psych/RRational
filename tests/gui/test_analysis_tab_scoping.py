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


def test_poor_quality_reason_uses_documented_boundary():
    from rrational.gui.tabs.analysis import _poor_quality_reason

    assert _poor_quality_reason({"artifact_rate": 0.10}) is None  # moderate
    assert _poor_quality_reason({"artifact_rate": 0.1001}).startswith("Excluded: Poor")
    assert _poor_quality_reason({"artifact_rate": 0.25}) == (
        "Excluded: Poor quality (25.0% artifacts)"
    )
    # A known rate wins over a stale grade; without a rate the grade decides.
    assert _poor_quality_reason({"artifact_rate": 0.03, "quality_grade": "poor"}) is None
    assert _poor_quality_reason({"quality_grade": "poor"}) == "Excluded: Poor quality"
    assert _poor_quality_reason({"quality_grade": "raw"}) is None
    assert _poor_quality_reason({}) is None
