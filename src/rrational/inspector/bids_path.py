"""Immutable path builder for BIDS-compliant filenames.

Cluster B5 — mirrors ``mne_bids.BIDSPath`` for the inspector's BIDS
export pipeline. The dataclass holds the four BIDS entities we
actually use (subject, session, task, run) plus a ``root`` pointing
at the dataset's top directory, and exposes :meth:`update`,
:meth:`match`, :meth:`mkdir`, and :meth:`find_matching_sidecar` so
callers can compose / query BIDS bundles without re-implementing the
string-stitching every time.

Immutability is enforced via ``@dataclass(frozen=True)``: ``update``
returns a NEW instance with the overridden fields rather than
mutating the receiver, matching the mne_bids API and making the
class safely shareable across threads / signal handlers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path


# Entity prefixes per BIDS v1.11 — exposed as constants so other
# inspector modules can reuse them without re-typing.
_PREFIX = {
    "subject": "sub",
    "session": "ses",
    "task": "task",
    "run": "run",
}


@dataclass(frozen=True)
class RRBIDSPath:
    """Single BIDS path entry for a cardiac-physio recording.

    Attributes
    ----------
    subject
        Required. BIDS-conformant ``sub-<label>`` value (alphanumerics
        only; no leading "sub-" prefix — that's added by ``basename``).
    session, task, run
        Optional entities. ``None`` drops the entity from ``basename``.
    root
        Dataset root directory. Used by :meth:`match`, :meth:`mkdir`,
        and :meth:`find_matching_sidecar` to anchor relative paths.
    """

    subject: str
    root: Path
    session: str | None = None
    task: str | None = None
    run: str | None = None

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    def update(self, **kwargs) -> "RRBIDSPath":
        """Return a new RRBIDSPath with the supplied fields overridden.

        Matches ``mne_bids.BIDSPath.update`` — passes accepted kwargs
        through ``dataclasses.replace`` so unknown keys raise (rather
        than being silently ignored). ``root`` is coerced to Path for
        callers that pass a string.
        """
        if "root" in kwargs and not isinstance(kwargs["root"], Path):
            kwargs["root"] = Path(kwargs["root"])
        return replace(self, **kwargs)

    # ------------------------------------------------------------------
    # Path composition
    # ------------------------------------------------------------------
    @property
    def basename(self) -> str:
        """Compose the BIDS file stem (no suffix / extension).

        Order: sub > ses > task > run, matching the BIDS entity order
        rule. Optional entities are dropped when None.
        """
        parts = [f"{_PREFIX['subject']}-{self.subject}"]
        if self.session:
            parts.append(f"{_PREFIX['session']}-{self.session}")
        if self.task:
            parts.append(f"{_PREFIX['task']}-{self.task}")
        if self.run:
            parts.append(f"{_PREFIX['run']}-{self.run}")
        return "_".join(parts)

    @property
    def directory(self) -> Path:
        """Compose ``root / sub-<id> [/ ses-<ses>] / <datatype>``.

        Datatype is hard-coded to ``physio`` because the inspector only
        emits cardiac-physio recordings. Sub-and-session-only — task
        and run live in the FILENAME, not the directory tree, per BIDS.
        """
        out = self.root / f"{_PREFIX['subject']}-{self.subject}"
        if self.session:
            out = out / f"{_PREFIX['session']}-{self.session}"
        return out / "physio"

    def mkdir(self) -> Path:
        """Create :attr:`directory` (with parents) and return it."""
        d = self.directory
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------
    def match(self, suffix: str = "physio", extension: str = ".json") -> list[Path]:
        """Return every file under :attr:`root` matching the BIDS query.

        Pattern is ``root/**/<basename>_<suffix><extension>`` so the
        caller can find existing sidecars, TSVs, or any other BIDS
        artifact that shares the basename. ``suffix`` defaults to
        ``physio`` and ``extension`` to ``.json`` because the most
        common inspector call is "find this recording's sidecar".

        Returns
        -------
        list[Path]
            Sorted, deduplicated list of matches. Empty when the root
            does not exist (no exception — callers can iterate).
        """
        if not self.root.exists():
            return []
        pattern = f"**/{self.basename}_{suffix}{extension}"
        return sorted({p for p in self.root.glob(pattern)})

    def find_matching_sidecar(self) -> Path | None:
        """Return the canonical physio JSON sidecar, or None.

        Convenience wrapper around :meth:`match` for the most common
        lookup. Returns ``None`` (not a stale Path) when nothing
        matches so callers can branch without try/except.
        """
        hits = self.match(suffix="physio", extension=".json")
        return hits[0] if hits else None
