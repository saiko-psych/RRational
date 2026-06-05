"""Persistent inspector settings via QSettings.

Pattern borrowed from mnelab's ``settings.py``: a ``_DEFAULTS`` dict
declares both the default value AND implies the type — QSettings
serialises everything to platform-native storage (Windows registry,
macOS ``plist``, Linux INI) so the user's preferences survive across
runs.

We expose a thin façade (``read_settings`` / ``write_settings``)
rather than letting the rest of the app touch ``QSettings`` directly.
That keeps Qt-specific imports in one place and makes the whole thing
mockable in tests (``test_mode`` sets ``IniFormat`` in a temp dir).
"""

from __future__ import annotations

import json
from pathlib import Path

from qtpy.QtCore import QByteArray, QSettings

# ----------------------------------------------------------------------
# Default values. Adding a key here is the ONLY place you need to touch
# to introduce a new persistent preference — readers will automatically
# fall back to the default if the user hasn't set it.
# ----------------------------------------------------------------------
_DEFAULTS: dict[str, object] = {
    "recent_files": [],  # list[str] — most-recent first
    "max_recent": 10,
    "last_dir": "",  # str — last directory used in Open dialog
    "geometry": None,  # QByteArray — main window geometry
    "window_state": None,  # QByteArray — dock/toolbar state
    "show_sidebar": True,
    "show_overview_bar": True,  # Phase 3c will use this
    "show_events": True,
    "show_sections": True,
    "show_grid": True,
    "show_crosshair": True,  # Phase 3d will use this
    # Phase 20: dockable BrowseTab layout
    "show_datasets_dock": True,
    "show_preprocessing_dock": True,
    "browse_dock_state": None,  # QByteArray — saveState() of BrowseTab's QMainWindow
    # Phase 22.3: top-level layout mode.
    # "streamlit" — Data / Participant / Setup / Analysis / Results tabs (Browse hidden)
    # "mnelab"    — Browse / Setup / Participants / Analysis / Results (dock-heavy)
    "ui_layout": "streamlit",
    # Phase 23A: per-user RR cleaning thresholds surfaced on the Data tab.
    # Defaults match what the Streamlit prep wizard shows by default.
    "cleaning_min_rr_ms": 300,
    "cleaning_max_rr_ms": 2000,
    "cleaning_sudden_change_pct": 20,
    # Phase 24B: participant ID regex used when extracting an ID from
    # raw-file stems. Default mirrors ``rrational.io.DEFAULT_ID_PATTERN``.
    "participant_id_pattern": r"(?P<participant>\d{4}[A-Z]{4})",
}


def _qsettings() -> QSettings:
    """Construct a QSettings handle.

    QApplication's ``organizationName`` + ``applicationName`` (set in
    ``app.py``) determine the storage path — we just trust they're set.
    """
    return QSettings()


def read_setting(key: str):
    """Return the stored value for ``key``, or the registered default."""
    if key not in _DEFAULTS:
        raise KeyError(f"unknown inspector setting: {key!r}")
    default = _DEFAULTS[key]
    settings = _qsettings()
    raw = settings.value(key, default)

    # QSettings has no idea about list[str] — it stores them as a
    # ``QStringList`` which round-trips fine on Linux but comes back as
    # a single str on Windows when the list has length 1. We normalise.
    if isinstance(default, list):
        if raw is None or raw == "":
            return []
        if isinstance(raw, str):
            return [raw]
        return list(raw)

    if isinstance(default, bool):
        # QSettings stringifies bools on some platforms ("true"/"false").
        if isinstance(raw, str):
            return raw.lower() == "true"
        return bool(raw)

    return raw


def write_setting(key: str, value) -> None:
    """Persist a setting. ``None`` removes the key (resets to default)."""
    if key not in _DEFAULTS:
        raise KeyError(f"unknown inspector setting: {key!r}")
    settings = _qsettings()
    if value is None:
        settings.remove(key)
    else:
        settings.setValue(key, value)
    settings.sync()


# ----------------------------------------------------------------------
# Recent-files convenience API. Same contract as mnelab:
# - newest entry always at index 0
# - dead paths (file removed since last run) silently dropped on read
# - capped at ``max_recent``
# ----------------------------------------------------------------------
def get_recent_files() -> list[Path]:
    """Return existing recent paths, newest first; purges dead entries."""
    raw = read_setting("recent_files")
    paths: list[Path] = []
    for entry in raw:
        p = Path(entry)
        if p.exists():
            paths.append(p)
    # Persist the purge so the user's dead entries don't keep coming
    # back next session.
    if len(paths) != len(raw):
        write_setting("recent_files", [str(p) for p in paths])
    return paths


def add_recent_file(path: Path) -> None:
    """Bump ``path`` to the top of the recent-files list."""
    existing = [str(p) for p in get_recent_files()]
    path_str = str(path.resolve())
    if path_str in existing:
        existing.remove(path_str)
    existing.insert(0, path_str)
    write_setting("recent_files", existing[: read_setting("max_recent")])


def clear_recent_files() -> None:
    write_setting("recent_files", [])


# ----------------------------------------------------------------------
# Window state — QByteArray round-trips through QSettings natively.
# We just type-hint it for the call sites.
# ----------------------------------------------------------------------
def save_window_state(geometry: QByteArray, state: QByteArray) -> None:
    write_setting("geometry", geometry)
    write_setting("window_state", state)


# ----------------------------------------------------------------------
# Test mode: redirect settings to a throwaway in-memory store. Tests
# call this from a fixture so they never touch the user's real
# preferences.
# ----------------------------------------------------------------------
def enable_test_mode(tmp_dir: Path) -> None:
    """Redirect QSettings to an INI file under ``tmp_dir``.

    Must be called BEFORE any ``read_setting`` / ``write_setting`` call
    in the test — otherwise the first call materialises the user's real
    QSettings in the default registry/plist location.
    """
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(
        QSettings.IniFormat,
        QSettings.UserScope,
        str(tmp_dir),
    )


# ----------------------------------------------------------------------
# JSON dump/restore — useful for "Reset settings" UI or for printing
# the current config in bug reports. Not invoked yet; will be wired
# into the Settings dialog (Phase 3b).
# ----------------------------------------------------------------------
def dump_settings_json() -> str:
    """Return the current settings as pretty-printed JSON."""
    out: dict = {}
    for key in _DEFAULTS:
        value = read_setting(key)
        if isinstance(value, QByteArray):
            value = "<binary>"
        elif isinstance(value, Path):
            value = str(value)
        out[key] = value
    return json.dumps(out, indent=2, default=str)
