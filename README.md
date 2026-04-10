# RRational

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11-3.13](https://img.shields.io/badge/python-3.11--3.13-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.9.1-green.svg)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-91%20passing-brightgreen.svg)](tests/)
[![Documentation](https://readthedocs.org/projects/rrational/badge/?version=latest)](https://rrational.readthedocs.io)

**A rational approach to Heart Rate Variability analysis**

*Free, open-source HRV toolkit for researchers*

[Documentation](https://rrational.readthedocs.io) |
[Quick Start](https://rrational.readthedocs.io/en/latest/getting-started/quickstart/) |
[Download](https://github.com/saiko-psych/rrational/releases/latest) |
[Report a Bug](https://github.com/saiko-psych/rrational/issues/new/choose)

</div>

---

## What is RRational?

RRational is an open-source HRV analysis toolkit built for researchers who need reliable, transparent, and reproducible heart rate variability analysis. It provides an interactive Streamlit GUI for importing, inspecting, cleaning, and analyzing RR-interval data — following current scientific guidelines (Quigley et al., 2024).

## Supported Data Sources

| Source | Platform | Format |
|--------|----------|--------|
| [HRV Logger](https://www.hrv.tools/hrv-logger-faq.html) | iOS / Android | CSV |
| [VNS Analyse](https://apps.apple.com/de/app/vns-analyse/id990667927) | iOS (clinical) | TXT |
| Polar H10 / Polar Beat | Chest strap | CSV |
| Polar Flow | Web export | TSV |
| Empatica E4 / EmbracePlus | Wristband (PPG) | CSV |
| Elite HRV | iOS / Android | TXT |
| Kubios HRV | Desktop | TXT |
| Plain text RR intervals | Any | TXT/CSV |

## Key Features

- **Interactive tachogram** — WebGL-accelerated plots with click-to-add events, zoom, and pan
- **Power Spectrum (PSD)** — Real-time frequency-domain view with VLF/LF/HF band analysis
- **Artifact detection** — Lipponen & Tarvainen (2019) algorithm with per-segment quality grading
- **HRV metrics** — Time domain (RMSSD, SDNN, pNN50), frequency domain (LF, HF), nonlinear (SD1, SD2)
- **Group & Sequence comparison** — Batch analysis with bar charts, violin plots, and raincloud plots
- **Report generation** — Export as HTML or Markdown for publication-ready documentation
- **Standalone app** — Available for Windows, macOS, and Linux (no Python needed)
- **Scientific rigor** — Follows 2024 Quigley guidelines for artifact handling and reporting

## Quick Start

```bash
git clone https://github.com/saiko-psych/rrational.git
cd rrational
uv sync
uv run streamlit run src/rrational/gui/app.py
```

> Requires Python 3.11-3.13 and [uv](https://docs.astral.sh/uv/getting-started/installation/).
> Or [download the standalone app](https://github.com/saiko-psych/rrational/releases/latest) — no installation required.

## Documentation

Full documentation at **[rrational.readthedocs.io](https://rrational.readthedocs.io)**.

## Citation

If you use RRational in your research, please cite:

> RRational: A rational approach to Heart Rate Variability analysis. https://github.com/saiko-psych/rrational

## Contributing

Found a bug or have a feature idea? Check [existing issues](https://github.com/saiko-psych/rrational/issues) first, then see the [Contributing Guide](https://rrational.readthedocs.io/en/latest/development/contributing/).

## License

[MIT License](LICENSE) — free for academic and commercial use.
