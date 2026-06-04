# Changelog

All notable changes to RRational are documented here.

## [Unreleased] — feature/pyqt-inspector branch

### Added — PyQt Inspector (Phases 1–20)

Standalone desktop counterpart to the Streamlit app. Mirrors MNE-LAB architecture (multi-tab QMainWindow, dockable panels, native menus, recent-files, project structure). Shares persistence formats with Streamlit so the same project folder works in both UIs.

**Inspector architecture**
- 5-tab shell: Browse · Setup · Participants · Analysis · Results
- Multi-dataset workspace with sidebar tree + overview bar + scrollable timeline
- QSettings-backed persistence (window geometry, recents, view toggles)
- Project Management à la MNE-LAB (Phase 7): `project.rrational` manifest + `data/raw/` + `data/processed/` + `config/`; New / Open / Open recent / Close project menu actions; auto-load existing `.rrational` files on project open

**Streamlit-shared persistence** (all reuse `gui.persistence` directly)
- Phase 8 — Groups editor with members + persistence
- Phase 10 — Events (with regex synonyms) + Sections editors
- Phase 11 — Participants tab + Protocol sub-pane
- Phase 12 — Artifact corrections autosave + restore
- Phase 13 — Results cache (autosave + autoload, `inspector_results.yml`)

**Analysis** (all four Streamlit modes)
- Single Participant · Repeating Section · Group Comparison · Sequence Comparison
- Sequence stats with Friedman + RM-ANOVA (Mauchly + Greenhouse-Geisser sphericity correction) + Holm-corrected post-hoc + Kendall's W / partial η²
- Phase 14 — Manual artifact marking via click-to-mark (with Ctrl+Z/Ctrl+Y undo/redo)
- Phase 15 — Exclusion zones via drag-select (filters beats out of downstream HRV compute)
- Phase 16 — Section boundary editing via draggable LinearRegionItem handles + rename/delete/split context menu

**Visualizations** (Phase 17, native pyqtgraph — no Plotly)
- Tachogram with mean ± SD bands + artifact markers
- Poincaré plot with SD1/SD2 ellipse
- PSD (Welch) with VLF/LF/HF band shading
- HR distribution histogram + KDE
- Group bar chart with error bars (SEM/SD/CI95/None) + individual-points overlay + auto log-y for log-normal metrics
- Group box / violin / SD1-SD2 scatter

**MNE-LAB extras** (Phase 20)
- Free-text annotations on the plot timeline
- QDockWidget layout for Browse tab (tear-off panels, saveState/restoreState)
- BIDS-style folder detection (`participants.tsv` + `sub-*/` subdirs auto-load)

**Reports** (Phase 18)
- HTML and Markdown report generation from accumulated `ResultsStore`
- Inline base64-PNG plot embedding · TOC + anchor links · color-coded p-values · print-friendly CSS · DOI-linked references

**Color schemes** (Phase 19)
- ColorScheme reuse from Streamlit (5 preset themes + custom)
- Preferences dialog with per-element QColorDialog swatches
- Persisted in `~/.rrational/inspector/color_scheme.yml`

**Standalone build** (Phase 9)
- PyInstaller spec for Windows / macOS Intel / macOS Apple Silicon / Linux
- Extended `.github/workflows/build-release.yml` with Inspector-Windows / -macOS-Intel / -macOS-AppleSilicon / -Linux artifacts

### Fixed — HRV methodology cleanup
- Sequence post-hoc now log-transforms LF/HF/VLF/TP/LF_HF for parametric paths (Task Force 1996)
- Artifact indices sourced from NeuroKit2's `info` output instead of float-diff recovery (Lipponen & Tarvainen 2019)
- RM-ANOVA gains Mauchly sphericity check + Greenhouse-Geisser ε correction
- Group test note correctly distinguishes "n<3 silent fallback" from "non-normal"
- `adjust_pvalues` preserves raw p-value (`p_value_raw` field) and is idempotent via `is_corrected` flag
- Kubios VLF band lower bound corrected from 0 Hz to 0.0033 Hz (Task Force 1996)

### Tests
~241 new inspector tests + 121 analysis tests + adjacent regression suites — all green at the merge tip.

## [0.9.3] - 2026-06-01

### Added
- **Kubios-compatible frequency-domain mode** (`freq_method="kubios"`): Cubic Spline interpolation @ 4 Hz, Smoothness Priors detrending (Tarvainen et al. 2002, λ=500), Welch 180 s / 50% overlap, absolute ms² output. Matches Kubios HRV Scientific within <10% on frequency-domain metrics (RMSSD/HF within ±5%, LF within ±9%) on cross-validated data
- GUI **"Frequency-domain pipeline"** selector in Group Analysis and Sequence Comparison tabs, with inline help expander
- `docs/science/validation.md` — full validation report against Kubios (5 participants), including the cross-validation methodology and DOI-linked NeuroKit2 / Task Force 1996 / Quigley 2024 / Lipponen 2019 / Tarvainen 2002 / Berntson 1997 references
- `docs/user-guide/kubios-compatibility.md` — step-by-step guide for reproducing Kubios output
- 6 new tests in `TestFrequencyMethod` covering the Kubios pipeline (140 tests pass)

### Changed
- All 9 direct `nk.hrv_frequency()` call sites in the Analysis tab now respect the `freq_method` setting via the `_hrv_freq()` helper
- FAQ extended with three Kubios-related entries

### Documentation
- Processing-Pipeline doc explains both `neurokit` and `kubios` modes side-by-side

## [0.9.2] - 2026-04-17

### Fixed
- **macOS Intel builds**: Separate Intel (x86_64) and Apple Silicon (arm64) binaries in GitHub Actions. Previous releases silently shipped arm64-only when `macos-latest` migrated to Apple Silicon runners, causing `Bad CPU type in executable` on Intel Macs.
- Group Analysis failed loading `.rrational` files; now searches `project/data/processed/`
- Group bar chart x-axis rendering when mixing categorical bars with jittered individual points
- Color picker labels truncated in sidebar
- Documentation citation errors; all scientific references now include DOI links

### Added
- Hypothesis testing UI in Group Analysis Statistics tab
- `group_statistics` module for between-group comparisons
- Save/load Group Analysis results in project cache
- Configurable error bar type (SD / SEM / CI95 / None) in group bar chart
- Individual points overlay + log y-axis toggle in group bar chart
- HRV-specific Claude Code automations (hooks, slash commands)
- CI sanity-check: verifies built binary architecture matches runner, fails on mismatch
- README: clickable DOI links for Quigley 2024 and Lipponen & Tarvainen 2019
- README: explicit software + methodology citation block with version

### Changed
- **CI hardening**: Runners pinned (`windows-2022`, `macos-13`, `macos-14`, `ubuntu-24.04`) to prevent silent host-environment drift
- **CI hardening**: `pyinstaller` and `streamlit-desktop-app` version-ranged in build step
- 14x faster Group Analysis by loading `.rrational` files once (not per-metric)
- Default raw fallback set to OFF in Group and Sequence analysis
- Deduplicated code from review findings; removed remaining hardcoded colors

## [0.9.1] - 2026-04-10

### Added
- Color theming system with 5 preset themes: Scientific, Colorful, High Contrast, Monochrome, Pastel (#25)
- Per-element color pickers for RR line, NN line, artifacts, exclusions, events, sections
- Dark mode auto-adjusts all plot colors for visibility
- Ruff auto-lint PostToolUse hook for consistent code formatting
- Comprehensive data format documentation for all 8 supported sources

### Changed
- All analysis plots use configurable colors instead of hardcoded values
- Group plots use configurable palette from settings
- Permissions consolidated (110+ entries to 54 wildcard patterns)
- 101 tests (10 new for ColorScheme)

## [0.9.0] - 2026-04-08

### Added
- Support for 5 new data formats: Polar Sensor Logger, Polar Flow, Empatica E4, Elite HRV/plain text, Kubios HRV (#26)
- Auto-format detection from file content
- Power Spectrum (PSD) expander in Participants tab
- Sequence Comparison analysis mode with group filter
- HTML and Markdown report generation
- Standalone desktop app for Windows, macOS, Linux (PyInstaller + pywebview)
- GitHub Actions CI/CD for automated builds on tag push
- MkDocs Material theme with custom branding, Mermaid diagrams, grid cards

### Changed
- Removed ~2000 lines of duplicated code (7 plot functions, cached functions, shared utilities)
- Science section rewritten as practical Methodology reference
- README redesigned with badges, feature table, quick start

### Fixed
- Security: subprocess injection in welcome.py (sys.argv instead of f-string)
- Generic RR format loading in Participants tab
- Kubios parser: relaxed section header matching
- Comment-line detection in format auto-detection

## [0.8.1] - 2026-04

### Added
- Universal event sequences system (replaces music-specific playlists) (#17)
- Per-segment quality assessment with include/exclude controls
- Arrow key panning in Signal Inspection mode (#16)

### Changed
- Unified time-based segmentation for artifact detection and analysis
- Project restructured into clean modules (~3000 lines extracted from monoliths)
- "Playlists" renamed to "Event Sequences" throughout

### Fixed
- NaN handling in section data editor (#22)
- Exclusion zones update immediately after marking (#27)
- Enter key no longer auto-creates sections (#19)

## [0.8.0] - 2026-03

### Added
- Unified time-based segmentation (same segments for artifact detection and analysis)
- Batch processing and groupwise HRV analysis
- Per-segment artifact assessment with Quigley 2024 quality grades

## [0.7.2] - 2026-01

### Added
- Project management system (welcome screen, project folders, auto-load)
- Ready for Analysis export (.rrational files with audit trail)

### Changed
- Renamed project from music_hrv to RRational

## [0.7.0] - 2026-01

### Added
- Smart power formatting for frequency domain metrics
- Professional analysis plots with reference values

## [0.6.8] - 2026-01

### Added
- Data quality warnings in analysis output
- Professional analysis plots with reference bands

## [0.6.7] - 2025-12

### Added
- Processed folder for participant events
- `--test-mode` flag for demo data
- Analysis tab improvements

## [0.6.5] - 2025-12

### Added
- Demo data generation
- VNS event alignment fix
- Settings panel with plot resolution slider
