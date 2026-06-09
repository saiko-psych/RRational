"""Recordable user-action dataclasses for the inspector history log.

Each subclass of :class:`Action` is a frozen dataclass that
1. captures the inputs of one GUI-driven mutation (open project, load
   file, detect artifacts, save export, ...), and
2. implements :meth:`to_python` so the recorded action can be replayed
   from a generated ``.py`` script.

The pattern mirrors MNELAB, which stores its history as raw Python
strings — we keep the strings on the boundary (``to_python``) but
hold structured data in memory so callers can introspect / filter the
log without parsing text. None of the ``to_python`` outputs import
their own ``pathlib.Path`` symbol; the serialiser's script header
imports ``Path`` once at the top.
"""

from __future__ import annotations

from dataclasses import dataclass


class Action:
    """Marker base class for recordable history actions.

    Subclasses MUST be frozen dataclasses and MUST implement
    :meth:`to_python`. The base class is intentionally abstract — it
    exists only so callers can type-check against a single supertype.
    """

    def to_python(self) -> str:  # pragma: no cover - abstract
        raise NotImplementedError(f"{type(self).__name__} must implement to_python()")


@dataclass(frozen=True)
class OpenProject(Action):
    """User opened (or switched to) a project directory."""

    path: str  # absolute string path to the project root

    def to_python(self) -> str:
        return (
            "from rrational.inspector import persistence\n"
            f"persistence.set_active_project_config_dir("
            f"Path({self.path!r}) / 'config')"
        )


@dataclass(frozen=True)
class LoadRecording(Action):
    """User opened a recording file (raw or .rrational v2)."""

    path: str
    fmt: str | None = None  # auto-detect when None

    def to_python(self) -> str:
        # Also bind ``rr_intervals`` so the DetectArtifacts block that
        # typically follows can call clean_rr_intervals(rr_intervals,
        # ...) without re-importing or re-attribute-walking.
        if self.fmt:
            return (
                "from rrational.io.generic_rr import load_generic_rr\n"
                f"recording = load_generic_rr("
                f"Path({self.path!r}), source_app={self.fmt!r})\n"
                "rr_intervals = recording.rr_intervals"
            )
        return (
            "from rrational.io.generic_rr import detect_format, load_generic_rr\n"
            f"_p = Path({self.path!r})\n"
            "recording = load_generic_rr(_p, source_app=detect_format(_p))\n"
            "rr_intervals = recording.rr_intervals"
        )


@dataclass(frozen=True)
class DetectArtifacts(Action):
    """One round of artifact detection on the currently-loaded recording."""

    method: str  # e.g. "neurokit2_lipponen" / "kubios"
    pid: str | None = None  # optional context for batch flows

    def to_python(self) -> str:
        return (
            "from rrational.cleaning.rr import clean_rr_intervals, CleaningConfig\n"
            f"_config = CleaningConfig()  # method={self.method!r}\n"
            "cleaned = clean_rr_intervals(rr_intervals, _config)"
        )


@dataclass(frozen=True)
class AddExclusionZone(Action):
    """User drew a manual exclusion window on the timeline."""

    pid: str
    t_start: float
    t_end: float
    reason: str = ""

    def to_python(self) -> str:
        # Persisted via the inspector's exclusion_persistence module —
        # the recipe instantiates a real ExclusionZone and saves it via
        # the same code path the GUI uses on drag-release.
        return (
            "from rrational.inspector.exclusion_persistence import (\n"
            "    ExclusionZone,\n"
            "    load_exclusion_zones,\n"
            "    save_exclusion_zones,\n"
            ")\n"
            f"_pid = {self.pid!r}\n"
            "_existing = load_exclusion_zones(_pid)\n"
            "_existing.append(ExclusionZone(\n"
            f"    t_start={self.t_start}, t_end={self.t_end},\n"
            f"    reason={self.reason!r},\n"
            "))\n"
            "save_exclusion_zones(_pid, _existing)"
        )


@dataclass(frozen=True)
class AddAnnotation(Action):
    """User attached a free-text annotation at a timestamp."""

    pid: str
    t: float
    label: str

    def to_python(self) -> str:
        # Persist through the same on-disk path the GUI uses so the
        # recipe truly reproduces session state — not just a dataclass
        # instance left dangling in memory.
        return (
            "from rrational.inspector.annotations import Annotation\n"
            "from rrational.inspector.annotation_persistence import (\n"
            "    load_annotations,\n"
            "    save_annotations,\n"
            ")\n"
            f"_pid = {self.pid!r}\n"
            "_existing = load_annotations(_pid)\n"
            f"_existing.append(Annotation.create(t={self.t}, "
            f"text={self.label!r}))\n"
            "save_annotations(_pid, _existing)"
        )


@dataclass(frozen=True)
class SaveRRationalExport(Action):
    """User wrote the active dataset out as a .rrational v2 file."""

    pid: str
    section: str
    out_path: str
    n_beats: int

    def to_python(self) -> str:
        # ``inspector_data`` is whatever the previous DetectArtifacts /
        # cleaning step produced. We leave the body referencing it as a
        # symbol so a user adapting the recipe can plug in their own
        # InspectorData; the trailing comment makes the assumption
        # explicit instead of letting it surface as a NameError after
        # the script is half-way through.
        return (
            "from rrational.inspector.export import (\n"
            "    export_inspector_to_rrational,\n"
            ")\n"
            "# inspector_data must be an InspectorData built from the\n"
            "# previous cleaning step. Wire it up before running this\n"
            "# block when adapting the recipe.\n"
            f"# Saves {self.n_beats} beats of section "
            f"{self.section!r} for participant {self.pid!r}.\n"
            "export = export_inspector_to_rrational(\n"
            "    inspector_data,\n"
            f"    Path({self.out_path!r}),\n"
            f"    participant_id={self.pid!r},\n"
            ")"
        )


@dataclass(frozen=True)
class BatchPreprocess(Action):
    """Hook for the Tools -> Run preprocessing on all loaded recordings flow."""

    recording_paths: tuple[str, ...]
    method: str

    def to_python(self) -> str:
        paths_literal = list(self.recording_paths)
        return (
            "from rrational.io.generic_rr import detect_format, load_generic_rr\n"
            "from rrational.cleaning.rr import clean_rr_intervals, CleaningConfig\n"
            f"_paths = {paths_literal!r}\n"
            "for _p in _paths:\n"
            "    _p = Path(_p)\n"
            "    recording = load_generic_rr(_p, source_app=detect_format(_p))\n"
            "    cleaned = clean_rr_intervals("
            f"recording.rr_intervals, CleaningConfig())  # {self.method}"
        )
