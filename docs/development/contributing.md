# Contributing to RRational

Thank you for your interest in contributing to RRational! This guide covers how to report issues, suggest features, and contribute code.

---

## Reporting Issues (For All Users)

### Before You Report

1. **Check existing issues first!**
   - Go to [Issues](https://github.com/saiko-psych/rrational/issues)
   - Search for keywords related to your problem
   - If you find a similar issue, add a comment or thumbs up instead of creating a new one

2. **Try the latest version**
   - Update RRational: `git pull origin main && uv sync`
   - Your issue might already be fixed!

### How to Report a Bug

1. Go to [New Issue](https://github.com/saiko-psych/rrational/issues/new/choose)
2. Select **"Bug Report"**
3. Fill out the form completely:
   - **Description**: What happened? What were you trying to do?
   - **Steps to reproduce**: How can we recreate this?
   - **Error message**: Copy and paste any red error text
   - **Screenshot**: Very helpful! (Win: `Win+Shift+S`, Mac: `Cmd+Shift+4`)
   - **Priority**: How much does this affect your work?

### Priority Labels

Please select an appropriate priority when reporting:

| Priority | When to Use | Label |
|----------|-------------|-------|
| **Low** | Minor inconvenience, you have a workaround | `priority: low` |
| **Medium** | Affects workflow but you can continue | `priority: medium` |
| **High** | Significantly blocking your work | `priority: high` |
| **Critical** | Cannot use RRational at all | `priority: critical` |

### Suggesting Features

1. Go to [New Issue](https://github.com/saiko-psych/rrational/issues/new/choose)
2. Select **"Feature Request"**
3. Describe:
   - What problem would this solve?
   - How would you like it to work?
   - How important is it to your research?

---

## For Developers

### Repository Layout

```
rrational/
├── src/rrational/
│   ├── gui/              # Streamlit GUI (app.py, project.py, welcome.py, tabs/)
│   ├── io/               # Data loaders (hrv_logger.py, vns_analyse.py)
│   ├── cleaning/         # RR interval processing
│   └── segments/         # Section normalization
├── tests/                # pytest test suites
│   └── fixtures/         # Test data (anonymized CSV snippets)
├── data/
│   ├── demo/             # Demo data (included in repo)
│   ├── raw/              # User data (git-ignored)
│   └── processed/        # Processed data (git-ignored)
├── docs/                 # Documentation
└── .github/              # Issue templates
```

### Development Setup

```bash
# Clone and install
git clone https://github.com/saiko-psych/rrational.git
cd rrational
uv sync --group dev

# Run the app
uv run streamlit run src/rrational/gui/app.py

# Run tests
uv run pytest -v

# Lint code
uv run ruff check src/ tests/ --fix
```

### Coding Standards

- **Python**: 3.11+ required
- **Formatting**: Use `ruff` for linting
- **Naming**: `snake_case` for functions/variables, `PascalCase` for classes
- **Types**: Prefer explicit type hints
- **Paths**: Use `pathlib.Path` for filesystem operations
- **Docstrings**: NumPy-style for public functions

### Testing

- Run full suite: `uv run pytest`
- Run specific tests: `uv run pytest tests/cleaning/ -v`
- Target: 85%+ statement coverage
- Always add tests for new features or bug fixes

### Pull Request Guidelines

1. **Branch from main**: Create a feature branch (`feat/my-feature` or `fix/bug-description`)
2. **Write tests**: Cover new functionality
3. **Update docs**: If your change affects users, update README or QUICKSTART
4. **Run tests**: Ensure all tests pass (`uv run pytest`)
5. **Describe changes**: Summarize what and why in the PR description
6. **Screenshots**: Include for any GUI changes

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add batch analysis for multiple participants
fix: correct event sorting in Participants tab
docs: update QUICKSTART with project workflow
refactor: extract artifact detection to separate module
```

---

## Data Privacy

- **Never commit real participant data** to the repository
- Test fixtures use anonymized/simulated data only
- Keep sensitive data in `data/raw/` (git-ignored) or `local_test_data/`
- Verify that screenshots don't contain identifiable information

---

## Questions?

- Check the [QUICKSTART.md](../QUICKSTART.md) guide
- Search [existing issues](https://github.com/saiko-psych/rrational/issues)
- Open a new issue with the "Question" label

---

**Thank you for helping improve RRational!**
