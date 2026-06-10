"""Multi-participant tachogram grid (Cluster C3).

Builds a compact NxM grid of mini-tachograms — one per loaded dataset
— so the user can eyeball every recording's overall shape at once.
Inspired by ``mne.viz.plot_topomap`` grids and most clinical-HRV
dashboards.

Layout: pyqtgraph's ``GraphicsLayoutWidget`` packs ``PlotItem``s into
a row/col grid without per-cell window chrome, so 20 mini-plots fit
comfortably without overlapping. Axes are hidden; subject ID and
mean-HR badge are rendered as ``TextItem`` overlays in the top corners
so the cells stay self-describing at thumbnail scale.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pyqtgraph as pg
from qtpy.QtGui import QColor

# Cell footprint matches the brief: 220x140 px nominal. Round 16 — we
# hand pyqtgraph a FIXED max as well as a min so that workspaces with
# n < n_cols datasets don't stretch each cell across the whole row
# (the previous min-only contract let a single dataset blow up into a
# full-width flat tachogram).
_CELL_W = 220
_CELL_H = 140
# Tachogram line — sky-blue to stay neutral against the Okabe-Ito
# palette and not collide with stress-bands the user might overlay.
_LINE_COLOR = "#2E86AB"
# Round 16 — subject-ID badge was barely legible at thumbnail scale.
# Promote to a bold white-on-translucent-dark fill so it stays readable
# on top of both light and dark cell backgrounds.
_BADGE_COLOR = "#ffffff"
_BADGE_BG = (24, 26, 30, 220)
_HR_BADGE_COLOR = "#1a1a1a"
_HR_BADGE_BG = (255, 255, 255, 220)
# Subject-ID label font (top-left). 12pt bold is comfortably readable at
# the 220x140 thumbnail footprint without dominating the tachogram.
_ID_FONT_PT = 12


class ParticipantGridWidget(pg.GraphicsLayoutWidget):
    """N-column grid of mini-tachograms with subject + mean-HR badges."""

    def __init__(self, n_cols: int = 4, parent=None) -> None:
        super().__init__(parent)
        # Background defers to the global pyqtgraph config (dark/light theme).
        self._n_cols = max(1, int(n_cols))
        # Keep cell handles so we can pop them on clear/reset.
        self._cells: list[pg.PlotItem] = []
        # Public callback hook — the host sets ``on_subject_click`` to
        # a ``(subject_id) -> None`` to delegate the cell click to the
        # main tachogram dialog. Default is a no-op.
        self.on_subject_click = lambda _subject_id: None

    # ------------------------------------------------------------------
    # Data population
    # ------------------------------------------------------------------
    def set_datasets(
        self, datasets: Sequence[tuple[str, np.ndarray, np.ndarray]]
    ) -> None:
        """Render one cell per ``(subject_id, t, rr_ms)`` triplet.

        ``t`` is in seconds (absolute or relative — only its span is
        used). ``rr_ms`` is the per-beat RR in milliseconds (NaN gaps
        OK; rendered with ``connect='finite'``).
        """
        # Local import — bundling QFont at module level invites
        # formatters to delete it (no other top-level use). Kept inside
        # the populate routine where it's load-bearing.
        from qtpy.QtGui import QFont

        self.clear()
        self._cells = []
        if not datasets:
            return

        id_font = QFont()
        id_font.setPointSize(_ID_FONT_PT)
        id_font.setBold(True)

        n = len(datasets)
        for i, (subject_id, t, rr) in enumerate(datasets):
            row, col = divmod(i, self._n_cols)
            plot = self.addPlot(row=row, col=col)
            # Round 16 — fix cell footprint to the nominal 220x140 so
            # workspaces with n < n_cols don't stretch each cell across
            # the whole row. Cap with setMaximumWidth/Height; the
            # PARTICIPANT GRID is meant to look like a contact-sheet of
            # uniform thumbnails, not a full-width tachogram.
            plot.setMinimumSize(_CELL_W, _CELL_H)
            plot.setMaximumWidth(_CELL_W * 2)
            plot.setMaximumHeight(_CELL_H * 2)
            plot.hideAxis("bottom")
            plot.hideAxis("left")
            plot.setMouseEnabled(x=False, y=False)
            plot.setMenuEnabled(False)
            plot.showGrid(x=False, y=False)

            t_arr = np.asarray(t, dtype=float)
            rr_arr = np.asarray(rr, dtype=float)
            if len(t_arr) > 0:
                plot.plot(
                    t_arr - t_arr[0],
                    rr_arr,
                    pen=pg.mkPen(_LINE_COLOR, width=1),
                    connect="finite",
                )

            # Subject-ID label (top-left). Round 16 — bumped font size +
            # bold + filled background so the ID stays readable against
            # both light and dark tachogram backgrounds.
            id_item = pg.TextItem(
                subject_id,
                anchor=(0, 0),
                color=_BADGE_COLOR,
                fill=QColor(*_BADGE_BG),
            )
            id_item.setFont(id_font)
            id_item.setPos(0, 0)
            plot.addItem(id_item)

            # Mean-HR badge (top-right). Converts mean RR -> mean HR.
            finite = rr_arr[np.isfinite(rr_arr)]
            if finite.size:
                mean_hr = 60_000.0 / float(np.mean(finite))
                badge = pg.TextItem(
                    f"{mean_hr:.0f} bpm",
                    anchor=(1, 0),
                    color=_HR_BADGE_COLOR,
                    fill=QColor(*_HR_BADGE_BG),
                )
                # Pin to right edge — we use ViewBox coordinates via
                # the plot range; setting after data plot means
                # autoRange has resolved a sensible x-extent. Use *args
                # rather than fixed positional names because pyqtgraph's
                # sigRangeChanged emits (viewbox, ranges) OR (viewbox,
                # ranges, changed_axes) depending on version — a fixed
                # signature lets the third arg overwrite our default
                # ``b=badge`` and pass a list into setPos.
                vb = plot.getViewBox()
                vb.sigRangeChanged.connect(
                    lambda *_args, b=badge, p=plot: _pin_top_right(b, p)
                )
                plot.addItem(badge)
                _pin_top_right(badge, plot)

            # Click-to-zoom: capture the subject_id in default-arg so
            # the lambda doesn't close over the loop variable.
            plot.scene().sigMouseClicked.connect(
                lambda _ev, sid=subject_id: self.on_subject_click(sid)
            )
            self._cells.append(plot)

        # Round 16 — left-pin the row when n < n_cols. Without a stretch
        # spacer on the right, pyqtgraph's GraphicsLayout stretches the
        # populated cells to fill the entire row (visible at n=1 as a
        # single full-width band). Add an empty graphics item with a
        # column-stretch hint to consume the slack.
        last_row = (n - 1) // self._n_cols if n else 0
        empty_cols = self._n_cols - (n - last_row * self._n_cols)
        if empty_cols > 0:
            # nextRow() ensures the spacer doesn't bleed into a later
            # added cell — but we have none here, so simply add to the
            # last row, columns n..n_cols-1, as zero-content items.
            for c in range(empty_cols):
                placeholder = self.addLabel(
                    "",
                    row=last_row,
                    col=(n - last_row * self._n_cols) + c,
                )
                # Set fixed width so the placeholder doesn't expand;
                # combined with the cell maxWidth above this keeps the
                # populated cells at their nominal footprint.
                placeholder.setFixedWidth(_CELL_W)


def _pin_top_right(item: pg.TextItem, plot: pg.PlotItem) -> None:
    """Reposition a TextItem to the top-right corner of a PlotItem's view.

    ``ViewBox.viewRange()`` returns ``[[x_lo, x_hi], [y_lo, y_hi]]`` —
    two nested lists, not a tuple. The previous unpacking treated the
    outer container as a (xtuple, ytuple) tuple and then indexed the
    INNER as if it were a TextItem (chained method-resolution failure
    that surfaced as ``'list' object has no attribute 'setPos'`` when
    ``item`` got swapped for ``x_range`` in the signal callback).
    """
    vb = plot.getViewBox()
    rng = vb.viewRange()
    x_hi = float(rng[0][1])
    y_hi = float(rng[1][1])
    item.setPos(x_hi, y_hi)
