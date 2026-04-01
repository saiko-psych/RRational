# Changelog

All notable changes to RRational are documented here.

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
