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
    # Round 33 (S1) — atomic write (tmp + replace + retry), matching the R30
    # standard. A crash mid-write previously left a zero-byte color_scheme.yml
    # and load silently fell back to "Scientific", losing the user's scheme.
    import os
    import time

    body = yaml.safe_dump(payload, default_flow_style=False, allow_unicode=True)
    tmp = target.with_suffix(f"{target.suffix}.{os.getpid()}.{time.time_ns()}.tmp")
    tmp.write_text(body, encoding="utf-8")
    last_exc: BaseException | None = None
    for attempt in range(5):
        try:
            tmp.replace(target)
            return target
        except PermissionError as exc:
            last_exc = exc
            time.sleep(0.02 * (2**attempt))
    if last_exc is not None:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise last_exc
    return target


def load_color_scheme() -> tuple[str, ColorScheme]:
    """Return the persisted ``(preset_name, ColorScheme)`` pair.

    Falls back to ("Scientific", ColorScheme()) on:
    - missing file
    - unreadable / malformed YAML
    - unknown preset name with no usable ``custom_scheme`` payload

    Cluster A5 — when the ``colorblind_safe_palette`` QSetting is True,
    the returned scheme has its ``group_palette`` overwritten with the
    Okabe-Ito 8-colour palette regardless of preset choice. The preset
    name is preserved so the Preferences dialog still shows the user's
    chosen base preset.
    """
    default = (DEFAULT_PRESET_NAME, PRESET_THEMES[DEFAULT_PRESET_NAME])
    path = _color_scheme_path()
    if not path.exists():
        return _apply_colorblind_overlay(*default)
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return _apply_colorblind_overlay(*default)
    if not isinstance(raw, dict):
        return _apply_colorblind_overlay(*default)

    preset_name = raw.get("preset_name") or DEFAULT_PRESET_NAME
    custom = raw.get("custom_scheme")

    if preset_name in PRESET_THEMES:
        return _apply_colorblind_overlay(preset_name, PRESET_THEMES[preset_name])
    if isinstance(custom, dict):
        try:
            return _apply_colorblind_overlay(
                CUSTOM_PRESET_NAME, ColorScheme.from_dict(custom)
            )
        except (TypeError, ValueError, KeyError):
            return _apply_colorblind_overlay(*default)
    return _apply_colorblind_overlay(*default)


def _apply_colorblind_overlay(
    preset_name: str, scheme: ColorScheme
) -> tuple[str, ColorScheme]:
    """If the global colorblind-safe flag is on, swap to Okabe-Ito palette.

    Reading QSettings here keeps the policy in one place — every caller
    of ``load_color_scheme`` gets the overlay applied. Import is local
    so this module does not pull in inspector.settings (and transitively
    qtpy) when used from non-Qt contexts like CLI tooling.
    """
    try:
        from rrational.inspector.palette import OKABE_ITO
        from rrational.inspector.settings import read_setting

        if read_setting("colorblind_safe_palette"):
            # Deep-copy so we don't mutate the PRESET_THEMES dict in place.
            patched = ColorScheme.from_dict(scheme.to_dict())
            patched.group_palette = list(OKABE_ITO)
            return preset_name, patched
    except (ImportError, KeyError, RuntimeError):  # pragma: no cover - defensive
        pass
    return preset_name, scheme
