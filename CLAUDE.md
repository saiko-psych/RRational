# CLAUDE.md

Quick reference for Claude Code working in this repository. **For detailed session history, see MEMORY.md**.

## Working Style with David

1. **GUI-first development**: David works with the Streamlit GUI. Describe what changes in the interface, not code details.
2. **Minimal code exposure**: Only show code when necessary.
3. **Track progress**: Use TodoWrite tool actively.
4. **Be proactive**: Describe what user will see differently in GUI.
5. **Update MEMORY.md**: Add detailed notes to MEMORY.md, keep this file slim.
6. **ALWAYS TEST**: Run `uv run pytest` and test imports before delivering code changes!
7. **OPTIMIZE FOR SPEED**: Always consider performance. Profile before optimizing!

## Current Status (2025-11-28)

**Version**: `v0.3.1`

**GUI**: 5-tab Streamlit app with persistent storage
- Tab 1: Data & Groups (import, WebGL plot, quality detection, music events, batch processing)
- Tab 2: Event Mapping (define events, synonyms auto-lowercase, timing validation)
- Tab 3: Group Management (groups + playlist/randomization groups)
- Tab 4: Sections (define time ranges between events)
- Tab 5: Analysis (NeuroKit2 HRV analysis, plots, metrics)

**Key Features (v0.3.1)**:
- Performance optimized (downsampling, lazy loading, caching)
- Batch processing for all participants
- Help text in all tabs
- Smart status summary (only shows issues when they exist)
- WebGL-accelerated Plotly plots with 5000-point downsampling
- Auto-create gap/variability events
- Music section events (separate category, playlist groups R1-R6)

**Storage**: `~/.music_hrv/*.yml` (groups, events, sections, playlist_groups)

**Status**: All tests passing (13/13), no linting errors

## Quick Commands

```bash
# Launch GUI
uv run streamlit run src/music_hrv/gui/app.py

# Run tests (ALWAYS DO THIS BEFORE DELIVERING!)
uv run pytest

# Lint
uv run ruff check src/ tests/ --fix
```

## Performance Guidelines (IMPORTANT!)

**ALWAYS optimize for speed. Profile before making changes.**

### Caching Functions (in app.py)
- `cached_discover_recordings()` - Directory scanning
- `cached_load_recording()` - File loading per participant
- `cached_clean_rr_intervals()` - RR cleaning results
- `cached_quality_analysis()` - Changepoint detection (SLOW - 1.2s)
- `cached_get_plot_data()` - Downsampled plot data

### Performance Rules
1. **NEVER use Plotly JSON serialization** - It's extremely slow (1.5s for large figures)
2. **Downsample large datasets** - 5000 points max for plots
3. **Lazy load expensive operations** - Only compute when user requests
4. **Cache data, not objects** - Cache raw data, build objects on demand
5. **Profile with timer context managers** before optimizing

### Current Performance
- First participant load: ~500ms
- Toggling plot options: Near-instant
- Switching participants: ~200ms (cached)

## Architecture Essentials

**Data Flow**: CSVs → `discover_recordings()` → `RecordingBundle` → `load_recording()` → cache → plot

**Key Files**:
- `src/music_hrv/gui/app.py` - Main Streamlit app (~2500 lines)
- `src/music_hrv/gui/persistence.py` - YAML storage helpers
- `src/music_hrv/io/hrv_logger.py` - CSV loading, multi-file support

## Important Patterns

**Plotly Event Lines** (use `add_shape()` not `add_vline()` for datetime):
```python
fig.add_shape(type="line", x0=event_time, x1=event_time, ...)
```

**Timezone Handling**:
```python
if ts.tzinfo is None:
    ts = pd.Timestamp(ts).tz_localize('UTC')
```

## Version Tags

- `v0.3.1` - Performance optimization, batch processing, help text
- `v0.3.0` - Music events, quality detection, timing validation
- `v0.2.3-patterns` - Predefined ID patterns, multi-file detection fix
- `v0.2.2-multi-files` - Multiple files per participant
- `v0.2.1-sorting-fix` - Timezone handling and visible sorting
- `v0.2.0-plotly-viz` - Interactive Plotly visualization

## Next Session TODOs

### High Priority
- [x] ~~Better explanations/help text in GUI~~ (DONE v0.3.1)
- [x] ~~Performance optimization~~ (DONE v0.3.1)
- [x] ~~Batch processing~~ (DONE v0.3.1)
- [x] ~~Smart status summary~~ (DONE v0.3.1)

### Medium Priority
- [ ] Improve UI layout (spacing, element sizing, visual polish)
- [ ] Plot customization (RR line color, titles, etc.) - LOW PRIORITY

### Known Limitations
- [ ] Section-based HRV analysis (currently analyzes whole recording)
- [ ] VNS Analyse loader not implemented

## References

- **MEMORY.md** - Detailed session history, implementation notes
- **QUICKSTART.md** - User quick start guide
- `docs/HRV_project_spec.md` - Full specification

---

*Last updated: 2025-11-28 | Keep this file concise - add details to MEMORY.md*
