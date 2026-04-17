# Changelog

All notable changes to RRational are documented here.

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
