# Changelog

All notable changes to RRational are documented here.

## [Unreleased] — main (Rounds 11-15, MNE-deep-integration + Visual/Coverage P0)

Strukturierte Implementierung der MNE-Gap-Analyse-Roadmap (Cluster A-D)
aus der Recherche vom 10. Juni 2026. Etwa 12 Commits zwischen
`cbcca6a..4304af7` auf `main`. Fokus: jedes load-bearing MNE-Python-Idiom
spiegeln (Epochs, Reports, describe / to_data_frame, dock-heavy Layout,
strukturierte History) plus Streamlit-Lücken schließen.

### Added — Cluster A (UI quick-wins, Round 11)
- Workflow-Stepper-Polish + Cluster-A1 bis A8 in einem Sprint: Statusbar-
  context-Widget, Cursor-Readout (Zeit + RR), Grid-Toggle im View-Menu,
  colorblind-safe Okabe-Ito-Palette per Preferences, Plot-Hover-Pfad,
  Workflow-Stepper-Label-Wrapping (commit `a4c9328`).

### Added — Cluster B (MNE concepts, Round 12)
- `InspectorData.to_data_frame()` + `describe()` — pandas-Frame mit
  Sektion-Spalte und Per-Sektion-Summary-Tabelle, kompatibel mit
  `mne.io.Raw.to_data_frame()` (commits `16da83f`, `ff1101f`).
- Compare-Curves-Dialog (Mehrfach-Overlay auf einer Plot-Achse).
- Overview-Bar-Stripes per Sektion (Streifenmuster zur Sichtbarkeit
  zwischen abutting Sections).

### Added — Cluster C (Strukturelle Erweiterungen, Round 13)
- **C1 RREpochs** + **C2 MNE-Report-style HTML** (commit `ae6d805`) —
  Epochs-Datenstruktur über RR-Series plus ein HTML-Report im Stil von
  `mne.Report` mit reproduzierbarem Recipe-Block.
- **C3 ParticipantGrid** + **C4 EmptyStateWidget** (commit `16679a2`) —
  Karten-Grid für Multi-Probanden-Übersicht und gestrichelter
  Drop-Target für leere Workspaces.
- **C5 InfoDock** (commit `353a157`) — rechts angedockter Info-Panel
  mit Dateiname, Approx-Sampling-Frequenz (60000/mean_RR), Länge mm:ss,
  Window-/Exclusion-/Annotation-Counts und Pre-Processing-Chain aus
  dem HistoryRecorder.
- **C6 WorkspaceTreeWidget** (commit `8656f9b`) — Tree-Sidebar mit
  custom `_BadgeDelegate` für rounded Pill-Badges (`PROC`, `N-WIN`,
  `BAD-Q`, `KUBIOS`, `BIDS`), getintet aus `theme.palette_tokens()`.
- **C7 Report.save/load** + **C8 CachedBIDSPipeline** (commit `9c4ad79`)
  — `ReportBuilder.save(path)` / `Report.load(path)` als STUBS (h5py
  noch nicht in pyproject.toml) plus content-addressed BIDS-Cache mit
  stdlib `hashlib` + `json` (kein joblib).

### Added — Cluster D (Streamlit-Parität, Round 14)
- **D1 _SequencesPane VERIFIED** — bereits vollständig implementiert
  in `setup_tab.py` mit Add/Edit/Delete + Reordering.
- **D2 RepetitiveEventsDialog VERIFIED** — Button "Add repetitive
  sequence..." im PreprocessingPanel des ParticipantTab vorhanden.
- **D3 VNS use_corrected toggle** (commit `4304af7`) — `load_generic_rr`
  propagiert ein `use_corrected` Keyword durch `_parse_vns_analyse` zum
  Loader; Default auf `True` geflippt (wissenschaftliche Norm).

### Fixed — Round 15 (Visual + Coverage P0-Fixes)
- **Sprint 1 — Hardcoded white plot backgrounds entfernt** (commit
  `cf292d3`) — 8 Plot-Dateien (tachogram, poincare, psd, hr_distribution,
  participant_grid, drop_log, compare_curves, overview_bar) deferenzieren
  jetzt auf den globalen pyqtgraph-Theme statt einer fixen `#FFFFFF`
  Background; behebt unleserliche Plots im Dark-Mode.
- **Sprint 2 — WorkspaceTreeWidget in BrowseTab verdrahtet** (commit
  `b99a9a8`) — Cluster-C6-Sidebar mit Status-Badges (`PROC`, `N-WIN`,
  `BAD-Q`, `KUBIOS`, `BIDS`) ist jetzt im BrowseTab eingebunden, nicht
  mehr ein toter Widget-Konstruktor.
- **Sprint 3 — EmptyStateWidget theme-aware QSS + Drop-Target**
  (commit `68b9b32`) — Cluster-C4-Drop-Zone übernimmt
  `theme.palette_tokens()` für Border + Hintergrund + Hover; Drag-and-drop
  echter `.rrational`/CSV-Dateien wird in der leeren BrowseTab akzeptiert.
- **Sprint 4 — ParticipantGridWidget in ParticipantsTab verdrahtet**
  (commit `e64df16`) — Cluster-C3-Multi-Probanden-Grid (300 px hoch,
  4-spaltig) sitzt jetzt über der Editor-Tabelle und refresht auf jeder
  Workspace-Änderung; Cell-Click aktiviert das passende Dataset via
  `main_window.set_active_dataset`.
- **Sprint 5 — InfoDock minimum width + View menu HUD/Zen toggles**
  (commit `85a9002`) — InfoDock kollabierte beim Erststart auf einen
  1-px-Spalt, weil das Plot-Central-Widget den gesamten horizontalen
  Platz griff; `setMinimumWidth(280)` liefert eine brauchbare
  Initialgröße. Plus: `Show HUD readout` + `Zen mode` als
  View-Menu-Einträge (die H/Z-QShortcuts auf dem Plot bleiben aktiv).
- **Sprint 6 — Test-Coverage für palette + drop_log** (commit `04b2cf1`)
  — 13 neue Tests schließen die Tier-1-Lücke: Okabe-Ito 8-Farben-
  Invarianz + Cycling-Verhalten + Hex-Format; drop_log Pareto-Sortierung,
  Cumulative-Overlay, Reason-Labels, Min-Height-Skalierung.

### Fixed — Round 16 (Layout polish post visual inspection)
- **Sprint 1 — Welcome-State Dock-Visibility** (commit `b5a9afd`) —
  Preprocessing- und InfoDock werden im Welcome-State (kein Dataset
  geladen) ausgeblendet, damit der Landing-Screen nicht von
  disabled-Controls (Detect artifacts, Exclusion zones, Section
  editing) umrahmt wird. Neuer Helper
  `MainWindow._update_docks_for_welcome_state()` läuft nach
  `_notify_tabs_workspace_changed` und einmal am Ende von `__init__`,
  respektiert die persisted QSettings `show_*_dock` Präferenzen
  beim Restore.
- **Sprint 2 — ParticipantGrid n<4 Layout + Subject-Label** (commit
  `3c64d68`) — Fixe Cell-Größe 220x140 mit `setMaximumWidth`/
  `setMaximumHeight` zusätzlich zum min-only-Contract; trailing
  Placeholder-Labels konsumieren den Slack-Space sodass populated
  Cells link-pin statt full-width zu stretchen (vorher: n=1 als
  einzige flache Tachogram-Band über die ganze Widget-Breite).
  Subject-ID Badge promoted zu 12pt bold weiß auf translucent-dark
  Fill, lesbar auf beiden Theme-Modes. ParticipantsTab versteckt
  das gesamte Grid wenn n<=1 (kein Vergleichs-View bei einem
  Thumbnail).
- **Sprint 3 — Welcome Vertical Centering + Recent-Files Polish**
  (commit `5d3c0b9`) — Outer QVBoxLayout mit 1:1-Stretchern
  zentriert den Content-Block vertikal (vorher 1:2 hob ihn ins
  obere Drittel). "(no recent files)" -> "No recordings opened yet."
  in italic 11pt mit `hint`-QSS-Property für muted-secondary-Color.
- **Sprint 4 — Unified Tab-Counter Format** (commit `0340ce3`) —
  Vorher inkonsistent: `Browse (empty)`, `Setup (8 groups, 2 seqs)`,
  `Participants (44)`, `Analysis (1 loaded)`, `Results` (kein
  Counter). Jetzt einheitlich `(N)` wenn N>0, leer sonst, für alle
  Tabs (Setup summiert Groups+Sequences, Results summiert
  metric+group+sequence rows, Data summiert participants+datasets).
  ParticipantTab bleibt außerhalb dieses Vertrags (contextuelles
  Subject-Label).
- **Sprint 5 — ParticipantsTab Header + Toolbar** (commit `4193768`)
  — Header in zwei Zeilen aufgeteilt: bold "Participants" plus
  muted "Link each participant ID to a group and an event sequence";
  Config-Path verschoben in Hover-Tooltip auf dem Heading. Toolbar-
  Buttons (Add / Edit / Remove / Import) bekommen gemeinsame 110px
  min-width plus 8px Spacing, "Import from workspace" verkürzt zu
  "Import…" mit Volltext im Tooltip.
- **Sprint 6 — Snapshot Harness erweitert** (commit `717c162`) —
  Vier neue Passes: `info_dock_isolated.png` (Dock als Standalone-
  Widget), `compare_curves_dialog.png` (Multi-Curve-Overlay gegen
  2-Dataset-Workspace), `tab_04_ParticipantsTab_multi.png`
  (6 synthetische Datasets, 4x2 Grid-Layout-Verifikation),
  `light_00..05_*.png` (Light-Mode-Re-Snap der vier wichtigsten
  Tabs). Harness emittiert jetzt 30 PNGs (vorher 22).

### Infrastructure
- CI hardening: preflight job + pre-push hook + libEGL libs (commits
  `d4be003`, `926911c` aus dem Vorlauf).

## [Unreleased] — main (Rounds 7-10, MNE-inspired feature parity + BIDS/PRISM interop)

Continued from Sprint 6. Forty-five commits on `main` between `00e29b7..cbcca6a`. Theme: import MNE-Python's interaction patterns and persistence formats so the Inspector behaves like a familiar EEG-lab tool, plus first-class round-trip with BIDS-physio and PRISM Studio so RR datasets can move into multi-modal workflows without bespoke glue code.

### Changed — Round 7 (naming + workflow polish)
- User-facing "RRational Inspector" renamed to "RRational" across window titles, menus, dialogs, and report subjects — the Inspector is now the primary UI, not a subordinate tool. Tests updated accordingly (commit `95399f7`).
- Workflow stepper labels no longer ellipsise mid-step; column widths scale to the longest label so all four steps stay readable on narrow Layouts (commit `c802557`).

### Added — Round 8 (five MNE-inspired Inspector features)
- **Live regex validation in event-definition dialog** (commit `cfe6edd`) — synonyms field validates incrementally with red border + tooltip on `re.error`; the OK button disables on malformed input. Mirrors MNE-Python's `mne.event.find_events` regex semantics so the same patterns work cross-tool.
- **Batch preprocessing + quality triage dashboard** (commit `a73a3f6`) — multi-select datasets in the workspace tree, run cleaning + artifact correction across all of them, then review a quality-triage dialog (signal length, artifact %, gap count, recommended action) before committing. Pattern from MNE-LAB's batch-processing dock.
- **Cross-recording annotation table + CSV import/export** (commit `626a7fe`) — `AnnotationTableDialog` lists every annotation across the workspace with file column, timestamp, text, duration. CSV round-trip handles `end_s` field with negative-duration clamping. Drop-in replacement for MNE's `Annotations.to_dataframe()`.
- **MNE-style plot shortcuts + drag-annotation** (commit `faa6179`) — `R` reset view, `1/2/3` jump to 60s/600s/full, `A` toggle annotation mode, `E` toggle exclusion mode. Left-drag in annotation mode creates a range annotation; sub-0.5s drags fall through to the click-to-annotate path. Exclusion mode wins on dual-mode drags.
- **Reproducible recipe export — history subpackage** (commits `0df990c` + `d69beb6` + `93358f9`) — every recorded `Action` (frozen dataclass) emits real `to_python()` source via the actual inspector APIs (`load_exclusion_zones`/`save_exclusion_zones`, `load_annotations`/`save_annotations`). File menu entry "Export Recipe…" writes a runnable `.py` that re-applies the entire history to a fresh load of the same recording.

### Fixed — Round 8 polish
- Round-8 dialogs picked up visual cleanup pass: missing primary-action tagging on the AnnotationTableDialog OK button, inconsistent dialog padding, label/widget alignment (commit `e82d9f9`).
- Recipe-export test expectations updated post-rename (`source_app="RRational"` instead of `"RRational Inspector"`, commit `c398027`).

### Added — Round 9 (range annotations + BIDS/MNE round-trip)
- **Range annotations (MNE-style onset + duration)** (commit `f03fad2`) — `Annotation` dataclass extended with `duration: float = 0.0` and computed `t_end`, `is_range` properties. `Annotation.create_range(t_start, t_end, text)` classmethod. Drag-to-annotate now stores the full range instead of collapsing to the midpoint; the on-plot marker still pins at the onset. Legacy YAML files load with `duration=0.0` (backward compatible).
- **BIDS-prep metadata on `InspectorData`** (commit `1e54b7c`) — added `experimenter`, `description`, `device`, `line_freq` fields so BIDS export has the spec's RECOMMENDED keys available at export time.
- **BIDS-physio export** (commit `a42da2e`, issue #3) — `bids_export.py` writes `sub-<pid>[_ses-<ses>]_task-<task>_recording-cardiac_physio.tsv.gz` plus a JSON sidecar with all BIDS REQUIRED + RECOMMENDED fields. `SamplingFrequency = mean_beat_rate` per the spec's documented workaround for event-spaced cardiac data. Tools menu entry "Export to BIDS-physio…" with `test_mode` no-dialog path.
- **BIDS-physio import** (commit `a4ce230`, issue #4) — `generic_rr.py` `detect_format()` recognises filenames ending `_recording-cardiac_physio.tsv.gz` paired with a sidecar JSON. `_parse_bids_physio()` reads the gzipped TSV, honours the sidecar's `Columns` array, anchors absolute timestamps from `StartTime`. Round-trip preserves RR values to ±1 ms (round-to-nearest-ms semantics documented in tests).
- **Reproducible recipe embedded in HTML report** (commit `e25d952`, QW1) — Report's new "Reproducible recipe" section includes the recorder's full Python script with `tokenize`-based syntax highlighting (keywords coral, strings jade, comments slate, numbers amber). Report becomes a self-contained reproduction artifact.
- **Central `rrational._logging` module** (commit `8ff217f`, issue #5) — `logger = logging.getLogger("rrational")` with `NullHandler`, plus `set_log_level()`, `use_log_level()` context manager, and `@verbose` decorator. `_resolve_level()` accepts `str` / `int` / `bool` / `None` for MNE-compatibility (`verbose=True` → DEBUG, `False` → WARNING, etc.).

### Fixed — Round 10 (BIDS spec compliance + PRISM Studio interop)
- **BIDS-physio sidecar drops non-spec key** (commit `2706a1a`) — removed bespoke `RecordingType` field that isn't in BIDS v1.11.1; added spec-compliant `PhysioType: "generic"` and `cardiac.LongName: "RR interval"` so labels surface correctly in `mne-bids` / `fmriprep` BIDS-aware UIs. Three new tests verify the spec assertions.

### Added — Round 10 (PRISM Studio biometrics)
- **PRISM Studio biometrics export** (commit `6181206`) — `prism_export.py` writes `sub-<pid>[_ses-<ses>]_task-<task>_biometrics-hrv_biometrics.tsv` (one row per recording) plus a JSON sidecar with PRISM's Technical / Study / Metadata blocks. Twelve HRV summary metrics mapped from NK2 keys to PRISM column names (`MeanNN`→`mean_nn_ms`, `RMSSD`→`rmssd_ms`, etc.) with column metadata (LongName, Units, DataType). Tools menu entry "Export to PRISM biometrics…". Confirms RRational HRV outputs are first-class citizens of the PRISM multi-modal research framework without a "BIDS-with-PRISM-flag" anti-pattern — two distinct exporters, one per spec.

### Verified — Round 7-10 test coverage
- Full test suite: 215 tests, 1 documented skip (`test_app_renders_welcome_screen_without_project` — AppTest inherits user's `~/.rrational/settings.yml`, env-dependent). 
- New test files added: `tests/inspector/test_bids_export.py` (13 tests including 3 for Round-10 spec fixes), `test_bids_export_wiring.py` (4 tests), `test_bids_import.py` (9 tests), `test_prism_export.py` (14 tests), `test_prism_export_wiring.py` (5 tests), `test_plot_shortcuts.py` (10 tests), `test_annotation_table_dialog.py` (multiple suites), `test_batch_preprocess.py` (multiple suites), `test_quality_triage.py`, `test_save_recipe.py` (history + script emit), `test_history.py` (Action dataclasses + recorder), `tests/test_logging.py` (8 tests for `@verbose` + `use_log_level`).

### Documented — Round 10 audit
- `.claude/analysis/bids_cardiac_compat.md` (internal, gitignored) — research notes on BIDS Physiological Recordings v1.11.1 spec, PRISM Studio biometrics modality, and the event-spaced-data limitation (sampling-frequency=mean-beat-rate workaround). Confirms PRISM does not parse cardiac time-series; its biometrics modality is summary-metrics-only (one row per recording).

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
