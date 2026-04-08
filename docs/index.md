# RRational

**A rational approach to Heart Rate Variability analysis**

---

RRational is a free, open-source HRV analysis toolkit built for researchers who need reliable, transparent, and reproducible heart rate variability analysis.

It provides an interactive Streamlit GUI for importing, inspecting, cleaning, and analyzing RR-interval data — following current scientific guidelines (Quigley et al., 2024).

## Key Features

- **Interactive tachogram** — WebGL-accelerated plots with click-to-add events, zoom, and pan
- **Artifact detection** — Lipponen & Tarvainen (2019) algorithm with per-segment quality grading
- **Section-based analysis** — Define time segments with start/end events and duration validation
- **HRV metrics** — Time domain (RMSSD, SDNN, pNN50), frequency domain (LF, HF, LF/HF), nonlinear (SD1, SD2)
- **Project management** — Self-contained project folders with data, config, and results
- **Group comparison** — Batch analysis across study groups with statistical summaries
- **Scientific rigor** — Follows 2024 Quigley guidelines for artifact handling and reporting
- **Export ready** — CSV export for statistical analysis, `.rrational` files with full audit trail

## Supported Data Sources

| App | Platform | Format | Details |
|-----|----------|--------|---------|
| [HRV Logger](https://www.hrv.tools/hrv-logger-faq.html) | iOS / Android | CSV | [Format Reference](user-guide/data-formats.md) |
| [VNS Analyse](https://apps.apple.com/de/app/vns-analyse/id990667927) | iOS | TXT | [Format Reference](user-guide/data-formats.md#vns-analyse-txt) |

## Getting Started

New to RRational? Start here:

1. **[Installation](getting-started/installation.md)** — Set up RRational on your system
2. **[Quick Start](getting-started/quickstart.md)** — Your first HRV analysis in 5 minutes
3. **[User Guide](user-guide/workflow.md)** — Complete workflow from import to export

## Getting Help

- **In-app help** — Look for expandable help sections throughout the GUI
- **Bug reports** — [Report an issue on GitHub](https://github.com/saiko-psych/rrational/issues/new/choose)
- **Source code** — [GitHub Repository](https://github.com/saiko-psych/rrational)

## Citation

If you use RRational in your research, please cite:

> RRational: A rational approach to Heart Rate Variability analysis. [https://github.com/saiko-psych/rrational](https://github.com/saiko-psych/rrational)

---

*RRational is [MIT licensed](https://github.com/saiko-psych/rrational/blob/main/LICENSE) — free for academic and commercial use.*
