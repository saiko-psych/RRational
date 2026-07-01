"""Round 32 regression tests — atomic config/export writes + UTC export ISO.

- SU1: the gui.persistence config writers (groups/events/sections/protocol/
  participants/event_sequences/condition_labels) must write atomically so a
  crash or concurrent reader cannot leave a truncated file that reloads as {}.
- EX1: save_rrational_v2 / save_rrational must write atomically.
- EX2: export._epoch_to_iso must emit a tz-aware UTC ISO string, not naive
  local time (DST-stable, unambiguous).

We can't easily simulate a mid-write crash, so we assert the observable
contract: (a) round-trip fidelity survives the new code path, and (b) no
stray ``.tmp`` files are left behind. Pure logic, no Qt.
"""

from __future__ import annotations

from datetime import datetime, timezone

from rrational.gui import persistence


# ---------------------------------------------------------------------
# SU1 — config writers atomic + round-trip
# ---------------------------------------------------------------------
def test_save_groups_atomic_roundtrip_no_tmp(tmp_path):
    project = tmp_path / "proj"
    (project / "config").mkdir(parents=True)
    groups = {"Control": {"members": ["P01", "P02"]}, "Treat": {"members": ["P03"]}}
    persistence.save_groups(groups, project_path=project)
    # No stray temp file left behind.
    assert not list((project / "config").glob("*.tmp"))
    assert persistence.load_groups(project_path=project) == groups


def test_save_sections_and_protocol_atomic_roundtrip(tmp_path):
    project = tmp_path / "proj"
    (project / "config").mkdir(parents=True)
    sections = {"rest_pre": {"duration_s": 300}}
    protocol = {"order": ["rest_pre", "music", "rest_post"]}
    persistence.save_sections(sections, project_path=project)
    persistence.save_protocol(protocol, project_path=project)
    assert not list((project / "config").glob("*.tmp"))
    assert persistence.load_sections(project_path=project) == sections
    assert persistence.load_protocol(project_path=project) == protocol


def test_atomic_yaml_dump_overwrites_cleanly(tmp_path):
    target = tmp_path / "x.yml"
    persistence._atomic_yaml_dump(target, {"a": 1})
    persistence._atomic_yaml_dump(target, {"a": 2, "b": 3})
    import yaml

    assert yaml.safe_load(target.read_text(encoding="utf-8")) == {"a": 2, "b": 3}
    assert not list(tmp_path.glob("*.tmp"))


# ---------------------------------------------------------------------
# EX1 — export writer atomic
# ---------------------------------------------------------------------
def test_save_rrational_v2_atomic_no_tmp(tmp_path):
    from rrational.gui.rrational_export import _atomic_yaml_write

    target = tmp_path / "S01.rrational"
    _atomic_yaml_write(target, {"file_type": "rrational", "rrational_version": "2.0"})
    assert target.exists()
    assert not list(tmp_path.glob("*.tmp"))
    import yaml

    loaded = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert loaded["rrational_version"] == "2.0"


# ---------------------------------------------------------------------
# EX2 — export ISO timestamps are tz-aware UTC
# ---------------------------------------------------------------------
def test_epoch_to_iso_is_utc_aware():
    from rrational.inspector.export import _epoch_to_iso

    # A fixed epoch: 2026-01-01T00:00:00Z.
    epoch = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
    iso = _epoch_to_iso(epoch)
    parsed = datetime.fromisoformat(iso)
    assert parsed.tzinfo is not None, "exported ISO must carry a timezone"
    assert parsed.utcoffset() == timezone.utc.utcoffset(None)
    # Round-trips back to the same instant regardless of the machine tz.
    assert abs(parsed.timestamp() - epoch) < 1e-6
