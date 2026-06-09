"""Render a :class:`HistoryRecorder` as a runnable Python script."""

from __future__ import annotations

from rrational.inspector.history.recorder import HistoryRecorder

SCRIPT_HEADER = '''"""Auto-generated RRational recipe.

Re-running this script with the same input files in place reproduces
the GUI actions that were recorded. The recipe is exported from
File -> Save recipe... and is intended as a reproducible companion to
the .rrational v2 audit trail (which lives inside each export).
"""

from __future__ import annotations

from pathlib import Path

'''


def to_script(recorder: HistoryRecorder) -> str:
    """Render the recorded history as a single ``.py`` script string.

    Each :class:`~rrational.inspector.history.actions.Action` contributes
    its own ``to_python()`` block; the blocks are separated by a blank
    line so the rendered script reads top-to-bottom like a manual
    transcript of the session. When the recorder is empty we emit a
    short placeholder comment so the file is still valid Python.
    """
    body = "\n\n".join(action.to_python() for action in recorder)
    if not body:
        body = "# No actions recorded yet."
    return SCRIPT_HEADER + body + "\n"
