"""Setup tab - Event mapping, Group management, and Sections.

Combines the Events, Groups, and Sections functionality into one
organized tab with nested sub-tabs.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from rrational.gui.persistence import (
    load_sections,
    load_event_sequences,
    save_event_sequences,
    save_condition_labels,
)
from rrational.gui.shared import (
    auto_save_config,
    show_toast,
    update_normalizer,
    validate_regex_pattern,
)


def render_setup_tab():
    """Render the Setup tab with nested sub-tabs for Events, Groups, Playlists, Sections."""
    st.header("Setup")

    # Use radio buttons instead of tabs to properly persist selection state
    # st.tabs() doesn't persist state across reruns which causes tab jumping
    if "setup_subtab" not in st.session_state:
        st.session_state.setup_subtab = "Events"

    # Use columns to prevent radio button from taking full width and causing scroll issues
    col_radio, _ = st.columns([2, 3])
    with col_radio:
        selected_subtab = st.radio(
            "Select section:",
            ["Events", "Groups", "Sequences", "Sections"],
            key="setup_subtab",
            horizontal=True,
            label_visibility="collapsed"
        )

    st.markdown("---")

    if selected_subtab == "Events":
        _render_events_section()
    elif selected_subtab == "Groups":
        _render_groups_section()
    elif selected_subtab == "Sequences":
        _render_event_sequences_section()
    elif selected_subtab == "Sections":
        _render_sections_section()

    # Scroll to top after content is rendered (fixes issue where page scrolls to middle)
    if st.session_state.get("_setup_scroll_to_top", False):
        st.session_state._setup_scroll_to_top = False
        st.components.v1.html(
            """
            <script>
                setTimeout(function() {
                    var container = window.parent.document.querySelector('[data-testid="stAppViewContainer"]');
                    if (container) container.scrollTop = 0;
                    window.parent.scrollTo(0, 0);
                }, 50);
            </script>
            """,
            height=0
        )


def _render_events_section():
    """Render the Events sub-section."""
    st.subheader("Event Mapping")

    with st.expander("Help - Event Mapping", expanded=False):
        st.markdown("""
        ### What are Events?

        Events are **markers in time** that define key moments in your HRV recording, such as:
        - `measurement_start` / `measurement_end` - Beginning and end of data collection
        - `rest_pre_start` / `rest_pre_end` - Pre-measurement rest period
        - `pause_start` / `pause_end` - Break between measurement blocks

        ### How Event Matching Works

        1. **Raw Label**: The label written in the HRV Logger (e.g., "Ruhe Pre Start")
        2. **Synonym Pattern**: A regex pattern to match variations (e.g., `ruhe[ _-]?pre[ _-]?start`)
        3. **Canonical Name**: The standardized internal name (e.g., `rest_pre_start`)

        The app automatically matches raw labels to canonical names using the synonym patterns you define.

        ### Tips for Synonyms

        - Use `[ _-]?` to match optional spaces, underscores, or hyphens
        - Use `.*` to match any characters (e.g., `start.*measurement`)
        - All matching is **case-insensitive** (lowercase automatically)
        """)

    st.info("All event matching is done in **lowercase** automatically to reduce the number of synonyms needed.")

    # Create new event
    with st.expander("Create New Event"):
        new_event_name = st.text_input("Event Name (canonical)", key="new_event_name_global")
        new_event_synonyms = st.text_area(
            "Synonyms (one per line, regex patterns supported)",
            key="new_event_synonyms_global",
            help="Enter regex patterns, one per line. All matching is lowercase. Example: ruhe[ _-]?pre[ _-]?start"
        )

        # Real-time validation of event name
        if new_event_name:
            if new_event_name in st.session_state.all_events:
                st.warning(f"Event '{new_event_name}' already exists")
            elif not new_event_name.replace("_", "").isalnum():
                st.warning("Event name should be alphanumeric with underscores")

        # Validate synonyms as regex patterns
        if new_event_synonyms:
            invalid_patterns = []
            for line in new_event_synonyms.split("\n"):
                if line.strip():
                    error = validate_regex_pattern(line.strip())
                    if error:
                        invalid_patterns.append(f"'{line.strip()}': {error}")
            if invalid_patterns:
                st.error("Invalid regex patterns:\n" + "\n".join(invalid_patterns))

        def create_event():
            """Callback to create new event."""
            # Read from session state to avoid stale closure variables
            event_name = st.session_state.get("new_event_name_global", "").strip()
            synonyms_raw = st.session_state.get("new_event_synonyms_global", "")

            if event_name and event_name not in st.session_state.all_events:
                synonyms_list = [s.strip().lower() for s in synonyms_raw.split("\n") if s.strip()]
                st.session_state.all_events[event_name] = synonyms_list
                auto_save_config()
                update_normalizer()
                show_toast(f"Created event '{event_name}'", icon="success")
                # Clear the input fields after successful creation
                st.session_state.new_event_name_global = ""
                st.session_state.new_event_synonyms_global = ""
            elif event_name in st.session_state.all_events:
                show_toast(f"Event '{event_name}' already exists", icon="error")
            else:
                show_toast("Please enter an event name", icon="error")

        st.button("Create Event", key="create_event_btn_global", on_click=create_event, type="primary")

    st.markdown("---")

    # Show all events
    st.subheader("All Available Events")
    st.info(f"**{len(st.session_state.all_events)} event(s) defined**")

    # Define callbacks outside loop for better performance
    def _rename_event(old_name: str):
        """Callback to rename event - reads new name from session_state."""
        new_name = st.session_state.get(f"edit_event_name_{old_name}", old_name)
        if new_name != old_name and new_name not in st.session_state.all_events:
            st.session_state.all_events[new_name] = st.session_state.all_events.pop(old_name)
            for group_data in st.session_state.groups.values():
                if old_name in group_data.get("expected_events", {}):
                    group_data["expected_events"][new_name] = group_data["expected_events"].pop(old_name)
            auto_save_config()
            update_normalizer()
            show_toast(f"Renamed to '{new_name}'", icon="success")
        elif new_name == old_name:
            show_toast("Name unchanged", icon="info")
        else:
            show_toast(f"Event '{new_name}' already exists", icon="error")

    def _delete_synonym(evt_name: str, idx: int):
        """Callback to delete synonym."""
        if evt_name not in st.session_state.all_events:
            return  # Event already deleted
        syn_list = st.session_state.all_events[evt_name]
        if idx < len(syn_list):
            syn_list.pop(idx)
            st.session_state.all_events[evt_name] = syn_list
            for group_data in st.session_state.groups.values():
                if evt_name in group_data.get("expected_events", {}):
                    group_data["expected_events"][evt_name] = syn_list.copy()
            auto_save_config()
            update_normalizer()
            show_toast("Synonym deleted", icon="success")

    def _add_synonym(evt_name: str):
        """Callback to add synonym - reads new synonym from session_state."""
        if evt_name not in st.session_state.all_events:
            return  # Event already deleted
        new_syn = st.session_state.get(f"new_syn_{evt_name}", "")
        synonym_lower = new_syn.strip().lower()
        syn_list = st.session_state.all_events[evt_name]
        if synonym_lower and synonym_lower not in syn_list:
            syn_list.append(synonym_lower)
            st.session_state.all_events[evt_name] = syn_list
            for group_data in st.session_state.groups.values():
                if evt_name in group_data.get("expected_events", {}):
                    group_data["expected_events"][evt_name] = syn_list.copy()
            auto_save_config()
            update_normalizer()
            show_toast(f"Added '{synonym_lower}'", icon="success")
            # Clear input
            st.session_state[f"new_syn_{evt_name}"] = ""
        elif synonym_lower in syn_list:
            show_toast("Synonym already exists", icon="warning")
        else:
            show_toast("Please enter a synonym", icon="error")

    def _delete_event(evt_name: str):
        """Callback to delete event."""
        if evt_name not in st.session_state.all_events:
            show_toast(f"Event '{evt_name}' already deleted", icon="info")
            return  # Already deleted
        del st.session_state.all_events[evt_name]
        for group_data in st.session_state.groups.values():
            if evt_name in group_data.get("expected_events", {}):
                del group_data["expected_events"][evt_name]
        auto_save_config()
        update_normalizer()
        show_toast(f"Deleted event '{evt_name}'", icon="success")

    if st.session_state.all_events:
        for event_name, synonyms in list(st.session_state.all_events.items()):
            with st.expander(f"Event: {event_name} ({len(synonyms)} synonym(s))", expanded=False):
                # Editable event name
                col1, col2 = st.columns([3, 1])
                with col1:
                    new_event_name_edit = st.text_input(
                        "Event Name",
                        value=event_name,
                        key=f"edit_event_name_{event_name}"
                    )

                # Real-time validation
                name_valid = True
                if new_event_name_edit != event_name:
                    if new_event_name_edit in st.session_state.all_events:
                        st.warning(f"Event '{new_event_name_edit}' already exists")
                        name_valid = False
                    elif not new_event_name_edit.replace("_", "").isalnum():
                        st.warning("Event name should be alphanumeric with underscores")
                        name_valid = False

                with col2:
                    st.button(
                        "Save Name",
                        key=f"save_event_name_{event_name}",
                        on_click=_rename_event,
                        args=(event_name,),
                        disabled=not name_valid or new_event_name_edit == event_name,
                        use_container_width=True,
                    )

                # Show used in groups
                used_in_groups = [
                    gname for gname, gdata in st.session_state.groups.items()
                    if event_name in gdata.get("expected_events", {})
                ]
                if used_in_groups:
                    st.info(f"Used in groups: {', '.join(used_in_groups)}")
                else:
                    st.info("Not used in any groups yet")

                st.markdown("---")
                st.markdown("**Synonyms:**")

                # Display and manage synonyms
                if synonyms:
                    for syn_idx, synonym in enumerate(synonyms):
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.text(synonym)
                        with col2:
                            st.button(
                                "X",
                                key=f"delete_syn_{event_name}_{syn_idx}",
                                on_click=_delete_synonym,
                                args=(event_name, syn_idx),
                                help="Delete this synonym",
                            )
                else:
                    st.info("No synonyms defined")

                # Add new synonym
                st.markdown("**Add New Synonym:**")
                col1, col2 = st.columns([3, 1])
                with col1:
                    new_synonym = st.text_input(
                        "New synonym (regex pattern)",
                        key=f"new_syn_{event_name}",
                        placeholder="e.g., rest[ _-]?start"
                    )

                    if new_synonym:
                        error = validate_regex_pattern(new_synonym.strip())
                        if error:
                            st.error(f"Invalid regex: {error}")
                        elif new_synonym.strip().lower() in synonyms:
                            st.warning("This synonym already exists")

                with col2:
                    st.write("")
                    st.write("")
                    st.button(
                        "Add",
                        key=f"add_syn_btn_{event_name}",
                        on_click=_add_synonym,
                        args=(event_name,),
                        type="primary",
                        disabled=not new_synonym or validate_regex_pattern(new_synonym.strip()) is not None,
                    )

                # Delete event
                st.markdown("---")
                st.button(
                    f"Delete Event '{event_name}'",
                    key=f"delete_event_{event_name}",
                    on_click=_delete_event,
                    args=(event_name,),
                    type="secondary",
                    use_container_width=True,
                )
    else:
        st.info("No events defined yet. Create events above.")


def _render_groups_section():
    """Render the Groups sub-section."""
    st.subheader("Group Management")

    with st.expander("Help - Groups & Playlists", expanded=False):
        st.markdown("""
        ### Study Groups

        Groups define **which events are expected** for each participant. For example:
        - **Control Group**: May only need `rest_pre`, `measurement`, `rest_post`
        - **Intervention Group**: May need additional events like `pause_start`, `pause_end`

        When you assign a participant to a group, the app will check if all expected events
        are present and warn you about missing ones.

        ### Playlist Groups (Music Randomization)

        If your study involves music interventions with different randomization orders:
        - **R1**: music_1 -> music_2 -> music_3
        - **R2**: music_1 -> music_3 -> music_2
        - etc.

        Assign participants to playlist groups. The playlist order is used when generating
        music section events in the **Participants** tab.
        """)

    st.markdown("Create groups, edit/rename/delete them, and assign events from the Event Mapping tab.")

    # Create new group
    with st.expander("Create New Group"):
        new_group_name = st.text_input("Group Name (internal ID)", key="new_group_name")
        new_group_label = st.text_input("Group Label (display name)", key="new_group_label")

        if new_group_name:
            if new_group_name in st.session_state.groups:
                st.warning(f"Group '{new_group_name}' already exists")
            elif not new_group_name.replace("_", "").replace("-", "").isalnum():
                st.warning("Group name should be alphanumeric with underscores/hyphens")

        def create_group():
            """Callback to create new group."""
            if new_group_name and new_group_name not in st.session_state.groups:
                st.session_state.groups[new_group_name] = {
                    "label": new_group_label or new_group_name,
                    "expected_events": {},
                    "selected_sections": []
                }
                auto_save_config()
                show_toast(f"Created group '{new_group_name}'", icon="success")
            elif new_group_name in st.session_state.groups:
                show_toast(f"Group '{new_group_name}' already exists", icon="error")
            else:
                show_toast("Please enter a group name", icon="error")

        st.button("Create Group", key="create_group_btn", on_click=create_group, type="primary")

    st.markdown("---")

    # Manage existing groups
    st.subheader("Existing Groups")

    for group_name, group_data in list(st.session_state.groups.items()):
        with st.expander(f"{group_name} - {group_data['label']}", expanded=(group_name == "Default")):

            st.markdown("**Edit Group:**")
            col1, col2 = st.columns(2)
            with col1:
                new_name = st.text_input(
                    "Group Name (ID)",
                    value=group_name,
                    key=f"edit_group_name_{group_name}"
                )
            with col2:
                new_label = st.text_input(
                    "Group Label",
                    value=group_data["label"],
                    key=f"edit_group_label_{group_name}"
                )

            def save_group_changes(old_name):
                """Callback to save group changes."""
                # Read from session_state to avoid stale closure variables
                new_name_val = st.session_state.get(f"edit_group_name_{old_name}", old_name)
                new_label_val = st.session_state.get(f"edit_group_label_{old_name}", old_name)

                current_name = old_name
                if new_name_val != old_name:
                    st.session_state.groups[new_name_val] = st.session_state.groups.pop(old_name)
                    for pid, gname in st.session_state.participant_groups.items():
                        if gname == old_name:
                            st.session_state.participant_groups[pid] = new_name_val
                    current_name = new_name_val

                st.session_state.groups[current_name]["label"] = new_label_val
                auto_save_config()
                show_toast(f"Saved changes to '{current_name}'", icon="success")

            st.button(
                f"Save Changes to {group_name}",
                key=f"save_group_{group_name}",
                on_click=save_group_changes,
                args=(group_name,),
                type="primary",
            )

            st.markdown("---")

            participant_count = sum(1 for g in st.session_state.participant_groups.values() if g == group_name)
            st.markdown(f"**Participants in this group:** {participant_count}")

            # Sections selection
            st.markdown("**Select Sections for Analysis:**")
            available_sections = list(st.session_state.sections.keys()) if hasattr(st.session_state, 'sections') else []
            if available_sections:
                def update_sections(grp_name):
                    """Callback to update sections selection."""
                    st.session_state.groups[grp_name]["selected_sections"] = st.session_state[f"sections_select_{grp_name}"]
                    auto_save_config()
                    show_toast(f"Sections updated for {grp_name}", icon="success")

                st.multiselect(
                    "Sections to use in analysis",
                    options=available_sections,
                    default=group_data.get("selected_sections", []),
                    key=f"sections_select_{group_name}",
                    help="Choose which sections to analyze for participants in this group (saves automatically)",
                    on_change=update_sections,
                    args=(group_name,),
                )
            else:
                st.info("No sections defined yet. Create sections in the Sections tab first.")

            st.markdown("---")

            # Expected events
            st.markdown("**Select Expected Events:**")
            expected_events = group_data.get("expected_events", {})

            st.markdown("*Click events to add/remove from this group (saves automatically):*")

            num_cols = 3
            cols = st.columns(num_cols)

            available_event_names = list(st.session_state.all_events.keys())
            for idx, event_name in enumerate(available_event_names):
                col_idx = idx % num_cols
                with cols[col_idx]:
                    is_selected = event_name in expected_events

                    def toggle_event(grp_name, evt_name, currently_selected):
                        """Callback to toggle event selection."""
                        # Ensure expected_events exists
                        if "expected_events" not in st.session_state.groups[grp_name]:
                            st.session_state.groups[grp_name]["expected_events"] = {}
                        exp_events = st.session_state.groups[grp_name]["expected_events"]
                        if st.session_state[f"event_select_{grp_name}_{evt_name}"]:
                            if evt_name not in exp_events:
                                exp_events[evt_name] = st.session_state.all_events[evt_name].copy()
                                st.session_state.groups[grp_name]["expected_events"] = exp_events
                                auto_save_config()
                                show_toast(f"Added '{evt_name}' to {grp_name}", icon="success")
                        else:
                            if evt_name in exp_events:
                                del exp_events[evt_name]
                                st.session_state.groups[grp_name]["expected_events"] = exp_events
                                auto_save_config()
                                show_toast(f"Removed '{evt_name}' from {grp_name}", icon="info")

                    st.checkbox(
                        event_name,
                        value=is_selected,
                        key=f"event_select_{group_name}_{event_name}",
                        on_change=toggle_event,
                        args=(group_name, event_name, is_selected),
                    )

            st.markdown("---")

            # Show currently selected events
            if expected_events:
                st.markdown("**Currently Selected Events:**")
                events_list = []
                for event_name_item, synonyms in expected_events.items():
                    events_list.append({
                        "Event Name": event_name_item,
                        "Synonyms": ", ".join(synonyms[:3]) + ("..." if len(synonyms) > 3 else "") if synonyms else "No synonyms",
                    })

                df_group_events = pd.DataFrame(events_list)
                st.dataframe(df_group_events, width='stretch', hide_index=True)

                csv_group_events = df_group_events.to_csv(index=False)
                st.download_button(
                    label=f"Download Events for {group_name}",
                    data=csv_group_events,
                    file_name=f"group_events_{group_name}.csv",
                    mime="text/csv",
                    key=f"download_group_{group_name}"
                )
            else:
                st.info("No events selected for this group yet. Select events above.")

            # Delete group
            st.markdown("---")

            def delete_group(grp_name):
                """Callback to delete group."""
                for pid, gname in st.session_state.participant_groups.items():
                    if gname == grp_name:
                        st.session_state.participant_groups[pid] = "Default"
                del st.session_state.groups[grp_name]
                auto_save_config()
                show_toast(f"Deleted group '{grp_name}' and reassigned participants to Default", icon="success")

            st.button(
                f"Delete Group '{group_name}'",
                key=f"delete_group_{group_name}",
                on_click=delete_group,
                args=(group_name,),
                type="secondary",
            )

    st.markdown("---")
    st.info("**All changes save automatically** when you modify group settings or select events.")


def _render_event_sequences_section():
    """Render the Event Sequences sub-section for condition randomization."""
    st.subheader("Event Sequences (Condition Randomization)")

    with st.expander("Help - Event Sequences", expanded=False):
        st.markdown("""
        ### What are Event Sequences?

        Event sequences define the **condition order** for randomization in your study.
        Each participant can be assigned to a sequence, which determines the order of
        conditions they experience (e.g., treatments, stimuli, music pieces).

        ### Example

        If your study has 3 conditions and 6 randomization sequences:
        - **sequence_01**: condition_a -> condition_b -> condition_c
        - **sequence_02**: condition_a -> condition_c -> condition_b
        - **sequence_03**: condition_b -> condition_a -> condition_c
        - etc.

        ### How to Use

        1. Define event sequences here with their condition order
        2. Assign participants to sequences in the Data tab
        3. Use Repeating Section Analysis to analyze HRV by condition type
        """)

    st.markdown("""
    Define condition order for each randomization group. Participants assigned to a sequence
    will have condition events generated in the specified order.
    """)

    # Initialize event sequences (already done at app startup, but ensure present)
    if "event_sequences" not in st.session_state:
        loaded = load_event_sequences()
        if loaded:
            st.session_state.event_sequences = loaded
        else:
            st.session_state.event_sequences = {}

    if "participant_sequences" not in st.session_state:
        st.session_state.participant_sequences = {}

    # Create new event sequence
    with st.expander("Create New Event Sequence"):
        new_seq_name = st.text_input(
            "Sequence ID (e.g., sequence_01)",
            key="new_sequence_name"
        )
        new_seq_label = st.text_input("Sequence Label", key="new_sequence_label")
        new_seq_order = st.text_input(
            "Condition Order (comma-separated, e.g., condition_a, condition_b, condition_c)",
            key="new_sequence_order"
        )

        def create_event_sequence():
            if new_seq_name and new_seq_name not in st.session_state.event_sequences:
                order_list = [m.strip() for m in new_seq_order.split(",") if m.strip()]
                if not order_list:
                    order_list = ["condition_a", "condition_b", "condition_c"]
                st.session_state.event_sequences[new_seq_name] = {
                    "label": new_seq_label or new_seq_name,
                    "condition_order": order_list
                }
                save_event_sequences(st.session_state.event_sequences)
                show_toast(f"Created event sequence '{new_seq_name}'", icon="success")
            elif new_seq_name in st.session_state.event_sequences:
                show_toast(f"Event sequence '{new_seq_name}' already exists", icon="error")

        st.button("Create Event Sequence", key="create_sequence_btn", on_click=create_event_sequence)

    # Show existing event sequences
    st.markdown("---")
    st.subheader("Existing Event Sequences")

    if not st.session_state.event_sequences:
        st.info("No event sequences defined yet. Create one above.")
    else:
        for seq_name, seq_data in list(st.session_state.event_sequences.items()):
            condition_order = seq_data.get('condition_order', seq_data.get('music_order', []))
            with st.expander(f"{seq_name} - {seq_data.get('label', seq_name)}"):
                # Edit label
                new_label = st.text_input(
                    "Label",
                    value=seq_data.get('label', seq_name),
                    key=f"edit_seq_label_{seq_name}"
                )

                st.markdown(f"**Condition Order:** {' -> '.join(condition_order)}")

                new_order = st.text_input(
                    "Edit Condition Order (comma-separated)",
                    value=", ".join(condition_order),
                    key=f"edit_seq_order_{seq_name}"
                )

                col1, col2, col3 = st.columns(3)
                with col1:
                    def save_sequence_changes(s_name, new_ord, new_lbl):
                        order_list = [m.strip() for m in new_ord.split(",") if m.strip()]
                        if order_list:
                            st.session_state.event_sequences[s_name]["condition_order"] = order_list
                        st.session_state.event_sequences[s_name]["label"] = new_lbl
                        save_event_sequences(st.session_state.event_sequences)
                        show_toast(f"Updated '{s_name}'", icon="success")

                    st.button(
                        "Save Changes",
                        key=f"save_seq_{seq_name}",
                        on_click=save_sequence_changes,
                        args=(seq_name, new_order, new_label)
                    )

                with col3:
                    def delete_sequence(s_name):
                        del st.session_state.event_sequences[s_name]
                        for pid in list(st.session_state.participant_sequences.keys()):
                            if st.session_state.participant_sequences.get(pid) == s_name:
                                del st.session_state.participant_sequences[pid]
                        for pid in list(st.session_state.get("participant_randomizations", {}).keys()):
                            if st.session_state.participant_randomizations.get(pid) == s_name:
                                del st.session_state.participant_randomizations[pid]
                        save_event_sequences(st.session_state.event_sequences)
                        show_toast(f"Deleted event sequence '{s_name}'", icon="success")

                    st.button(
                        "Delete",
                        key=f"delete_seq_{seq_name}",
                        on_click=delete_sequence,
                        args=(seq_name,),
                        type="secondary"
                    )

                # Show participants assigned to this sequence
                participants_in_group = [
                    pid for pid, s in st.session_state.get("participant_randomizations", {}).items()
                    if s == seq_name
                ]
                if participants_in_group:
                    st.markdown(f"**Participants:** {', '.join(participants_in_group)}")
                else:
                    st.caption("No participants assigned yet")

    # Condition Labels Section
    st.markdown("---")
    st.subheader("Condition Labels")
    st.markdown("""
    Define labels and descriptions for your conditions (e.g., `condition_a`, `treatment_1`).
    These labels will appear in exports and the codebook.
    """)

    # Collect all unique conditions from sequence orders
    all_conditions = set()
    for s_data in st.session_state.get("event_sequences", {}).values():
        all_conditions.update(s_data.get("condition_order", s_data.get("music_order", [])))
    all_conditions = sorted(all_conditions)

    if all_conditions:
        if "condition_labels" not in st.session_state:
            st.session_state.condition_labels = {}

        label_data = []
        for condition in all_conditions:
            current_data = st.session_state.condition_labels.get(condition, {})
            label_data.append({
                "Code": condition,
                "Label": current_data.get("label", condition.replace("_", " ").title()),
                "Description": current_data.get("description", ""),
            })

        df_labels = pd.DataFrame(label_data)

        edited_labels = st.data_editor(
            df_labels,
            width='stretch',
            hide_index=True,
            key="condition_labels_table",
            column_config={
                "Code": st.column_config.TextColumn("Code", disabled=True, help="Internal identifier"),
                "Label": st.column_config.TextColumn("Label", help="Short display name"),
                "Description": st.column_config.TextColumn("Description", help="Full description", width="large"),
            }
        )

        def save_condition_labels_callback():
            """Save condition labels from the edited table."""
            for _, row in edited_labels.iterrows():
                code = row["Code"]
                st.session_state.condition_labels[code] = {
                    "label": row["Label"],
                    "description": row["Description"],
                }
            save_condition_labels(st.session_state.condition_labels)
            show_toast("Condition labels saved", icon="success")

        st.button("Save Condition Labels", key="save_condition_labels_btn", on_click=save_condition_labels_callback, type="primary")
    else:
        st.info("No conditions defined yet. Add them to event sequences above.")

    st.markdown("---")
    st.info("**All changes save automatically.** Condition labels are used in the Data tab.")


def _render_sections_section():
    """Render the Sections sub-section."""
    st.subheader("Sections")

    with st.expander("Help - Sections", expanded=False):
        st.markdown("""
        ### What are Sections?

        Sections define **time ranges** between events for HRV analysis. Each section has:
        - **Code**: Internal identifier (e.g., `pre_pause`)
        - **Label**: Short display name (e.g., `Pre-Pause`)
        - **Start/End Events**: The events that mark the beginning and end
        - **Duration**: Expected duration in minutes
        - **Tolerance**: Acceptable deviation from expected duration

        ### Validation

        In the **Participants** tab, sections are validated:
        - Start and end events present
        - Duration within tolerance of expected

        ### Example

        | Code | Label | Start Event | End Event | Duration | Tolerance |
        |------|-------|-------------|-----------|----------|-----------|
        | pre_pause | Pre-Pause | measurement_start | pause_start | 90 min | 5 min |
        | rest_pre | Pre-Rest | rest_pre_start | rest_pre_end | 5 min | 1 min |
        """)

    st.markdown("Define time ranges (sections) between events for analysis.")

    # Initialize sections if not present
    if "sections" not in st.session_state:
        loaded_sections = load_sections()
        if not loaded_sections:
            # Default sections - start_events/end_events are lists (any of these events can start/end the section)
            st.session_state.sections = {
                "rest_pre": {"label": "Pre-Rest", "description": "Baseline rest period", "start_events": ["rest_pre_start"], "end_events": ["rest_pre_end"], "expected_duration_min": 5.0, "tolerance_min": 1.0},
                "pre_pause": {"label": "Pre-Pause", "description": "Music before pause", "start_events": ["measurement_start"], "end_events": ["pause_start"], "expected_duration_min": 90.0, "tolerance_min": 5.0},
                "post_pause": {"label": "Post-Pause", "description": "Music after pause", "start_events": ["pause_end"], "end_events": ["measurement_end"], "expected_duration_min": 90.0, "tolerance_min": 5.0},
                "rest_post": {"label": "Post-Rest", "description": "Post-measurement rest", "start_events": ["rest_post_start"], "end_events": ["rest_post_end"], "expected_duration_min": 5.0, "tolerance_min": 1.0},
            }
        else:
            # Migrate old format (start_event/end_event) to new format (start_events/end_events)
            for section_data in loaded_sections.values():
                if "start_event" in section_data and "start_events" not in section_data:
                    section_data["start_events"] = [section_data.pop("start_event")]
                if "end_event" in section_data and "end_events" not in section_data:
                    section_data["end_events"] = [section_data.pop("end_event")]
            st.session_state.sections = loaded_sections

    # Create new section - use form to prevent Enter key from triggering rerun
    with st.expander("Create New Section"):
        available_events = list(st.session_state.all_events.keys())

        with st.form("create_section_form", clear_on_submit=True, enter_to_submit=False):
            new_section_name = st.text_input("Section Code (internal ID)",
                                             help="e.g., music_01, rest_pre")
            new_section_label = st.text_input("Section Label (short name)",
                                              help="e.g., Music 1, Pre-Rest")
            new_section_desc = st.text_input("Description (detailed)",
                                             help="e.g., Brandenburg Concerto No. 3 - Bach")

            col1, col2 = st.columns(2)
            with col1:
                start_events = st.multiselect(
                    "Start Event(s)",
                    options=available_events,
                    default=[available_events[0]] if available_events else [],
                    help="Select one or more events. Section starts when ANY of these events occurs."
                )
            with col2:
                end_events = st.multiselect(
                    "End Event(s)",
                    options=available_events,
                    default=[available_events[1]] if len(available_events) > 1 else [],
                    help="Select one or more events. Section ends when ANY of these events occurs."
                )

            col3, col4 = st.columns(2)
            with col3:
                expected_duration = st.number_input("Expected Duration (min)", min_value=0.0, max_value=300.0, value=5.0,
                                                   help="Expected section duration in minutes")
            with col4:
                tolerance = st.number_input("Tolerance (min)", min_value=0.0, max_value=60.0, value=1.0,
                                           help="Acceptable deviation from expected duration")

            submitted = st.form_submit_button("Create Section", type="primary")

            if submitted:
                if new_section_name and new_section_name not in st.session_state.sections:
                    if not start_events:
                        st.error("Please select at least one start event")
                    elif not end_events:
                        st.error("Please select at least one end event")
                    elif not new_section_name.replace("_", "").isalnum():
                        st.error("Section name should be alphanumeric with underscores")
                    else:
                        st.session_state.sections[new_section_name] = {
                            "label": new_section_label or new_section_name,
                            "description": new_section_desc or "",
                            "start_events": list(start_events),  # List of possible start events
                            "end_events": list(end_events),  # List of possible end events
                            "expected_duration_min": expected_duration,
                            "tolerance_min": tolerance,
                        }
                        auto_save_config()
                        st.success(f"Created section '{new_section_name}'")
                elif new_section_name in st.session_state.sections:
                    st.error(f"Section '{new_section_name}' already exists")
                else:
                    st.error("Please enter a section name")

    st.markdown("---")

    # Show all sections
    st.subheader("All Defined Sections")

    if st.session_state.sections:
        sections_list = []
        for section_name, section_data in st.session_state.sections.items():
            # Support both old (start_event/end_event) and new (start_events/end_events) format
            start_events = section_data.get("start_events", [])
            if not start_events and "start_event" in section_data:
                start_events = [section_data["start_event"]]
            end_events = section_data.get("end_events", [])
            if not end_events and "end_event" in section_data:
                end_events = [section_data["end_event"]]
            sections_list.append({
                "Code": section_name,
                "Label": section_data.get("label", section_name),
                "Start Event(s)": ", ".join(start_events),  # Show as comma-separated
                "End Event(s)": ", ".join(end_events),  # Show as comma-separated
                "Duration (min)": section_data.get("expected_duration_min", 5.0),
                "Tolerance (min)": section_data.get("tolerance_min", 1.0),
            })

        df_sections = pd.DataFrame(sections_list)

        available_events = list(st.session_state.all_events.keys())
        edited_sections = st.data_editor(
            df_sections,
            width='stretch',
            hide_index=True,
            num_rows="dynamic",
            key="sections_table",
            column_config={
                "Code": st.column_config.TextColumn("Code", help="Internal identifier", width="small"),
                "Label": st.column_config.TextColumn("Label", help="Short display name", width="medium"),
                "Start Event(s)": st.column_config.TextColumn("Start Event(s)", help="Comma-separated list of events (any can start section)", width="medium"),
                "End Event(s)": st.column_config.TextColumn("End Event(s)", help="Comma-separated list of events (any can end section)", width="medium"),
                "Duration (min)": st.column_config.NumberColumn("Duration (min)", help="Expected duration in minutes", min_value=0.0, max_value=300.0, format="%.1f", width="small"),
                "Tolerance (min)": st.column_config.NumberColumn("Tolerance (min)", help="Acceptable deviation", min_value=0.0, max_value=60.0, format="%.1f", width="small"),
            }
        )

        # Use button detection instead of callback to avoid session_state issues
        if st.button("Save Section Changes", key="save_sections_btn", type="primary"):
            updated_sections = {}
            validation_errors = []
            valid_events = set(st.session_state.all_events.keys())

            # edited_sections is the DataFrame returned by data_editor
            for _, row in edited_sections.iterrows():
                section_code = row["Code"]
                if section_code:  # Skip empty rows
                    # Parse comma-separated start events (data_editor returns NaN for empty cells)
                    start_events_str = row.get("Start Event(s)", "")
                    if not isinstance(start_events_str, str) or pd.isna(start_events_str):
                        start_events_str = ""
                    start_events_list = [e.strip() for e in start_events_str.split(",") if e.strip()]
                    if not start_events_list:
                        start_events_list = ["measurement_start"]  # Fallback

                    # Validate start events exist
                    invalid_start = [e for e in start_events_list if e not in valid_events]
                    if invalid_start:
                        validation_errors.append(f"Section '{section_code}': invalid start event(s): {', '.join(invalid_start)}")

                    # Parse comma-separated end events (data_editor returns NaN for empty cells)
                    end_events_str = row.get("End Event(s)", "")
                    if not isinstance(end_events_str, str) or pd.isna(end_events_str):
                        end_events_str = ""
                    end_events_list = [e.strip() for e in end_events_str.split(",") if e.strip()]
                    if not end_events_list:
                        end_events_list = ["measurement_end"]  # Fallback

                    # Validate end events exist
                    invalid_end = [e for e in end_events_list if e not in valid_events]
                    if invalid_end:
                        validation_errors.append(f"Section '{section_code}': invalid end event(s): {', '.join(invalid_end)}")

                    updated_sections[section_code] = {
                        "label": row["Label"],
                        "description": "",  # Description removed from table view
                        "start_events": start_events_list,  # Store as list
                        "end_events": end_events_list,  # Store as list
                        "expected_duration_min": row.get("Duration (min)", 5.0),
                        "tolerance_min": row.get("Tolerance (min)", 1.0),
                    }

            if validation_errors:
                for err in validation_errors:
                    st.error(err)
                st.warning("Define missing events in the **Events** tab first, or correct the event names.")
            else:
                st.session_state.sections = updated_sections
                auto_save_config()
                st.success("Saved section changes")

        csv_sections = df_sections.to_csv(index=False)
        st.download_button(
            label="Download Sections CSV",
            data=csv_sections,
            file_name="sections.csv",
            mime="text/csv",
            key="download_sections"
        )
    else:
        st.info("No sections defined yet. Create sections above.")

    # Codebook Export Section
    st.markdown("---")
    st.subheader("Codebook Export")
    st.markdown("Export all codes, labels, and descriptions for documentation.")

    def generate_codebook():
        """Generate a comprehensive codebook with all definitions."""
        codebook_data = []

        # Events
        for event_name, synonyms in st.session_state.get("all_events", {}).items():
            codebook_data.append({
                "Category": "Event",
                "Code": event_name,
                "Label": event_name.replace("_", " ").title(),
                "Description": f"Synonyms: {', '.join(synonyms[:3])}" if synonyms else "",
            })

        # Sections
        for section_code, section_data in st.session_state.get("sections", {}).items():
            codebook_data.append({
                "Category": "Section",
                "Code": section_code,
                "Label": section_data.get("label", section_code),
                "Description": section_data.get("description", ""),
            })

        # Groups
        for group_id, group_data in st.session_state.get("groups", {}).items():
            codebook_data.append({
                "Category": "Group",
                "Code": group_id,
                "Label": group_data.get("label", group_id),
                "Description": f"Expected events: {len(group_data.get('expected_events', {}))}",
            })

        # Playlist Groups
        for pl_id, pl_data in st.session_state.get("playlist_groups", {}).items():
            codebook_data.append({
                "Category": "Playlist",
                "Code": pl_id,
                "Label": pl_data.get("label", pl_id),
                "Description": f"Order: {' -> '.join(pl_data.get('music_order', []))}",
            })

        # Music Items
        for music_code, music_data in st.session_state.get("music_labels", {}).items():
            codebook_data.append({
                "Category": "Music",
                "Code": music_code,
                "Label": music_data.get("label", music_code),
                "Description": music_data.get("description", ""),
            })

        # Device Settings
        device_settings = st.session_state.get("default_device_settings", {})
        if device_settings:
            codebook_data.append({
                "Category": "Device",
                "Code": "recording_app",
                "Label": "Recording App",
                "Description": device_settings.get("recording_app", "HRV Logger"),
            })
            codebook_data.append({
                "Category": "Device",
                "Code": "device",
                "Label": "HR Sensor",
                "Description": device_settings.get("device", "Polar H10"),
            })
            codebook_data.append({
                "Category": "Device",
                "Code": "sampling_rate",
                "Label": "Sampling Rate",
                "Description": f"{device_settings.get('sampling_rate', 1000)} Hz",
            })

        return pd.DataFrame(codebook_data)

    if st.button("Generate Codebook", key="generate_codebook_btn"):
        df_codebook = generate_codebook()
        st.dataframe(df_codebook, width='stretch', hide_index=True)

        csv_codebook = df_codebook.to_csv(index=False)
        st.download_button(
            label="Download Codebook CSV",
            data=csv_codebook,
            file_name="codebook.csv",
            mime="text/csv",
            key="download_codebook"
        )
