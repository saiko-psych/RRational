"""Refresh ``tests/runtime_baseline.json`` from a fresh pytest run.

Run after intentional speed-up work (or after a deliberate slowdown
that needs to land — e.g. a new test that genuinely needs ~5 s). The
baseline is the source the conftest hook compares against to warn on
runtime regressions.

The baseline is **machine-local** (gitignored) — timings differ too much
between a dev laptop and the CI runner for a shared file to be meaningful.
Each contributor generates their own; there is no ``git add`` step.

Usage::

    python scripts/refresh_runtime_baseline.py            # full inspector + analysis slice
    python scripts/refresh_runtime_baseline.py tests/io    # only one directory
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = ROOT / "tests"
BASELINE = TESTS_DIR / "runtime_baseline.json"
LOG = TESTS_DIR / ".runtime_log.json"


def main(argv: list[str]) -> int:
    test_targets = argv[1:] or [
        "tests/inspector/",
        "tests/io/",
        "tests/analysis/",
        "tests/cleaning/",
        "tests/segments/",
    ]
    print(f"Refreshing baseline from: {' '.join(test_targets)}")

    started = time.perf_counter()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            *test_targets,
            "--tb=line",
            "-q",
            "--durations=0",
        ],
        cwd=ROOT,
    )
    elapsed = time.perf_counter() - started
    print(f"Elapsed: {elapsed:.1f}s  (pytest exit={proc.returncode})")

    if not LOG.exists():
        print("ERROR: tests/.runtime_log.json was not written — did conftest run?")
        return 1

    durations: dict[str, float] = json.loads(LOG.read_text(encoding="utf-8"))
    if not durations:
        print("ERROR: log file empty.")
        return 1

    # Keep only tests >= 0.1 s to bound the baseline size + skip pure-import noise.
    pruned = {k: round(v, 3) for k, v in durations.items() if v >= 0.1}
    pruned = dict(sorted(pruned.items(), key=lambda kv: kv[1], reverse=True))

    BASELINE.write_text(json.dumps(pruned, indent=2), encoding="utf-8")
    print(f"Wrote {len(pruned)} entries to {BASELINE.relative_to(ROOT)}")
    print("Remember to: git add tests/runtime_baseline.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
