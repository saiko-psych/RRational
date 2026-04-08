# Supported Data Formats

RRational supports data from two popular HRV recording apps:

| App | Platform | Format | Link |
|-----|----------|--------|------|
| **HRV Logger** | iOS/Android | CSV | [hrv.tools](https://www.hrv.tools/hrv-logger-faq.html) |
| **VNS Analyse** | iOS | TXT | [App Store](https://apps.apple.com/de/app/vns-analyse/id990667927) |

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

## Participant ID Extraction

RRational extracts participant IDs from filenames using regex patterns. The default pattern matches 4 digits + 4 letters (e.g., `0001CTRL`).

Available patterns can be configured in Import Settings (Data tab). Custom regex is also supported.

---

## Multi-File Merging

If a participant has multiple recording files, RRational automatically merges them in chronological order. This is useful for recordings split across sessions or devices.

For detailed HRV Logger documentation, see [manual_HRV_logger.md](manual_HRV_logger.md).
