"""Smoke tests for the workflow Walkthrough dialog.

Covers the PAGES tuple shape, the WalkthroughPage dataclass, and
construction + navigation of WalkthroughDialog without a real
MainWindow (None is a documented valid argument).
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from rrational.inspector.walkthrough import (  # noqa: E402
    PAGES,
    WalkthroughDialog,
    WalkthroughPage,
)


# ---------------------------------------------------------------------
# PAGES tuple shape
# ---------------------------------------------------------------------
def test_pages_has_expected_count():
    # 11 pages cover the full Welcome -> Tips and tricks -> Colorblind flow.
    assert len(PAGES) == 11


def test_pages_are_walkthrough_page_instances():
    assert all(isinstance(p, WalkthroughPage) for p in PAGES)


def test_pages_have_title_and_body_html():
    for page in PAGES:
        assert page.title
        assert page.body_html
        assert (
            "<p>" in page.body_html
            or "<ul>" in page.body_html
            or "<ol>" in page.body_html
        )


# ---------------------------------------------------------------------
# WalkthroughPage dataclass
# ---------------------------------------------------------------------
def test_walkthrough_page_dataclass_fields():
    page = WalkthroughPage(title="t", body_html="<p>x</p>")
    assert page.title == "t"
    assert page.body_html == "<p>x</p>"
    # Defaults exist for the optional fields.
    assert page.illustration == ""
    assert page.try_target_attr is None
    assert page.try_label == "Try it now"


def test_walkthrough_page_is_frozen():
    page = WalkthroughPage(title="t", body_html="<p>x</p>")
    try:
        page.title = "new"  # type: ignore[misc]
    except Exception:
        pass
    else:  # pragma: no cover - documents intent
        raise AssertionError("WalkthroughPage should be frozen (immutable)")


# ---------------------------------------------------------------------
# WalkthroughDialog construction + navigation
# ---------------------------------------------------------------------
def test_dialog_constructs_without_main_window(qtbot):
    """``main_window=None`` is the documented Help-menu test path."""
    dlg = WalkthroughDialog(main_window=None)
    qtbot.addWidget(dlg)
    assert dlg.page_count() == len(PAGES)
    assert dlg.current_index() == 0


def test_dialog_next_advances_index(qtbot):
    dlg = WalkthroughDialog(main_window=None)
    qtbot.addWidget(dlg)
    assert dlg.current_index() == 0
    dlg._on_next()
    assert dlg.current_index() == 1
    dlg._on_next()
    assert dlg.current_index() == 2


def test_dialog_previous_goes_back(qtbot):
    dlg = WalkthroughDialog(main_window=None)
    qtbot.addWidget(dlg)
    dlg._on_next()
    dlg._on_next()
    assert dlg.current_index() == 2
    dlg._on_prev()
    assert dlg.current_index() == 1


def test_dialog_previous_at_start_is_a_noop(qtbot):
    dlg = WalkthroughDialog(main_window=None)
    qtbot.addWidget(dlg)
    assert dlg.current_index() == 0
    dlg._on_prev()
    assert dlg.current_index() == 0


def test_dialog_next_at_end_is_a_noop(qtbot):
    dlg = WalkthroughDialog(main_window=None)
    qtbot.addWidget(dlg)
    last_idx = dlg.page_count() - 1
    for _ in range(last_idx + 3):
        dlg._on_next()
    assert dlg.current_index() == last_idx
