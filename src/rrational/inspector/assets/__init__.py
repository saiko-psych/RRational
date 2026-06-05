"""Static assets for the RRational Inspector (app icon, etc.).

Loaders go here so callers don't have to know the on-disk layout —
ship as a package + use ``importlib.resources``-friendly Paths so the
PyInstaller bundle can find them too.
"""

from __future__ import annotations

from pathlib import Path

from qtpy.QtGui import QIcon

_ASSETS_DIR = Path(__file__).resolve().parent

# Ordered largest-first so QIcon.addFile picks the highest-fidelity
# source when Qt asks for an intermediate size (e.g. 96 px on HiDPI).
_PNG_SIZES = (256, 128, 64, 48, 32, 16)


def app_icon() -> QIcon:
    """Return the multi-resolution app icon as a ``QIcon``.

    On Windows we also feed the ``.ico`` so Explorer thumbnails / the
    taskbar pin use the embedded LZ77 sizes rather than rescaling a
    single PNG. On Linux/macOS the per-size PNGs are what Qt expects.
    """
    icon = QIcon()
    for size in _PNG_SIZES:
        png = _ASSETS_DIR / f"icon_{size}.png"
        if png.exists():
            icon.addFile(
                str(png),
            )
    ico = _ASSETS_DIR / "icon.ico"
    if ico.exists():
        icon.addFile(str(ico))
    return icon
