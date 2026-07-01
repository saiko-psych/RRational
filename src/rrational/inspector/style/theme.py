"""Central application theme (QSS) for the RRational Inspector.

Two cohesive themes ("dark" and "light") expose the same selectors so
switching at runtime is a single ``setStyleSheet`` call. Palette tokens
are named — change a colour in one place and every widget updates.

Aesthetic direction is "Refined Laboratory": think a high-end
scientific instrument display panel — restrained, warm, technical
without being cold. Modern data tool aesthetic in the spirit of
JupyterLab and Linear with a hint of vintage oscilloscope. NOT the
generic Bootstrap-blue SaaS dashboard look.

Conventions used by callers:

* ``btn.setProperty("primary", True)`` marks a button as a primary
  action — the QSS picks it up via ``QPushButton[primary="true"]`` and
  applies the amber accent fill. After flipping the property the call
  site must re-polish the widget so QSS re-evaluates the selectors::

      btn.setProperty("primary", True)
      btn.style().unpolish(btn)
      btn.style().polish(btn)

* ``label.setProperty("muted", True)`` paints a label with the
  secondary text colour — used for captions / hints. Same re-polish
  protocol applies.

Typography uses a smart fallback chain so we never ship fonts: the
system picks the best-available across IBM Plex Sans / Segoe UI
Variable / SF Pro Text. Body copy is 13px at default DPI.

Spacing rhythm is a 4px base unit: 4, 8, 12, 16, 20, 24… The QSS
defines a consistent rhythm for QGroupBox / QPushButton / QTabBar /
QHeaderView so individual call sites don't need per-widget overrides.
"""

from __future__ import annotations

from qtpy.QtWidgets import QApplication

# ---------------------------------------------------------------------------
# Palettes
# ---------------------------------------------------------------------------
# Keys are kept identical between palettes so the QSS template can use the
# same lookup names. Hex strings use lower-case to keep diffs readable.

_DARK: dict[str, str] = {
    # Surface stack — base behind everything, surface on panels, elevated
    # on hover / table headers. Each step is a few graphite shades up.
    "bg_base": "#1a1d22",
    "bg_surface": "#232830",
    "bg_elevated": "#2a3038",
    "border_subtle": "#2f343d",
    "border_strong": "#3d4350",
    # Text stack — warm off-white at full brightness, soft greys for
    # secondary copy. WCAG AA: text_primary on bg_base contrast ~13:1,
    # text_secondary on bg_surface ~5.5:1, text_muted on bg_surface ~3.4:1.
    "text_primary": "#eaecef",
    "text_secondary": "#a8adb5",
    "text_muted": "#6e7480",
    # Accent — warm amber, used sparingly for primary actions + focus
    # rings. The "soft" suffix is the same hue at ~13% alpha so hovers
    # tint without overpowering.
    "accent": "#e8a13a",
    # Qt CSS parses 8-digit hex as #AARRGGBB, NOT #RRGGBBAA — the previous
    # "#e8a13a22" was interpreted as alpha=0xe8 + colour #a13a22 (blood
    # red at 91% opacity), which turned every QListWidget selection into
    # what looked like a hard error highlight. Use explicit rgba() so
    # the alpha channel is unambiguous.
    "accent_soft": "rgba(232, 161, 58, 0.13)",
    "accent_hover": "#f0ad4d",
    "accent_pressed": "#c98a2a",
    # Status colours — desaturated to feel like instrument LEDs instead
    # of standard web red/green.
    "success": "#5ab896",
    "warning": "#d4a04e",
    "danger": "#d97862",
    # Selection (when text is highlighted with the cursor).
    "selection_bg": "#3a4a5e",
    "selection_fg": "#ffffff",
    # Scrollbar handle.
    "scroll_handle": "#3a4047",
    "scroll_handle_hover": "#4a5158",
    # Alternating row tint (very subtle — keep contrast under 1.2:1 vs
    # surface so rows still read uniformly).
    "row_alt": "#262b33",
}

_LIGHT: dict[str, str] = {
    "bg_base": "#f8f6f1",
    "bg_surface": "#ffffff",
    "bg_elevated": "#f1ede4",
    "border_subtle": "#e3ddd0",
    "border_strong": "#c8c0ad",
    "text_primary": "#1f2228",
    "text_secondary": "#4a5160",
    "text_muted": "#7d8390",
    "accent": "#b87214",
    # See dark theme comment — Qt parses #RRGGBBAA as #AARRGGBB so the
    # previous "#b8721422" rendered as alpha=0xb8 + colour #721422
    # (dark plum at 72% opacity) on every selection. rgba() keeps the
    # intent explicit.
    "accent_soft": "rgba(184, 114, 20, 0.13)",
    "accent_hover": "#c98423",
    "accent_pressed": "#9c5f0f",
    "success": "#2f8669",
    "warning": "#a06b18",
    "danger": "#b54a36",
    "selection_bg": "#f0e2c4",
    "selection_fg": "#1f2228",
    "scroll_handle": "#cdc6b6",
    "scroll_handle_hover": "#b3aa97",
    "row_alt": "#fbf9f4",
}


# Font stacks — declared once so the QSS template can reuse them in
# multiple selectors without re-typing.
_FONT_BODY = (
    '"IBM Plex Sans", "Segoe UI Variable", "SF Pro Text", '
    '"Segoe UI", system-ui, sans-serif'
)
_FONT_MONO = '"JetBrains Mono", "IBM Plex Mono", "Cascadia Code", "Consolas", monospace'

# Pristine application-font point size, captured on the first ``apply_app_theme``
# call (before any zoom scaling touches the app font). 0.0 means "not yet
# captured". Anchoring the UI-zoom scale to this fixed base keeps repeated
# zoom-in/out keypresses from compounding — see ``apply_app_theme``.
_BASE_FONT_PT: float = 0.0


def _qss_for(p: dict[str, str], scale: float = 1.0) -> str:
    """Render the full QSS string with the given palette ``p``.

    The output is one long string deliberately — Qt parses the whole
    sheet in one pass, and keeping it in a single f-string makes the
    cascade easy to read top-to-bottom.

    ``scale`` multiplies every ``font-size`` in the sheet so the whole UI
    can be zoomed for accessibility. It must scale the QSS values (not just
    ``app.setFont``) because the base ``QWidget {{ font-size }}`` rule wins
    over the application font for every styled widget. QStyleSheetStyle also
    sizes widgets (tab widths, button heights) from these values, so scaling
    them keeps the chrome laid out correctly around the larger text.
    """
    # Clamp so a corrupted persisted value can never produce an unreadable or
    # absurd sheet; floor each result so tiny scales stay legible.
    scale = min(2.0, max(0.7, float(scale)))
    body_px = max(9, round(13 * scale))
    caption_px = max(8, round(11 * scale))
    return f"""
    /* ===================== Base ===================== */
    QWidget {{
        background-color: {p["bg_base"]};
        color: {p["text_primary"]};
        font-family: {_FONT_BODY};
        font-size: {body_px}px;
        selection-background-color: {p["selection_bg"]};
        selection-color: {p["selection_fg"]};
    }}

    QMainWindow, QDialog {{
        background-color: {p["bg_base"]};
    }}

    QToolTip {{
        background-color: {p["bg_elevated"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border_strong"]};
        padding: 4px 8px;
    }}

    /* ===================== Menu bar / context menus ===================== */
    QMenuBar {{
        background-color: {p["bg_base"]};
        color: {p["text_primary"]};
        border-bottom: 1px solid {p["border_subtle"]};
        padding: 2px 4px;
    }}
    QMenuBar::item {{
        background: transparent;
        padding: 6px 12px;
        border-radius: 3px;
    }}
    QMenuBar::item:selected {{
        background-color: {p["accent_soft"]};
        color: {p["text_primary"]};
    }}

    QMenu {{
        background-color: {p["bg_surface"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border_strong"]};
        padding: 4px 0;
    }}
    QMenu::item {{
        padding: 6px 22px 6px 22px;
        background: transparent;
    }}
    QMenu::item:selected {{
        background-color: {p["accent_soft"]};
        color: {p["text_primary"]};
    }}
    QMenu::item:disabled {{
        color: {p["text_muted"]};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {p["border_subtle"]};
        margin: 4px 8px;
    }}

    /* ===================== Status bar ===================== */
    QStatusBar {{
        background-color: {p["bg_base"]};
        color: {p["text_secondary"]};
        border-top: 1px solid {p["border_subtle"]};
        padding: 2px 8px;
    }}
    QStatusBar::item {{
        border: none;
    }}

    /* ===================== Tabs ===================== */
    QTabWidget::pane {{
        background-color: {p["bg_surface"]};
        border: 1px solid {p["border_subtle"]};
        border-radius: 4px;
        top: -1px;
    }}
    QTabBar {{
        background: transparent;
        qproperty-drawBase: 0;
    }}
    QTabBar::tab {{
        background-color: {p["bg_base"]};
        color: {p["text_secondary"]};
        /* ``letter-spacing`` was removed here (it was 0.3px): Qt's
           QStyleSheetStyle reserves the tab width from the base font metrics
           and does NOT add letter-spacing, but paints it — so long labels
           ("Participants  (44)") drew wider than the reserved rect and
           clipped at both ends. The generous 20px horizontal padding stays as
           a defensive margin so minor font/DPI rounding never re-clips. See
           also ``QTabBar::tab:selected``, which deliberately keeps the base
           font-weight for the same reason. */
        padding: 8px 20px;
        margin-right: 2px;
        border: 1px solid {p["border_subtle"]};
        border-bottom: none;
        border-top-left-radius: 4px;
        border-top-right-radius: 4px;
        min-width: 80px;
    }}
    QTabBar::tab:hover {{
        background-color: {p["bg_elevated"]};
        color: {p["text_primary"]};
    }}
    QTabBar::tab:selected {{
        background-color: {p["bg_surface"]};
        color: {p["text_primary"]};
        border-color: {p["border_strong"]};
        border-bottom: 1px solid {p["bg_surface"]};
        /* No ``font-weight`` change on select. Qt sizes every tab from the
           base (normal-weight) font metrics, so a heavier selected weight
           paints wider than the reserved rect and clips long labels
           ("Participants  (44)"). The selected tab is already distinguished
           by its lighter surface, brighter text, and stronger border — bold
           was redundant emphasis that cost us a guaranteed clip. */
    }}
    QTabBar::tab:disabled {{
        color: {p["text_muted"]};
    }}

    /* ===================== Docks ===================== */
    QDockWidget {{
        color: {p["text_primary"]};
        titlebar-close-icon: none;
        titlebar-normal-icon: none;
    }}
    QDockWidget::title {{
        text-align: left;
        background-color: {p["bg_elevated"]};
        color: {p["text_secondary"]};
        padding: 8px 12px;
        border: 1px solid {p["border_subtle"]};
        border-bottom: 1px solid {p["border_strong"]};
        font-weight: 600;
        letter-spacing: 0.3px;
    }}
    QDockWidget::close-button, QDockWidget::float-button {{
        background: transparent;
        border: none;
        padding: 2px;
    }}
    QDockWidget::close-button:hover, QDockWidget::float-button:hover {{
        background-color: {p["accent_soft"]};
    }}

    /* ===================== Group box ===================== */
    QGroupBox {{
        background-color: {p["bg_surface"]};
        border: 1px solid {p["border_subtle"]};
        border-radius: 4px;
        margin-top: 14px;
        padding: 18px 14px 12px 14px;
        font-weight: 600;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 12px;
        padding: 0 6px;
        color: {p["text_secondary"]};
        background-color: {p["bg_base"]};
        text-transform: uppercase;
        letter-spacing: 0.3px;
        font-size: {caption_px}px;
    }}
    QGroupBox::indicator {{
        width: 14px;
        height: 14px;
    }}

    /* ===================== Buttons ===================== */
    QPushButton {{
        background-color: {p["bg_elevated"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border_strong"]};
        border-radius: 4px;
        padding: 6px 14px;
        min-height: 18px;
    }}
    QPushButton:hover {{
        background-color: {p["accent_soft"]};
        border-color: {p["accent"]};
    }}
    QPushButton:pressed {{
        background-color: {p["accent_soft"]};
        border-color: {p["accent_pressed"]};
    }}
    QPushButton:focus {{
        border: 1px solid {p["accent"]};
        outline: none;
    }}
    QPushButton:disabled {{
        background-color: {p["bg_surface"]};
        color: {p["text_muted"]};
        border-color: {p["border_subtle"]};
    }}

    /* Primary-action variant — opt-in via setProperty("primary", True).
       Amber fill, white text. The hover state lightens; pressed darkens. */
    QPushButton[primary="true"] {{
        background-color: {p["accent"]};
        color: #ffffff;
        border: 1px solid {p["accent_pressed"]};
        font-weight: 600;
        padding: 7px 18px;
    }}
    QPushButton[primary="true"]:hover {{
        background-color: {p["accent_hover"]};
        border-color: {p["accent"]};
    }}
    QPushButton[primary="true"]:pressed {{
        background-color: {p["accent_pressed"]};
    }}
    QPushButton[primary="true"]:disabled {{
        background-color: {p["bg_elevated"]};
        color: {p["text_muted"]};
        border-color: {p["border_subtle"]};
    }}

    /* Flat variant — for inline links / recent-files list. setFlat(True)
       triggers the :flat pseudo state. */
    QPushButton:flat {{
        background: transparent;
        border: none;
        color: {p["accent"]};
        text-align: left;
        padding: 2px 8px;
    }}
    QPushButton:flat:hover {{
        color: {p["accent_hover"]};
        text-decoration: underline;
    }}

    QToolButton {{
        background-color: transparent;
        color: {p["text_secondary"]};
        border: 1px solid transparent;
        border-radius: 3px;
        padding: 4px;
    }}
    QToolButton:hover {{
        background-color: {p["accent_soft"]};
        color: {p["text_primary"]};
    }}
    QToolButton:pressed {{
        background-color: {p["accent_soft"]};
    }}

    /* ===================== Inputs ===================== */
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{
        background-color: {p["bg_base"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border_strong"]};
        border-radius: 3px;
        padding: 4px 8px;
        selection-background-color: {p["selection_bg"]};
        selection-color: {p["selection_fg"]};
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus,
    QTextEdit:focus, QPlainTextEdit:focus {{
        border: 1px solid {p["accent"]};
    }}
    QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
    QComboBox:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
        color: {p["text_muted"]};
        background-color: {p["bg_surface"]};
        border-color: {p["border_subtle"]};
    }}

    QComboBox::drop-down {{
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 18px;
        border-left: 1px solid {p["border_subtle"]};
    }}
    QComboBox QAbstractItemView {{
        background-color: {p["bg_surface"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border_strong"]};
        selection-background-color: {p["accent_soft"]};
        selection-color: {p["text_primary"]};
        outline: none;
    }}

    QSpinBox::up-button, QDoubleSpinBox::up-button {{
        subcontrol-origin: border;
        subcontrol-position: top right;
        width: 16px;
        border-left: 1px solid {p["border_subtle"]};
        border-bottom: 1px solid {p["border_subtle"]};
        background-color: {p["bg_elevated"]};
    }}
    QSpinBox::down-button, QDoubleSpinBox::down-button {{
        subcontrol-origin: border;
        subcontrol-position: bottom right;
        width: 16px;
        border-left: 1px solid {p["border_subtle"]};
        background-color: {p["bg_elevated"]};
    }}
    QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
    QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
        background-color: {p["accent_soft"]};
    }}

    /* ===================== Tables ===================== */
    QTableWidget, QTableView, QTreeWidget, QTreeView, QListWidget, QListView {{
        background-color: {p["bg_surface"]};
        alternate-background-color: {p["row_alt"]};
        color: {p["text_primary"]};
        border: 1px solid {p["border_subtle"]};
        border-radius: 3px;
        gridline-color: {p["border_subtle"]};
        outline: none;
    }}
    QTableWidget::item, QTableView::item, QTreeWidget::item, QTreeView::item,
    QListWidget::item, QListView::item {{
        padding: 4px 6px;
        border: none;
    }}
    QTableWidget::item:selected, QTableView::item:selected,
    QTreeWidget::item:selected, QTreeView::item:selected,
    QListWidget::item:selected, QListView::item:selected {{
        background-color: {p["accent_soft"]};
        color: {p["text_primary"]};
    }}
    QTableWidget::item:hover, QTableView::item:hover,
    QTreeWidget::item:hover, QTreeView::item:hover,
    QListWidget::item:hover, QListView::item:hover {{
        background-color: {p["bg_elevated"]};
    }}

    QHeaderView {{
        background-color: {p["bg_elevated"]};
        border: none;
    }}
    QHeaderView::section {{
        background-color: {p["bg_elevated"]};
        color: {p["text_secondary"]};
        padding: 6px 8px;
        border: none;
        border-right: 1px solid {p["border_subtle"]};
        border-bottom: 1px solid {p["border_strong"]};
        font-weight: 600;
        letter-spacing: 0.3px;
    }}
    QHeaderView::section:hover {{
        background-color: {p["bg_base"]};
        color: {p["text_primary"]};
    }}

    /* ===================== Check / radio ===================== */
    QCheckBox, QRadioButton {{
        color: {p["text_primary"]};
        spacing: 6px;
        background: transparent;
    }}
    QCheckBox:disabled, QRadioButton:disabled {{
        color: {p["text_muted"]};
    }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 14px;
        height: 14px;
        border: 1px solid {p["border_strong"]};
        background-color: {p["bg_base"]};
    }}
    QCheckBox::indicator {{
        border-radius: 2px;
    }}
    QRadioButton::indicator {{
        border-radius: 7px;
    }}
    QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
        border-color: {p["accent"]};
    }}
    QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
        background-color: {p["accent"]};
        border-color: {p["accent_pressed"]};
    }}
    QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
        border-color: {p["border_subtle"]};
        background-color: {p["bg_surface"]};
    }}

    /* ===================== Labels ===================== */
    QLabel {{
        background: transparent;
        color: {p["text_primary"]};
    }}
    QLabel[muted="true"] {{
        color: {p["text_secondary"]};
    }}
    QLabel[hint="true"] {{
        color: {p["text_muted"]};
        font-style: italic;
    }}
    QLabel[heading="true"] {{
        color: {p["text_primary"]};
        font-weight: 600;
        letter-spacing: 0.3px;
    }}

    /* ===================== Splitter ===================== */
    QSplitter::handle {{
        background-color: {p["border_subtle"]};
    }}
    QSplitter::handle:horizontal {{
        width: 6px;
    }}
    QSplitter::handle:vertical {{
        height: 6px;
    }}
    QSplitter::handle:hover {{
        background-color: {p["accent_soft"]};
    }}

    /* ===================== Scrollbars ===================== */
    QScrollBar:vertical {{
        background: {p["bg_base"]};
        width: 10px;
        margin: 0;
        border: none;
    }}
    QScrollBar::handle:vertical {{
        background: {p["scroll_handle"]};
        min-height: 32px;
        border-radius: 5px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {p["scroll_handle_hover"]};
    }}
    QScrollBar:horizontal {{
        background: {p["bg_base"]};
        height: 10px;
        margin: 0;
        border: none;
    }}
    QScrollBar::handle:horizontal {{
        background: {p["scroll_handle"]};
        min-width: 32px;
        border-radius: 5px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {p["scroll_handle_hover"]};
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{
        background: none;
        border: none;
        height: 0;
        width: 0;
    }}
    QScrollBar::add-page, QScrollBar::sub-page {{
        background: none;
    }}

    /* ===================== Misc ===================== */
    QProgressBar {{
        background-color: {p["bg_surface"]};
        border: 1px solid {p["border_subtle"]};
        border-radius: 3px;
        text-align: center;
        color: {p["text_primary"]};
    }}
    QProgressBar::chunk {{
        background-color: {p["accent"]};
        border-radius: 2px;
    }}

    QFrame[frameShape="4"], QFrame[frameShape="5"] {{
        color: {p["border_subtle"]};
    }}
    """


def palette_tokens(mode: str = "dark") -> dict[str, str]:
    """Return the colour-token dict for ``mode`` ("dark" or "light").

    Exposed so other modules (e.g. tests, the workflow stepper) can stay
    in lock-step with the theme without hard-coding the same hex codes.
    """
    return dict(_DARK if mode == "dark" else _LIGHT)


def apply_app_theme(app: QApplication, mode: str = "dark", scale: float = 1.0) -> None:
    """Apply the theme to ``app``. ``mode`` is "dark" or "light".

    ``scale`` (default 1.0) zooms every font in the sheet — see ``_qss_for``.
    It is re-applied live by the View-menu text-size actions, and read from
    persisted settings at startup. The application font point size is scaled
    too, as a belt-and-braces fallback for any widget that renders text
    without hitting a QSS ``font-size`` rule.

    Call this once at startup AFTER ``QApplication`` is created but
    BEFORE the first widget renders — otherwise the user sees a flash
    of unstyled Qt default before our QSS takes over.

    Unknown values for ``mode`` fall back to "dark" rather than raising:
    a typo or stale config entry should never block app startup.
    """
    global _BASE_FONT_PT
    palette = _LIGHT if mode == "light" else _DARK
    app.setStyleSheet(_qss_for(palette, scale))
    # Belt-and-braces: also scale the application default font so widgets
    # that draw text outside a QSS ``font-size`` rule (custom-painted
    # delegates, some native dialogs) grow with the rest of the UI.
    #
    # Capture the pristine base point size ONCE, before we ever scale the
    # app font. Re-reading ``app.font()`` on later calls would return the
    # already-scaled size and compound zoom on every keypress — anchoring to
    # the captured base keeps the mapping ``scale -> absolute size`` stable.
    font = app.font()
    if _BASE_FONT_PT <= 0:
        _BASE_FONT_PT = font.pointSizeF()
    if _BASE_FONT_PT and _BASE_FONT_PT > 0:
        font.setPointSizeF(_BASE_FONT_PT * min(2.0, max(0.7, float(scale))))
        app.setFont(font)
