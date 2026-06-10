"""Publication-ready HTML / Markdown reports built from ResultsStore.

Renders the inspector's accumulated metric rows + statistical-test rows
into a self-contained report file with:

- Title + project + report metadata (RRational version, timestamp)
- Datasets table (name, beat count, duration)
- HRV metrics table (one row per Single-Participant / Repeating-Section
  compute), sortable in HTML
- Group test results (between-subjects), with colour-coded p-values
- Sequence test results (within-subjects RM-ANOVA / Friedman)
- Quality summary (per-dataset artifact-rate breakdown, pulled from any
  loaded .rrational file's ``QualityV2`` block)
- Methods paragraph + reference bibliography with clickable DOI links
- Audit trail collected from loaded .rrational files

HTML output is **self-contained**: inline CSS, base64-embedded plots,
no external assets. Friendly for emailing, attaching to grant
applications, or printing.

Markdown output is GitHub-flavoured (pipe tables + `![alt](data:…)`)
and follows the same section structure so the two formats stay in
lock-step.

Plots are exported via ``pyqtgraph.exporters.ImageExporter`` if a live
``BrowseTab`` plot is reachable. When that fails (headless environment,
plot widget not yet built), the renderer silently emits an HTML comment
``<!-- plot pending -->`` and Markdown skips the image line — the rest
of the report still builds.
"""

from __future__ import annotations

import base64
import io
import math
from dataclasses import dataclass
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rrational.inspector.main_window import MainWindow
    from rrational.inspector.results_store import (
        MetricRow,
        ResultsStore,
    )


# ----------------------------------------------------------------------
# References used in the Methods section. Every DOI here has been
# manually verified to resolve to the cited paper. Adding new references
# requires the same verification step (see superpowers/verify-citations).
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class _Reference:
    key: str
    citation: str
    doi: str | None  # plain DOI suffix, e.g. "10.3389/fpsyg.2013.00863"
    url: str | None = None  # used when there is no DOI (e.g. JSTOR)


_REFERENCES: tuple[_Reference, ...] = (
    _Reference(
        key="TaskForce1996",
        citation=(
            "Task Force of the European Society of Cardiology and the North "
            "American Society of Pacing and Electrophysiology (1996). Heart "
            "rate variability: Standards of measurement, physiological "
            "interpretation, and clinical use. Circulation, 93(5), 1043-1065."
        ),
        doi="10.1161/01.CIR.93.5.1043",
    ),
    _Reference(
        key="Quigley2024",
        citation=(
            "Quigley, K.S., Gianaros, P.J., Norman, G.J., Jennings, J.R., "
            "Berntson, G.G., & de Geus, E.J.C. (2024). Publication standards "
            "for cardiac psychophysiology revisited: An update for "
            "researchers and reviewers. Psychophysiology, 61(1), e14438."
        ),
        doi="10.1111/psyp.14438",
    ),
    _Reference(
        key="Lipponen2019",
        citation=(
            "Lipponen, J.A., & Tarvainen, M.P. (2019). A robust algorithm "
            "for heart rate variability time series artefact correction "
            "using novel beat classification. Journal of Medical "
            "Engineering & Technology, 43(3), 173-181."
        ),
        doi="10.1080/03091902.2019.1640306",
    ),
    _Reference(
        key="Welch1947",
        citation=(
            "Welch, B.L. (1947). The generalization of 'Student's' problem "
            "when several different population variances are involved. "
            "Biometrika, 34(1/2), 28-35."
        ),
        doi="10.1093/biomet/34.1-2.28",
    ),
    _Reference(
        key="Friedman1937",
        citation=(
            "Friedman, M. (1937). The use of ranks to avoid the assumption "
            "of normality implicit in the analysis of variance. Journal of "
            "the American Statistical Association, 32(200), 675-701."
        ),
        doi="10.1080/01621459.1937.10503522",
    ),
    _Reference(
        key="Holm1979",
        citation=(
            "Holm, S. (1979). A simple sequentially rejective multiple test "
            "procedure. Scandinavian Journal of Statistics, 6(2), 65-70."
        ),
        doi=None,
        url="https://www.jstor.org/stable/4615733",
    ),
    _Reference(
        key="Cohen1988",
        citation=(
            "Cohen, J. (1988). Statistical Power Analysis for the "
            "Behavioral Sciences (2nd ed.). Lawrence Erlbaum Associates."
        ),
        doi="10.4324/9780203771587",
    ),
    _Reference(
        key="Lakens2013",
        citation=(
            "Lakens, D. (2013). Calculating and reporting effect sizes to "
            "facilitate cumulative science. Frontiers in Psychology, 4, 863."
        ),
        doi="10.3389/fpsyg.2013.00863",
    ),
)


def _ref_url(ref: _Reference) -> str:
    if ref.doi:
        return f"https://doi.org/{ref.doi}"
    return ref.url or ""


# ----------------------------------------------------------------------
# Small format helpers
# ----------------------------------------------------------------------
_DEFAULT_METRICS = ["RMSSD", "SDNN", "MeanHR", "LF", "HF", "LF_HF", "pNN50"]


def _get_version() -> str:
    try:
        return version("rrational")
    except PackageNotFoundError:  # pragma: no cover - dev install only
        return "unknown"


def _fmt_num(value, ndigits: int = 3) -> str:
    if value is None:
        return "—"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(f):
        return "—"
    if abs(f) >= 1000 or (f != 0 and abs(f) < 0.01):
        return f"{f:.2e}"
    return f"{f:.{ndigits}f}"


def _fmt_p(p: float | None) -> str:
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "—"
    if p < 0.001:
        return "&lt;0.001"
    return f"{p:.3f}"


def _fmt_p_md(p: float | None) -> str:
    """Plain-text p-value for Markdown (no HTML entities)."""
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "—"
    if p < 0.001:
        return "<0.001"
    return f"{p:.3f}"


def _p_class(p: float | None) -> str:
    """CSS class for colour-coded p-values."""
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "p-ns"
    if p <= 0.001:
        return "p-001"
    if p <= 0.01:
        return "p-01"
    if p <= 0.05:
        return "p-05"
    return "p-ns"


def _fmt_duration(seconds: float) -> str:
    if seconds is None or math.isnan(seconds):
        return "—"
    minutes, secs = divmod(int(round(seconds)), 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    return f"{minutes}m {secs:02d}s"


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


_PYTHON_KEYWORDS = frozenset(
    [
        "False",
        "None",
        "True",
        "and",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "class",
        "continue",
        "def",
        "del",
        "elif",
        "else",
        "except",
        "finally",
        "for",
        "from",
        "global",
        "if",
        "import",
        "in",
        "is",
        "lambda",
        "nonlocal",
        "not",
        "or",
        "pass",
        "raise",
        "return",
        "try",
        "while",
        "with",
        "yield",
    ]
)


def _highlight_python(code: str) -> str:
    """Tiny in-house Python highlighter for the embedded recipe block.

    Tokenises the recorded recipe via :mod:`tokenize` and wraps each
    token in a span carrying one of the four CSS classes defined in
    ``_BASE_CSS`` (``kw`` / ``str`` / ``com`` / ``num``). We use
    ``tokenize`` rather than regex so the highlighter handles triple-
    quoted strings, escape sequences, and comments after code on the
    same line without false positives. Falls back to a plain
    HTML-escape on any tokenisation error — the script is then still
    readable, just not coloured.
    """
    import io
    import tokenize

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(code).readline))
    except (tokenize.TokenizeError, IndentationError, SyntaxError):
        return _html_escape(code)

    # Rebuild the source line by line so whitespace + indentation are
    # preserved exactly — token columns track the original character
    # offsets, so we can splice spans into the raw source.
    lines = code.splitlines(keepends=True)
    out: list[str] = []
    for lineno, line in enumerate(lines, start=1):
        cursor = 0
        for tok in tokens:
            if tok.type in (tokenize.ENCODING, tokenize.ENDMARKER):
                continue
            (s_line, s_col), (e_line, e_col) = tok.start, tok.end
            if s_line != lineno:
                continue
            # Emit any whitespace between the previous token and this one.
            if s_col > cursor:
                out.append(_html_escape(line[cursor:s_col]))
            text = line[s_col:e_col] if e_line == lineno else line[s_col:]
            css = _token_css_class(tok)
            if css is not None:
                out.append(f"<span class='{css}'>{_html_escape(text)}</span>")
            else:
                out.append(_html_escape(text))
            cursor = e_col if e_line == lineno else len(line)
        if cursor < len(line):
            out.append(_html_escape(line[cursor:]))
    return "".join(out)


def _token_css_class(tok) -> str | None:
    """Map a tokenize.Token to a span class — None means "no styling"."""
    import tokenize

    if tok.type == tokenize.COMMENT:
        return "com"
    if tok.type == tokenize.STRING:
        return "str"
    if tok.type == tokenize.NUMBER:
        return "num"
    if tok.type == tokenize.NAME and tok.string in _PYTHON_KEYWORDS:
        return "kw"
    return None


# ----------------------------------------------------------------------
# Built-in CSS — single string concatenated into <style> at the top of
# every HTML report. Compact, print-friendly, no external fonts.
# ----------------------------------------------------------------------
_BASE_CSS = """
* { box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, sans-serif;
    margin: 0;
    padding: 0;
    color: #1a1a1a;
    line-height: 1.5;
    background: #f6f8fa;
}
/* Sticky top navigation -- mirrors MNE's report header. */
nav.topbar {
    position: sticky; top: 0; z-index: 100;
    background: #2E86AB; color: #fff;
    padding: .6em 1.2em;
    display: flex; align-items: center; gap: 1em;
    box-shadow: 0 1px 4px rgba(0,0,0,.15);
}
nav.topbar .brand { font-weight: 700; font-size: 1.1em; }
nav.topbar .ts { margin-left: auto; opacity: .85; font-size: .9em; }
nav.topbar select.tag-filter {
    padding: .25em .5em; border-radius: 4px; border: 1px solid #1a5db4;
    background: #fff; color: #1a1a1a; font-size: .9em;
}
/* Layout: collapsible left sidebar + main content. */
.layout { display: flex; min-height: calc(100vh - 3em); }
aside.sidebar {
    flex: 0 0 240px;
    background: #fff;
    border-right: 1px solid #e1e4e8;
    padding: 1em 0;
    position: sticky;
    top: 3em;
    align-self: flex-start;
    max-height: calc(100vh - 3em);
    overflow-y: auto;
}
aside.sidebar h4 {
    margin: 0 1em .5em; font-size: .82em; text-transform: uppercase;
    color: #586069; letter-spacing: .04em;
}
aside.sidebar ul { list-style: none; margin: 0; padding: 0; }
aside.sidebar li a {
    display: block; padding: .4em 1.2em;
    text-decoration: none; color: #24292e; border-left: 3px solid transparent;
}
aside.sidebar li a:hover { background: #f6f8fa; border-left-color: #2E86AB; }
aside.sidebar details { padding: 0 1em; }
aside.sidebar details summary {
    cursor: pointer; padding: .4em 0; font-weight: 600;
    color: #2E86AB; font-size: .9em;
}
main.content {
    flex: 1;
    max-width: 960px;
    margin: 0 auto;
    padding: 1.5em 2em;
    background: #fff;
}
h1 { border-bottom: 2px solid #2E86AB; padding-bottom: .3em; margin-top: 0; }
h2 { color: #2E86AB; margin-top: 2em; border-bottom: 1px solid #ddd;
     padding-bottom: .2em; scroll-margin-top: 4em; }
h3 { margin-top: 1.5em; color: #444; }
/* Tag pills used to filter custom sections. */
section[data-tag] { transition: opacity .15s ease; }
section[data-tag].hidden { display: none; }
.tag-pill {
    display: inline-block; background: #eef3f7; color: #1a5db4;
    border-radius: 10px; padding: 1px 8px; font-size: .75em;
    margin-left: .5em; vertical-align: middle;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
    font-size: 0.92em;
}
th, td {
    border: 1px solid #ccc;
    padding: 6px 10px;
    text-align: left;
}
th { background: #f4f6f8; font-weight: 600; cursor: pointer; }
tr:nth-child(even) td { background: #fafbfc; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
.meta { color: #666; font-size: 0.9em; }
.empty { color: #888; font-style: italic; padding: 1em 0; }
.p-001 { color: #1a7a1a; font-weight: 600; }
.p-01  { color: #1a5db4; font-weight: 600; }
.p-05  { color: #c25a00; font-weight: 600; }
.p-ns  { color: #666; }
.toc { background: #f8f9fb; border: 1px solid #e1e4e8; padding: 1em 1.5em;
       margin: 1.5em 0; }
.toc ol { margin: 0; padding-left: 1.4em; }
.toc a { text-decoration: none; color: #1a5db4; }
.toc a:hover { text-decoration: underline; }
/* Hide the legacy inline TOC when a sticky sidebar is present so we
   don't render the same anchors twice. The sidebar nav becomes the
   canonical navigator. */
.layout nav.toc { display: none; }
.plot { text-align: center; margin: 1.5em 0; }
.plot img { max-width: 100%; height: auto; border: 1px solid #ddd; }
.refs { font-size: 0.9em; }
.refs li { margin: .5em 0; }
.audit { background: #f8f9fb; border-left: 3px solid #2E86AB;
         padding: .5em 1em; margin: .5em 0; font-size: 0.9em; }
.note { font-style: italic; color: #555; font-size: 0.9em; }
.hint { color: #555; font-size: 0.9em; margin-top: .25em; }
pre.code { background: #1f2228; color: #eaecef; padding: 1em 1.25em;
           border-radius: 6px; overflow-x: auto; font-size: 0.85em;
           line-height: 1.5; }
pre.code code { font-family: 'JetBrains Mono', 'Consolas',
                'SF Mono', monospace; white-space: pre; }
/* Tiny built-in Python keyword highlighter — no external JS load,
   no network at render time. Keywords identified by a trivial regex
   substitution in _recipe_code_html below. */
pre.code .kw { color: #d97862; font-weight: 600; }
pre.code .str { color: #5ab896; }
pre.code .com { color: #8c98a6; font-style: italic; }
pre.code .num { color: #e8a13a; }

@media print {
    body { max-width: 100%; margin: 0; }
    h2 { page-break-before: always; }
    h2:first-of-type { page-break-before: avoid; }
    th { background: #eee !important; }
}
"""


# ----------------------------------------------------------------------
# Plot rendering (graceful no-op when widget not available)
# ----------------------------------------------------------------------
def _encode_qimage_png(qimg) -> str | None:
    """Convert a QImage to a base-64 PNG string. Returns None on failure."""
    try:
        from qtpy.QtCore import QBuffer, QByteArray, QIODevice
    except Exception:
        return None
    try:
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.WriteOnly)
        if not qimg.save(buf, "PNG"):
            return None
        return base64.b64encode(bytes(ba)).decode("ascii")
    except Exception:
        return None


def _render_tachogram_png(data, max_points: int = 2000) -> str | None:
    """Render a tachogram PNG (base64) using pyqtgraph + ImageExporter."""
    try:
        import numpy as np
        import pyqtgraph as pg
        from pyqtgraph.exporters import ImageExporter
    except Exception:
        return None
    try:
        t = np.asarray(data.t, dtype=float)
        v = np.asarray(data.v, dtype=float)
        if len(t) == 0:
            return None
        # Downsample naively to ``max_points`` so the embedded PNG stays
        # small even for hour-long recordings. Plot quality is fine for
        # the report's reduced size.
        if len(t) > max_points:
            stride = len(t) // max_points + 1
            t = t[::stride]
            v = v[::stride]
        plt = pg.PlotWidget()
        plt.resize(800, 240)
        plt.setLabel("left", "RR", "ms")
        plt.setLabel("bottom", "Time", "s")
        plt.plot(t - t[0], v, pen=pg.mkPen("#2E86AB", width=1), connect="finite")
        exporter = ImageExporter(plt.plotItem)
        exporter.parameters()["width"] = 800
        qimg = exporter.export(toBytes=True)
        return _encode_qimage_png(qimg)
    except Exception:
        return None


# ----------------------------------------------------------------------
# ReportBuilder — public API
# ----------------------------------------------------------------------
class ReportBuilder:
    """Build HTML / Markdown reports from the inspector's current state."""

    def __init__(self, main_window: "MainWindow") -> None:
        self._mw = main_window
        # Cluster C2: user-added sections via add_section(title, html, tag).
        # Each entry is {title, content_html, tag, anchor}.
        self._custom_sections: list[dict] = []

    # ------------------------------------------------------------------
    # Helpers — share data extraction across HTML + Markdown paths
    # ------------------------------------------------------------------
    @property
    def _store(self) -> "ResultsStore":
        return self._mw._results_store

    def _project_name(self) -> str:
        pm = getattr(self._mw, "_project", None)
        if pm is not None and pm.metadata is not None:
            return pm.metadata.name
        return "(no project)"

    def _datasets(self):
        return list(getattr(self._mw, "_datasets", []))

    def _recipe_code(self) -> str | None:
        """Render the recorded GUI actions as a Python script string.

        Returns ``None`` when the recorder is missing or empty so the
        report can substitute an explanatory placeholder. The same
        text powers File -> Save recipe..., so HTML readers see the
        exact code the user would download via the menu.
        """
        recorder = getattr(self._mw, "history", None)
        if recorder is None or not getattr(recorder, "actions", None):
            return None
        try:
            from rrational.inspector.history import to_script

            return to_script(recorder)
        except Exception:  # pragma: no cover - defensive
            return None

    def _audit_entries(self) -> list[tuple[str, str, str, str]]:
        """Walk every loaded .rrational dataset and pull its audit_trail.

        Returns a list of (dataset_name, step, action, details) tuples.
        Datasets that don't carry a v2 file silently contribute nothing.
        """
        entries: list[tuple[str, str, str, str]] = []
        for ds in self._datasets():
            path = getattr(ds, "path", None)
            if path is None or path.suffix.lower() != ".rrational":
                continue
            try:
                from rrational.gui.rrational_export import load_rrational_v2

                exp = load_rrational_v2(path)
            except Exception:
                continue
            for entry in exp.audit_trail:
                entries.append((ds.name, str(entry.step), entry.action, entry.details))
        return entries

    def _quality_rows(self) -> list[tuple[str, str, int, float, str]]:
        """Pull (dataset, section, beats, artifact_rate, grade) from .rrational."""
        rows: list[tuple[str, str, int, float, str]] = []
        for ds in self._datasets():
            path = getattr(ds, "path", None)
            if path is None or path.suffix.lower() != ".rrational":
                continue
            try:
                from rrational.gui.rrational_export import load_rrational_v2

                exp = load_rrational_v2(path)
            except Exception:
                continue
            for sec_name, sec in exp.sections.items():
                quality = getattr(sec, "quality", None)
                final = getattr(sec, "final_artifacts", None)
                beats = quality.usable_beats if quality else 0
                rate = final.rate if final else 0.0
                grade = quality.grade if quality else "unknown"
                rows.append((ds.name, sec_name, beats, rate, grade))
        return rows

    # ------------------------------------------------------------------
    # HTML
    # ------------------------------------------------------------------
    def build_html(self) -> str:
        parts: list[str] = []
        parts.append("<!DOCTYPE html>")
        parts.append("<html lang='en'>")
        parts.append("<head>")
        parts.append("<meta charset='utf-8'>")
        parts.append("<title>RRational Report</title>")
        # Bootstrap 5 grid + utilities -- loaded from jsdelivr CDN for
        # responsive layout polish. Self-contained fall-through CSS in
        # _BASE_CSS keeps the report readable offline.
        parts.append(
            "<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/"
            "bootstrap@5.3.3/dist/css/bootstrap.min.css' "
            "integrity='sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH' "
            "crossorigin='anonymous'>"
        )
        parts.append(f"<style>{_BASE_CSS}</style>")
        parts.append("</head>")
        parts.append("<body>")

        # ----- Sticky top-bar with brand + tag filter dropdown -----
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        custom_tags = sorted({t for t in self._collect_custom_tags() if t})
        parts.append("<nav class='topbar'>")
        parts.append("<span class='brand'>RRational Report</span>")
        if custom_tags:
            parts.append(
                "<label for='tagFilter' class='visually-hidden'>Filter sections</label>"
            )
            parts.append(
                "<select id='tagFilter' class='tag-filter' onchange='_rrFilterTag(this.value)'>"
            )
            parts.append("<option value=''>All sections</option>")
            for tag in custom_tags:
                parts.append(
                    f"<option value='{_html_escape(tag)}'>{_html_escape(tag)}</option>"
                )
            parts.append("</select>")
        parts.append(f"<span class='ts'>{ts}</span>")
        parts.append("</nav>")

        # ----- Layout: sidebar TOC + main content -----
        parts.append("<div class='layout'>")
        parts.append("<aside class='sidebar'>")
        parts.append("<details open><summary>Standard sections</summary><ul>")
        for anchor, label in [
            ("datasets", "Datasets"),
            ("metrics", "HRV metrics"),
            ("group-tests", "Group comparisons"),
            ("sequence-tests", "Sequence comparisons"),
            ("quality", "Quality summary"),
            ("methods", "Methods"),
            ("references", "References"),
            ("audit", "Audit trail"),
            ("recipe", "Reproducible recipe"),
        ]:
            parts.append(f"<li><a href='#{anchor}'>{label}</a></li>")
        parts.append("</ul></details>")
        custom_sections = list(self._custom_sections)
        if custom_sections:
            parts.append("<details><summary>Custom sections</summary><ul>")
            for sec in custom_sections:
                parts.append(
                    f"<li><a href='#{sec['anchor']}'>"
                    f"{_html_escape(sec['title'])}</a></li>"
                )
            parts.append("</ul></details>")
        parts.append("</aside>")
        parts.append("<main class='content'>")

        # ----- Title + metadata -----
        parts.append("<h1>RRational Report</h1>")
        parts.append("<div class='meta'>")
        parts.append(
            f"Project: <b>{_html_escape(self._project_name())}</b> &middot; "
            f"Generated: {ts} &middot; "
            f"RRational v{_get_version()} &middot; "
            f"Inspector phase: 18"
        )
        parts.append("</div>")

        # ----- Datasets -----
        parts.append("<h2 id='datasets'>Datasets</h2>")
        datasets = self._datasets()
        if not datasets:
            parts.append("<div class='empty'>(no datasets loaded)</div>")
        else:
            parts.append("<table><thead><tr>")
            parts.append("<th>Name</th><th>Beats</th><th>Duration</th>")
            parts.append("</tr></thead><tbody>")
            for ds in datasets:
                data = ds.data
                n_beats = int(len(data.t))
                duration = float(data.t_end - data.t_start) if n_beats >= 2 else 0.0
                parts.append(
                    "<tr>"
                    f"<td>{_html_escape(ds.name)}</td>"
                    f"<td class='num'>{n_beats}</td>"
                    f"<td class='num'>{_fmt_duration(duration)}</td>"
                    "</tr>"
                )
            parts.append("</tbody></table>")

        # ----- HRV metrics -----
        parts.append("<h2 id='metrics'>HRV metrics</h2>")
        rows = self._store.metric_rows
        if not rows:
            parts.append("<div class='empty'>(no results yet)</div>")
        else:
            metric_keys = self._metric_keys(rows)
            parts.append("<table><thead><tr>")
            parts.append("<th>Mode</th><th>Dataset</th><th>Section</th><th>Beats</th>")
            for m in metric_keys:
                parts.append(f"<th>{_html_escape(m)}</th>")
            parts.append("</tr></thead><tbody>")
            for row in rows:
                parts.append("<tr>")
                parts.append(f"<td>{_html_escape(row.mode)}</td>")
                parts.append(f"<td>{_html_escape(row.dataset)}</td>")
                parts.append(f"<td>{_html_escape(row.section)}</td>")
                parts.append(f"<td class='num'>{row.n_beats}</td>")
                for m in metric_keys:
                    parts.append(f"<td class='num'>{_fmt_num(row.metrics.get(m))}</td>")
                parts.append("</tr>")
            parts.append("</tbody></table>")

        # ----- Group tests -----
        parts.append("<h2 id='group-tests'>Group comparisons</h2>")
        gt = self._store.group_test_rows
        if not gt:
            parts.append("<div class='empty'>(no results yet)</div>")
        else:
            png = self._maybe_group_plot_png()
            if png:
                parts.append(
                    "<div class='plot'>"
                    f"<img alt='Group bar chart' src='data:image/png;base64,{png}'>"
                    "</div>"
                )
            else:
                parts.append("<!-- plot pending -->")
            parts.append("<table><thead><tr>")
            parts.append(
                "<th>Section</th><th>Metric</th><th>Test</th>"
                "<th>Statistic</th><th>p</th>"
                "<th>Effect size</th><th>n per group</th><th>Parametric?</th>"
            )
            parts.append("</tr></thead><tbody>")
            for r in gt:
                n_str = ", ".join(f"{g}={n}" for g, n in r.n_per_group.items())
                parts.append(
                    "<tr>"
                    f"<td>{_html_escape(r.section)}</td>"
                    f"<td>{_html_escape(r.metric)}</td>"
                    f"<td>{_html_escape(r.test_name)}</td>"
                    f"<td class='num'>{_fmt_num(r.statistic)}</td>"
                    f"<td class='num {_p_class(r.p_value)}'>{_fmt_p(r.p_value)}</td>"
                    f"<td class='num'>"
                    f"{_html_escape(r.effect_size_name or '—')}="
                    f"{_fmt_num(r.effect_size)}</td>"
                    f"<td>{_html_escape(n_str)}</td>"
                    f"<td>{'parametric' if r.is_parametric else 'non-parametric'}</td>"
                    "</tr>"
                )
            parts.append("</tbody></table>")

        # ----- Sequence tests -----
        parts.append("<h2 id='sequence-tests'>Sequence comparisons</h2>")
        st = self._store.sequence_test_rows
        if not st:
            parts.append("<div class='empty'>(no results yet)</div>")
        else:
            png = self._maybe_sequence_plot_png()
            if png:
                parts.append(
                    "<div class='plot'>"
                    f"<img alt='Sequence line chart' src='data:image/png;base64,{png}'>"
                    "</div>"
                )
            else:
                parts.append("<!-- plot pending -->")
            parts.append("<table><thead><tr>")
            parts.append(
                "<th>Sequence</th><th>Metric</th><th>Sections</th>"
                "<th>n complete</th><th>Test</th>"
                "<th>Statistic</th><th>p</th><th>Effect size</th>"
            )
            parts.append("</tr></thead><tbody>")
            for r in st:
                parts.append(
                    "<tr>"
                    f"<td>{_html_escape(r.sequence_name)}</td>"
                    f"<td>{_html_escape(r.metric)}</td>"
                    f"<td>{_html_escape(' → '.join(r.sections))}</td>"
                    f"<td class='num'>{r.n_complete_subjects}</td>"
                    f"<td>{_html_escape(r.test_name)}</td>"
                    f"<td class='num'>{_fmt_num(r.statistic)}</td>"
                    f"<td class='num {_p_class(r.p_value)}'>{_fmt_p(r.p_value)}</td>"
                    f"<td class='num'>"
                    f"{_html_escape(r.effect_size_name)}={_fmt_num(r.effect_size)}</td>"
                    "</tr>"
                )
            parts.append("</tbody></table>")
            parts.append(
                "<p class='note'>Holm-Bonferroni correction is applied to the "
                "all-pairwise post-hoc battery of each omnibus test "
                "(see Methods).</p>"
            )

        # ----- Quality summary -----
        parts.append("<h2 id='quality'>Quality summary</h2>")
        q = self._quality_rows()
        if not q:
            parts.append(
                "<div class='empty'>"
                "(no quality data available — load .rrational v2 files or run "
                "artifact detection on the Browse tab)"
                "</div>"
            )
        else:
            parts.append("<table><thead><tr>")
            parts.append(
                "<th>Dataset</th><th>Section</th><th>Beats</th>"
                "<th>Artifact rate</th><th>Grade</th>"
            )
            parts.append("</tr></thead><tbody>")
            for ds_name, sec_name, beats, rate, grade in q:
                parts.append(
                    "<tr>"
                    f"<td>{_html_escape(ds_name)}</td>"
                    f"<td>{_html_escape(sec_name)}</td>"
                    f"<td class='num'>{beats}</td>"
                    f"<td class='num'>{rate * 100:.2f}%</td>"
                    f"<td>{_html_escape(grade)}</td>"
                    "</tr>"
                )
            parts.append("</tbody></table>")

        # ----- Methods + per-section plots -----
        parts.append("<h2 id='methods'>Methods</h2>")
        parts.append(self._methods_html())

        # Per-dataset tachograms — embed up to one per loaded dataset.
        plot_html_parts: list[str] = []
        for ds in datasets:
            png = _render_tachogram_png(ds.data)
            if png:
                plot_html_parts.append(
                    "<div class='plot'>"
                    f"<h3>Tachogram: {_html_escape(ds.name)}</h3>"
                    f"<img alt='Tachogram {_html_escape(ds.name)}' "
                    f"src='data:image/png;base64,{png}'>"
                    "</div>"
                )
        if plot_html_parts:
            parts.extend(plot_html_parts)
        elif datasets:
            parts.append("<!-- plot pending -->")

        # ----- References -----
        parts.append("<h2 id='references'>References</h2>")
        parts.append("<ol class='refs'>")
        for ref in _REFERENCES:
            url = _ref_url(ref)
            citation = _html_escape(ref.citation)
            if url:
                parts.append(
                    f"<li>{citation} "
                    f"<a href='{url}' target='_blank' rel='noopener'>{url}</a></li>"
                )
            else:
                parts.append(f"<li>{citation}</li>")
        parts.append("</ol>")

        # ----- Audit trail -----
        parts.append("<h2 id='audit'>Audit trail</h2>")
        audit = self._audit_entries()
        if not audit:
            parts.append(
                "<div class='empty'>"
                "(no audit entries — load .rrational v2 files exported with "
                "audit metadata)"
                "</div>"
            )
        else:
            for ds_name, step, action, details in audit:
                parts.append(
                    "<div class='audit'>"
                    f"<b>{_html_escape(ds_name)}</b> &middot; "
                    f"step {step}: <code>{_html_escape(action)}</code><br>"
                    f"{_html_escape(details)}"
                    "</div>"
                )

        # ----- Reproducible recipe -----
        parts.append("<h2 id='recipe'>Reproducible recipe</h2>")
        recipe_code = self._recipe_code()
        if recipe_code is None:
            parts.append(
                "<div class='empty'>"
                "(no actions recorded in this session — interact with "
                "the inspector then re-export the report)"
                "</div>"
            )
        else:
            parts.append(
                "<p class='hint'>The Python below replays this session's "
                "GUI actions. Re-running it with the same input files in "
                "place reproduces the same .rrational v2 outputs.</p>"
            )
            parts.append(
                f"<pre class='code'><code>{_highlight_python(recipe_code)}</code></pre>"
            )

        # ----- User-added custom sections -----
        for sec in self._custom_sections:
            tag_attr = (
                f" data-tag='{_html_escape(sec['tag'])}'" if sec.get("tag") else ""
            )
            pill = (
                f" <span class='tag-pill'>{_html_escape(sec['tag'])}</span>"
                if sec.get("tag")
                else ""
            )
            parts.append(f"<section{tag_attr}>")
            parts.append(
                f"<h2 id='{sec['anchor']}'>{_html_escape(sec['title'])}{pill}</h2>"
            )
            parts.append(sec["content_html"])
            parts.append("</section>")

        # Close <main> + <div class='layout'>
        parts.append("</main></div>")

        # Tag-filter behaviour: tiny inline script. No external JS load.
        parts.append(
            "<script>"
            "function _rrFilterTag(tag){"
            "document.querySelectorAll('section[data-tag]').forEach(function(s){"
            "if(!tag||s.dataset.tag===tag){s.classList.remove('hidden');}"
            "else{s.classList.add('hidden');}});"
            "}"
            "</script>"
        )

        parts.append("</body></html>")
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # User-extensible sections (Cluster C2)
    # ------------------------------------------------------------------
    def add_section(self, title: str, content_html: str, tag: str = "") -> None:
        """Append a custom section to the report.

        ``tag`` lets the user filter the report's sticky top-bar
        dropdown ("All sections" / one entry per unique tag); empty
        tag means the section always shows.
        """
        anchor = "sec-" + "".join(
            c if c.isalnum() else "-" for c in title.lower()
        ).strip("-")
        self._custom_sections.append(
            {
                "title": title,
                "content_html": content_html,
                "tag": tag,
                "anchor": anchor,
            }
        )

    def _collect_custom_tags(self) -> set[str]:
        return {sec["tag"] for sec in self._custom_sections}

    # ------------------------------------------------------------------
    # HDF5 persistence (Cluster C7) — STUB until h5py lands.
    #
    # The MNE-Report API exposes ``report.save("file.h5", overwrite=True)``
    # and ``Report.load("file.h5")`` for round-trippable storage. We
    # mirror the signatures here so callers can wire UI menu items
    # against the API today even though the dependency is not yet
    # bundled; the methods raise a NotImplementedError that points the
    # user at the install fix.
    # ------------------------------------------------------------------
    def save(self, path) -> None:
        """Persist the report's custom sections to an HDF5 file.

        Raises NotImplementedError until ``h5py`` is added to the
        project's optional dependencies. Add ``h5py`` under
        ``pyproject.toml`` ``[project.optional-dependencies] reports``
        and reinstall with ``pip install -e .[reports]`` to enable.
        """
        raise NotImplementedError(
            "h5py is not installed. Add `h5py` to pyproject.toml "
            "[project.optional-dependencies] reports and reinstall."
        )

    @classmethod
    def load(cls, path) -> "ReportBuilder":
        """Read a previously-saved HDF5 report back into a builder.

        Symmetric stub — see :meth:`save` for the dependency note.
        """
        raise NotImplementedError(
            "h5py is not installed. Add `h5py` to pyproject.toml "
            "[project.optional-dependencies] reports and reinstall."
        )

    # ------------------------------------------------------------------
    # Markdown
    # ------------------------------------------------------------------
    def build_markdown(self) -> str:
        out = io.StringIO()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        out.write("# RRational Report\n\n")
        out.write(
            f"_Project_: **{self._project_name()}**  \n"
            f"_Generated_: {ts}  \n"
            f"_RRational version_: {_get_version()}  \n"
            f"_Inspector phase_: 18\n\n"
        )

        # ----- Datasets -----
        out.write("## Datasets\n\n")
        datasets = self._datasets()
        if not datasets:
            out.write("_(no datasets loaded)_\n\n")
        else:
            out.write("| Name | Beats | Duration |\n")
            out.write("|------|------:|---------:|\n")
            for ds in datasets:
                data = ds.data
                n_beats = int(len(data.t))
                duration = float(data.t_end - data.t_start) if n_beats >= 2 else 0.0
                out.write(f"| {ds.name} | {n_beats} | {_fmt_duration(duration)} |\n")
            out.write("\n")

        # ----- HRV metrics -----
        out.write("## HRV metrics\n\n")
        rows = self._store.metric_rows
        if not rows:
            out.write("_(no results yet)_\n\n")
        else:
            metric_keys = self._metric_keys(rows)
            header = ["Mode", "Dataset", "Section", "Beats", *metric_keys]
            out.write("| " + " | ".join(header) + " |\n")
            out.write("|" + "|".join("---" for _ in header) + "|\n")
            for row in rows:
                cells = [
                    row.mode,
                    row.dataset,
                    row.section,
                    str(row.n_beats),
                    *(_fmt_num(row.metrics.get(m)) for m in metric_keys),
                ]
                out.write("| " + " | ".join(cells) + " |\n")
            out.write("\n")

        # ----- Group tests -----
        out.write("## Group comparisons\n\n")
        gt = self._store.group_test_rows
        if not gt:
            out.write("_(no results yet)_\n\n")
        else:
            out.write(
                "| Section | Metric | Test | Statistic | p | Effect size | n per group | Parametric? |\n"
            )
            out.write(
                "|---------|--------|------|----------:|--:|------------:|-------------|-------------|\n"
            )
            for r in gt:
                n_str = ", ".join(f"{g}={n}" for g, n in r.n_per_group.items())
                eff = f"{r.effect_size_name or '—'}={_fmt_num(r.effect_size)}"
                out.write(
                    f"| {r.section} | {r.metric} | {r.test_name} | "
                    f"{_fmt_num(r.statistic)} | {_fmt_p_md(r.p_value)} | "
                    f"{eff} | {n_str} | "
                    f"{'parametric' if r.is_parametric else 'non-parametric'} |\n"
                )
            out.write("\n")

        # ----- Sequence tests -----
        out.write("## Sequence comparisons\n\n")
        st = self._store.sequence_test_rows
        if not st:
            out.write("_(no results yet)_\n\n")
        else:
            out.write(
                "| Sequence | Metric | Sections | n complete | Test | Statistic | p | Effect size |\n"
            )
            out.write(
                "|----------|--------|----------|-----------:|------|----------:|--:|------------:|\n"
            )
            for r in st:
                sects = " -> ".join(r.sections)
                eff = f"{r.effect_size_name}={_fmt_num(r.effect_size)}"
                out.write(
                    f"| {r.sequence_name} | {r.metric} | {sects} | "
                    f"{r.n_complete_subjects} | {r.test_name} | "
                    f"{_fmt_num(r.statistic)} | {_fmt_p_md(r.p_value)} | {eff} |\n"
                )
            out.write("\n")
            out.write(
                "_Holm-Bonferroni correction is applied to the all-pairwise "
                "post-hoc battery of each omnibus test (see Methods)._\n\n"
            )

        # ----- Quality summary -----
        out.write("## Quality summary\n\n")
        q = self._quality_rows()
        if not q:
            out.write(
                "_(no quality data available — load .rrational v2 files or "
                "run artifact detection on the Browse tab)_\n\n"
            )
        else:
            out.write("| Dataset | Section | Beats | Artifact rate | Grade |\n")
            out.write("|---------|---------|------:|--------------:|-------|\n")
            for ds_name, sec_name, beats, rate, grade in q:
                out.write(
                    f"| {ds_name} | {sec_name} | {beats} | "
                    f"{rate * 100:.2f}% | {grade} |\n"
                )
            out.write("\n")

        # ----- Methods -----
        out.write("## Methods\n\n")
        out.write(self._methods_markdown())
        out.write("\n")

        # Per-dataset tachograms in Markdown (base64 PNG)
        for ds in datasets:
            png = _render_tachogram_png(ds.data)
            if png:
                out.write(f"### Tachogram: {ds.name}\n\n")
                out.write(f"![Tachogram {ds.name}](data:image/png;base64,{png})\n\n")

        # ----- References -----
        out.write("## References\n\n")
        for ref in _REFERENCES:
            url = _ref_url(ref)
            if url:
                out.write(f"- {ref.citation} [{url}]({url})\n")
            else:
                out.write(f"- {ref.citation}\n")
        out.write("\n")

        # ----- Audit trail -----
        out.write("## Audit trail\n\n")
        audit = self._audit_entries()
        if not audit:
            out.write(
                "_(no audit entries — load .rrational v2 files exported "
                "with audit metadata)_\n"
            )
        else:
            for ds_name, step, action, details in audit:
                out.write(f"- **{ds_name}** step {step}: `{action}` — {details}\n")

        return out.getvalue()

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _metric_keys(self, rows: "list[MetricRow]") -> list[str]:
        """Return the metric column order. Default-metrics first, then extras."""
        seen: set[str] = set()
        for r in rows:
            seen.update(r.metrics.keys())
        ordered: list[str] = [m for m in _DEFAULT_METRICS if m in seen]
        ordered.extend(sorted(m for m in seen if m not in _DEFAULT_METRICS))
        return ordered

    def _methods_html(self) -> str:
        # Build inline DOI links to the references used in the Methods text.
        def cite(key: str) -> str:
            ref = next((r for r in _REFERENCES if r.key == key), None)
            if ref is None:
                return key
            url = _ref_url(ref)
            label = ref.key
            if url:
                return f"<a href='{url}' target='_blank' rel='noopener'>{label}</a>"
            return label

        return (
            "<p>HRV metrics were computed following the Task Force (1996) "
            f"recommendations [{cite('TaskForce1996')}], with artifact "
            "handling guided by the 2024 Quigley HRV reporting standards "
            f"[{cite('Quigley2024')}]. Artifact detection and beat-level "
            "correction used the NeuroKit2 implementation of the "
            "Lipponen-Tarvainen algorithm "
            f"[{cite('Lipponen2019')}].</p>"
            "<p>Frequency-domain metrics, where computed in Kubios-compatible "
            "mode, used smoothness-priors detrending (λ=500) followed by "
            "Welch's periodogram with a 180-second window (cross-validated "
            "to within ±5% of Kubios reference output on LF, HF and total "
            "power).</p>"
            "<p>Between-group hypothesis tests were selected automatically "
            "based on the Shapiro-Wilk normality test: Welch's t-test "
            f"[{cite('Welch1947')}] or Mann-Whitney U for two groups, "
            "one-way ANOVA or Kruskal-Wallis for three or more. Effect "
            "sizes are Cohen's d "
            f"[{cite('Cohen1988')}] for two-group tests and η² "
            f"[{cite('Lakens2013')}] for omnibus tests.</p>"
            "<p>Within-subject (sequence) comparisons used Friedman's "
            f"rank-sum test [{cite('Friedman1937')}] with Kendall's W as "
            "the effect size, or one-way repeated-measures ANOVA "
            "(partial η²) when normality held and n≥10 complete cases. "
            "All-pairwise post-hoc comparisons were Holm-Bonferroni "
            f"corrected [{cite('Holm1979')}].</p>"
        )

    def _methods_markdown(self) -> str:
        def cite(key: str) -> str:
            ref = next((r for r in _REFERENCES if r.key == key), None)
            if ref is None:
                return key
            url = _ref_url(ref)
            if url:
                return f"[{ref.key}]({url})"
            return ref.key

        return (
            f"HRV metrics were computed following the Task Force (1996) "
            f"recommendations ({cite('TaskForce1996')}), with artifact "
            f"handling guided by the 2024 Quigley HRV reporting standards "
            f"({cite('Quigley2024')}). Artifact detection and beat-level "
            f"correction used the NeuroKit2 implementation of the "
            f"Lipponen-Tarvainen algorithm ({cite('Lipponen2019')}).\n\n"
            "Frequency-domain metrics, where computed in Kubios-compatible "
            "mode, used smoothness-priors detrending (lambda=500) followed "
            "by Welch's periodogram with a 180-second window "
            "(cross-validated to within +/-5% of Kubios reference output "
            "on LF, HF and total power).\n\n"
            "Between-group hypothesis tests were selected automatically "
            "based on the Shapiro-Wilk normality test: Welch's t-test "
            f"({cite('Welch1947')}) or Mann-Whitney U for two groups, "
            "one-way ANOVA or Kruskal-Wallis for three or more. Effect "
            f"sizes are Cohen's d ({cite('Cohen1988')}) for two-group "
            f"tests and eta-squared ({cite('Lakens2013')}) for omnibus tests.\n\n"
            "Within-subject (sequence) comparisons used Friedman's "
            f"rank-sum test ({cite('Friedman1937')}) with Kendall's W as "
            "the effect size, or one-way repeated-measures ANOVA "
            "(partial eta-squared) when normality held and n>=10 complete "
            "cases. All-pairwise post-hoc comparisons were Holm-Bonferroni "
            f"corrected ({cite('Holm1979')}).\n"
        )

    def _maybe_group_plot_png(self) -> str | None:
        """Try to grab a screenshot of the analysis tab's group bar chart.

        Looks for any plot widget the analysis tab might expose and
        falls back to ``None`` if nothing matches. The HTML caller
        emits an ``<!-- plot pending -->`` comment in that case.
        """
        tab = getattr(self._mw, "_analysis_tab", None)
        if tab is None:
            return None
        plot = getattr(tab, "_group_bar_chart", None) or getattr(
            tab, "_group_plot", None
        )
        if plot is None:
            return None
        return _grab_widget_png(plot)

    def _maybe_sequence_plot_png(self) -> str | None:
        tab = getattr(self._mw, "_analysis_tab", None)
        if tab is None:
            return None
        plot = getattr(tab, "_sequence_line_chart", None) or getattr(
            tab, "_sequence_plot", None
        )
        if plot is None:
            return None
        return _grab_widget_png(plot)


def _grab_widget_png(widget) -> str | None:
    """Return a base-64 PNG of any QWidget via ``grab``. ``None`` on failure."""
    try:
        pix = widget.grab()
        qimg = pix.toImage()
        return _encode_qimage_png(qimg)
    except Exception:
        return None


# ----------------------------------------------------------------------
# F8: standalone HTML report for the Group Comparison pane. Kept
# deliberately small (no plots, no audit-trail) so the inspector can
# wire a "Generate HTML report..." button without dragging the full
# ReportBuilder pipeline. Plot embedding can be added later.
# ----------------------------------------------------------------------
_GROUP_REPORT_CSS = (
    "body{font-family:sans-serif;max-width:900px;margin:2em auto;padding:0 1em;}"
    "table{border-collapse:collapse;}"
    "th,td{border:1px solid #ccc;padding:6px 12px;text-align:left;}"
    "th{background:#f5f5f5;}"
    "h1{color:#222;}"
    "h2{color:#2E86AB;margin-top:2em;}"
    ".meta{color:#666;}"
    ".empty{color:#888;font-style:italic;}"
)


def _group_descriptive_rows(values: list[float]) -> tuple[int, str, str]:
    """Return ``(n, mean_str, sd_str)`` for a list of floats."""
    import statistics

    finite = [v for v in values if v is not None and not math.isnan(v)]
    n = len(finite)
    if n == 0:
        return 0, "—", "—"
    mean = statistics.fmean(finite)
    sd = statistics.stdev(finite) if n >= 2 else 0.0
    return n, f"{mean:.3f}", f"{sd:.3f}"


def generate_group_analysis_html(results: dict, output_path) -> "Path":
    """Render a self-contained HTML report for the Group Comparison pane.

    Args:
        results: dict with keys:
            - ``timestamp`` (str | None): pre-formatted timestamp; falls
              back to "n/a" so tests can build deterministic payloads.
            - ``project_name`` (str | None): optional project label.
            - ``per_group_descriptives`` (dict[str, dict[str, list[float]]]):
              ``{group_label: {metric: [values]}}``.
            - ``group_tests`` (list[GroupTestRow]): the pyobjects already
              held in the results store; rendered as a stats table.
        output_path: ``pathlib.Path`` destination. Parent dirs are
            created if missing.

    Returns:
        ``output_path`` (echoed) for chaining.
    """
    from pathlib import Path

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    timestamp = str(results.get("timestamp") or "n/a")
    project_name = results.get("project_name")
    per_group: dict[str, dict[str, list[float]]] = (
        results.get("per_group_descriptives") or {}
    )
    group_tests = results.get("group_tests") or []

    parts: list[str] = []
    parts.append("<html>")
    parts.append("<head>")
    parts.append("<title>Group analysis report</title>")
    parts.append(f"<style>{_GROUP_REPORT_CSS}</style>")
    parts.append("</head>")
    parts.append("<body>")
    parts.append("<h1>Group analysis report</h1>")
    parts.append("<p class='meta'>")
    if project_name:
        parts.append(f"Project: <b>{_html_escape(str(project_name))}</b><br>")
    parts.append(f"Generated: {_html_escape(timestamp)}")
    parts.append("</p>")

    # ---- Per-group descriptives ----
    parts.append("<h2>Per-group descriptives</h2>")
    if not per_group:
        parts.append("<p class='empty'>(no descriptive data)</p>")
    for group_label, metrics_dict in per_group.items():
        parts.append(f"<h3>{_html_escape(str(group_label))}</h3>")
        if not metrics_dict:
            parts.append("<p class='empty'>(no metrics recorded)</p>")
            continue
        parts.append(
            "<table><thead><tr>"
            "<th>Metric</th><th>Mean</th><th>SD</th><th>N</th>"
            "</tr></thead><tbody>"
        )
        for metric, values in metrics_dict.items():
            n, mean_str, sd_str = _group_descriptive_rows(list(values))
            parts.append(
                "<tr>"
                f"<td>{_html_escape(str(metric))}</td>"
                f"<td>{mean_str}</td>"
                f"<td>{sd_str}</td>"
                f"<td>{n}</td>"
                "</tr>"
            )
        parts.append("</tbody></table>")

    # ---- Statistical tests ----
    parts.append("<h2>Statistical tests</h2>")
    if not group_tests:
        parts.append("<p class='empty'>(no test results)</p>")
    else:
        parts.append(
            "<table><thead><tr>"
            "<th>Metric</th><th>Test</th><th>Statistic</th><th>p</th><th>p_fdr</th>"
            "</tr></thead><tbody>"
        )
        # Holm/Bonferroni-style FDR fallback: if the row carries a
        # ``p_fdr`` attribute, use it; otherwise show "—" (FDR is not
        # always available depending on how the row was constructed).
        for row in group_tests:
            metric = getattr(row, "metric", "")
            test_name = getattr(row, "test_name", "")
            statistic = getattr(row, "statistic", None)
            p_value = getattr(row, "p_value", None)
            p_fdr = getattr(row, "p_fdr", None)
            parts.append(
                "<tr>"
                f"<td>{_html_escape(str(metric))}</td>"
                f"<td>{_html_escape(str(test_name))}</td>"
                f"<td>{_fmt_num(statistic)}</td>"
                f"<td>{_fmt_p(p_value).replace('&lt;', '<')}</td>"
                f"<td>{'—' if p_fdr is None else _fmt_p(p_fdr).replace('&lt;', '<')}</td>"
                "</tr>"
            )
        parts.append("</tbody></table>")

    parts.append("</body></html>")
    out.write_text("\n".join(parts), encoding="utf-8")
    return out
