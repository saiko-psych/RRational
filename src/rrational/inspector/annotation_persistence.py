"""Persistence for per-dataset annotations.

Annotations are saved to ``{pid}_annotations.yml`` in the same
``processed`` folder used by Streamlit's artifact corrections — keeping
the convention so users find every per-recording side-car next to the
``.rrational`` export.

Storage priority (mirrors :func:`gui.persistence.get_processed_dir`):

1. If ``project_path`` is provided: ``{project}/data/processed/``.
2. Otherwise: a configurable global fallback (defaults to
   ``~/.rrational/inspector_annotations/``).

Schema::

    participant_id: 0012MEBE
    format_version: '1.0'
    annotations:
      - t: 1700000001.0
        text: Subject coughed
        created_at: '2026-06-04T12:34:56'
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from rrational.inspector.annotations import Annotation

# Module-level constant so save and load can detect schema drift on load.
FORMAT_VERSION = "1.0"

# Global fallback when no project is open. Overridable by tests via
# ``set_annotation_config_dir`` so the developer's home isn't touched.
_DEFAULT_DIR = Path.home() / ".rrational" / "inspector_annotations"
_dir_override: Path | None = None

# Round 30 — defense against path traversal via a malicious participant_id
# loaded from an untrusted .rrational file. Allow only word chars + dash.
_PARTICIPANT_ID_RE = re.compile(r"[^\w\-]")


def _safe_participant_id(pid: str) -> str:
    """Sanitize ``pid`` for safe use in a filename component."""
    return _PARTICIPANT_ID_RE.sub("_", str(pid))


def set_annotation_config_dir(path: Path | None) -> None:
    """Override the global-fallback directory (None resets to default)."""
    global _dir_override
    _dir_override = path


def _resolve_dir(project_path: Path | None) -> Path:
    """Decide where ``{pid}_annotations.yml`` lives for this call."""
    if project_path is not None:
        out = Path(project_path) / "data" / "processed"
    else:
        out = _dir_override or _DEFAULT_DIR
    out.mkdir(parents=True, exist_ok=True)
    return out


def annotations_path(participant_id: str, project_path: Path | None = None) -> Path:
    """Resolve the on-disk path for ``{pid}_annotations.yml``.

    Round 30 — sanitizes ``participant_id`` to defeat path traversal
    (``../`` segments) and asserts the resolved path stays under
    ``_resolve_dir(project_path)``.
    """
    base = _resolve_dir(project_path)
    safe_pid = _safe_participant_id(participant_id)
    path = base / f"{safe_pid}_annotations.yml"
    resolved = path.resolve()
    base_resolved = base.resolve()
    if base_resolved != resolved.parent and base_resolved not in resolved.parents:
        raise ValueError(
            f"Resolved annotations path {resolved} escapes base {base_resolved}"
        )
    return path


def save_annotations(
    participant_id: str,
    annotations: list[Annotation],
    project_path: Path | None = None,
) -> Path:
    """Overwrite the annotations file for ``participant_id``.

    Always writes (even on empty list) so deleting the last annotation
    leaves a tidy empty file rather than a stale set on disk.
    """
    path = annotations_path(participant_id, project_path=project_path)
    payload = {
        "participant_id": str(participant_id),
        "format_version": FORMAT_VERSION,
        "annotations": [a.to_dict() for a in annotations],
    }
    # Atomic write — same pattern as save_sequences / save_exclusion_zones
    # in Round 24/26. A concurrent Streamlit reader between truncate and
    # flush previously saw an empty file and silently dropped the list.
    # Round 28 — Windows holds an exclusive lock on the destination file
    # while a reader has it open, so a plain ``tmp.replace()`` raises
    # PermissionError under contention. Retry with exponential backoff
    # so the legitimate concurrent-read case eventually wins.
    _atomic_replace(path, payload)
    return path


def _atomic_replace(path: Path, payload: dict) -> None:
    """Write ``payload`` to ``path`` atomically, with Windows-safe retries.

    Uses a per-call unique tmp suffix (pid + nanoseconds) so concurrent
    writers don't trample each other's staging file. The earlier shared
    ``.tmp`` suffix lost a race when two threads saved simultaneously —
    one wrote, the other overwrote, the first ``replace()`` then failed
    with FileNotFoundError.
    """
    import os
    import time

    tmp = path.with_suffix(f"{path.suffix}.{os.getpid()}.{time.time_ns()}.tmp")
    tmp.write_text(
        yaml.safe_dump(payload, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    last_exc: BaseException | None = None
    for attempt in range(5):
        try:
            tmp.replace(path)
            return
        except PermissionError as exc:
            last_exc = exc
            # 20 ms, 40 ms, 80 ms, 160 ms, 320 ms — total < 0.7 s
            time.sleep(0.02 * (2**attempt))
    if last_exc is not None:
        # Best-effort cleanup of the stranded tmp file before re-raising.
        try:
            tmp.unlink()
        except OSError:
            pass
        raise last_exc


def load_annotations(
    participant_id: str,
    project_path: Path | None = None,
) -> list[Annotation]:
    """Return the saved annotation list (empty if no file / unreadable)."""
    path = annotations_path(participant_id, project_path=project_path)
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return []
    # Round 30 — surface schema drift; load no longer silently swallows
    # entries from incompatible format versions.
    file_version = raw.get("format_version") if isinstance(raw, dict) else None
    if file_version is not None and file_version != FORMAT_VERSION:
        import logging

        logging.getLogger("rrational.inspector.annotation_persistence").warning(
            "Loading %s from format_version %s (current: %s); entries may be skipped if schema diverged.",
            path.name,
            file_version,
            FORMAT_VERSION,
        )
    items = raw.get("annotations", []) or []
    out: list[Annotation] = []
    for entry in items:
        try:
            out.append(Annotation.from_dict(entry))
        except (KeyError, TypeError, ValueError):
            continue
    return out
