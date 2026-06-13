"""Per-dataset persistence for exclusion zones.

An *exclusion zone* is a user-marked time window inside a recording
whose beats should be filtered out of every downstream HRV computation.
They're created by drag-selecting on the timeline plot (see
:class:`rrational.inspector.plot_widget.RRPlotWidget`) and round-trip
through the same project-vs-global storage scheme as the artifact
corrections.

File layout::

    {project}/data/processed/{pid}_exclusions.yml   # when a project is open
    ~/.rrational/inspector/{pid}_exclusions.yml     # global fallback

Schema (v1.0)::

    format_version: "1.0"
    participant_id: <pid>
    exclusion_zones:
      - start_t: 1767268800.0
        end_t:   1767268830.0
        start_iso: "2026-01-01T12:00:00"
        end_iso:   "2026-01-01T12:00:30"
        start_beat_idx: 12     # optional - None when not resolvable
        end_beat_idx:   58     # optional - None when not resolvable
        reason:    "noisy electrode"
        created_at: "2026-06-04T09:31:12"

The artifact-correction file is intentionally SEPARATE from this one
so the two concerns can evolve independently and so the Streamlit app —
which knows nothing about exclusion zones yet — keeps loading
artifacts cleanly.

Resolution order for the storage directory mirrors
``inspector.persistence``: a test-override path beats the project path
beats the global fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

_DEFAULT_DIR = Path.home() / ".rrational" / "inspector"
_dir_override: Path | None = None


@dataclass
class ExclusionZone:
    """One user-marked time window to remove from analysis.

    ``start_t`` / ``end_t`` are seconds-since-epoch (same convention as
    :class:`~rrational.inspector.data_loader.InspectorData.t`).  The
    optional ``start_beat_idx`` / ``end_beat_idx`` mirror the resolved
    array indices at the moment the zone was created; they're stored
    for provenance but downstream code re-resolves the indices against
    the live timeline so the zones remain meaningful even if the
    underlying recording changes layout.
    """

    start_t: float
    end_t: float
    reason: str = ""
    start_beat_idx: int | None = None
    end_beat_idx: int | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        # Persist the human-readable ISO timestamp alongside the raw
        # epoch seconds. The epoch value is the source of truth on
        # reload (no parsing fuzz), but the ISO string makes the YAML
        # diffable for users sanity-checking on disk.
        start_iso = datetime.fromtimestamp(self.start_t).isoformat()
        end_iso = datetime.fromtimestamp(self.end_t).isoformat()
        return {
            "start_t": float(self.start_t),
            "end_t": float(self.end_t),
            "start_iso": start_iso,
            "end_iso": end_iso,
            "start_beat_idx": (
                None if self.start_beat_idx is None else int(self.start_beat_idx)
            ),
            "end_beat_idx": (
                None if self.end_beat_idx is None else int(self.end_beat_idx)
            ),
            "reason": str(self.reason or ""),
            "created_at": str(self.created_at),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ExclusionZone":
        # Tolerate older / partial dicts: missing reason -> empty string,
        # missing indices -> None, missing timestamps -> derive from ISO.
        start_t = d.get("start_t")
        end_t = d.get("end_t")
        if start_t is None and d.get("start_iso"):
            start_t = datetime.fromisoformat(d["start_iso"]).timestamp()
        if end_t is None and d.get("end_iso"):
            end_t = datetime.fromisoformat(d["end_iso"]).timestamp()
        if start_t is None or end_t is None:
            raise KeyError("ExclusionZone requires start_t/end_t (or *_iso)")
        return cls(
            start_t=float(start_t),
            end_t=float(end_t),
            reason=str(d.get("reason", "") or ""),
            start_beat_idx=(
                None if d.get("start_beat_idx") is None else int(d["start_beat_idx"])
            ),
            end_beat_idx=(
                None if d.get("end_beat_idx") is None else int(d["end_beat_idx"])
            ),
            created_at=str(d.get("created_at") or datetime.now().isoformat()),
        )


def set_exclusion_config_dir(path: Path | None) -> None:
    """Redirect persistence reads/writes to ``path`` (None = default).

    Test-override hook - takes priority over the project path passed
    into :func:`save_exclusion_zones`.
    """
    global _dir_override
    _dir_override = path


def _resolve_dir(project_path: Path | None) -> Path:
    """Pick the storage directory using the documented precedence.

    1. The test override (``set_exclusion_config_dir``)
    2. ``{project}/data/processed`` when ``project_path`` is supplied
    3. ``~/.rrational/inspector`` as global fallback
    """
    if _dir_override is not None:
        base = _dir_override
    elif project_path is not None:
        base = Path(project_path) / "data" / "processed"
    else:
        base = _DEFAULT_DIR
    base.mkdir(parents=True, exist_ok=True)
    return base


def _zones_path(pid: str, project_path: Path | None) -> Path:
    return _resolve_dir(project_path) / f"{pid}_exclusions.yml"


def save_exclusion_zones(
    pid: str,
    zones: list[ExclusionZone],
    project_path: Path | None = None,
) -> Path:
    """Overwrite the on-disk exclusion-zone list for ``pid``.

    Always writes (even for an empty list) so the file accurately
    reflects "user actively cleared the zones" rather than "never set".
    Use :func:`delete_exclusion_zones` to remove the file entirely.
    """
    p = _zones_path(pid, project_path)
    # Sort by start_t so YAML diffs stay deterministic — drag order
    # previously bled into the on-disk representation, producing
    # spurious commits when two sessions added the same zones in
    # different order.
    sorted_zones = sorted(zones, key=lambda z: z.start_t)
    payload = {
        "format_version": "1.0",
        "participant_id": str(pid),
        "exclusion_zones": [z.to_dict() for z in sorted_zones],
        "last_modified": datetime.now().isoformat(),
    }
    # Atomic write: a concurrent Streamlit reader between truncate
    # and flush previously saw an empty file and silently dropped
    # every exclusion. Same pattern as Round 24's save_sequences fix.
    # Round 28 — Windows rejects ``replace()`` if the target is open
    # by another process; retry with backoff so the concurrent-read
    # contention case actually wins instead of crashing the GUI. Use
    # a per-call unique tmp suffix so concurrent writers from the same
    # process don't trample each other's staging file (the earlier
    # shared ``.tmp`` lost the race with FileNotFoundError).
    import os
    import time

    tmp = p.with_suffix(f"{p.suffix}.{os.getpid()}.{time.time_ns()}.tmp")
    tmp.write_text(
        yaml.safe_dump(payload, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    last_exc: BaseException | None = None
    for attempt in range(5):
        try:
            tmp.replace(p)
            return p
        except PermissionError as exc:
            last_exc = exc
            time.sleep(0.02 * (2**attempt))
    if last_exc is not None:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise last_exc
    return p


def load_exclusion_zones(
    pid: str,
    project_path: Path | None = None,
) -> list[ExclusionZone]:
    """Return all zones for ``pid`` (empty list if no file or unreadable)."""
    p = _zones_path(pid, project_path)
    if not p.exists():
        return []
    try:
        with p.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return []
    items = raw.get("exclusion_zones", []) or []
    zones: list[ExclusionZone] = []
    for entry in items:
        try:
            zones.append(ExclusionZone.from_dict(entry))
        except (KeyError, TypeError, ValueError):
            # Skip malformed entries rather than dropping the whole file
            continue
    return zones


def delete_exclusion_zones(
    pid: str,
    project_path: Path | None = None,
) -> None:
    """Remove the on-disk file for ``pid`` (no-op if missing)."""
    p = _zones_path(pid, project_path)
    try:
        p.unlink()
    except FileNotFoundError:
        return
