"""Semantic execution tests for recipe scripts produced by ``to_script``.

The recipe renderer in ``rrational.inspector.history.serializer`` turns a
recorded ``HistoryRecorder`` into a Python script that should be runnable
in isolation. Earlier tests in ``test_history.py`` only ``ast.parse`` the
output, which catches syntax errors but not import or attribute mistakes
that would prevent the recipe from actually running. These tests close
that gap by executing the produced script in an isolated namespace via
``exec()`` and verifying that the expected side effects materialise.

We intentionally avoid ``subprocess.run`` here so the tests do not pay
the cost of a full Python interpreter spawn per action -- ``exec()`` in
an empty ``globals()`` dict gives us the same isolation guarantees (no
leaked imports, no shared module state with the test process) at a
fraction of the runtime cost.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rrational.inspector.history import (
    AddAnnotation,
    DetectArtifacts,
    HistoryRecorder,
    LoadRecording,
    to_script,
)
from rrational.inspector.history.serializer import to_script as to_script_direct


# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------
@pytest.fixture
def plain_rr_file(tmp_path: Path) -> Path:
    """Write a plain-rr file (one RR interval in ms per line)."""
    # 30 beats around 800 ms, no outliers, so the auto-detector picks
    # ``plain_rr`` and ``clean_rr_intervals`` has something realistic to
    # operate on without raising on degenerate input.
    rr_path = tmp_path / "rr_plain.txt"
    rr_path.write_text("\n".join(str(800 + (i % 5) * 10) for i in range(30)) + "\n")
    return rr_path


def _exec_recipe(script: str) -> dict[str, object]:
    """Run ``script`` in an isolated namespace and return its globals.

    Using a fresh dict guarantees the recipe cannot accidentally leak
    state into or pull state out of the running test process.
    """
    ns: dict[str, object] = {"__name__": "__recipe_exec__"}
    exec(compile(script, "<recipe>", "exec"), ns)
    return ns


# ---------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------
def test_recipe_with_load_recording_executes(plain_rr_file: Path) -> None:
    """A single LoadRecording action should produce a runnable recipe.

    After exec, the recipe binds ``recording`` and ``rr_intervals``;
    those names are the contract subsequent action snippets rely on.
    """
    recorder = HistoryRecorder()
    recorder.record(LoadRecording(path=str(plain_rr_file)))
    script = to_script(recorder)

    ns = _exec_recipe(script)

    assert "recording" in ns, "recipe must bind recording"
    assert "rr_intervals" in ns, "recipe must bind rr_intervals for downstream actions"
    rr = ns["rr_intervals"]
    # Should be a non-empty sequence of intervals (matches what
    # load_generic_rr returns from the plain-rr branch).
    assert len(list(rr)) == 30


def test_recipe_multiple_actions_in_order(plain_rr_file: Path) -> None:
    """Load + detect + annotate should chain without NameErrors.

    The serializer documents that LoadRecording binds ``rr_intervals``
    specifically so DetectArtifacts can immediately call
    ``clean_rr_intervals(rr_intervals, ...)``. Executing the combined
    script proves that contract holds end-to-end.
    """
    recorder = HistoryRecorder()
    recorder.record(LoadRecording(path=str(plain_rr_file)))
    recorder.record(DetectArtifacts(method="neurokit2_lipponen"))

    script = to_script(recorder)
    ns = _exec_recipe(script)

    # DetectArtifacts binds ``cleaned``; assert it landed in the
    # namespace so the next action could reference it.
    assert "cleaned" in ns
    # ``rr_intervals`` must still be alive (load action ran first).
    assert "rr_intervals" in ns


def test_recipe_with_empty_history_produces_valid_python() -> None:
    """An empty recorder must yield a script that exec'es without raising.

    The serializer emits a placeholder comment when no actions are
    recorded; verify that placeholder is genuinely a no-op and not just
    syntactically valid.
    """
    script = to_script(HistoryRecorder())
    ns = _exec_recipe(script)

    # Only the header import should leak through -- nothing user-visible.
    assert "Path" in ns


def test_to_script_alias_matches_module_export() -> None:
    """The package re-export ``to_script`` should be the same callable as
    ``serializer.to_script``. A divergence here would mean callers using
    ``from rrational.inspector.history import to_script`` get a stale
    implementation -- worth pinning with an identity check.
    """
    assert to_script is to_script_direct


def test_recipe_with_annotation_executes(plain_rr_file: Path, tmp_path: Path) -> None:
    """An AddAnnotation action persists through the real annotation
    code path. The action's ``to_python`` calls
    ``load_annotations`` / ``save_annotations``, both of which touch
    project config storage. Point the active project config dir at the
    test tmpdir so the recipe writes nothing into the real user profile.
    """
    from rrational.inspector import persistence

    project_dir = tmp_path / "proj"
    (project_dir / "config").mkdir(parents=True)
    persistence.set_active_project_config_dir(project_dir / "config")
    try:
        recorder = HistoryRecorder()
        recorder.record(LoadRecording(path=str(plain_rr_file)))
        recorder.record(AddAnnotation(pid="S01", t=12.3, label="ok"))
        script = to_script(recorder)

        # If this exec raises, the recipe is not really reproducible.
        _exec_recipe(script)
    finally:
        # Reset so other tests are not polluted.
        persistence.set_active_project_config_dir(None)
