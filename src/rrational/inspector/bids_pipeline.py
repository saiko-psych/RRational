"""Lightweight content-addressed cache for per-recording BIDS pipeline outputs (Cluster C8).

A pragmatic placeholder for MNE-BIDS-pipeline's joblib-backed memoiser:
we hash ``(recording-mtime, fn-name)`` with stdlib :mod:`hashlib`, look
up a JSON sidecar in ``cache_dir``, and on miss run ``fn`` and persist
the returned :class:`~pathlib.Path` next to the sidecar. No joblib
dependency — keeps the inspector portable and easy to reason about.

The cache value is the absolute string path returned by ``fn``; the
sidecar JSON carries the cache key + that path so the user can audit
what was reused. Callers MUST return a :class:`Path` from ``fn`` so we
can validate the artefact still exists before declaring a hit.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path


def _hash_key(recording_path: Path, fn_name: str) -> str:
    """Hash the (mtime, function-name) tuple to a 16-hex-char cache key.

    16 hex chars (~64 bits) is enough to make collisions astronomically
    unlikely for the sizes we care about (a few hundred recordings per
    project) while keeping filenames short on Windows.
    """
    stat = recording_path.stat()
    payload = f"{recording_path.resolve()}|{stat.st_mtime_ns}|{fn_name}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return digest[:16]


class CachedBIDSPipeline:
    """Memoise per-recording pipeline output paths in a content-addressed cache.

    Constructed with a project ``root`` and an optional ``cache_dir``
    (defaults to ``root / ".cache" / "bids_pipeline"``). Cache entries
    live as ``<cache_dir>/<key>.json`` sidecars that point at the
    cached artefact path.
    """

    def __init__(self, root: Path, cache_dir: Path | None = None) -> None:
        self.root = Path(root)
        self.cache_dir = (
            Path(cache_dir)
            if cache_dir is not None
            else self.root / ".cache" / "bids_pipeline"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _sidecar_for(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def lookup(self, recording_path: Path, fn_name: str) -> Path | None:
        """Return the cached artefact for this recording+fn, or None."""
        key = _hash_key(recording_path, fn_name)
        sidecar = self._sidecar_for(key)
        if not sidecar.is_file():
            return None
        try:
            payload = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        artefact = Path(payload.get("artefact", ""))
        if not artefact.is_file():
            # Stale sidecar — drop it so the next run rebuilds cleanly.
            sidecar.unlink(missing_ok=True)
            return None
        return artefact

    def process(
        self,
        recording_path: Path,
        fn: Callable[[Path], Path],
    ) -> Path:
        """Return ``fn(recording_path)`` with content-addressed caching.

        The first call for a given ``(recording-mtime, fn.__name__)``
        runs ``fn`` and persists its returned :class:`Path` in the
        sidecar; subsequent calls return the cached path directly until
        either the recording's mtime changes or the artefact is deleted.

        ``fn`` MUST return an absolute :class:`Path` to the produced
        artefact. Anything else raises :class:`TypeError`.
        """
        fn_name = getattr(fn, "__name__", "anonymous")
        cached = self.lookup(recording_path, fn_name)
        if cached is not None:
            return cached

        artefact = fn(recording_path)
        if not isinstance(artefact, Path):
            raise TypeError(
                f"CachedBIDSPipeline expected fn to return Path, got {type(artefact)!r}"
            )

        key = _hash_key(recording_path, fn_name)
        sidecar = self._sidecar_for(key)
        sidecar.write_text(
            json.dumps(
                {
                    "key": key,
                    "fn": fn_name,
                    "recording": str(recording_path.resolve()),
                    "artefact": str(artefact.resolve()),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return artefact
