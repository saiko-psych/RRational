# Project Restructure: Analysis → Plan → Execute

You are a senior Python/research software engineer helping restructure the **RRational HRV analysis project**
into a clean, professional, and maintainable codebase.

---

## PHASE 1: DEEP ANALYSIS (do this first, touch nothing)

Run the following analysis steps silently and compile the results before showing anything to the user.

### 1.1 — Map the current structure

```bash
find . -type f \( -name "*.py" -o -name "*.R" -o -name "*.qmd" -o -name "*.md" -o -name "*.ipynb" -o -name "*.yaml" -o -name "*.toml" -o -name "requirements*.txt" \) \
  | grep -v ".git" | sort
```

For each `.py` file, also gather:
```bash
wc -l **/*.py 2>/dev/null || find . -name "*.py" | xargs wc -l | sort -rn
```

### 1.2 — Identify what each large script actually does

For every `.py` file with more than 200 lines:
- Read the first 80 lines (imports, module docstring, top-level structure)
- Read all function/class definitions: `grep -n "^def \|^class " <file>`
- Identify: Is it a pipeline entry point? A utility module? A mixed monolith?

### 1.3 — Check existing project scaffolding

```bash
# Check for existing package structure, tests, configs
ls -la
cat requirements*.txt 2>/dev/null || cat pyproject.toml 2>/dev/null || echo "No dependency file found"
cat README.md 2>/dev/null | head -60
cat CLAUDE.md 2>/dev/null && echo "CLAUDE.md exists" || echo "No CLAUDE.md"
ls .claude/ 2>/dev/null && echo "Has .claude/" || echo "No .claude/"
git log --oneline -10 2>/dev/null || echo "No git history"
git status 2>/dev/null
```

### 1.4 — Identify data flow

Trace the pipeline: Where does raw Polar H10 data enter? How does it flow through the scripts?
Look for patterns like: `pd.read_csv`, `open(`, `load_`, file path arguments, `argparse`.

---

## PHASE 2: PRESENT THE PLAN (wait for confirmation before touching anything)

After the analysis, present a clear restructuring plan in this format:

---

### 📊 Current State Summary

| File | Lines | Role identified | Problem |
|------|-------|-----------------|---------|
| ... | ... | ... | ... |

### 🏗️ Proposed New Structure

```
RRational/
├── src/
│   └── rrational/              # installable Python package
│       ├── __init__.py
│       ├── io/                 # data loading (Polar H10, CSV, etc.)
│       │   ├── __init__.py
│       │   └── loaders.py
│       ├── preprocessing/      # artifact detection, Lipponen-Tarvainen, filtering
│       │   ├── __init__.py
│       │   ├── artifacts.py
│       │   └── interpolation.py
│       ├── analysis/           # HRV metrics: time/frequency/nonlinear domain
│       │   ├── __init__.py
│       │   ├── time_domain.py
│       │   ├── frequency_domain.py
│       │   └── nonlinear.py
│       ├── segmentation/       # windowing, epoch extraction, 3h recording handling
│       │   ├── __init__.py
│       │   └── windowing.py
│       └── visualization/      # plots, dashboards
│           ├── __init__.py
│           └── plots.py
├── scripts/                    # runnable entry points (thin wrappers only)
│   ├── run_pipeline.py
│   └── batch_process.py
├── notebooks/                  # exploratory analysis, not production code
├── data/
│   ├── raw/                    # untouched original files (read-only)
│   ├── processed/              # intermediate artifacts
│   └── results/                # final outputs
├── tests/                      # basic smoke tests
│   └── test_preprocessing.py
├── docs/
│   └── pipeline_overview.md
├── CLAUDE.md                   # Claude Code project memory
├── .claude/
│   ├── commands/               # slash commands
│   │   └── restructure.md      # this file
│   └── skills/                 # domain knowledge for Claude
│       └── hrv-domain.md
├── pyproject.toml              # replaces requirements.txt
└── README.md
```

### 🔪 Specific Refactoring Steps

For each monolithic script (e.g. a 10,000+ line file):

1. **Extract by responsibility** — group functions into the modules above
2. **Preserve the public API** — keep function signatures identical during extraction
3. **Add module docstrings** — one sentence per module explaining its role
4. **Create `__init__.py` exports** — so `from rrational.preprocessing import remove_artifacts` works

### 📄 Files to Create

- `CLAUDE.md` — project memory with: pipeline overview, key algorithms (Lipponen-Tarvainen),
  data formats (Polar H10 RR-intervals), naming conventions, known gotchas
- `.claude/skills/hrv-domain.md` — HRV domain knowledge for Claude
  (what RMSSD means, what artifact thresholds are reasonable, etc.)
- `pyproject.toml` — with all dependencies pinned
- Updated `README.md` — with: what the project does, how to install, how to run

### ⚠️ What will NOT be changed

- Logic inside functions (no silent behavior changes)
- Data file formats
- Git history

---

**Do you want to proceed with this plan?**
Type `yes` to execute all steps, `partial` to choose specific steps,
or tell me what to change in the plan.

---

## PHASE 3: EXECUTE (only after explicit confirmation)

Execute the plan step by step. For each step:

1. **Announce** what you are about to do in one line
2. **Do it**
3. **Verify** it worked (e.g. `python -c "from rrational.preprocessing import ..."`)
4. **Report** result before moving to next step

### Create CLAUDE.md with proper content:

```markdown
# RRational — HRV Analysis Pipeline

## What this project does
Processes long-duration (3h) RR-interval recordings from Polar H10 devices.
Implements artifact detection (Lipponen-Tarvainen algorithm), segmentation,
and computation of time/frequency/nonlinear HRV metrics.

## Pipeline overview
Raw Polar H10 data → Load → Artifact detection → Interpolation → Segmentation → HRV metrics → Output

## Key algorithms
- Artifact detection: Lipponen & Tarvainen (2019) method
- Frequency domain: Welch PSD / Lomb-Scargle for unevenly sampled data
- Nonlinear: Poincaré SD1/SD2, sample entropy

## Data formats
- Input: CSV with RR-intervals in milliseconds (Polar H10 export)
- Processing window: [to be filled]
- Output: [to be filled]

## Naming conventions
- Functions: snake_case, verb-first (e.g. `detect_artifacts`, `compute_rmssd`)
- Files: lowercase with underscores
- Constants: UPPER_CASE

## Known gotchas
- [Claude: fill this in from issues/comments found in the code]

## Running the pipeline
```bash
python scripts/run_pipeline.py --input data/raw/ --output data/results/
```

## Dependencies
See pyproject.toml
```

### Create `.claude/skills/hrv-domain.md`:

```markdown
# HRV Domain Knowledge for Claude

## Core concepts
- RR-interval: time between successive R-peaks in ECG (in ms)
- NN-interval: Normal-to-Normal = RR after artifact removal
- RMSSD: primary parasympathetic marker, use for short-term recordings
- SDNN: total HRV, use for long-term (≥24h) recordings
- LF/HF ratio: controversial as sympathovagal balance marker

## Artifact thresholds (Polar H10 / research standard)
- Physiologically implausible: RR < 300ms or > 2000ms (HR 30–200 bpm)
- Ectopic beats: >20% deviation from preceding interval (Malik rule)
- Lipponen-Tarvainen: preferred for long recordings, handles local rate changes

## Analysis windows
- Short-term metrics (RMSSD, pNN50): minimum 5 min
- Frequency domain (LF, HF): minimum 5 min, optimal ≥5 min stationary
- SDNN, triangular index: requires ≥20 min recording
- For 3h recordings: sliding window with overlap

## This project uses
- NeuroKit2 for signal processing
- hrv-analysis (Aura Healthcare) for metric computation
- Polar H10 as sensor
```

After all steps: run a final structural check and show the user the new `tree` output.
