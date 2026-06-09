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
        if self.fmt:
            return (
                "from rrational.io.generic_rr import load_generic_rr\n"
                f"recording = load_generic_rr("
                f"Path({self.path!r}), source_app={self.fmt!r})"
            )
        return (
            "from rrational.io.generic_rr import detect_format, load_generic_rr\n"
            f"_p = Path({self.path!r})\n"
            "recording = load_generic_rr(_p, source_app=detect_format(_p))"
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
        return (
            f"# pid={self.pid!r}\n"
            f"exclusion_zone("
            f"t_start={self.t_start}, t_end={self.t_end}, "
            f"reason={self.reason!r})"
        )


@dataclass(frozen=True)
class AddAnnotation(Action):
    """User attached a free-text annotation at a timestamp."""

    pid: str
    t: float
    label: str

    def to_python(self) -> str:
        return (
            "from rrational.inspector.annotations import Annotation\n"
            f"ann = Annotation.create(t={self.t}, text={self.label!r})\n"
            f"# attach to participant {self.pid!r}"
        )


@dataclass(frozen=True)
class SaveRRationalExport(Action):
    """User wrote the active dataset out as a .rrational v2 file."""

    pid: str
    section: str
    out_path: str
    n_beats: int

    def to_python(self) -> str:
        return (
            "from rrational.inspector.export import (\n"
            "    export_inspector_to_rrational,\n"
            ")\n"
            f"# save {self.n_beats} beats of {self.section!r} "
            f"for {self.pid!r}\n"
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
