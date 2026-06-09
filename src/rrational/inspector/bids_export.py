"""BIDS-Physio export for cardiac RR-interval recordings.

Writes one BIDS Physiological-Recording bundle (TSV.GZ + JSON sidecar)
per ``InspectorData`` so RRational outputs can be deposited directly
on OpenNeuro / DataLad / any BIDS-aware repository without manual
post-processing.

Schema reference: https://bids-specification.readthedocs.io/en/stable/
modality-specific-files/physiological-recordings.html — v1.11.1.

Two output files per export::

    sub-<pid>[_ses-<ses>]_task-<task>_recording-cardiac_physio.tsv.gz
    sub-<pid>[_ses-<ses>]_task-<task>_recording-cardiac_physio.json

The TSV.GZ is a header-less, tab-separated, gzipped matrix with one
sample per row and one column per channel. We export a single
``cardiac`` channel containing the RR interval at each beat (in ms).
The sample interval is variable (RR is event-spaced, not regularly
sampled) so ``SamplingFrequency`` in the JSON sidecar is computed as
``len(rr) / total_duration_s`` — the closest constant-rate
approximation the spec allows. ``StartTime`` is the wall-clock onset
of the first beat in epoch seconds.

The export is intentionally side-effect free apart from writing the
two files; it does not touch QSettings, the recipe recorder, or the
project YAML.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:  # pragma: no cover - typing only
    from rrational.inspector.data_loader import InspectorData


# BIDS does not require a hardware sampling frequency for event-spaced
# physio data, but the spec MUST have one — the spec acknowledges this
# limitation explicitly (Section "Physiological recordings"). Using the
# mean beat rate gives a reproducible, non-zero value.
@dataclass
class BIDSExportPaths:
    """Result of :func:`export_bids_physio` — useful for tests + UI."""

    tsv_gz: Path
    json: Path


def _bids_basename(participant_id: str, task: str, session: str | None) -> str:
    """Compose the BIDS file stem (no extension).

    The optional ``ses-`` entity is dropped when ``session`` is empty
    so single-session studies stay flat — matching the BIDS spec's
    "optional entity" rule.
    """
    parts = [f"sub-{participant_id}"]
    if session:
        parts.append(f"ses-{session}")
    parts.extend([f"task-{task}", "recording-cardiac", "physio"])
    return "_".join(parts)


def _sidecar_for(data: "InspectorData") -> dict:
    """Build the BIDS-physio JSON sidecar dict for ``data``."""
    # Coerce NaN gaps out of the timeline before doing duration math —
    # otherwise t_end - t_start blows up to NaN and SamplingFrequency
    # follows. We use the InspectorData properties which already drop
    # NaN samples.
    duration_s = max(1e-9, float(data.t_end) - float(data.t_start))
    n_samples = int(np.isfinite(data.v).sum())
    mean_rate = n_samples / duration_s

    sidecar = {
        "SamplingFrequency": round(mean_rate, 6),
        "StartTime": float(data.t_start),
        "Columns": ["cardiac"],
        "cardiac": {
            "Description": (
                "RR interval (ms) between consecutive R peaks. Variable "
                "sample interval — SamplingFrequency reports the mean "
                "beat rate across the recording."
            ),
            "Units": "ms",
        },
        "RecordingType": "continuous",
    }

    # BIDS-prep fields populated from QW2 metadata when present. Empty
    # strings / None get dropped so the sidecar stays clean.
    if data.experimenter:
        sidecar["Experimenter"] = data.experimenter
    if data.description:
        sidecar["TaskDescription"] = data.description
    if data.device:
        sidecar["Manufacturer"] = data.device
    if data.line_freq is not None:
        sidecar["PowerLineFrequency"] = float(data.line_freq)
    return sidecar


def export_bids_physio(
    data: "InspectorData",
    out_dir: Path,
    *,
    participant_id: str,
    task: str = "rest",
    session: str | None = None,
) -> BIDSExportPaths:
    """Write a BIDS-physio TSV.GZ + JSON sidecar for ``data``.

    Parameters
    ----------
    data
        Source recording — typically the active inspector dataset.
    out_dir
        Destination directory. Created (with parents) if missing.
    participant_id
        BIDS ``sub-<pid>`` value. Caller is responsible for stripping
        characters BIDS rejects (only alphanumerics allowed); we do a
        defensive ``isalnum`` check here and raise rather than write
        an invalid bundle.
    task
        BIDS ``task-<task>`` value. Defaults to ``"rest"`` so a quick
        single-condition export Just Works.
    session
        Optional BIDS ``ses-<ses>`` value. Omitted entirely when None
        or empty.

    Returns
    -------
    BIDSExportPaths
        Both paths echoed so the caller can show them in the status bar.
    """
    if not participant_id.isalnum():
        raise ValueError(
            "BIDS participant ids must be alphanumeric (a-z, A-Z, 0-9). "
            f"Got: {participant_id!r}"
        )
    if not task.isalnum():
        raise ValueError(f"BIDS task labels must be alphanumeric. Got: {task!r}")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = _bids_basename(participant_id, task, session)
    tsv_path = out_dir / f"{stem}.tsv.gz"
    json_path = out_dir / f"{stem}.json"

    # TSV body: one column ("cardiac"), one row per finite RR interval.
    # BIDS physio TSVs are header-less by spec — the column names live
    # in the JSON sidecar's "Columns" array.
    rr_finite = data.v[np.isfinite(data.v)]
    rows = "\n".join(f"{val:.6f}" for val in rr_finite)
    with gzip.open(tsv_path, "wt", encoding="utf-8", newline="\n") as f:
        f.write(rows)
        f.write("\n")

    json_path.write_text(
        json.dumps(_sidecar_for(data), indent=2) + "\n",
        encoding="utf-8",
    )
    return BIDSExportPaths(tsv_gz=tsv_path, json=json_path)
