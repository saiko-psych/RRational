"""Smoke tests for ``EmptyStateWidget`` (Cluster C4).

Construction + drag/drop wiring only — the host-side file-open handler
is out of scope (each callsite wires its own).
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from qtpy.QtCore import QMimeData, QPointF, Qt, QUrl
from qtpy.QtGui import QDropEvent

from rrational.inspector.empty_state_widget import EmptyStateWidget


def test_widget_constructs_with_message(qtbot):
    w = EmptyStateWidget("Drop files here")
    qtbot.addWidget(w)
    # The label exists and carries the message text we passed in.
    assert "Drop files here" in w._message_label.text()


def test_set_message_updates_label(qtbot):
    w = EmptyStateWidget("initial")
    qtbot.addWidget(w)
    w.set_message("updated")
    assert w._message_label.text() == "updated"


def test_drop_event_emits_files_dropped(qtbot, tmp_path):
    w = EmptyStateWidget("Drop files here")
    qtbot.addWidget(w)

    f = tmp_path / "demo.csv"
    f.write_text("rr_ms\n850\n")

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(f))])
    event = QDropEvent(
        QPointF(10, 10),
        Qt.CopyAction,
        mime,
        Qt.LeftButton,
        Qt.NoModifier,
    )

    with qtbot.waitSignal(w.files_dropped, timeout=500) as blocker:
        w.dropEvent(event)
    paths = blocker.args[0]
    assert len(paths) == 1
    assert paths[0].name == "demo.csv"


def test_drop_event_without_urls_is_silent(qtbot):
    w = EmptyStateWidget("Drop files here")
    qtbot.addWidget(w)

    mime = QMimeData()  # no urls
    event = QDropEvent(
        QPointF(10, 10),
        Qt.CopyAction,
        mime,
        Qt.LeftButton,
        Qt.NoModifier,
    )
    # Should not raise + should not emit (we'd see it if it did via timeout).
    w.dropEvent(event)
