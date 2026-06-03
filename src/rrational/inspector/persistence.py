"""YAML-backed persistence for inspector-specific definitions.

QSettings is the right tool for scalar preferences (window geometry,
last-dir, recent-files); it falls over once you need nested structures
like "a list of named sequences, each with an ordered list of section
names." For those we use a YAML file so the format is hand-editable
and trivially diffable.

Resolution order for the storage directory:

1. ``set_inspector_config_dir(path)`` override (used by tests)
2. ``set_active_project_config_dir(path)`` — points at the active
   project's ``config/`` directory, so the inspector's sequences live
   alongside the rest of the project state on disk
3. Default fallback: ``~/.rrational/inspector/``

A sequence is just::

    sequences:
      - name: "Pre-Music-Post"
        sections: [rest_pre, music_block_1, rest_post]
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_DEFAULT_CONFIG_DIR = Path.home() / ".rrational" / "inspector"
_config_dir_override: Path | None = None
_project_config_dir: Path | None = None


@dataclass
class Sequence:
    """An ordered chain of section names."""

    name: str
    sections: list[str]

    def to_dict(self) -> dict:
        return {"name": self.name, "sections": list(self.sections)}

    @classmethod
    def from_dict(cls, d: dict) -> "Sequence":
        return cls(
            name=str(d["name"]), sections=[str(s) for s in d.get("sections", [])]
        )


def set_inspector_config_dir(path: Path | None) -> None:
    """Redirect persistence reads/writes to ``path`` (None = default).

    Test override — wins over the project scope.
    """
    global _config_dir_override
    _config_dir_override = path


def set_active_project_config_dir(path: Path | None) -> None:
    """Point the persistence layer at a project's ``config/`` directory.

    Called by MainWindow when the user opens / closes a project.
    ``None`` reverts to the global fallback.
    """
    global _project_config_dir
    _project_config_dir = path


def _config_dir() -> Path:
    base = _config_dir_override or _project_config_dir or _DEFAULT_CONFIG_DIR
    base.mkdir(parents=True, exist_ok=True)
    return base


def _sequences_path() -> Path:
    return _config_dir() / "sequences.yml"


def load_sequences() -> list[Sequence]:
    """Return all stored sequences (empty list if file missing or unreadable)."""
    p = _sequences_path()
    if not p.exists():
        return []
    try:
        with p.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return []
    items = raw.get("sequences", []) or []
    out: list[Sequence] = []
    for entry in items:
        try:
            seq = Sequence.from_dict(entry)
        except (KeyError, TypeError):
            continue
        # Defensive: drop empty-name or empty-sections entries
        if seq.name and seq.sections:
            out.append(seq)
    return out


def save_sequences(sequences: list[Sequence]) -> None:
    """Overwrite the on-disk sequence list."""
    p = _sequences_path()
    payload = {"sequences": [s.to_dict() for s in sequences]}
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, default_flow_style=False, allow_unicode=True)
