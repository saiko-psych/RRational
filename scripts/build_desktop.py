"""Build standalone desktop application for RRational.

Usage:
    uv run python scripts/build_desktop.py

This script uses streamlit-desktop-app + PyInstaller to create a
standalone executable that runs RRational in a native window.

The build process:
1. Bundles all Python dependencies (including NeuroKit2, SciPy, NumPy)
2. Collects all Streamlit web assets (HTML, JS, CSS)
3. Includes the rrational package with GUI assets
4. Creates a native window using pywebview (no browser needed)

Output: dist/RRational/ (directory) or dist/RRational.exe (onefile)
"""

import subprocess
import sys
from pathlib import Path

# Project root
ROOT = Path(__file__).parent.parent
APP_SCRIPT = ROOT / "src" / "rrational" / "gui" / "app.py"
ICON = ROOT / "src" / "rrational" / "gui" / "assets" / "favicon.ico"
NAME = "RRational"

# Data files to include (relative to project root)
DATA_FILES = [
    # GUI assets (favicon, CSS, etc.)
    ("src/rrational/gui/assets", "rrational/gui/assets"),
    # Demo data for test mode
    ("data/demo", "data/demo"),
    # Streamlit config
    (".streamlit", ".streamlit"),
]

# Hidden imports that PyInstaller can't auto-detect
HIDDEN_IMPORTS = [
    # NeuroKit2 internals
    "neurokit2",
    "neurokit2.hrv",
    "neurokit2.signal",
    # SciPy submodules used by HRV analysis
    "scipy.signal",
    "scipy.interpolate",
    "scipy.stats",
    "scipy.special",
    "scipy.special._cdflib",
    # Streamlit components
    "streamlit_plotly_events",
    "streamlit.runtime.scriptrunner",
    # Plotly
    "plotly",
    "plotly.graph_objects",
    "plotly.subplots",
    "plotly.express",
    # Data handling
    "yaml",
    "pandas",
    "numpy",
    # Our package
    "rrational",
    "rrational.gui",
    "rrational.gui.tabs",
    "rrational.gui.plots",
    "rrational.analysis",
    "rrational.cleaning",
    "rrational.io",
    "rrational.prep",
    "rrational.segments",
]

# Packages to collect all data files from
COLLECT_ALL = [
    "streamlit",
    "streamlit_plotly_events",
    "plotly",
    "pywebview",
]


def build():
    """Run the build."""
    print(f"Building {NAME} desktop app...")
    print(f"  Script: {APP_SCRIPT}")
    print(f"  Icon: {ICON}")
    print()

    # Build the command
    cmd = [
        sys.executable, "-m", "streamlit_desktop_app", "build",
        str(APP_SCRIPT),
        "--name", NAME,
    ]

    if ICON.exists():
        cmd.extend(["--icon", str(ICON)])

    # Add PyInstaller options
    cmd.append("--pyinstaller-options")

    # Hidden imports
    for imp in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", imp])

    # Collect all from packages
    for pkg in COLLECT_ALL:
        cmd.extend(["--collect-all", pkg])

    # Add data files
    for src, dst in DATA_FILES:
        src_path = ROOT / src
        if src_path.exists():
            cmd.extend(["--add-data", f"{src_path}{os.pathsep}{dst}"])

    # Don't confirm overwrite
    cmd.append("--noconfirm")

    print("Command:")
    print(" ".join(cmd[:10]) + " ...")
    print()

    # Run PyInstaller
    result = subprocess.run(cmd, cwd=str(ROOT))

    if result.returncode == 0:
        dist_dir = ROOT / "dist" / NAME
        if dist_dir.exists():
            print(f"\nBuild successful! Output: {dist_dir}")
            # List contents
            exe_files = list(dist_dir.glob("*.exe")) + list(dist_dir.glob(NAME))
            for f in exe_files:
                size_mb = f.stat().st_size / (1024 * 1024)
                print(f"  {f.name}: {size_mb:.1f} MB")
        else:
            print(f"\nBuild may have succeeded. Check dist/ directory.")
    else:
        print(f"\nBuild failed with exit code {result.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    import os
    build()
