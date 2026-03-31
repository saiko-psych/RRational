"""Build participant overview table from recording summaries.

Pure data transform — no Streamlit dependency.
"""

from __future__ import annotations

from rrational.cleaning.quality import get_quality_badge


def build_participant_table(
    summaries_data: list[dict],
    participant_groups: dict,
    participant_randomizations: dict,
    group_labels: dict,
    randomization_labels: dict,
    loaded_participants: set[str],
) -> tuple[list[dict], list[str]]:
    """Build participant table data and issue summary.

    Args:
        summaries_data: List of dicts with participant summary fields.
        participant_groups: {participant_id: group_id}.
        participant_randomizations: {participant_id: randomization_id}.
        group_labels: {group_id: display_label}.
        randomization_labels: {rand_value: display_label}.
        loaded_participants: Set of participant IDs with saved data.

    Returns:
        (participants_data, issues) where participants_data is a list of row dicts.
    """
    issues = []
    high_artifact = sum(1 for s in summaries_data if s["artifact_ratio"] > 0.15)
    if high_artifact:
        issues.append(f"[X] **{high_artifact}** participant(s) with high artifact rates (>15%)")

    with_duplicates = sum(1 for s in summaries_data if s["duplicate_rr_intervals"] > 0)
    if with_duplicates:
        issues.append(f"**{with_duplicates}** participant(s) with duplicate RR intervals")

    with_multi_files = sum(1 for s in summaries_data
                           if s["rr_file_count"] > 1 or s["events_file_count"] > 1)
    if with_multi_files:
        issues.append(f"**{with_multi_files}** participant(s) with multiple files (merged)")

    no_events = sum(1 for s in summaries_data if s["events_detected"] == 0)
    if no_events:
        issues.append(f"? **{no_events}** participant(s) with no events detected")

    participants_data = []
    for s in summaries_data:
        rr_count = s["rr_file_count"]
        ev_count = s["events_file_count"]
        files_str = f"{rr_count}RR/{ev_count}Ev"

        group_id = participant_groups.get(s["participant_id"], "Default")
        group_display = group_labels.get(group_id, group_id)

        rand_id = participant_randomizations.get(s["participant_id"], "")
        rand_display = randomization_labels.get(rand_id, rand_id) if rand_id else ""

        participants_data.append({
            "Participant": s["participant_id"],
            "Quality": get_quality_badge(100, s["artifact_ratio"]),
            "Saved": "Y" if s["participant_id"] in loaded_participants else "N",
            "Files": files_str,
            "Date/Time": s["recording_datetime_str"],
            "Group": group_display,
            "_group_id": group_id,
            "Randomization": rand_display,
            "_rand_id": rand_id,
            "Total Beats": s["total_beats"],
            "Retained": s["retained_beats"],
            "Duplicates": s["duplicate_rr_intervals"],
            "Duration (min)": f"{s['duration_s'] / 60:.1f}",
            "Events": s["events_detected"],
            "Total Events": s["events_detected"] + s["duplicate_events"],
            "Duplicate Events": s["duplicate_events"],
            "RR Range (ms)": f"{int(s['rr_min_ms'])}-{int(s['rr_max_ms'])}",
            "Mean RR (ms)": f"{s['rr_mean_ms']:.0f}",
        })

    return participants_data, issues
