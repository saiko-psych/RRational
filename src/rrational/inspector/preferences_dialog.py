"""Inspector Preferences dialog — currently only Color Scheme tab.

Lets the user pick a built-in preset (Scientific / Colorful / High
Contrast / Monochrome / Pastel) or override individual colours via
per-element swatches. Picking a preset snaps every swatch to that
preset's colours; clicking a swatch and choosing a new colour switches
the preset dropdown to "Custom" without otherwise touching the other
swatches.

OK / Apply both persist to ``~/.rrational/inspector/color_scheme.yml``
and call the supplied ``apply_callback`` so the plot re-skins live.
Cancel discards the in-dialog edits without touching disk OR the plot.
"""

from __future__ import annotations

from collections.abc import Callable

from qtpy.QtCore import Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rrational.gui.color_scheme import PRESET_THEMES, ColorScheme
from rrational.inspector.color_scheme_persistence import (
    CUSTOM_PRESET_NAME,
    save_color_scheme,
)
from rrational.inspector.palette import OKABE_ITO
from rrational.inspector.settings import read_setting, write_setting

# Per-element fields exposed as swatches. Order = display order.
_SCALAR_FIELDS: list[tuple[str, str]] = [
    ("rr_line", "RR line"),
    ("artifact", "Artifact dots"),
    ("nn_line", "NN line"),
    ("exclusion", "Exclusion zone"),
    ("event_marker", "Event marker"),
    ("section_fill", "Section fill"),
    ("section_border", "Section border"),
    ("vlf_band", "VLF band"),
    ("lf_band", "LF band"),
    ("hf_band", "HF band"),
]

_SWATCH_SIZE = 28  # pixels per swatch button


def _parse_color(value: str) -> QColor:
    """Best-effort QColor parse — falls back to opaque grey on garbage.

    Accepts ``"#rrggbb"`` and ``"rgba(r, g, b, a_float)"`` (used by the
    preset section_fill / *_band values).
    """
    s = value.strip()
    if s.lower().startswith("rgba"):
        inside = s[s.index("(") + 1 : s.rindex(")")]
        parts = [p.strip() for p in inside.split(",")]
        if len(parts) == 4:
            try:
                r, g, b = (int(float(p)) for p in parts[:3])
                a = float(parts[3])
                a_int = max(0, min(255, int(round(a * 255)) if a <= 1 else int(a)))
                return QColor(r, g, b, a_int)
            except (TypeError, ValueError):
                return QColor("#808080")
    c = QColor(s)
    if not c.isValid():
        return QColor("#808080")
    return c


def _to_hex(color: QColor) -> str:
    """Serialize a QColor back to ``"#rrggbb"`` for scalar fields."""
    return color.name(QColor.HexRgb)


def _to_rgba_str(color: QColor) -> str:
    """Serialize a QColor back to ``rgba(r, g, b, a)`` for translucent fields."""
    a = color.alphaF()
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {a:.2f})"


_TRANSLUCENT_FIELDS = {"section_fill", "vlf_band", "lf_band", "hf_band"}


def _serialize_field(field: str, color: QColor) -> str:
    if field in _TRANSLUCENT_FIELDS:
        return _to_rgba_str(color)
    return _to_hex(color)


class _Swatch(QPushButton):
    """A small coloured button that opens QColorDialog on click."""

    def __init__(
        self,
        parent: QWidget | None,
        initial: QColor,
        on_picked: Callable[[QColor], None],
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(_SWATCH_SIZE, _SWATCH_SIZE)
        self.setCursor(Qt.PointingHandCursor)
        self._on_picked = on_picked
        self.set_color(initial)
        self.clicked.connect(self._open_picker)

    def set_color(self, color: QColor) -> None:
        self._color = QColor(color)
        # Round 27 — ``self._color.name(QColor.HexRgb)`` silently strips
        # the alpha channel. A translucent field like ``section_fill``
        # (10% alpha) was rendered as a fully opaque swatch, and on the
        # first innocent re-click the picker re-opened with alpha=1.00,
        # permanently destroying the transparency on round-trip. Emit
        # rgba() so the displayed swatch matches the underlying value.
        # Note: Qt 8-digit hex parses as #AARRGGBB so we MUST NOT use
        # HexArgb here — see [[feedback_qt_css_hex]].
        r, g, b, a = (
            self._color.red(),
            self._color.green(),
            self._color.blue(),
            self._color.alphaF(),
        )
        self.setStyleSheet(
            f"background-color: rgba({r}, {g}, {b}, {a:.3f}); border: 1px solid #555;"
        )

    def color(self) -> QColor:
        return QColor(self._color)

    def _open_picker(self) -> None:
        chosen = QColorDialog.getColor(
            self._color, self, "Pick colour", QColorDialog.ShowAlphaChannel
        )
        if chosen.isValid():
            self.set_color(chosen)
            self._on_picked(chosen)


class PreferencesDialog(QDialog):
    """Modal Preferences dialog — currently Color Scheme only.

    Constructor takes the CURRENT (preset_name, scheme) pair and an
    ``apply_callback`` invoked on OK/Apply with the chosen pair. The
    callback is responsible for re-applying to the live plot — the
    dialog itself only handles persistence.
    """

    def __init__(
        self,
        parent: QWidget | None,
        current_preset: str,
        current_scheme: ColorScheme,
        apply_callback: Callable[[str, ColorScheme], None],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setMinimumWidth(440)

        self._apply_callback = apply_callback
        # Working copy — only flushed to disk / callback on OK or Apply.
        self._preset_name = current_preset
        self._scheme = ColorScheme.from_dict(current_scheme.to_dict())

        outer = QVBoxLayout(self)

        # ----- Preset selector ------------------------------------------------
        preset_box = QGroupBox("Color scheme")
        preset_layout = QFormLayout(preset_box)
        self._preset_combo = QComboBox()
        # Build the dropdown: every preset, then a final "Custom" entry.
        preset_names = sorted(PRESET_THEMES.keys())
        for name in preset_names:
            self._preset_combo.addItem(name)
        self._preset_combo.addItem(CUSTOM_PRESET_NAME)
        self._sync_combo_to_state()
        self._preset_combo.currentTextChanged.connect(self._on_preset_changed)
        preset_layout.addRow("Preset:", self._preset_combo)

        # Cluster A5 — Okabe-Ito colorblind-safe toggle. Persists via
        # QSettings (so the choice survives across sessions even when
        # the active preset is swapped) and re-writes the working-copy
        # group_palette immediately for live preview.
        self._cb_safe = QCheckBox("Colorblind-safe palette (Okabe-Ito)")
        try:
            self._cb_safe.setChecked(bool(read_setting("colorblind_safe_palette")))
        except KeyError:
            self._cb_safe.setChecked(False)
        self._cb_safe.toggled.connect(self._on_colorblind_toggled)
        preset_layout.addRow("", self._cb_safe)
        outer.addWidget(preset_box)

        # ----- Per-element swatches -------------------------------------------
        swatch_box = QGroupBox("Per-element overrides")
        swatch_form = QFormLayout(swatch_box)
        self._scalar_swatches: dict[str, _Swatch] = {}
        for field, label in _SCALAR_FIELDS:
            value = getattr(self._scheme, field)
            initial = _parse_color(value)
            swatch = _Swatch(self, initial, self._on_scalar_swatch_picked(field))
            self._scalar_swatches[field] = swatch
            swatch_form.addRow(label + ":", swatch)
        outer.addWidget(swatch_box)

        # ----- Group palette row (8 swatches in a row) -----------------------
        palette_box = QGroupBox("Group palette")
        palette_outer = QVBoxLayout(palette_box)
        palette_row = QHBoxLayout()
        palette_row.setSpacing(4)
        self._palette_swatches: list[_Swatch] = []
        for idx, hex_str in enumerate(self._scheme.group_palette):
            sw = _Swatch(
                self, _parse_color(hex_str), self._on_palette_swatch_picked(idx)
            )
            self._palette_swatches.append(sw)
            palette_row.addWidget(sw)
        palette_row.addStretch()
        palette_outer.addLayout(palette_row)
        palette_outer.addWidget(
            QLabel("<small>Used to colour groups in Group Comparison plots.</small>")
        )
        outer.addWidget(palette_box)

        # ----- OK / Apply / Cancel -------------------------------------------
        bb = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Apply | QDialogButtonBox.Cancel
        )
        bb.accepted.connect(self._on_ok)
        bb.rejected.connect(self.reject)
        bb.button(QDialogButtonBox.Apply).clicked.connect(self._on_apply)
        outer.addWidget(bb)

    # ------------------------------------------------------------------
    # Internal state helpers
    # ------------------------------------------------------------------
    def _sync_combo_to_state(self) -> None:
        """Block signals while we update the dropdown to ``self._preset_name``."""
        idx = self._preset_combo.findText(self._preset_name)
        if idx < 0:
            idx = self._preset_combo.findText(CUSTOM_PRESET_NAME)
        self._preset_combo.blockSignals(True)
        self._preset_combo.setCurrentIndex(idx)
        self._preset_combo.blockSignals(False)

    def _refresh_swatches_from_scheme(self) -> None:
        for field, swatch in self._scalar_swatches.items():
            swatch.set_color(_parse_color(getattr(self._scheme, field)))
        for idx, sw in enumerate(self._palette_swatches):
            if idx < len(self._scheme.group_palette):
                sw.set_color(_parse_color(self._scheme.group_palette[idx]))

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_preset_changed(self, name: str) -> None:
        if name == CUSTOM_PRESET_NAME:
            self._preset_name = CUSTOM_PRESET_NAME
            return
        if name not in PRESET_THEMES:
            return
        self._preset_name = name
        # Deep copy the preset so subsequent swatch edits don't mutate it.
        self._scheme = ColorScheme.from_dict(PRESET_THEMES[name].to_dict())
        # If the user has the colorblind-safe palette enabled, the preset
        # swap should respect that — overwrite the preset's group_palette
        # with the Okabe-Ito set rather than silently ignoring the toggle.
        if self._cb_safe.isChecked():
            self._scheme.group_palette = list(OKABE_ITO)
        self._refresh_swatches_from_scheme()

    def _on_colorblind_toggled(self, enabled: bool) -> None:
        """Swap the working-copy group_palette to/from Okabe-Ito.

        Persists the flag immediately so the next session opens in the
        same state even if the user dismisses the dialog with Cancel.
        Switching off restores the active preset's native palette
        (or leaves the working copy alone if the preset is "Custom").
        Does NOT switch the preset name to "Custom" — the Okabe-Ito
        swap is a meta-overlay on top of any preset, not a custom
        per-element edit.
        """
        write_setting("colorblind_safe_palette", bool(enabled))
        if enabled:
            self._scheme.group_palette = list(OKABE_ITO)
        elif self._preset_name in PRESET_THEMES:
            preset = PRESET_THEMES[self._preset_name]
            self._scheme.group_palette = list(preset.group_palette)
        # When _preset_name is "Custom" with the toggle going off, we
        # leave the current swatches alone: the user has explicit colour
        # choices we should not silently overwrite.
        self._refresh_swatches_from_scheme()

    def _on_scalar_swatch_picked(self, field: str) -> Callable[[QColor], None]:
        def _cb(color: QColor) -> None:
            setattr(self._scheme, field, _serialize_field(field, color))
            self._switch_to_custom()

        return _cb

    def _on_palette_swatch_picked(self, idx: int) -> Callable[[QColor], None]:
        def _cb(color: QColor) -> None:
            new_palette = list(self._scheme.group_palette)
            if idx < len(new_palette):
                new_palette[idx] = _to_hex(color)
                self._scheme.group_palette = new_palette
                self._switch_to_custom()

        return _cb

    def _switch_to_custom(self) -> None:
        if self._preset_name == CUSTOM_PRESET_NAME:
            return
        self._preset_name = CUSTOM_PRESET_NAME
        self._sync_combo_to_state()

    # ------------------------------------------------------------------
    # OK / Apply / Cancel
    # ------------------------------------------------------------------
    def _on_apply(self) -> None:
        save_color_scheme(self._preset_name, self._scheme)
        self._apply_callback(self._preset_name, self._scheme)

    def _on_ok(self) -> None:
        self._on_apply()
        self.accept()

    # ------------------------------------------------------------------
    # Public read-back for tests
    # ------------------------------------------------------------------
    def current_pair(self) -> tuple[str, ColorScheme]:
        return self._preset_name, ColorScheme.from_dict(self._scheme.to_dict())
