# RRational Documentation

**A rational approach to Heart Rate Variability analysis**

RRational is a free, open-source HRV analysis toolkit built for researchers. It provides an interactive GUI for importing, inspecting, cleaning, and analyzing RR-interval data — following current scientific guidelines.

---

## Quick Links

<div class="grid cards" markdown>

- :material-download: **[Installation](INSTALLATION.md)** — Set up RRational on your system
- :material-file-document: **[Data Formats](DATA_FORMATS.md)** — Supported file formats (HRV Logger, VNS Analyse)
- :material-cog: **[Configuration](CONFIGURATION.md)** — Projects, settings, and storage
- :material-flask: **[Scientific Background](hrv_scientific.md)** — HRV guidelines and best practices

</div>

---

## Key Features

- **Interactive tachogram** — WebGL-accelerated plots with click-to-add events, zoom, and pan
- **Artifact detection** — Lipponen & Tarvainen (2019) algorithm with per-segment quality grading
- **Section-based analysis** — Define time segments with start/end events and duration validation
- **HRV metrics** — Time domain (RMSSD, SDNN, pNN50), frequency domain (LF, HF, LF/HF), nonlinear (SD1, SD2)
- **Project management** — Self-contained project folders with data, config, and results
- **Group comparison** — Batch analysis across study groups with statistical summaries
- **Scientific rigor** — Follows 2024 Quigley guidelines for artifact handling and reporting
- **Export ready** — CSV export for statistical analysis

## Supported Data Sources

| App | Platform | Format |
|-----|----------|--------|
| [HRV Logger](https://www.hrv.tools/hrv-logger-faq.html) | iOS / Android | CSV |
| [VNS Analyse](https://apps.apple.com/de/app/vns-analyse/id990667927) | iOS | TXT |

## Getting Help

- **Bug reports**: [GitHub Issues](https://github.com/saiko-psych/rrational/issues/new/choose)
- **Source code**: [GitHub Repository](https://github.com/saiko-psych/rrational)
- **Contributing**: [Contributing Guide](CONTRIBUTING.md)

---

*RRational is MIT licensed — free for academic and commercial use.*
