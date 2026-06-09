"""Smoke tests for the Streamlit app via AppTest.

These exercise the major render paths (welcome, data tab, analysis tab,
participants tab, setup tab, settings panel) to catch the kind of
import-scoping and display-after-return bugs that pytest unit tests miss:

  - ``components NameError`` in ``_setup_inspection_shortcuts`` (commit
    ``ac1dea9``) where a local ``components`` was deleted from a scope
    that still referenced ``st.components.v1`` at call time.
  - The "Aggregated results from N valid windows" path in
    ``src/rrational/gui/tabs/analysis.py`` returning before
    ``_display_single_participant_results`` was invoked, so the user saw
    an empty page.

The tests run without a browser - AppTest drives the script and inspects
the resulting element tree. They are intentionally fast (no heavy data
processing, no plotting): they only assert the script renders to
completion without raising and that the four main pages can be visited.

Maintenance notes
-----------------
- AppTest does **not** propagate ``sys.argv`` to the script run, but our
  app reads ``sys.argv`` at module import time. We mutate ``sys.argv``
  in a fixture so that the ``--test-mode`` flag is picked up; this
  bypasses the welcome gate and auto-loads the demo dataset.
- Streamlit's ``AppTest.session_state`` does not expose ``.get()``;
  use ``"key" in at.session_state`` and ``at.session_state["key"]``.
- The ``timeout`` keyword on ``.run()`` must be larger than the slowest
  cached operation (auto-load + cleaning). 60s is comfortable.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
APP_PATH = REPO / "src" / "rrational" / "gui" / "app.py"

RUN_TIMEOUT = 60.0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_mode_argv(monkeypatch):
    """Mutate sys.argv so the app picks up TEST_MODE at import time."""
    monkeypatch.setattr(sys, "argv", ["app.py", "--test-mode"])


@pytest.fixture
def fresh_argv(monkeypatch):
    """Clean sys.argv so the app boots the welcome gate (no test mode)."""
    monkeypatch.setattr(sys, "argv", ["app.py"])


@pytest.fixture
def at_test_mode(test_mode_argv):
    """A fresh AppTest instance running the app in --test-mode."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=RUN_TIMEOUT)
    at.run(timeout=RUN_TIMEOUT)
    return at


# ---------------------------------------------------------------------------
# Phase 1a - the script runs at all
# ---------------------------------------------------------------------------


def test_app_imports_and_first_run_does_not_crash(test_mode_argv):
    """The top-level script runs to completion without raising in test mode."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=RUN_TIMEOUT)
    at.run(timeout=RUN_TIMEOUT)
    assert not at.exception, "Streamlit app raised in --test-mode: " + "; ".join(
        e.message for e in at.exception
    )


@pytest.mark.skipif(
    True,
    reason=(
        "AppTest inherits the user's local ~/.rrational/settings.yml — if "
        "a project is persisted there the app boots straight into the "
        "dataset workspace instead of the welcome screen, so this test "
        "is environment-dependent. The welcome flow itself is covered by "
        "the inspector's WelcomeWidget tests; this assertion stays in "
        "the suite as a documented future TODO (skip until we sandbox "
        "QSettings / ~/.rrational for AppTest)."
    ),
)
def test_app_renders_welcome_screen_without_project(fresh_argv):
    """Without a project, the welcome screen renders (no crash, has CTAs)."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=RUN_TIMEOUT)
    at.run(timeout=RUN_TIMEOUT)
    assert not at.exception, "Welcome screen raised: " + "; ".join(
        e.message for e in at.exception
    )
    button_labels = {b.label for b in at.button}
    # The welcome screen always offers these four entry points
    assert "Create New Project" in button_labels
    assert "Open Existing Project" in button_labels
    assert "Try Demo" in button_labels
    assert "Continue Without Project" in button_labels


# ---------------------------------------------------------------------------
# Phase 1b - no HTML escape leaks and no NameError leakage in main render
# ---------------------------------------------------------------------------


def test_no_nameerror_or_unresolved_html_in_main_render(at_test_mode):
    """No NameError leaks + no literal <i>/</b> tags in widget labels.

    The components-NameError bug shipped a traceback into the Streamlit
    error widget; this test would have caught it. The HTML escape checks
    guard against future regressions where ``unsafe_allow_html=True`` is
    forgotten and Streamlit shows the raw markup.
    """
    at = at_test_mode
    all_text = " ".join(m.value for m in at.markdown if hasattr(m, "value") and m.value)
    assert "NameError" not in all_text
    assert "Traceback" not in all_text
    assert "</i>" not in all_text, "Literal closing italic tag in UI"
    assert "</b>" not in all_text, "Literal closing bold tag in UI"
    assert "<i>" not in all_text, "Literal opening italic tag in UI"
    assert "<b>" not in all_text, "Literal opening bold tag in UI"


# ---------------------------------------------------------------------------
# Phase 1c - the four navigation pages each render without exception
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "page,expected_header",
    [
        ("Data", "Data Import"),
        ("Participants", "Participant Details"),
        ("Setup", "Setup"),
        ("Analysis", "HRV Analysis"),
    ],
)
def test_each_main_page_renders(test_mode_argv, page, expected_header):
    """Switching ``active_page`` renders each page without raising."""
    at = AppTest.from_file(str(APP_PATH), default_timeout=RUN_TIMEOUT)
    at.run(timeout=RUN_TIMEOUT)
    # Skip the first-run noise (toast/migration may still echo a warning),
    # then jump to the target page.
    at.session_state["active_page"] = page
    at.run(timeout=RUN_TIMEOUT)
    assert not at.exception, f"Page '{page}' raised: " + "; ".join(
        e.message for e in at.exception
    )
    headers = [h.value for h in at.header]
    assert expected_header in headers, (
        f"Expected header '{expected_header}' on page '{page}', got {headers!r}"
    )


# ---------------------------------------------------------------------------
# Phase 1d - sidebar navigation works end-to-end
# ---------------------------------------------------------------------------


def test_sidebar_exposes_all_four_navigation_buttons(at_test_mode):
    """Sidebar navigation always shows Data/Participants/Setup/Analysis."""
    labels = [b.label for b in at_test_mode.sidebar.button]
    for page in ("Data", "Participants", "Setup", "Analysis"):
        assert page in labels, f"Sidebar missing '{page}' button - have {labels!r}"


def test_initial_active_page_is_data(at_test_mode):
    """First run lands on the Data tab."""
    assert at_test_mode.session_state["active_page"] == "Data"
    headers = [h.value for h in at_test_mode.header]
    assert "Data Import" in headers


# ---------------------------------------------------------------------------
# Phase 1e - settings panel does not crash when expanded
# ---------------------------------------------------------------------------


def test_settings_panel_renders_in_sidebar(at_test_mode):
    """The Settings expander is in the sidebar and the Save button shows."""
    button_labels = [b.label for b in at_test_mode.button]
    # render_settings_panel always emits a "Save Settings" submit button
    assert "Save Settings" in button_labels, (
        f"Settings panel did not render - buttons were {button_labels!r}"
    )


# ---------------------------------------------------------------------------
# Phase 1f - the Analyze HRV click path produces visible results
# ---------------------------------------------------------------------------


def test_analyze_hrv_click_renders_results(test_mode_argv):
    """Clicking Analyze HRV on the Analysis tab must render results.

    This is the regression test for the bug where the
    "Aggregated results from N valid windows" path in
    ``src/rrational/gui/tabs/analysis.py`` returned before
    ``_display_single_participant_results`` was invoked - the user saw
    the "N valid windows" banner and then nothing. We assert that after
    clicking Analyze HRV in --test-mode (which auto-loads the demo
    dataset), the page renders the "Results for ..." subheader and at
    least the core HRV metrics (MeanNN, SDNN, RMSSD).
    """
    at = AppTest.from_file(str(APP_PATH), default_timeout=120.0)
    at.run(timeout=120.0)
    at.session_state["active_page"] = "Analysis"
    at.run(timeout=120.0)

    # Find and click Analyze HRV
    analyze_btn = next((b for b in at.button if b.label == "Analyze HRV"), None)
    assert analyze_btn is not None, (
        "Analyze HRV button missing on Analysis tab - "
        f"buttons were {[b.label for b in at.button]!r}"
    )
    analyze_btn.click()
    at.run(timeout=180.0)

    assert not at.exception, "Analyze HRV click raised: " + "; ".join(
        e.message for e in at.exception
    )

    # The fix path emits "Results for <pid>" - if this is missing the
    # render returned early like the original bug.
    subheaders = [s.value for s in at.subheader]
    assert any(s.startswith("Results for") for s in subheaders), (
        "Missing 'Results for ...' subheader - the analysis tab "
        "rendered the windowed-analysis banner but returned before "
        "_display_single_participant_results was called. "
        f"Subheaders were {subheaders!r}"
    )

    # At least the canonical HRV metrics should be on the page.
    metric_labels = {m.label for m in at.metric}
    for required in ("MeanNN", "SDNN", "RMSSD"):
        assert required in metric_labels, (
            f"Missing core HRV metric '{required}' after Analyze HRV - "
            f"metrics were {sorted(metric_labels)!r}"
        )
