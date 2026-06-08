"""Analysis tab — HRV-metric computation modes.

Provides RRational's four analysis modes:

- **Single Participant**: pick a dataset + section, get HRV metrics for
  that one segment
- **Repeating Section**: pick a section name, get the same metrics
  computed across every loaded dataset that has that section (e.g.
  "rest_pre" across all subjects)
- **Group Comparison** + **Sequence**: aggregate views with per-mode
  result tables and pop-up plot dialogs.

A per-tab settings bar at the top exposes the metric preset dropdown,
a per-metric checkbox grid (mirrors ``HRV_METRICS_CATALOG``), a
frequency-domain pipeline radio (NeuroKit2 default vs Kubios), and an
overlapping-window panel (beats or seconds with configurable
window/step). All persist via QSettings under the ``analysis_*`` keys.

Per-metric rows in the result tables get a yellow tint + tooltip when
the analysed segment falls below ``MIN_BEATS_TIME_DOMAIN`` /
``MIN_BEATS_FREQUENCY_DOMAIN`` (Quigley et al. 2024).

All modes delegate the science to ``rrational.analysis.hrv_compute``;
this module is just the UI form + result-table rendering on top.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import numpy as np
from qtpy.QtCore import QSettings, Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from rrational.analysis.hrv_compute import (
    FREQ_METHOD_KUBIOS,
    FREQ_METHOD_NEUROKIT,
)
from rrational.analysis.hrv_metrics import (
    HRV_METRIC_PRESETS,
    HRV_METRICS_CATALOG,
    MIN_BEATS_FREQUENCY_DOMAIN,
    MIN_BEATS_TIME_DOMAIN,
)

# Optional reference catalogue. Imported defensively so the Analysis
# tab keeps loading if the constant is removed or renamed upstream —
# _resolve_reference_band() then short-circuits to "no overlay".
try:
    from rrational.analysis.hrv_metrics import HRV_REFERENCE_VALUES
except ImportError:  # pragma: no cover - defensive
    HRV_REFERENCE_VALUES = {}
from rrational.inspector.exclusion_persistence import ExclusionZone
from rrational.inspector.tabs.base import InspectorTab

if TYPE_CHECKING:
    from rrational.inspector.data_loader import InspectorData

# Default metric set — picked as the "Basic" preset from
# ``rrational/analysis/hrv_metrics`` (every researcher recognises RMSSD,
# SDNN, LF/HF, pNN50). Kept as a module-level constant for the importers
# in ``results_tab.py`` + tests; the Analysis tab itself reads from the
# per-tab settings bar.
_DEFAULT_METRICS = ["RMSSD", "SDNN", "MeanHR", "LF", "HF", "LF_HF", "pNN50"]

# Ordered metric list — categories side by side, alphabetical inside
# each. Used to build the checkbox grid in display order so layout is
# stable across runs.
_ALL_METRICS_ORDERED: list[str] = [
    m for cat in HRV_METRICS_CATALOG.values() for m in cat
]

# Preset → ordered list of metrics. Mirrors the Streamlit "Basic / Time /
# Frequency / Geometric / Nonlinear / All / Custom" presets, but
# anchored to the catalog so adding a metric there flows here too.
_PRESET_METRICS: dict[str, list[str]] = {
    "Basic": list(HRV_METRIC_PRESETS["Basic"]["metrics"]),
    "Time domain": [
        *HRV_METRICS_CATALOG["time_basic"].keys(),
        *HRV_METRICS_CATALOG["time_extended"].keys(),
    ],
    "Frequency domain": list(HRV_METRICS_CATALOG["frequency"].keys()),
    "Geometric": ["HTI", "TINN"],
    "Nonlinear": list(HRV_METRICS_CATALOG["nonlinear"].keys()),
    "All": list(_ALL_METRICS_ORDERED),
    "Custom": [],  # freeform — checkboxes drive the selection
}
_PRESET_ORDER = [
    "Basic",
    "Time domain",
    "Frequency domain",
    "Geometric",
    "Nonlinear",
    "All",
    "Custom",
]

# QSettings keys. All read/written via raw QSettings — they live
# outside the inspector's central ``_DEFAULTS`` dict because they are
# Analysis-tab specific and the rest of the inspector doesn't care.
_SETTING_METRIC_PRESET = "analysis_metric_preset"
_SETTING_SELECTED_METRICS = "analysis_selected_metrics"
_SETTING_FREQ_METHOD = "analysis_freq_method"
_SETTING_OVERLAP_ENABLED = "analysis_overlap_enabled"
_SETTING_OVERLAP_MODE = "analysis_overlap_mode"  # "beats" | "seconds"
_SETTING_OVERLAP_SIZE = "analysis_overlap_size"
_SETTING_OVERLAP_STEP = "analysis_overlap_step"

# Yellow tint applied to result-table rows where the segment fell
# below the recommended beat/duration minimum. Chosen to read on both
# light and dark themes.
_WARN_BRUSH = QColor(255, 247, 200)

# HRV reference-band tints. Soft pastels so they read on top of the
# alternating-row stripes without overwhelming the value text. Mapping
# rule (see _resolve_reference_band):
#   value >= high                  -> Excellent
#   normal  <= value <  high       -> Normal
#   low     <= value <  normal     -> Borderline
#   value < low                    -> Poor
_REF_EXCELLENT_BRUSH = QColor(200, 255, 200)
_REF_NORMAL_BRUSH = QColor(220, 255, 220)
_REF_BORDERLINE_BRUSH = QColor(255, 240, 200)
_REF_POOR_BRUSH = QColor(255, 210, 210)


def _resolve_reference_band(metric: str, value: float) -> tuple[QColor, str] | None:
    """Look up ``metric`` in HRV_REFERENCE_VALUES and return (brush, tooltip).

    Returns ``None`` when the metric isn't in the catalogue, when the
    catalogue entry is missing the expected ``low`` / ``normal`` / ``high``
    keys, or when the value isn't a finite number. Centralised here so
    every result-table populator can stay one line: just ``apply if
    not None``.
    """
    if not HRV_REFERENCE_VALUES:
        return None
    entry = HRV_REFERENCE_VALUES.get(metric)
    if not entry or not all(k in entry for k in ("low", "normal", "high")):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(v) or math.isinf(v):
        return None
    low = float(entry["low"])
    normal = float(entry["normal"])
    high = float(entry["high"])
    unit = str(entry.get("unit", "") or "")
    unit_suffix = f" {unit}" if unit else ""
    if v >= high:
        brush = _REF_EXCELLENT_BRUSH
        band = "Excellent"
    elif v >= normal:
        brush = _REF_NORMAL_BRUSH
        band = "Normal"
    elif v >= low:
        brush = _REF_BORDERLINE_BRUSH
        band = "Borderline"
    else:
        brush = _REF_POOR_BRUSH
        band = "Poor"
    tooltip = (
        f"{metric} reference (Shaffer & Ginsberg 2017, Nunan et al. 2010):\n"
        f"  Poor:       < {low}{unit_suffix}\n"
        f"  Borderline: {low}-{normal}{unit_suffix}\n"
        f"  Normal:     {normal}-{high}{unit_suffix}\n"
        f"  Excellent:  >= {high}{unit_suffix}\n"
        f"Current value: {v:.2f}{unit_suffix} ({band})"
    )
    return brush, tooltip


def _format_metric(value) -> str:
    """Format an HRV-metric value for table display."""
    if value is None:
        return "—"
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if math.isnan(f):
        return "—"
    if abs(f) >= 1000 or abs(f) < 0.01:
        return f"{f:.2e}"
    return f"{f:.2f}"


def _slice_section(
    data: "InspectorData",
    section_name: str,
    exclusions: list[ExclusionZone] | None = None,
) -> np.ndarray | None:
    """Return the RR (ms) values inside ``section_name``, minus excluded beats.

    The optional ``exclusions`` argument drops any beat whose timestamp
    falls inside ANY ``ExclusionZone``. Pass ``None`` (or an empty
    list) to skip the filter.
    """
    section = next((s for s in data.sections if s.name == section_name), None)
    if section is None:
        return None
    in_section = (data.t >= section.t_start) & (data.t <= section.t_end)
    finite = np.isfinite(data.v)
    mask = in_section & finite
    if exclusions:
        for z in exclusions:
            inside = (data.t >= z.start_t) & (data.t <= z.end_t)
            mask &= ~inside
    return data.v[mask]


def _active_exclusion_zones(main_window) -> list[ExclusionZone]:
    """Read the live exclusion-zone list from the Browse tab's plot.

    Centralised so every compute pane uses the same source — there's only
    ever one plot, but its zones change over time.
    """
    try:
        return list(main_window._browse_tab._plot._exclusion_zones)
    except AttributeError:
        return []


def _segment_warning(
    n_beats: int, duration_s: float | None, metrics: list[str]
) -> str | None:
    """Return a human-readable warning when ``n_beats`` is below the
    Quigley-et-al-2024 recommended minimums, else ``None``.

    Frequency-domain metrics trigger a stricter minimum than time-domain.
    The warning string is suitable as a tooltip and a status bar caption.
    """
    issues: list[str] = []
    if n_beats < MIN_BEATS_TIME_DOMAIN:
        issues.append(
            f"Only {n_beats} beats (min {MIN_BEATS_TIME_DOMAIN} for time domain)"
        )
    freq_metric_names = set(HRV_METRICS_CATALOG["frequency"].keys())
    has_freq = bool(set(metrics) & freq_metric_names)
    if has_freq and n_beats < MIN_BEATS_FREQUENCY_DOMAIN:
        issues.append(
            f"Frequency metrics need at least {MIN_BEATS_FREQUENCY_DOMAIN} "
            f"beats (have {n_beats})"
        )
    if duration_s is not None and duration_s < 120 and has_freq:
        issues.append(
            f"Frequency metrics need at least 120 s of recording "
            f"(have {duration_s:.0f} s)"
        )
    if not issues:
        return None
    return " · ".join(issues)


class _AnalysisSettingsBar(QWidget):
    """Top-of-tab settings group: metric preset, freq method, windows.

    Holds the persistent state across all four analysis modes. Reads /
    writes to :class:`QSettings` so user choices survive across runs.
    Emits no Qt signal yet — panes call :meth:`compute_kwargs` /
    :meth:`selected_metrics` at compute-time.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._building = True  # suppress persist during construction

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        settings_box = QGroupBox("Analysis settings", self)
        settings_layout = QVBoxLayout(settings_box)
        settings_layout.setContentsMargins(8, 8, 8, 8)
        settings_layout.setSpacing(6)
        outer.addWidget(settings_box)

        # ---- Preset + freq method row -------------------------------
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Metrics preset:"))
        self._preset_combo = QComboBox()
        for name in _PRESET_ORDER:
            self._preset_combo.addItem(name)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_row.addWidget(self._preset_combo)
        preset_row.addStretch()
        top_row.addLayout(preset_row)

        freq_row = QHBoxLayout()
        freq_row.addWidget(QLabel("Frequency pipeline:"))
        self._freq_neurokit = QRadioButton("NeuroKit2 default")
        self._freq_kubios = QRadioButton("Kubios-compatible")
        self._freq_neurokit.setToolTip(
            "NK2 default — normalized PSD, 100 Hz interpolation"
        )
        self._freq_kubios.setToolTip(
            "Kubios HRV Scientific compatible — absolute ms-squared, 4 Hz "
            "interpolation, 180 s Welch with Tarvainen smoothness-priors detrending"
        )
        self._freq_group = QButtonGroup(self)
        self._freq_group.addButton(self._freq_neurokit, 0)
        self._freq_group.addButton(self._freq_kubios, 1)
        self._freq_group.idToggled.connect(self._on_freq_changed)
        freq_row.addWidget(self._freq_neurokit)
        freq_row.addWidget(self._freq_kubios)
        freq_row.addStretch()
        top_row.addLayout(freq_row)

        settings_layout.addLayout(top_row)

        # ---- Per-metric checkbox grid (collapsible) ------------------
        # The group box is checkable so the (large) checkbox grid can
        # collapse when not in use. When collapsed, a single-line
        # "Selected: …" summary label takes the grid's place so the
        # group never reads as an empty bordered box.
        metrics_box = QGroupBox("Metrics to compute", self)
        metrics_box.setCheckable(True)
        metrics_box.setChecked(False)  # start collapsed
        metrics_outer = QVBoxLayout(metrics_box)
        metrics_outer.setContentsMargins(8, 6, 8, 6)
        metrics_outer.setSpacing(4)

        self._selected_metrics_summary = QLabel("", metrics_box)
        self._selected_metrics_summary.setWordWrap(True)
        self._selected_metrics_summary.setStyleSheet("QLabel { color: #555; }")
        metrics_outer.addWidget(self._selected_metrics_summary)

        self._metrics_grid_widget = QWidget(metrics_box)
        metrics_layout = QGridLayout(self._metrics_grid_widget)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        self._metric_checkboxes: dict[str, QCheckBox] = {}
        cols = 5
        for i, metric in enumerate(_ALL_METRICS_ORDERED):
            cb = QCheckBox(metric)
            cb.toggled.connect(lambda _checked, m=metric: self._on_metric_toggled(m))
            self._metric_checkboxes[metric] = cb
            metrics_layout.addWidget(cb, i // cols, i % cols)
        metrics_outer.addWidget(self._metrics_grid_widget)

        # Toggle visibility based on group-box checkable state so the
        # grid actually collapses when unchecked — and so the summary
        # label takes the grid's slot when collapsed.
        metrics_box.toggled.connect(self._toggle_metrics_grid_visible)
        self._metrics_box = metrics_box
        settings_layout.addWidget(metrics_box)
        # Force initial visibility sync (start collapsed).
        self._toggle_metrics_grid_visible(False)

        # ---- Overlapping windows group -------------------------------
        overlap_box = QGroupBox("Overlapping windows", self)
        overlap_layout = QVBoxLayout(overlap_box)
        overlap_layout.setContentsMargins(8, 6, 8, 6)
        overlap_layout.setSpacing(4)
        self._overlap_check = QCheckBox(
            "Use overlapping windows (compute metrics per window, then average)"
        )
        self._overlap_check.toggled.connect(self._on_overlap_toggled)
        overlap_layout.addWidget(self._overlap_check)

        self._overlap_form_widget = QWidget(overlap_box)
        form = QFormLayout(self._overlap_form_widget)
        form.setContentsMargins(20, 0, 0, 0)
        self._overlap_mode_combo = QComboBox()
        self._overlap_mode_combo.addItem("Beats (count)", "beats")
        self._overlap_mode_combo.addItem("Seconds (duration)", "seconds")
        self._overlap_mode_combo.currentIndexChanged.connect(
            self._on_overlap_mode_changed
        )
        self._overlap_size_spin = QSpinBox()
        self._overlap_size_spin.setRange(10, 100_000)
        self._overlap_size_spin.setValue(300)
        self._overlap_size_spin.setSuffix(" beats")
        self._overlap_size_spin.valueChanged.connect(self._persist)
        self._overlap_step_spin = QSpinBox()
        self._overlap_step_spin.setRange(1, 100_000)
        self._overlap_step_spin.setValue(75)
        self._overlap_step_spin.setSuffix(" beats")
        self._overlap_step_spin.valueChanged.connect(self._persist)
        form.addRow("Mode:", self._overlap_mode_combo)
        form.addRow("Window size:", self._overlap_size_spin)
        form.addRow("Step (gap between window starts):", self._overlap_step_spin)
        overlap_layout.addWidget(self._overlap_form_widget)
        self._overlap_form_widget.setVisible(False)
        settings_layout.addWidget(overlap_box)

        # Restore persisted state and re-enable the persist hooks.
        self._restore()
        self._building = False

    # ------------------------------------------------------------------
    # UI handlers
    # ------------------------------------------------------------------
    def _toggle_metrics_grid_visible(self, checked: bool) -> None:
        """Show the checkbox grid when expanded, the summary label when collapsed.

        Without the summary, the collapsed group renders as an empty
        bordered box (~50 px tall) that reads like a UI bug.
        """
        self._metrics_grid_widget.setVisible(checked)
        self._selected_metrics_summary.setVisible(not checked)
        if not checked:
            self._refresh_selected_metrics_summary()

    def _refresh_selected_metrics_summary(self) -> None:
        """Populate the collapsed-state summary with the current selection."""
        if not hasattr(self, "_selected_metrics_summary"):
            return
        selected = self.selected_metrics()
        if not selected:
            text = "No metrics selected — defaults will be used."
        else:
            text = "Selected: " + ", ".join(selected)
        self._selected_metrics_summary.setText(text)

    def _on_preset_changed(self, _idx: int) -> None:
        if self._building:
            return
        preset = self._preset_combo.currentText()
        if preset == "Custom":
            # Don't touch checkboxes — let the user keep their freeform set.
            self._persist()
            return
        target = set(_PRESET_METRICS.get(preset, []))
        # Block signals so we don't re-trigger "Custom" via _on_metric_toggled.
        prev_building = self._building
        self._building = True
        try:
            for name, cb in self._metric_checkboxes.items():
                cb.setChecked(name in target)
        finally:
            self._building = prev_building
        self._persist()

    def _on_metric_toggled(self, _metric: str) -> None:
        if self._building:
            return
        # Any manual toggle that takes the selection away from the
        # current preset's canonical set downgrades the preset to
        # "Custom" so subsequent visits keep the user's freeform choice.
        current = self._preset_combo.currentText()
        live = self.selected_metrics()
        canonical = _PRESET_METRICS.get(current, [])
        if current != "Custom" and set(live) != set(canonical):
            prev_building = self._building
            self._building = True
            try:
                idx = self._preset_combo.findText("Custom")
                if idx >= 0:
                    self._preset_combo.setCurrentIndex(idx)
            finally:
                self._building = prev_building
        self._persist()

    def _on_freq_changed(self, _id: int, _checked: bool) -> None:
        if self._building:
            return
        self._persist()

    def _on_overlap_toggled(self, checked: bool) -> None:
        self._overlap_form_widget.setVisible(checked)
        if not self._building:
            self._persist()

    def _on_overlap_mode_changed(self, _idx: int) -> None:
        mode = self.overlap_mode()
        suffix = " beats" if mode == "beats" else " s"
        self._overlap_size_spin.setSuffix(suffix)
        self._overlap_step_spin.setSuffix(suffix)
        if not self._building:
            self._persist()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _qs(self) -> QSettings:
        return QSettings()

    def _persist(self) -> None:
        if self._building:
            return
        s = self._qs()
        s.setValue(_SETTING_METRIC_PRESET, self._preset_combo.currentText())
        s.setValue(_SETTING_SELECTED_METRICS, ",".join(self.selected_metrics()))
        s.setValue(_SETTING_FREQ_METHOD, self.freq_method())
        s.setValue(
            _SETTING_OVERLAP_ENABLED, "1" if self._overlap_check.isChecked() else "0"
        )
        s.setValue(_SETTING_OVERLAP_MODE, self.overlap_mode())
        s.setValue(_SETTING_OVERLAP_SIZE, int(self._overlap_size_spin.value()))
        s.setValue(_SETTING_OVERLAP_STEP, int(self._overlap_step_spin.value()))
        s.sync()
        # Keep the collapsed-state summary in sync with the current
        # selection (cheap; no-op when the label isn't visible).
        self._refresh_selected_metrics_summary()

    def _restore(self) -> None:
        s = self._qs()
        # Preset
        preset = str(s.value(_SETTING_METRIC_PRESET, "Basic"))
        idx = self._preset_combo.findText(preset)
        if idx >= 0:
            self._preset_combo.setCurrentIndex(idx)
        else:
            self._preset_combo.setCurrentIndex(0)
        # Metrics — apply preset defaults first, then overlay the
        # persisted explicit selection if any.
        target_metrics = set(_PRESET_METRICS.get(self._preset_combo.currentText(), []))
        raw = s.value(_SETTING_SELECTED_METRICS, None)
        if raw:
            persisted = [m for m in str(raw).split(",") if m in self._metric_checkboxes]
            if persisted:
                target_metrics = set(persisted)
        for name, cb in self._metric_checkboxes.items():
            cb.setChecked(name in target_metrics)
        # Frequency
        freq = str(s.value(_SETTING_FREQ_METHOD, FREQ_METHOD_NEUROKIT))
        if freq == FREQ_METHOD_KUBIOS:
            self._freq_kubios.setChecked(True)
        else:
            self._freq_neurokit.setChecked(True)
        # Overlap
        enabled = str(s.value(_SETTING_OVERLAP_ENABLED, "0")) in ("1", "true", "True")
        self._overlap_check.setChecked(enabled)
        self._overlap_form_widget.setVisible(enabled)
        mode = str(s.value(_SETTING_OVERLAP_MODE, "beats"))
        idx = self._overlap_mode_combo.findData(mode)
        if idx >= 0:
            self._overlap_mode_combo.setCurrentIndex(idx)
        try:
            self._overlap_size_spin.setValue(int(s.value(_SETTING_OVERLAP_SIZE, 300)))
        except (TypeError, ValueError):
            self._overlap_size_spin.setValue(300)
        try:
            self._overlap_step_spin.setValue(int(s.value(_SETTING_OVERLAP_STEP, 75)))
        except (TypeError, ValueError):
            self._overlap_step_spin.setValue(75)
        # Sync the suffix with the restored mode.
        self._on_overlap_mode_changed(self._overlap_mode_combo.currentIndex())
        # Initial summary text reflects whatever just got restored.
        self._refresh_selected_metrics_summary()

    # ------------------------------------------------------------------
    # Read-only accessors used by the compute panes
    # ------------------------------------------------------------------
    def selected_metrics(self) -> list[str]:
        """Return the list of metric names currently ticked, catalog order."""
        return [
            m for m in _ALL_METRICS_ORDERED if self._metric_checkboxes[m].isChecked()
        ]

    def freq_method(self) -> str:
        """Return ``FREQ_METHOD_NEUROKIT`` or ``FREQ_METHOD_KUBIOS``."""
        return (
            FREQ_METHOD_KUBIOS
            if self._freq_kubios.isChecked()
            else FREQ_METHOD_NEUROKIT
        )

    def overlap_enabled(self) -> bool:
        return self._overlap_check.isChecked()

    def overlap_mode(self) -> str:
        data = self._overlap_mode_combo.currentData()
        return str(data) if data else "beats"

    def overlap_size(self) -> int:
        return int(self._overlap_size_spin.value())

    def overlap_step(self) -> int:
        return int(self._overlap_step_spin.value())

    def compute_kwargs(self, rr_ms: np.ndarray | list[float]) -> dict:
        """Build the kwargs forwarded to ``calculate_hrv_metrics``."""
        metrics = self.selected_metrics()
        if not metrics:
            metrics = list(_DEFAULT_METRICS)
        kwargs: dict = {
            "selected_metrics": metrics,
            "freq_method": self.freq_method(),
        }
        if self.overlap_enabled():
            mode = self.overlap_mode()
            size = self.overlap_size()
            step = self.overlap_step()
            # calculate_hrv_metrics accepts window size + overlap_pct.
            # Convert explicit step → overlap_pct (clamped to [0, 99.9]).
            overlap_pct = max(0.0, min(99.9, 100.0 * (1.0 - (step / max(1, size)))))
            if mode == "beats":
                kwargs.update(
                    use_windows=True,
                    window_beats=int(size),
                    overlap_pct=float(overlap_pct),
                )
            else:
                kwargs.update(
                    use_windows=True,
                    window_s=float(size),
                    overlap_pct=float(overlap_pct),
                )
        else:
            kwargs.update(use_windows=False)
        return kwargs


def _compute_metrics_with_settings(
    rr_ms: np.ndarray,
    settings_bar: _AnalysisSettingsBar | None,
) -> tuple[dict[str, float], list[str]]:
    """Run HRV compute on an RR array, honouring the settings bar.

    Returns ``(metrics_dict, selected_metric_names)``. ``selected_metric_names``
    is the ordered list of metrics the user asked for — used for warning
    decisions (e.g. whether to flag too-few beats for frequency metrics).
    """
    from rrational.analysis.hrv_compute import calculate_hrv_metrics

    if settings_bar is not None:
        selected = settings_bar.selected_metrics()
        kwargs = settings_bar.compute_kwargs(rr_ms)
    else:  # back-compat path for tools that don't route through the UI
        selected = list(_DEFAULT_METRICS)
        kwargs = {"selected_metrics": selected, "use_windows": False}

    if not selected:
        selected = list(_DEFAULT_METRICS)
        kwargs["selected_metrics"] = selected

    if len(rr_ms) < 10:
        return {m: float("nan") for m in selected}, selected
    try:
        metrics, _, _ = calculate_hrv_metrics(nn_ms_list=rr_ms.tolist(), **kwargs)
    except Exception:
        metrics = {m: float("nan") for m in selected}
    return metrics, selected


def _compute_metrics(rr_ms: np.ndarray) -> dict[str, float]:
    """Back-compat single-shot compute (used by tests + tools that
    don't yet route through the settings bar)."""
    metrics, _ = _compute_metrics_with_settings(rr_ms, None)
    return metrics


def _tint_row(table: QTableWidget, row: int, tooltip: str) -> None:
    """Tint every cell in ``row`` yellow + attach a shared tooltip."""
    for col in range(table.columnCount()):
        item = table.item(row, col)
        if item is None:
            continue
        item.setBackground(_WARN_BRUSH)
        item.setToolTip(tooltip)


def _make_empty_hint(text: str) -> QLabel:
    """Build a centred, multi-line empty-state hint label."""
    label = QLabel(text)
    label.setAlignment(Qt.AlignCenter)
    label.setWordWrap(True)
    label.setTextFormat(Qt.RichText)
    label.setStyleSheet("QLabel { color: #666; font-size: 13px; padding: 32px; }")
    return label


def _wrap_table_with_hint(table: QTableWidget, hint_text: str) -> QStackedWidget:
    """Wrap ``table`` in a QStackedWidget [hint, table].

    Callers should switch to index 1 (the table) the first time they
    populate it; the stack starts on index 0 (the hint).
    """
    stack = QStackedWidget()
    stack.addWidget(_make_empty_hint(hint_text))
    stack.addWidget(table)
    stack.setCurrentIndex(0)
    return stack


class _SingleParticipantPane(QWidget):
    """Pick a dataset + section, compute HRV metrics on that segment."""

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self._main_window = main_window
        # Bound at AnalysisTab construction time — see the back-ref injection
        # in ``AnalysisTab.__init__``.
        self._settings_bar: _AnalysisSettingsBar | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        form_box = QGroupBox("Inputs")
        form = QFormLayout(form_box)
        self._dataset_combo = QComboBox()
        self._dataset_combo.currentIndexChanged.connect(self._on_dataset_changed)
        self._section_combo = QComboBox()
        form.addRow("Dataset:", self._dataset_combo)
        form.addRow("Section:", self._section_combo)
        outer.addWidget(form_box)

        button_row = QHBoxLayout()
        self._compute_btn = QPushButton("Compute HRV metrics")
        self._compute_btn.clicked.connect(self._on_compute)
        self._compute_btn.setEnabled(False)
        button_row.addWidget(self._compute_btn)
        button_row.addStretch()
        outer.addLayout(button_row)

        self._result_table = QTableWidget(0, 2, self)
        self._result_table.setHorizontalHeaderLabels(["Metric", "Value"])
        self._result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._result_table.setAlternatingRowColors(True)
        self._result_table.verticalHeader().setVisible(False)
        self._result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._result_stack = _wrap_table_with_hint(
            self._result_table,
            "Click <b>Compute HRV metrics</b> below to populate this table.",
        )
        outer.addWidget(self._result_stack)

        # F6: plot tabs — instantiated lazily on first compute so the
        # empty state stays cheap. Plot widgets take rr_intervals in
        # their constructors so we rebuild them each run.
        self._plot_tabs = QTabWidget(self)
        self._plot_empty_label = _make_empty_hint(
            "Run <b>Compute HRV metrics</b> to see plots."
        )
        self._plot_stack = QStackedWidget(self)
        self._plot_stack.addWidget(self._plot_empty_label)
        self._plot_stack.addWidget(self._plot_tabs)
        self._plot_stack.setCurrentIndex(0)
        outer.addWidget(self._plot_stack, 1)

    def refresh_workspace(self) -> None:
        """Rebuild the dataset dropdown from the workspace."""
        prev = self._dataset_combo.currentData()
        self._dataset_combo.blockSignals(True)
        self._dataset_combo.clear()
        for i, ds in enumerate(self._main_window._datasets):
            self._dataset_combo.addItem(ds.name, i)
        # Restore previous selection if still valid
        if prev is not None:
            idx = self._dataset_combo.findData(prev)
            if idx >= 0:
                self._dataset_combo.setCurrentIndex(idx)
        self._dataset_combo.blockSignals(False)
        self._on_dataset_changed(self._dataset_combo.currentIndex())

    def _on_dataset_changed(self, _row: int) -> None:
        self._section_combo.clear()
        idx = self._dataset_combo.currentData()
        if idx is None or not (0 <= idx < len(self._main_window._datasets)):
            self._compute_btn.setEnabled(False)
            return
        ds = self._main_window._datasets[idx]
        for sec in ds.data.sections:
            self._section_combo.addItem(sec.name)
        self._compute_btn.setEnabled(self._section_combo.count() > 0)

    def _on_compute(self) -> None:
        from rrational.inspector.results_store import MetricRow

        ds_idx = self._dataset_combo.currentData()
        sec_name = self._section_combo.currentText()
        if ds_idx is None or not sec_name:
            return
        ds = self._main_window._datasets[ds_idx]
        exclusions = _active_exclusion_zones(self._main_window)
        rr = _slice_section(ds.data, sec_name, exclusions=exclusions)
        if rr is None or len(rr) == 0:
            self._main_window.statusBar().showMessage(
                f"No samples in section '{sec_name}'", 3000
            )
            return
        self._main_window.statusBar().showMessage(
            f"Computing HRV on '{sec_name}' ({len(rr)} beats)…"
        )
        metrics, selected = _compute_metrics_with_settings(rr, self._settings_bar)
        duration_s = float(np.nansum(rr) / 1000.0) if len(rr) else 0.0
        warning = _segment_warning(int(len(rr)), duration_s, selected)
        self._populate_result_table(
            metrics,
            n_beats=len(rr),
            section=sec_name,
            selected_metrics=selected,
            warning=warning,
        )
        # F6: rebuild the plot tabs with the freshly-computed RR data.
        # The plot widgets expect rr_intervals in their constructors, so
        # discarding + reinstantiating is simpler than a per-widget setter.
        self._rebuild_plot_tabs(rr, sec_name)
        # Flip the stacks from empty-hint (0) to populated (1).
        self._result_stack.setCurrentIndex(1)
        self._plot_stack.setCurrentIndex(1)
        # Push to the central results store; Results tab picks it up.
        self._main_window._results_store.add_metric_row(
            MetricRow(
                mode="single",
                dataset=ds.name,
                section=sec_name,
                n_beats=int(len(rr)),
                metrics=dict(metrics),
            )
        )
        self._main_window._results_tab.refresh_results()
        msg = f"HRV computed for {ds.name} · {sec_name} ({len(rr)} beats)"
        if warning:
            msg += f" — {warning}"
        self._main_window.statusBar().showMessage(msg, 5000)

    def _rebuild_plot_tabs(self, rr_ms: np.ndarray, section_label: str) -> None:
        """Replace every tab in ``_plot_tabs`` with fresh widgets for ``rr_ms``."""
        from rrational.inspector.plots.hr_distribution import HRDistributionPlot
        from rrational.inspector.plots.poincare import PoincarePlot
        from rrational.inspector.plots.psd import PSDPlot
        from rrational.inspector.plots.tachogram import TachogramPlot

        while self._plot_tabs.count() > 0:
            w = self._plot_tabs.widget(0)
            self._plot_tabs.removeTab(0)
            w.deleteLater()
        self._plot_tabs.addTab(
            TachogramPlot(rr_ms, section_label=section_label), "Tachogram"
        )
        self._plot_tabs.addTab(
            PoincarePlot(rr_ms, section_label=section_label), "Poincaré"
        )
        self._plot_tabs.addTab(
            PSDPlot(rr_ms, section_label=section_label), "Frequency (PSD)"
        )
        self._plot_tabs.addTab(
            HRDistributionPlot(rr_ms, section_label=section_label), "HR distribution"
        )

    def _populate_result_table(
        self,
        metrics: dict,
        n_beats: int,
        section: str,
        selected_metrics: list[str] | None = None,
        warning: str | None = None,
    ) -> None:
        self._result_table.setRowCount(0)
        # First row: meta info
        meta_rows = [
            ("Section", section),
            ("Beats analysed", str(n_beats)),
        ]
        for name, value in meta_rows:
            row = self._result_table.rowCount()
            self._result_table.insertRow(row)
            self._result_table.setItem(row, 0, QTableWidgetItem(name))
            self._result_table.setItem(row, 1, QTableWidgetItem(value))
        if warning:
            # Add an explicit warning row at the top of the metric list
            # plus a yellow tint so it can't be missed.
            warn_row = self._result_table.rowCount()
            self._result_table.insertRow(warn_row)
            self._result_table.setItem(warn_row, 0, QTableWidgetItem("Warning"))
            self._result_table.setItem(warn_row, 1, QTableWidgetItem(warning))
            _tint_row(self._result_table, warn_row, warning)
        # Metric rows
        metric_list = selected_metrics or _DEFAULT_METRICS
        freq_set = set(HRV_METRICS_CATALOG["frequency"].keys())
        for m in metric_list:
            row = self._result_table.rowCount()
            self._result_table.insertRow(row)
            self._result_table.setItem(row, 0, QTableWidgetItem(m))
            value_item = QTableWidgetItem(_format_metric(metrics.get(m)))
            self._result_table.setItem(row, 1, value_item)
            # Overlay reference-band colour + tooltip BEFORE the
            # warning-tint pass so the too-few-beats yellow always
            # wins on undersampled segments.
            band = _resolve_reference_band(m, metrics.get(m))
            if band is not None:
                brush, tooltip = band
                value_item.setBackground(brush)
                value_item.setToolTip(tooltip)
            # Tint frequency-metric rows yellow when the segment is too
            # short for reliable PSD analysis.
            if m in freq_set and n_beats < MIN_BEATS_FREQUENCY_DOMAIN:
                _tint_row(
                    self._result_table,
                    row,
                    f"{n_beats} beats — frequency metrics need at least "
                    f"{MIN_BEATS_FREQUENCY_DOMAIN}",
                )
            elif m not in freq_set and n_beats < MIN_BEATS_TIME_DOMAIN:
                _tint_row(
                    self._result_table,
                    row,
                    f"{n_beats} beats — time-domain metrics need at least "
                    f"{MIN_BEATS_TIME_DOMAIN}",
                )


class _RepeatingSectionPane(QWidget):
    """Pick one section name; compute HRV across every dataset that has it."""

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self._main_window = main_window
        self._settings_bar: _AnalysisSettingsBar | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        form_box = QGroupBox("Inputs")
        form = QFormLayout(form_box)
        self._section_combo = QComboBox()
        form.addRow("Section name (across datasets):", self._section_combo)
        outer.addWidget(form_box)

        button_row = QHBoxLayout()
        self._compute_btn = QPushButton("Compute across all datasets")
        self._compute_btn.clicked.connect(self._on_compute)
        self._compute_btn.setEnabled(False)
        button_row.addWidget(self._compute_btn)
        button_row.addStretch()
        outer.addLayout(button_row)

        self._result_table = QTableWidget(0, 1 + len(_DEFAULT_METRICS), self)
        self._result_table.setHorizontalHeaderLabels(["Dataset", *_DEFAULT_METRICS])
        self._result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._result_table.setAlternatingRowColors(True)
        self._result_table.verticalHeader().setVisible(False)
        self._result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._result_stack = _wrap_table_with_hint(
            self._result_table,
            "Pick a section and click <b>Compute across all datasets</b>.",
        )
        outer.addWidget(self._result_stack)

    def refresh_workspace(self) -> None:
        """Rebuild the section-name dropdown from the union across datasets."""
        prev = self._section_combo.currentText()
        section_names = sorted(
            {sec.name for ds in self._main_window._datasets for sec in ds.data.sections}
        )
        self._section_combo.blockSignals(True)
        self._section_combo.clear()
        for name in section_names:
            self._section_combo.addItem(name)
        if prev in section_names:
            idx = self._section_combo.findText(prev)
            if idx >= 0:
                self._section_combo.setCurrentIndex(idx)
        self._section_combo.blockSignals(False)
        self._compute_btn.setEnabled(bool(section_names))

    def _on_compute(self) -> None:
        from rrational.inspector.results_store import MetricRow

        sec_name = self._section_combo.currentText()
        if not sec_name:
            return
        self._main_window.statusBar().showMessage(
            f"Computing HRV on '{sec_name}' across every dataset…"
        )
        rows: list[tuple[str, dict, int]] = []
        exclusions = _active_exclusion_zones(self._main_window)
        selected_metrics_seen: list[str] = []
        for ds in self._main_window._datasets:
            rr = _slice_section(ds.data, sec_name, exclusions=exclusions)
            if rr is None or len(rr) == 0:
                continue
            metrics, selected = _compute_metrics_with_settings(rr, self._settings_bar)
            selected_metrics_seen = selected
            rows.append((ds.name, metrics, int(len(rr))))
        self._populate_result_table(
            rows, selected_metrics_seen or list(_DEFAULT_METRICS)
        )
        if rows:
            self._result_stack.setCurrentIndex(1)
        # Push each per-dataset row into the central store.
        for ds_name, metrics, n_beats in rows:
            self._main_window._results_store.add_metric_row(
                MetricRow(
                    mode="repeating",
                    dataset=ds_name,
                    section=sec_name,
                    n_beats=n_beats,
                    metrics=dict(metrics),
                )
            )
        self._main_window._results_tab.refresh_results()
        self._main_window.statusBar().showMessage(
            f"HRV computed for '{sec_name}' on {len(rows)} dataset(s)", 4000
        )

    def _populate_result_table(
        self,
        rows: list[tuple[str, dict, int]],
        selected_metrics: list[str],
    ) -> None:
        # Table shape follows the user's metric selection so that picking
        # e.g. "Nonlinear only" doesn't leave empty time-domain columns.
        metric_cols = (
            list(selected_metrics) if selected_metrics else list(_DEFAULT_METRICS)
        )
        self._result_table.setColumnCount(1 + len(metric_cols))
        self._result_table.setHorizontalHeaderLabels(["Dataset", *metric_cols])
        self._result_table.setRowCount(0)
        freq_set = set(HRV_METRICS_CATALOG["frequency"].keys())
        for ds_name, metrics, n_beats in rows:
            row = self._result_table.rowCount()
            self._result_table.insertRow(row)
            self._result_table.setItem(row, 0, QTableWidgetItem(ds_name))
            for col, m in enumerate(metric_cols, start=1):
                value_item = QTableWidgetItem(_format_metric(metrics.get(m)))
                self._result_table.setItem(row, col, value_item)
                # Per-cell reference-band overlay. The warning-tint
                # below intentionally clobbers this when the segment is
                # too short — incomplete data trumps "where does it fall
                # on the band?".
                band = _resolve_reference_band(m, metrics.get(m))
                if band is not None:
                    brush, tooltip = band
                    value_item.setBackground(brush)
                    value_item.setToolTip(tooltip)
            warning = _segment_warning(n_beats, None, selected_metrics)
            if warning:
                _tint_row(self._result_table, row, warning)
            else:
                # Tint just the frequency cells when the segment is too short
                # even though time-domain metrics are fine.
                if n_beats < MIN_BEATS_FREQUENCY_DOMAIN:
                    for col, m in enumerate(metric_cols, start=1):
                        if m in freq_set:
                            item = self._result_table.item(row, col)
                            if item is not None:
                                item.setBackground(_WARN_BRUSH)
                                item.setToolTip(
                                    f"{n_beats} beats — frequency metrics "
                                    f"need at least {MIN_BEATS_FREQUENCY_DOMAIN}"
                                )


class _GroupPlotDialog(QDialog):
    """Modal dialog hosting a single group-comparison plot widget.

    Instantiated with the actual plot widget so the dialog stays
    plot-type agnostic — the caller picks one of ``GroupBarChart``,
    ``GroupBoxPlot``, ``GroupViolinPlot``, ``SD1SD2Scatter``.
    """

    def __init__(
        self,
        title: str,
        plot_widget: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(720, 520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(plot_widget, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
        self._plot_widget = plot_widget


class _GroupComparisonPane(QWidget):
    """Per-dataset group assignment + hypothesis-test comparison.

    Two assignment modes:

    - **Saved groups** (Streamlit-shared): pick from groups defined in
      the Setup tab's Groups sub-pane (which writes ``groups.yml`` via
      ``gui.persistence.save_groups``). Members are auto-applied.
    - **Ad-hoc labels**: type a free-text label directly in the second
      column of the assignment table. Useful for quick exploration.
      When Compute is clicked, the ad-hoc assignment can be persisted
      as a new group definition via the "Save as group…" button.
    """

    DEFAULT_GROUP = ""  # empty string = unassigned

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self._main_window = main_window
        self._settings_bar: _AnalysisSettingsBar | None = None
        # Per-dataset group label (keyed by dataset index — re-keyed on
        # workspace change so close-then-reload doesn't carry stale labels).
        self._group_by_idx: dict[int, str] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        # ---- 1a. Saved-groups picker (top) ---------------------------
        saved_box = QGroupBox("Saved groups (from Setup → Groups)")
        saved_row = QHBoxLayout(saved_box)
        self._saved_groups_combo = QComboBox()
        self._saved_groups_combo.setPlaceholderText("Pick a saved group definition…")
        self._apply_saved_btn = QPushButton("Apply members")
        self._apply_saved_btn.setToolTip(
            "Apply the selected saved group's member list to the assignment table"
        )
        self._apply_saved_btn.clicked.connect(self._on_apply_saved)
        self._apply_saved_btn.setEnabled(False)
        self._saved_groups_combo.currentIndexChanged.connect(
            lambda _: self._apply_saved_btn.setEnabled(
                self._saved_groups_combo.currentIndex() >= 0
            )
        )
        saved_row.addWidget(self._saved_groups_combo, 1)
        saved_row.addWidget(self._apply_saved_btn)
        outer.addWidget(saved_box)

        # ---- 1b. Group assignment table ------------------------------
        assign_box = QGroupBox("Group assignment (edit column 2 for ad-hoc labels)")
        assign_layout = QVBoxLayout(assign_box)
        self._assign_table = QTableWidget(0, 2, self)
        self._assign_table.setHorizontalHeaderLabels(["Dataset", "Group"])
        self._assign_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._assign_table.verticalHeader().setVisible(False)
        self._assign_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._assign_table.itemChanged.connect(self._on_assignment_changed)
        assign_layout.addWidget(self._assign_table)

        # "Save as group" button — persists current ad-hoc labels as a
        # named group definition the Streamlit app will see too.
        save_row = QHBoxLayout()
        save_row.addStretch()
        self._save_as_group_btn = QPushButton("Save assignment as new group…")
        self._save_as_group_btn.setToolTip(
            "Persist the current assignment as one or more groups in groups.yml"
        )
        self._save_as_group_btn.clicked.connect(self._on_save_as_group)
        self._save_as_group_btn.setEnabled(False)
        save_row.addWidget(self._save_as_group_btn)
        assign_layout.addLayout(save_row)
        outer.addWidget(assign_box)

        # ---- 2. Inputs + Compute -------------------------------------
        form_box = QGroupBox("Comparison inputs")
        form = QFormLayout(form_box)
        self._section_combo = QComboBox()
        self._metric_combo = QComboBox()
        for m in _DEFAULT_METRICS:
            self._metric_combo.addItem(m)
        form.addRow("Section name:", self._section_combo)
        form.addRow("Metric:", self._metric_combo)
        outer.addWidget(form_box)

        button_row = QHBoxLayout()
        self._compute_btn = QPushButton("Compare across groups")
        self._compute_btn.clicked.connect(self._on_compute)
        self._compute_btn.setEnabled(False)
        button_row.addWidget(self._compute_btn)
        button_row.addStretch()
        outer.addLayout(button_row)

        # ---- 3. Result panel -----------------------------------------
        self._result_label = QLabel(
            "<i>Assign a group label to at least two datasets, then click "
            "<b>Compare across groups</b>.</i>"
        )
        self._result_label.setWordWrap(True)
        self._result_label.setStyleSheet("padding: 8px;")
        outer.addWidget(self._result_label)

        self._group_stats_table = QTableWidget(0, 5, self)
        self._group_stats_table.setHorizontalHeaderLabels(
            ["Group", "n", "Mean", "SD", "Normal (p)"]
        )
        self._group_stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._group_stats_table.setAlternatingRowColors(True)
        self._group_stats_table.verticalHeader().setVisible(False)
        self._group_stats_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self._result_stack = _wrap_table_with_hint(
            self._group_stats_table,
            "Click <b>Compare across groups</b> after selecting at least 2 groups.",
        )
        outer.addWidget(self._result_stack)

        # ---- 4. View buttons: pop-up group plots ---------------------
        plot_row = QHBoxLayout()
        plot_row.addStretch()
        self._bar_btn = QPushButton("Bar chart…")
        self._bar_btn.clicked.connect(lambda: self._open_plot("bar"))
        self._bar_btn.setEnabled(False)
        plot_row.addWidget(self._bar_btn)
        self._box_btn = QPushButton("Box plot…")
        self._box_btn.clicked.connect(lambda: self._open_plot("box"))
        self._box_btn.setEnabled(False)
        plot_row.addWidget(self._box_btn)
        self._violin_btn = QPushButton("Violin plot…")
        self._violin_btn.clicked.connect(lambda: self._open_plot("violin"))
        self._violin_btn.setEnabled(False)
        plot_row.addWidget(self._violin_btn)
        self._sd_btn = QPushButton("SD1/SD2 scatter…")
        self._sd_btn.clicked.connect(lambda: self._open_plot("sd"))
        self._sd_btn.setEnabled(False)
        plot_row.addWidget(self._sd_btn)
        # F8: HTML report export — only meaningful after at least one
        # compute has produced stats; gated alongside the plot buttons.
        self._report_btn = QPushButton("Generate HTML report…")
        self._report_btn.setToolTip(
            "Write a self-contained HTML report of the current group-comparison "
            "results (descriptives + statistical tests)."
        )
        self._report_btn.clicked.connect(self._on_generate_report)
        self._report_btn.setEnabled(False)
        plot_row.addWidget(self._report_btn)
        outer.addLayout(plot_row)

        # Track the latest dialog so tests can introspect it.
        self._last_plot_dialog: _GroupPlotDialog | None = None

    # ------------------------------------------------------------------
    # Workspace sync
    # ------------------------------------------------------------------
    def refresh_workspace(self) -> None:
        # Rebuild section list (union across datasets)
        prev_sec = self._section_combo.currentText()
        section_names = sorted(
            {sec.name for ds in self._main_window._datasets for sec in ds.data.sections}
        )
        self._section_combo.blockSignals(True)
        self._section_combo.clear()
        for name in section_names:
            self._section_combo.addItem(name)
        if prev_sec in section_names:
            self._section_combo.setCurrentIndex(self._section_combo.findText(prev_sec))
        self._section_combo.blockSignals(False)

        # Re-key the group labels by current dataset index. We use the
        # dataset NAME as the persistence key so closing+reopening a
        # file keeps its assignment.
        new_label_by_idx: dict[int, str] = {}
        old_label_by_name = {
            self._main_window._datasets[i].name: lbl
            for i, lbl in self._group_by_idx.items()
            if i < len(self._main_window._datasets)
        }
        for i, ds in enumerate(self._main_window._datasets):
            new_label_by_idx[i] = old_label_by_name.get(ds.name, self.DEFAULT_GROUP)
        self._group_by_idx = new_label_by_idx

        # Auto-populate from saved groups: if a dataset's name appears in
        # a saved group's members list, pre-fill its label with that
        # group name (only when current label is empty — never overwrite
        # user-typed ad-hoc labels).
        saved = self._load_saved_groups()
        for i, ds in enumerate(self._main_window._datasets):
            if not self._group_by_idx[i]:
                for grp_name, grp_data in saved.items():
                    if ds.name in (grp_data.get("members") or []):
                        self._group_by_idx[i] = grp_name
                        break

        # Repopulate the assignment table
        self._assign_table.blockSignals(True)
        self._assign_table.setRowCount(0)
        for i, ds in enumerate(self._main_window._datasets):
            row = self._assign_table.rowCount()
            self._assign_table.insertRow(row)
            name_item = QTableWidgetItem(ds.name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            self._assign_table.setItem(row, 0, name_item)
            self._assign_table.setItem(row, 1, QTableWidgetItem(self._group_by_idx[i]))
        self._assign_table.blockSignals(False)
        self._refresh_saved_groups_combo()
        self._refresh_compute_enabled()
        self._refresh_save_as_enabled()
        # View buttons share the compute-enabled gate (need ≥2 groups).
        self._refresh_plot_buttons_enabled()

    def _load_saved_groups(self) -> dict[str, dict]:
        """Project-aware reuse of gui.persistence.load_groups."""
        from rrational.gui.persistence import load_groups as _lg

        proj = getattr(self._main_window, "_project", None)
        project_path = proj.project_path if proj is not None else None
        return _lg(project_path=project_path) or {}

    def refresh_saved_groups(self) -> None:
        """Called by MainWindow when Setup's GroupsPane has persisted edits."""
        self._refresh_saved_groups_combo()

    def _refresh_saved_groups_combo(self) -> None:
        prev = self._saved_groups_combo.currentText()
        saved = self._load_saved_groups()
        self._saved_groups_combo.blockSignals(True)
        self._saved_groups_combo.clear()
        for name, data in saved.items():
            display = (
                f"{name}  ({len(data.get('members') or [])} members)"
                if data.get("members")
                else name
            )
            self._saved_groups_combo.addItem(display, name)
        if prev:
            idx = self._saved_groups_combo.findText(prev)
            if idx >= 0:
                self._saved_groups_combo.setCurrentIndex(idx)
        self._saved_groups_combo.blockSignals(False)
        self._apply_saved_btn.setEnabled(self._saved_groups_combo.count() > 0)

    def _on_apply_saved(self) -> None:
        """Apply the picked saved group's members → assignment table."""
        idx = self._saved_groups_combo.currentIndex()
        if idx < 0:
            return
        group_name = self._saved_groups_combo.itemData(idx)
        saved = self._load_saved_groups()
        members = set(saved.get(group_name, {}).get("members") or [])
        # Assign group_name to every workspace dataset whose name is in
        # the group's member list. Leave others unchanged so the user
        # can chain multiple applies (e.g. apply Control first, then
        # apply Music to fill in the rest).
        self._assign_table.blockSignals(True)
        for i, ds in enumerate(self._main_window._datasets):
            if ds.name in members:
                self._group_by_idx[i] = group_name
                if i < self._assign_table.rowCount():
                    self._assign_table.setItem(i, 1, QTableWidgetItem(group_name))
        self._assign_table.blockSignals(False)
        self._refresh_compute_enabled()
        self._refresh_save_as_enabled()
        self._main_window.statusBar().showMessage(
            f"Applied saved group '{group_name}' to {sum(1 for ds in self._main_window._datasets if ds.name in members)} dataset(s)",
            4000,
        )

    def _refresh_save_as_enabled(self) -> None:
        """Save-as button needs at least 1 non-empty label."""
        has_labels = any(lbl for lbl in self._group_by_idx.values())
        self._save_as_group_btn.setEnabled(has_labels)

    def _on_save_as_group(self) -> None:
        """Persist current ad-hoc assignment as named groups in groups.yml."""

        from rrational.gui.persistence import load_groups, save_groups

        # Build per-label member list from current assignment
        members_by_label: dict[str, list[str]] = {}
        for i, ds in enumerate(self._main_window._datasets):
            lbl = self._group_by_idx.get(i, "")
            if lbl:
                members_by_label.setdefault(lbl, []).append(ds.name)
        if not members_by_label:
            return

        proj = getattr(self._main_window, "_project", None)
        project_path = proj.project_path if proj is not None else None
        existing = load_groups(project_path=project_path) or {}

        # Conflict check
        conflicts = [lbl for lbl in members_by_label if lbl in existing]
        if conflicts and not self._main_window.test_mode:
            reply = QMessageBox.question(
                self,
                "Overwrite existing groups",
                "These groups already exist: "
                + ", ".join(conflicts)
                + "\n\nOverwrite their member lists with the current assignment?",
            )
            if reply != QMessageBox.Yes:
                return

        for lbl, members in members_by_label.items():
            existing[lbl] = {
                "label": (existing.get(lbl, {}) or {}).get("label", lbl),
                "description": (existing.get(lbl, {}) or {}).get("description", ""),
                "members": members,
                "expected_events": (existing.get(lbl, {}) or {}).get(
                    "expected_events", {}
                ),
                "selected_sections": (existing.get(lbl, {}) or {}).get(
                    "selected_sections", []
                ),
            }
        save_groups(existing, project_path=project_path)
        # Refresh the Setup tab's GroupsPane + our own combo
        setup_groups = getattr(self._main_window._setup_tab, "_groups_pane", None)
        if setup_groups is not None and hasattr(setup_groups, "refresh_from_workspace"):
            setup_groups.refresh_from_workspace()
        self._refresh_saved_groups_combo()
        self._main_window.statusBar().showMessage(
            f"Saved {len(members_by_label)} group(s) to groups.yml", 4000
        )

    def _on_assignment_changed(self, item: QTableWidgetItem) -> None:
        # Only react to edits in the "Group" column.
        if item.column() != 1:
            return
        self._group_by_idx[item.row()] = item.text().strip()
        self._refresh_compute_enabled()
        self._refresh_save_as_enabled()
        self._refresh_plot_buttons_enabled()

    def _refresh_compute_enabled(self) -> None:
        """Compute is enabled iff ≥2 distinct non-empty group labels exist
        AND the section combo has at least one entry."""
        labels = {lbl for lbl in self._group_by_idx.values() if lbl}
        self._compute_btn.setEnabled(
            len(labels) >= 2 and self._section_combo.count() > 0
        )

    def _refresh_plot_buttons_enabled(self) -> None:
        """Plot view buttons need ≥2 distinct groups + ≥1 metric row in store."""
        labels = {lbl for lbl in self._group_by_idx.values() if lbl}
        store = getattr(self._main_window, "_results_store", None)
        has_rows = bool(store and getattr(store, "metric_rows", []))
        enabled = len(labels) >= 2 and has_rows
        self._bar_btn.setEnabled(enabled)
        self._box_btn.setEnabled(enabled)
        self._violin_btn.setEnabled(enabled)
        self._sd_btn.setEnabled(enabled)
        # F8: report needs a group-test result row, not just metric rows.
        has_group_tests = bool(store and getattr(store, "group_test_rows", []))
        self._report_btn.setEnabled(enabled and has_group_tests)

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    def _on_compute(self) -> None:
        from rrational.analysis.group_statistics import compare_groups

        sec_name = self._section_combo.currentText()
        metric = self._metric_combo.currentText()
        if not sec_name or not metric:
            return

        # Build {group_label: [metric_value_per_dataset]}. Also push a
        # MetricRow per dataset into the results store so the group-plot
        # widgets have rows to render later.
        from rrational.inspector.results_store import MetricRow

        values_per_group: dict[str, list[float]] = {}
        exclusions = _active_exclusion_zones(self._main_window)
        for i, ds in enumerate(self._main_window._datasets):
            label = self._group_by_idx.get(i, "")
            if not label:
                continue
            rr = _slice_section(ds.data, sec_name, exclusions=exclusions)
            if rr is None or len(rr) == 0:
                continue
            metrics, _ = _compute_metrics_with_settings(rr, self._settings_bar)
            self._main_window._results_store.add_metric_row(
                MetricRow(
                    mode="group",
                    dataset=ds.name,
                    section=sec_name,
                    n_beats=int(len(rr)),
                    metrics=dict(metrics),
                )
            )
            value = metrics.get(metric)
            if value is None or (isinstance(value, float) and math.isnan(value)):
                continue
            values_per_group.setdefault(label, []).append(float(value))

        # Need ≥2 groups WITH data
        non_empty = {k: v for k, v in values_per_group.items() if v}
        if len(non_empty) < 2:
            self._result_label.setText(
                "<span style='color:#d62728'><b>Need ≥2 groups with at least "
                "1 valid value each.</b></span> Assign labels in the table above."
            )
            self._group_stats_table.setRowCount(0)
            return

        try:
            result = compare_groups(
                non_empty,
                metric=metric,
                section=sec_name,
            )
        except Exception as e:
            self._result_label.setText(
                f"<span style='color:#d62728'>Comparison failed: {e}</span>"
            )
            return

        # Render
        sig_color = "#2ca02c" if result.p_value < 0.05 else "#555"
        effect_str = (
            f" · {result.effect_size_name} = <b>{result.effect_size:.3f}</b>"
            if result.effect_size is not None
            else ""
        )
        self._result_label.setText(
            f"<b>{result.test_name}</b> on <b>{metric}</b> in section "
            f"<b>{sec_name}</b><br>"
            f"statistic = <b>{result.statistic:.3f}</b>, "
            f"<span style='color:{sig_color}'>"
            f"p = <b>{result.p_value:.4f}</b> {result.significance}</span>"
            f"{effect_str}<br>"
            f"<small style='color:#777'>"
            f"{'parametric' if result.is_parametric else 'non-parametric'} test"
            f"{(' · ' + result.note) if result.note else ''}</small>"
        )

        self._group_stats_table.setRowCount(0)
        # Stats are about to populate — flip the empty-state stack.
        self._result_stack.setCurrentIndex(1)
        for group_name in result.groups:
            row = self._group_stats_table.rowCount()
            self._group_stats_table.insertRow(row)
            self._group_stats_table.setItem(row, 0, QTableWidgetItem(group_name))
            self._group_stats_table.setItem(
                row, 1, QTableWidgetItem(str(result.n_per_group[group_name]))
            )
            self._group_stats_table.setItem(
                row,
                2,
                QTableWidgetItem(_format_metric(result.means[group_name])),
            )
            self._group_stats_table.setItem(
                row,
                3,
                QTableWidgetItem(_format_metric(result.sds[group_name])),
            )
            norm_p = result.normality_p.get(group_name)
            self._group_stats_table.setItem(
                row,
                4,
                QTableWidgetItem(_format_metric(norm_p) if norm_p else "—"),
            )

        # Push the inferential test into the central results store; Results
        # tab picks it up.
        from rrational.inspector.results_store import GroupTestRow

        self._main_window._results_store.add_group_test_row(
            GroupTestRow(
                section=sec_name,
                metric=metric,
                test_name=result.test_name,
                statistic=float(result.statistic),
                p_value=float(result.p_value),
                effect_size_name=result.effect_size_name,
                effect_size=(
                    None if result.effect_size is None else float(result.effect_size)
                ),
                is_parametric=bool(result.is_parametric),
                groups=tuple(result.groups),
                n_per_group=dict(result.n_per_group),
            )
        )
        self._main_window._results_tab.refresh_results()
        self._refresh_plot_buttons_enabled()

    # ------------------------------------------------------------------
    # Group plots
    # ------------------------------------------------------------------
    def _group_label_by_dataset(self) -> dict[str, str]:
        """Snapshot of {dataset_name: group_label} for non-empty labels."""
        return {
            self._main_window._datasets[i].name: lbl
            for i, lbl in self._group_by_idx.items()
            if lbl and i < len(self._main_window._datasets)
        }

    def _build_long_df(self):
        """Flatten the results store to the long-format DF the group
        plot widgets expect."""
        from rrational.inspector.plots.group_charts import (
            results_store_to_long_df,
        )

        store = getattr(self._main_window, "_results_store", None)
        if store is None:
            import pandas as pd

            return pd.DataFrame()
        return results_store_to_long_df(
            store, group_label_by_dataset=self._group_label_by_dataset()
        )

    def _open_plot(self, kind: str) -> "_GroupPlotDialog | None":
        """Open a modal dialog hosting the requested group-comparison plot."""
        from rrational.inspector.plots.group_charts import (
            GroupBarChart,
            GroupBoxPlot,
            GroupViolinPlot,
            SD1SD2Scatter,
        )

        long_df = self._build_long_df()
        metric = self._metric_combo.currentText() or "RMSSD"

        if kind == "bar":
            widget = GroupBarChart(metric=metric, long_df=long_df)
            title = f"Bar chart — {metric}"
        elif kind == "box":
            widget = GroupBoxPlot(metric=metric, long_df=long_df)
            title = f"Box plot — {metric}"
        elif kind == "violin":
            widget = GroupViolinPlot(metric=metric, long_df=long_df)
            title = f"Violin plot — {metric}"
        elif kind == "sd":
            widget = SD1SD2Scatter(long_df=long_df)
            title = "SD1 vs SD2 scatter"
        else:  # defensive — kind comes from internal lambdas only
            return None

        dialog = _GroupPlotDialog(title, widget, parent=self)
        self._last_plot_dialog = dialog
        # In test_mode (or when running headless) we don't block the
        # test thread on exec(); show() lets pytest-qt drive interaction.
        if getattr(self._main_window, "test_mode", False):
            dialog.show()
        else:  # interactive use: modal exec_ blocks until closed
            try:
                dialog.exec_()
            except AttributeError:
                dialog.exec()
        return dialog

    # ------------------------------------------------------------------
    # F8: HTML report export
    # ------------------------------------------------------------------
    def _build_group_report_payload(self) -> dict:
        """Collect the results-store data needed for the HTML report."""
        from datetime import datetime

        store = self._main_window._results_store
        group_label_by_dataset = self._group_label_by_dataset()

        # Per-group descriptives: scan the metric_rows currently in the
        # store and bucket by the live group-label mapping.
        per_group: dict[str, dict[str, list[float]]] = {}
        for r in store.metric_rows:
            label = group_label_by_dataset.get(r.dataset)
            if not label:
                continue
            metric_bucket = per_group.setdefault(label, {})
            for m, v in r.metrics.items():
                if v is None:
                    continue
                try:
                    fv = float(v)
                except (TypeError, ValueError):
                    continue
                if math.isnan(fv) or math.isinf(fv):
                    continue
                metric_bucket.setdefault(m, []).append(fv)

        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "project_name": (
                self._main_window._project.metadata.name
                if getattr(self._main_window, "_project", None) is not None
                and self._main_window._project.metadata is not None
                else None
            ),
            "per_group_descriptives": per_group,
            "group_tests": list(store.group_test_rows),
        }

    def _on_generate_report(self) -> None:
        from pathlib import Path

        from rrational.inspector import settings as _settings
        from rrational.inspector.report import generate_group_analysis_html

        payload = self._build_group_report_payload()
        if getattr(self._main_window, "test_mode", False):
            # Don't pop dialogs in test mode — surface a status message
            # so tests can assert it without mocking QFileDialog.
            self._main_window.statusBar().showMessage(
                "Group HTML report ready (test mode — no file written).", 3000
            )
            return
        start_dir = _settings.read_setting("last_dir") or str(Path.cwd())
        suggested = str(Path(start_dir) / "group_analysis_report.html")
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save report",
            suggested,
            "HTML Files (*.html)",
        )
        if not path_str:
            return
        try:
            out_path = generate_group_analysis_html(payload, Path(path_str))
        except OSError as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        self._main_window.statusBar().showMessage(f"Saved report to {out_path}", 4000)


class _SequenceComparisonPane(QWidget):
    """Repeated-measures analysis across an ordered Sequence of sections.

    Pick a saved Sequence (defined in Setup tab), pick a metric, pick
    parametric/non-parametric — the pane computes the metric per section
    per dataset, then runs Friedman (default) or RM-ANOVA, plus all-pairwise
    post-hoc with Holm correction, plus a line chart of the per-dataset
    trajectories.
    """

    def __init__(self, main_window, parent=None) -> None:
        super().__init__(parent)
        self._main_window = main_window
        self._settings_bar: _AnalysisSettingsBar | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        # ---- Inputs --------------------------------------------------
        form_box = QGroupBox("Inputs")
        form = QFormLayout(form_box)
        self._sequence_combo = QComboBox()
        self._sequence_combo.currentIndexChanged.connect(self._on_sequence_changed)
        self._metric_combo = QComboBox()
        for m in _DEFAULT_METRICS:
            self._metric_combo.addItem(m)

        self._prefer_parametric = QCheckBox(
            "Prefer parametric (RM-ANOVA) when normality + n >= 10"
        )
        form.addRow("Sequence:", self._sequence_combo)
        form.addRow("Metric:", self._metric_combo)
        form.addRow("", self._prefer_parametric)
        outer.addWidget(form_box)

        # Sequence preview label — shows the chain of section names
        self._sequence_preview = QLabel("<i>No sequence selected.</i>")
        self._sequence_preview.setWordWrap(True)
        self._sequence_preview.setStyleSheet("color: #666; padding: 4px;")
        outer.addWidget(self._sequence_preview)

        button_row = QHBoxLayout()
        self._compute_btn = QPushButton("Run repeated-measures comparison")
        self._compute_btn.clicked.connect(self._on_compute)
        self._compute_btn.setEnabled(False)
        button_row.addWidget(self._compute_btn)
        button_row.addStretch()
        outer.addLayout(button_row)

        # ---- Result label (omnibus test summary) ---------------------
        self._result_label = QLabel(
            "<i>Define a sequence in the Setup tab, then pick it above + "
            "click <b>Run repeated-measures comparison</b>.</i>"
        )
        self._result_label.setWordWrap(True)
        self._result_label.setStyleSheet("padding: 8px;")
        outer.addWidget(self._result_label)

        # ---- Per-section descriptives --------------------------------
        outer.addWidget(QLabel("<b>Per-section descriptives</b>"))
        self._section_stats_table = QTableWidget(0, 5, self)
        self._section_stats_table.setHorizontalHeaderLabels(
            ["Section", "n", "Mean", "SD", "Normality (p)"]
        )
        self._section_stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._section_stats_table.setAlternatingRowColors(True)
        self._section_stats_table.verticalHeader().setVisible(False)
        self._section_stats_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self._section_stats_table.setMaximumHeight(180)
        self._result_stack = _wrap_table_with_hint(
            self._section_stats_table,
            "Define a sequence in the Setup tab, then click "
            "<b>Run repeated-measures comparison</b>.",
        )
        outer.addWidget(self._result_stack)

        # ---- Per-dataset line chart ----------------------------------
        outer.addWidget(QLabel("<b>Per-dataset trajectories</b>"))
        import pyqtgraph as pg

        self._plot_widget = pg.PlotWidget(background="w")
        self._plot_widget.setMinimumHeight(220)
        self._plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self._plot_widget.getAxis("left").setPen("k")
        self._plot_widget.getAxis("bottom").setPen("k")
        outer.addWidget(self._plot_widget, 1)

        # ---- Post-hoc table ------------------------------------------
        outer.addWidget(QLabel("<b>Post-hoc pairwise comparisons (Holm-corrected)</b>"))
        self._post_hoc_table = QTableWidget(0, 6, self)
        self._post_hoc_table.setHorizontalHeaderLabels(
            ["Section A", "Section B", "Test", "Statistic", "p (raw)", "p (Holm)"]
        )
        self._post_hoc_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._post_hoc_table.setAlternatingRowColors(True)
        self._post_hoc_table.verticalHeader().setVisible(False)
        self._post_hoc_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        outer.addWidget(self._post_hoc_table)

        # Initial population
        self.refresh_sequences()

    # ------------------------------------------------------------------
    # Workspace + sequences sync
    # ------------------------------------------------------------------
    def refresh_sequences(self) -> None:
        """Reload the dropdown from disk + setup-tab pane.

        We prefer the live in-memory list from the SetupTab's
        SequencesPane (so unsaved edits would show through too), but
        fall back to loading from disk if the setup tab isn't built yet.
        """
        prev = self._sequence_combo.currentText()
        setup_pane = getattr(self._main_window._setup_tab, "_sequences_pane", None)
        if setup_pane is not None:
            seqs = setup_pane.sequences
        else:
            from rrational.inspector.persistence import load_sequences

            seqs = load_sequences()

        self._sequence_combo.blockSignals(True)
        self._sequence_combo.clear()
        for s in seqs:
            self._sequence_combo.addItem(s.name, s)
        if prev:
            idx = self._sequence_combo.findText(prev)
            if idx >= 0:
                self._sequence_combo.setCurrentIndex(idx)
        self._sequence_combo.blockSignals(False)
        self._on_sequence_changed(self._sequence_combo.currentIndex())

    def refresh_workspace(self) -> None:
        # The compute button depends on having datasets loaded.
        self._refresh_compute_enabled()

    def _on_sequence_changed(self, _idx: int) -> None:
        seq = self._sequence_combo.currentData()
        if seq is None:
            self._sequence_preview.setText("<i>No sequence selected.</i>")
        else:
            self._sequence_preview.setText(
                "<b>Sections:</b> " + " → ".join(seq.sections)
            )
        self._refresh_compute_enabled()

    def _refresh_compute_enabled(self) -> None:
        has_seq = self._sequence_combo.currentData() is not None
        has_data = len(self._main_window._datasets) > 0
        self._compute_btn.setEnabled(has_seq and has_data)

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------
    def _on_compute(self) -> None:
        from rrational.analysis.sequence_statistics import analyze_sequence
        from rrational.inspector.results_store import SequenceTestRow

        seq = self._sequence_combo.currentData()
        metric = self._metric_combo.currentText()
        if seq is None or not metric:
            return

        # Build {section: [per-subject metric values]} — subject order
        # = dataset order so subject i is dataset i across every section.
        values_per_section: dict[str, list[float]] = {s: [] for s in seq.sections}
        exclusions = _active_exclusion_zones(self._main_window)
        for ds in self._main_window._datasets:
            for s in seq.sections:
                rr = _slice_section(ds.data, s, exclusions=exclusions)
                if rr is None or len(rr) == 0:
                    values_per_section[s].append(float("nan"))
                    continue
                metrics, _ = _compute_metrics_with_settings(rr, self._settings_bar)
                v = metrics.get(metric)
                values_per_section[s].append(
                    float("nan")
                    if v is None or (isinstance(v, float) and math.isnan(v))
                    else float(v)
                )

        try:
            result = analyze_sequence(
                values_per_section,
                sequence_name=seq.name,
                metric=metric,
                sections=list(seq.sections),
                prefer_parametric=self._prefer_parametric.isChecked(),
            )
        except Exception as e:
            self._result_label.setText(
                f"<span style='color:#d62728'>Analysis failed: {e}</span>"
            )
            return

        self._render_result(result, values_per_section)

        # Push into central results store
        self._main_window._results_store.add_sequence_test_row(
            SequenceTestRow(
                sequence_name=result.sequence_name,
                metric=result.metric,
                sections=tuple(result.sections),
                n_complete_subjects=result.n_complete_subjects,
                test_name=result.test_name,
                statistic=float(result.statistic)
                if not math.isnan(result.statistic)
                else float("nan"),
                p_value=float(result.p_value)
                if not math.isnan(result.p_value)
                else float("nan"),
                effect_size_name=result.effect_size_name,
                effect_size=float(result.effect_size)
                if not math.isnan(result.effect_size)
                else float("nan"),
                is_parametric=bool(result.is_parametric),
            )
        )
        self._main_window._results_tab.refresh_results()

    def _render_result(
        self, result, values_per_section: dict[str, list[float]]
    ) -> None:
        # ----- Omnibus result label -----
        if math.isnan(result.p_value):
            sig_color = "#888"
            p_str = "—"
        else:
            sig_color = "#2ca02c" if result.p_value < 0.05 else "#555"
            p_str = f"{result.p_value:.4f}"

        if math.isnan(result.effect_size):
            effect_str = ""
        else:
            effect_str = (
                f" · {result.effect_size_name} = <b>{result.effect_size:.3f}</b>"
            )

        df_str = ""
        if isinstance(result.df, tuple):
            df_str = f"<small> (df={int(result.df[0])}, {int(result.df[1])})</small>"
        elif result.df:
            df_str = f"<small> (df={int(result.df)})</small>"

        self._result_label.setText(
            f"<b>{result.test_name}</b> on <b>{result.metric}</b> across "
            f"<b>{result.sequence_name}</b> "
            f"({result.n_complete_subjects} complete subjects"
            f"{', ' + str(result.n_excluded_subjects) + ' excluded' if result.n_excluded_subjects else ''})"
            f"<br>statistic = <b>{result.statistic:.3f}</b>{df_str}, "
            f"<span style='color:{sig_color}'>p = <b>{p_str}</b> {result.significance}</span>"
            f"{effect_str}<br>"
            f"<small style='color:#777'>"
            f"{'parametric' if result.is_parametric else 'non-parametric'} test"
            f"{(' · ' + result.note) if result.note else ''}</small>"
        )

        # ----- Per-section descriptives table -----
        self._section_stats_table.setRowCount(0)
        self._result_stack.setCurrentIndex(1)
        for s in result.sections:
            row = self._section_stats_table.rowCount()
            self._section_stats_table.insertRow(row)
            n = sum(
                1
                for v in values_per_section[s]
                if not (v is None or (isinstance(v, float) and math.isnan(v)))
            )
            self._section_stats_table.setItem(row, 0, QTableWidgetItem(s))
            self._section_stats_table.setItem(row, 1, QTableWidgetItem(str(n)))
            self._section_stats_table.setItem(
                row, 2, QTableWidgetItem(_format_metric(result.means.get(s)))
            )
            self._section_stats_table.setItem(
                row, 3, QTableWidgetItem(_format_metric(result.sds.get(s)))
            )
            norm_p = result.normality_p.get(s)
            self._section_stats_table.setItem(
                row,
                4,
                QTableWidgetItem(_format_metric(norm_p) if norm_p else "—"),
            )

        # ----- Line chart -----
        import pyqtgraph as pg

        self._plot_widget.clear()
        n_subjects = max((len(vals) for vals in values_per_section.values()), default=0)
        # X positions = 1..len(sections); tick labels = section names
        x_positions = list(range(1, len(result.sections) + 1))
        ax = self._plot_widget.getAxis("bottom")
        ax.setTicks([list(zip(x_positions, result.sections))])
        # One curve per dataset (subject). Use a colormap to distinguish.
        colormap = pg.colormap.get("CET-C7")  # smooth perceptual
        for i in range(n_subjects):
            ys = []
            xs = []
            for j, s in enumerate(result.sections):
                vals = values_per_section[s]
                if i < len(vals):
                    v = vals[i]
                    if not (v is None or (isinstance(v, float) and math.isnan(v))):
                        ys.append(v)
                        xs.append(x_positions[j])
            if not ys:
                continue
            color = colormap.map(i / max(1, n_subjects - 1), mode="qcolor")
            name = (
                self._main_window._datasets[i].name
                if i < len(self._main_window._datasets)
                else f"S{i}"
            )
            self._plot_widget.plot(
                xs,
                ys,
                pen=pg.mkPen(color, width=2),
                symbol="o",
                symbolBrush=color,
                symbolSize=7,
                name=name,
            )
        self._plot_widget.setLabel("left", f"{result.metric}")
        self._plot_widget.setLabel("bottom", "Section (in sequence order)")

        # ----- Post-hoc table -----
        self._post_hoc_table.setRowCount(0)
        for pair in result.post_hoc:
            row = self._post_hoc_table.rowCount()
            self._post_hoc_table.insertRow(row)
            self._post_hoc_table.setItem(row, 0, QTableWidgetItem(pair.section_a))
            self._post_hoc_table.setItem(row, 1, QTableWidgetItem(pair.section_b))
            self._post_hoc_table.setItem(row, 2, QTableWidgetItem(pair.test_name))
            self._post_hoc_table.setItem(
                row, 3, QTableWidgetItem(_format_metric(pair.statistic))
            )
            self._post_hoc_table.setItem(
                row, 4, QTableWidgetItem(_format_metric(pair.p_value_raw))
            )
            self._post_hoc_table.setItem(
                row, 5, QTableWidgetItem(_format_metric(pair.p_value_corrected))
            )


class AnalysisTab(InspectorTab):
    TAB_LABEL = "Analysis"

    def __init__(self, main_window, parent=None) -> None:
        from rrational.inspector.help_widgets import HelpExpander

        super().__init__(main_window, parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        # Top-of-tab HRV basics expander. Content adapted from
        # gui/help_text.ANALYSIS_HELP — kept short here, defers to the
        # Streamlit reference for the deep-dive.
        outer.addWidget(
            HelpExpander(
                "HRV Analysis basics",
                (
                    "<p><b>Heart Rate Variability (HRV)</b> quantifies the "
                    "variation in time between heartbeats. Higher HRV "
                    "generally indicates better autonomic function.</p>"
                    "<p><b>Time-domain metrics</b> "
                    "(RMSSD, SDNN, pNN50) are the most robust and need "
                    "~100+ beats / 2+ min of clean data.</p>"
                    "<p><b>Frequency-domain metrics</b> "
                    "(HF, LF, LF/HF) are sensitive to artifacts — keep "
                    "artifact rate &lt;2% and use 5+ min of recording "
                    "(Quigley 2024).</p>"
                    "<p>Pick a <b>Mode</b> below, then choose a metric "
                    "preset in the settings bar above and click "
                    "<b>Compute</b>. Results land on the <i>Results</i> tab.</p>"
                ),
            )
        )

        # Settings bar lives at the top, visible across every mode.
        self._settings_bar = _AnalysisSettingsBar(self)
        outer.addWidget(self._settings_bar)

        # Mode selector — switches the stacked widget below.
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self._mode_combo = QComboBox()
        self._mode_combo.setToolTip("Pick the analysis flavour to compute below.")
        self._mode_combo.addItem("Single Participant", "single")
        self._mode_combo.addItem("Repeating Section", "repeating")
        self._mode_combo.addItem("Group comparison", "group")
        self._mode_combo.addItem("Sequence Comparison", "sequence")
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        mode_row.addWidget(self._mode_combo)
        mode_row.addStretch()

        # Analysis report export — generates a Markdown report from the
        # current ResultsStore + workspace state.
        self._export_report_btn = QPushButton("Export analysis report...")
        self._export_report_btn.setToolTip(
            "Write a Markdown report summarising the data source, cleaning "
            "config, artifact correction, exclusion zones and per-section "
            "HRV metrics. Mirrors the Streamlit AnalysisDocumentation export."
        )
        self._export_report_btn.clicked.connect(self._on_export_report)
        mode_row.addWidget(self._export_report_btn)
        outer.addLayout(mode_row)

        self._stack = QStackedWidget(self)
        self._single_pane = _SingleParticipantPane(main_window, self)
        self._repeating_pane = _RepeatingSectionPane(main_window, self)
        self._group_pane = _GroupComparisonPane(main_window, self)
        self._sequence_pane = _SequenceComparisonPane(main_window, self)
        # Wire every pane to the shared settings bar so they all honour
        # the same preset / freq method / window choices.
        for pane in (
            self._single_pane,
            self._repeating_pane,
            self._group_pane,
            self._sequence_pane,
        ):
            pane._settings_bar = self._settings_bar
        self._stack.addWidget(self._single_pane)
        self._stack.addWidget(self._repeating_pane)
        self._stack.addWidget(self._group_pane)
        self._stack.addWidget(self._sequence_pane)
        outer.addWidget(self._stack)

    def _on_mode_changed(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # Notification hooks
    # ------------------------------------------------------------------
    def tab_label_state(self) -> str:
        n = len(self._main_window._datasets)
        return f"({n} loaded)" if n else ""

    def on_workspace_changed(self) -> None:
        self._single_pane.refresh_workspace()
        self._repeating_pane.refresh_workspace()
        self._group_pane.refresh_workspace()
        self._sequence_pane.refresh_workspace()

    def on_active_dataset_changed(self, data: "InspectorData | None") -> None:
        # Single-Participant pane defaults to whatever's currently active;
        # easiest is to re-sync from the workspace each time.
        self._single_pane.refresh_workspace()
        if data is not None:
            idx = self._main_window._active_idx
            if idx is not None:
                self._single_pane._dataset_combo.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # Markdown analysis report
    # ------------------------------------------------------------------
    def build_analysis_report_markdown(self) -> str:
        """Return a Markdown report summarising the current analysis.

        Reuses :class:`rrational.inspector.report.ReportBuilder` so the
        per-tab "Export analysis report..." button stays in lock-step
        with the project-level publication report.
        """
        from rrational.inspector.report import ReportBuilder

        return ReportBuilder(self._main_window).build_markdown()

    def _on_export_report(self) -> None:
        from pathlib import Path

        from rrational.inspector import settings as _settings

        text = self.build_analysis_report_markdown()
        if getattr(self._main_window, "test_mode", False):
            self._main_window.statusBar().showMessage(
                f"Analysis report ready ({len(text)} chars).", 3000
            )
            return
        start_dir = _settings.read_setting("last_dir") or str(Path.cwd())
        suggested = str(Path(start_dir) / "analysis_report.md")
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export analysis report",
            suggested,
            "Markdown (*.md);;All files (*)",
        )
        if not path_str:
            return
        try:
            Path(path_str).write_text(text, encoding="utf-8")
        except OSError as e:
            QMessageBox.warning(self, "Export failed", str(e))
            return
        self._main_window.statusBar().showMessage(
            f"Exported analysis report to {path_str}", 4000
        )
