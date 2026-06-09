"""Free-text annotation dataclass.

Lightweight value object so persistence + UI code can pass annotations
around without coupling to PyQtGraph items. The actual on-plot rendering
(vertical line + label) lives in :mod:`plot_widget`.

Schema::

    Annotation(t=1700000123.456, text="subject coughed",
               created_at="2026-06-04T12:34:56", duration=0.0)

Round-trips through ``to_dict`` / ``from_dict`` so the persistence layer
can emit plain YAML without YAML-tag-prefixed dataclasses.

Range vs point annotations
--------------------------
``duration`` defaults to 0.0 (a point annotation). When the user
drags a region on the plot the dialog passes ``duration = t_end - t``
so the annotation describes the whole range. MNE's
``mne.Annotations`` exposes onset / duration / description; we use the
same trio (``t`` / ``duration`` / ``text``) so future BIDS-physio
export can mirror the spec one-to-one. Older YAML files without a
``duration`` field load as point annotations — no migration needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Annotation:
    """A free-text annotation pinned to a point or range on the timeline.

    Attributes
    ----------
    t : float
        Wall-clock time of the annotation onset, seconds-since-epoch.
    text : str
        Free-text content the user typed in the input dialog.
    created_at : str
        ISO-8601 creation timestamp. Stored so editors / future versions
        can sort or display "added at...". Auto-filled by :meth:`create`.
    duration : float
        Length of the annotated range in seconds. ``0.0`` (default)
        means the annotation is a point in time, matching the original
        single-instant semantics. Set to a positive value when the
        annotation covers a range — exposed via :attr:`t_end`.
    """

    t: float
    text: str
    created_at: str
    duration: float = field(default=0.0)

    @property
    def t_end(self) -> float:
        """End time of the annotated range, seconds-since-epoch."""
        return float(self.t) + float(self.duration)

    @property
    def is_range(self) -> bool:
        """True when the annotation spans a non-zero duration."""
        return self.duration > 0.0

    def to_dict(self) -> dict:
        # ``duration`` is always written so newer YAML files are
        # consistent. Older files omitting it still load (see from_dict).
        return {
            "t": float(self.t),
            "text": str(self.text),
            "created_at": str(self.created_at),
            "duration": float(self.duration),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Annotation":
        return cls(
            t=float(d["t"]),
            text=str(d.get("text", "")),
            created_at=str(d.get("created_at", "")),
            duration=float(d.get("duration", 0.0)),
        )

    @classmethod
    def create(cls, t: float, text: str, duration: float = 0.0) -> "Annotation":
        """Build a fresh annotation, auto-stamping ``created_at`` to now.

        Pass ``duration > 0`` to create a range annotation (the
        ``end_t`` becomes ``t + duration``); leave at the default ``0.0``
        for a single-instant marker.
        """
        return cls(
            t=float(t),
            text=str(text),
            created_at=datetime.now().isoformat(),
            duration=float(duration),
        )

    @classmethod
    def create_range(cls, t_start: float, t_end: float, text: str) -> "Annotation":
        """Convenience constructor for drag-range annotations.

        ``t_end`` is the absolute end timestamp (not a duration). The
        ordering of the two timestamps does not matter — the helper
        sorts them so an inverted drag still yields a positive
        duration.
        """
        a, b = sorted((float(t_start), float(t_end)))
        return cls.create(t=a, text=text, duration=b - a)
