"""HTML report generation — render a complete report and verify
structure + visual quality.

Round 26 found that report._recipe_code referenced a non-existent
``actions`` attribute on HistoryRecorder, producing an empty recipe
block in every published HTML report. This script exercises the full
report pipeline end-to-end so that regressions are caught at the
visual level — opening the HTML in a browser screenshot.

Output:
  tests/visual/e2e_snapshots/html_report.html (the generated report)
  tests/visual/e2e_snapshots/html_report_summary.txt (structure check)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
from qtpy.QtCore import QEventLoop, QTimer
from qtpy.QtWidgets import QApplication

from rrational.inspector.app import set_plot_theme  # noqa: E402
from rrational.inspector.data_loader import (  # noqa: E402
    Dataset,
    EventMeta,
    InspectorData,
    SectionMeta,
)
from rrational.inspector.history.actions import (  # noqa: E402
    AddExclusionZone,
    DetectArtifacts,
    LoadRecording,
)
from rrational.inspector.main_window import MainWindow  # noqa: E402
from rrational.inspector.style import apply_app_theme  # noqa: E402

_OUT = Path(__file__).parent / "e2e_snapshots"
_OUT.mkdir(exist_ok=True)


def _settle(app, ms=400):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()
    app.processEvents()


def _synth(name, seed, mean_rr, n_beats=600):
    rng = np.random.default_rng(seed=seed)
    rr = mean_rr + 30 * rng.standard_normal(n_beats)
    t = 1_700_000_000.0 + np.cumsum(rr) / 1000.0
    sections = [
        SectionMeta(
            name="rest",
            t_start=float(t[0]),
            t_end=float(t[n_beats // 2 - 1]),
            beat_count=n_beats // 2,
        ),
        SectionMeta(
            name="task",
            t_start=float(t[n_beats // 2]),
            t_end=float(t[-1]),
            beat_count=n_beats - n_beats // 2,
        ),
    ]
    events = [
        EventMeta(label="rest_start", t=float(t[0])),
        EventMeta(label="task_start", t=float(t[n_beats // 2])),
        EventMeta(label="task_end", t=float(t[-1])),
    ]
    return Dataset(
        name=name,
        data=InspectorData(t=t, v=rr, sections=sections, events=events),
    )


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    apply_app_theme(app, mode="dark")
    set_plot_theme("dark")

    print("[boot] HTML report E2E starting")
    win = MainWindow()
    win.resize(1400, 900)
    win.show()
    _settle(app, 400)

    # Add 3 datasets to give the report something to summarise.
    for i in range(3):
        win.add_dataset(
            _synth(name=f"html_subj_{i}.csv", seed=10 + i, mean_rr=800 + i * 20)
        )
    win.set_active_dataset(0)
    _settle(app, 500)

    # Record a representative action history so the recipe block is
    # non-empty — Round 26 found it was always empty due to the
    # attribute-name typo.
    win.history.record(LoadRecording(path="html_subj_0.csv"))
    win.history.record(DetectArtifacts(method="neurokit2_lipponen"))
    win.history.record(
        AddExclusionZone(
            pid="html_subj_0",
            t_start=10.0,
            t_end=20.0,
            reason="motion artifact",
        )
    )
    print(f"[record] history has {len(win.history)} action(s)")

    # Build the report via the inspector's ReportBuilder rather than
    # going through the menu action (which would open a file dialog).
    from rrational.inspector.report import ReportBuilder

    rb = ReportBuilder(win)
    html = rb.build_html()

    out_html = _OUT / "html_report.html"
    out_html.write_text(html, encoding="utf-8")
    print(f"[write] {out_html} ({len(html)} chars)")

    # Structural checks — these are the contract the report claims to
    # provide. Anything missing flags a regression.
    summary_lines: list[str] = []

    def _check(label: str, predicate: bool, detail: str = "") -> bool:
        mark = "OK" if predicate else "MISS"
        line = f"[{mark}] {label}"
        if detail:
            line += f" — {detail}"
        summary_lines.append(line)
        print(line)
        return predicate

    _check("doctype declared", html.lstrip().lower().startswith("<!doctype"))
    _check("title element present", "<title" in html)
    _check("project / dataset section present", "html_subj_0.csv" in html)

    # Recipe block: Round 26 fixed report._recipe_code to use len()
    # instead of getattr("actions"). Verify the recipe Python is now
    # embedded.
    has_recipe = (
        "DetectArtifacts" in html
        or "_existing.append" in html
        or "rr_intervals" in html
    )
    _check(
        "recipe block contains action code",
        has_recipe,
        "look for DetectArtifacts / _existing.append / rr_intervals",
    )

    # The audit trail (per-dataset history) should be present.
    has_audit = "Audit" in html or "audit" in html
    _check("audit trail section present", has_audit)

    # Anchor links table-of-contents (markers of a structured report).
    n_anchors = len(re.findall(r"<a [^>]*href=['\"]#", html))
    _check("at least 3 internal anchor links", n_anchors >= 3, f"found {n_anchors}")

    # DOI references — published builds should include citations.
    n_doi = len(re.findall(r"\bdoi\.org/10\.", html, flags=re.IGNORECASE))
    _check("at least 1 DOI citation embedded", n_doi >= 1, f"found {n_doi}")

    # Negative-style checks — these strings should NOT appear because
    # they indicate placeholder content shipped to production.
    # Strip every base64 inline image first; the random byte sequence
    # easily contains "XXX" or "TODO" substrings that aren't real
    # placeholders (the regex matched inside image src attributes).
    html_no_imgs = re.sub(r"data:image/[^;]+;base64,[A-Za-z0-9+/=]+", "", html)
    leaks = ["TODO", "FIXME", "XXX", "placeholder text"]
    leaked = [w for w in leaks if w in html_no_imgs]
    _check("no placeholder strings leaked", not leaked, f"leaked={leaked}")

    summary_path = _OUT / "html_report_summary.txt"
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(f"\n[done] summary at {summary_path}")
    return 0 if all("[OK]" in line for line in summary_lines) else 1


if __name__ == "__main__":
    sys.exit(main())
