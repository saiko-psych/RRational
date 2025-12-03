"""Tab modules for the Music HRV GUI."""

from music_hrv.gui.tabs.data import render_data_tab
from music_hrv.gui.tabs.participant import render_participant_tab
from music_hrv.gui.tabs.setup import render_setup_tab
from music_hrv.gui.tabs.analysis import render_analysis_tab

__all__ = [
    "render_data_tab",
    "render_participant_tab",
    "render_setup_tab",
    "render_analysis_tab",
]
