"""Round 31 regression tests for project atomicity + empty-dataset guards.

- D1: ProjectManager.save_metadata must write atomically (tmp + replace) so a
  crash mid-write cannot truncate project.rrational.
- D2: create_project must roll back a partially-created tree it created.
- D3: InspectorData.t_start / t_end must raise a clear ValueError (not an
  opaque IndexError) on an empty dataset.

No Qt widgets required.
"""

from __future__ import annotations

import numpy as np
import pytest

from rrational.inspector.data_loader import InspectorData


# ---------------------------------------------------------------------
# D3 — empty InspectorData guards
# ---------------------------------------------------------------------
def test_t_start_on_empty_raises_valueerror_not_indexerror():
    empty = InspectorData(t=np.array([]), v=np.array([]))
    with pytest.raises(ValueError, match="no finite samples"):
        _ = empty.t_start


def test_t_end_on_empty_raises_valueerror_not_indexerror():
    empty = InspectorData(t=np.array([]), v=np.array([]))
    with pytest.raises(ValueError, match="no finite samples"):
        _ = empty.t_end


def test_t_start_all_nan_raises():
    allnan = InspectorData(t=np.array([np.nan, np.nan]), v=np.array([np.nan, np.nan]))
    with pytest.raises(ValueError):
        _ = allnan.t_start


# ---------------------------------------------------------------------
# D1 / D2 — project save is atomic + create rolls back
# ---------------------------------------------------------------------
def test_save_metadata_is_atomic(tmp_path):
    from rrational.gui.project import ProjectManager

    proj = tmp_path / "study"
    pm = ProjectManager.create_project(proj, name="Study")
    project_file = proj / ProjectManager.PROJECT_FILE
    assert project_file.exists()
    # A second save must leave a single valid file and no stray .tmp files.
    pm.metadata.description = "updated"
    pm.save_metadata()
    tmp_leftovers = list(proj.glob("*.tmp"))
    assert not tmp_leftovers, f"atomic write left temp files: {tmp_leftovers}"
    import yaml

    loaded = yaml.safe_load(project_file.read_text(encoding="utf-8"))
    assert loaded["metadata"]["description"] == "updated"


def test_create_project_rolls_back_new_dir_on_failure(tmp_path, monkeypatch):
    from rrational.gui.project import ProjectManager

    proj = tmp_path / "doomed"

    # Force save_metadata to blow up AFTER the directory tree is created.
    def _boom(self):
        raise RuntimeError("simulated write failure")

    monkeypatch.setattr(ProjectManager, "save_metadata", _boom)

    with pytest.raises(RuntimeError, match="simulated write failure"):
        ProjectManager.create_project(proj, name="Doomed")

    # The partially-created tree we made must be gone (we created it).
    assert not proj.exists(), "partial project tree was not rolled back"


def test_create_project_preserves_preexisting_dir_on_failure(tmp_path, monkeypatch):
    from rrational.gui.project import ProjectManager

    proj = tmp_path / "preexisting"
    proj.mkdir()
    sentinel = proj / "user_file.txt"
    sentinel.write_text("do not delete me", encoding="utf-8")

    def _boom(self):
        raise RuntimeError("simulated write failure")

    monkeypatch.setattr(ProjectManager, "save_metadata", _boom)

    with pytest.raises(RuntimeError):
        ProjectManager.create_project(proj, name="X")

    # Because the directory pre-existed, rollback must NOT delete it.
    assert proj.exists()
    assert sentinel.exists(), "rollback wrongly deleted a pre-existing user dir"
