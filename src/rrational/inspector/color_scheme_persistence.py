"""YAML-backed persistence for the inspector's active color scheme.

Color preferences are USER-LEVEL, not per-project: the same user wants
their picked theme to follow them across every project on the machine.
So unlike ``persistence.py`` / ``results_persistence.py`` this module
deliberately ignores the active-project hook and always reads/writes
under ``~/.rrational/inspector/color_scheme.yml`` (with a test override).

On-disk schema::

    preset_name: Scientific
    custom_scheme: null

or, when the user has edited a swatch::

    preset_name: Custom
    custom_scheme:
      rr_line: "#123456"
      artifact: "#abcdef"
      ...

``custom_scheme`` is the literal output of ``ColorScheme.to_dict()``.
Loaders are defensive: a missing file, garbled YAML, or an unknown
preset all return the built-in default ("Scientific" + ColorScheme()).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from rrational.gui.color_scheme import PRESET_THEMES, ColorScheme

CUSTOM_PRESET_NAME = "Custom"
DEFAULT_PRESET_NAME = "Scientific"
COLOR_SCHEME_FILENAME = "color_scheme.yml"

_DEFAULT_DIR = Path.home() / ".rrational" / "inspector"
_config_dir_override: Path | None = None


def set_color_scheme_config_dir(path: Path | None) -> None:
    """Redirect persistence reads/writes to ``path`` (None = default).

    Test-only override — color preferences are never per-project, so we
    don't honour the project-config hook used by ``persistence.py``.
    """
    global _config_dir_override
    _config_dir_override = path


def _config_dir() -> Path:
    base = _config_dir_override or _DEFAULT_DIR
    base.mkdir(parents=True, exist_ok=True)
    return base


def _color_scheme_path() -> Path:
    return _config_dir() / COLOR_SCHEME_FILENAME


def save_color_scheme(preset_name: str, scheme: ColorScheme) -> Path:
    """Persist the active ``(preset_name, scheme)`` pair.

    When ``preset_name`` is the name of a known preset, only the name
    is written — the dict is omitted so on-disk drift in the preset
    definitions is automatically picked up next launch.
    When ``preset_name`` is "Custom" (or anything not in PRESET_THEMES),
    the scheme dict is written too so the user's pickings round-trip.
    """
    if preset_name in PRESET_THEMES:
        payload = {"preset_name": preset_name, "custom_scheme": None}
    else:
        payload = {
            "preset_name": CUSTOM_PRESET_NAME,
            "custom_scheme": scheme.to_dict(),
        }
    target = _color_scheme_path()
    with target.open("w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, default_flow_style=False, allow_unicode=True)
    return target


def load_color_scheme() -> tuple[str, ColorScheme]:
    """Return the persisted ``(preset_name, ColorScheme)`` pair.

    Falls back to ("Scientific", ColorScheme()) on:
    - missing file
    - unreadable / malformed YAML
    - unknown preset name with no usable ``custom_scheme`` payload
    """
    default = (DEFAULT_PRESET_NAME, PRESET_THEMES[DEFAULT_PRESET_NAME])
    path = _color_scheme_path()
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return default
    if not isinstance(raw, dict):
        return default

    preset_name = raw.get("preset_name") or DEFAULT_PRESET_NAME
    custom = raw.get("custom_scheme")

    if preset_name in PRESET_THEMES:
        return preset_name, PRESET_THEMES[preset_name]
    if isinstance(custom, dict):
        try:
            return CUSTOM_PRESET_NAME, ColorScheme.from_dict(custom)
        except (TypeError, ValueError, KeyError):
            return default
    return default
