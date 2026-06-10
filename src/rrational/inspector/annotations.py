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


# ---------------------------------------------------------------------
# Cluster B3 / B4 — MNE-style helpers on annotation lists.
#
# These mirror ``mne.Annotations`` methods but operate on plain
# ``list[Annotation]`` containers (the format the inspector persists
# and passes around) so callers don't need to wrap their data in a
# new class.
# ---------------------------------------------------------------------


def crop(annotations: list[Annotation], tmin: float, tmax: float) -> list[Annotation]:
    """Return annotations whose onset falls within ``[tmin, tmax]``.

    Range annotations are clipped: if the original onset/end straddles
    the window, the returned annotation's duration is shrunk to the
    overlap region. Annotations entirely outside the window drop.

    Mirrors ``mne.Annotations.crop`` (without the ``emit_warning``
    side-effect). ``tmin > tmax`` raises — matching MNE's contract.
    """
    if tmin > tmax:
        raise ValueError(f"tmin ({tmin}) must be <= tmax ({tmax})")
    out: list[Annotation] = []
    for ann in annotations:
        # Treat the annotation as the inclusive interval [t, t_end].
        a_start = float(ann.t)
        a_end = float(ann.t_end)
        if a_end < tmin or a_start > tmax:
            continue
        clipped_start = max(a_start, tmin)
        clipped_end = min(a_end, tmax)
        new_duration = max(0.0, clipped_end - clipped_start)
        out.append(
            Annotation(
                t=clipped_start,
                text=ann.text,
                created_at=ann.created_at,
                duration=new_duration,
            )
        )
    return out


def rename(annotations: list[Annotation], mapping: dict[str, str]) -> list[Annotation]:
    """Return a new list with annotation ``text`` rewritten via ``mapping``.

    Annotations whose ``text`` is not a mapping key are passed through
    unchanged. Mirrors ``mne.Annotations.rename`` — useful for batch-
    relabelling protocols like ``{"baseline": "rest"}``.
    """
    out: list[Annotation] = []
    for ann in annotations:
        new_text = mapping.get(ann.text, ann.text)
        out.append(
            Annotation(
                t=ann.t,
                text=new_text,
                created_at=ann.created_at,
                duration=ann.duration,
            )
        )
    return out


def count(annotations: list[Annotation]) -> dict[str, int]:
    """Return a ``{text: count}`` histogram of annotation labels.

    Mirrors ``mne.Annotations.count``. Empty texts are bucketed under
    the literal empty string so the user can spot un-labelled markers.
    """
    counts: dict[str, int] = {}
    for ann in annotations:
        counts[ann.text] = counts.get(ann.text, 0) + 1
    return counts


def set_durations(
    annotations: list[Annotation], mapping: dict[str, float]
) -> list[Annotation]:
    """Return a new list with ``duration`` rewritten by label mapping.

    Annotations whose ``text`` does not appear in ``mapping`` keep
    their original duration. Mirrors ``mne.Annotations.set_durations``
    — handy for replacing point-marker placeholders with the real
    epoch length after the fact.
    """
    out: list[Annotation] = []
    for ann in annotations:
        new_duration = float(mapping.get(ann.text, ann.duration))
        out.append(
            Annotation(
                t=ann.t,
                text=ann.text,
                created_at=ann.created_at,
                duration=max(0.0, new_duration),
            )
        )
    return out


def chunk_annotations(
    annotation: Annotation,
    chunk_duration_s: float,
    overlap_s: float = 0.0,
) -> list[Annotation]:
    """Slice a long range annotation into N shorter overlapping chunks.

    Cluster B4 — mirrors ``mne.events_from_annotations(chunk_duration=)``
    on the ``Epochs`` side: take a long ``BAD_movement`` annotation and
    fan it out into 30-second epochs you can compute HRV on.

    The original ``text`` is preserved on every chunk. ``created_at``
    is propagated unchanged so the audit trail still points to the
    parent annotation's creation. Point annotations (duration == 0)
    return a one-element list (the original) since there is nothing to
    chunk.

    Parameters
    ----------
    annotation
        A range annotation (duration > 0). Point annotations are
        returned unchanged in a single-element list.
    chunk_duration_s
        Length of each sub-event in seconds. Must be > 0.
    overlap_s
        Per-chunk overlap in seconds. ``0.0`` (default) gives
        non-overlapping sub-events. Must be ``< chunk_duration_s``.
    """
    if chunk_duration_s <= 0:
        raise ValueError("chunk_duration_s must be > 0")
    if overlap_s < 0 or overlap_s >= chunk_duration_s:
        raise ValueError("overlap_s must be in [0, chunk_duration_s)")
    if annotation.duration <= 0:
        return [annotation]

    step = chunk_duration_s - overlap_s
    out: list[Annotation] = []
    t_cursor = float(annotation.t)
    t_end = float(annotation.t_end)
    # Use a half-open interval [t_cursor, t_cursor + chunk_duration_s)
    # so the last chunk gets emitted even when it would extend exactly
    # to t_end (no fractional rounding silent-drop).
    while t_cursor < t_end:
        chunk_end = min(t_cursor + chunk_duration_s, t_end)
        # Skip degenerate trailing chunks (< 1ms) — they're nearly
        # always rounding artefacts and never useful to analysis.
        if chunk_end - t_cursor < 1e-3:
            break
        out.append(
            Annotation(
                t=t_cursor,
                text=annotation.text,
                created_at=annotation.created_at,
                duration=chunk_end - t_cursor,
            )
        )
        t_cursor += step
    return out
