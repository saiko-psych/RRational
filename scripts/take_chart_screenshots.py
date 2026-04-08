"""Take tachogram + artifact detection screenshots.

Uses JavaScript Element.scrollIntoView() which works through Streamlit's
nested scroll containers, unlike window.scrollTo().
"""

from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8501"
OUT = Path("docs/assets/screenshots")
W, H = 1400, 900


def wait_st(page, ms=2000):
    try:
        page.get_by_text("Running...").wait_for(state="detached", timeout=15000)
    except Exception:
        pass
    page.wait_for_timeout(ms)


def save(page, name):
    path = OUT / name
    page.screenshot(path=str(path))
    kb = path.stat().st_size // 1024
    print(f"  [{kb:>4}KB] {name}")


def js_scroll_to_text(page, text, offset=0):
    """Scroll any element containing text into view via JavaScript."""
    page.evaluate(f"""() => {{
        const walker = document.createTreeWalker(
            document.body, NodeFilter.SHOW_TEXT, null, false
        );
        while (walker.nextNode()) {{
            if (walker.currentNode.textContent.includes('{text}')) {{
                const el = walker.currentNode.parentElement;
                el.scrollIntoView({{block: 'start', behavior: 'instant'}});
                // Apply offset by scrolling parent
                const scrollable = el.closest('[data-testid="stMain"]') || window;
                if (scrollable.scrollBy) scrollable.scrollBy(0, {offset});
                else window.scrollBy(0, {offset});
                break;
            }}
        }}
    }}""")
    page.wait_for_timeout(1000)


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--enable-webgl", "--use-gl=swiftshader"],
        )
        ctx = browser.new_context(viewport={"width": W, "height": H})
        page = ctx.new_page()

        # ── Load app & go to Participants ──
        print("1. Loading...")
        page.goto(BASE_URL)
        wait_st(page, 5000)
        page.locator("[data-testid='stSidebar'] button:has-text('Participants')").first.click()
        wait_st(page, 3000)

        # ── Find the tachogram title and scroll to it ──
        print("2. Finding tachogram...")

        # The chart title is "RR Interval Visualization" inside the main content area
        found_chart = page.evaluate("""() => {
            // Search ONLY in stMain to avoid matching sidebar text
            const main = document.querySelector('[data-testid="stMain"]');
            if (!main) return {found: false, error: 'no stMain'};

            const headings = [...main.querySelectorAll('h1, h2, h3, h4, h5, h6')];
            const chartHeading = headings.find(h =>
                h.textContent.includes('RR Interval Visualization') ||
                h.textContent.includes('Tachogram')
            );
            if (chartHeading) {
                chartHeading.scrollIntoView({block: 'start', behavior: 'instant'});
                return {found: true, text: chartHeading.textContent.substring(0, 50)};
            }
            return {found: false, headingsFound: headings.map(h => h.textContent.substring(0, 30))};
        }""")
        print(f"   Chart heading: {found_chart}")

        if found_chart.get("found"):
            # Scroll down a bit more so chart is fully visible (title + plot)
            page.evaluate("""() => {
                const main = document.querySelector('[data-testid="stMain"]');
                if (main) main.scrollBy(0, 350);
            }""")
            page.wait_for_timeout(4000)  # Wait for WebGL render after scroll
            save(page, "tachogram.png")

            # Now scroll up slightly to show plot options + chart
            page.evaluate("""() => {
                const main = document.querySelector('[data-testid="stMain"]');
                if (!main) return;
                const texts = [...main.querySelectorAll('p, div, span, label')];
                const plotOpt = texts.find(t => t.textContent.includes('Plot Options'));
                if (plotOpt) {
                    plotOpt.scrollIntoView({block: 'start', behavior: 'instant'});
                }
            }""")
            page.wait_for_timeout(2000)
            save(page, "plot-options-with-chart.png")
        else:
            print("   ! No chart heading found, trying canvas directly...")
            # Fallback: scroll to canvas element
            page.evaluate("""() => {
                const canvas = document.querySelector('canvas');
                if (canvas) canvas.scrollIntoView({block: 'center', behavior: 'instant'});
            }""")
            page.wait_for_timeout(3000)
            save(page, "tachogram.png")

        # ── Artifact Detection ──
        print("3. Artifact detection...")

        # Find and click the expander via JavaScript - search only in main content
        clicked = page.evaluate("""() => {
            const main = document.querySelector('[data-testid="stMain"]');
            if (!main) return {clicked: false, error: 'no stMain'};

            // Streamlit expanders: look for the summary/toggle element
            const allElements = main.querySelectorAll('p, span, summary, details');
            for (const el of allElements) {
                const text = el.textContent.trim();
                if (text === 'Detect New Artifacts' || text.startsWith('Detect New Artifacts')) {
                    el.scrollIntoView({block: 'center', behavior: 'instant'});
                    el.click();
                    return {clicked: true, tag: el.tagName, text: text.substring(0, 40)};
                }
            }
            return {clicked: false};
        }""")
        print(f"   Expander click: {clicked}")
        wait_st(page, 2000)

        if clicked.get("clicked"):
            save(page, "artifact-detection-settings.png")

            # Try to click Run Detection via JavaScript - in main content only
            run_clicked = page.evaluate("""() => {
                const main = document.querySelector('[data-testid="stMain"]');
                if (!main) return false;
                const buttons = main.querySelectorAll('button');
                for (const btn of buttons) {
                    if (btn.textContent.includes('Run Detection')) {
                        btn.scrollIntoView({block: 'center', behavior: 'instant'});
                        btn.click();
                        return true;
                    }
                }
                return false;
            }""")

            if run_clicked:
                print("   Running detection (waiting 12s)...")
                wait_st(page, 12000)
                save(page, "artifact-detection-results.png")

                # Scroll back to tachogram to show artifacts on plot
                page.evaluate("""() => {
                    const main = document.querySelector('[data-testid="stMain"]');
                    if (!main) return;
                    const headings = [...main.querySelectorAll('h1, h2, h3, h4, h5, h6')];
                    const h = headings.find(h => h.textContent.includes('RR Interval'));
                    if (h) h.scrollIntoView({block: 'start', behavior: 'instant'});
                }""")
                page.wait_for_timeout(3000)
                save(page, "tachogram-with-artifacts.png")
            else:
                print("   ! Run Detection button not found")

        browser.close()

    pngs = sorted(OUT.glob("*.png"))
    print(f"\nDone! {len(pngs)} total screenshots")
    for s in pngs:
        print(f"  {s.name} ({s.stat().st_size // 1024}KB)")


if __name__ == "__main__":
    main()
