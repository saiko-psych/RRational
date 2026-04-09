# Supported Data Formats

RRational supports RR interval data from multiple recording apps and devices. All formats are auto-detected — just place your files in the correct subfolder and click "Analyze Folder".

| Source | Platform | Timestamps | Events | Resolution |
|--------|----------|------------|--------|------------|
| **HRV Logger** | iOS/Android | Real clock time | Yes (separate CSV) | 1 ms |
| **VNS Analyse** | iOS (clinical) | Cumulative | Embedded annotations | ~1 ms |
| **Polar Sensor Logger** | iOS/Android | Real phone time | No | 1 ms |
| **Polar Flow** | Web export | Elapsed only | No | 1 ms |
| **Empatica E4** | Wristband (PPG) | Unix-based | No | 1/64 s (~16 ms) |
| **Elite HRV** | iOS/Android | None | No | 1 ms |
| **Kubios HRV** | Desktop | None | No | 1 ms |
| **Plain text RR** | Any source | None | No | Varies |

### Folder Structure

```
data/raw/
├── hrv_logger/      → HRV Logger CSV files
├── vns_analyse/     → VNS Analyse TXT files
├── polar/           → Polar Sensor Logger or Flow exports
├── empatica/        → Empatica E4 IBI.csv files
├── elite_hrv/       → Elite HRV exports
└── kubios/          → Kubios HRV report exports
```

!!! tip "Auto-Detection"
    RRational detects the format in two ways: (1) from the **folder name** (e.g., `polar/`), or (2) from the **file content** if the folder name doesn't match a known pattern. You can mix formats in the same project.

---

## HRV Logger (CSV)

**Best supported format** — full timestamps, events, and multi-file merging.

### Setup

1. Place files in `data/raw/hrv_logger/`
2. Each recording creates two files: `*_RR_*.csv` (data) and `*_Events_*.csv` (events)
3. Participant ID is extracted from the filename (e.g., `2025-03-15_RR_0001CTRL.csv` → `0001CTRL`)

### File Format

**RR file** (`*_RR_*.csv`):

```csv
date,rr,since start
2025-03-15 09:00:15.123,823,0
2025-03-15 09:00:15.946,812,823
```

| Column | Type | Unit | Description |
|--------|------|------|-------------|
| `date` | datetime | ISO 8601 | Real clock timestamp per beat |
| `rr` | integer | milliseconds | RR interval duration |
| `since start` | integer | milliseconds | Cumulative time from recording start |

**Events file** (`*_Events_*.csv`):

```csv
date,timestamp,annotation,manual
2025-03-15 09:00:15,0,Start Ruhe,false
2025-03-15 09:05:30,315000,Ruhe Ende,false
```

### What works well

- Full timestamp support — events align with RR data precisely
- Event markers for section boundaries (rest, measurement, pause)
- Multiple files per participant automatically merged chronologically
- Duplicate detection and removal

### Limitations

- Some newer HRV Logger versions use `timestamp` column instead of `date` — RRational shows a warning but still tries to parse

### Best practices

- Use the **HRV Logger Events feature** during recording to mark protocol events
- Name files consistently: include participant ID in the filename
- Keep RR and Events files together in the same folder

---

## VNS Analyse (TXT)

Clinical-grade RR interval data from VNS Analyse iOS app.

### Setup

1. Place files in `data/raw/vns_analyse/` or `data/raw/vns/`
2. One `.txt` file per recording session

### File Format

```
RR-Intervalle - Korrigierte Werte (Aktiv)
0.807
0.838	Notiz: Start Ruhe
0.851
```

| Data | Type | Unit | Description |
|------|------|------|-------------|
| RR values | float | **seconds** | One per line (RRational converts to ms) |
| Annotations | text | — | Embedded as `Notiz: label` next to RR values |

### What works well

- Provides both raw and VNS-corrected RR intervals
- Embedded event annotations (no separate events file needed)
- Clinical-grade precision

### Limitations

- **No real timestamps** — only cumulative time. Events are positioned by beat index, not clock time
- **Cumulative timestamps are synthetic** — removing beats would shift all subsequent timestamps
- **No artifact filtering during import** — artifact detection happens at analysis time
- VNS correction is proprietary — you can choose raw or corrected on import

### Best practices

- Use **corrected values** (`Korrigierte Werte`) unless you want to apply your own correction
- The filename contains recording metadata (date, duration) — keep original filenames

---

## Polar Sensor Logger / Polar Beat (CSV)

Data from the Polar Sensor Logger or Polar Beat Android/iOS apps connected to a Polar chest strap (H10, H9, etc.).

### Setup

1. Place files in `data/raw/polar/`
2. One CSV file per recording

### File Format

```csv
Phone timestamp,RR-interval [ms]
2026-04-01 09:00:00.000,832
2026-04-01 09:00:00.832,845
2026-04-01 09:00:01.677,798
```

| Column | Type | Unit | Description |
|--------|------|------|-------------|
| `Phone timestamp` | datetime | `YYYY-MM-DD HH:MM:SS.fff` | Real phone clock time |
| `RR-interval [ms]` | integer | milliseconds | RR interval duration |

### What works well

- **Real timestamps** — allows precise event alignment
- High accuracy from Polar chest straps (validated against medical ECG)
- Millisecond precision

### Limitations

- **No event markers** — you must add events manually in RRational
- Phone clock may drift slightly from chest strap clock
- Participant ID must be in the filename (not in the file content)

### Best practices

- Include participant ID in filename: `polar_P001_session1.csv`
- Note event times separately (paper, phone timer) and add them in RRational
- Polar H10 is the gold standard for wearable HRV research — prefer it over wrist-based PPG

---

## Polar Flow HRV Export (TSV)

HRV data exported from the Polar Flow web service or app.

### Setup

1. Place files in `data/raw/polar/`
2. Tab-separated, **no header row**

### File Format

```
0.997	832
1.829	845
2.674	798
```

| Column | Type | Unit | Description |
|--------|------|------|-------------|
| Column 1 | float | seconds | Elapsed time from recording start |
| Column 2 | integer | milliseconds | RR interval duration |

### What works well

- Simple, clean format
- Elapsed time allows relative positioning

### Limitations

- **No absolute timestamps** — only elapsed time. The tachogram shows elapsed time, not clock time
- **No event markers**
- **No header row** — RRational detects this format by checking for two tab-separated numeric columns
- Cannot determine recording start time (no date/time information)

### Best practices

- If you need timestamps and events, use **Polar Sensor Logger** instead of Polar Flow export
- Record the session start time separately for your protocol documentation

---

## Empatica E4 / EmbracePlus (IBI.csv)

Inter-beat interval data from Empatica wristband devices (PPG-based).

### Setup

1. Place `IBI.csv` files in `data/raw/empatica/`
2. Download from Empatica Connect or extract from the device archive

### File Format

```
1644844459.000000, IBI
26.984375,0.687500
27.671875,0.687500
28.359375,0.734375
```

| Line | Content | Description |
|------|---------|-------------|
| Line 1 | `unix_timestamp, IBI` | Recording start as Unix timestamp |
| Data lines | `offset, duration` | Time offset (s) and IBI duration (s) |

| Column | Type | Unit | Description |
|--------|------|------|-------------|
| Offset | float | seconds | Time since recording start |
| IBI | float | seconds | Inter-beat interval (RRational converts to ms) |

### What works well

- **Unix timestamps** — RRational calculates real clock times from the header
- Widely used in psychology and stress research
- Ambulatory recordings possible

### Limitations

!!! warning "PPG Limitations"
    Empatica uses **photoplethysmography (PPG)**, not ECG. This means:

    - **Lower temporal resolution**: 1/64 second (~16 ms) vs 1 ms for ECG
    - **Signal dropouts**: PPG is sensitive to movement, pressure, and skin contact. Expect gaps in the data (visible as gray regions in the tachogram)
    - **Less accurate** for short-term metrics: RMSSD may have ~10% error vs ECG reference
    - **Not suitable** for beat-to-beat morphology analysis

- **No event markers** — events must be added manually
- IBI values can be 0 or negative during signal loss — RRational filters these automatically
- Gap detection is important: check the "Time Gap Analysis" section for each participant

### Best practices

- Ensure tight wristband fit during recording
- Review gap analysis before running HRV analysis — exclude segments with excessive gaps
- For research requiring high precision, validate against ECG-based recordings
- Use time-domain metrics (RMSSD, SDNN) rather than frequency-domain for PPG data

---

## Elite HRV / Plain Text RR

Simple one-value-per-line format. Compatible with Elite HRV exports, Kubios plain exports, PhysioNet datasets, and any tool that outputs raw RR intervals.

### Setup

1. Place files in `data/raw/elite_hrv/`
2. One `.txt` file per recording

### File Format

```
832
845
798
812
856
```

One RR interval per line. No header, no timestamps, no metadata.

### Unit Auto-Detection

RRational automatically detects whether values are in **milliseconds** or **seconds**:

| Median value | Detected unit | Example |
|-------------|---------------|---------|
| > 10 | Milliseconds | `832`, `845`, `798` |
| < 10 | Seconds | `0.832`, `0.845`, `0.798` |

### What works well

- **Universal format** — works with data from any source
- Easy to create manually or export from other tools
- Compatible with PhysioNet datasets

### Limitations

- **No timestamps** — tachogram shows beat index, not clock time
- **No event markers** — section boundaries cannot be automatically detected
- **No metadata** — recording device, date, and participant info must be tracked separately
- **No multi-file merging** — each file is treated as one participant

### Best practices

- Include participant ID in the filename: `P001_resting.txt`
- Keep a separate log with recording times, device info, and protocol events
- Verify that values are in the expected unit (ms vs seconds) after import
- For PhysioNet data: check if the dataset provides timestamps in a separate file

---

## Kubios HRV Export (TXT)

Report files exported from Kubios HRV Premium or Scientific edition.

### Setup

1. Place files in `data/raw/kubios/`
2. Kubios exports a `.txt` report with analysis results AND raw RR intervals

### File Format

RRational supports two Kubios export types:

**Report export** (with analysis sections):

```
Kubios HRV Analysis Report
==========================
Software:,Kubios HRV Premium (ver 3.5.0)
Date:,01-Apr-2026
...
RR Intervals (ms)
------------------
832
845
798
```

**Signal/series export** (with comment headers):

```
# SIGNAL/SERIES EXPORT - KUBIOS
# File: recording.txt
832.5
845.1
798.3
```

### What works well

- **Re-analyze Kubios data** in RRational with different parameters
- Report exports include Kubios metadata (software version, correction settings)
- Validated data if Kubios artifact correction was already applied

### Limitations

- **No timestamps** — RR intervals are listed without time information
- **No event markers**
- If Kubios already corrected artifacts, re-correction in RRational may over-correct
- Report format varies between Kubios versions — RRational handles common variants

### Best practices

- Export the **signal/series** format if you want to re-analyze from scratch
- If using the report format, note that Kubios may have already applied correction
- Keep the original recording files as a backup

---

## General Recommendations

### Recording Quality

| Factor | Recommendation |
|--------|---------------|
| **Duration** | Minimum 5 minutes per condition; 2 min absolute minimum |
| **Beat count** | 100+ beats for time-domain; 300+ for frequency-domain |
| **Chest strap** | Preferred over wrist PPG for research accuracy |
| **Movement** | Minimize during recording; seated/supine is ideal |
| **Environment** | Consistent temperature; quiet setting |

### Data Preparation Checklist

- [ ] Files named with participant IDs
- [ ] One folder per data source (e.g., `polar/`, `empatica/`)
- [ ] Protocol events documented (start/end times of conditions)
- [ ] Recording metadata noted (device, date, duration, conditions)

### Participant ID Extraction

RRational extracts participant IDs from filenames using regex patterns:

| Pattern | Example Filename | Extracted ID |
|---------|-----------------|-------------|
| `\d{4}[A-Z]{4}` (default) | `2025-03-15_RR_0001CTRL.csv` | `0001CTRL` |
| `\d+` (digits only) | `participant_042.txt` | `042` |
| `[A-Za-z]+\d+` (letters + digits) | `SUB001_session1.csv` | `SUB001` |

Custom patterns can be configured in Import Settings (Data tab).

### Multi-File Merging

If a participant has multiple recording files (e.g., split sessions), RRational automatically merges them in chronological order. This works for:

- **HRV Logger**: Multiple `_RR_` files with the same participant ID
- **VNS Analyse**: Multiple `.txt` files with the same participant ID

For other formats, each file is treated as a separate participant.
