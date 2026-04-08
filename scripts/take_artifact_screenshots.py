"""Take artifact detection screenshots.

The "Detect New Artifacts" expander only appears when "Show artifacts" checkbox
is enabled in the plot fragment. We need to check that checkbox first.
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


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--enable-webgl", "--use-gl=swiftshader"],
        )
        ctx = browser.new_context(viewport={"width": W, "height": H})
        page = ctx.new_page()

        # Load & navigate to Participants
        print("1. Loading app...")
        page.goto(BASE_URL)
        wait_st(page, 5000)
        page.locator("[data-testid='stSidebar'] button:has-text('Participants')").first.click()
        wait_st(page, 3000)

        # Enable "Show artifacts" checkbox to trigger the artifact fragment
        print("2. Enabling 'Show artifacts' checkbox...")
        checked = page.evaluate("""() => {
            const main = document.querySelector('[data-testid="stMain"]');
            if (!main) return {found: false, error: 'no stMain'};

            // Find all checkbox labels
            const labels = main.querySelectorAll('label');
            for (const label of labels) {
                if (label.textContent.includes('Show artifacts')) {
                    // Click the checkbox input
                    const input = label.querySelector('input[type="checkbox"]');
                    if (input && !input.checked) {
                        label.click();
                        return {found: true, clicked: true};
                    } else if (input && input.checked) {
                        return {found: true, clicked: false, alreadyChecked: true};
                    }
                    // Fallback: click the label itself
                    label.click();
                    return {found: true, clicked: true, fallback: true};
                }
            }
            return {found: false, labelCount: labels.length};
        }""")
        print(f"   Result: {checked}")
        wait_st(page, 5000)  # Fragment reruns after checkbox change

        # Now search for "Detect New Artifacts" expander
        print("3. Searching for Detect New Artifacts after checkbox...")
        expanders = page.evaluate("""() => {
            const details = document.querySelectorAll('details');
            return Array.from(details).map((d, i) => ({
                index: i,
                open: d.open,
                text: d.textContent.substring(0, 60),
                y: d.getBoundingClientRect().y,
            })).filter(d => d.text.includes('Detect'));
        }""")
        print(f"   Detect expanders: {expanders}")

        if expanders:
            idx = expanders[0]['index']
            print(f"4. Opening Detect expander (details[{idx}])...")

            # Open it and scroll into view
            page.evaluate(f"""() => {{
                const allDetails = document.querySelectorAll('details');
                // Find all details that match, use the actual index from allDetails
                for (const d of allDetails) {{
                    if (d.textContent.includes('Detect New Artifacts')) {{
                        d.scrollIntoView({{block: 'start', behavior: 'instant'}});
                        d.open = true;
                        const summary = d.querySelector('summary');
                        if (summary) summary.click();
                        break;
                    }}
                }}
            }}""")
            wait_st(page, 3000)
            save(page, "artifact-detection-settings.png")

            # Find and click Run Detection
            print("5. Running detection...")
            run_clicked = page.evaluate("""() => {
                const buttons = document.querySelectorAll('button');
                for (const b of buttons) {
                    if (b.textContent.includes('Run Detection')) {
                        b.scrollIntoView({block: 'center', behavior: 'instant'});
                        b.click();
                        return {clicked: true, text: b.textContent.trim()};
                    }
                }
                return {clicked: false};
            }""")
            print(f"   Run button: {run_clicked}")

            if run_clicked.get('clicked'):
                print("   Waiting for detection to complete (15s)...")
                wait_st(page, 15000)
                save(page, "artifact-detection-results.png")

                # Scroll to tachogram to see artifacts on plot
                print("6. Scrolling to tachogram with artifacts...")
                page.evaluate("""() => {
                    const main = document.querySelector('[data-testid="stMain"]');
                    if (!main) return;
                    const h = [...main.querySelectorAll('h1,h2,h3,h4,h5,h6')]
                        .find(h => h.textContent.includes('RR Interval'));
                    if (h) h.scrollIntoView({block: 'start', behavior: 'instant'});
                }""")
                page.evaluate("""() => {
                    const main = document.querySelector('[data-testid="stMain"]');
                    if (main) main.scrollBy(0, 350);
                }""")
                page.wait_for_timeout(4000)
                save(page, "tachogram-with-artifacts.png")
        else:
            print("   ! Still no Detect expander found after enabling checkbox")
            # Debug: list ALL details elements
            all_details = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('details')).map((d, i) => ({
                    i: i, text: d.textContent.substring(0, 50), y: d.getBoundingClientRect().y
                }));
            }""")
            print(f"   All <details>: {len(all_details)}")
            for d in all_details:
                print(f"     [{d['i']}] y={d['y']:.0f} '{d['text']}'")

        browser.close()

    pngs = sorted(OUT.glob("*.png"))
    print(f"\nDone! {len(pngs)} total screenshots")


if __name__ == "__main__":
    main()
