# CLAUDE.md

Quick reference for Claude Code. **Detailed history: MEMORY.md**

## Rules
- **ALWAYS TEST**: `uv run pytest` before delivering!
- **Check docs first** before implementing - solutions may already exist!
- **Do NOT close GitHub issues** without manual verification by the user!

### File Maintenance Rules
| File | What to write | What NOT to write |
|------|---------------|-------------------|
| **CLAUDE.md** | Current version, TODOs, quick reference | Session notes, version history |
| **MEMORY.md** | Session notes, version history, style guides | Old sessions (archive when stale) |

**After each session**: Add notes to MEMORY.md, update version in CLAUDE.md if changed. Keep CLAUDE.md <90 lines!

## Quick Commands
```bash
uv run streamlit run src/rrational/gui/app.py  # Launch GUI
uv run streamlit run src/rrational/gui/app.py -- --test-mode  # Demo data
uv run pytest                                   # Run tests
uv run ruff check src/ tests/ --fix            # Lint
```

## Current Status

**Version**: `v0.9.0` | **Tests**: 101/101 passing

**GUI**: 4-tab Streamlit app (Data, Participants, Setup, Analysis)
**Analysis modes**: Single Participant, Repeating Section, Group, Sequence Comparison
**Setup sub-tabs**: Events, Groups, Sequences, Sections
**Segmentation**: Unified time-based (artifact detection + analysis use same segments)
**Storage**: Project-based (`MyProject/config/*.yml`) or global fallback (`~/.rrational/`)
**Docs**: https://rrational.readthedocs.io (MkDocs Material, auto-builds on push)
**Hooks**: PostToolUse ruff auto-lint on .py files (`.claude/settings.json`)

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

## Environment Notes
- Windows: `taskkill //F //IM streamlit.exe` to kill running instances
- Streamlit `@st.fragment`: content only in DOM after parent checkbox/interaction
- Plotly WebGL headless: needs `--use-gl=swiftshader` flag for Playwright
- `uv.lock` changes block `git pull` — users need `git checkout uv.lock` first
- Playwright MCP plugin: use for doc screenshots (saves to disk, unlike Chrome Extension)
- ReadTheDocs: `requirements-docs.txt` uses pip (RTD build server), project uses uv

## Key Files
- `app.py` - Main app + Participants tab + artifact detection
- `tabs/` - data.py, setup.py, analysis.py
- `gui/segmentation.py` - Unified time-based segments
- `gui/persistence.py` - YAML storage (event_sequences.yml, condition_labels.yml)
- `analysis/repeating_sections.py` - Repeating section extraction (formerly music_sections)
- `analysis/hrv_metrics.py` - Metric catalogs, presets, windowing
- `analysis/hrv_compute.py` - HRV calculation, result transforms
- `cleaning/quality.py` - Quality detection, artifact fixpeaks, gap detection
- `gui/color_scheme.py` - ColorScheme dataclass, 5 preset themes, dark mode variant
- `io/generic_rr.py` - Parsers for Polar, Empatica, Elite HRV, Kubios, plain text

## TODOs

**High Priority:**
- [x] Event sequence group comparison (Sequence Comparison mode + group filter)
- [x] R-R power spectrum plot (PSD expander in Participants tab)
- [x] Report generation (HTML + Markdown export)

**Low Priority:**
- [x] Standalone app (PyInstaller + pywebview, GitHub Actions CI/CD)
- [x] Support for more apps (#26) — Polar, Empatica, Elite HRV, Kubios, plain text
- [ ] Detrending (#15)
- [x] Better colouring options (#25) — ColorScheme presets + per-element color pickers

## Documentation Structure

```
README.md              → Landing page (links to RTD)
CHANGELOG.md           → Version history
QUICKSTART.md          → Redirect to RTD
mkdocs.yml             → RTD config
docs/
├── index.md           → RTD home page
├── getting-started/   → installation, quickstart, use-cases, FAQ
├── user-guide/        → workflow (with screenshots), data-formats, configuration
├── science/           → methodology: guidelines, processing-pipeline
├── development/       → architecture, contributing, issue-handling
├── reference/         → glossary, HRV_project_spec, PLAN_rrational_v2
└── assets/screenshots/→ 38 Playwright-captured GUI screenshots
```
