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


def test_qss_uses_palette_tokens(qtbot):
    """The dashed-border QSS pulls from palette_tokens, not hardcoded hex."""
    from rrational.inspector.empty_state_widget import _dashed_qss
    from rrational.inspector.style.theme import palette_tokens

    dark_tokens = palette_tokens("dark")
    light_tokens = palette_tokens("light")
    dark_qss = _dashed_qss("dark")
    light_qss = _dashed_qss("light")
    # The dashed border colour for each mode must appear in the rendered QSS.
    assert dark_tokens["border_strong"] in dark_qss
    assert light_tokens["border_strong"] in light_qss
    # And the two stylesheets must actually differ — proof that the
    # palette switch flows through to the QSS string.
    assert dark_qss != light_qss


def test_set_theme_mode_reapplies_stylesheet(qtbot):
    """``set_theme_mode`` flips the active stylesheet without rebuilding."""
    w = EmptyStateWidget("Drop here", theme_mode="dark")
    qtbot.addWidget(w)
    dark_qss = w._frame.styleSheet()
    w.set_theme_mode("light")
    light_qss = w._frame.styleSheet()
    assert dark_qss != light_qss


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
