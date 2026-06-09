# BIDS Cardiac Spec + PRISM Studio Compatibility Audit

**Subject:** Audit of RRational's BIDS-physio cardiac export (`src/rrational/inspector/bids_export.py`) against
(a) the official BIDS specification v1.11.x and (b) the MRI-Lab-Graz **PRISM Studio** framework.

**Date:** 2026-06-09
**Scope:** Recherche only. No code changes.

---

## TL;DR

1. **Our current BIDS-physio output is already spec-conformant.** All `REQUIRED` fields are present; the `cardiac`
   column block uses the correct shape; the TSV is correctly header-less and gzipped; the filename uses the right
   entity order (`sub`, `ses`, `task`, `recording-cardiac`, `_physio` suffix). The "spec violation" worth flagging
   is that we emit one **non-standard** key (`RecordingType`) — that field does not exist in BIDS.

2. **PRISM Studio does NOT consume BIDS `_physio.tsv.gz` cardiac files.** PRISM's "biometrics" modality is a
   different thing entirely (VO2max, plank, anthropometry — event-aggregated test results in a flat TSV with one
   row per metric). Standard BIDS physio is mentioned in passing as a file type that exists in PRISM datasets,
   but PRISM Studio's validator/converter does not parse or process the cardiac time-series; it would treat our
   `_physio.tsv.gz` + sidecar as a pass-through BIDS-core file. So "PRISM compat for cardiac" is effectively
   "stay BIDS-valid" — there is nothing PRISM-specific to add for RR-interval data today.

3. The **only realistic compatibility move** for PRISM is a parallel/optional export path that writes the data
   *as a PRISM `_biometrics` file* (HRV summary metrics — RMSSD, SDNN, mean HR, etc., one row per recording) with
   a PRISM-shaped `Technical` / `Study` / `Metadata` sidecar. That is a feature request, not a fix.

---

## Phase 1 — BIDS Spec for Cardiac (v1.11.1, current stable)

### Source

- BIDS Specification, "Physiological recordings" page:
  <https://bids-specification.readthedocs.io/en/stable/modality-specific-files/physiological-recordings.html>
- BIDS Common Principles (TSV / `.tsv.gz` rules):
  <https://bids-specification.readthedocs.io/en/stable/common-principles.html>
- Real-world example sidecar (BIDS-Examples `7t_trt/physio.json`):
  <https://raw.githubusercontent.com/bids-standard/bids-examples/master/7t_trt/physio.json>

### Filename grammar

```
sub-<sub>[_ses-<ses>]_task-<task>[_recording-<label>]_physio.tsv.gz
sub-<sub>[_ses-<ses>]_task-<task>[_recording-<label>]_physio.json
```

- `recording-<label>` is **optional in general** (only mandatory for eye-tracking) but **recommended values**
  in the spec text are `cardiac` and `respiratory`. We use `recording-cardiac` — correct.
- Different sampling frequencies or manufacturers MUST live in separate files with distinct `recording-` labels.

### Sidecar fields

| Field                  | Status          | Spec rule                                                             | RRational today                                                       |
|------------------------|-----------------|-----------------------------------------------------------------------|-----------------------------------------------------------------------|
| `SamplingFrequency`    | **REQUIRED**    | Number, in Hz                                                         | Present (`n_finite_beats / duration_s`, mean beat rate)               |
| `StartTime`            | **REQUIRED**    | Seconds relative to first neural-data sample (sub-second OK)          | Present (epoch seconds)                                               |
| `Columns`              | **REQUIRED**    | Array of strings; must match TSV columns                              | Present (`["cardiac"]`)                                               |
| `<column>` blocks      | OPTIONAL        | Object per column with `Description`, `Units`, `LongName`, ...        | Present (`cardiac` block with `Description` + `Units: "ms"`)          |
| `PhysioType`           | RECOMMENDED     | Default `"generic"`; allowed values `"generic"`, `"eyetrack"`         | **Not set** (defaults to `"generic"` — fine for cardiac)              |
| `DeviceSerialNumber`   | OPTIONAL        | String                                                                | Not set                                                               |
| `Manufacturer`         | OPTIONAL        | String                                                                | Conditional (from `data.device`)                                      |
| `ManufacturersModelName` | OPTIONAL      | String                                                                | Not set                                                               |
| `SoftwareVersions`     | OPTIONAL        | String                                                                | Not set                                                               |
| **`RecordingType`**    | **NOT IN SPEC** | -                                                                     | **Present (`"continuous"`)** — this is non-standard, see finding #1   |

### Other fields we emit (compat status)

| Field               | Source                                | Status                                                                              |
|---------------------|---------------------------------------|-------------------------------------------------------------------------------------|
| `Experimenter`      | `data.experimenter`                   | Not in physio sidecar spec, BUT it IS a documented BIDS top-level field for `_events.json` and tolerated by validators as "additional metadata". Low risk. |
| `TaskDescription`   | `data.description`                    | Officially defined for MR/EEG/MEG modality sidecars, NOT physio. Validators won't reject; PRISM won't see it. Low risk. |
| `PowerLineFrequency`| `data.line_freq`                      | Defined for EEG/MEG/iEEG sidecars, NOT physio. Same status as above.                |

The above three are "extra metadata" — BIDS explicitly allows arbitrary additional sidecar keys as long as
required keys are present. No spec violation.

### Column-block rules (spec — Common Principles, "Tabular files")

For each column entry the spec lists:

| Sub-field   | Status        |
|-------------|---------------|
| `LongName`  | OPTIONAL      |
| `Description` | RECOMMENDED |
| `Units`     | RECOMMENDED   |
| `Levels`    | OPTIONAL      |
| `TermURL`   | OPTIONAL      |
| `HED`       | OPTIONAL      |
| `Delimiter` | OPTIONAL      |

So `cardiac: {Description, Units: "ms"}` covers the only two **RECOMMENDED** fields. Adding `LongName` is
trivially nice-to-have.

### Special note on RR-intervals vs continuous ECG

The BIDS spec does **not** distinguish RR-interval (event-spaced) data from continuous-rate ECG. It has only
one model: TSV.GZ with a single `SamplingFrequency`. The community workaround we already use — `SamplingFrequency
= mean_beat_rate` — is the documented best practice. Some labs additionally include a `time` column to make
event-spaced timing explicit; this is allowed but optional.

### BIDS-Examples — cardiac in practice

The `7t_trt` dataset sidecar (root-level `physio.json`, inherited by all subjects) is literally:

```json
{"StartTime": 0, "SamplingFrequency": 100, "Columns": ["cardiac", "respiratory", "trigger", "oxygen saturation"]}
```

i.e. real-world cardiac sidecars are extremely minimal. No `Units`, no per-column descriptions, no
`PhysioType`. We are already richer than this. Other physio-containing example datasets: `ds210`, `synthetic`,
`eyetracking_fmri`, `emg_MultiBodyParts` (most are ECG-during-fMRI, not RR-interval).

### TSV format rules (Common Principles)

- "Compressed tabular files MUST NOT contain a header in the first row." We comply.
- "Compressed tabular files MUST have an associated JSON file that defines the columns" via `Columns`. We comply.
- Files MUST be gzip-compressed. We comply (`gzip.open(... "wt")`).

---

## Phase 2 — PRISM Studio (MRI-Lab-Graz)

### Sources

- Repo: <https://github.com/MRI-Lab-Graz/prism-studio>
- README: <https://raw.githubusercontent.com/MRI-Lab-Graz/prism-studio/main/README.md>
- SPECIFICATIONS.md: <https://raw.githubusercontent.com/MRI-Lab-Graz/prism-studio/main/docs/SPECIFICATIONS.md>
- Biometrics spec: <https://raw.githubusercontent.com/MRI-Lab-Graz/prism-studio/main/docs/specs/biometrics.md>
- (`prism-studio.readthedocs.io` redirects to ReadTheDocs but only the `main/docs/` markdown is authoritative.)

### What PRISM Studio is

> "PRISM Studio is the software implementation of the **PRISM (Psychological Research Information System Model)**
> framework for psychological experiment datasets. It is an **add-on to BIDS**, not a replacement."

Stack: Python 3.10+, Flask/JS web app + CLI (`prism-validator`, `prism_tools.py`). It validates BIDS datasets,
applies PRISM's own extension schemas (surveys, biometrics, environment, super-BIDS events), generates
derivatives via "recipes", and offers an export/scoring workflow. The lab uses it to manage *psychological*
study datasets — questionnaires, performance tests, etc. — anchored in an MRI workflow but not centered on
MR-image processing itself.

### What PRISM does with cardiac/physio data

**This is the critical finding.** PRISM's `docs/SPECIFICATIONS.md` lists the modality file-name examples:

```
survey TSV:      sub-001_ses-1_task-ads_beh.tsv
biometrics TSV:  sub-001_ses-1_biometrics-cmj_biometrics.tsv
physio EDF:      sub-001_ses-1_task-rest_physio.edf
```

So **`_physio` files are passed through as plain BIDS** — the PRISM extension does not add or require physio
sidecar fields. PRISM does not contain a cardiac/ECG/PPG/HRV parser; there is no `physio.py`, no
`cardiac` module, no `_physio.tsv.gz` reader in the source tree (confirmed via repo file search: 0 hits for
"cardiac" or "physio" outside of the SPECIFICATIONS.md mention above and the biometrics doc disambiguation).

### What PRISM's "biometrics" modality IS (and isn't)

The PRISM **biometrics** spec is **NOT a physio time-series format**. From `docs/specs/biometrics.md`:

> "The `biometrics` modality is a PRISM extension designed for physiological assessments that **do not fit
> into standard BIDS `beh` or `physio` categories**. Examples include VO2max tests, plank tests, balance
> assessments, or anthropometric measurements."

#### File-name pattern (NOT `_physio`):

```
sub-<label>[_ses-<label>]_task-<label>_biometrics.<extension>
```

Note: `_biometrics` suffix, `task-` entity (not `recording-`), and `.tsv` (un-gzipped) is typical. This is
completely separate from `_physio.tsv.gz`.

#### Sidecar structure (totally different shape):

```json
{
  "Technical": { "Type": "...", "FileFormat": "tsv", "Equipment": "...", ... },
  "Study":     { "BiometricName": "...", "OriginalName": "...", "Description": "...", ... },
  "Metadata":  { "SchemaVersion": "1.1.1", "CreationDate": "YYYY-MM-DD" },
  "<column_name>": { "Description": "...", "Units": "...", "DataType": "...", ... }
}
```

- `Technical.Type` must be one of: `Biometrics`, `PhysicalPerformance`, `Anthropometry`, `FitnessTest`.
- `Technical.SoftwarePlatform` examples explicitly include `"Kubios"` — interesting for us because RRational
  already has a Kubios-compat mode (cf. `project_kubios_validation.md` in MEMORY.md).
- A biometrics TSV is one row per metric (or one row per session with HRV summary metrics across columns) —
  not a time-series.

#### What this means

If we wanted to export to PRISM, we would write a SECOND file type next to (or instead of) our BIDS-physio
output: a `task-<task>_biometrics.tsv` of HRV summary metrics (e.g. mean HR, RMSSD, SDNN, pNN50, LF/HF, ...
one row, columns are the metrics) with a PRISM-shaped JSON sidecar. The raw RR series itself does not fit
PRISM's biometrics model.

### Compatibility verdict

| Question                                                                  | Answer |
|---------------------------------------------------------------------------|--------|
| Will our current BIDS-physio cardiac files be **read** by PRISM Studio?   | They will be **passed through as plain BIDS** during PRISM validation. PRISM will not extract HRV metrics from them — there is no physio parser. |
| Will PRISM **reject** them?                                               | No. PRISM extends BIDS; standard BIDS files are valid by definition. |
| Does PRISM **require** extra sidecar fields for cardiac?                  | No. There is no PRISM cardiac/physio schema. |
| Could a PRISM dataset *contain* our BIDS-physio files?                    | Yes, fully — they would just sit alongside PRISM survey/biometrics files. |

**Bottom line:** "PRISM compat" for raw RR-interval time-series collapses to "be BIDS-valid", which we already are.

---

## Phase 3 — Concrete Recommendations

### Priority table

| # | Priority | Change                                                                                                    | Rationale                                                                                                                                          | Effort |
|---|----------|-----------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|--------|
| 1 | **HIGH**     | **Drop `RecordingType: "continuous"`** from the sidecar.                                                  | Not a defined BIDS field. Strict validators (e.g. `bids-validator` v1.13+) ignore unknown keys with a warning, but it adds noise and our own docstring already acknowledges the event-spaced nature. | trivial |
| 2 | MED      | Add `"PhysioType": "generic"` (or omit; default is `generic`).                                            | RECOMMENDED in the spec. Explicit > implicit, especially as future versions may make this required for some downstream tools.                       | trivial |
| 3 | MED      | Add `"LongName": "RR interval"` to the `cardiac` column block; consider renaming the column itself to `cardiac` (we already use this — keep) and keep `Units: "ms"`. | OPTIONAL but improves machine-readability; many BIDS-aware tools surface `LongName` in plots/UIs.                                                  | trivial |
| 4 | LOW      | Consider adding a `time` column (event onsets in seconds, relative to `StartTime`) alongside `cardiac`.   | Makes the event-spaced nature explicit without breaking the constant-rate assumption. Helpful for downstream tools that expect either uniform sampling or explicit timestamps. Would change `Columns` to `["time", "cardiac"]`. **Breaking** for round-trip import unless gated behind a flag. | medium |
| 5 | LOW      | Move PRISM-style metadata (Experimenter, TaskDescription, Manufacturer, PowerLineFrequency) into a PRISM-namespaced block, OR drop fields that aren't BIDS-defined for the physio sidecar. | Cleaner separation. Today's stray top-level keys don't break validators but pollute the sidecar with non-spec fields. Alternative: keep as-is — explicitly allowed by "additional keys" rule. | small |
| 6 | OPTIONAL | **Future feature:** add a parallel `_biometrics.tsv` + PRISM sidecar exporter for HRV summary metrics (RMSSD, SDNN, mean HR, LF, HF, LF/HF, pNN50, ...) targeting `Technical.SoftwarePlatform = "RRational"` (or `"Kubios"` if using compat mode). | This is the *only* meaningful PRISM-native cardiac export PRISM can actually parse. Useful for MRI-Lab-Graz if/when they pull RRational outputs into their pipelines. Not a fix — a feature. | medium |

### BIDS-spec fields we do NOT have but probably should (priority order)

1. **`LongName`** under the `cardiac` column block — see #3 above.
2. **`PhysioType: "generic"`** — see #2.
3. **`DeviceSerialNumber`**, **`ManufacturersModelName`**, **`SoftwareVersions`** — all OPTIONAL hardware
   provenance fields. Worth populating when we know them (e.g. for Polar H10 / Movesense exports where the
   loader already has this info).

### PRISM-Studio-specific adjustments

**None required** for the BIDS-physio output. If we want to export to PRISM Studio natively, we need a new
exporter for the **biometrics** modality (summary metrics, not the raw RR series). See recommendation #6.

### Compat improvements (multi-column / multi-modality)

PRISM does NOT expect multiple physio modes per file (it does not process physio at all). The standard BIDS
guidance is: different sampling frequencies / manufacturers → separate files with distinct `recording-` labels.
We do that correctly (one file = one `recording-cardiac`). If we ever export simultaneous ECG + respiration,
we should write two files (`recording-cardiac` + `recording-respiratory`), not one file with two columns —
unless the two channels share `SamplingFrequency` and `StartTime`.

---

## Appendix A — Verbatim quote from PRISM `SPECIFICATIONS.md`

> ## High-level filename expectations
>
> PRISM follows BIDS-like entity conventions.
>
> Examples:
> - survey TSV: `sub-001_ses-1_task-ads_beh.tsv`
> - biometrics TSV: `sub-001_ses-1_biometrics-cmj_biometrics.tsv`
> - physio EDF: `sub-001_ses-1_task-rest_physio.edf`
>
> In general, data files should have matching JSON sidecars with the same stem.

Note: PRISM's physio example is `.edf`, suggesting their physio pipeline (if any) is geared to EDF rather
than TSV.GZ. We are still spec-compliant — BIDS allows both — but if MRI-Lab-Graz has a future PRISM
physio converter it may target EDF first.

## Appendix B — Verbatim quote from PRISM `biometrics.md`

> The `biometrics` modality is a PRISM extension designed for physiological assessments that do not fit into
> standard BIDS `beh` or `physio` categories. Examples include VO2max tests, plank tests, balance
> assessments, or anthropometric measurements.

→ Raw RR-interval time-series is exactly what `_physio` is for. It is **not** biometrics.

## Appendix C — Verbatim quote from BIDS-Examples `7t_trt/physio.json`

```json
{"StartTime": 0, "SamplingFrequency": 100, "Columns": ["cardiac", "respiratory", "trigger", "oxygen saturation"]}
```

Our sidecar is already substantially richer than this real-world reference.
