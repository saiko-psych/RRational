"""Inspector → .rrational v2 export.

Builds a :class:`RRationalExportV2` from the inspector's in-memory
state and hands it to :func:`save_rrational_v2` from
``gui.rrational_export``. Keeps the inspector free of YAML-writing
details — the format already has a single source of truth in the GUI
backend.

What gets mapped:

- Each :class:`SectionMeta` becomes one entry in
  ``RRationalExportV2.sections`` with definition + validation built
  from start/end timestamps.
- NN intervals per section are pulled from the slice of ``data.t``
  inside the section's time range. If a :class:`PreprocessingResult`
  is provided, corrected values + per-beat ``was_corrected`` flags
  come from there; otherwise the raw RR values are used as-is and
  every flag is ``False``.
- Artifact detection metadata (method, count, by_type, rate) is
  mapped section-by-section by intersecting the global artifact
  indices with the section's beat range.
- Quality is computed from the per-section artifact rate using the
  same Quigley 2024 thresholds as the GUI export path.
- Audit trail: a single entry stamped with the export timestamp.

What stays empty (the inspector doesn't surface these yet):

- exclusion zones, recording gaps, manual artifacts.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import numpy as np

from rrational.gui.rrational_export import (
    AnalysisSegmentV2,
    ArtifactDetectionV2,
    AuditEntryV2,
    EventChoiceV2,
    FinalArtifactsV2,
    ManualArtifactsV2,
    MetadataV2,
    NNCorrectionV2,
    NNIntervalsDataV2,
    QualityV2,
    RRationalExportV2,
    SectionDefinitionV2,
    SectionExportV2,
    SectionValidationV2,
    get_quality_grade,
    get_quigley_recommendation,
    save_rrational_v2,
)

if TYPE_CHECKING:
    from pathlib import Path

    from rrational.inspector.data_loader import InspectorData
    from rrational.inspector.preprocessing import PreprocessingResult


def _epoch_to_iso(t: float) -> str:
    return datetime.fromtimestamp(t).isoformat()


def _slice_section_indices(
    data: "InspectorData", t_start: float, t_end: float
) -> tuple[int, int]:
    """Return (start_idx, end_idx_exclusive) for beats inside [t_start, t_end]."""
    in_section = (data.t >= t_start) & (data.t <= t_end)
    if not in_section.any():
        return 0, 0
    idxs = np.where(in_section)[0]
    return int(idxs[0]), int(idxs[-1]) + 1


def _build_section_export(
    data: "InspectorData",
    section,
    *,
    preprocessing: "PreprocessingResult | None",
    timestamp: str,
) -> SectionExportV2:
    """Build one SectionExportV2 from a SectionMeta + the dataset."""
    start_idx, end_idx = _slice_section_indices(data, section.t_start, section.t_end)
    beat_count = end_idx - start_idx

    # Build raw NN data: [[ms_from_section_start, nn_ms, was_corrected], ...]
    rr_slice = data.v[start_idx:end_idx]
    t_slice = data.t[start_idx:end_idx]
    if beat_count > 0:
        t0 = t_slice[0]
        ts_from_start_ms = ((t_slice - t0) * 1000).astype(int).tolist()
        # If preprocessing is present, swap in corrected values where available
        # and mark them.
        if (
            preprocessing is not None
            and preprocessing.corrected_v is not None
            and len(preprocessing.corrected_v) == len(data.v)
        ):
            corrected_slice = preprocessing.corrected_v[start_idx:end_idx]
            # was_corrected per beat: True where the corrected value differs
            # from the raw value
            was_corrected_arr = ~np.isclose(rr_slice, corrected_slice, equal_nan=True)
            nn_data = [
                [
                    int(ts),
                    float(corrected_slice[i]),
                    bool(was_corrected_arr[i]),
                ]
                for i, ts in enumerate(ts_from_start_ms)
            ]
            corrections_list = [
                {
                    "nn_idx": int(i),
                    "original_rr_ms": float(rr_slice[i]),
                    "corrected_nn_ms": float(corrected_slice[i]),
                }
                for i in range(len(rr_slice))
                if was_corrected_arr[i]
            ]
        else:
            nn_data = [
                [int(ts), float(rr_slice[i]), False]
                for i, ts in enumerate(ts_from_start_ms)
            ]
            corrections_list = []
    else:
        nn_data = []
        corrections_list = []

    # Artifact detection — restrict to this section's beat range
    artifact_detection = None
    final_artifacts = FinalArtifactsV2()
    nn_correction = NNCorrectionV2()

    if preprocessing is not None:
        # Cast each index to plain Python int — preprocessing.indices is
        # a numpy.int64 array and yaml.dump emits Python-object tags for
        # numpy scalars that yaml.safe_load then refuses on read-back.
        section_artifact_idxs = sorted(
            int(i - start_idx)
            for i in preprocessing.indices
            if start_idx <= i < end_idx
        )
        section_rate = float(
            len(section_artifact_idxs) / beat_count if beat_count > 0 else 0.0
        )
        # PreprocessingResult.by_type is aggregate (str → total count),
        # not per-index. We can't truthfully attribute counts to a
        # specific section, so we leave the per-section breakdown
        # empty; the global count is preserved via detected_count.
        section_by_type: dict[str, int] = {}
        artifact_detection = ArtifactDetectionV2(
            method="lipponen2019",  # NK2 Kubios = Lipponen & Tarvainen 2019
            threshold_pct=None,
            run_at=timestamp,
            detected_count=len(section_artifact_idxs),
            by_type=section_by_type,
            artifact_rate_detected=section_rate,
        )
        final_artifacts = FinalArtifactsV2(
            indices=section_artifact_idxs,
            count=len(section_artifact_idxs),
            rate=section_rate,
        )
        if corrections_list:
            nn_correction = NNCorrectionV2(
                method="kubios",
                corrected_at=timestamp,
                intervals_corrected=len(corrections_list),
            )

    # Quality
    artifact_rate = final_artifacts.rate
    duration_s = float(section.t_end - section.t_start)
    quality = QualityV2(
        grade=get_quality_grade(artifact_rate),
        recommendation=get_quigley_recommendation(artifact_rate, beat_count),
        usable_beats=beat_count,
        usable_duration_s=duration_s,
        meets_time_domain_min=beat_count >= 100,
        meets_freq_domain_min=beat_count >= 300 and duration_s >= 120,
    )

    # Single data-only analysis segment (no exclusion zones in the
    # inspector yet).
    analysis_segments: list[AnalysisSegmentV2] = []
    if beat_count > 0:
        analysis_segments.append(
            AnalysisSegmentV2(
                segment_id=f"{section.name}_seg1",
                type="data",
                start_timestamp=_epoch_to_iso(section.t_start),
                end_timestamp=_epoch_to_iso(section.t_end),
                duration_s=duration_s,
                nn_count=beat_count,
                nn_start_idx=0,
                nn_end_idx=beat_count - 1,
            )
        )

    return SectionExportV2(
        definition=SectionDefinitionV2(
            start_event=f"{section.name}_start",
            end_event=f"{section.name}_end",
            label=section.name,
        ),
        validation=SectionValidationV2(
            validated_at=timestamp,
            start_event=EventChoiceV2(
                label=f"{section.name}_start",
                timestamp=_epoch_to_iso(section.t_start),
                beat_idx=start_idx,
            ),
            end_event=EventChoiceV2(
                label=f"{section.name}_end",
                timestamp=_epoch_to_iso(section.t_end),
                beat_idx=max(0, end_idx - 1),
            ),
            total_duration_s=duration_s,
            total_beat_count=beat_count,
        ),
        exclusion_zones=[],
        gaps=[],
        artifact_detection=artifact_detection,
        manual_artifacts=ManualArtifactsV2(),
        final_artifacts=final_artifacts,
        quality=quality,
        nn_correction=nn_correction,
        analysis_segments=analysis_segments,
        nn_intervals=NNIntervalsDataV2(data=nn_data, corrections=corrections_list),
    )


def build_v2_export(
    data: "InspectorData",
    *,
    participant_id: str,
    preprocessing: "PreprocessingResult | None" = None,
    source_path: "Path | None" = None,
    source_app: str = "RRational",
) -> RRationalExportV2:
    """Build a complete :class:`RRationalExportV2` from inspector state.

    Pure function — does not touch disk. The caller hands the result
    to :func:`save_rrational_v2` (or persists differently if desired).
    """
    timestamp = datetime.now().isoformat()

    sections: dict[str, SectionExportV2] = {}
    for section in data.sections:
        sections[section.name] = _build_section_export(
            data, section, preprocessing=preprocessing, timestamp=timestamp
        )

    source_files: list[dict] = []
    if source_path is not None:
        source_files.append({"path": str(source_path), "type": "raw"})

    metadata = MetadataV2(
        participant_id=participant_id,
        created_at=timestamp,
        last_modified=timestamp,
        source_app=source_app,
        source_files=source_files,
        recording_info={
            "start": _epoch_to_iso(float(data.t[0])) if len(data.t) else "",
            "end": _epoch_to_iso(float(data.t[-1])) if len(data.t) else "",
            "total_beats": int(len(data.t)),
            "total_duration_s": float(data.t[-1] - data.t[0])
            if len(data.t) >= 2
            else 0.0,
        },
        software_versions={"rrational_inspector": "phase-6"},
    )

    audit_trail = [
        AuditEntryV2(
            step=1,
            action="exported_from_inspector",
            timestamp=timestamp,
            details=(
                f"Exported {len(sections)} section(s) from the PyQt inspector"
                + (
                    " with artifact-correction applied"
                    if preprocessing is not None
                    else " (raw RR, no artifact detection)"
                )
            ),
        )
    ]

    return RRationalExportV2(
        metadata=metadata,
        sections=sections,
        exclusion_zones_summary=[],
        recording_gaps=[],
        audit_trail=audit_trail,
    )


def export_inspector_to_rrational(
    data: "InspectorData",
    out_path: "Path",
    *,
    participant_id: str,
    preprocessing: "PreprocessingResult | None" = None,
    source_path: "Path | None" = None,
) -> RRationalExportV2:
    """Build + save in one call. Returns the export object for inspection."""
    export = build_v2_export(
        data,
        participant_id=participant_id,
        preprocessing=preprocessing,
        source_path=source_path,
    )
    save_rrational_v2(export, out_path)
    return export
