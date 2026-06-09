"""Tests for the artifact-detection preprocessing layer and its UI panel.

Two test groups:
1. Pure ``preprocessing.detect_artifacts`` — no Qt, runs the NK2
   Kubios algorithm on numpy arrays directly
2. ``PreprocessingPanel`` — verifies the right-side panel transitions
   states correctly: empty → loaded → detected → toggle visibility
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _exists_or_skip(rel: str) -> Path:
    p = REPO_ROOT / rel
    if not p.exists():
        pytest.skip(f"{rel} not in repo")
    return p


# ---------------------------------------------------------------------
# Pure detector (no Qt)
# ---------------------------------------------------------------------
def test_detect_artifacts_handles_short_input():
    """<10 beats → unknown grade, zero artifacts, no crash."""
    from rrational.inspector.preprocessing import detect_artifacts

    result = detect_artifacts(np.array([800.0, 810.0, 820.0]))
    assert result.total == 0
    assert result.grade == "unknown"
    assert "too short" in result.recommendation.lower()


def test_detect_artifacts_on_clean_data_finds_few():
    """A flat 800-ms train should be classified as excellent."""
    from rrational.inspector.preprocessing import detect_artifacts

    clean = np.full(200, 800.0)
    result = detect_artifacts(clean)
    assert result.rate < 0.01  # less than 1% (no spikes by construction)
    assert result.grade in ("excellent", "unknown")


def test_detect_artifacts_on_real_world_data_returns_finite_rate():
    """Real Empatica file should produce a finite, reasonable artifact rate."""
    from rrational.inspector.data_loader import load_raw_rr
    from rrational.inspector.preprocessing import detect_artifacts

    p = _exists_or_skip("data/demo/empatica/IBI_stress_predict_S10.csv")
    data = load_raw_rr(p)
    result = detect_artifacts(data.v)
    # Rate must be in [0, 1]
    assert 0.0 <= result.rate <= 1.0
    # Corrected array preserves length
    assert result.corrected_v is not None
    assert len(result.corrected_v) == len(data.v)
    # If artifacts were found, indices must be valid array positions
    assert result.indices.dtype.kind in ("i", "u")
    if result.total > 0:
        assert result.indices.min() >= 0
        assert result.indices.max() < len(data.v)


def test_grade_thresholds_match_quigley_2024():
    """Quality grade boundaries match the 2%/5%/10% Quigley cutoffs."""
    from rrational.inspector.preprocessing import _grade_for_rate

    assert _grade_for_rate(0.01)[0] == "excellent"
    assert _grade_for_rate(0.03)[0] == "good"
    assert _grade_for_rate(0.07)[0] == "moderate"
    assert _grade_for_rate(0.15)[0] == "poor"


def test_cleaning_quality_returns_artifact_indices_key():
    """Fix 2: detect_artifacts_fixpeaks's result dict must include
    'artifact_indices', even when zero artifacts are found."""
    from rrational.cleaning.quality import detect_artifacts_fixpeaks

    rr = [800] * 200
    result = detect_artifacts_fixpeaks(rr_values=rr)
    assert "artifact_indices" in result
    assert isinstance(result["artifact_indices"], list)
    # On a flat input no artifacts should be flagged
    assert len(result["artifact_indices"]) == result["total_artifacts"]


def test_cleaning_quality_artifact_indices_sorted_unique_inbounds():
    """Indices returned by detect_artifacts_fixpeaks must be sorted,
    unique, and lie inside [0, len(rr_values))."""
    from rrational.cleaning.quality import detect_artifacts_fixpeaks

    # Realistic RR series with clear extra/missed spikes
    rng = np.random.default_rng(42)
    rr = [int(round(x)) for x in (800 + 20 * rng.standard_normal(400))]
    # Inject several flagrant artifacts
    for idx in (60, 180, 300):
        rr[idx] = 200  # impossibly short -> "extra" / "longshort"

    result = detect_artifacts_fixpeaks(rr_values=rr)
    indices = result["artifact_indices"]

    assert list(indices) == sorted(set(int(i) for i in indices))
    for idx in indices:
        assert 0 <= idx < len(rr)
    # Index count equals total per-type artifact count (per docstring).
    assert len(indices) == result["total_artifacts"]


def test_detect_artifacts_inspector_indices_use_nk2_set_not_diff():
    """Fix 2: inspector should consume the NK2 artifact_indices set
    rather than diffing corrected vs original — the index count must
    match what cleaning.quality returns one-to-one."""
    from rrational.cleaning.quality import detect_artifacts_fixpeaks
    from rrational.inspector.preprocessing import detect_artifacts

    rng = np.random.default_rng(42)
    rr_floats = 800 + 20 * rng.standard_normal(400)
    for idx in (60, 180, 300):
        rr_floats[idx] = 200.0
    rr_ints = [int(round(x)) for x in rr_floats]

    raw_result = detect_artifacts_fixpeaks(rr_values=rr_ints)
    insp_result = detect_artifacts(rr_floats)

    assert insp_result.total == raw_result["total_artifacts"]
    assert len(insp_result.indices) == len(raw_result["artifact_indices"])


# ---------------------------------------------------------------------
# Panel integration (Qt needed)
# ---------------------------------------------------------------------
pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path):
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    yield


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


def test_panel_disables_detect_when_no_data(main_window):
    panel = main_window._browse_tab._preprocessing_panel
    assert panel._detect_btn.isEnabled() is False


def test_panel_enables_detect_after_load(main_window):
    p = _exists_or_skip("data/demo/empatica/IBI_stress_predict_S10.csv")
    main_window.open_path(p)
    panel = main_window._browse_tab._preprocessing_panel
    assert panel._detect_btn.isEnabled() is True


def test_panel_detection_populates_overlay_and_summary(main_window):
    """End-to-end: load file → click Detect → overlay points + summary updated."""
    p = _exists_or_skip("data/demo/empatica/IBI_stress_predict_S10.csv")
    main_window.open_path(p)
    panel = main_window._browse_tab._preprocessing_panel

    panel._on_detect_clicked()

    # Result stored on the panel
    assert panel._last_result is not None
    assert panel._last_result.total >= 0  # at minimum, doesn't crash
    # Overlay points correspond to artifact indices
    overlay = main_window._browse_tab._plot._artifact_overlay
    overlay_x, _ = overlay.getData()
    assert len(overlay_x) == panel._last_result.total
    # Toggles are enabled (post-detection)
    assert panel._toggle_show_artifacts.isEnabled() is True
    assert panel._export_btn.isEnabled() is True
    # Summary text now mentions the artifact count
    assert "artifacts" in panel._summary.text().lower()


def test_show_artifacts_checkbox_toggles_overlay(main_window):
    p = _exists_or_skip("data/demo/empatica/IBI_stress_predict_S10.csv")
    main_window.open_path(p)
    panel = main_window._browse_tab._preprocessing_panel
    panel._on_detect_clicked()

    overlay = main_window._browse_tab._plot._artifact_overlay
    # Currently checked → overlay visible
    assert panel._toggle_show_artifacts.isChecked() is True
    assert overlay.isVisible() is True

    panel._toggle_show_artifacts.setChecked(False)
    assert overlay.isVisible() is False
    panel._toggle_show_artifacts.setChecked(True)
    assert overlay.isVisible() is True


def test_use_corrected_toggle_swaps_curve_data(main_window):
    """When toggled on, the plot curve must use the corrected RR values."""
    p = _exists_or_skip("data/demo/empatica/IBI_stress_predict_S10.csv")
    main_window.open_path(p)
    panel = main_window._browse_tab._preprocessing_panel
    panel._on_detect_clicked()

    if panel._last_result.total == 0:
        pytest.skip("This file produced no artifacts; toggle has nothing to swap")

    curve = main_window._browse_tab._plot._curve
    _, original_v = curve.getData()
    assert np.array_equal(original_v, main_window._data.v, equal_nan=True)

    panel._toggle_use_corrected.setChecked(True)
    _, corrected_v = curve.getData()
    assert not np.array_equal(corrected_v, main_window._data.v, equal_nan=True)
    # The corrected array exactly matches what the detector returned
    assert np.array_equal(corrected_v, panel._last_result.corrected_v, equal_nan=True)

    panel._toggle_use_corrected.setChecked(False)
    _, back_to_original = curve.getData()
    assert np.array_equal(back_to_original, main_window._data.v, equal_nan=True)


def test_panel_resets_when_dataset_switched(main_window):
    """Closing the dataset must reset the panel back to empty state."""
    p = _exists_or_skip("data/demo/empatica/IBI_stress_predict_S10.csv")
    main_window.open_path(p)
    panel = main_window._browse_tab._preprocessing_panel
    panel._on_detect_clicked()
    assert panel._last_result is not None

    main_window.close_all_datasets()

    assert panel._last_result is None
    assert panel._detect_btn.isEnabled() is False
    assert panel._toggle_show_artifacts.isEnabled() is False
    assert panel._export_btn.isEnabled() is False


def test_export_button_enabled_immediately_after_load(main_window):
    """Phase 6: Save-as button is usable before Detect runs (raw export)."""
    p = _exists_or_skip("data/demo/empatica/IBI_stress_predict_S10.csv")
    main_window.open_path(p)
    panel = main_window._browse_tab._preprocessing_panel
    # Export should be available straight away — corrected data is optional
    assert panel._export_btn.isEnabled() is True


def test_export_clicked_in_test_mode_writes_real_file(
    main_window, tmp_path, monkeypatch
):
    """In test_mode, _on_export_clicked skips dialogs and writes a real file."""
    from rrational.gui.rrational_export import load_rrational_v2
    from rrational.inspector import settings

    p = _exists_or_skip("data/demo/empatica/IBI_stress_predict_S10.csv")
    main_window.open_path(p)

    # Redirect last_dir to the temp path so the export lands inside tmp_path
    settings.write_setting("last_dir", str(tmp_path))

    panel = main_window._browse_tab._preprocessing_panel
    panel._on_export_clicked()

    # File should be in tmp_path with the dataset's stem as participant_id
    written = list(tmp_path.glob("*.rrational"))
    assert len(written) == 1
    loaded = load_rrational_v2(written[0])
    assert loaded.metadata.source_app == "RRational"
    # The CSV has at least one section (empatica generic_rr parser
    # creates a single-section dataset)
    assert len(loaded.sections) >= 1
