"""Tests for Phase 18 — HTML / Markdown report generation."""

from __future__ import annotations

import re

import numpy as np
import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path):
    """Redirect every persistence layer at a fresh tmp_path."""
    from rrational.inspector import persistence, settings

    settings.enable_test_mode(tmp_path)
    persistence.set_inspector_config_dir(tmp_path)
    yield
    persistence.set_inspector_config_dir(None)


def _make_data(section_names: list[str], beats_per_section: int = 200):
    """Build a synthetic InspectorData covering N named sections."""
    from rrational.inspector.data_loader import (
        EventMeta,
        InspectorData,
        SectionMeta,
    )

    base = 1_700_000_000
    n = beats_per_section * len(section_names)
    rng = np.random.default_rng(seed=11)
    rr_ms = 800 + 30 * rng.standard_normal(n)
    t = base + np.cumsum(rr_ms) / 1000.0

    sections = []
    events = []
    for i, name in enumerate(section_names):
        s = i * beats_per_section
        e = (i + 1) * beats_per_section - 1
        sections.append(
            SectionMeta(
                name=name,
                t_start=float(t[s]),
                t_end=float(t[e]),
                beat_count=beats_per_section,
            )
        )
        events.append(EventMeta(label=f"{name}_start", t=float(t[s])))
    return InspectorData(t=t, v=rr_ms, sections=sections, events=events)


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


def _populate_store(window) -> None:
    """Drop one of each row type into the window's ResultsStore."""
    from rrational.inspector.results_store import (
        GroupTestRow,
        MetricRow,
        SequenceTestRow,
    )

    store = window._results_store
    store.add_metric_row(
        MetricRow(
            mode="single",
            dataset="P001.rrational",
            section="rest_pre",
            n_beats=300,
            metrics={"RMSSD": 42.5, "SDNN": 80.1, "LF": 250.0, "HF": 100.0},
        )
    )
    store.add_metric_row(
        MetricRow(
            mode="repeating",
            dataset="P002.rrational",
            section="rest_pre",
            n_beats=310,
            metrics={"RMSSD": 38.7, "SDNN": 75.3, "LF": 230.0, "HF": 110.0},
        )
    )
    store.add_group_test_row(
        GroupTestRow(
            section="rest_pre",
            metric="RMSSD",
            test_name="Welch t",
            statistic=2.13,
            p_value=0.041,
            effect_size_name="Cohen's d",
            effect_size=0.78,
            is_parametric=True,
            groups=("control", "music"),
            n_per_group={"control": 12, "music": 13},
        )
    )
    store.add_sequence_test_row(
        SequenceTestRow(
            sequence_name="protocol_v1",
            metric="RMSSD",
            sections=("rest_pre", "stim", "rest_post"),
            n_complete_subjects=20,
            test_name="Friedman",
            statistic=11.4,
            p_value=0.003,
            effect_size_name="Kendall's W",
            effect_size=0.57,
            is_parametric=False,
        )
    )


# ---------------------------------------------------------------------
# build_html
# ---------------------------------------------------------------------
def test_build_html_starts_with_doctype(main_window):
    from rrational.inspector.report import ReportBuilder

    html = ReportBuilder(main_window).build_html()
    assert html.startswith("<!DOCTYPE html>")


def test_build_html_empty_store_shows_friendly_placeholders(main_window):
    from rrational.inspector.report import ReportBuilder

    html = ReportBuilder(main_window).build_html()
    # Every "results" section should have its empty-state copy.
    assert html.count("(no results yet)") >= 3
    # Datasets section also empty.
    assert "(no datasets loaded)" in html


def test_build_html_non_empty_store_contains_expected_rows(main_window):
    from rrational.inspector.report import ReportBuilder

    _populate_store(main_window)
    html = ReportBuilder(main_window).build_html()

    # Metric row values render
    assert "P001.rrational" in html
    assert "P002.rrational" in html
    assert "rest_pre" in html
    assert "RMSSD" in html
    assert "42.5" in html  # MetricRow value
    # Group test
    assert "Welch t" in html
    assert "control" in html
    assert "music" in html
    # Sequence test
    assert "Friedman" in html
    assert "protocol_v1" in html


def test_build_html_p_value_colour_classes_present(main_window):
    from rrational.inspector.report import ReportBuilder

    _populate_store(main_window)
    html = ReportBuilder(main_window).build_html()
    # 0.041 -> p-05, 0.003 -> p-01
    assert "p-05" in html
    assert "p-01" in html


def test_build_html_contains_toc_with_anchors(main_window):
    from rrational.inspector.report import ReportBuilder

    html = ReportBuilder(main_window).build_html()
    for anchor in [
        "#datasets",
        "#metrics",
        "#group-tests",
        "#sequence-tests",
        "#quality",
        "#methods",
        "#references",
        "#audit",
    ]:
        assert anchor in html


def test_build_html_doi_links_well_formed(main_window):
    from rrational.inspector.report import ReportBuilder

    html = ReportBuilder(main_window).build_html()
    # Every DOI URL should follow the canonical https://doi.org/<prefix>/<suffix>
    doi_pattern = re.compile(r"https://doi\.org/10\.[0-9]+(\.[0-9]+)*/[^\s'\"<>]+")
    assert len(doi_pattern.findall(html)) >= 5  # we cite at least 5 DOIs


def test_build_html_inlines_css_and_has_semantic_tables(main_window):
    from rrational.inspector.report import ReportBuilder

    _populate_store(main_window)
    html = ReportBuilder(main_window).build_html()
    assert "<style>" in html
    assert "<table>" in html
    assert "<thead>" in html
    assert "<tbody>" in html


def test_build_html_file_at_least_500_bytes(main_window, tmp_path):
    from rrational.inspector.report import ReportBuilder

    html = ReportBuilder(main_window).build_html()
    out = tmp_path / "report.html"
    out.write_text(html, encoding="utf-8")
    assert out.stat().st_size >= 500


# ---------------------------------------------------------------------
# build_markdown
# ---------------------------------------------------------------------
def test_build_markdown_starts_with_title(main_window):
    from rrational.inspector.report import ReportBuilder

    md = ReportBuilder(main_window).build_markdown()
    assert md.startswith("# RRational Report")


def test_build_markdown_empty_store_shows_friendly_placeholders(main_window):
    from rrational.inspector.report import ReportBuilder

    md = ReportBuilder(main_window).build_markdown()
    assert md.count("_(no results yet)_") >= 3
    assert "_(no datasets loaded)_" in md


def test_build_markdown_has_proper_heading_hierarchy(main_window):
    from rrational.inspector.report import ReportBuilder

    md = ReportBuilder(main_window).build_markdown()
    # Top-level title is H1, every section header is H2.
    h1 = [
        ln for ln in md.splitlines() if ln.startswith("# ") and not ln.startswith("##")
    ]
    h2 = [ln for ln in md.splitlines() if ln.startswith("## ")]
    assert len(h1) == 1
    expected_h2 = {
        "## Datasets",
        "## HRV metrics",
        "## Group comparisons",
        "## Sequence comparisons",
        "## Quality summary",
        "## Methods",
        "## References",
        "## Audit trail",
    }
    assert expected_h2.issubset(set(h2))


def test_build_markdown_non_empty_store_renders_pipe_tables(main_window):
    from rrational.inspector.report import ReportBuilder

    _populate_store(main_window)
    md = ReportBuilder(main_window).build_markdown()
    # Pipe-table separator row appears under each populated section.
    assert "|------" in md or "|---" in md
    # Concrete cell values from the store.
    assert "Friedman" in md
    assert "Welch t" in md
    assert "RMSSD" in md
    assert "protocol_v1" in md


def test_build_markdown_doi_links_well_formed(main_window):
    from rrational.inspector.report import ReportBuilder

    md = ReportBuilder(main_window).build_markdown()
    doi_pattern = re.compile(r"https://doi\.org/10\.[0-9]+(\.[0-9]+)*/[^\s)]+")
    assert len(doi_pattern.findall(md)) >= 5


# ---------------------------------------------------------------------
# Menu integration + save dialog (test_mode bypass)
# ---------------------------------------------------------------------
def test_main_window_exposes_export_actions(main_window):
    assert main_window._export_html_act is not None
    assert main_window._export_md_act is not None
    assert (
        main_window._export_html_act.text()
        .replace("&", "")
        .startswith("Export report (HTML)")
    )
    assert (
        main_window._export_md_act.text()
        .replace("&", "")
        .startswith("Export report (Markdown)")
    )


def test_export_html_action_writes_default_path_in_test_mode(main_window, tmp_path):
    # In test_mode the MainWindow skips the QFileDialog and uses the
    # default report path. Redirect that path into tmp_path.
    from rrational.inspector import settings

    settings.write_setting("last_dir", str(tmp_path))
    main_window._on_export_report_html_clicked()
    out = tmp_path / "rrational_report.html"
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
    assert out.stat().st_size >= 500


def test_export_markdown_action_writes_default_path_in_test_mode(main_window, tmp_path):
    from rrational.inspector import settings

    settings.write_setting("last_dir", str(tmp_path))
    main_window._on_export_report_markdown_clicked()
    out = tmp_path / "rrational_report.md"
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("# RRational Report")


# ---------------------------------------------------------------------
# Datasets + quality + audit integration
# ---------------------------------------------------------------------
def test_loaded_dataset_appears_in_datasets_table(main_window):
    from rrational.inspector.data_loader import Dataset
    from rrational.inspector.report import ReportBuilder

    data = _make_data(["rest_pre"], beats_per_section=150)
    main_window.add_dataset(Dataset(name="P042.rrational", data=data, path=None))
    main_window.set_active_dataset(0)

    html = ReportBuilder(main_window).build_html()
    md = ReportBuilder(main_window).build_markdown()
    assert "P042.rrational" in html
    assert "P042.rrational" in md
    assert "150" in html


def test_audit_trail_section_appears_even_when_empty(main_window):
    from rrational.inspector.report import ReportBuilder

    html = ReportBuilder(main_window).build_html()
    assert "id='audit'" in html
    assert "(no audit entries" in html


# ---------------------------------------------------------------------
# Cluster C2 — Bootstrap layout, sidebar TOC, tag-filter, add_section
# ---------------------------------------------------------------------
def test_html_includes_sticky_topbar_and_sidebar(main_window):
    from rrational.inspector.report import ReportBuilder

    html = ReportBuilder(main_window).build_html()
    assert "class='topbar'" in html
    assert "class='sidebar'" in html
    # Round 20: the CDN Bootstrap link was replaced by an inlined utility
    # subset so the report is self-contained for offline / email use.
    assert "cdn.jsdelivr.net" not in html
    assert "bootstrap@" not in html
    # The single Bootstrap utility class we still rely on is inlined.
    assert ".visually-hidden" in html


def test_add_section_renders_custom_section(main_window):
    from rrational.inspector.report import ReportBuilder

    rb = ReportBuilder(main_window)
    rb.add_section("Quality Notes", "<p>Looks good.</p>", tag="qa")
    html = rb.build_html()
    assert "Quality Notes" in html
    assert "Looks good." in html
    assert "data-tag='qa'" in html


def test_tag_filter_dropdown_lists_added_tags(main_window):
    from rrational.inspector.report import ReportBuilder

    rb = ReportBuilder(main_window)
    rb.add_section("A", "<p>x</p>", tag="qa")
    rb.add_section("B", "<p>y</p>", tag="methods")
    html = rb.build_html()
    assert "id='tagFilter'" in html
    assert "<option value='qa'>" in html
    assert "<option value='methods'>" in html


def test_add_section_without_tag_omits_data_attribute(main_window):
    from rrational.inspector.report import ReportBuilder

    rb = ReportBuilder(main_window)
    rb.add_section("Untagged", "<p>z</p>")
    html = rb.build_html()
    assert "Untagged" in html
    # No data-tag means it always shows (no pill, no attribute).
    assert "data-tag=''" not in html
