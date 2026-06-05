"""Load .rrational v2 files into the inspector's continuous-timeline format.

Replaces the per-section dict that ``main_window._load_rrational_sections``
used to return. Phase 2 renders the WHOLE recording in a single plot
with section bands as overlays, so we need:

- one ``(t, v)`` array spanning every section, with NaN gaps where
  sections don't touch (PyQtGraph's ``connect="finite"`` breaks the
  line at NaN values)
- per-section metadata (name, t_start, t_end, beat count) for sidebar
  and ``SectionRegion`` overlays
- a deduplicated event list (label + timestamp) for ``EventMarker``
  overlays — events come from each section's ``start_event`` /
  ``end_event``, and the same boundary often appears twice (e.g.
  ``end_event`` of "rest_pre" == ``start_event`` of "first_measurement")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

# Sentinel inserted between sections that aren't contiguous in time —
# tells PyQtGraph's PlotDataItem (with connect="finite") to break the
# line rather than draw a straight segment across the gap.
_GAP_VALUE = np.nan


@dataclass
class SectionMeta:
    """Metadata for one section, used by sidebar and SectionRegion overlay."""

    name: str
    t_start: float  # seconds since epoch
    t_end: float
    beat_count: int


@dataclass
class EventMeta:
    """One named event on the timeline (start or end of a section)."""

    label: str
    t: float  # seconds since epoch


@dataclass
class InspectorData:
    """Everything the inspector needs from one .rrational file.

    ``t`` and ``v`` together form the full concatenated timeline:
    seconds-since-epoch on x, RR-ms on y, with NaN gaps where sections
    don't abut. ``t`` is monotonically non-decreasing (NaN-aware).
    """

    t: np.ndarray  # shape (N,), float64 — seconds since epoch
    v: np.ndarray  # shape (N,), float64 — RR ms, NaN at gaps
    sections: list[SectionMeta] = field(default_factory=list)
    events: list[EventMeta] = field(default_factory=list)

    @property
    def t_start(self) -> float:
        """Timestamp of first non-gap sample."""
        finite = np.isfinite(self.t)
        return float(self.t[finite][0])

    @property
    def t_end(self) -> float:
        """Timestamp of last non-gap sample."""
        finite = np.isfinite(self.t)
        return float(self.t[finite][-1])


@dataclass
class Dataset:
    """One loaded .rrational file: its parsed data + the path it came from.

    MainWindow holds a ``list[Dataset]`` so the user can open multiple
    files in parallel (mnelab-style). ``path`` is None for synthetic
    datasets injected by tests; ``name`` is what shows up in the
    sidebar tree.
    """

    name: str
    data: InspectorData
    path: Path | None = None

    @classmethod
    def from_path(cls, path: Path) -> "Dataset":
        """Auto-detect the file format and wrap it in a Dataset.

        Routes to:
        - ``load_inspector_data`` for ``.rrational`` v2 exports
        - ``load_raw_rr`` for raw RR formats (Polar / Empatica / Kubios /
          Elite HRV / plain text), auto-detected via
          ``io.generic_rr.detect_format``
        """
        if path.suffix.lower() == ".rrational":
            data = load_inspector_data(path)
        else:
            data = load_raw_rr(path)
        return cls(name=path.name, data=data, path=path)


def load_inspector_data(filepath: Path) -> InspectorData:
    """Read a .rrational v2 file and return a flat ``InspectorData``.

    Imports are deferred so the inspector module stays importable in
    environments that don't have NeuroKit2 installed (e.g. when the GUI
    is built without the inspector extra).
    """
    from rrational.gui.rrational_export import (
        load_rrational_v2,
        get_rrational_version,
        RRATIONAL_VERSION_V2,
    )

    version = get_rrational_version(filepath)
    if version != RRATIONAL_VERSION_V2:
        raise ValueError(
            f"Inspector currently supports v2.0 .rrational files only "
            f"(got v{version} for {filepath.name}). Export a v2.0 file via "
            "the Streamlit app's 'Save All Validated Sections' button."
        )

    data = load_rrational_v2(filepath)

    # ------------------------------------------------------------------
    # Pass 1: build per-section arrays + collect events
    # ------------------------------------------------------------------
    section_chunks: list[tuple[SectionMeta, np.ndarray, np.ndarray]] = []
    raw_events: list[EventMeta] = []

    for sec_name, sec in data.sections.items():
        if not sec.nn_intervals or not sec.nn_intervals.data:
            continue
        if not sec.validation or not sec.validation.start_event:
            continue

        start_dt = datetime.fromisoformat(sec.validation.start_event.timestamp)
        start_epoch = start_dt.timestamp()

        # Each row: [offset_ms_from_section_start, rr_ms, is_corrected]
        rows = np.asarray(sec.nn_intervals.data, dtype=np.float64)
        offsets_ms = rows[:, 0]
        rr_ms = rows[:, 1]
        t_section = start_epoch + offsets_ms / 1000.0

        meta = SectionMeta(
            name=sec_name,
            t_start=float(t_section[0]),
            t_end=float(t_section[-1]),
            beat_count=len(rr_ms),
        )
        section_chunks.append((meta, t_section, rr_ms))

        # Section-boundary events. Same boundary often appears as both
        # an end_event of one section and the start_event of the next;
        # we dedupe in the next pass.
        raw_events.append(
            EventMeta(
                label=sec.validation.start_event.label,
                t=start_epoch,
            )
        )
        if sec.validation.end_event:
            end_dt = datetime.fromisoformat(sec.validation.end_event.timestamp)
            raw_events.append(
                EventMeta(
                    label=sec.validation.end_event.label,
                    t=end_dt.timestamp(),
                )
            )

    if not section_chunks:
        # Empty file (no sections with NN data): return empty timeline,
        # caller decides what to show.
        return InspectorData(
            t=np.array([], dtype=np.float64), v=np.array([], dtype=np.float64)
        )

    # ------------------------------------------------------------------
    # Pass 2: sort sections by start time, concat with NaN gap markers
    # ------------------------------------------------------------------
    section_chunks.sort(key=lambda chunk: chunk[0].t_start)

    t_parts: list[np.ndarray] = []
    v_parts: list[np.ndarray] = []
    last_end: float | None = None
    GAP_THRESHOLD_S = 1.0  # touching = no gap; 1 s+ gap = insert NaN break

    for meta, t_sec, v_sec in section_chunks:
        if last_end is not None and (t_sec[0] - last_end) > GAP_THRESHOLD_S:
            # Insert a single NaN sample at the midpoint so the line
            # breaks. Midpoint keeps the x-axis monotonic and gives a
            # visually centred gap.
            gap_t = (last_end + t_sec[0]) / 2.0
            t_parts.append(np.array([gap_t]))
            v_parts.append(np.array([_GAP_VALUE]))
        t_parts.append(t_sec)
        v_parts.append(v_sec)
        last_end = float(t_sec[-1])

    t_full = np.concatenate(t_parts)
    v_full = np.concatenate(v_parts)

    # ------------------------------------------------------------------
    # Pass 3: dedupe events (same label + timestamp within 1 ms)
    # ------------------------------------------------------------------
    seen: set[tuple[str, int]] = set()
    events: list[EventMeta] = []
    for ev in sorted(raw_events, key=lambda e: e.t):
        key = (ev.label, int(ev.t * 1000))  # ms-rounded
        if key in seen:
            continue
        seen.add(key)
        events.append(ev)

    sections_meta = [chunk[0] for chunk in section_chunks]

    return InspectorData(
        t=t_full,
        v=v_full,
        sections=sections_meta,
        events=events,
    )


# ----------------------------------------------------------------------
# Raw RR formats (Polar / Empatica / Kubios / Elite HRV / plain text)
# ----------------------------------------------------------------------
def load_raw_rr(filepath: Path) -> InspectorData:
    """Load a raw RR file into ``InspectorData`` (one synthetic section).

    Auto-detects the format via ``io.generic_rr.detect_format``. Returns
    an InspectorData whose ``sections`` list has exactly one entry named
    ``"recording"`` covering the whole file — Phase 4-Prep will let the
    user split it into named sections via event markers.

    Timestamp source priority (per-beat):
    1. Real wall-clock ``timestamp`` if the format carries it (Polar
       Sensor Logger, Empatica with unix-epoch header, etc.)
    2. ``elapsed_ms`` from recording start (synthesised from file mtime)
    3. Cumulative sum of ``rr_ms`` from t=0 (last-resort)
    """
    from rrational.io.generic_rr import detect_format, load_generic_rr

    fmt = detect_format(filepath)
    if fmt is None:
        raise ValueError(
            f"Could not detect raw RR format for {filepath.name}. "
            "Supported: Polar Sensor Logger, Polar Flow, Empatica E4, "
            "Kubios HRV exports, Elite HRV / plain text."
        )

    recording = load_generic_rr(filepath, source_app=fmt)
    intervals = recording.rr_intervals
    if not intervals:
        return InspectorData(
            t=np.array([], dtype=np.float64), v=np.array([], dtype=np.float64)
        )

    # Build timestamps. If any beat carries a real ``timestamp``, we
    # use that throughout (and trust the source); otherwise fall back to
    # file mtime + elapsed_ms (or cumulative RR if elapsed missing).
    has_real_timestamps = any(iv.timestamp is not None for iv in intervals)

    rr_ms = np.array([iv.rr_ms for iv in intervals], dtype=np.float64)

    if has_real_timestamps:
        # Use real wall-clock timestamps where available; fill any
        # straggler with the previous timestamp + rr_ms.
        ts: list[float] = []
        last: float | None = None
        for iv in intervals:
            if iv.timestamp is not None:
                last = iv.timestamp.timestamp()
            elif last is not None:
                last = last + iv.rr_ms / 1000.0
            else:
                # Shouldn't happen if has_real_timestamps was True, but
                # be defensive.
                last = 0.0
            ts.append(last)
        t = np.array(ts, dtype=np.float64)
    else:
        # Anchor at file mtime so the X-axis shows a plausible date —
        # users don't usually care about absolute time when there's no
        # device clock, but a DateAxis-friendly start beats "1970".
        anchor = filepath.stat().st_mtime
        if intervals[0].elapsed_ms is not None:
            # Use the provided elapsed_ms offsets
            offsets = np.array(
                [iv.elapsed_ms or 0 for iv in intervals], dtype=np.float64
            )
            t = anchor + offsets / 1000.0
        else:
            # Cumulative sum of RR (each beat occurs ``rr_ms`` after the
            # previous one). Offset by zero so t[0] == anchor.
            cum = np.concatenate([[0.0], np.cumsum(rr_ms[:-1])])
            t = anchor + cum / 1000.0

    section = SectionMeta(
        name="recording",
        t_start=float(t[0]),
        t_end=float(t[-1]),
        beat_count=len(rr_ms),
    )

    # Phase 26: paired-file formats (HRV Logger, VNS Analyse) carry
    # event markers in metadata['events']. Convert them to EventMeta
    # so they show up on the plot + in the Events tab.
    raw_events = recording.metadata.get("events") if recording.metadata else None
    events: list[EventMeta] = [EventMeta(label="recording_start", t=float(t[0]))]
    if raw_events:
        for ev in raw_events:
            ts = ev.get("timestamp")
            label = ev.get("label", "event")
            if ts is None:
                continue
            try:
                t_epoch = ts.timestamp() if hasattr(ts, "timestamp") else float(ts)
            except (TypeError, ValueError):
                continue
            events.append(EventMeta(label=str(label), t=float(t_epoch)))

    return InspectorData(
        t=t,
        v=rr_ms,
        sections=[section],
        events=events,
    )
