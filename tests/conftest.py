"""Test-suite-wide configuration and hooks.

Hosts the **runtime regression tracker** introduced in Round 30. The goal
(a standing user policy) is that test runtime is always measured and drift
is caught early — without ever changing pass/fail behaviour.

How it works:

- Every pytest run records each test's TOTAL wallclock (setup + call +
  teardown — the fixture setup is where the Qt suite spends most of its
  time, so call-only would hide the real cost) into
  ``tests/.runtime_log.json``.
- Under pytest-xdist every worker writes its own ``.runtime_log.<worker>.json``
  slice; the controller process merges them at session end. This avoids
  parallel writers clobbering one shared file.
- If a LOCAL ``tests/runtime_baseline.json`` exists, the session teardown
  compares each test against it and prints a WARNING block for anything
  that regressed > 30 % AND is now > 2 s. Regressions NEVER fail the run —
  the app's functional tests stay the only fail signal.

The baseline is deliberately **machine-local** (gitignored): comparing my
Windows timings against a CI ubuntu runner would be pure noise. Generate
your own with ``python scripts/refresh_runtime_baseline.py``; until you do,
the comparator stays dormant and only the ``.runtime_log.json`` snapshot is
written.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_TESTS_DIR = Path(__file__).parent
_BASELINE_PATH = _TESTS_DIR / "runtime_baseline.json"
_LOG_PATH = _TESTS_DIR / ".runtime_log.json"
_REGRESSION_RATIO = 1.30  # 30 % slower -> warn
_REGRESSION_FLOOR_SECONDS = 2.0  # ignore tests still < 2 s

# Per-process accumulator: nodeid -> summed wallclock across all phases.
_DURATIONS: dict[str, float] = {}


def _worker_id() -> str:
    """xdist worker id ('gw0'...) or 'main' for the controller / single-lane."""
    return os.environ.get("PYTEST_XDIST_WORKER", "main")


def _per_worker_log_path() -> Path:
    return _TESTS_DIR / f".runtime_log.{_worker_id()}.json"


def pytest_runtest_logreport(report):  # noqa: D401 — pytest hook
    """Accumulate setup + call + teardown wallclock per test.

    Fixture setup (the ``setup`` phase) dominates the Qt suite, so summing
    all three phases is what surfaces the real per-test cost — call-only
    would report ~0.1 s for a test whose MainWindow fixture took 14 s.
    """
    _DURATIONS[report.nodeid] = _DURATIONS.get(report.nodeid, 0.0) + float(
        report.duration
    )


def pytest_sessionfinish(session, exitstatus):  # noqa: D401 — pytest hook
    """Dump this worker's slice; on the controller, merge + report drift."""
    if _DURATIONS:
        try:
            _per_worker_log_path().write_text(
                json.dumps(_DURATIONS, indent=2), encoding="utf-8"
            )
        except OSError:
            return  # never fail the suite over a logging blip

    # Only the controller (or a single-lane run) merges + compares.
    if _worker_id() != "main":
        return

    merged: dict[str, float] = {}
    for slice_path in _TESTS_DIR.glob(".runtime_log.*.json"):
        try:
            merged.update(json.loads(slice_path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    # The controller also receives every worker's reports, so fold in its
    # own accumulator too (covers the single-lane / no-xdist case).
    merged.update(_DURATIONS)

    if not merged:
        return
    try:
        _LOG_PATH.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    except OSError:
        pass

    if not _BASELINE_PATH.exists():
        return  # dormant until a local baseline is generated

    try:
        baseline: dict[str, float] = json.loads(
            _BASELINE_PATH.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return

    regressions: list[tuple[str, float, float, float]] = []
    for nodeid, current in merged.items():
        base = baseline.get(nodeid)
        if base is None or base <= 0 or current < _REGRESSION_FLOOR_SECONDS:
            continue
        if current / base >= _REGRESSION_RATIO:
            regressions.append((nodeid, base, current, current / base))

    if not regressions:
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    emit = reporter.write_line if reporter else print
    emit("")
    emit("=" * 78)
    emit(f"RUNTIME REGRESSION (>{int((_REGRESSION_RATIO - 1) * 100)}% and >2s):")
    regressions.sort(key=lambda r: r[3], reverse=True)
    for nodeid, base, current, ratio in regressions[:10]:
        emit(f"  {ratio:5.2f}x   {base:7.2f}s -> {current:7.2f}s   {nodeid}")
    emit("Baseline is machine-local; refresh via scripts/refresh_runtime_baseline.py")
    emit("=" * 78)
