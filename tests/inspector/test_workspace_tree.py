"""Tests for the WorkspaceTreeWidget with badge delegate (Cluster C6)."""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from qtpy.QtGui import QFont

from rrational.inspector.workspace_tree import (
    ROLE_BADGES,
    ROLE_DATASET_IDX,
    ROLE_SECTION_NAME,
    WorkspaceItem,
    WorkspaceTreeWidget,
    _BADGE_COLORS,
    _BadgeDelegate,
)


def test_widget_constructs_empty(qtbot):
    w = WorkspaceTreeWidget()
    qtbot.addWidget(w)
    assert w.topLevelItemCount() == 0
    assert w.indentation() == 14
    assert w.isHeaderHidden()


def test_set_items_populates_tree(qtbot):
    w = WorkspaceTreeWidget()
    qtbot.addWidget(w)
    w.set_items(
        [
            WorkspaceItem(
                name="file_a.rrational",
                dataset_idx=0,
                badges=["PROC", "BIDS"],
                tooltip="/tmp/file_a.rrational",
                children=[
                    WorkspaceItem(
                        name="rest_pre (120 beats)",
                        dataset_idx=0,
                        section_name="rest_pre",
                    ),
                ],
            ),
            WorkspaceItem(name="file_b.rrational", dataset_idx=1, badges=["KUBIOS"]),
        ]
    )
    assert w.topLevelItemCount() == 2
    top0 = w.topLevelItem(0)
    assert top0.text(0) == "file_a.rrational"
    assert top0.data(0, ROLE_DATASET_IDX) == 0
    assert top0.data(0, ROLE_BADGES) == ["PROC", "BIDS"]
    # Child
    assert top0.childCount() == 1
    kid = top0.child(0)
    assert kid.data(0, ROLE_SECTION_NAME) == "rest_pre"
    assert kid.data(0, ROLE_DATASET_IDX) == 0
    # Second top-level
    top1 = w.topLevelItem(1)
    assert top1.data(0, ROLE_BADGES) == ["KUBIOS"]


def test_set_active_index_bolds_matching_row(qtbot):
    w = WorkspaceTreeWidget()
    qtbot.addWidget(w)
    w.set_items(
        [
            WorkspaceItem(name="a", dataset_idx=0),
            WorkspaceItem(name="b", dataset_idx=1),
            WorkspaceItem(name="c", dataset_idx=2),
        ]
    )
    w.set_active_index(1)
    assert w.topLevelItem(0).font(0).bold() is False
    assert w.topLevelItem(1).font(0).bold() is True
    assert w.topLevelItem(2).font(0).bold() is False
    # Switching clears the previous active.
    w.set_active_index(2)
    assert w.topLevelItem(1).font(0).bold() is False
    assert w.topLevelItem(2).font(0).bold() is True
    # None unbolds everything.
    w.set_active_index(None)
    for i in range(3):
        assert w.topLevelItem(i).font(0).bold() is False


def test_set_items_replaces_existing_rows(qtbot):
    w = WorkspaceTreeWidget()
    qtbot.addWidget(w)
    w.set_items([WorkspaceItem(name="a", dataset_idx=0)])
    assert w.topLevelItemCount() == 1
    w.set_items(
        [
            WorkspaceItem(name="x", dataset_idx=0),
            WorkspaceItem(name="y", dataset_idx=1),
        ]
    )
    assert w.topLevelItemCount() == 2
    assert w.topLevelItem(0).text(0) == "x"


def test_badge_colors_cover_documented_taxonomy():
    """Every documented badge tag in the spec resolves to a palette token."""
    for tag in ("PROC", "N-WIN", "BAD-Q", "KUBIOS", "BIDS"):
        assert tag in _BADGE_COLORS


def test_delegate_size_hint_grows_with_badges(qtbot):
    """A row with badges must reserve more horizontal space than one without."""
    w = WorkspaceTreeWidget()
    qtbot.addWidget(w)
    w.set_items(
        [
            WorkspaceItem(name="bare", dataset_idx=0),
            WorkspaceItem(name="badged", dataset_idx=1, badges=["PROC", "BIDS"]),
        ]
    )
    bare_idx = w.indexFromItem(w.topLevelItem(0))
    badged_idx = w.indexFromItem(w.topLevelItem(1))
    from qtpy.QtWidgets import QStyleOptionViewItem

    opt = QStyleOptionViewItem()
    opt.font = QFont()
    bare_size = w._delegate.sizeHint(opt, bare_idx)
    badged_size = w._delegate.sizeHint(opt, badged_idx)
    assert badged_size.width() > bare_size.width()


def test_delegate_set_theme_mode_resolves_tokens():
    d = _BadgeDelegate(mode="dark")
    dark_tokens = dict(d._tokens)
    d.set_theme_mode("light")
    # At least one common token must differ between dark + light themes
    # (e.g. bg_base flips from charcoal to ivory).
    assert dark_tokens["bg_base"] != d._tokens["bg_base"]
