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
from datetime import datetime, timedelta, timezone
from pathlib import Path

from rrational.io.hrv_logger import RRInterval


def _read_text_with_fallback(path: Path) -> str:
    """Read ``path`` trying UTF-8-sig → UTF-8 → Windows-1252 → Latin-1.

    Round 28 — every loader previously used ``errors="ignore"`` on UTF-8,
    which silently dropped every umlaut-bearing byte for the
    German-market VNS Analyse exports + Windows-1252 CSVs from Excel.
    Headers with participant names or notes were corrupted but no
    error fired, so callers believed the load succeeded. The new
    fallback chain decodes cleanly across all three common encodings.
    """
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    # Last resort: utf-8 with replacement so the caller still gets a
    # string (some bytes garbled) instead of an exception bubbling up.
    return path.read_text(encoding="utf-8", errors="replace")


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
    'elite_hrv', 'kubios', 'plain_rr', 'hrv_logger', 'vns_analyse',
    'bids_physio', or None if unrecognized.
    """
    # BIDS-physio detection happens FIRST because it is the only
    # extension-driven format we support (everything else is a plain
    # text/CSV the read_text call below can sniff). We require the
    # canonical ``recording-cardiac_physio.tsv.gz`` BIDS suffix so an
    # arbitrary ``.tsv.gz`` from somewhere else does not get mistaken
    # for a BIDS bundle.
    name_lower = path.name.lower()
    if name_lower.endswith("_physio.tsv.gz") and "recording-cardiac" in name_lower:
        sidecar = path.with_name(path.name[: -len(".tsv.gz")] + ".json")
        if sidecar.exists():
            return "bids_physio"

    try:
        text = _read_text_with_fallback(path)
    except Exception:
        return None

    lines = text.strip().splitlines()
    if not lines:
        return None

    first = lines[0].strip()
    lower_first = first.lower()

    # VNS Analyse: text file with German section headers like
    # "RR-Intervalle - Rohwerte" or "RR-Intervalle - Korrigierte Werte",
    # or English equivalents from older exports. Also recognizes
    # "mainParameterRMSSD" / "Hauptparameter" which only VNS exports use.
    text_lower = text[:4096].lower()
    if any(
        marker in text_lower
        for marker in (
            "rr-intervalle",
            "mainparameterrmssd",
            "hauptparameter der vns",
            "rr intervals (uncorrected)",
            "rr intervals (corrected)",
            "hb intervals",
            "vegetatives nervensystem",
        )
    ):
        return "vns_analyse"

    # HRV Logger: CSV with EITHER "date,rr,since start" (classic) OR
    # "timestamp, rr, since_start" (newer unix-ms format). Also detect
    # by filename — '_RR' / '_RRIntervals' is the canonical naming.
    cols = [c.strip().lower() for c in first.split(",")]
    if "rr" in cols and ("date" in cols or "timestamp" in cols):
        return "hrv_logger"

    # HRV Logger Events file: opened directly — auto-find the RR pair.
    stem_lower = path.stem.lower()
    if "_events" in stem_lower and (
        "timestamp" in lower_first or "annotation" in lower_first
    ):
        return "hrv_logger_events"

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
    *,
    use_corrected: bool = True,
) -> GenericRecording:
    """Load RR intervals from any supported format.

    Auto-detects format if source_app is not specified.

    Args:
        path: Path to the RR interval file
        participant_id: Participant identifier (extracted from filename if empty)
        source_app: Force a specific format ('polar_sensor_logger', 'polar_flow',
                    'empatica', 'elite_hrv', 'kubios', 'plain_rr').
                    Auto-detected if empty.
        use_corrected: For VNS Analyse files only — when True (default),
                      load the corrected/cleaned RR series VNS exports
                      alongside the raw values. Ignored for every other
                      format.

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
        "hrv_logger": _parse_hrv_logger,
        "vns_analyse": _parse_vns_analyse,
        "bids_physio": _parse_bids_physio,
    }

    # Phase 26: if the user opened an Events.csv directly, point them
    # to the matching RR file.
    if fmt == "hrv_logger_events":
        rr_companion = _find_hrv_logger_rr_companion(path)
        if rr_companion is not None:
            return load_generic_rr(
                rr_companion, participant_id, "hrv_logger", use_corrected=use_corrected
            )
        raise ValueError(
            f"{path.name} is an HRV Logger Events file. Could not find the "
            "matching '_RR' or '_RRIntervals' file in the same folder. "
            "Open the RR file instead — the Events file is loaded "
            "automatically as event markers."
        )

    parser = parsers.get(fmt)
    if parser is None:
        raise ValueError(f"Unknown format: {fmt}")

    # D3 — only the VNS parser honours use_corrected; others would
    # raise TypeError on the keyword arg.
    if fmt == "vns_analyse":
        rr_intervals, metadata = _parse_vns_analyse(path, use_corrected=use_corrected)
    else:
        rr_intervals, metadata = parser(path)
    metadata["format"] = fmt
    metadata["file"] = path.name

    return GenericRecording(
        participant_id=participant_id,
        source_app=fmt,
        rr_intervals=rr_intervals,
        metadata=metadata,
    )


def _parse_bids_physio(path: Path) -> tuple[list[RRInterval], dict]:
    """Read a BIDS-spec cardiac physio TSV.GZ + matching JSON sidecar.

    The TSV is header-less, one column (``cardiac``) of RR intervals in
    ms (RRational's BIDS export keeps that shape, and the BIDS spec
    leaves column ordering / count to the sidecar's ``Columns`` array
    so we honour it). The sidecar's ``StartTime`` becomes the recording
    epoch anchor; subsequent beat timestamps are reconstructed by
    cumulative RR sum because BIDS physio for event-spaced data does
    not carry per-beat times.
    """
    import gzip
    import json
    from datetime import datetime

    sidecar_path = path.with_name(path.name[: -len(".tsv.gz")] + ".json")
    sidecar: dict = {}
    if sidecar_path.exists():
        try:
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            sidecar = {}

    columns = sidecar.get("Columns") or ["cardiac"]
    try:
        cardiac_idx = columns.index("cardiac")
    except ValueError:
        # No explicit cardiac column — fall back to column 0.
        cardiac_idx = 0

    intervals: list[RRInterval] = []
    elapsed = 0
    start_time = sidecar.get("StartTime")
    base_ts = None
    if isinstance(start_time, (int, float)):
        base_ts = datetime.fromtimestamp(float(start_time), tz=timezone.utc)

    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t") if "\t" in line else [line]
            if cardiac_idx >= len(parts):
                continue
            try:
                rr_ms = int(round(float(parts[cardiac_idx])))
            except ValueError:
                continue
            ts = (
                datetime.fromtimestamp(
                    base_ts.timestamp() + elapsed / 1000.0,
                    tz=timezone.utc,
                )
                if base_ts is not None
                else None
            )
            intervals.append(RRInterval(timestamp=ts, rr_ms=rr_ms, elapsed_ms=elapsed))
            elapsed += rr_ms

    metadata = {
        "sidecar": sidecar,
        "source_format": "bids_physio",
        "task": sidecar.get("TaskName"),
        "manufacturer": sidecar.get("Manufacturer"),
        "experimenter": sidecar.get("Experimenter"),
    }
    return intervals, metadata


def _parse_polar_sensor_logger(path: Path) -> tuple[list[RRInterval], dict]:
    """Parse Polar Sensor Logger / Polar Beat CSV.

    Format: Phone timestamp,RR-interval [ms]
    Example: 2026-04-01 09:00:00.000,832
    """
    text = _read_text_with_fallback(path)
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
    text = _read_text_with_fallback(path)
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
    text = _read_text_with_fallback(path)
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

    # Round 30 — explicit UTC so downstream wall-clock conversions don't
    # drift by an hour across DST transitions; naive fromtimestamp uses
    # local time which silently shifts on every spring-/fall-forward.
    start_dt = (
        datetime.fromtimestamp(start_unix, tz=timezone.utc) if start_unix else None
    )
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
    text = _read_text_with_fallback(path)
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
    text = _read_text_with_fallback(path)
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


# Phase 26 — HRV Logger / VNS Analyse parsers using the existing
# Streamlit-shared loaders. We thin-wrap them so generic_rr can serve
# both single-file formats (Polar/Empatica/Kubios) AND paired/sectioned
# formats (HRV Logger RR+Events, VNS Analyse with embedded sections)
# behind one ``load_generic_rr`` entry point.
_HRV_RR_TOKENS = ("RRIntervals", "RR_Intervals", "RR")
_HRV_EVENT_TOKENS = ("Events", "EventMarkers")


def _find_hrv_logger_rr_companion(events_path: Path) -> Path | None:
    """Given an HRV Logger Events file, find the matching RR file.

    Handles BOTH naming patterns observed in real exports:
      ``{prefix}_Events.csv`` + ``{prefix}_RRIntervals.csv``
      ``{date}_Events_{participant}.csv`` + ``{date}_RR_{participant}.csv``
    Case-insensitive token replacement.
    """
    return _find_companion(events_path, _HRV_EVENT_TOKENS, _HRV_RR_TOKENS)


def _find_hrv_logger_events_companion(rr_path: Path) -> Path | None:
    """Inverse of :func:`_find_hrv_logger_rr_companion`."""
    return _find_companion(rr_path, _HRV_RR_TOKENS, _HRV_EVENT_TOKENS)


def _find_companion(
    src_path: Path,
    from_tokens: tuple[str, ...],
    to_tokens: tuple[str, ...],
) -> Path | None:
    """Replace a token in the filename and return the path if it exists.

    Tries every (from, to) combination, case-insensitive matching but
    preserving original surrounding case in the new filename.
    """
    stem = src_path.stem
    parent = src_path.parent
    suffix = src_path.suffix
    stem_lower = stem.lower()
    for from_tok in from_tokens:
        ft = from_tok.lower()
        # Find the token bracketed by underscores or at the boundary.
        for sep_l, sep_r in (("_", "_"), ("_", ""), ("", "_")):
            needle = f"{sep_l}{ft}{sep_r}"
            idx = stem_lower.find(needle)
            if idx < 0:
                continue
            for to_tok in to_tokens:
                replacement = f"{sep_l}{to_tok}{sep_r}"
                new_stem = stem[:idx] + replacement + stem[idx + len(needle) :]
                cand = parent / f"{new_stem}{suffix}"
                if cand.exists():
                    return cand
    return None


def _parse_hrv_logger(path: Path) -> tuple[list[RRInterval], dict]:
    """Load HRV Logger RR file — supports BOTH legacy + unix-ms formats.

    Legacy: ``date, rr, since start`` (datetime strings) — delegates to
    the existing :func:`rrational.io.hrv_logger.load_rr_intervals`.
    New: ``timestamp, rr, since_start`` (unix-ms integers) — parsed
    inline since the shared loader currently rejects it.

    Also auto-loads the companion Events.csv if found.
    """
    from datetime import datetime

    from rrational.io.hrv_logger import load_rr_intervals

    # Round 30 — use the established _read_text_with_fallback helper here
    # as well; the previous errors="ignore" silently dropped umlauts in
    # cp1252 German clinical files. R28 added the helper but missed these
    # HRV Logger sites.
    text = _read_text_with_fallback(path)
    header_line = text.split("\n", 1)[0] if text else ""
    cols = [c.strip().lower() for c in header_line.strip().split(",")]
    is_unix_ms = "timestamp" in cols and "date" not in cols

    intervals: list[RRInterval] = []
    if is_unix_ms:
        import csv

        ts_idx = cols.index("timestamp")
        rr_idx = cols.index("rr") if "rr" in cols else cols.index("rr (ms)")
        ss_idx = cols.index("since_start") if "since_start" in cols else None
        with io.StringIO(text, newline="") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if not row or len(row) <= max(ts_idx, rr_idx):
                    continue
                try:
                    ts_ms = int(float(row[ts_idx].strip()))
                    # Round 28 — RRInterval.rr_ms is declared ``int`` in
                    # the slots dataclass; storing float here silently
                    # broke every downstream ``%d`` format and any int
                    # arithmetic. Every other parser uses int(round(...))
                    # — match that contract.
                    rr_ms = int(round(float(row[rr_idx].strip())))
                except (ValueError, IndexError):
                    continue
                elapsed = None
                if ss_idx is not None and ss_idx < len(row):
                    try:
                        elapsed = int(float(row[ss_idx].strip()))
                    except ValueError:
                        elapsed = None
                intervals.append(
                    RRInterval(
                        timestamp=datetime.fromtimestamp(
                            ts_ms / 1000.0, tz=timezone.utc
                        ),
                        rr_ms=rr_ms,
                        elapsed_ms=elapsed,
                    )
                )
    else:
        intervals, _row_count, _dupes = load_rr_intervals(path)

    metadata: dict = {}
    ev_path = _find_hrv_logger_events_companion(path)
    if ev_path is not None:
        try:
            events = _load_events_flexible(ev_path)
            metadata["events"] = events
            metadata["events_file"] = ev_path.name
        except Exception as exc:
            # Round 30 — bare ``pass`` previously hid every failure (malformed
            # companion file, missing column, IO error) and the user only
            # noticed via "events missing" with no log. Log + flag on metadata.
            import logging

            metadata["events_load_error"] = f"{type(exc).__name__}: {exc}"
            logging.getLogger("rrational.io.generic_rr").warning(
                "Failed to load events companion %s: %s",
                ev_path.name,
                exc,
                exc_info=True,
            )
    return intervals, metadata


def _load_events_flexible(ev_path: Path) -> list[dict]:
    """Load an HRV Logger Events file, supporting both header schemas.

    Legacy: ``annotation, timestamp`` (datetime strings) via the shared
    loader. New: ``timestamp, label`` (unix-ms) or just ``timestamp``
    parsed inline.
    """
    import csv
    from datetime import datetime

    from rrational.io.hrv_logger import load_events

    # Round 30 — encoding fallback (was errors="ignore" silently dropping bytes).
    ev_text = _read_text_with_fallback(ev_path)
    header_line = ev_text.split("\n", 1)[0] if ev_text else ""
    cols = [c.strip().lower() for c in header_line.strip().split(",")]
    if "annotation" in cols and "timestamp" in cols:
        try:
            evs = load_events(ev_path)
            return [
                {"label": e.label, "timestamp": e.timestamp}
                for e in evs
                if e.timestamp is not None
            ]
        except Exception:
            return []
    if "timestamp" in cols:
        ts_idx = cols.index("timestamp")
        label_idx = cols.index("label") if "label" in cols else None
        out: list[dict] = []
        with io.StringIO(ev_text, newline="") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if not row:
                    continue
                try:
                    ts_ms = int(float(row[ts_idx].strip()))
                except (ValueError, IndexError):
                    continue
                label = "event"
                if label_idx is not None and label_idx < len(row):
                    label = row[label_idx].strip() or "event"
                out.append(
                    {
                        "label": label,
                        "timestamp": datetime.fromtimestamp(
                            ts_ms / 1000.0, tz=timezone.utc
                        ),
                    }
                )
        return out
    return []


def _parse_vns_analyse(
    path: Path, *, use_corrected: bool = True
) -> tuple[list[RRInterval], dict]:
    """Load a VNS Analyse text file via the shared loader.

    ``use_corrected`` defaults to True so the inspector's Open dialog
    matches the most common scientific workflow (use the artefact-
    corrected RR column when one is available). Set to False to pull
    the raw RR section instead.
    """
    from rrational.io.vns_analyse import _load_single_vns_file

    intervals, events, header_info = _load_single_vns_file(
        path, use_corrected=use_corrected
    )
    metadata: dict = dict(header_info)
    metadata["use_corrected"] = use_corrected
    metadata["events"] = [
        {"label": e.label, "timestamp": e.timestamp}
        for e in events
        if e.timestamp is not None
    ]
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
