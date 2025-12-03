"""Data tab - Import settings and participant table."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from music_hrv.cleaning.rr import CleaningConfig
from music_hrv.io import DEFAULT_ID_PATTERN, PREDEFINED_PATTERNS
from music_hrv.gui.shared import (
    cached_load_hrv_logger_preview,
    cached_load_participants,
    save_participant_data,
    show_toast,
    validate_regex_pattern,
    get_quality_badge,
)


def render_data_tab():
    """Render the Data tab content."""
    st.header("Data Import")

    # Quick help section
    with st.expander("Help - Getting Started", expanded=False):
        st.markdown("""
        ### Workflow Overview

        1. **Import Data**: Select your HRV Logger data folder below. The app will automatically
           detect all RR interval and event files.

        2. **Assign Groups**: Use the participant table to assign each participant to a study group.
           Groups define which events are expected for each participant.

        3. **Review Events**: Go to the Participant tab to see individual RR interval plots and events.
           You can add manual events by clicking on the plot.

        4. **Quality Check**: The app automatically detects gaps in data and high variability segments.
           Use "Batch Processing" to detect issues across all participants at once.

        ---

        **Key Terms:**
        - **RR Interval**: Time between consecutive heartbeats (in milliseconds)
        - **Canonical Event**: Standardized event name (e.g., `measurement_start`)
        - **Synonym**: Alternative label that maps to a canonical event
        - **Gap**: Period where data is missing (>15s between timestamps by default)
        """)

    # Import Settings section
    with st.expander("Import Settings", expanded=False):
        col_cfg1, col_cfg2 = st.columns(2)

        with col_cfg1:
            st.markdown("**Participant ID Pattern**")

            # Predefined pattern dropdown
            pattern_options = list(PREDEFINED_PATTERNS.keys()) + ["Custom pattern..."]
            selected_pattern_name = st.selectbox(
                "Select pattern format",
                options=pattern_options,
                index=0,
                key="pattern_selector",
                help="Choose a predefined pattern or select 'Custom pattern...' to enter your own",
            )

            # Get the pattern based on selection
            if selected_pattern_name == "Custom pattern...":
                id_pattern = st.text_input(
                    "Custom regex pattern",
                    value=DEFAULT_ID_PATTERN,
                    help="Regex pattern with named group 'participant'",
                    key="id_pattern_input",
                )
            else:
                id_pattern = PREDEFINED_PATTERNS[selected_pattern_name]
                st.code(id_pattern, language=None)

            # Real-time validation for regex pattern
            pattern_error = validate_regex_pattern(id_pattern)
            if pattern_error:
                st.error(f"Invalid regex: {pattern_error}")
            elif "(?P<participant>" not in id_pattern:
                st.warning("Pattern should include named group '(?P<participant>...)'")

        with col_cfg2:
            st.markdown("**RR Cleaning Thresholds**")

            def update_cleaning_config():
                """Callback to update cleaning config and clear cache."""
                st.session_state.cleaning_config = CleaningConfig(
                    rr_min_ms=st.session_state.rr_min_input,
                    rr_max_ms=st.session_state.rr_max_input,
                    sudden_change_pct=st.session_state.sudden_change_input,
                )
                cached_load_hrv_logger_preview.clear()

            col_rr1, col_rr2 = st.columns(2)
            with col_rr1:
                st.number_input(
                    "Min RR (ms)",
                    min_value=200,
                    max_value=1000,
                    value=st.session_state.cleaning_config.rr_min_ms,
                    step=10,
                    key="rr_min_input",
                    on_change=update_cleaning_config,
                )
            with col_rr2:
                st.number_input(
                    "Max RR (ms)",
                    min_value=1000,
                    max_value=3000,
                    value=st.session_state.cleaning_config.rr_max_ms,
                    step=10,
                    key="rr_max_input",
                    on_change=update_cleaning_config,
                )
            st.slider(
                "Sudden change threshold",
                min_value=0.0,
                max_value=1.0,
                value=st.session_state.cleaning_config.sudden_change_pct,
                step=0.05,
                format="%.2f",
                key="sudden_change_input",
                on_change=update_cleaning_config,
            )

    # Data directory input
    col1, col2 = st.columns([3, 1])
    with col1:
        data_dir_input = st.text_input(
            "Data directory path",
            value=st.session_state.data_dir or "data/raw/hrv_logger",
            help="Path to folder containing HRV Logger RR and Events CSV files",
        )
    with col2:
        st.write("")  # Spacer
        st.write("")  # Spacer
        if st.button("Load Data", type="primary", use_container_width=True):
            data_path = Path(data_dir_input).expanduser()
            if data_path.exists():
                st.session_state.data_dir = str(data_path)

                with st.status("Loading recordings...", expanded=True) as status:
                    try:
                        st.write("Discovering recordings...")

                        config_dict = {
                            "rr_min_ms": st.session_state.cleaning_config.rr_min_ms,
                            "rr_max_ms": st.session_state.cleaning_config.rr_max_ms,
                            "sudden_change_pct": st.session_state.cleaning_config.sudden_change_pct,
                        }
                        summaries = cached_load_hrv_logger_preview(
                            str(data_path),
                            pattern=id_pattern,
                            config_dict=config_dict,
                            gui_events_dict=st.session_state.all_events,
                        )

                        st.write(f"Processing {len(summaries)} participant(s)...")
                        st.session_state.summaries = summaries

                        # Auto-assign to Default group if not assigned
                        for summary in summaries:
                            if summary.participant_id not in st.session_state.participant_groups:
                                st.session_state.participant_groups[summary.participant_id] = "Default"

                        status.update(label=f"Loaded {len(summaries)} participant(s)", state="complete")
                        show_toast(f"Loaded {len(summaries)} participant(s)", icon="success")
                    except Exception as e:
                        status.update(label="Error loading data", state="error")
                        st.error(f"Error loading data: {e}")
            else:
                st.error(f"Directory not found: {data_path}")

    # Store id_pattern for use by other tabs
    st.session_state.id_pattern = id_pattern

    if st.session_state.summaries:
        st.markdown("---")
        _render_participants_table()


def _render_participants_table():
    """Render the participants overview table."""
    st.subheader("Participants Overview")

    # Smart status summary - only show issues if they exist
    issues = []
    total_participants = len(st.session_state.summaries)

    # Check for high artifact rates
    high_artifact = [s for s in st.session_state.summaries if s.artifact_ratio > 0.15]
    if high_artifact:
        issues.append(f"**{len(high_artifact)}** participant(s) with high artifact rates (>15%)")

    # Check for duplicates
    with_duplicates = [s for s in st.session_state.summaries if s.duplicate_rr_intervals > 0]
    if with_duplicates:
        issues.append(f"**{len(with_duplicates)}** participant(s) with duplicate RR intervals")

    # Check for multiple files
    with_multi_files = [s for s in st.session_state.summaries
                       if getattr(s, 'rr_file_count', 1) > 1 or getattr(s, 'events_file_count', 0) > 1]
    if with_multi_files:
        issues.append(f"**{len(with_multi_files)}** participant(s) with multiple files (merged)")

    # Check for missing events
    no_events = [s for s in st.session_state.summaries if s.events_detected == 0]
    if no_events:
        issues.append(f"**{len(no_events)}** participant(s) with no events detected")

    # Display status summary
    if issues:
        with st.container():
            st.markdown("**Issues Detected:**")
            for issue in issues:
                st.markdown(f"- {issue}")
            st.markdown("---")
    else:
        st.success(f"All {total_participants} participants look good! No issues detected.")

    # Create editable dataframe
    participants_data = []
    loaded_participants = cached_load_participants()

    for summary in st.session_state.summaries:
        recording_dt_str = ""
        if summary.recording_datetime:
            recording_dt_str = summary.recording_datetime.strftime("%Y-%m-%d %H:%M")

        # Show file counts
        rr_count = getattr(summary, 'rr_file_count', 1)
        ev_count = getattr(summary, 'events_file_count', 1 if summary.events_detected > 0 else 0)
        files_str = f"{rr_count}RR/{ev_count}Ev"
        if rr_count > 1 or ev_count > 1:
            files_str = f"* {files_str}"

        quality_badge = get_quality_badge(100, summary.artifact_ratio)

        participants_data.append({
            "Participant": summary.participant_id,
            "Quality": quality_badge,
            "Saved": "Y" if summary.participant_id in loaded_participants else "N",
            "Files": files_str,
            "Date/Time": recording_dt_str,
            "Group": st.session_state.participant_groups.get(summary.participant_id, "Default"),
            "Total Beats": summary.total_beats,
            "Retained": summary.retained_beats,
            "Duplicates": summary.duplicate_rr_intervals,
            "Artifacts (%)": f"{summary.artifact_ratio * 100:.1f}",
            "Duration (min)": f"{summary.duration_s / 60:.1f}",
            "Events": summary.events_detected,
            "Total Events": summary.events_detected + summary.duplicate_events,
            "Duplicate Events": summary.duplicate_events,
            "RR Range (ms)": f"{int(summary.rr_min_ms)}-{int(summary.rr_max_ms)}",
            "Mean RR (ms)": f"{summary.rr_mean_ms:.0f}",
        })

    df_participants = pd.DataFrame(participants_data)

    # Editable dataframe
    edited_df = st.data_editor(
        df_participants,
        column_config={
            "Participant": st.column_config.TextColumn("Participant", disabled=True, width="medium"),
            "Quality": st.column_config.TextColumn("Quality", disabled=True, width="small",
                help="Green=Good (<5% artifacts), Yellow=Moderate (5-15%), Red=Poor (>15%)"),
            "Saved": st.column_config.TextColumn("Saved", disabled=True, width="small"),
            "Files": st.column_config.TextColumn("Files", disabled=True, width="small",
                help="RR files / Events files. * indicates multiple files (merged)"),
            "Group": st.column_config.SelectboxColumn("Group", options=list(st.session_state.groups.keys()),
                required=True, help="Assign participant to a group", width="medium"),
            "Total Beats": st.column_config.NumberColumn("Total Beats", disabled=True, format="%d"),
            "Retained": st.column_config.NumberColumn("Retained", disabled=True, format="%d"),
            "Artifacts (%)": st.column_config.TextColumn("Artifacts (%)", disabled=True, width="small"),
            "Total Events": st.column_config.NumberColumn("Total Events", disabled=True, format="%d"),
            "Duplicate Events": st.column_config.NumberColumn("Duplicate Events", disabled=True, format="%d"),
        },
        use_container_width=True,
        hide_index=True,
        key="participants_table",
        disabled=["Participant", "Saved", "Date/Time", "Total Beats", "Retained", "Duplicates",
                  "Artifacts (%)", "Duration (min)", "Events", "Total Events", "Duplicate Events",
                  "RR Range (ms)", "Mean RR (ms)"]
    )

    # Auto-save group assignments when changed
    groups_changed = False
    for idx, row in edited_df.iterrows():
        participant_id = row["Participant"]
        new_group = row["Group"]
        old_group = st.session_state.participant_groups.get(participant_id)
        if old_group != new_group:
            st.session_state.participant_groups[participant_id] = new_group
            groups_changed = True

    if groups_changed:
        save_participant_data()
        cached_load_participants.clear()
        show_toast("Group assignments saved", icon="success")

    # Show warning if any participant has duplicate RR intervals
    high_duplicates = [
        (row["Participant"], row["Duplicates"])
        for _, row in df_participants.iterrows()
        if row["Duplicates"] > 0
    ]
    if high_duplicates:
        st.warning(
            f"**Duplicate RR intervals detected!** "
            f"{len(high_duplicates)} participant(s) have duplicate RR intervals that were removed."
        )
        with st.expander("Show participants with duplicates"):
            for pid, dup_count in high_duplicates:
                st.text(f"- {pid}: {dup_count} duplicates removed")

    # Download button
    csv_participants = df_participants.to_csv(index=False)
    st.download_button(
        label="Download Participants CSV",
        data=csv_participants,
        file_name="participants_overview.csv",
        mime="text/csv",
        use_container_width=False,
    )
    st.info("**Tip:** Group assignments save automatically when you change them in the table above.")
