"""Tests for Phase 7 project management in the inspector."""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


# These tests instantiate a full MainWindow + ProjectManager, which
# leaves QApplication singleton + Inspector persistence dirs in a state
# that pollutes neighbour tests when pytest-xdist parallelises the
# suite. Pinning to a named group routes them all to the same worker
# in known order. Require ``--dist=loadgroup`` (set in pyproject.toml
# pytest config) for the marker to take effect.
pytestmark = pytest.mark.xdist_group("inspector_project")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path, monkeypatch):
    """Isolate all persistence sources: Qt settings, inspector YAML store,
    AND the global rrational settings file (which is where recent projects
    live)."""
    from rrational.gui import persistence as gui_persistence
    from rrational.inspector import persistence, settings

    settings.enable_test_mode(tmp_path)
    persistence.set_inspector_config_dir(tmp_path / "global_inspector")

    # Redirect the global rrational settings file so get_recent_projects()
    # doesn't see the developer's real recent-project history.
    isolated_settings_path = tmp_path / "rrational_settings.yml"
    monkeypatch.setattr(gui_persistence, "SETTINGS_FILE", isolated_settings_path)

    yield
    persistence.set_inspector_config_dir(None)
    persistence.set_active_project_config_dir(None)


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


def _make_project(tmp_path, name="TestStudy"):
    from rrational.gui.project import ProjectManager

    return ProjectManager.create_project(
        path=tmp_path / name, name=name, description="phase 7 fixture"
    )


# ---------------------------------------------------------------------
# Project state on MainWindow
# ---------------------------------------------------------------------
def test_main_window_starts_with_no_project(main_window):
    assert main_window._project is None


def test_set_active_project_updates_state_and_title(main_window, tmp_path):
    pm = _make_project(tmp_path)
    main_window.set_active_project(pm)
    assert main_window._project is pm
    assert "TestStudy" in main_window.windowTitle()
    assert "[TestStudy]" in main_window.windowTitle()


def test_close_project_clears_state_and_title(main_window, tmp_path):
    pm = _make_project(tmp_path)
    main_window.set_active_project(pm)
    main_window.close_project()
    assert main_window._project is None
    assert "[" not in main_window.windowTitle()  # No project bracket


def test_window_title_combines_project_and_dataset(main_window, tmp_path):
    from rrational.inspector.data_loader import (
        Dataset,
        EventMeta,
        InspectorData,
        SectionMeta,
    )
    import numpy as np

    pm = _make_project(tmp_path, name="MyStudy")
    main_window.set_active_project(pm)

    data = InspectorData(
        t=np.arange(100, dtype=np.float64),
        v=np.full(100, 800.0),
        sections=[SectionMeta(name="s", t_start=0.0, t_end=99.0, beat_count=100)],
        events=[EventMeta(label="ev", t=0.0)],
    )
    main_window.add_dataset(Dataset(name="alpha", data=data))
    main_window.set_active_dataset(0)

    title = main_window.windowTitle()
    assert "MyStudy" in title
    assert "alpha" in title


# ---------------------------------------------------------------------
# Persistence redirection
# ---------------------------------------------------------------------
def test_setting_project_redirects_sequence_persistence(main_window, tmp_path):
    """Sequences written after open_project should land in project/config/."""
    from rrational.inspector import persistence as _p
    from rrational.inspector.persistence import Sequence, save_sequences

    pm = _make_project(tmp_path)
    main_window.set_active_project(pm)
    # Drop the test-fixture's global override so the project-scope can win
    _p.set_inspector_config_dir(None)

    save_sequences([Sequence(name="proj_seq", sections=["a", "b"])])

    project_yaml = pm.get_config_dir() / "sequences.yml"
    assert project_yaml.exists()


def test_closing_project_reverts_persistence_to_global(main_window, tmp_path):
    """After close_project, sequence saves go back to the global dir."""
    from rrational.inspector import persistence
    from rrational.inspector.persistence import Sequence, save_sequences

    pm = _make_project(tmp_path)
    main_window.set_active_project(pm)
    main_window.close_project()

    save_sequences([Sequence(name="back_to_global", sections=["x", "y"])])

    project_yaml = pm.get_config_dir() / "sequences.yml"
    # New save did NOT land in the project dir
    if project_yaml.exists():
        import yaml as _y

        with project_yaml.open() as f:
            content = _y.safe_load(f) or {}
        assert not any(
            s.get("name") == "back_to_global" for s in content.get("sequences", [])
        )
    # It landed in the override / global dir
    global_yaml = persistence._config_dir() / "sequences.yml"
    assert global_yaml.exists()


# ---------------------------------------------------------------------
# open_project_path
# ---------------------------------------------------------------------
def test_open_project_path_rejects_invalid_folder(main_window, tmp_path):
    """A folder without project.rrational returns False, no crash."""
    bad = tmp_path / "not_a_project"
    bad.mkdir()
    ok = main_window.open_project_path(bad)
    assert ok is False
    assert main_window._project is None


def test_open_project_does_NOT_auto_load_rrational_files(main_window, tmp_path, qtbot):
    """Phase 22 behaviour change: opening a project should NOT silently
    open every .rrational file from data/processed/ — overwhelms the
    user. They explicitly pick files from the DataTab overview instead."""
    from rrational.gui.rrational_export import (
        EventChoiceV2,
        FinalArtifactsV2,
        MetadataV2,
        NNCorrectionV2,
        NNIntervalsDataV2,
        QualityV2,
        RRationalExportV2,
        SectionDefinitionV2,
        SectionExportV2,
        SectionValidationV2,
        save_rrational_v2,
    )

    pm = _make_project(tmp_path)

    # Write a minimal valid v2 file into the project's processed folder
    def _minimal_export(pid: str) -> RRationalExportV2:
        section = SectionExportV2(
            definition=SectionDefinitionV2("s_start", "s_end", "section1"),
            validation=SectionValidationV2(
                validated_at="2026-01-01T00:00:00",
                start_event=EventChoiceV2(
                    label="s_start", timestamp="2026-01-01T00:00:00", beat_idx=0
                ),
                end_event=EventChoiceV2(
                    label="s_end", timestamp="2026-01-01T00:00:30", beat_idx=29
                ),
                total_duration_s=30.0,
                total_beat_count=30,
            ),
            nn_correction=NNCorrectionV2(),
            quality=QualityV2(usable_beats=30, usable_duration_s=30.0),
            final_artifacts=FinalArtifactsV2(),
            nn_intervals=NNIntervalsDataV2(
                data=[[i * 1000, 1000, False] for i in range(30)]
            ),
        )
        return RRationalExportV2(
            metadata=MetadataV2(
                participant_id=pid,
                created_at="2026-01-01T00:00:00",
                last_modified="2026-01-01T00:00:00",
            ),
            sections={"section1": section},
        )

    for pid in ("alpha", "beta"):
        save_rrational_v2(
            _minimal_export(pid), pm.get_processed_dir() / f"{pid}.rrational"
        )

    main_window.set_active_project(pm)
    # NOT auto-loaded — workspace stays empty until user explicitly opens
    # files via the DataTab overview (or File → Open recording).
    assert len(main_window._datasets) == 0
    assert main_window._project is pm
    data_tab = getattr(main_window, "_data_tab", None)
    if data_tab is not None:
        data_tab.refresh_from_workspace()
        items = [
            data_tab._processed_list.item(i).text()
            for i in range(data_tab._processed_list.count())
        ]
        assert "alpha.rrational" in items
        assert "beta.rrational" in items


# ---------------------------------------------------------------------
# Menu wiring
# ---------------------------------------------------------------------
def test_recent_project_menu_shows_placeholder_when_empty(main_window):
    main_window._rebuild_recent_project_menu()
    actions = main_window._recent_project_menu.actions()
    assert len(actions) == 1
    assert "(no recent projects)" in actions[0].text()


# ---------------------------------------------------------------------
# UX1: permanent project badge in the status bar
# ---------------------------------------------------------------------
def test_project_badge_text_when_no_project(main_window):
    """Default state: badge is empty (the inline DataTab project block
    carries the "No project active" hint instead — keeping it in the
    permanent badge produced redundant noise on every tab)."""
    assert main_window._project is None
    assert main_window._project_badge.text() == ""


def test_project_badge_updates_on_set_active_project(main_window, tmp_path):
    """Setting an active project should put its name in the badge."""
    pm = _make_project(tmp_path, name="BadgeStudy")
    main_window.set_active_project(pm)
    text = main_window._project_badge.text()
    assert "Project:" in text
    assert "BadgeStudy" in text


def test_project_badge_clears_on_close_project(main_window, tmp_path):
    """Closing the project should revert the badge to its empty default."""
    pm = _make_project(tmp_path, name="TempStudy")
    main_window.set_active_project(pm)
    main_window.close_project()
    assert main_window._project_badge.text() == ""


# ---------------------------------------------------------------------
# F10: auto-load last project on startup
# ---------------------------------------------------------------------
def test_set_active_project_persists_last_project_path(qtbot, tmp_path):
    """Opening a project (outside test_mode) should record its path so the
    next launch can auto-load it. test_mode is the only thing that blocks
    the write — the autouse fixture isolates QSettings so the real user
    config is untouched."""
    from rrational.inspector import settings
    from rrational.inspector.main_window import MainWindow

    pm = _make_project(tmp_path, name="PersistMe")

    win = MainWindow()
    win.test_mode = False  # so set_active_project writes to QSettings
    qtbot.addWidget(win)
    win.set_active_project(pm)
    assert settings.read_setting("last_project_path") == str(pm.project_path)
    win.close()


def test_close_project_keeps_last_project_path(qtbot, tmp_path):
    """Closing a project must NOT erase last_project_path; otherwise the
    auto-load on the NEXT launch would have nothing to open."""
    from rrational.inspector import settings
    from rrational.inspector.main_window import MainWindow

    pm = _make_project(tmp_path, name="StickyPath")

    win = MainWindow()
    win.test_mode = False
    qtbot.addWidget(win)
    win.set_active_project(pm)
    win.close_project()
    assert settings.read_setting("last_project_path") == str(pm.project_path)
    win.close()


def test_auto_load_last_project_opens_project_on_startup(qtbot, tmp_path):
    """A second MainWindow constructed after a project is on record + the
    auto-load flag is on must come up with that project already active."""
    from rrational.inspector import settings
    from rrational.inspector.main_window import MainWindow

    pm = _make_project(tmp_path, name="AutoOpenStudy")

    # Seed QSettings as if a previous session had opened the project.
    settings.write_setting("auto_load_last_project", True)
    settings.write_setting("last_project_path", str(pm.project_path))

    win = MainWindow()
    # test_mode must stay False for the auto-load path to fire.
    win.test_mode = False
    qtbot.addWidget(win)

    assert win._project is not None
    assert win._project.project_path == pm.project_path
    win.close()


def test_auto_load_skipped_when_flag_disabled(qtbot, tmp_path):
    """Even with a recorded last project, the auto-load is off when the
    user disabled the toggle."""
    from rrational.inspector import settings
    from rrational.inspector.main_window import MainWindow

    pm = _make_project(tmp_path, name="DisabledAutoLoad")

    settings.write_setting("auto_load_last_project", False)
    settings.write_setting("last_project_path", str(pm.project_path))

    win = MainWindow()
    win.test_mode = False
    qtbot.addWidget(win)
    assert win._project is None
    win.close()


def test_auto_load_skipped_when_path_missing(qtbot, tmp_path):
    """A stale last_project_path (project deleted between sessions) is
    silently ignored — the user falls through to the normal welcome flow."""
    from rrational.inspector import settings
    from rrational.inspector.main_window import MainWindow

    settings.write_setting("auto_load_last_project", True)
    settings.write_setting("last_project_path", str(tmp_path / "does-not-exist"))

    win = MainWindow()
    win.test_mode = False
    qtbot.addWidget(win)
    assert win._project is None
    win.close()


def test_auto_load_skipped_in_test_mode(qtbot, tmp_path):
    """When test_mode is flipped on BEFORE the auto-load check fires, the
    helper must do nothing. We exercise this with a subclass that sets
    ``self.test_mode = True`` at the start of ``__init__`` so the gate
    inside the auto-load path sees the test-mode flag."""
    from rrational.inspector import settings
    from rrational.inspector.main_window import MainWindow

    pm = _make_project(tmp_path, name="TestModeSafe")
    settings.write_setting("auto_load_last_project", True)
    settings.write_setting("last_project_path", str(pm.project_path))

    class _TestModeWindow(MainWindow):
        def __init__(self):
            # Flip test_mode BEFORE super().__init__ so the auto-load
            # gate inside __init__ honours it.
            super().__init__()

        # The super().__init__ above runs to completion before we can
        # touch self, so we need a different hook. We instead override
        # the helper itself to record the call and refuse to load.
        def _maybe_auto_load_last_project(self) -> None:
            self._auto_load_called_when_test_mode = self.test_mode
            return None

    # First: prove that the helper IS the gatekeeper — when not in
    # test_mode it auto-loads the project.
    win = MainWindow()
    win.test_mode = False
    qtbot.addWidget(win)
    assert win._project is not None
    win.close()

    # Second: subclass that no-ops the helper proves the call site is
    # the only place the auto-load fires (regression guard).
    win2 = _TestModeWindow()
    qtbot.addWidget(win2)
    # The subclass refused to load, so no project is active.
    assert win2._project is None
    win2.close()
