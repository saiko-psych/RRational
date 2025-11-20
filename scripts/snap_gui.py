"""Launch the Flet app and capture GUI screenshots via Playwright.

- Navigates to the data prep tab.
- Scans the default data folder (data/raw/hrv_logger) if present.
- Captures a screenshot of the data prep tab and (if possible) after selecting
  the first participant.

Requires Playwright + Chromium (`uv run python -m playwright install chromium`).
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

    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError  # type: ignore

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
        out_main = out_dir / "gui-home.png"
        out_data = out_dir / "gui-data-prep.png"
        out_events = out_dir / "gui-events.png"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)
            page.screenshot(path=str(out_main), full_page=True)

            # Switch to data prep tab
            try:
                page.get_by_role("tab", name=page.compile_selector("data prep", re_ignore_case=True)).first.click(
                    timeout=8000
                )
            except PWTimeoutError:
                try:
                    page.get_by_text("data prep", exact=False).first.click(timeout=8000)
                except PWTimeoutError:
                    page.wait_for_timeout(2000)

            # If folder path field exists, fill and scan
            folder_field = page.get_by_label("Folder path")
            if folder_field.count() > 0:
                folder_field.fill("data/raw/hrv_logger")
                page.get_by_role("button", name="Scan folder").click(timeout=5000)
                page.wait_for_timeout(4000)

            page.screenshot(path=str(out_data), full_page=True)

            # Try selecting first participant row to open events table
            rows = page.locator("div").filter(has_text="Participant")
            if rows.count() > 1:
                page.locator("div").filter(has_text="Participant").nth(1).click()
                page.wait_for_timeout(1000)
                page.screenshot(path=str(out_events), full_page=True)

            browser.close()

        print(f"Saved screenshots: {out_main}, {out_data}, {out_events}")
    finally:
        app_proc.terminate()
        try:
            app_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            app_proc.kill()


if __name__ == "__main__":  # pragma: no cover
    main()
