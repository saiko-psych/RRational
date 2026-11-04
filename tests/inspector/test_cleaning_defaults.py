"""Cleaning defaults agree across Inspector settings and the Data tab."""

from __future__ import annotations

from rrational.cleaning.rr import CleaningConfig, _sudden_change_enabled


def test_inspector_sudden_change_default_is_disabled_and_consistent():
    from rrational.inspector.settings import _DEFAULTS as DEFAULTS
    from rrational.inspector.tabs.data_tab import _CLEANING_DEFAULT_SUDDEN_PCT

    assert float(DEFAULTS["cleaning_sudden_change_pct"]) == _CLEANING_DEFAULT_SUDDEN_PCT
    cfg = CleaningConfig(sudden_change_pct=_CLEANING_DEFAULT_SUDDEN_PCT / 100.0)
    assert not _sudden_change_enabled(cfg)
