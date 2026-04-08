"""Take documentation screenshots of the RRational GUI using Playwright.

Uses Streamlit-specific wait strategies:
- Wait for "Running..." indicator to disappear
- Wait for specific elements (canvas, tables) to render
- Element-specific screenshots for clarity

Usage:
    # Start the app first:
    uv run streamlit run src/rrational/gui/app.py --server.headless true -- --test-mode
    # Then take screenshots:
    uv run python scripts/take_screenshots.py
"""

from pathlib import Path
from playwright.sync_api import sync_playwright, Page, expect

BASE_URL = "http://localhost:8501"
OUT = Path("docs/assets/screenshots")
W, H = 1400, 900


def wait_streamlit(page: Page, timeout: int = 15000):
    """Wait for Streamlit to finish processing."""
    try:
        running = page.get_by_text("Running...")
        running.wait_for(state="detached", timeout=timeout)
    except Exception:
        pass  # May not appear if already loaded
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1500)


def click_nav(page: Page, label: str):
    """Click a sidebar navigation button."""
    page.locator(f"[data-testid='stSidebar'] button:has-text('{label}')").first.click()
    wait_streamlit(page)


def click_radio(page: Page, label: str):
    """Click a Streamlit radio option."""
    page.locator(f"label:has-text('{label}')").first.click()
    wait_streamlit(page)


def screenshot(page: Page, name: str, full_page: bool = False):
    """Take and save a screenshot."""
    path = OUT / name
    page.screenshot(path=str(path), full_page=full_page)
    size_kb = path.stat().st_size // 1024
    print(f"  [{size_kb:>4}KB] {name}")


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": W, "height": H})
        page = ctx.new_page()

        # ── 1. DATA TAB ──────────────────────────────────
        print("1. Data Tab")
        page.goto(BASE_URL)
        wait_streamlit(page, timeout=20000)

        # Wait for the participant table to render
        try:
            page.locator("table").first.wait_for(state="visible", timeout=10000)
        except Exception:
            pass
        page.wait_for_timeout(1000)
        screenshot(page, "data-tab-loaded.png")

        # Scroll to participants table
        page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.4)")
        page.wait_for_timeout(1000)
        screenshot(page, "participants-overview.png")

        # ── 2. PARTICIPANTS TAB ───────────────────────────
        print("2. Participants Tab")
        click_nav(page, "Participants")

        # Wait for the participant header/metrics to render
        try:
            page.get_by_text("Total Beats").wait_for(state="visible", timeout=10000)
        except Exception:
            pass
        screenshot(page, "participants-header.png")

        # Scroll down to where tachogram + plot options are
        page.evaluate("window.scrollTo(0, 400)")
        page.wait_for_timeout(1000)

        # Wait for canvas (Plotly chart) to render
        try:
            page.locator("canvas").first.wait_for(state="visible", timeout=10000)
            page.wait_for_timeout(2000)  # Extra for WebGL
        except Exception:
            pass
        screenshot(page, "participants-tachogram.png")

        # Scroll to plot options checkboxes
        page.evaluate("window.scrollTo(0, 600)")
        page.wait_for_timeout(1000)
        screenshot(page, "plot-options.png")

        # Scroll to bottom - events area / section validation
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1500)
        screenshot(page, "events-area.png")

        # ── 3. SETUP TAB ─────────────────────────────────
        print("3. Setup Tab")
        click_nav(page, "Setup")
        screenshot(page, "setup-events.png")

        # Click Sequences radio
        try:
            click_radio(page, "Sequences")
            # Scroll to show condition labels table
            page.evaluate("window.scrollTo(0, 300)")
            page.wait_for_timeout(500)
            screenshot(page, "setup-sequences.png")

            # Scroll further to Condition Labels section
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(500)
            screenshot(page, "setup-condition-labels.png")
        except Exception as e:
            print(f"  ! Sequences: {e}")

        # Click Sections radio
        try:
            # Scroll back to top first so the radio is visible
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(500)
            click_radio(page, "Sections")
            screenshot(page, "setup-sections.png")
        except Exception as e:
            print(f"  ! Sections: {e}")

        # ── 4. ANALYSIS TAB ──────────────────────────────
        print("4. Analysis Tab")
        click_nav(page, "Analysis")
        screenshot(page, "analysis-mode.png")

        # Click "Repeating Section Analysis" radio
        try:
            click_radio(page, "Repeating Section Analysis")
            screenshot(page, "analysis-repeating.png")
        except Exception as e:
            print(f"  ! Repeating: {e}")

        # ── 5. SIDEBAR ───────────────────────────────────
        print("5. Sidebar")
        sidebar = page.locator("[data-testid='stSidebar']")
        if sidebar.count() > 0:
            # Scroll sidebar to bottom to show version + buttons
            sidebar.evaluate("el => el.scrollTo(0, el.scrollHeight)")
            page.wait_for_timeout(800)
            screenshot(page, "sidebar-bottom.png")

            # Take sidebar-only screenshot
            try:
                sidebar.screenshot(path=str(OUT / "sidebar-only.png"))
                print(f"  [{(OUT / 'sidebar-only.png').stat().st_size // 1024:>4}KB] sidebar-only.png")
            except Exception as e:
                print(f"  ! Sidebar element: {e}")

        browser.close()

    # Summary
    pngs = sorted(OUT.glob("*.png"))
    print(f"\nDone! {len(pngs)} screenshots in {OUT}/")
    for p in pngs:
        print(f"  {p.name}")


if __name__ == "__main__":
    main()
