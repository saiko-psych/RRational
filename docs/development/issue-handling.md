# Issue Handling Guidelines

Guidelines for handling user-reported issues in RRational.

## Process

### 1. Reproduce First
Before making any code changes:
- **Always try to reproduce the issue** in the current codebase
- Use the Playwright MCP plugin for visual testing (saves screenshots to disk)
- Document the exact steps to reproduce
- If the issue cannot be reproduced, it may already be fixed or needs more information

### 2. Understand the Root Cause
- Read the relevant code sections
- Trace the data flow
- Identify why the bug occurs (e.g., stale closure variables, missing state updates)

### 3. Implement Fix
- Make minimal, targeted changes
- Follow existing code patterns
- Add comments explaining non-obvious fixes

### 4. Test Thoroughly
- Run `uv run pytest` to ensure no regressions
- Visually test the fix using the Playwright MCP plugin
- Test edge cases (empty inputs, invalid data, etc.)
- Verify the fix doesn't break related functionality

### 5. Document
- Update MEMORY.md with session notes
- Update CLAUDE.md if version changes
- Close GitHub issues with commit references

---

## Common Bug Patterns in Streamlit

### Stale Closure Variables
**Problem**: Callbacks defined inside the render loop capture stale variable values.

**Symptom**: Input values appear to be ignored, using defaults instead.

**Fix**: Read values from `st.session_state` using widget keys inside callbacks:
```python
# BAD - uses stale closure variable
def callback():
    value = input_var  # Captures value from previous render!

# GOOD - reads current value from session state
def callback():
    value = st.session_state.get("input_key", default)
```

### Widget Key Conflicts
**Problem**: Duplicate widget keys cause unpredictable behavior.

**Fix**: Use unique keys with participant/context prefixes:
```python
key=f"widget_name_{participant_id}"
```

### State Not Persisting
**Problem**: Changes don't persist across reruns.

**Fix**: Always update `st.session_state` and call save functions.

### Double-Click Required
**Problem**: UI updates only after second interaction.

**Cause**: State updated but `st.rerun()` not called, or callback runs before state is visible.

**Fix**: Add `st.rerun()` after state changes, or use `on_change` callbacks.

---

## Issue Categories

### High Priority
- Data loss (groups/events disappearing)
- Core features broken (adding events, artifact marking)
- Crashes

### Medium Priority
- UI glitches (double-click needed, wrong warnings)
- Platform-specific issues (Mac settings)
- Validation gaps

### Low Priority
- Cosmetic issues
- Minor UX improvements
- Performance (unless severe)

---

## Testing Checklist

- [ ] Issue reproduced before fix
- [ ] All tests pass (`uv run pytest`)
- [ ] Visual testing confirms fix
- [ ] Related functionality still works
- [ ] No new warnings in console
- [ ] Fix works on demo data

---

## GitHub Issue Commands

```bash
# List open issues
gh issue list --state open

# View issue details
gh issue view <number>

# Close issue with comment
gh issue close <number> -c "Fixed in commit <hash>"
```
