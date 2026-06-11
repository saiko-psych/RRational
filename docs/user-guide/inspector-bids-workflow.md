# Inspector BIDS-physio + PRISM Studio Export Workflow

RRational supports two complementary standards for sharing cardiac
recordings beyond the inspector:

- **BIDS-physio** — the Brain Imaging Data Structure specification
  for physiological recordings, the de-facto standard for
  multi-modal (EEG / fMRI + cardiac) study packaging.
- **PRISM Studio biometrics** — a single-row summary-metrics format
  used by the PRISM Studio framework for psychological-research
  workflows.

Both exporters live under the **Tools** menu and operate on the
active recording (the dataset currently shown in the Participant
tab).

---

## Exporting to BIDS-physio

### Step-by-step

1. Load a recording into the inspector (see
   [Inspector Workflows](inspector-workflows.md)).
2. Open the **Tools** menu and choose
   *Export to BIDS-physio…*.
3. In the dialog:
   - **Participant ID** (`sub-<id>`) — required, alphanumeric.
   - **Session ID** (`ses-<id>`) — optional, omit for single-session
     studies.
   - **Task name** (`task-<name>`) — required, defaults to
     `cardiac`.
   - **Output directory** — typically your BIDS root or a
     `sourcedata/` subfolder.
   - **Anonymize** — see below.
4. Click **Export**. RRational writes two files into the chosen
   directory.

### Output naming

```text
sub-<pid>[_ses-<ses>]_task-<task>_recording-cardiac_physio.tsv.gz
sub-<pid>[_ses-<ses>]_task-<task>_recording-cardiac_physio.json
```

The `.tsv.gz` is a single-column gzipped TSV of RR intervals (ms).
The `.json` sidecar carries the BIDS-required metadata for the
recording.

### Sidecar fields

**Required (BIDS spec):**

- `SamplingFrequency` — populated with the mean beat rate
  (Hz, computed as `1 / mean(RR_seconds)`) per the BIDS-spec
  documented workaround for event-spaced cardiac data.
- `StartTime` — recording start, in seconds relative to the run
  start.
- `Columns` — `["cardiac"]`.

**Recommended:**

- `Manufacturer` — original device vendor when known.
- `RecordingDuration` — in seconds.
- `RecordingType` — `"continuous"`.

**Anonymize switch:**

Ticking the *Anonymize* checkbox in the export dialog:

- Shifts the `acq_date` field back by a configurable N days
  (DSGVO / HIPAA-style date offset).
- Strips the `experimenter` and `description` fields from the
  sidecar.
- Replaces participant-identifying free-text with the canonical
  `sub-<id>` token only.

For data-sharing in EU contexts, *Anonymize* is the recommended
default.

### Round-trip — re-importing your own BIDS export

The same `.tsv.gz + .json` pair produced by *Tools → Export to
BIDS-physio…* can be re-loaded via **File → Open recording…** and
picking the `.tsv.gz`. The importer:

1. Reads the JSON sidecar for sampling-frequency hints and
   metadata.
2. Treats the single column as the RR series (in ms).
3. Reconstructs an internal annotation list with synthetic
   `recording_start` / `recording_end` events if the sidecar
   carries no event timing.

This round-trip is verified by the inspector test suite — see
`tests/inspector/test_bids_physio_round_trip.py`.

---

## PRISM Studio biometrics — for psych research

The PRISM Studio framework expects HRV summary metrics rather than
the full time-series. To export:

1. Run an analysis (Single Participant or Repeating Section) so
   metrics are computed.
2. Open **Tools → Export to PRISM biometrics…**.
3. Choose an output directory. RRational writes:
   - A single-row `.tsv` with the canonical HRV columns
     (`MeanNN`, `SDNN`, `RMSSD`, `pNN50`, `LF`, `HF`, `LF/HF`,
     `SD1`, `SD2`, `SD1/SD2`).
   - A matching `.json` sidecar with PRISM's three required
     blocks:
     - **Technical** — sampling, detector version, correction
       flags.
     - **Study** — participant ID, group, session, condition.
     - **Metadata** — RRational version, export timestamp.

The PRISM exporter is **summary-only** by design — the
time-series itself stays in your project as `.rrational v2`. If
you need the time-series in a PRISM workflow, use the BIDS-physio
exporter alongside.

---

## See also

- [Inspector Feature Reference](inspector-features.md) — menu
  layout and all available actions.
- [Inspector Workflows](inspector-workflows.md) — end-to-end
  analysis recipes.
- [Inspector Recipe Replay](inspector-recipe-replay.md) — capture
  the export step as a reproducible Python script.
