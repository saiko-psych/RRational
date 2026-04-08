"""Comprehensive documentation screenshots for RRational.

Takes 30+ screenshots covering every tab, every interaction state,
and every important UI element. Uses SwiftShader for WebGL rendering.
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


def scroll_main(page, y):
    page.evaluate(f"""() => {{
        const main = document.querySelector('[data-testid="stMain"]');
        if (main) main.scrollTop = {y};
    }}""")
    page.wait_for_timeout(800)


def scroll_main_by(page, dy):
    page.evaluate(f"""() => {{
        const main = document.querySelector('[data-testid="stMain"]');
        if (main) main.scrollBy(0, {dy});
    }}""")
    page.wait_for_timeout(800)


def scroll_to_text(page, text):
    page.evaluate(f"""() => {{
        const main = document.querySelector('[data-testid="stMain"]');
        if (!main) return;
        const els = [...main.querySelectorAll('h1,h2,h3,h4,h5,h6,p,div,span,label')];
        const el = els.find(e => e.textContent.includes('{text}') && e.textContent.length < 200);
        if (el) el.scrollIntoView({{block: 'start', behavior: 'instant'}});
    }}""")
    page.wait_for_timeout(800)


def click_nav(page, label):
    page.locator(f"[data-testid='stSidebar'] button:has-text('{label}')").first.click()
    wait_st(page, 3000)


def click_radio_in_main(page, label):
    page.evaluate(f"""() => {{
        const main = document.querySelector('[data-testid="stMain"]');
        if (!main) return;
        const labels = main.querySelectorAll('label');
        for (const l of labels) {{
            if (l.textContent.includes('{label}')) {{
                l.click();
                break;
            }}
        }}
    }}""")
    wait_st(page, 2000)


def click_checkbox_in_main(page, label):
    """Enable a checkbox by label text."""
    page.evaluate(f"""() => {{
        const main = document.querySelector('[data-testid="stMain"]');
        if (!main) return;
        const labels = main.querySelectorAll('label');
        for (const l of labels) {{
            if (l.textContent.includes('{label}')) {{
                const input = l.querySelector('input[type="checkbox"]');
                if (input && !input.checked) l.click();
                break;
            }}
        }}
    }}""")
    wait_st(page, 2000)


def open_expander(page, text):
    """Open an expander by its text content."""
    page.evaluate(f"""() => {{
        const details = document.querySelectorAll('details');
        for (const d of details) {{
            if (d.textContent.includes('{text}') && !d.open) {{
                d.scrollIntoView({{block: 'start', behavior: 'instant'}});
                const summary = d.querySelector('summary');
                if (summary) summary.click();
                break;
            }}
        }}
    }}""")
    wait_st(page, 1500)


def click_button_in_main(page, text):
    """Click a button by text."""
    return page.evaluate(f"""() => {{
        const buttons = document.querySelectorAll('button');
        for (const b of buttons) {{
            if (b.textContent.includes('{text}')) {{
                b.scrollIntoView({{block: 'center', behavior: 'instant'}});
                b.click();
                return true;
            }}
        }}
        return false;
    }}""")


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--enable-webgl", "--use-gl=swiftshader"],
        )
        ctx = browser.new_context(viewport={"width": W, "height": H})
        page = ctx.new_page()

        # ═══════════════════════════════════════════════════
        # DATA TAB
        # ═══════════════════════════════════════════════════
        print("=== DATA TAB ===")
        page.goto(BASE_URL)
        wait_st(page, 5000)

        # 01: Top of Data tab - header, test mode banner, folder path
        scroll_main(page, 0)
        save(page, "01-data-top.png")

        # 02: Import settings area
        scroll_to_text(page, "Import Settings")
        save(page, "02-data-import-settings.png")

        # 03: Participants Overview table
        scroll_to_text(page, "Participants Overview")
        save(page, "03-data-participants-overview.png")

        # 04: Participants table with data
        scroll_main_by(page, 200)
        save(page, "04-data-participants-table.png")

        # 05: CSV import section
        scroll_to_text(page, "Import Group")
        save(page, "05-data-csv-import.png")

        # ═══════════════════════════════════════════════════
        # PARTICIPANTS TAB
        # ═══════════════════════════════════════════════════
        print("=== PARTICIPANTS TAB ===")
        click_nav(page, "Participants")

        # 06: Participant header with metrics
        scroll_main(page, 0)
        save(page, "06-participants-header.png")

        # 07: Participant details (Total Beats, Duration, etc.)
        scroll_to_text(page, "Total Beats")
        save(page, "07-participants-metrics.png")

        # 08: Mode selector and plot options
        scroll_to_text(page, "RR Interval Visualization")
        save(page, "08-participants-mode-selector.png")

        # 09: Plot options checkboxes
        scroll_to_text(page, "Plot Options")
        save(page, "09-participants-plot-options.png")

        # 10: Tachogram chart
        scroll_to_text(page, "RR Interval Visualization")
        scroll_main_by(page, 350)
        page.wait_for_timeout(3000)  # WebGL render
        save(page, "10-participants-tachogram.png")

        # 11: Enable "Show artifacts" checkbox
        click_checkbox_in_main(page, "Show artifacts")
        scroll_to_text(page, "Tachogram")
        scroll_main_by(page, 100)
        page.wait_for_timeout(3000)
        save(page, "11-participants-tachogram-artifacts.png")

        # 12: Detect New Artifacts expander (opened)
        open_expander(page, "Detect New Artifacts")
        save(page, "12-artifact-detection-expander.png")

        # 13: Detection scope options
        scroll_to_text(page, "Detection Scope")
        save(page, "13-artifact-detection-scope.png")

        # 14: Run detection and show results
        if click_button_in_main(page, "Run Detection"):
            print("   Running detection...")
            wait_st(page, 12000)
            save(page, "14-artifact-detection-results.png")

            # 15: Scroll to see segment quality
            scroll_main_by(page, 300)
            save(page, "15-artifact-segment-quality.png")

        # 16: Section Validation area
        scroll_to_text(page, "Section Validation")
        save(page, "16-section-validation.png")

        # 17: Section validation details
        scroll_main_by(page, 200)
        save(page, "17-section-validation-details.png")

        # 18: Events table area
        scroll_to_text(page, "Event Mapping Status")
        save(page, "18-events-mapping.png")

        # 19: Export for Analysis
        scroll_to_text(page, "Export for Analysis")
        save(page, "19-export-for-analysis.png")

        # ═══════════════════════════════════════════════════
        # SETUP TAB
        # ═══════════════════════════════════════════════════
        print("=== SETUP TAB ===")
        click_nav(page, "Setup")

        # 20: Setup Events tab
        scroll_main(page, 0)
        save(page, "20-setup-events-top.png")

        # 21: Event definitions table
        scroll_main_by(page, 400)
        save(page, "21-setup-events-table.png")

        # 22: Setup Groups tab
        click_radio_in_main(page, "Groups")
        scroll_main(page, 0)
        save(page, "22-setup-groups.png")

        # 23: Setup Sequences tab
        click_radio_in_main(page, "Sequences")
        scroll_main(page, 0)
        save(page, "23-setup-sequences-top.png")

        # 24: Existing sequences list
        scroll_to_text(page, "Existing Event Sequences")
        save(page, "24-setup-sequences-list.png")

        # 25: Condition Labels table
        scroll_to_text(page, "Condition Labels")
        save(page, "25-setup-condition-labels.png")

        # 26: Setup Sections tab
        try:
            click_radio_in_main(page, "Sections")
            scroll_main(page, 0)
            save(page, "26-setup-sections.png")
        except Exception:
            print("   ! Sections radio not clickable")

        # ═══════════════════════════════════════════════════
        # ANALYSIS TAB
        # ═══════════════════════════════════════════════════
        print("=== ANALYSIS TAB ===")
        click_nav(page, "Analysis")

        # 27: Analysis mode selection
        scroll_main(page, 0)
        save(page, "27-analysis-mode-selection.png")

        # 28: Single participant analysis settings
        scroll_main_by(page, 200)
        save(page, "28-analysis-single-settings.png")

        # 29: Repeating Section Analysis
        click_radio_in_main(page, "Repeating Section Analysis")
        scroll_main(page, 0)
        save(page, "29-analysis-repeating-top.png")

        # 30: Repeating Section settings
        scroll_main_by(page, 200)
        save(page, "30-analysis-repeating-settings.png")

        # 31: Group Analysis
        click_radio_in_main(page, "Group Analysis")
        scroll_main(page, 0)
        save(page, "31-analysis-group.png")

        # ═══════════════════════════════════════════════════
        # SIDEBAR
        # ═══════════════════════════════════════════════════
        print("=== SIDEBAR ===")

        # 32: Sidebar navigation
        sidebar = page.locator("[data-testid='stSidebar']")
        if sidebar.count() > 0:
            sidebar.evaluate("el => el.scrollTo(0, 0)")
            page.wait_for_timeout(500)
            sidebar.screenshot(path=str(OUT / "32-sidebar-navigation.png"))
            print(f"  [{(OUT / '32-sidebar-navigation.png').stat().st_size // 1024:>4}KB] 32-sidebar-navigation.png")

            # 33: Sidebar bottom (settings, docs, bug report, version)
            sidebar.evaluate("el => el.scrollTo(0, el.scrollHeight)")
            page.wait_for_timeout(500)
            sidebar.screenshot(path=str(OUT / "33-sidebar-bottom.png"))
            print(f"  [{(OUT / '33-sidebar-bottom.png').stat().st_size // 1024:>4}KB] 33-sidebar-bottom.png")

        browser.close()

    pngs = sorted(OUT.glob("*.png"))
    print(f"\n=== DONE! {len(pngs)} total screenshots ═══")
    for s in pngs:
        print(f"  {s.name} ({s.stat().st_size // 1024}KB)")


if __name__ == "__main__":
    main()
