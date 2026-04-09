# Supported Data Formats

RRational supports data from multiple HRV recording apps and devices:

| Source | Platform | Format | Auto-Detected |
|--------|----------|--------|--------------|
| **HRV Logger** | iOS/Android | CSV | Yes (folder name) |
| **VNS Analyse** | iOS (clinical) | TXT | Yes (folder name) |
| **Polar Sensor Logger / Polar Beat** | iOS/Android | CSV | Yes (folder or content) |
| **Polar Flow** | Web export | TSV | Yes (content) |
| **Empatica E4 / EmbracePlus** | Wristband | CSV (IBI.csv) | Yes (content) |
| **Elite HRV** | iOS/Android | TXT | Yes (folder name) |
| **Kubios HRV** | Desktop | TXT | Yes (content) |
| **Plain text RR** | Any | TXT/CSV | Yes (content) |

### Folder Structure

Place files in subfolders named after the recording app:

```
data/raw/
├── hrv_logger/      → HRV Logger CSV files
├── vns_analyse/     → VNS Analyse TXT files
├── polar/           → Polar Sensor Logger or Flow exports
├── empatica/        → Empatica E4 IBI.csv files
├── elite_hrv/       → Elite HRV exports
└── kubios/          → Kubios HRV report exports
```

RRational auto-detects the format from the folder name. For files with no matching folder name, the file content is analyzed to determine the format automatically.

---

## HRV Logger (CSV)

Place files in your project's `data/raw/hrv_logger/` folder.

### File Naming

HRV Logger creates two files per recording:
- `*_RR_*.csv` — RR interval data
- `*_Events_*.csv` — Event markers (optional)

Example:
```
2025-03-15_RR_0001CTRL.csv
2025-03-15_Events_0001CTRL.csv
```

### RR File Format

```csv
date,rr,since start
2025-03-15 09:00:15.123,823,0
2025-03-15 09:00:15.946,812,823
```

| Column | Description |
|--------|-------------|
| `date` | Timestamp (ISO 8601) |
| `rr` | RR interval in milliseconds |
| `since start` | Cumulative time from recording start (ms) |

### Events File Format

```csv
date,timestamp,annotation,manual
2025-03-15 09:00:15,0,Start Ruhe,false
2025-03-15 09:05:30,315000,Ruhe Ende,false
```

| Column | Description |
|--------|-------------|
| `date` | Timestamp |
| `timestamp` | Offset from recording start (ms) |
| `annotation` | Event label (free text) |
| `manual` | Whether the event was added manually |

---

## VNS Analyse (TXT)

Place files in your project's `data/raw/vns/` folder.

### File Naming

VNS Analyse exports a single `.txt` file per recording. The filename should include date and time:

```
VNS - 0001VNST, 0001VNST (0) - 15.03.2025 09.07 Langzeit, 1h 46min KORRIGIERT.txt
```

### File Structure

VNS files contain multiple sections separated by headers:

```
Korrektur	Aktiv

Hauptparameter der VNS Analyse - Rohwerte (Nicht aktiv)
...

RR-Intervalle - Rohwerte (Nicht aktiv)
0.807	Notiz: Start Ruhe
0.838
0.851

RR-Intervalle - Korrigierte Werte (Aktiv)
0.807
0.838
```

RR values are in **seconds** (not milliseconds). Events are embedded as annotations (`Notiz: ...`) next to RR values.

### Import Settings

In the Data tab, you can choose:
- **Raw values** (`Rohwerte`) — Original uncorrected RR intervals
- **Corrected values** (`Korrigierte Werte`) — VNS-corrected intervals

---

## Polar Sensor Logger / Polar Beat (CSV)

Place files in `data/raw/polar/`.

CSV with two columns:

```
Phone timestamp,RR-interval [ms]
2026-04-01 09:00:00.000,832
2026-04-01 09:00:00.832,845
```

Timestamps are real phone time with millisecond precision. RR intervals in milliseconds.

## Polar Flow HRV Export (TSV)

Tab-separated, no header:

```
0.997	832
1.829	845
2.674	798
```

Column 1: elapsed time in seconds. Column 2: RR interval in ms. No absolute timestamps available.

## Empatica E4 / EmbracePlus (IBI.csv)

Place `IBI.csv` files in `data/raw/empatica/`.

```
1775181600.000000, IBI
7.734375,0.875000
8.609375,0.953125
```

First line: Unix timestamp of recording start. Data: time offset (seconds), IBI duration (seconds). RRational converts to milliseconds automatically.

!!! note
    Empatica uses 1/64 second resolution (PPG-based). Expect slightly lower precision than ECG-based devices.

## Elite HRV / Plain Text RR

Place files in `data/raw/elite_hrv/`. One RR interval per line:

```
832
845
798
```

RRational auto-detects whether values are in milliseconds or seconds based on the value range. Compatible with any tool that exports simple RR interval lists.

## Kubios HRV Export

Place Kubios report files in `data/raw/kubios/`. RRational extracts RR intervals from the "RR Intervals" section of the report, plus analysis metadata.

---

## Participant ID Extraction

RRational extracts participant IDs from filenames using regex patterns. The default pattern matches 4 digits + 4 letters (e.g., `0001CTRL`).

Available patterns can be configured in Import Settings (Data tab). Custom regex is also supported.

---

## Multi-File Merging

If a participant has multiple recording files, RRational automatically merges them in chronological order. This is useful for recordings split across sessions or devices.

For detailed HRV Logger documentation, see [manual_HRV_logger.md](manual_HRV_logger.md).
