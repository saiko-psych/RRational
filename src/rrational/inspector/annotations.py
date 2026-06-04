"""Free-text annotation dataclass (Phase 20).

Lightweight value object so persistence + UI code can pass annotations
around without coupling to PyQtGraph items. The actual on-plot rendering
(vertical line + label) lives in :mod:`plot_widget`.

Schema::

    Annotation(t=1700000123.456, text="subject coughed", created_at="2026-06-04T12:34:56")

Round-trips through ``to_dict`` / ``from_dict`` so the persistence layer
can emit plain YAML without YAML-tag-prefixed dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Annotation:
    """A free-text annotation pinned to one point on the timeline.

    Attributes
    ----------
    t : float
        Wall-clock time of the annotation, seconds-since-epoch.
    text : str
        Free-text content the user typed in the input dialog.
    created_at : str
        ISO-8601 creation timestamp. Stored so editors / future versions
        can sort or display "added at...". Auto-filled by :meth:`create`.
    """

    t: float
    text: str
    created_at: str

    def to_dict(self) -> dict:
        return {
            "t": float(self.t),
            "text": str(self.text),
            "created_at": str(self.created_at),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Annotation":
        return cls(
            t=float(d["t"]),
            text=str(d.get("text", "")),
            created_at=str(d.get("created_at", "")),
        )

    @classmethod
    def create(cls, t: float, text: str) -> "Annotation":
        """Build a fresh annotation, auto-stamping ``created_at`` to now."""
        return cls(t=float(t), text=str(text), created_at=datetime.now().isoformat())
