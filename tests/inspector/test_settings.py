"""Tests for the QSettings-backed inspector preferences.

Each test redirects QSettings to ``tmp_path`` via ``enable_test_mode``
so the user's real registry/plist preferences are never touched. A
fresh QSettings file is created per test, which also gives us a
known-empty starting state.
"""

from __future__ import annotations

import pytest

pytest.importorskip("qtpy")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path):
    """Redirect QSettings to ``tmp_path`` before every test.

    Depends on pytest-qt's ``qapp`` fixture so QApplication is alive
    before we call QSettings.setPath (the path table is per-QApp).
    """
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    yield


def test_default_returned_when_setting_missing():
    from rrational.inspector.settings import read_setting

    assert read_setting("show_sidebar") is True
    assert read_setting("recent_files") == []
    assert read_setting("max_recent") == 10


def test_write_then_read_round_trips_string():
    from rrational.inspector.settings import read_setting, write_setting

    write_setting("last_dir", "C:/data")
    assert read_setting("last_dir") == "C:/data"


def test_write_then_read_round_trips_bool():
    """Bool coercion — QSettings stringifies bools on some platforms."""
    from rrational.inspector.settings import read_setting, write_setting

    write_setting("show_sidebar", False)
    assert read_setting("show_sidebar") is False


def test_unknown_setting_raises():
    from rrational.inspector.settings import read_setting, write_setting

    with pytest.raises(KeyError):
        read_setting("does_not_exist")
    with pytest.raises(KeyError):
        write_setting("does_not_exist", 42)


# ---------------------------------------------------------------------
# Recent files
# ---------------------------------------------------------------------
def test_add_recent_file_appears_at_top(tmp_path):
    from rrational.inspector.settings import add_recent_file, get_recent_files

    a = tmp_path / "a.rrational"
    b = tmp_path / "b.rrational"
    a.write_text("dummy")
    b.write_text("dummy")

    add_recent_file(a)
    add_recent_file(b)

    recent = get_recent_files()
    assert recent[0] == b.resolve()
    assert recent[1] == a.resolve()


def test_recent_file_re_added_moves_to_top(tmp_path):
    """Re-opening a file must NOT create a duplicate entry."""
    from rrational.inspector.settings import add_recent_file, get_recent_files

    a = tmp_path / "a.rrational"
    b = tmp_path / "b.rrational"
    a.write_text("dummy")
    b.write_text("dummy")

    add_recent_file(a)
    add_recent_file(b)
    add_recent_file(a)  # re-open a → bumped to top

    recent = get_recent_files()
    assert recent == [a.resolve(), b.resolve()]


def test_dead_paths_purged_from_recent(tmp_path):
    """Files deleted since last session must not show up in recent."""
    from rrational.inspector.settings import add_recent_file, get_recent_files

    alive = tmp_path / "alive.rrational"
    dead = tmp_path / "dead.rrational"
    alive.write_text("dummy")
    dead.write_text("dummy")

    add_recent_file(dead)
    add_recent_file(alive)
    dead.unlink()  # simulate user deletes file outside the app

    recent = get_recent_files()
    assert recent == [alive.resolve()]


def test_recent_capped_at_max(tmp_path):
    from rrational.inspector.settings import (
        add_recent_file,
        get_recent_files,
        read_setting,
    )

    cap = read_setting("max_recent")
    files = []
    for i in range(cap + 5):
        p = tmp_path / f"f{i}.rrational"
        p.write_text("dummy")
        files.append(p)
        add_recent_file(p)

    recent = get_recent_files()
    assert len(recent) == cap
    # Newest file is on top
    assert recent[0] == files[-1].resolve()


def test_clear_recent_files_empties_list(tmp_path):
    from rrational.inspector.settings import (
        add_recent_file,
        clear_recent_files,
        get_recent_files,
    )

    p = tmp_path / "x.rrational"
    p.write_text("dummy")
    add_recent_file(p)
    assert len(get_recent_files()) == 1

    clear_recent_files()
    assert get_recent_files() == []
