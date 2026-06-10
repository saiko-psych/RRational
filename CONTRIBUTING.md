# Contributing to RRational

## Local development setup

```bash
# Clone + install
git clone https://github.com/saiko-psych/rrational.git
cd rrational
uv sync --all-extras --dev

# Activate the pre-push hook so you don't push a broken-import branch
git config core.hooksPath .githooks
```

The hook runs a `pytest --collect-only` sweep on every `git push`.
Mirrors what the CI preflight job runs, finishes in ~5-10s. If you
need to push WIP that you know is broken, use `git push --no-verify`.

## Running tests

| Command | What it runs | Wall time |
| --- | --- | --- |
| `uv run pytest tests/analysis tests/cleaning tests/io tests/prep tests/segments tests/gui tests/streamlit tests/test_cli.py` | Fast tier (analysis + IO + Streamlit AppTest smoke) | ~3 min |
| `QT_QPA_PLATFORM=offscreen uv run pytest tests/inspector` | Inspector tier (PyQt6 + pyqtgraph, offscreen) | ~10-15 min |
| `uv run pytest` | Everything | ~15 min |

CI runs the same suites in two tiers (`fast` then `inspector`), gated
by a `preflight` job that catches setup failures (`libEGL`, broken
plugin configure, syntax errors) in ~15s before kicking off the
expensive jobs.

## Commit style

Follow the existing convention:

- `feat(<area>): <summary>` — new functionality
- `fix(<area>): <summary>` — bug fixes
- `refactor(<area>): <summary>` — no behavior change
- `test(<area>): <summary>` — tests only
- `docs: <summary>` — documentation
- `ci: <summary>` — CI / build infrastructure
- `chore: <summary>` — everything else

Where `<area>` is `inspector`, `analysis`, `io`, `gui` (Streamlit),
`prep`, `segments`, or omitted for cross-cutting changes.

## What NOT to commit

Internal Claude/Cursor scratch (`.claude/analysis/*.md`,
`docs/superpowers/`, `tests/workflow_verification.py`) and OS / IDE
state (`.venv/`, `.DS_Store`, `dist/`, `build/`) are gitignored.
Memory files (the assistant's recall) live outside the repo entirely.

Real participant data is gitignored by filename pattern (`*_RR_*.csv`,
`*_Events_*.csv`, VNS-style timestamped `.txt`). If you have a
non-standard format for testing, drop it under `tests/fixtures/` so
the unignore rule picks it up.
