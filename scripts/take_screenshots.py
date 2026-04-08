"""Take documentation screenshots of the RRational GUI using Playwright.

Usage:
    uv run python scripts/take_screenshots.py

Requires:
    uv pip install playwright
    uv run playwright install chromium
"""

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

BASE_URL = "http://localhost:8501"
OUTPUT_DIR = Path("docs/assets/screenshots")
VIEWPORT = {"width": 1400, "height": 900}


async def wait_for_streamlit(page, extra_ms=3000):
    """Wait for Streamlit to fully render."""
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(extra_ms)


async def click_sidebar_button(page, text):
    """Click a sidebar navigation button by its text."""
    sidebar = page.locator("[data-testid='stSidebar']")
    btn = sidebar.locator(f"button:has-text('{text}')").first
    await btn.click()
    await wait_for_streamlit(page)


async def click_radio_option(page, text):
    """Click a Streamlit radio option by label text."""
    # Streamlit renders radio labels as <p> inside a label container
    label = page.locator(f"text='{text}'").first
    await label.click()
    await wait_for_streamlit(page)


async def take_screenshots():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport=VIEWPORT)
        page = await context.new_page()

        # === 1. Data Tab (initial load in test mode) ===
        print("1. Data tab...")
        await page.goto(BASE_URL)
        await wait_for_streamlit(page, 5000)  # Extra time for first load
        await page.screenshot(path=str(OUTPUT_DIR / "data-tab-loaded.png"))
        print("   -> data-tab-loaded.png")

        # === 2. Participants Tab ===
        print("2. Participants tab...")
        await click_sidebar_button(page, "Participants")
        await page.screenshot(path=str(OUTPUT_DIR / "participants-tachogram.png"))
        print("   -> participants-tachogram.png")

        # Scroll to plot options and tachogram
        await page.evaluate("window.scrollTo(0, 500)")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(OUTPUT_DIR / "plot-options.png"))
        print("   -> plot-options.png")

        # Scroll to bottom area (events, validation)
        await page.evaluate("window.scrollTo(0, 2000)")
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(OUTPUT_DIR / "signal-inspection-area.png"))
        print("   -> signal-inspection-area.png")

        # === 3. Setup Tab - Events ===
        print("3. Setup tab...")
        await click_sidebar_button(page, "Setup")
        await page.screenshot(path=str(OUTPUT_DIR / "setup-events.png"))
        print("   -> setup-events.png")

        # Click Sequences radio option
        try:
            await click_radio_option(page, "Sequences")
            await page.screenshot(path=str(OUTPUT_DIR / "setup-sequences.png"))
            print("   -> setup-sequences.png")
        except Exception as e:
            print(f"   ! Sequences failed: {e}")

        # Click Sections radio option
        try:
            await click_radio_option(page, "Sections")
            await page.screenshot(path=str(OUTPUT_DIR / "setup-sections.png"))
            print("   -> setup-sections.png")
        except Exception as e:
            print(f"   ! Sections failed: {e}")

        # === 4. Analysis Tab ===
        print("4. Analysis tab...")
        await click_sidebar_button(page, "Analysis")
        await page.screenshot(path=str(OUTPUT_DIR / "analysis-mode.png"))
        print("   -> analysis-mode.png")

        # === 5. Sidebar bottom (version, bug report, docs buttons) ===
        print("5. Sidebar...")
        sidebar = page.locator("[data-testid='stSidebar']")
        if await sidebar.count() > 0:
            # Scroll sidebar to show version + link buttons
            await sidebar.evaluate("el => el.scrollTo(0, el.scrollHeight)")
            await page.wait_for_timeout(1000)
            await page.screenshot(path=str(OUTPUT_DIR / "sidebar-bottom.png"))
            print("   -> sidebar-bottom.png")

        await browser.close()

    screenshots = list(OUTPUT_DIR.glob("*.png"))
    print(f"\nDone! {len(screenshots)} screenshots in {OUTPUT_DIR}/")
    for s in sorted(screenshots):
        print(f"  {s.name} ({s.stat().st_size // 1024}KB)")


if __name__ == "__main__":
    asyncio.run(take_screenshots())
