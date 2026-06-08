# Changelog

All notable changes to RRational are documented here.

## [Unreleased] — main (post Phase 28 polish, Sprints 1-6)

### Fixed — Streamlit app
- Participant tab "Could not generate RR plot: name 'components' is not defined" — `_setup_inspection_shortcuts` now uses `st.components.v1.html(...)` instead of a missing local `components` alias. The whole RR-plot block (mode radio, resolution slider, fragment) was being swallowed by the surrounding `except` (commit ac1dea9).
- Single-Participant Analysis with v1.0 ready-file + overlapping-windows showed "Aggregated results from N valid windows" then nothing. `_render_single_participant_analysis` now calls `_display_single_participant_results` before its early `return` so metrics + plots render in the same script run as the click (commit 255a259).
- `st.toast(..., icon="info")` raised `StreamlitAPIException` on Streamlit 1.51 during legacy `~/.music_hrv` migration. Switched to `icon=":material/info:"` (commit df9080b).

### Added — Streamlit tests (the gap that let those bugs slip)
- New `tests/streamlit/test_app_smoke.py` — 11 AppTest-driven smoke tests (~60 s wall clock). Covers: imports + first render, welcome screen, no NameError / unresolved HTML tags in markdown, each of Data/Participants/Setup/Analysis renders, sidebar nav contract, Analyze HRV click renders results table + metrics (direct regression test for the display bug). Catches both classes of bug that previously only showed up via manual click-testing.

### Added — Inspector features (Sprints 1-6)
- Sprint 1 (bugs + small visuals): repeating analysis table respects `selected_metrics` (B1); `_ROLE_DATASET_IDX` dead re-export dropped (B2); layout-menu lambdas call `set_ui_layout` unconditionally so `act.trigger()` works in tests (B3); dock widths capped so the central plot keeps its space + snapshot harness uses a real `QEventLoop` to settle layout (B4); `{project}/config/X.yml` placeholders resolve to live paths via new `format_config_path()` helper (V2); status-bar tab hints reference the actual button labels in the UI (V5).
- Sprint 2 (features + UX): DataTab restructured as a 4-step workflow with stepper + state-aware primary action + humanized regex (V1); empty-state hints across AnalysisTab / ResultsTab tables (V3); MNE-LAB is now the default UI layout (V7); auto-load last project on startup (F10); "Try with sample data" button on the WelcomeWidget + matching File menu entry (F11); repetitive events generator on ParticipantTab (F1); four plot tabs (Tachogram / Poincaré / Frequency PSD / HR distribution) wired into the Single-Participant pane (F6); `generate_group_analysis_html()` + matching button on the Group Comparison pane (F8).
- Sprint 3 (code hygiene): dead `workflow_sidebar.py` (344 LOC) removed (C3); ~97 `# Phase N:` development-log comments + module-docstring changelogs stripped while preserving WHY context (C1); redundant `addStretch()` removed from preprocessing panel (C5).
- Sprint 4 (cosmetic): SetupTab sub-pane tables claim vertical space so "Export codebook" pins to the bottom (V8); collapsed "Metrics to compute" group shows the selected-metrics summary instead of an empty bordered box (V9); ParticipantsTab columns stretch evenly with the numeric "# manual events" column sizing to its content (V10); permanent "No project active" status-bar message dropped in favour of the inline `format_config_path` hints (V11); snapshot harness gained Welcome-state pass + explicit DataTab pass + compute-then-snap-plot-tabs pass (V12).
- Sprint 5 (frontend-design): new central `style/theme.py` module with `apply_app_theme(app, mode)`. Refined Laboratory aesthetic — graphite surface stack, warm amber primary accent, 4 px spacing rhythm, smart font fallback (IBM Plex Sans / Segoe UI Variable / SF Pro Text — no bundled fonts). Both dark and light palettes share the same selectors so runtime mode switching is a single `setStyleSheet` call. Nine primary-action buttons tagged via `setProperty("primary", True)` so they pick up the amber fill. Six `QLabel`s with embedded `<i>`/`<code>`/`<b>` now have `setTextFormat(RichText)` — the literal `</i>` leak in the preprocessing-panel summary is gone.
- Sprint 6 (post-review fixes): DataTab primary-action navigation used wrong attribute name (`_tabs` instead of `_tabs_widget`), crashed on `.count()` — fixed (C1). `generate_group_analysis_html` now `mkdir(parents=True, exist_ok=True)` on its output path (C3). ResultsTab `_MetricsPane` propagates the B1 fix — table columns and CSV export follow the union of metric keys across rows instead of hardcoded `_DEFAULT_METRICS` (I1). Surviving `# Phase-2 entry point` comment rephrased (I2).

### Verified — End-to-end workflow against Kubios HRV Premium 3.5.0
- The full pipeline (Format-Detect → Load → Range-Clean → NK2 Lipponen 2019 artifact detect → correct → HRV in either NK2-default or Kubios-compatible mode) runs cleanly on the demo HRV Logger data (8971 RR intervals, 2.13 % artifact rate). Companion `_Events.csv` files auto-load. Kubios-mode produces absolute ms² (LF/HF >> 1) while NK2-default yields normalised n.u. (<<1). Validation memo (`project_kubios_validation.md`): MeanNN ±0.35 %, RMSSD ±0.83 %, HF ±2.7 %, LF ±5.4 %, LF/HF ±5.8 %. SDNN diverges 30-60 % by design (Task Force 1996 raw NN vs. Kubios detrended signal). All 3 `test_kubios_*` tests in `tests/analysis/test_hrv_compute.py` pass.

## [Unreleased] — feature/pyqt-inspector branch (Phases 1-20 baseline, now merged to main)

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
