# Music HRV Toolkit - Quick Start Guide

## Current Version: v0.2.0-plotly-viz

### Running the GUI

```bash
cd "C:\Users\David\Nextcloud2\Documents\python\music_hrv"
uv run streamlit run src/music_hrv/gui/app.py
```

The app will open at http://localhost:8501

### Key Features

#### 1. Interactive RR Interval Plot
- **Zoom**: Scroll or use plot controls
- **Pan**: Click and drag
- **Add Event**: Click anywhere on the plot
- **View Time**: Hover over data points

#### 2. Event Management
- **Edit Label**: Click in the "Raw Label" column
- **Change Mapping**: Click in the "Canonical" column
- **Add Synonym**: Use the synonym form
- **Reorder**: Use drag-and-drop (if enabled)

#### 3. Data Persistence
Events are automatically saved to: `~/.music_hrv/events.yml`

### Data Location

Test fixtures: `tests/fixtures/hrv_logger/`

Your data should be in the format:
- `*_RR_*.csv` - RR interval data
- `*_Events_*.csv` - Event markers

### Common Tasks

#### Load Data
1. Select data directory in sidebar
2. Choose participant ID pattern
3. Click "Load Preview"

#### Add Custom Event
1. Click on RR plot at desired time
2. Enter event label
3. Click "Add Event"

#### Export Results
(Coming soon in future updates)

### Troubleshooting

**Plot not showing?**
- Check that plotly is installed: `uv pip list | grep plotly`
- Refresh the browser page
- Clear Streamlit cache: Press 'C' in the app

**Events not persisting?**
- Check `~/.music_hrv/events.yml` exists and is writable
- Events are saved automatically when you add synonyms

**Duplicate detection not working?**
- Ensure your RR files have timestamp columns
- Check that timestamps are in ISO format

### Keyboard Shortcuts

- **R**: Rerun the app
- **C**: Clear cache
- **Ctrl+S**: (In forms) Submit

### File Locations

- **GUI Code**: `src/music_hrv/gui/app.py`
- **Persistence**: `src/music_hrv/gui/persistence.py`
- **I/O Logic**: `src/music_hrv/io/hrv_logger.py`
- **Summaries**: `src/music_hrv/prep/summaries.py`
- **Config**: `config/canonical_events.yaml`

### Version History

- **v0.2.0-plotly-viz** (2025-11-26): Interactive Plotly plots with click-to-add events
- **v0.1.x**: Previous matplotlib-based visualization

### Rollback

To revert to previous version:
```bash
git checkout v0.2.0-plotly-viz^1
```

To return to current version:
```bash
git checkout main
```

### Next Session Ideas

1. Add event deletion by clicking event markers
2. Implement drag-and-drop to move events
3. Add export functionality for modified events
4. Create comparison view for multiple participants
5. Add artifact highlighting in the plot

---

**Last Updated**: 2025-11-26
**Status**: Stable and tested ✅
