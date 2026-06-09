"""PRISM Studio biometrics export for RRational.

Writes a PRISM-compatible biometrics TSV + JSON sidecar so HRV summary
metrics (mean HR, SDNN, RMSSD, pNN50, LF, HF, LF/HF, SD1, SD2, ...)
can be deposited in PRISM-managed psychological study datasets
alongside the rest of a session's biometrics measurements.

PRISM is the **Psychological Research Information System Model**
framework from the MRI-Lab-Graz — a BIDS-add-on for psychological /
behavioural studies. Its ``biometrics`` modality is the only PRISM
file type that meaningfully consumes cardiac-derived data; raw
RR time series stay in the BIDS-physio bucket
(:mod:`rrational.inspector.bids_export`).

Schema reference: https://github.com/MRI-Lab-Graz/prism-studio/blob/
main/docs/specs/biometrics.md

The output is intentionally minimal — one row per recording, with
HRV summary metrics as columns. The sidecar carries
``Technical`` / ``Study`` / ``Metadata`` / per-column blocks that
follow the PRISM schema (verified against the upstream spec doc on
2026-06-09).
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from rrational.inspector.data_loader import InspectorData


# PRISM expects an alphanumeric ``biometric_kind`` label in the filename.
# We use ``hrv`` so a recording's biometrics file ends up named
# ``sub-001_ses-1_task-rest_biometrics-hrv_biometrics.tsv``.
DEFAULT_BIOMETRIC_KIND = "hrv"


@dataclass
class PRISMExportPaths:
    """Result of :func:`export_prism_biometrics` — useful for tests + UI."""

    tsv: Path
    json: Path


# Column → (LongName, Units, DataType) tuples for the biometrics sidecar.
# Only the keys actually emitted in the TSV are described here; the
# exporter looks up each metric in this table to fill the column block.
_COLUMN_META: dict[str, tuple[str, str, str]] = {
    "n_beats": ("Number of RR intervals", "count", "integer"),
    "duration_s": ("Recording duration", "s", "number"),
    "mean_hr_bpm": ("Mean heart rate", "bpm", "number"),
    "mean_nn_ms": ("Mean NN interval", "ms", "number"),
    "sdnn_ms": (
        "Standard deviation of NN intervals (SDNN)",
        "ms",
        "number",
    ),
    "rmssd_ms": (
        "Root mean square of successive NN differences (RMSSD)",
        "ms",
        "number",
    ),
    "pnn50_pct": (
        "Percentage of successive NN intervals differing by > 50 ms (pNN50)",
        "%",
        "number",
    ),
    "lf_ms2": ("Low-frequency power (0.04 - 0.15 Hz)", "ms^2", "number"),
    "hf_ms2": ("High-frequency power (0.15 - 0.40 Hz)", "ms^2", "number"),
    "lf_hf_ratio": ("LF / HF ratio", "ratio", "number"),
    "sd1_ms": ("Poincare SD1", "ms", "number"),
    "sd2_ms": ("Poincare SD2", "ms", "number"),
}


def _prism_basename(
    participant_id: str,
    task: str,
    session: str | None,
    biometric_kind: str,
) -> str:
    """Compose the PRISM biometrics file stem (no extension)."""
    parts = [f"sub-{participant_id}"]
    if session:
        parts.append(f"ses-{session}")
    parts.extend(
        [
            f"task-{task}",
            f"biometrics-{biometric_kind}",
            "biometrics",
        ]
    )
    return "_".join(parts)


def _sidecar_for(
    metrics: dict,
    biometric_kind: str,
    data: "InspectorData",
    software_platform: str,
) -> dict:
    """Build the PRISM biometrics JSON sidecar."""
    column_blocks: dict[str, dict] = {}
    for key in metrics:
        if key not in _COLUMN_META:
            continue
        long_name, units, dtype = _COLUMN_META[key]
        column_blocks[key] = {
            "LongName": long_name,
            "Units": units,
            "DataType": dtype,
        }

    sidecar = {
        # ----- PRISM Technical block -----
        "Technical": {
            "Type": "Biometrics",
            "FileFormat": "tsv",
            "Equipment": data.device or "Unknown",
            "SoftwarePlatform": software_platform,
        },
        # ----- PRISM Study block -----
        "Study": {
            "BiometricName": "Heart rate variability",
            "OriginalName": biometric_kind,
            "Description": (
                "Per-recording HRV summary metrics computed from the "
                "RR-interval time series."
            ),
        },
        # ----- PRISM Metadata block -----
        "Metadata": {
            "SchemaVersion": "1.1.1",
            "CreationDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        },
        # ----- Per-column blocks -----
        **column_blocks,
    }

    # Mirror QW2 BIDS-prep metadata where it overlaps with PRISM's
    # Technical block — keeps both exporters in sync.
    if data.experimenter:
        sidecar["Technical"]["Experimenter"] = data.experimenter
    return sidecar


def export_prism_biometrics(
    metrics: dict,
    out_dir: Path,
    *,
    participant_id: str,
    task: str = "rest",
    session: str | None = None,
    biometric_kind: str = DEFAULT_BIOMETRIC_KIND,
    software_platform: str = "RRational",
    data: "InspectorData | None" = None,
) -> PRISMExportPaths:
    """Write a PRISM biometrics TSV + JSON sidecar for ``metrics``.

    Parameters
    ----------
    metrics
        Mapping ``{column_name: numeric_value}``. Unknown keys are kept
        verbatim in the TSV (PRISM allows arbitrary column names) but
        will lack a column-block in the sidecar.
    out_dir
        Destination directory; created with parents if missing.
    participant_id, task, session
        BIDS entity values; same alphanumeric rule as the BIDS
        exporter — we delegate the check here so a typo surfaces at
        the same boundary instead of mid-write.
    biometric_kind
        Free-text identifier for the biometric "test", e.g. ``hrv``
        (default). Filed into the filename and into ``Study.OriginalName``.
    software_platform
        PRISM's ``Technical.SoftwarePlatform`` field. Defaults to
        ``"RRational"``; callers that ran the Kubios-compatible
        frequency pipeline may want to pass ``"Kubios"`` for clarity.
    data
        Optional :class:`InspectorData` source. Used only to populate
        the ``Equipment`` (= device) and ``Experimenter`` fields. The
        export still runs if ``None`` — those keys get sensible
        fallbacks.

    Returns
    -------
    PRISMExportPaths
        Both written paths echoed so the caller can show them in the
        status bar.
    """
    for label in (participant_id, task, biometric_kind):
        if not str(label).isalnum():
            raise ValueError(
                f"PRISM entity labels must be alphanumeric. Got: {label!r}"
            )

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = _prism_basename(participant_id, task, session, biometric_kind)
    tsv_path = out_dir / f"{stem}.tsv"
    json_path = out_dir / f"{stem}.json"

    # TSV body — one row per recording. Columns and values are emitted
    # in the order they were passed in so callers can curate the layout
    # (e.g. group time-domain / frequency-domain / nonlinear).
    columns = list(metrics.keys())
    with tsv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(columns)
        writer.writerow([_fmt_value(metrics[c]) for c in columns])

    # Sidecar — needs the data object for Equipment / Experimenter only.
    # When the caller is unable to pass it, build a placeholder so the
    # sidecar still passes PRISM validation (Equipment is REQUIRED).
    if data is None:
        from rrational.inspector.data_loader import InspectorData
        import numpy as _np

        data = InspectorData(t=_np.array([0.0]), v=_np.array([0.0]))

    sidecar = _sidecar_for(metrics, biometric_kind, data, software_platform)
    json_path.write_text(
        json.dumps(sidecar, indent=2) + "\n",
        encoding="utf-8",
    )
    return PRISMExportPaths(tsv=tsv_path, json=json_path)


def _fmt_value(v) -> str:
    """Stringify a numeric metric for TSV output without locale drift."""
    if v is None:
        return "n/a"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    try:
        return f"{float(v):.6g}"
    except (TypeError, ValueError):
        return str(v)
