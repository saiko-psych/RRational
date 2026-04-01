# Installation Guide

## Prerequisites

- **Python 3.11, 3.12, or 3.13** — [Download from python.org](https://www.python.org/downloads/)
  - Python 3.14 is **not yet supported** (pyarrow lacks wheels)
  - Check your version: `python --version`

- **uv** (recommended package manager) — [Install uv](https://docs.astral.sh/uv/getting-started/installation/)
  ```bash
  # Windows (PowerShell)
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

  # macOS/Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

## Installation

```bash
git clone https://github.com/saiko-psych/rrational.git
cd rrational
uv sync
```

If you have Python 3.14 installed, install a compatible version first:
```bash
uv python install 3.11
uv sync
```

### Alternative: pip

```bash
pip install -e .
```

## Launching

```bash
uv run streamlit run src/rrational/gui/app.py
```

The app opens at http://localhost:8501.

### Test Mode (Demo Data)

```bash
uv run streamlit run src/rrational/gui/app.py -- --test-mode
```

## Updating

```bash
cd rrational
git pull origin main
uv sync
```

## Troubleshooting

### `Failed to build pyarrow`

You likely have Python 3.14. Run `uv python install 3.11` first, then `uv sync` again.

### `failed to canonicalize script path`

Your virtual environment may be corrupted. Delete and re-sync:

```bash
# Windows
rmdir /s /q .venv
uv sync

# macOS/Linux
rm -rf .venv
uv sync
```

### Slow startup

- Close other browser tabs
- Reduce plot resolution in Settings
- Use "Load Preview" first for large datasets

### Port already in use

If port 8501 is busy, Streamlit will try 8502, 8503, etc. Check the terminal output for the actual URL.
