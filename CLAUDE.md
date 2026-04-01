# CLAUDE.md

Quick reference for Claude Code. **Detailed history: MEMORY.md**

## Rules
- **ALWAYS TEST**: `uv run pytest` before delivering!
- **Check docs first** before implementing - solutions may already exist!

### File Maintenance Rules
| File | What to write | What NOT to write |
|------|---------------|-------------------|
| **CLAUDE.md** | Current version, TODOs, quick reference | Session notes, version history, detailed explanations |
| **MEMORY.md** | Session notes, version history, style guides | Old sessions (move to archive when >v0.7.x) |
| **MEMORY_ARCHIVE.md** | Archived sessions (v0.6.x and older) | Current work |

**After each session**: Add notes to MEMORY.md, update version in CLAUDE.md if changed. Keep CLAUDE.md <90 lines!

## Quick Commands
```bash
uv run streamlit run src/rrational/gui/app.py  # Launch GUI
uv run pytest                                   # Run tests
uv run ruff check src/ tests/ --fix            # Lint
```

## Current Status

**Version**: `v0.8.1` | **Tests**: 71/71 passing

**GUI**: 5-tab Streamlit app (Data, Participants, Setup, Sections, Analysis)
**Segmentation**: Unified time-based (artifact detection + analysis use same segments)

**Storage**: Project-based (`MyProject/config/*.yml`) or global fallback (`~/.rrational/`)

**Data Sources**: [HRV Logger](https://www.hrv.tools/hrv-logger-faq.html) (CSV) and [VNS Analyse](https://apps.apple.com/de/app/vns-analyse/id990667927) (TXT)

## Scientific Best Practices (CRITICAL)

This is a **scientific research tool**. Follow HRV guidelines:
1. **Artifact handling**: 2024 Quigley guidelines - artifact rates dictate valid metrics
2. **Data requirements**: Min 100 beats (time), 300 beats (frequency)
3. **Correction**: NeuroKit2 Kubios algorithm (2-10% artifacts)
4. **Exclusion**: Exclude segments with >10% artifacts

## Performance Rules
1. **Lazy imports**: Use `get_neurokit()`, `get_matplotlib()`
2. **Downsample plots**: 5000 points max
3. **Cache data**: `@st.cache_data` - cache raw data, not objects
4. **NEVER use Plotly JSON serialization** - extremely slow

## Key Files
- `app.py` - Main app + Participants tab + artifact detection
- `tabs/` - data.py, setup.py, analysis.py
- `gui/segmentation.py` - Unified time-based segments (artifact + analysis)
- `gui/theme.py` - CSS/HTML/JS theming (extracted from app.py)
- `gui/plots/` - analysis_plots.py, group_plots.py (extracted from analysis.py)
- `gui/shared.py` - GUI utilities, caching
- `analysis/repeating_sections.py` - Repeating section extraction (formerly music_sections)
- `analysis/hrv_metrics.py` - Metric catalogs, presets, windowing
- `analysis/hrv_compute.py` - HRV calculation, result transforms
- `cleaning/quality.py` - Quality detection, artifact fixpeaks, gap detection
- `segments/section_validation.py` - Event/section validation dataclasses
- `prep/participant_table.py` - Participant table building
- `persistence.py` - YAML storage
- `project.py` - ProjectManager

## TODOs

**High Priority:**
- [ ] Event sequence group comparison
- [x] Setup section rework (#17) - Playlists → Event Sequences
- [ ] R-R power spectrum plot
- [x] Batch processing / groupwise analysis (v0.7.9)
- [x] Unified time-based segmentation (v0.8.1)
- [x] Project restructuring (v0.8.1)
- [ ] Report generation (PDF/HTML)

**Low Priority:**
- [ ] Standalone app (PyInstaller/Nuitka)
- [ ] Detrending (#15)
- [ ] Better colouring options (#25)
- [ ] Support for more apps (#26)
- [ ] Loading animation (#13)

**Known limitations:**
- Plot zoom doesn't auto-load detail (use resolution slider)
- Arrow key panning works but with server roundtrip (#16)
- Tab switching briefly shows old tab content (Streamlit limitation, #14)

## Documentation Resources

**Use these resources when needed - don't reinvent the wheel!**

| Resource | Purpose |
|----------|---------|
| **MEMORY.md** | Recent session notes (v0.7.x), version summary table, style guides |
| **MEMORY_ARCHIVE.md** | Older session notes (v0.6.x and earlier), architecture patterns |
| **QUICKSTART.md** | User guide for the app |
| `docs/HRV_project_spec.md` | Full project specification |
| `docs/hrv_scientific.md` | Scientific HRV guidelines and references |
| `docs/hrv_processing_pipeline.md` | Data processing pipeline details |
| `docs/CONTRIBUTING.md` | Contribution guidelines |
| `docs/ISSUE_HANDLING.md` | GitHub issue handling procedures |
| `docs/manual_HRV_logger.md` | HRV Logger app documentation |

**When to use:** Bug fix → MEMORY.md | Architecture → MEMORY_ARCHIVE.md | Science → docs/hrv_scientific.md
