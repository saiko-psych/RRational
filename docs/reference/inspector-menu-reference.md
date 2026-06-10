# Inspector Menu Reference

A complete reference for every menu item, dialog, and side-panel
control in the **RRational Inspector**. Skim it as a manual or use
`Ctrl+F` to find a specific action.

For the higher-level feature reference see
[Inspector features](../user-guide/inspector-features.md). For task
recipes see [Inspector workflows](../user-guide/inspector-workflows.md).

---

## File menu

| Item | Action |
|------|--------|
| New project… | Create a new project folder with the standard layout |
| Open project… | Open an existing project folder |
| Open recent project | Submenu of recently opened projects |
| Open recent file | Submenu of recently loaded `.rrational` files |
| Save | Save the active dataset as `.rrational` v2 |
| Save as… | Save the active dataset to a new path |
| Export report (HTML) | Render the project's results as an HTML report with embedded plots |
| Export report (Markdown) | Same as above but Markdown output |
| Quit | Exit the application |

Notes:

- The `.rrational` v2 format embeds raw RR + correction metadata +
  exclusion ranges + annotations in a single file.
- HTML and Markdown reports embed DOI-linked references and the
  reproducible-recipe block introduced in Round 14.

---

## Edit menu

| Item | Shortcut | Action |
|------|----------|--------|
| Undo manual mark | `Ctrl+Z` | Reverse the last manual artifact mark / unmark |
| Redo manual mark | `Ctrl+Y` / `Cmd+Shift+Z` | Re-apply the last undone mark |
| Preferences… | `Ctrl+,` | Open the Preferences dialog (color scheme, defaults) |

### Preferences dialog

| Section | Controls |
|---------|----------|
| Color scheme | Palette dropdown (Okabe-Ito / Viridis / Custom) + hex inputs |
| Help system | "Always show help expanders" checkbox |
| Defaults | Default zoom preset on file open, default mode (browse / annotate) |

Color-scheme changes apply immediately to every open plot.

---

## View menu

### Side panels

| Item | Default | Notes |
|------|---------|-------|
| Show sidebar | On | Workspace tree + dataset list |
| Show overview bar | On | Reduced-scale recording strip below the plot |
| Show Datasets panel | On | Dockable BrowseTab side dock |
| Show Preprocessing panel | On | Dockable BrowseTab side dock |
| Show Info panel | On | Right-side metadata dock |

### Plot overlays

| Item | Shortcut | Default | Notes |
|------|----------|---------|-------|
| Show section bands | `S` | On | Colored bands for defined sections |
| Show event markers | `V` | On | Vertical lines at every event |
| Show grid | `G` | On | Plot grid lines |
| Show crosshair | `C` | Off | Vertical reference line at cursor |
| Show HUD readout | `H` | On | Top-right `t / RR / HR` panel |
| Zen mode | `Z` | Off | Hide HUD + crosshair in one stroke |

### Layout submenu

| Item | Notes |
|------|-------|
| Streamlit mode | Data / Participant / Setup / Analysis / Results tabs |
| MNE-LAB mode | Browse / Setup / Analysis / Results, dock-heavy |

The two modes are mutually exclusive; the active mode persists across
sessions.

---

## Tools menu

### Import from… submenu

| Item | File filter |
|------|-------------|
| Polar (CSV)… | `*.csv` |
| Empatica (CSV)… | `*.csv` |
| Kubios (TXT)… | `*.txt` |
| Elite HRV (CSV)… | `*.csv` |
| Plain text (TXT/DAT)… | `*.txt *.dat` |

### Visualisation

| Item | Action |
|------|--------|
| Tachogram… | Open a tachogram (RR vs beat) of the active dataset |
| Poincare plot… | Open a Poincare plot of the active dataset |
| PSD plot… | Open a power spectral density plot |
| HR distribution… | Heart-rate histogram + KDE |
| Compare HRV curves… | Cross-dataset overlay with bootstrap CI |

All five actions become enabled only when at least one dataset is
loaded.

### Annotations and quality

| Item | Action |
|------|--------|
| Annotations… | Open the cross-recording annotation table (sort/filter/CSV) |
| Run preprocessing on all loaded recordings… | Batch Lipponen detector + save `.rrational` v2 |
| Quality triage… | Open the quality-triage dashboard for the loaded set |

### Export

| Item | Output |
|------|--------|
| Export to BIDS-physio… | TSV.GZ + JSON sidecar per active dataset |
| Export to PRISM biometrics… | TSV + JSON sidecar with HRV summary metrics for PRISM Studio |

---

## Help menu

| Item | Action |
|------|--------|
| Workflow walkthrough… | Open the 11-page wizard |
| Welcome… | Re-open the first-launch welcome dialog |
| Keyboard shortcuts (F1) | Open the shortcut reference |
| About RRational… | Version + license + dependency list |
| Report a bug… | Open the project's GitHub issue tracker |

---

## Compare HRV curves dialog

Opened via `Tools → Compare HRV curves…`.

| Control | Purpose |
|---------|---------|
| Group A dataset list | Checkboxes for every loaded recording |
| Group B dataset list | Optional — leave empty for single-group overlay |
| Confidence level (%) | Bootstrap CI level, default 95 |
| Number of bootstrap iterations | Default 1000 |
| Random seed | Optional — set for reproducibility |
| Plot button | Render the overlay in a new window |
| Cancel button | Close without plotting |

The output window has:

- Mean curves (one per group) with bootstrap CI bands.
- Toolbar for save-as-PNG, copy-to-clipboard, and re-fit.

---

## Sidebar elements

### Workspace tree

The left sidebar's tree mirrors the project folder structure. Each
dataset row shows two small badges:

- **Artifact count** — number of detected artifacts after correction.
- **Annotation count** — number of saved annotations.

Hover any row for the full file path tooltip. Right-click for a
context menu (rename, exclude, reveal in file explorer).

### Info dock

The right-side dock shows metadata for the currently active dataset:

| Field | Source |
|-------|--------|
| Participant | Dataset metadata or filename stem |
| Group | Setup tab → Groups pane |
| Sequence | Setup tab → Sequences pane |
| Beats | Loaded RR count |
| Duration | Sum of RR intervals (mm:ss) |
| Duplicates | Count of duplicate timestamps detected at load |
| Notes | Free-text field, persisted per recording |

Toggle via `View → Show Info panel`.

---

## Status bar reference

The bottom status bar has three slots:

| Slot | Content |
|------|---------|
| Left | Project badge (click to switch projects) |
| Center | Tab-specific hint (e.g. "Choose a metric preset to begin") |
| Right | Active dataset name + section count |

Context hints change on every tab switch and persist for ~10 seconds
after a manual action (e.g. "Saved 3 datasets").

---

## Full keyboard shortcuts reference

See the dedicated cheat sheet:
[Inspector keyboard shortcuts](../user-guide/inspector-keyboard-shortcuts.md).

The most-used keys at a glance:

| Key | Action |
|-----|--------|
| `R` | Reset zoom to full recording |
| `1` / `2` / `3` | Last 1 min / 10 min / full |
| `←` / `→` | Pan 25% of visible window |
| `↑` / `↓` | Zoom out / in |
| `Home` / `End` | First / last 60 s |
| `A` | Annotation mode |
| `E` | Exclusion mode |
| `H` | HUD readout |
| `C` | Crosshair |
| `Z` | Zen mode |
| `F1` | Keyboard reference |

---

## See also

- [Inspector features](../user-guide/inspector-features.md)
- [Inspector workflows](../user-guide/inspector-workflows.md)
- [Inspector keyboard shortcuts](../user-guide/inspector-keyboard-shortcuts.md)
- [Inspector standalone app](../getting-started/inspector.md)
