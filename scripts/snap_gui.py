"""Launch the Flet app and capture a screenshot via Playwright.

This is a helper for CI/manual debugging when we need a headless view of the
GUI. It expects Playwright with Chromium installed. If Playwright is missing,
the script prints instructions and exits.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


def ensure_playwright() -> None:
    try:
        import playwright  # type: ignore  # noqa: F401
    except ImportError:  # pragma: no cover - helper path
        print("Playwright is not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)


def main() -> None:
    ensure_playwright()

    from playwright.sync_api import sync_playwright  # type: ignore

    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.setdefault("FLET_FORCE_WEB_SERVER", "1")
    env.setdefault("FLET_SERVER_PORT", "8550")

    app_proc = subprocess.Popen(
        [sys.executable, "-m", "src.music_hrv.gui.app"],
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    try:
        time.sleep(2)
        url = f"http://127.0.0.1:{env['FLET_SERVER_PORT']}/music-hrv"
        out_dir = root / "artifacts"
        out_dir.mkdir(exist_ok=True)
        out_path = out_dir / "gui.png"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.goto(url, wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(1500)
            page.screenshot(path=str(out_path), full_page=True)
            browser.close()

        print(f"Saved screenshot to {out_path}")
    finally:
        app_proc.terminate()
        try:
            app_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            app_proc.kill()


if __name__ == "__main__":  # pragma: no cover
    main()
