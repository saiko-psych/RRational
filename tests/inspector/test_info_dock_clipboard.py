"""Round 30 regression — InfoDock copy button copies the FULL filename.

R29 changed ``_CopyableLabel._refresh_display`` to store the *elided*
string in the inner ``QLabel`` so a long filename renders as
``negative_r…csv`` at slim dock widths. The copy handler used to read
back from ``_label.text()`` and therefore silently put the truncated,
useless string on the clipboard. R30 fixed ``_on_copy`` to copy
``self._full_text`` instead.

This test forces the label narrow enough that ``_refresh_display``
actually elides (so ``_label.text()`` differs from the full name), then
clicks the copy button and asserts the clipboard holds the complete,
unabbreviated filename — not the ``…`` form.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")

from qtpy.QtWidgets import QApplication

from rrational.inspector.info_dock import _CopyableLabel

# A deliberately long, real-world-shaped filename: the stem is long
# enough that ElideMiddle must drop information-bearing characters at a
# slim dock width, so the elided display string cannot equal the full
# name. Written to disk via tmp_path so the test stays hermetic.
_LONG_NAME = "0405SAAD_170325_MEL_0.00-0.40_RRIntervals_negative_rr.csv"


def test_copy_button_copies_full_name_not_elided(qtbot, tmp_path):
    # Create the file on disk purely to keep the fixture hermetic and to
    # source the name from a real path rather than a bare literal.
    path = tmp_path / _LONG_NAME
    path.write_text("800\n810\n820\n", encoding="utf-8")
    full_name = path.name

    label = _CopyableLabel()
    qtbot.addWidget(label)
    label.setText(full_name)

    # Force a narrow width and re-elide, mimicking the slim InfoDock
    # (min width 220px) minus the label/button layout margins.
    label.resize(90, 22)
    label._refresh_display()

    # Sanity: elision actually happened. The inner QLabel must hold a
    # truncated ("…") string that is NOT the full filename; otherwise the
    # test would pass vacuously even under the old buggy behaviour.
    displayed = label._label.text()
    assert displayed != full_name
    assert "…" in displayed

    # Trigger the copy handler exactly as the button click would.
    label._on_copy()

    clipboard = QApplication.clipboard()
    copied = clipboard.text()

    # The clipboard must hold the FULL name, including the long stem and
    # the ".csv" extension — not the elided display string.
    assert copied == full_name
    assert copied == _LONG_NAME
    assert "…" not in copied
    assert copied.endswith(".csv")
    assert "0405SAAD_170325_MEL" in copied
    assert "negative_rr" in copied
    # Guard against the exact R29 regression: never the elided form.
    assert copied != displayed


def test_text_getter_returns_full_name_after_elision(qtbot):
    """``_CopyableLabel.text()`` must also report the full, unelided name.

    The public getter is what host code (and selection-copy) relies on;
    it should mirror the clipboard behaviour even when the visible label
    has been truncated.
    """
    label = _CopyableLabel()
    qtbot.addWidget(label)
    label.setText(_LONG_NAME)

    label.resize(90, 22)
    label._refresh_display()

    assert label._label.text() != _LONG_NAME  # visibly elided
    assert label.text() == _LONG_NAME  # logically full
