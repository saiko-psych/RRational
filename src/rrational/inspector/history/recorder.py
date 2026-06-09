"""Append-only ledger of recorded :class:`Action` instances."""

from __future__ import annotations

from collections.abc import Iterator

from rrational.inspector.history.actions import Action


class HistoryRecorder:
    """Append-only log of user actions on the inspector.

    Held as ``MainWindow.history``. Components push via
    ``self._main_window.history.record(action)``. A future "Undo via
    history" feature could replay or invert from the same log, mirroring
    MNELAB's history list which is rendered to a Python script on
    application close.
    """

    def __init__(self) -> None:
        self._actions: list[Action] = []

    def record(self, action: Action) -> None:
        """Append ``action`` to the log. No-op when ``action`` is None."""
        if action is None:
            return
        self._actions.append(action)

    def clear(self) -> None:
        """Drop every recorded action — used when the workspace resets."""
        self._actions.clear()

    def __len__(self) -> int:
        return len(self._actions)

    def __iter__(self) -> Iterator[Action]:
        return iter(self._actions)
