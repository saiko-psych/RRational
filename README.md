# RRational

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11-3.13](https://img.shields.io/badge/python-3.11--3.13-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.8.1-green.svg)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-77%20passing-brightgreen.svg)](tests/)
[![Documentation](https://readthedocs.org/projects/rrational/badge/?version=latest)](https://rrational.readthedocs.io)

**A rational approach to Heart Rate Variability analysis**

*Free, open-source HRV toolkit for researchers*

[Documentation](https://rrational.readthedocs.io) |
[Quick Start](https://rrational.readthedocs.io/en/latest/getting-started/quickstart/) |
[Report a Bug](https://github.com/saiko-psych/rrational/issues/new/choose)

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

## Quick Start

```bash
git clone https://github.com/saiko-psych/rrational.git
cd rrational
uv sync
uv run streamlit run src/rrational/gui/app.py
```

> Requires Python 3.11-3.13 and [uv](https://docs.astral.sh/uv/getting-started/installation/).
> See the [Installation Guide](https://rrational.readthedocs.io/en/latest/getting-started/installation/) for details.

## Documentation

Full documentation is available at **[rrational.readthedocs.io](https://rrational.readthedocs.io)**.

## Citation

If you use RRational in your research, please cite:

> RRational: A rational approach to Heart Rate Variability analysis. https://github.com/saiko-psych/rrational

## Contributing

Found a bug or have a feature idea? Check [existing issues](https://github.com/saiko-psych/rrational/issues) first, then see the [Contributing Guide](https://rrational.readthedocs.io/en/latest/development/contributing/).

## License

[MIT License](LICENSE) — free for academic and commercial use.
