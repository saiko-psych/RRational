"""CSS/HTML/JS theme system for Streamlit GUI.

Extracted from app.py.
"""

from __future__ import annotations

import streamlit as st


def get_current_theme_colors():
    """Get Plotly-compatible colors based on current theme setting.

    Reads from app_settings to determine if dark mode is enabled.
    Returns dict with colors for plot backgrounds, text, grid, etc.
    """
    # Check if dark theme is set in settings
    settings = st.session_state.get("app_settings", {})
    # Theme is stored in localStorage by JS, but we can check a session state flag
    # For now, check if user preference was saved
    is_dark = settings.get("theme", "light") == "dark"

    if is_dark:
        return {
            "bg": "#0E1117",
            "text": "#FAFAFA",
            "grid": "rgba(255,255,255,0.1)",
            "line": "#3D3D4D",
        }
    else:
        return {
            "bg": "#FFFFFF",
            "text": "#31333F",
            "grid": "rgba(0,0,0,0.1)",
            "line": "#E5E5E5",
        }


def get_plot_colors() -> dict:
    """Get custom plot colors from settings.

    Returns full color dict from ColorScheme, respecting dark mode.
    Backward-compatible: always includes 'line' key.
    """
    from rrational.gui.color_scheme import ColorScheme

    settings = st.session_state.get("app_settings", {})
    colors_dict = settings.get("plot_options", {}).get("colors", {})
    scheme = ColorScheme.from_dict(colors_dict)

    # Apply dark variant if dark mode is active
    is_dark = settings.get("theme", "light") == "dark"
    if is_dark:
        scheme = scheme.dark_variant()

    result = scheme.to_dict()
    # Backward-compat: 'line' key for existing code
    result["line"] = result["rr_line"]
    return result


def apply_custom_css():
    """Apply CSS-only theme system with instant switching.

    Uses CSS custom properties for colors and a class toggle for theme switching.
    No page reload required - themes switch instantly via JavaScript.
    """
    theme_css = """
    /* ============================================
       CSS-ONLY THEME SYSTEM FOR STREAMLIT
       ============================================ */

    /* CSS Custom Properties - Light Theme (default) */
    :root {
        --bg-primary: #FFFFFF;
        --bg-secondary: #F0F2F6;
        --bg-tertiary: #E6E9EF;
        --text-primary: #31333F;
        --text-secondary: #555867;
        --text-muted: #808495;
        --accent-primary: #2E86AB;
        --accent-hover: #236B8E;
        --border-color: #D3D3D3;
        --border-light: #E5E5E5;
        --input-bg: #FFFFFF;
        --input-border: #D3D3D3;
        --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
        --shadow-md: 0 4px 6px rgba(0,0,0,0.07);
        --success-bg: #D4EDDA;
        --success-text: #155724;
        --warning-bg: #FFF3CD;
        --warning-text: #856404;
        --error-bg: #F8D7DA;
        --error-text: #721C24;
        --info-bg: #D1ECF1;
        --info-text: #0C5460;
        --sidebar-bg: #F0F2F6;
        --sidebar-text: #31333F;
        --tab-active-bg: #FFFFFF;
        --tab-hover-bg: #E6E9EF;
        --code-bg: #F5F5F5;
        --scrollbar-track: #F0F2F6;
        --scrollbar-thumb: #C1C1C1;
    }

    /* CSS Custom Properties - Dark Theme */
    :root.dark-theme {
        --bg-primary: #0E1117;
        --bg-secondary: #262730;
        --bg-tertiary: #1E1E2E;
        --text-primary: #FAFAFA;
        --text-secondary: #B8B8C0;
        --text-muted: #808495;
        --accent-primary: #4DA6C9;
        --accent-hover: #6BB8D6;
        --border-color: #3D3D4D;
        --border-light: #333340;
        --input-bg: #1A1A24;
        --input-border: #3D3D4D;
        --shadow-sm: 0 1px 2px rgba(0,0,0,0.3);
        --shadow-md: 0 4px 6px rgba(0,0,0,0.4);
        --success-bg: #1D3D2B;
        --success-text: #75D99A;
        --warning-bg: #3D3520;
        --warning-text: #E5C76B;
        --error-bg: #3D1D20;
        --error-text: #F5A0A8;
        --info-bg: #1D3540;
        --info-text: #7DCCE8;
        --sidebar-bg: #1A1A24;
        --sidebar-text: #FAFAFA;
        --tab-active-bg: #262730;
        --tab-hover-bg: #1E1E2E;
        --code-bg: #1A1A24;
        --scrollbar-track: #1A1A24;
        --scrollbar-thumb: #4A4A5A;
    }

    /* ============================================
       GLOBAL STYLES
       ============================================ */

    /* Main app container */
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: var(--bg-primary) !important;
        color: var(--text-primary) !important;
    }

    /* Main content area */
    .main .block-container {
        background-color: var(--bg-primary) !important;
    }

    /* Headers */
    h1, h2, h3, h4, h5, h6,
    .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        color: var(--text-primary) !important;
    }

    /* Paragraphs and text */
    p, span, div, label {
        color: var(--text-primary);
    }

    /* Links */
    a {
        color: var(--accent-primary) !important;
    }
    a:hover {
        color: var(--accent-hover) !important;
    }

    /* ============================================
       SIDEBAR
       ============================================ */

    [data-testid="stSidebar"],
    [data-testid="stSidebar"] > div {
        background-color: var(--sidebar-bg) !important;
    }

    [data-testid="stSidebar"] * {
        color: var(--sidebar-text);
    }

    [data-testid="stSidebar"] .stMarkdown p,
    [data-testid="stSidebar"] label {
        color: var(--sidebar-text) !important;
    }

    /* Sidebar collapse button */
    [data-testid="stSidebar"] button[kind="header"] {
        color: var(--sidebar-text) !important;
    }

    /* ============================================
       BUTTONS
       ============================================ */

    /* Primary button */
    .stButton > button,
    button[kind="primary"] {
        background-color: var(--accent-primary) !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }

    .stButton > button:hover,
    button[kind="primary"]:hover {
        background-color: var(--accent-hover) !important;
        box-shadow: var(--shadow-md) !important;
    }

    /* Secondary button */
    .stButton > button[kind="secondary"],
    button[kind="secondary"] {
        background-color: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
    }

    .stButton > button[kind="secondary"]:hover {
        background-color: var(--bg-tertiary) !important;
    }

    /* Link buttons (st.link_button) — Streamlit emits these with a
       white-ish default background that becomes unreadable in dark
       mode. Mirror the secondary-button styling so they blend in. */
    .stLinkButton > a,
    .stLinkButton a[data-testid="baseLinkButton-secondary"],
    .stLinkButton a[kind="secondary"] {
        background-color: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
        text-decoration: none !important;
        transition: all 0.2s ease !important;
    }

    .stLinkButton > a:hover,
    .stLinkButton a[data-testid="baseLinkButton-secondary"]:hover {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        text-decoration: none !important;
    }

    /* ============================================
       INPUTS & FORMS
       ============================================ */

    /* Text inputs */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stTextArea textarea {
        background-color: var(--input-bg) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--input-border) !important;
        border-radius: 6px !important;
    }

    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus,
    .stTextArea textarea:focus {
        border-color: var(--accent-primary) !important;
        box-shadow: 0 0 0 2px rgba(46, 134, 171, 0.2) !important;
    }

    /* Input placeholders */
    .stTextInput input::placeholder,
    .stNumberInput input::placeholder,
    .stTextArea textarea::placeholder {
        color: var(--text-muted) !important;
        opacity: 0.7 !important;
    }

    /* Select boxes */
    [data-baseweb="select"] {
        border-radius: 6px !important;
    }

    [data-baseweb="select"] > div {
        background-color: var(--input-bg) !important;
        border-color: var(--input-border) !important;
    }

    [data-baseweb="select"] span {
        color: var(--text-primary) !important;
    }

    /* Dropdown menus */
    [data-baseweb="popover"] > div,
    [data-baseweb="menu"] {
        background-color: var(--bg-secondary) !important;
        border: 1px solid var(--border-color) !important;
    }

    [data-baseweb="menu"] li {
        color: var(--text-primary) !important;
    }

    [data-baseweb="menu"] li:hover {
        background-color: var(--bg-tertiary) !important;
    }

    /* Select box dropdown arrow/icon */
    [data-baseweb="select"] svg {
        fill: var(--text-primary) !important;
        color: var(--text-primary) !important;
    }

    /* Select box clear button */
    [data-baseweb="select"] [data-baseweb="clear-icon"] {
        color: var(--text-muted) !important;
    }

    /* Checkboxes - MAXIMUM SPECIFICITY to override Streamlit defaults */
    .stCheckbox label span {
        color: var(--text-primary) !important;
    }

    /* Checkbox visual box - target Streamlit's span element with st-* classes */
    .stCheckbox label span[class*="st-"] {
        background-color: var(--input-bg) !important;
        border-color: var(--input-border) !important;
    }

    /* Checked checkbox - override the RED default (rgb(255, 75, 75)) */
    .stCheckbox input[aria-checked="true"] + span,
    .stCheckbox input:checked + span,
    .stCheckbox label span[class*="st-ch"],
    .stApp .stCheckbox label > span:first-child {
        background-color: var(--accent-primary) !important;
        border-color: var(--accent-primary) !important;
    }

    /* Target emotion-cache classes used by Streamlit for checkbox */
    [class*="emotion-cache"][class*="stCheckbox"] span:first-of-type,
    .stCheckbox span[class*="st-c"] {
        background-color: var(--accent-primary) !important;
    }

    /* Force override on any 16x16 colored span in checkbox (the visual box) */
    .stCheckbox label span {
        background-color: var(--accent-primary) !important;
    }

    /* Unchecked state */
    .stCheckbox input[aria-checked="false"] + span,
    .stCheckbox input:not(:checked) + span {
        background-color: var(--input-bg) !important;
        border-color: var(--input-border) !important;
    }

    /* Checkbox checkmark icon */
    .stCheckbox svg {
        fill: white !important;
        stroke: white !important;
    }

    /* Radio buttons */
    .stRadio label span {
        color: var(--text-primary) !important;
    }

    /* Radio button circle - HIGH SPECIFICITY */
    .stRadio > div > label > div:first-child,
    .stRadio [data-baseweb="radio"],
    .stApp .stRadio input[type="radio"] + div {
        background-color: var(--input-bg) !important;
        border-color: var(--input-border) !important;
    }

    .stRadio > div > label > div:first-child:hover,
    .stRadio [data-baseweb="radio"]:hover {
        border-color: var(--accent-primary) !important;
    }

    /* Selected radio - IMPORTANT: override default */
    .stRadio > div > label > div:first-child[aria-checked="true"],
    .stRadio [data-baseweb="radio"][aria-checked="true"],
    .stApp .stRadio input[type="radio"]:checked + div {
        background-color: var(--accent-primary) !important;
        border-color: var(--accent-primary) !important;
    }

    /* ============================================
       HORIZONTAL RADIO BUTTONS - Simple styling
       ============================================ */

    /* FORCE remove ALL backgrounds from radio buttons */
    .stRadio label,
    .stRadio label *,
    .stRadio [role="radiogroup"] label,
    .stRadio [role="radiogroup"] > div,
    .stRadio [role="radiogroup"] > div > label,
    .stRadio [role="radiogroup"] > div > label > div,
    .stRadio [data-baseweb="radio"],
    .stRadio [class*="st-"],
    .stApp .stRadio label,
    .stApp .stRadio [role="radiogroup"] label {
        background-color: transparent !important;
        background: none !important;
    }

    /* Unselected radio circle - black border */
    .stRadio [data-baseweb="radio"] > div:first-child {
        border-color: #31333F !important;
        background-color: transparent !important;
    }

    :root.dark-theme .stRadio [data-baseweb="radio"] > div:first-child {
        border-color: #FAFAFA !important;
    }

    /* Selected radio circle - accent color filled */
    .stRadio [data-baseweb="radio"][aria-checked="true"] > div:first-child {
        background-color: var(--accent-primary) !important;
        border-color: var(--accent-primary) !important;
    }

    /* Selected button - border highlight around the whole option */
    .stRadio [role="radiogroup"] > div:has([aria-checked="true"]) {
        outline: 2px solid var(--accent-primary) !important;
        outline-offset: 2px !important;
        border-radius: 4px !important;
    }

    /* ============================================
       TABS - COMPLETE STYLING
       ============================================ */

    .stTabs [data-baseweb="tab-list"] {
        gap: 8px !important;
        background-color: transparent !important;
        border-bottom: 1px solid var(--border-light) !important;
    }

    .stTabs [data-baseweb="tab"] {
        background-color: var(--bg-secondary) !important;
        color: var(--text-secondary) !important;
        border-radius: 6px 6px 0 0 !important;
        border: 1px solid var(--border-light) !important;
        border-bottom: none !important;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background-color: var(--tab-hover-bg) !important;
        color: var(--text-primary) !important;
    }

    /* Selected tab - with accent color indicator */
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: var(--tab-active-bg) !important;
        color: var(--accent-primary) !important;
        border-color: var(--accent-primary) !important;
        border-bottom: 2px solid var(--accent-primary) !important;
        font-weight: 600 !important;
    }

    /* Tab highlight/underline indicator - override Streamlit default */
    .stTabs [data-baseweb="tab-highlight"],
    .stTabs [data-baseweb="tab-border"] {
        background-color: var(--accent-primary) !important;
    }

    .stTabs [data-baseweb="tab-panel"] {
        background-color: var(--bg-primary) !important;
        border: 1px solid var(--border-light) !important;
        border-top: none !important;
        border-radius: 0 0 8px 8px !important;
        padding: 1rem !important;
    }

    /* Tab button text */
    .stTabs button[role="tab"] {
        color: var(--text-secondary) !important;
    }

    .stTabs button[role="tab"][aria-selected="true"] {
        color: var(--accent-primary) !important;
    }

    /* ============================================
       EXPANDERS
       ============================================ */

    [data-testid="stExpander"] {
        background-color: var(--bg-secondary) !important;
        border: 1px solid var(--border-light) !important;
        border-radius: 8px !important;
    }

    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] details > summary,
    [data-testid="stExpander"] summary[class*="emotion-cache"] {
        color: var(--text-primary) !important;
        font-weight: 500 !important;
        background-color: var(--bg-secondary) !important;
    }

    [data-testid="stExpander"] details,
    [data-testid="stExpander"] details > div,
    [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
        background-color: var(--bg-secondary) !important;
    }

    /* ============================================
       DATA FRAMES & TABLES
       ============================================ */

    .stDataFrame {
        border-radius: 8px !important;
        overflow: hidden !important;
    }

    .stDataFrame [data-testid="stDataFrameResizable"] {
        background-color: var(--bg-primary) !important;
    }

    /* Table headers */
    .stDataFrame th {
        background-color: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
    }

    /* Table cells */
    .stDataFrame td {
        background-color: var(--bg-primary) !important;
        color: var(--text-primary) !important;
        border-color: var(--border-light) !important;
    }

    /* Table row hover */
    .stDataFrame tr:hover td {
        background-color: var(--bg-secondary) !important;
    }

    /* Table container border */
    .stDataFrame > div {
        border: 1px solid var(--border-light) !important;
    }

    /* Dark mode: invert data grid canvas colors (canvas ignores CSS, needs filter) */
    :root.dark-theme .stDataFrame [data-testid="stDataFrameResizable"],
    :root.dark-theme [data-testid="glideDataEditor"] {
        filter: invert(0.93) hue-rotate(180deg);
    }

    /* Dark mode for Plotly charts: JavaScript handles color updates via Plotly.relayout()
       CSS filter removed to avoid double-inversion when JS updates colors.
       The MutationObserver in apply_custom_css() detects new plots and updates them. */

    /* For plotly_events component (iframe) - still needs CSS filter since JS can't access cross-origin */
    :root.dark-theme .stCustomComponentV1 {
        filter: invert(0.93) hue-rotate(180deg);
    }

    /* ============================================
       ALERTS & MESSAGES
       ============================================ */

    [data-testid="stAlert"] {
        border-radius: 8px !important;
    }

    .stSuccess, [data-testid="stAlert"][data-baseweb-type="positive"] {
        background-color: var(--success-bg) !important;
        color: var(--success-text) !important;
    }

    .stWarning, [data-testid="stAlert"][data-baseweb-type="warning"] {
        background-color: var(--warning-bg) !important;
        color: var(--warning-text) !important;
    }

    .stError, [data-testid="stAlert"][data-baseweb-type="negative"] {
        background-color: var(--error-bg) !important;
        color: var(--error-text) !important;
    }

    .stInfo, [data-testid="stAlert"][data-baseweb-type="info"] {
        background-color: var(--info-bg) !important;
        color: var(--info-text) !important;
    }

    /* ============================================
       METRICS
       ============================================ */

    [data-testid="stMetric"] {
        background-color: var(--bg-secondary) !important;
        border-radius: 8px !important;
        padding: 12px 16px !important;
        border: 1px solid var(--border-light) !important;
    }

    [data-testid="stMetric"] label {
        color: var(--text-secondary) !important;
    }

    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: var(--text-primary) !important;
    }

    /* ============================================
       CODE BLOCKS
       ============================================ */

    .stCodeBlock, pre, code {
        background-color: var(--code-bg) !important;
        color: var(--text-primary) !important;
        border-radius: 6px !important;
    }

    /* ============================================
       PROGRESS BARS
       ============================================ */

    .stProgress > div {
        background-color: var(--bg-tertiary) !important;
        border-radius: 4px !important;
    }

    .stProgress > div > div {
        background-color: var(--accent-primary) !important;
        border-radius: 4px !important;
    }

    /* ============================================
       SCROLLBARS
       ============================================ */

    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }

    ::-webkit-scrollbar-track {
        background: var(--scrollbar-track);
    }

    ::-webkit-scrollbar-thumb {
        background: var(--scrollbar-thumb);
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: var(--text-muted);
    }

    /* ============================================
       MISC ELEMENTS
       ============================================ */

    /* Dividers */
    hr {
        border-color: var(--border-light) !important;
    }

    /* Captions */
    .stCaption, figcaption {
        color: var(--text-muted) !important;
    }

    /* Tooltips */
    [data-baseweb="tooltip"] {
        background-color: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
    }

    /* Popovers */
    [data-testid="stPopover"] > div {
        background-color: var(--bg-secondary) !important;
        border: 1px solid var(--border-color) !important;
    }

    /* File uploader */
    [data-testid="stFileUploader"] {
        background-color: var(--bg-secondary) !important;
        border: 2px dashed var(--border-color) !important;
        border-radius: 8px !important;
    }

    /* Spinner */
    .stSpinner > div {
        border-color: var(--accent-primary) transparent transparent transparent !important;
    }

    /* Toast messages */
    [data-testid="stToast"] {
        background-color: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
    }

    /* ============================================
       MULTI-SELECT
       ============================================ */

    /* Multi-select container */
    [data-baseweb="select"] [data-baseweb="tag"] {
        background-color: var(--accent-primary) !important;
        color: white !important;
    }

    /* Multi-select clear button */
    [data-baseweb="tag"] [data-baseweb="icon"] {
        color: white !important;
    }

    /* ============================================
       NUMBER INPUT
       ============================================ */

    .stNumberInput [data-baseweb="input"] {
        background-color: var(--input-bg) !important;
        border-color: var(--input-border) !important;
    }

    .stNumberInput [data-baseweb="input"] input {
        background-color: var(--input-bg) !important;
        color: var(--text-primary) !important;
        -webkit-text-fill-color: var(--text-primary) !important;
    }

    .stNumberInput > div > div {
        background-color: var(--input-bg) !important;
    }

    .stNumberInput button {
        background-color: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
        border-color: var(--input-border) !important;
    }

    /* Remove blue highlighting from number input */
    .stNumberInput [data-baseweb="input"] {
        border-color: var(--input-border) !important;
        background-color: var(--input-bg) !important;
    }

    .stNumberInput [data-baseweb="input"]:focus-within {
        border-color: var(--accent-primary) !important;
        box-shadow: none !important;
    }

    /* ============================================
       HELP/TOOLTIP ICONS
       ============================================ */

    /* Help icon circles next to labels - comprehensive styling */
    [data-testid="stTooltipIcon"],
    .stTooltipIcon,
    button[kind="tooltip"],
    [data-baseweb="tooltip"] button,
    .stCheckbox [data-testid="stTooltipIcon"],
    [data-testid="stWidgetLabel"] button,
    [data-testid="tooltipHoverTarget"],
    .st-emotion-cache-1inwz65,
    [class*="stTooltipIcon"] {
        background-color: var(--bg-tertiary) !important;
        color: var(--text-muted) !important;
        border: none !important;
        border-radius: 50% !important;
    }

    [data-testid="stTooltipIcon"] svg,
    .stTooltipIcon svg,
    button[kind="tooltip"] svg,
    [data-testid="tooltipHoverTarget"] svg,
    [class*="stTooltipIcon"] svg {
        fill: var(--text-muted) !important;
        color: var(--text-muted) !important;
    }

    /* Tooltip popup content */
    [data-baseweb="tooltip"] > div,
    [role="tooltip"],
    [data-baseweb="popover"] [data-baseweb="tooltip"],
    .stTooltipContent {
        background-color: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
    }

    /* Popover container (help text popup) */
    [data-baseweb="popover"] > div {
        background-color: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
    }

    .stPopover button {
        background-color: transparent !important;
        color: var(--text-primary) !important;
        border: none !important;
    }

    .stPopover button:hover {
        background-color: var(--bg-tertiary) !important;
    }

    /* ============================================
       DATE/TIME INPUTS
       ============================================ */

    [data-baseweb="calendar"] {
        background-color: var(--bg-secondary) !important;
    }

    [data-baseweb="calendar"] * {
        color: var(--text-primary) !important;
    }

    [data-baseweb="datepicker"] {
        background-color: var(--input-bg) !important;
    }

    /* ============================================
       DOWNLOAD BUTTON
       ============================================ */

    .stDownloadButton > button {
        background-color: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-color) !important;
    }

    .stDownloadButton > button:hover {
        background-color: var(--bg-tertiary) !important;
        border-color: var(--accent-primary) !important;
    }

    /* ============================================
       COLUMN CONTAINERS
       ============================================ */

    [data-testid="column"] {
        background-color: transparent !important;
    }

    /* ============================================
       FORMS
       ============================================ */

    [data-testid="stForm"] {
        background-color: var(--bg-secondary) !important;
        border: 1px solid var(--border-light) !important;
        border-radius: 8px !important;
        padding: 1rem !important;
    }

    /* ============================================
       IFRAMES (components.html)
       ============================================ */

    iframe {
        background-color: transparent !important;
    }

    /* ============================================
       HEADER & TOOLBAR
       ============================================ */

    [data-testid="stHeader"] {
        background-color: var(--bg-primary) !important;
    }

    [data-testid="stToolbar"] {
        background-color: var(--bg-primary) !important;
    }

    [data-testid="stToolbar"] button {
        color: var(--text-primary) !important;
    }

    /* ============================================
       HELP TOOLTIPS
       ============================================ */

    .stTooltipIcon {
        color: var(--text-muted) !important;
    }

    /* ============================================
       EMPTY STATES
       ============================================ */

    .stEmpty {
        color: var(--text-muted) !important;
    }

    /* ============================================
       JSON VIEWER
       ============================================ */

    [data-testid="stJson"] {
        background-color: var(--code-bg) !important;
        border-radius: 6px !important;
    }

    [data-testid="stJson"] * {
        color: var(--text-primary) !important;
    }

    /* ============================================
       DIALOG/MODAL
       ============================================ */

    [data-testid="stModal"] > div {
        background-color: var(--bg-primary) !important;
        border: 1px solid var(--border-color) !important;
    }

    /* ============================================
       WIDGET LABELS
       ============================================ */

    .stSelectbox label,
    .stMultiSelect label,
    .stTextInput label,
    .stNumberInput label,
    .stTextArea label,
    .stDateInput label,
    .stTimeInput label,
    .stCheckbox label,
    .stRadio label,
    .stSlider label,
    .stFileUploader label {
        color: var(--text-primary) !important;
    }

    /* ============================================
       WIDGET HELP TEXT
       ============================================ */

    .stSelectbox [data-testid="stWidgetLabel"] small,
    .stMultiSelect [data-testid="stWidgetLabel"] small,
    .stTextInput [data-testid="stWidgetLabel"] small,
    .stNumberInput [data-testid="stWidgetLabel"] small {
        color: var(--text-muted) !important;
    }

    /* ============================================
       MARKDOWN ELEMENTS
       ============================================ */

    .stMarkdown code {
        background-color: var(--code-bg) !important;
        color: var(--text-primary) !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
    }

    .stMarkdown blockquote {
        border-left: 3px solid var(--accent-primary) !important;
        padding-left: 1rem !important;
        color: var(--text-secondary) !important;
    }

    /* ============================================
       DROPDOWN MENUS (Selectbox, Multiselect)
       ============================================ */

    /* Dropdown menu container (popover) */
    [data-baseweb="popover"],
    [data-baseweb="menu"],
    [data-baseweb="select"] [data-baseweb="popover"] {
        background-color: var(--bg-secondary) !important;
        border: 1px solid var(--border-light) !important;
    }

    /* Dropdown menu list */
    [data-baseweb="menu"] ul,
    [data-baseweb="popover"] ul {
        background-color: var(--bg-secondary) !important;
    }

    /* Dropdown menu items */
    [data-baseweb="menu"] li,
    [data-baseweb="popover"] li,
    [role="option"] {
        background-color: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
    }

    /* Dropdown menu item hover */
    [data-baseweb="menu"] li:hover,
    [data-baseweb="popover"] li:hover,
    [role="option"]:hover,
    [data-highlighted="true"] {
        background-color: var(--bg-primary) !important;
    }

    /* Selected dropdown item */
    [aria-selected="true"],
    [data-baseweb="menu"] li[aria-selected="true"] {
        background-color: var(--accent-primary) !important;
        color: white !important;
    }

    /* ============================================
       PLOTLY SPECIFIC
       Note: Chart colors handled by JavaScript updatePlotlyTheme/updatePlotsForTheme
       We only style the container here, not internal SVG elements
       ============================================ */

    [data-testid="stPlotlyChart"] {
        background-color: transparent !important;
    }

    /* ============================================
       BOTTOM STATUS BAR / FOOTER
       ============================================ */

    [data-testid="stBottom"] {
        background-color: var(--bg-primary) !important;
        border-top: 1px solid var(--border-light) !important;
    }

    [data-testid="stStatusWidget"] {
        color: var(--text-muted) !important;
    }

    /* ============================================
       ICON BUTTONS
       ============================================ */

    [data-testid="baseButton-headerNoPadding"],
    [data-testid="baseButton-minimal"] {
        color: var(--text-primary) !important;
    }

    [data-testid="baseButton-headerNoPadding"]:hover,
    [data-testid="baseButton-minimal"]:hover {
        background-color: var(--bg-secondary) !important;
    }

    /* ============================================
       SPECIFIC TEXT ELEMENTS
       ============================================ */

    /* Ensure all small/caption text uses correct color */
    small, .caption, [data-testid="stCaptionContainer"] {
        color: var(--text-muted) !important;
    }

    /* Widget instruction text */
    [data-testid="InputInstructions"] {
        color: var(--text-muted) !important;
    }

    /* Ensure SVG icons get correct color */
    .stApp svg:not([fill]) {
        fill: currentColor;
    }

    /* ============================================
       STREAMLIT NATIVE COMPONENTS
       ============================================ */

    /* Chat message styling */
    [data-testid="stChatMessage"] {
        background-color: var(--bg-secondary) !important;
        border: 1px solid var(--border-light) !important;
    }

    /* Status indicator */
    [data-testid="stStatusIndicator"] {
        background-color: var(--bg-secondary) !important;
    }

    /* Markdown container */
    [data-testid="stMarkdownContainer"] {
        color: var(--text-primary) !important;
    }

    /* Element container */
    [data-testid="element-container"] {
        color: var(--text-primary);
    }

    /* Vertical block */
    [data-testid="stVerticalBlock"] {
        background-color: transparent !important;
    }

    /* ============================================
       FIX: BASEWEB COMPONENTS OVERRIDES
       ============================================ */

    /* BaseWeb input containers */
    [data-baseweb="input"] {
        background-color: var(--input-bg) !important;
        border-color: var(--input-border) !important;
    }

    [data-baseweb="input"] input {
        color: var(--text-primary) !important;
        background-color: transparent !important;
    }

    /* BaseWeb base button overrides for non-primary buttons */
    [data-baseweb="button"]:not([kind="primary"]) {
        color: var(--text-primary) !important;
    }

    /* ============================================
       ENSURE SIDEBAR ELEMENTS
       ============================================ */

    /* Sidebar select boxes */
    [data-testid="stSidebar"] [data-baseweb="select"] > div {
        background-color: var(--input-bg) !important;
    }

    /* Sidebar inputs - comprehensive targeting */
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] [data-baseweb="input"],
    [data-testid="stSidebar"] [data-baseweb="input"] > div,
    [data-testid="stSidebar"] .stTextInput > div > div,
    [data-testid="stSidebar"] .stTextInput input,
    [data-testid="stSidebar"] [data-testid="stExpander"] input,
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-baseweb="input"],
    [data-testid="stSidebar"] [data-testid="stExpander"] [data-baseweb="input"] > div {
        background-color: var(--input-bg) !important;
        color: var(--sidebar-text) !important;
        border-color: var(--input-border) !important;
    }

    /* Sidebar buttons */
    [data-testid="stSidebar"] .stButton > button {
        background-color: var(--accent-primary) !important;
    }

    /* Sidebar link buttons - same fix as the global rule above so
       Documentation / Report a bug stay legible in dark mode. */
    [data-testid="stSidebar"] .stLinkButton > a,
    [data-testid="stSidebar"] .stLinkButton a[data-testid="baseLinkButton-secondary"] {
        background-color: var(--bg-secondary) !important;
        color: var(--sidebar-text) !important;
        border: 1px solid var(--border-color) !important;
    }

    [data-testid="stSidebar"] .stLinkButton > a:hover {
        background-color: var(--bg-tertiary) !important;
        color: var(--sidebar-text) !important;
    }

    /* Sidebar checkboxes */
    [data-testid="stSidebar"] .stCheckbox span {
        color: var(--sidebar-text) !important;
    }

    /* ============================================
       LOADING INDICATOR OVERRIDE
       ============================================ */

    /* Hide the default Streamlit loading swimmer icon */
    [data-testid="stStatusWidget"] .StatusWidget-swimming-icon,
    [data-testid="stStatusWidget"] svg[class*="swimming"],
    .stStatusWidget svg,
    div[data-testid="stStatusWidget"] > div > svg {
        display: none !important;
    }

    /* Clean status widget - remove grey box, hide swimmer */
    [data-testid="stStatusWidget"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }

    [data-testid="stStatusWidget"] svg {
        display: none !important;
    }
    """

    # Apply CSS
    st.markdown(f"<style>{theme_css}</style>", unsafe_allow_html=True)

    # JavaScript to apply saved theme and accent color on page load
    import streamlit.components.v1 as components

    theme_init_js = """
    <script>
        (function() {
            // Access parent document (Streamlit app)
            var parentDoc = window.parent.document;
            var root = parentDoc.documentElement;

            // Immediately set page title and favicon (before Streamlit loads)
            if (parentDoc.title === 'Streamlit' || parentDoc.title === '') {
                parentDoc.title = 'RRational';
            }
            // Update favicon if it's the default Streamlit one
            var existingFavicon = parentDoc.querySelector("link[rel*='icon']");
            if (existingFavicon && existingFavicon.href.includes('streamlit')) {
                existingFavicon.href = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y=".9em" font-size="90">📊</text></svg>';
            }

            // Force Streamlit to use custom theme from config.toml on startup
            var savedTheme = window.parent.localStorage.getItem('music-hrv-theme') || 'light';
            var isDark = savedTheme === 'dark';

            // Check if we already attempted theme setup (prevent infinite reload)
            var themeSetupDone = window.parent.localStorage.getItem('music-hrv-theme-setup-done');

            if (!themeSetupDone) {
                // Set Streamlit's internal theme to use custom theme (from config.toml)
                var customTheme = {
                    name: 'Custom',
                    themeInput: isDark ? {
                        primaryColor: '#2E86AB',
                        backgroundColor: '#0E1117',
                        secondaryBackgroundColor: '#262730',
                        textColor: '#FAFAFA',
                        base: 'dark'
                    } : {
                        primaryColor: '#2E86AB',
                        backgroundColor: '#FFFFFF',
                        secondaryBackgroundColor: '#F0F2F6',
                        textColor: '#31333F',
                        base: 'light'
                    }
                };
                window.parent.localStorage.setItem('stActiveTheme-/-v1', JSON.stringify(customTheme));
                window.parent.localStorage.setItem('music-hrv-theme-setup-done', 'true');
                // One-time reload to apply custom theme
                window.parent.location.reload();
                return;
            }

            if (isDark) {
                root.classList.add('dark-theme');
            }

            // Apply saved accent color
            var savedAccent = window.parent.localStorage.getItem('music-hrv-accent') || '#2E86AB';
            root.style.setProperty('--accent-primary', savedAccent);

            // Calculate hover color (slightly darker)
            var num = parseInt(savedAccent.slice(1), 16);
            var r = Math.min(255, Math.max(0, (num >> 16) - 20));
            var g = Math.min(255, Math.max(0, ((num >> 8) & 0x00FF) - 20));
            var b = Math.min(255, Math.max(0, (num & 0x0000FF) - 20));
            var hoverColor = '#' + (0x1000000 + r * 0x10000 + g * 0x100 + b).toString(16).slice(1);
            root.style.setProperty('--accent-hover', hoverColor);

            // Inject dynamic CSS to override Streamlit's st-* classes
            function injectAccentCSS() {
                var styleId = 'music-hrv-accent-override';
                var existingStyle = parentDoc.getElementById(styleId);
                if (existingStyle) existingStyle.remove();

                var styleTag = parentDoc.createElement('style');
                styleTag.id = styleId;

                // Use CSS custom properties instead of hardcoded colors
                // This allows theme switching without re-injecting CSS
                styleTag.textContent = `
                    /* Dynamic accent color override for Streamlit components */
                    .stCheckbox label > span:first-child,
                    .stCheckbox span[class*="st-ch"],
                    .stCheckbox span[class*="st-c"]:first-child {
                        background-color: ${savedAccent} !important;
                        border-color: ${savedAccent} !important;
                    }
                    .stCheckbox input:not(:checked) + span,
                    .stCheckbox input[aria-checked="false"] + span {
                        background-color: var(--input-bg) !important;
                        border-color: var(--border-color) !important;
                    }
                    .stTabs [data-baseweb="tab"][aria-selected="true"],
                    .stTabs button[role="tab"][aria-selected="true"] {
                        color: ${savedAccent} !important;
                        border-bottom-color: ${savedAccent} !important;
                    }
                    .stTabs [data-baseweb="tab-highlight"] {
                        background-color: ${savedAccent} !important;
                    }
                    .stButton > button {
                        background-color: ${savedAccent} !important;
                    }
                    .stButton > button:hover {
                        background-color: ${hoverColor} !important;
                    }
                    /* Expanders - use CSS variables for theme switching */
                    [data-testid="stExpander"],
                    [data-testid="stExpander"] > details,
                    [data-testid="stExpander"] details[open],
                    [data-testid="stExpander"] details > summary,
                    [data-testid="stExpander"] details > div,
                    [data-testid="stExpander"] details[open] > div,
                    [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
                        background-color: var(--bg-secondary) !important;
                        border-color: var(--border-color) !important;
                    }
                    [data-testid="stExpander"] summary span,
                    [data-testid="stExpander"] p,
                    [data-testid="stExpander"] label {
                        color: var(--text-primary) !important;
                    }
                    /* Dataframes / Tables - use CSS variables */
                    .stDataFrame,
                    .stDataFrame > div,
                    .stDataFrame > div > div,
                    [data-testid="stDataFrame"],
                    [data-testid="stTable"],
                    .stDataFrame [data-testid="stDataFrameResizable"] {
                        background-color: var(--bg-primary) !important;
                    }
                    .stDataFrame th,
                    .stDataFrame thead tr,
                    .stDataFrame thead {
                        background-color: var(--bg-secondary) !important;
                        color: var(--text-primary) !important;
                    }
                    .stDataFrame td,
                    .stDataFrame tbody tr,
                    .stDataFrame tbody {
                        background-color: var(--bg-primary) !important;
                        color: var(--text-primary) !important;
                    }
                    /* Plotly charts - only style container, JS handles chart internals */
                    [data-testid="stPlotlyChart"] {
                        background-color: transparent !important;
                    }
                    /* Data editor / Glide data grid */
                    [data-testid="stDataFrameResizable"],
                    [data-testid="glideDataEditor"],
                    [data-testid="glideDataEditor"] > div,
                    [data-testid="glideDataEditor"] canvas,
                    .dvn-scroller,
                    .dvn-scroller > div,
                    .gdg-cell,
                    [class*="dvn-underlay"],
                    [class*="dvn-scroll-inner"] {
                        background-color: var(--bg-primary) !important;
                    }
                    /* Data editor cells */
                    [data-testid="glideDataEditor"] [class*="dvn-cell"],
                    [data-testid="glideDataEditor"] [class*="cell"],
                    [class*="gdg-cell"] {
                        background-color: var(--bg-primary) !important;
                        color: var(--text-primary) !important;
                    }
                    /* Data editor header */
                    [data-testid="glideDataEditor"] [class*="header"],
                    .gdg-header,
                    [class*="gdg-header"] {
                        background-color: var(--bg-secondary) !important;
                        color: var(--text-primary) !important;
                    }
                    /* RADIO BUTTONS - remove all background highlighting */
                    .stRadio label,
                    .stRadio label span,
                    .stRadio label > div,
                    .stRadio [role="radiogroup"] label,
                    .stRadio [role="radiogroup"] > div > label,
                    .stRadio [data-baseweb="radio"],
                    .stRadio [class*="st-e"],
                    .stRadio [class*="st-f"],
                    .stRadio [class*="st-g"],
                    .stRadio [class*="st-h"] {
                        background-color: transparent !important;
                        background: none !important;
                    }
                    /* Radio circle - black when unselected */
                    .stRadio [data-baseweb="radio"] > div:first-child {
                        border-color: #31333F !important;
                        background-color: transparent !important;
                    }
                    /* Radio circle - blue when selected */
                    .stRadio [data-baseweb="radio"][aria-checked="true"] > div:first-child {
                        background-color: ${savedAccent} !important;
                        border-color: ${savedAccent} !important;
                    }
                    /* Selected option - outline border */
                    .stRadio [role="radiogroup"] > div:has([aria-checked="true"]) {
                        outline: 2px solid ${savedAccent} !important;
                        outline-offset: 2px !important;
                        border-radius: 4px !important;
                    }
                `;
                parentDoc.head.appendChild(styleTag);
            }

            // Inject CSS after a short delay to ensure DOM is ready
            setTimeout(injectAccentCSS, 100);

            // Style horizontal radio buttons (remove background highlight, show circles)
            function styleRadioButtons() {
                var isDark = root.classList.contains('dark-theme');
                var borderColor = isDark ? '#FAFAFA' : '#31333F';
                var radioLabels = parentDoc.querySelectorAll('.stRadio [role="radiogroup"] label');

                radioLabels.forEach(function(label) {
                    var input = label.querySelector('input[type="radio"]');
                    var textDiv = label.querySelector('[data-testid="stMarkdownContainer"]');
                    if (textDiv) textDiv = textDiv.parentElement;
                    var circleOuter = label.querySelector('div:first-child');

                    // Remove background from text
                    if (textDiv) {
                        textDiv.style.setProperty('background-color', 'transparent', 'important');
                        textDiv.style.setProperty('background', 'none', 'important');
                    }

                    // Style radio circle
                    if (circleOuter) {
                        circleOuter.style.setProperty('border', '2px solid ' + borderColor, 'important');
                        circleOuter.style.setProperty('border-radius', '50%', 'important');

                        if (input && input.checked) {
                            circleOuter.style.setProperty('background-color', savedAccent, 'important');
                            circleOuter.style.setProperty('border-color', savedAccent, 'important');
                            label.style.setProperty('outline', '2px solid ' + savedAccent, 'important');
                            label.style.setProperty('outline-offset', '4px', 'important');
                            label.style.setProperty('border-radius', '4px', 'important');
                        } else {
                            circleOuter.style.setProperty('background-color', 'transparent', 'important');
                            label.style.removeProperty('outline');
                        }
                    }
                });
            }

            // Run initially and observe for changes
            setTimeout(styleRadioButtons, 200);
            var radioObserver = new MutationObserver(function(mutations) {
                setTimeout(styleRadioButtons, 50);
            });
            radioObserver.observe(parentDoc.body, { childList: true, subtree: true, attributes: true });

            // Update Plotly charts for current theme (both dark AND light, including iframes)
            function updatePlotsForTheme() {
                // Check current theme state (not captured value)
                var currentIsDark = root.classList.contains('dark-theme');
                var bgColor = currentIsDark ? '#0E1117' : '#FFFFFF';
                var gridColor = currentIsDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.1)';
                var textColor = currentIsDark ? '#FAFAFA' : '#31333F';
                var lineColor = currentIsDark ? '#3D3D4D' : '#E5E5E5';

                function updatePlot(plot, Plotly) {
                    if (Plotly && plot.data) {
                        try {
                            Plotly.relayout(plot, {
                                'paper_bgcolor': bgColor,
                                'plot_bgcolor': bgColor,
                                'xaxis.gridcolor': gridColor,
                                'yaxis.gridcolor': gridColor,
                                'xaxis.linecolor': lineColor,
                                'yaxis.linecolor': lineColor,
                                'xaxis.tickfont.color': textColor,
                                'yaxis.tickfont.color': textColor,
                                'xaxis.title.font.color': textColor,
                                'yaxis.title.font.color': textColor,
                                'font.color': textColor,
                                'title.font.color': textColor,
                                'legend.font.color': textColor
                            });
                        } catch(e) {}
                    }
                }

                // Update plots in main document
                var plots = parentDoc.querySelectorAll('.js-plotly-plot');
                plots.forEach(function(plot) {
                    updatePlot(plot, window.parent.Plotly);
                });

                // Also update plots inside iframes (for plotly_events component)
                var iframes = parentDoc.querySelectorAll('iframe');
                iframes.forEach(function(iframe) {
                    try {
                        var iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                        var iframePlots = iframeDoc.querySelectorAll('.js-plotly-plot');
                        var iframePlotly = iframe.contentWindow.Plotly;
                        iframePlots.forEach(function(plot) {
                            updatePlot(plot, iframePlotly);
                        });
                    } catch(e) {} // Cross-origin iframes will throw
                });
            }

            // Initial update for any existing plots - multiple calls to catch async renders
            setTimeout(updatePlotsForTheme, 100);
            setTimeout(updatePlotsForTheme, 500);
            setTimeout(updatePlotsForTheme, 1000);

            // Debounced observer for new plots (avoid excessive updates)
            var plotUpdateTimeout = null;
            var observer = new MutationObserver(function(mutations) {
                // Check for any DOM changes that might include Plotly charts
                var hasPlotlyChange = mutations.some(function(m) {
                    if (m.addedNodes.length > 0) {
                        return Array.from(m.addedNodes).some(function(n) {
                            if (n.nodeType !== 1) return false;
                            // Check for Plotly-related classes
                            return n.classList?.contains('js-plotly-plot') ||
                                   n.classList?.contains('stPlotlyChart') ||
                                   n.querySelector?.('.js-plotly-plot') ||
                                   n.querySelector?.('[data-testid="stPlotlyChart"]');
                        });
                    }
                    return false;
                });
                if (hasPlotlyChange) {
                    clearTimeout(plotUpdateTimeout);
                    // Multiple updates to catch Plotly async rendering
                    plotUpdateTimeout = setTimeout(function() {
                        updatePlotsForTheme();
                        setTimeout(updatePlotsForTheme, 300);
                    }, 100);
                }
            });
            observer.observe(parentDoc.body, { childList: true, subtree: true });
        })();
    </script>
    """
    components.html(theme_init_js, height=0)
