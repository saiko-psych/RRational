# Frequently Asked Questions

## Data & Import

### What data formats does RRational support?

RRational supports 8 input formats:

- **HRV Logger** (iOS/Android) — CSV with timestamps and events
- **VNS Analyse** (clinical) — TXT with embedded annotations
- **Polar Sensor Logger / Polar Beat** — CSV with phone timestamps
- **Polar Flow** — TSV export (elapsed time only)
- **Empatica E4 / EmbracePlus** — IBI.csv with Unix timestamps
- **Elite HRV** — Plain text, one RR value per line
- **Kubios HRV** — Report or signal/series export
- **Plain text RR** — Any single-column RR interval file

See [Data Formats](../user-guide/data-formats.md) for detailed specifications.

### How are participant IDs extracted?

By default, RRational extracts participant IDs from filenames using the pattern `(\d+)` (first number found). For example, `VP01_RR_2024-01-15.csv` becomes `VP01`. You can customize the pattern in the Data tab settings.

### Can I merge multiple recording files per participant?

Yes. If multiple `_RR_` files share the same participant ID, RRational automatically merges them chronologically. For VNS Analyse, multiple `.txt` files per participant are concatenated with gap detection.

---

## Artifact Detection

### What artifact rate is acceptable?

Following the 2024 Quigley guidelines:

| Artifact Rate | Quality Grade | Recommendation |
|---------------|---------------|----------------|
| < 2% | A (Excellent) | All metrics valid |
| 2–5% | B (Good) | All metrics valid |
| 5–10% | C (Acceptable) | Time-domain only |
| > 10% | D (Poor) | Exclude segment |

### Which artifact detection method should I use?

- **Kubios (Segmented)** — recommended for long recordings (> 10 min). Processes in 5-minute windows for better sensitivity.
- **Kubios (Single-pass)** — for short segments (< 10 min)
- **Threshold** — simple min/max filter, useful for initial screening

### Should I correct artifacts before analysis?

Yes. RRational uses the Kubios algorithm (Lipponen & Tarvainen, 2019) for correction. Corrected NN intervals replace detected artifacts with interpolated values. However, segments with > 10% artifacts should be excluded entirely rather than corrected.

---

## Analysis

### How many beats do I need for valid HRV analysis?

| Domain | Minimum Beats | Recommended |
|--------|---------------|-------------|
| Time-domain (RMSSD, SDNN) | 100 | 300+ |
| Frequency-domain (LF, HF) | 300 | 500+ |

Short recordings produce unreliable frequency metrics. RRational warns you when beat counts are insufficient.

### What does RMSSD measure?

RMSSD (Root Mean Square of Successive Differences) reflects parasympathetic (vagal) cardiac modulation. It is the most robust short-term HRV metric and is resistant to breathing rate confounds.

### Is the LF/HF ratio a valid measure of sympathovagal balance?

No. Current consensus (Quigley et al., 2024; Laborde et al., 2017) rejects the LF/HF ratio as an index of sympathovagal balance. The LF band reflects both sympathetic and parasympathetic activity plus baroreflex function. RRational includes it for completeness but we recommend focusing on RMSSD and HF power for parasympathetic assessment.

### What window size should I use?

- **5 minutes** — standard for short-term HRV (Task Force, 1996)
- **2–3 minutes** — acceptable for ultra-short recordings (Munoz et al., 2015)
- Ensure consistent window sizes within a study

---

## Segments & Sections

### What is the difference between segments and sections?

- **Segments** are time-based windows (e.g., every 5 minutes) created automatically for artifact detection and quality assessment
- **Sections** are event-based boundaries (e.g., "measurement_start" to "pause_start") defined by your experimental protocol

### How do I set up repeating experimental conditions?

1. Define **Event Sequences** in Setup > Sequences (e.g., Sequence A: music, silence, music, silence)
2. Assign participants to sequences
3. Set **Condition Labels** (e.g., "condition_a" → "Music", "condition_b" → "Silence")
4. Use **Repeating Section Analysis** in the Analysis tab

---

## Export & Reporting

### What export formats are available?

- **CSV** — metric tables with all computed HRV values
- **JSON** — structured results with metadata
- **.rrational** — native format preserving full analysis state (reimportable)

### What should I report in a publication?

Following the GRAPH checklist (Quintana et al., 2016):

1. Recording device and sampling rate
2. Artifact detection method and threshold
3. Artifact rate per segment
4. Correction algorithm used
5. HRV metrics with window duration
6. Number of excluded segments and reasons
7. Beat count per analyzed segment

---

## Appearance

### How do I customize plot colors?

Open the sidebar → expand **Settings** → scroll to **Color Theme**. Choose a preset (Scientific, Colorful, High Contrast, Monochrome, Pastel) or select **Custom** to pick individual colors for RR line, NN line, artifacts, exclusions, events, and sections. Click **Save Settings** to persist your choice.

### Does dark mode affect plot colors?

Yes. When you switch to dark mode, all plot colors are automatically lightened for better visibility on dark backgrounds. You don't need to configure separate dark mode colors.

### What are the preset themes?

| Preset | Style | Best for |
|--------|-------|----------|
| **Scientific** | Classic blue/green tones | Publications, presentations |
| **Colorful** | Vibrant purple/pink/teal | Exploratory analysis |
| **High Contrast** | Pure primary colors | Accessibility, projectors |
| **Monochrome** | Grayscale | B&W printing |
| **Pastel** | Soft, muted tones | Light backgrounds, reports |

---

## Technical

### The macOS app won't open / "unverified developer"

The standalone app is not signed with an Apple Developer certificate. macOS Gatekeeper blocks unsigned apps by default.

**Fix:** Right-click `RRational.app` → **Open** (not double-click). Click **Open** in the dialog. This only needs to be done once.

**Alternative:** Open Terminal and run:
```bash
xattr -cr /path/to/RRational.app
```

### Why is the app slow to start?

First launch imports heavy dependencies (NeuroKit2, Plotly, NumPy). Subsequent reruns are fast due to caching. Use `--test-mode` for quick testing with demo data.

### Can I use RRational without an internet connection?

Yes. RRational runs entirely locally. No data is transmitted externally. All processing happens on your machine.

### How do I update RRational?

```bash
uv pip install --upgrade rrational
```

Or pull the latest from the repository:

```bash
git pull origin main
uv sync
```
