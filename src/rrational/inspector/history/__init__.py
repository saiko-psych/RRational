"""Reproducible action history for the RRational Inspector.

Modelled on MNELAB's ``model.py`` history pattern: every user action
that mutates project / dataset / preprocessing state is recorded as a
frozen :class:`Action` dataclass. The Action knows how to serialise
itself as a runnable Python expression (``Action.to_python()``).

Saving the history produces a self-contained ``.py`` script that, when
re-run with the same input files in place, reproduces the same
output. The recipe is the audit-trail-as-code, complementing the
JSON ``audit_trail`` already embedded in ``.rrational`` v2 exports.

MNELAB stores history as a flat ``list[str]`` of pre-rendered Python
lines. We use frozen dataclasses instead — the structured form makes
each entry inspectable, type-checkable, and trivially testable, while
``to_python()`` keeps the user-facing artefact (the recipe script)
identical in spirit to what MNELAB writes out via ``format_code``.
"""

from rrational.inspector.history.actions import (
    Action,
    AddAnnotation,
    AddExclusionZone,
    BatchPreprocess,
    DetectArtifacts,
    LoadRecording,
    OpenProject,
    SaveRRationalExport,
)
from rrational.inspector.history.recorder import HistoryRecorder
from rrational.inspector.history.serializer import to_script

__all__ = [
    "Action",
    "AddAnnotation",
    "AddExclusionZone",
    "BatchPreprocess",
    "DetectArtifacts",
    "HistoryRecorder",
    "LoadRecording",
    "OpenProject",
    "SaveRRationalExport",
    "to_script",
]
