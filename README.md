# RRational

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11-3.13](https://img.shields.io/badge/python-3.11--3.13-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.8.1-green.svg)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-77%20passing-brightgreen.svg)](tests/)

**A rational approach to Heart Rate Variability analysis**

*Free, open-source HRV toolkit for researchers — like Kubios, but free.*

</div>

---

## What is RRational?

RRational is an open-source HRV analysis toolkit built for researchers who need reliable, transparent, and reproducible heart rate variability analysis. It provides an interactive Streamlit GUI for importing, inspecting, cleaning, and analyzing RR-interval data — following current scientific guidelines (Quigley et al., 2024).

Supports data from [HRV Logger](https://www.hrv.tools/hrv-logger-faq.html) (iOS/Android) and [VNS Analyse](https://apps.apple.com/de/app/vns-analyse/id990667927) (iOS).

## Key Features

- **Interactive tachogram** — WebGL-accelerated plots with click-to-add events, zoom, and pan
- **Artifact detection** — Lipponen & Tarvainen (2019) algorithm with per-segment quality grading
- **Section-based analysis** — Define time segments with start/end events and duration validation
- **HRV metrics** — Time domain (RMSSD, SDNN, pNN50), frequency domain (LF, HF, LF/HF), nonlinear (SD1, SD2)
- **Project management** — Self-contained project folders with data, config, and results
- **Group comparison** — Batch analysis across study groups with statistical summaries
- **Scientific rigor** — Follows 2024 Quigley guidelines for artifact handling and reporting
- **Export ready** — CSV export for statistical analysis, `.rrational` files with full audit trail

## Quick Start

```bash
git clone https://github.com/saiko-psych/rrational.git
cd rrational
uv sync                # Install dependencies (requires uv)
uv run streamlit run src/rrational/gui/app.py   # Launch the GUI
```

> Requires Python 3.11-3.13 and [uv](https://docs.astral.sh/uv/getting-started/installation/). See [Installation Guide](docs/INSTALLATION.md) for detailed setup and troubleshooting.

## Documentation

| Resource | Description |
|----------|-------------|
| **[Quick Start Guide](QUICKSTART.md)** | Get up and running in 5 minutes |
| **[Installation Guide](docs/INSTALLATION.md)** | Detailed setup, updating & troubleshooting |
| **[Data Formats](docs/DATA_FORMATS.md)** | Supported file formats (HRV Logger, VNS Analyse) |
| **[Configuration](docs/CONFIGURATION.md)** | Project structure, settings & storage |
| **[Architecture](docs/ARCHITECTURE.md)** | Code structure & module overview |
| **[Scientific Background](docs/hrv_scientific.md)** | HRV guidelines, references & best practices |
| **[Contributing](docs/CONTRIBUTING.md)** | How to report issues & contribute code |
| **[Changelog](CHANGELOG.md)** | Version history |

## Scientific Background

RRational implements current best practices for HRV research, including the 2024 Quigley guidelines for artifact handling, minimum data requirements (100 beats for time domain, 300 for frequency domain), and transparent quality reporting. For details, see [Scientific Background](docs/hrv_scientific.md) and [Signal Processing Pipeline](docs/hrv_processing_pipeline.md).

## Citation

If you use RRational in your research, please cite:

> RRational: A rational approach to Heart Rate Variability analysis. https://github.com/saiko-psych/rrational

## Contributing

Found a bug or have a feature idea? Check [existing issues](https://github.com/saiko-psych/rrational/issues) first, then see our [Contributing Guide](docs/CONTRIBUTING.md).

## License

[MIT License](LICENSE) — free for academic and commercial use.
