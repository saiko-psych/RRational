"""Tests for rrational.prep.participant_table.build_participant_table."""

from __future__ import annotations

from rrational.prep.participant_table import build_participant_table


def _summary(pid="P01", **over):
    s = {
        "participant_id": pid,
        "artifact_ratio": 0.02,
        "duplicate_rr_intervals": 0,
        "rr_file_count": 1,
        "events_file_count": 1,
        "events_detected": 4,
        "duplicate_events": 0,
        "recording_datetime_str": "2024-03-01 10:00",
        "total_beats": 6000,
        "retained_beats": 5900,
        "duration_s": 3030.0,
        "rr_min_ms": 512.7,
        "rr_max_ms": 1203.9,
        "rr_mean_ms": 801.49,
    }
    s.update(over)
    return s


def _build(summaries, **kw):
    args = dict(
        participant_groups={},
        participant_randomizations={},
        group_labels={},
        randomization_labels={},
        loaded_participants=set(),
    )
    args.update(kw)
    return build_participant_table(summaries, **args)


def test_clean_participant_row_and_no_issues():
    rows, issues = _build([_summary()])
    assert issues == []
    (row,) = rows
    assert row["Participant"] == "P01"
    assert row["Quality"] == "[OK]"
    assert row["Saved"] == "N"
    assert row["Files"] == "1RR/1Ev"
    assert row["Group"] == "Default" and row["_group_id"] == "Default"
    assert row["Randomization"] == "" and row["_rand_id"] == ""
    assert row["Total Beats"] == 6000 and row["Retained"] == 5900
    assert row["Duration (min)"] == "50.5"  # 3030 s / 60
    assert row["Total Events"] == 4 and row["Duplicate Events"] == 0
    assert row["RR Range (ms)"] == "512-1203"  # truncated, not rounded
    assert row["Mean RR (ms)"] == "801"


def test_group_and_randomization_labels_are_resolved():
    rows, _ = _build(
        [_summary("P01"), _summary("P02")],
        participant_groups={"P01": "g1", "P02": "g_unlabelled"},
        participant_randomizations={"P01": "r1"},
        group_labels={"g1": "Music"},
        randomization_labels={"r1": "Order A"},
        loaded_participants={"P02"},
    )
    p1, p2 = rows
    assert (p1["Group"], p1["_group_id"]) == ("Music", "g1")
    assert (p1["Randomization"], p1["_rand_id"]) == ("Order A", "r1")
    # Unknown label falls back to the raw id.
    assert p2["Group"] == "g_unlabelled"
    assert p2["Randomization"] == ""
    assert (p1["Saved"], p2["Saved"]) == ("N", "Y")


def test_unlabelled_randomization_falls_back_to_id():
    rows, _ = _build([_summary()], participant_randomizations={"P01": "r9"})
    assert rows[0]["Randomization"] == "r9"


def test_issue_summary_counts():
    summaries = [
        _summary("A", artifact_ratio=0.15),  # exactly 15 % -> not "high"
        _summary("B", artifact_ratio=0.151),
        _summary("C", duplicate_rr_intervals=3, duplicate_events=2),
        _summary("D", rr_file_count=2),
        _summary("E", events_file_count=3, events_detected=0),
    ]
    rows, issues = _build(summaries)
    assert issues == [
        "[X] **1** participant(s) with high artifact rates (>15%)",
        "**1** participant(s) with duplicate RR intervals",
        "**2** participant(s) with multiple files (merged)",
        "? **1** participant(s) with no events detected",
    ]
    by_id = {r["Participant"]: r for r in rows}
    assert by_id["C"]["Total Events"] == 6  # detected + duplicates
    assert by_id["E"]["Files"] == "1RR/3Ev"


def test_quality_badge_uses_artifact_ratio():
    rows, _ = _build([_summary("A", artifact_ratio=0.3)])
    assert rows[0]["Quality"] == "[!]"


def test_empty_input():
    assert _build([]) == ([], [])
