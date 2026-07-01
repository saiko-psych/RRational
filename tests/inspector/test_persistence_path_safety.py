"""Round 30 regression — path-traversal defense in the per-dataset
persistence layers.

A ``participant_id`` / ``pid`` is read verbatim from an untrusted
``.rrational`` export, so a malicious value like ``"../evil"`` must never
let the resolved side-car file escape the storage directory. Both
:mod:`rrational.inspector.annotation_persistence` and
:mod:`rrational.inspector.exclusion_persistence` sanitize the id before
building the filename and assert the resolved path stays under the base.

These tests are intentionally Qt-free: they exercise the pure
path-resolution + save/load functions directly with a ``tmp_path``
sandbox, so they stay fast and hermetic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rrational.inspector import annotation_persistence as ann
from rrational.inspector import exclusion_persistence as excl
from rrational.inspector.annotations import Annotation
from rrational.inspector.exclusion_persistence import ExclusionZone

# Participant ids that try to break out of the storage dir. On Windows
# both ``/`` and ``\\`` are separators; on POSIX only ``/`` — but the
# sanitizer treats every non-``[\w-]`` char identically, so both forms
# collapse to underscores regardless of platform.
_TRAVERSAL_IDS = [
    "../evil",
    "..\\evil",
    "../../etc/passwd",
    "sub/../../escape",
]

_NORMAL_PID = "0012MEBE"


@pytest.fixture(autouse=True)
def _sandbox(tmp_path):
    """Redirect both persistence modules to isolated tmp_path dirs.

    Uses the documented test-override hooks so no project path is needed
    and the developer's home directory is never touched. Both overrides
    are reset after the test regardless of outcome.
    """
    ann_dir = tmp_path / "ann_base"
    excl_dir = tmp_path / "excl_base"
    ann.set_annotation_config_dir(ann_dir)
    excl.set_exclusion_config_dir(excl_dir)
    try:
        yield ann_dir, excl_dir
    finally:
        ann.set_annotation_config_dir(None)
        excl.set_exclusion_config_dir(None)


def _assert_under(child: Path, base: Path) -> None:
    """Fail unless ``child`` resolves strictly inside ``base``."""
    child_r = child.resolve()
    base_r = base.resolve()
    # relative_to raises ValueError if child is not under base — that's
    # exactly the traversal escape we're guarding against.
    child_r.relative_to(base_r)
    # And the file must sit directly in base (no interposed segment).
    assert child_r.parent == base_r


# ---------------------------------------------------------------------
# annotation_persistence
# ---------------------------------------------------------------------
@pytest.mark.parametrize("pid", _TRAVERSAL_IDS)
def test_annotations_traversal_pid_stays_under_base(_sandbox, pid):
    """A malicious participant_id must not escape the annotations dir."""
    ann_dir, _ = _sandbox
    path = ann.annotations_path(pid, project_path=None)
    _assert_under(path, ann_dir)
    # The traversal tokens must have been scrubbed from the filename.
    assert ".." not in path.name
    assert "/" not in path.name and "\\" not in path.name


@pytest.mark.parametrize("pid", _TRAVERSAL_IDS)
def test_annotations_traversal_save_writes_inside_base(_sandbox, pid):
    """Saving under a traversal pid lands the file inside the base dir."""
    ann_dir, _ = _sandbox
    written = ann.save_annotations(pid, [Annotation.create(t=1.0, text="x")])
    _assert_under(written, ann_dir)
    # No stray file created in the parent (the escape target).
    parent_yamls = list(ann_dir.parent.glob("*_annotations.yml"))
    assert parent_yamls == []


def test_annotations_normal_pid_roundtrips(_sandbox):
    """A benign pid resolves inside base and survives save -> load."""
    ann_dir, _ = _sandbox
    path = ann.annotations_path(_NORMAL_PID, project_path=None)
    _assert_under(path, ann_dir)
    assert path.name == f"{_NORMAL_PID}_annotations.yml"

    original = [
        Annotation.create(t=1_700_000_001.0, text="Subject coughed"),
        Annotation.create(t=1_700_000_050.0, text="Music started"),
    ]
    written = ann.save_annotations(_NORMAL_PID, original)
    assert written == path
    assert written.exists()

    loaded = ann.load_annotations(_NORMAL_PID)
    assert len(loaded) == 2
    assert loaded[0].t == pytest.approx(1_700_000_001.0)
    assert loaded[0].text == "Subject coughed"
    assert loaded[1].text == "Music started"


def test_annotations_traversal_and_normal_do_not_collide(_sandbox):
    """The sanitized traversal id must not alias the normal file."""
    normal = ann.annotations_path(_NORMAL_PID)
    evil = ann.annotations_path("../" + _NORMAL_PID)
    assert normal.name != evil.name


# ---------------------------------------------------------------------
# exclusion_persistence
# ---------------------------------------------------------------------
@pytest.mark.parametrize("pid", _TRAVERSAL_IDS)
def test_exclusions_traversal_pid_stays_under_base(_sandbox, pid):
    """A malicious pid must not escape the exclusions dir."""
    _, excl_dir = _sandbox
    path = excl._zones_path(pid, None)
    _assert_under(path, excl_dir)
    assert ".." not in path.name
    assert "/" not in path.name and "\\" not in path.name


@pytest.mark.parametrize("pid", _TRAVERSAL_IDS)
def test_exclusions_traversal_save_writes_inside_base(_sandbox, pid):
    """Saving under a traversal pid lands the file inside the base dir."""
    _, excl_dir = _sandbox
    written = excl.save_exclusion_zones(
        pid, [ExclusionZone(start_t=1.0, end_t=2.0, reason="x")]
    )
    _assert_under(written, excl_dir)
    parent_yamls = list(excl_dir.parent.glob("*_exclusions.yml"))
    assert parent_yamls == []


def test_exclusions_normal_pid_roundtrips(_sandbox):
    """A benign pid resolves inside base and survives save -> load."""
    _, excl_dir = _sandbox
    path = excl._zones_path(_NORMAL_PID, None)
    _assert_under(path, excl_dir)
    assert path.name == f"{_NORMAL_PID}_exclusions.yml"

    original = [
        ExclusionZone(
            start_t=1_700_000_010.0,
            end_t=1_700_000_020.0,
            reason="motion artifact",
            start_beat_idx=10,
            end_beat_idx=22,
        ),
        ExclusionZone(start_t=1_700_000_100.0, end_t=1_700_000_120.0, reason="cough"),
    ]
    written = excl.save_exclusion_zones(_NORMAL_PID, original)
    assert written == path
    assert written.exists()

    loaded = excl.load_exclusion_zones(_NORMAL_PID)
    assert len(loaded) == 2
    assert loaded[0].start_t == pytest.approx(1_700_000_010.0)
    assert loaded[0].reason == "motion artifact"
    assert loaded[0].start_beat_idx == 10
    assert loaded[1].reason == "cough"


# ---------------------------------------------------------------------
# project_path routing still enforces containment
# ---------------------------------------------------------------------
def test_annotations_traversal_pid_stays_under_project(tmp_path):
    """With a project_path, a traversal pid stays under project/data/processed."""
    ann.set_annotation_config_dir(None)
    try:
        base = tmp_path / "proj" / "data" / "processed"
        path = ann.annotations_path("../../secrets", project_path=tmp_path / "proj")
        _assert_under(path, base)
    finally:
        ann.set_annotation_config_dir(None)


def test_exclusions_traversal_pid_stays_under_project(tmp_path):
    """With a project_path, a traversal pid stays under project/data/processed."""
    excl.set_exclusion_config_dir(None)
    try:
        base = tmp_path / "proj" / "data" / "processed"
        path = excl._zones_path("../../secrets", tmp_path / "proj")
        _assert_under(path, base)
    finally:
        excl.set_exclusion_config_dir(None)
