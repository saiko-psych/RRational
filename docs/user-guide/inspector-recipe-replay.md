# Inspector Recipe Export + Replay

RRational silently records every user action in the inspector
(load, detect artifacts, add annotations, run analyses, export)
as a **recipe**: a structured list of API calls that re-creates
the same session deterministically.

---

## What is a recipe?

A recipe is a runnable Python file — a sequence of calls into
the `rrational` library — that, when executed, reproduces the
end state of an inspector session: the same data loaded, the
same artifact corrections applied, the same annotations placed,
the same exports written.

### Use cases

- **Reproducibility audits** — share a single `.py` file with
  reviewers; they re-run it on the original data to verify your
  analysis.
- **Batch processing** — adapt one recipe to iterate over many
  recordings without clicking through the GUI for each.
- **Lab documentation** — store recipes alongside a study's data
  so future students can replay the canonical pre-processing.
- **Collaborator handoff** — send a colleague a recipe instead of
  a screen-recording or written walkthrough.

---

## Recording — implicit

You do not need to start or stop recording. The inspector wires
each user-facing mutation through a single dispatcher that:

1. Performs the action (loads the file, detects artifacts, etc.).
2. Appends a `RecipeStep` to the in-memory action log.
3. Refreshes the UI.

Closing a dataset, switching tabs, panning the plot, hovering the
HUD, and other view-only operations are **not** recorded — only
state-changing actions are.

---

## Saving via File → Save recipe…

When you are ready to export:

1. Open the **File** menu.
2. Choose *Save recipe…*.
3. Pick a destination (default: project root, suggested filename
   `rrational_recipe.py`).
4. Click **Save**.

The exporter walks the action log, renders each step as a
`rrational.*` call, and writes a single self-contained Python
script:

```python
"""RRational recipe — auto-generated, replay with: python recipe.py"""
from pathlib import Path
import rrational as rr

project = rr.Project.open(Path(r"C:/path/to/project"))
ds = project.load_recording(Path(r"C:/path/to/recording.csv"))
ds = ds.detect_artifacts(method="lipponen2019")
ds = ds.add_exclusion(start=120.5, end=135.2, reason="motion")
result = ds.compute_hrv(section="baseline_rest", preset="time-domain")
result.export_csv(Path("results/baseline.csv"))
```

The header carries the RRational version + export timestamp so a
future replay knows which library version produced the recipe.

---

## Replaying with `python recipe.py`

From a shell in any environment with the same RRational version
installed:

```sh
python rrational_recipe.py
```

The script runs end-to-end, producing the same artifacts the GUI
session produced. No GUI is launched — the recipe targets the
underlying API directly.

For batch use, wrap the recipe in a loop:

```python
for rec_path in Path("data/").glob("*.csv"):
    ds = project.load_recording(rec_path)
    ds = ds.detect_artifacts(method="lipponen2019")
    # … etc, factored out of the original recipe
```

---

## Limitations

- **Path dependencies** — recipes hard-code the project + data
  paths from the original session. Move or rename inputs and you
  must edit the recipe before replay.
- **Random state** — actions that depend on RNG seeding (e.g.
  bootstrap CIs) are reproducible only if you set the seed
  identically. RRational seeds deterministically when run via the
  CLI; replay results may vary slightly otherwise.
- **GUI-only state is not exported** — palette choice, dock
  layout, zoom level, etc. live in your local preferences, not
  in the recipe.
- **External tool versions** — if your recipe depends on a
  specific NeuroKit2 / MNE version, pin those in your environment
  for byte-exact replay.

---

## See also

- [Inspector Feature Reference](inspector-features.md) — File
  menu layout and where Save recipe… sits.
- [Inspector BIDS Workflow](inspector-bids-workflow.md) — recipe
  export pairs naturally with BIDS-physio export for shareable
  analysis bundles.
