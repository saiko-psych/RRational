---
hide:
  - navigation
---

# RRational

**A rational approach to Heart Rate Variability analysis**

---

RRational is a free, open-source HRV analysis toolkit built for researchers who need reliable, transparent, and reproducible heart rate variability analysis.

It provides an interactive Streamlit GUI for importing, inspecting, cleaning, and analyzing RR-interval data — following current scientific guidelines (Quigley et al., 2024).

<div class="grid cards" markdown>

-   :material-chart-line:{ .lg .middle } **Interactive Visualization**

    ---

    WebGL-accelerated tachogram with click-to-add events, zoom, pan, and real-time Power Spectral Density plots.

-   :material-shield-check:{ .lg .middle } **Artifact Detection**

    ---

    Lipponen & Tarvainen (2019) algorithm with per-segment quality grading following Quigley 2024 guidelines.

-   :material-chart-bar:{ .lg .middle } **Comprehensive HRV Metrics**

    ---

    Time domain (RMSSD, SDNN, pNN50), frequency domain (LF, HF), and nonlinear (SD1, SD2) metrics.

-   :material-account-group:{ .lg .middle } **Group & Sequence Comparison**

    ---

    Batch analysis across study groups and event sequences with bar charts, violin plots, and raincloud plots.

</div>

## Key Features

- **Section-based analysis** — Define time segments with start/end events and duration validation
- **Project management** — Self-contained project folders with data, config, and results
- **Report generation** — Export as HTML or Markdown for publication-ready documentation
- **Scientific rigor** — Follows 2024 Quigley guidelines for artifact handling and reporting
- **Export ready** — CSV export for statistical analysis, `.rrational` files with full audit trail

## Supported Data Sources

| App | Platform | Format | Details |
|-----|----------|--------|---------|
| [HRV Logger](https://www.hrv.tools/hrv-logger-faq.html) | iOS / Android | CSV | [Format Reference](user-guide/data-formats.md) |
| [VNS Analyse](https://apps.apple.com/de/app/vns-analyse/id990667927) | iOS | TXT | [Format Reference](user-guide/data-formats.md#vns-analyse-txt) |

## Getting Started

!!! tip "New to RRational?"

    1. **[Installation](getting-started/installation.md)** — Set up RRational on your system
    2. **[Quick Start](getting-started/quickstart.md)** — Your first HRV analysis in 5 minutes
    3. **[User Guide](user-guide/workflow.md)** — Complete workflow from import to export
    4. **[FAQ](getting-started/faq.md)** — Common questions answered

## Downloads

[:material-download: **Download Standalone App**](https://github.com/saiko-psych/rrational/releases/latest){ .md-button .md-button--primary }
[:material-github: **Source Code**](https://github.com/saiko-psych/rrational){ .md-button }

!!! info "Standalone App"
    RRational is available as a standalone desktop application for **Windows**, **macOS**, and **Linux** — no Python installation required. Download from the [Releases page](https://github.com/saiko-psych/rrational/releases).

## Getting Help

- **In-app help** — Look for expandable help sections throughout the GUI
- **Bug reports** — [Report an issue on GitHub](https://github.com/saiko-psych/rrational/issues/new/choose)
- **[FAQ](getting-started/faq.md)** — Common questions and answers
- **[Glossary](reference/glossary.md)** — HRV terminology explained

## Citation

If you use RRational in your research, please cite:

> RRational: A rational approach to Heart Rate Variability analysis. [https://github.com/saiko-psych/rrational](https://github.com/saiko-psych/rrational)

---

*RRational is [MIT licensed](https://github.com/saiko-psych/rrational/blob/main/LICENSE) — free for academic and commercial use.*
