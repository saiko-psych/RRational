"""Rasterize the RRational Inspector SVG icon into PNGs and a .ico bundle.

Re-run this script whenever ``src/rrational/inspector/assets/icon.svg``
changes. It produces:

  - ``icon_{16,32,48,64,128,256}.png`` — PNG sizes Qt picks from for
    QIcon scaling on Linux/macOS taskbars.
  - ``icon.ico`` — multi-resolution Windows ICO bundle (used by
    PyInstaller's ``--icon`` flag and Explorer thumbnails).

Uses Qt's QSvgRenderer for rasterization (project already depends on Qt
via the ``inspector`` extra) and Pillow for the ICO container.

Usage::

    python scripts/build_inspector_icon.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Force headless QPA so the script works in CI / over SSH without a display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402  -- after env var
from qtpy.QtCore import QByteArray, Qt  # noqa: E402
from qtpy.QtGui import QImage, QPainter  # noqa: E402
from qtpy.QtSvg import QSvgRenderer  # noqa: E402
from qtpy.QtWidgets import QApplication  # noqa: E402

SIZES = (16, 32, 48, 64, 128, 256)


def main() -> int:
    # QApplication is required even for offscreen image painting on some
    # Qt builds (font db init lives behind it).
    QApplication.instance() or QApplication(sys.argv)

    assets = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "rrational"
        / "inspector"
        / "assets"
    )
    svg_path = assets / "icon.svg"
    if not svg_path.exists():
        print(f"ERROR: {svg_path} not found", file=sys.stderr)
        return 1

    renderer = QSvgRenderer(QByteArray(svg_path.read_bytes()))
    if not renderer.isValid():
        print(f"ERROR: {svg_path} did not parse as SVG", file=sys.stderr)
        return 1

    for size in SIZES:
        img = QImage(size, size, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        renderer.render(painter)
        painter.end()
        out_png = assets / f"icon_{size}.png"
        if not img.save(str(out_png), "PNG"):
            print(f"ERROR: failed to write {out_png}", file=sys.stderr)
            return 1
        print(f"Wrote {out_png}")

    # Pillow builds the multi-resolution ICO from the 256px master so the
    # ICO contains crisp downscales for every Windows taskbar size.
    master = Image.open(assets / "icon_256.png").convert("RGBA")
    ico_path = assets / "icon.ico"
    master.save(
        str(ico_path),
        format="ICO",
        sizes=[(s, s) for s in SIZES],
    )
    print(f"Wrote {ico_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
