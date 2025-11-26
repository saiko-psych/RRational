# Session Notes - Interactive Plotly Visualization

**Date**: 2025-11-26
**Tag**: `v0.2.0-plotly-viz`
**Commit**: `eb5688a`

## Session Summary

This session focused on implementing an interactive Plotly-based visualization for RR intervals with click-to-add event functionality, replacing the previous matplotlib static plots.

## Key Achievements

### 1. Interactive Plotly Plot ✅
- Replaced matplotlib with Plotly for RR interval visualization
- Real datetime timestamps on x-axis (shows actual measurement times)
- Automatic gap detection - scatter plot shows where measurements are missing
- Interactive zoom/pan capabilities
- Time display in HH:MM:SS format

### 2. Click-to-Add Events ✅
- Click anywhere on the plot to add a new event at that timestamp
- Form appears with the clicked timestamp
- Events integrate with existing event management system
- New events appear in the events table below

### 3. Event Visualization ✅
- Vertical dashed lines mark event positions
- Color-coded by canonical event type
- Rotated text labels at the top of each line
- Legend positioned on the right side

### 4. Duplicate Detection ✅
- Enhanced `load_rr_intervals()` to detect duplicate timestamps
- Returns count and detailed list of duplicates
- Duplicates displayed in GUI with timestamps
- Integrated into summary statistics

## Technical Challenges Solved

### Problem 1: Plotly `add_vline()` with Datetime
**Error**: `TypeError: unsupported operand type(s) for +: 'int' and 'datetime.datetime'`

**Root Cause**: Plotly's `add_vline()` internally tries to calculate mean of x-axis values, which fails with datetime objects.

**Solution**: Used `add_shape()` and `add_annotation()` instead:
```python
# Draw vertical line
fig.add_shape(
    type="line",
    x0=event_time, x1=event_time,
    y0=y_min - 0.05 * y_range, y1=y_max + 0.05 * y_range,
    line=dict(color=color, width=2, dash='dash'),
    opacity=0.7
)
# Add label
fig.add_annotation(
    x=event_time,
    y=y_max + 0.08 * y_range,
    text=event_name,
    showarrow=False,
    textangle=-90,
    font=dict(color=color, size=10)
)
```

### Problem 2: Session State Initialization Order
**Error**: `st.session_state has no attribute 'participant_events'`

**Root Cause**: Plot code was trying to access `participant_events` before it was initialized.

**Solution**: Moved initialization code to run before the plot is generated (lines 704-713 in app.py).

### Problem 3: List Concatenation Type Safety
**Error**: Unexpected types in `events_list + manual_list`

**Solution**: Added type checking before concatenation:
```python
events_list = stored_data.get('events', [])
manual_list = stored_data.get('manual', [])
if not isinstance(events_list, list):
    events_list = []
if not isinstance(manual_list, list):
    manual_list = []
current_events = events_list + manual_list
```

## Files Modified

### Core Changes
- `src/music_hrv/gui/app.py` (lines 704-851): Plotly plot implementation
- `src/music_hrv/gui/persistence.py`: New file for YAML-based persistence
- `src/music_hrv/io/hrv_logger.py`: Added duplicate detection
- `src/music_hrv/prep/summaries.py`: Enhanced with duplicate tracking
- `pyproject.toml`: Added plotly and streamlit-plotly-events dependencies

### New Dependencies
```toml
plotly = "^6.5.0"
streamlit-plotly-events = "^0.0.6"
```

## Rollback Instructions

If you need to revert to the previous version:

```bash
# Option 1: Revert to the commit before this session
git checkout d1f14f8

# Option 2: Restore from backup
cp src/music_hrv/gui/app.py.backup src/music_hrv/gui/app.py

# Option 3: Use the tag
git checkout v0.2.0-plotly-viz^1  # One commit before the tag
```

## Next Steps (Future Sessions)

### Immediate Improvements
1. **Add event deletion** - Click on event marker to delete
2. **Event drag-and-drop** - Move events to different timestamps
3. **Export functionality** - Save modified events to file
4. **Undo/redo** - Track event modifications

### UI Enhancements
1. **Event type selector** - Dropdown for common event types when clicking
2. **Event color picker** - Let users customize event colors
3. **Plot themes** - Light/dark mode toggle
4. **Multiple plots** - Compare multiple participants side-by-side

### Data Quality
1. **Artifact highlighting** - Show cleaned vs. removed intervals
2. **Statistics overlay** - Display HRV metrics on the plot
3. **Event validation** - Warn about missing or duplicate events
4. **Time synchronization** - Align events across participants

## Testing Performed

- ✅ Plot renders correctly with real timestamps
- ✅ Event markers display at correct positions
- ✅ Click functionality works
- ✅ Events integrate with session state
- ✅ Zoom/pan works correctly
- ✅ Time format displays as HH:MM:SS
- ✅ Gaps visible in measurement data
- ✅ Legend positioned correctly

## Known Issues

None at this time. The implementation is stable and tested.

## Performance Notes

- Plotly handles 1000+ data points smoothly
- Plot renders in < 1 second for typical datasets
- Interactive features (zoom/pan) are responsive
- Click detection is accurate

## Documentation Updates Needed

1. Update README with Plotly dependencies
2. Add screenshots of the new interactive plot
3. Document click-to-add events feature
4. Update installation instructions

---

**Session End**: Ready for next session!
**Status**: ✅ All features working, tested, and committed
