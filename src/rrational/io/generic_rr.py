"""Generic RR interval file parsers.

Supports: Polar H10, Empatica E4, Elite HRV, Kubios export,
and plain-text RR interval files.
"""

from __future__ import annotations

import csv
import io
import re
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from rrational.io.hrv_logger import RRInterval


@dataclass(slots=True)
class GenericRecording:
    """Recording loaded from a generic RR interval file."""

    participant_id: str
    source_app: str
    rr_intervals: list[RRInterval]
    metadata: dict


def _values_to_rr_intervals(values: list[float]) -> tuple[list[RRInterval], str]:
    """Convert raw numeric values to RRInterval objects with auto unit detection.

    Returns (intervals, detected_unit) where detected_unit is "seconds" or "milliseconds".
    """
    median_val = statistics.median(values)
    is_seconds = median_val < 10

    intervals = []
    elapsed = 0
    for val in values:
        rr_ms = int(round(val * 1000)) if is_seconds else int(round(val))
        intervals.append(RRInterval(timestamp=None, rr_ms=rr_ms, elapsed_ms=elapsed))
        elapsed += rr_ms

    return intervals, "seconds" if is_seconds else "milliseconds"


def detect_format(path: Path) -> str | None:
    """Auto-detect the RR interval file format.

    Returns one of: 'polar_sensor_logger', 'polar_flow', 'empatica',
    'elite_hrv', 'kubios', 'plain_rr', or None if unrecognized.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    lines = text.strip().splitlines()
    if not lines:
        return None

    first = lines[0].strip()

    # Kubios: starts with "Kubios HRV"
    if "kubios hrv" in first.lower():
        return "kubios"

    # Empatica: first line is "unix_timestamp, IBI"
    if ", IBI" in first or ",IBI" in first:
        return "empatica"

    # Polar Sensor Logger: has "Phone timestamp" and "RR-interval" columns
    if "phone timestamp" in first.lower() and "rr" in first.lower():
        return "polar_sensor_logger"

    # Polar Flow: tab-separated, two numeric columns, no header
    if "\t" in first:
        parts = first.split("\t")
        if len(parts) == 2:
            try:
                float(parts[0])
                float(parts[1])
                return "polar_flow"
            except ValueError:
                pass

    # Plain RR: just numbers, one per line (Elite HRV, Kubios plain export)
    # Skip leading comment lines (e.g. Kubios signal/series export with # headers)
    data_lines = [
        l.strip() for l in lines if l.strip() and not l.strip().startswith("#")
    ]
    first_data = data_lines[0] if data_lines else ""
    if re.match(r"^\d+\.?\d*$", first_data):
        # Check a few more lines to confirm
        numeric_count = sum(
            1 for line in data_lines[:10] if re.match(r"^\d+\.?\d*$", line.strip())
        )
        if numeric_count >= 3:
            return "plain_rr"

    return None


def load_generic_rr(
    path: Path,
    participant_id: str = "",
    source_app: str = "",
) -> GenericRecording:
    """Load RR intervals from any supported format.

    Auto-detects format if source_app is not specified.

    Args:
        path: Path to the RR interval file
        participant_id: Participant identifier (extracted from filename if empty)
        source_app: Force a specific format ('polar_sensor_logger', 'polar_flow',
                    'empatica', 'elite_hrv', 'kubios', 'plain_rr').
                    Auto-detected if empty.

    Returns:
        GenericRecording with RR intervals and metadata
    """
    if not participant_id:
        participant_id = path.stem

    fmt = source_app or detect_format(path)
    if fmt is None:
        raise ValueError(f"Could not detect RR interval format in {path.name}")

    parsers = {
        "polar_sensor_logger": _parse_polar_sensor_logger,
        "polar_flow": _parse_polar_flow,
        "empatica": _parse_empatica,
        "elite_hrv": _parse_plain_rr,
        "plain_rr": _parse_plain_rr,
        "kubios": _parse_kubios,
    }

    parser = parsers.get(fmt)
    if parser is None:
        raise ValueError(f"Unknown format: {fmt}")

    rr_intervals, metadata = parser(path)
    metadata["format"] = fmt
    metadata["file"] = path.name

    return GenericRecording(
        participant_id=participant_id,
        source_app=fmt,
        rr_intervals=rr_intervals,
        metadata=metadata,
    )


def _parse_polar_sensor_logger(path: Path) -> tuple[list[RRInterval], dict]:
    """Parse Polar Sensor Logger / Polar Beat CSV.

    Format: Phone timestamp,RR-interval [ms]
    Example: 2026-04-01 09:00:00.000,832
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    intervals = []
    elapsed = 0

    for row in reader:
        # Normalize keys
        norm = {k.strip().lower(): v.strip() for k, v in row.items() if k}

        # Find RR value
        rr_ms = None
        for key in norm:
            if "rr" in key and "interval" in key:
                rr_ms = int(float(norm[key]))
                break
        if rr_ms is None:
            continue

        # Find timestamp
        ts = None
        for key in norm:
            if "timestamp" in key or "time" in key:
                try:
                    ts = datetime.strptime(norm[key][:23], "%Y-%m-%d %H:%M:%S.%f")
                except (ValueError, IndexError):
                    try:
                        ts = datetime.strptime(norm[key][:19], "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        pass
                break

        intervals.append(RRInterval(timestamp=ts, rr_ms=rr_ms, elapsed_ms=elapsed))
        elapsed += rr_ms

    return intervals, {"source": "Polar Sensor Logger"}


def _parse_polar_flow(path: Path) -> tuple[list[RRInterval], dict]:
    """Parse Polar Flow HRV export (headerless TSV).

    Format: elapsed_seconds<TAB>rr_ms
    Example: 0.997\t832
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    intervals = []

    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        try:
            elapsed_s = float(parts[0])
            rr_ms = int(float(parts[1]))
        except ValueError:
            continue

        intervals.append(
            RRInterval(
                timestamp=None,  # No absolute timestamps in Polar Flow export
                rr_ms=rr_ms,
                elapsed_ms=int(elapsed_s * 1000),
            )
        )

    return intervals, {"source": "Polar Flow"}


def _parse_empatica(path: Path) -> tuple[list[RRInterval], dict]:
    """Parse Empatica E4 IBI.csv.

    Format:
      Line 1: unix_start_timestamp, IBI
      Data: time_offset_seconds, ibi_duration_seconds
    Example:
      1775181600.000000, IBI
      7.734375,0.875000
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.strip().splitlines()

    if not lines:
        return [], {}

    # Parse header: extract start timestamp
    header = lines[0].strip()
    start_unix = None
    try:
        start_str = header.split(",")[0].strip()
        start_unix = float(start_str)
    except (ValueError, IndexError):
        pass

    start_dt = datetime.fromtimestamp(start_unix) if start_unix else None
    intervals = []

    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split(",")
        if len(parts) < 2:
            continue
        try:
            offset_s = float(parts[0].strip())
            ibi_s = float(parts[1].strip())
        except ValueError:
            continue

        rr_ms = int(round(ibi_s * 1000))
        ts = start_dt + timedelta(seconds=offset_s) if start_dt else None
        elapsed_ms = int(round(offset_s * 1000))

        intervals.append(RRInterval(timestamp=ts, rr_ms=rr_ms, elapsed_ms=elapsed_ms))

    metadata = {"source": "Empatica E4"}
    if start_dt:
        metadata["recording_start"] = start_dt.isoformat()
    return intervals, metadata


def _parse_plain_rr(path: Path) -> tuple[list[RRInterval], dict]:
    """Parse plain-text RR intervals (one per line).

    Supports: Elite HRV export, Kubios plain export, any single-column RR file.
    Auto-detects ms vs seconds based on value range.

    Format: one number per line (integer or float)
    Example:
      832
      845
      798
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    values = []

    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            values.append(float(line))
        except ValueError:
            continue

    if not values:
        return [], {}

    intervals, unit = _values_to_rr_intervals(values)
    return intervals, {"source": "Plain RR", "detected_unit": unit}


def _parse_kubios(path: Path) -> tuple[list[RRInterval], dict]:
    """Parse Kubios HRV export file.

    Extracts RR intervals from the data section and analysis results from
    the report sections.
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.strip().splitlines()

    metadata = {"source": "Kubios HRV"}
    rr_values = []
    in_rr_section = False

    for line in lines:
        line = line.strip()

        # Extract metadata
        if line.startswith("Software:"):
            metadata["software"] = line.split(",", 1)[-1].strip()
        elif line.startswith("Date:"):
            metadata["date"] = line.split(",", 1)[-1].strip()
        elif line.startswith("Recording:"):
            metadata["recording_length"] = line.split(",", 1)[-1].strip()

        # Detect RR interval section
        if "rr interval" in line.lower():
            in_rr_section = True
            continue

        # End of RR section (next header or empty)
        if in_rr_section:
            if not line or (not line[0].isdigit() and line[0] != "-"):
                # Check if it's a section header
                if line and not re.match(r"^[\d.\-]", line):
                    in_rr_section = False
                    continue
                if not line:
                    continue

            # Parse RR values (comma or space separated on one line, or one per line)
            for part in re.split(r"[,\s]+", line):
                part = part.strip()
                if part:
                    try:
                        rr_values.append(float(part))
                    except ValueError:
                        pass

    # Convert to RRInterval objects
    if not rr_values:
        return [], metadata

    intervals, unit = _values_to_rr_intervals(rr_values)
    if unit == "seconds":
        metadata["detected_unit"] = "seconds"

    return intervals, metadata


# Supported formats for GUI display
SUPPORTED_FORMATS = {
    "polar_sensor_logger": {
        "label": "Polar Sensor Logger / Polar Beat",
        "extensions": [".csv"],
        "description": "CSV with 'Phone timestamp' and 'RR-interval [ms]' columns",
    },
    "polar_flow": {
        "label": "Polar Flow HRV Export",
        "extensions": [".csv", ".txt"],
        "description": "Tab-separated: elapsed_seconds, rr_ms (no header)",
    },
    "empatica": {
        "label": "Empatica E4 / EmbracePlus",
        "extensions": [".csv"],
        "description": "IBI.csv with unix timestamp header, offset + IBI in seconds",
    },
    "elite_hrv": {
        "label": "Elite HRV / Plain Text RR",
        "extensions": [".txt", ".csv", ".dat"],
        "description": "One RR interval per line (ms or seconds, auto-detected)",
    },
    "kubios": {
        "label": "Kubios HRV Export",
        "extensions": [".txt"],
        "description": "Kubios HRV Premium/Scientific report with RR data section",
    },
}
