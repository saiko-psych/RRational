"""HRV analysis visualization functions (individual participant).

Returns Plotly figures — no Streamlit dependency.
"""

from __future__ import annotations

import numpy as np

_go = None
_make_subplots = None


def get_plotly_analysis():
    """Lazily import plotly."""
    global _go, _make_subplots
    if _go is None:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        _go = go
        _make_subplots = make_subplots
    return _go, _make_subplots


from rrational.analysis.hrv_metrics import (  # noqa: E402
    format_power as _format_power,
)


def get_neurokit():
    """Lazy import NeuroKit2."""
    try:
        import neurokit2 as nk

        return nk
    except ImportError:
        return None


def _get_colors() -> dict:
    """Get plot colors from user config when Streamlit is running, defaults otherwise."""
    try:
        from rrational.gui.theme import get_plot_colors

        return get_plot_colors()
    except Exception:
        from rrational.gui.color_scheme import ColorScheme

        result = ColorScheme().to_dict()
        result["line"] = result["rr_line"]
        return result


# Static fallback for backward compat (used by external code if any)
PLOT_COLORS = {
    "primary": "#2E86AB",
    "secondary": "#A23B72",
    "accent": "#F18F01",
    "success": "#C73E1D",
    "neutral": "#6C757D",
    "background": "#FAFAFA",
    "lf_band": "rgba(255, 193, 7, 0.3)",
    "hf_band": "rgba(46, 134, 171, 0.3)",
    "vlf_band": "rgba(108, 117, 125, 0.2)",
}


def get_theme_colors():
    """Get colors for chart rendering.

    Always returns light theme colors to match config.toml base theme.
    Dark mode is handled by JavaScript updatePlotlyTheme() function
    which updates charts dynamically when user switches themes.
    """
    # Always use light theme for initial render (matches config.toml)
    # JavaScript handles dark mode switching dynamically
    return {
        "bg": "#FFFFFF",
        "text": "#31333F",
        "grid": "rgba(0,0,0,0.1)",
    }


def create_professional_tachogram(
    rr_intervals: list, section_label: str, artifact_indices: list = None
):
    """Create a professional tachogram with clean layout.

    Features:
    - RR intervals as connected scatter plot
    - Mean line with ±1 SD and ±2 SD bands
    - Artifact markers if provided
    - Professional styling with legend below plot

    Returns:
        Tuple of (figure, stats_dict) for external display of statistics
    """
    go, _ = get_plotly_analysis()
    if go is None:
        return None, {}

    colors = _get_colors()
    rr = np.array(rr_intervals)
    n_beats = len(rr)

    # Calculate statistics
    mean_rr = np.mean(rr)
    std_rr = np.std(rr)
    min_rr = np.min(rr)
    max_rr = np.max(rr)
    mean_hr = 60000 / mean_rr

    # Stats for external display
    stats = {
        "N beats": n_beats,
        "Mean RR": f"{mean_rr:.1f} ms",
        "SD": f"{std_rr:.1f} ms",
        "Mean HR": f"{mean_hr:.1f} bpm",
        "Range": f"{min_rr:.0f}–{max_rr:.0f} ms",
    }

    # Create figure
    fig = go.Figure()

    # Add ±2 SD band (lighter)
    fig.add_trace(
        go.Scatter(
            x=list(range(n_beats)) + list(range(n_beats - 1, -1, -1)),
            y=[mean_rr + 2 * std_rr] * n_beats + [mean_rr - 2 * std_rr] * n_beats,
            fill="toself",
            fillcolor=colors.get("section_fill", "rgba(46, 134, 171, 0.1)"),
            line=dict(width=0),
            name="±2 SD",
            hoverinfo="skip",
            showlegend=True,
        )
    )

    # Add ±1 SD band (darker)
    fig.add_trace(
        go.Scatter(
            x=list(range(n_beats)) + list(range(n_beats - 1, -1, -1)),
            y=[mean_rr + std_rr] * n_beats + [mean_rr - std_rr] * n_beats,
            fill="toself",
            fillcolor=colors.get("section_fill", "rgba(46, 134, 171, 0.1)").replace(
                "0.1", "0.2"
            ),
            line=dict(width=0),
            name="±1 SD",
            hoverinfo="skip",
            showlegend=True,
        )
    )

    # Add mean line
    fig.add_trace(
        go.Scatter(
            x=[0, n_beats - 1],
            y=[mean_rr, mean_rr],
            mode="lines",
            line=dict(color=colors["exclusion"], width=2, dash="dash"),
            name=f"Mean ({mean_rr:.0f} ms)",
            hoverinfo="name",
        )
    )

    # Add RR intervals
    fig.add_trace(
        go.Scattergl(
            x=list(range(n_beats)),
            y=rr.tolist(),
            mode="lines+markers",
            marker=dict(size=3, color=colors["rr_line"]),
            line=dict(width=1, color=colors["rr_line"]),
            name="RR Intervals",
            hovertemplate="Beat %{x}<br>RR: %{y:.0f} ms<br>HR: %{customdata:.1f} bpm<extra></extra>",
            customdata=60000 / rr,
        )
    )

    # Add artifact markers if provided
    if artifact_indices and len(artifact_indices) > 0:
        artifact_rr = [rr[i] for i in artifact_indices if i < len(rr)]
        fig.add_trace(
            go.Scatter(
                x=artifact_indices,
                y=artifact_rr,
                mode="markers",
                marker=dict(
                    size=10,
                    color=colors["artifact"],
                    symbol="x",
                    line=dict(width=2),
                ),
                name=f"Artifacts ({len(artifact_indices)})",
                hovertemplate="Artifact at beat %{x}<br>RR: %{y:.0f} ms<extra></extra>",
            )
        )
        stats["Artifacts"] = len(artifact_indices)

    # Update layout - legend below plot
    theme = get_theme_colors()
    fig.update_layout(
        title=dict(
            text=f"<b>Tachogram</b> — {section_label}",
            font=dict(size=16, color=theme["text"]),
        ),
        xaxis=dict(
            title=dict(text="Beat Number", font=dict(color=theme["text"])),
            showgrid=True,
            gridcolor=theme["grid"],
            zeroline=False,
            tickfont=dict(color=theme["text"]),
        ),
        yaxis=dict(
            title=dict(text="RR Interval (ms)", font=dict(color=theme["text"])),
            showgrid=True,
            gridcolor=theme["grid"],
            zeroline=False,
            tickfont=dict(color=theme["text"]),
        ),
        height=400,
        margin=dict(l=60, r=20, t=50, b=80),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.15,
            xanchor="center",
            x=0.5,
            font=dict(color=theme["text"]),
        ),
        hovermode="x unified",
        plot_bgcolor=theme["bg"],
        paper_bgcolor=theme["bg"],
        font=dict(color=theme["text"]),
    )

    return fig, stats


def create_poincare_plot(rr_intervals: list, section_label: str):
    """Create a Poincaré plot (RR[n] vs RR[n+1]) with SD1/SD2 ellipse.

    The Poincaré plot visualizes short-term (SD1) and long-term (SD2) HRV.
    - SD1: Perpendicular to identity line - short-term variability
    - SD2: Along identity line - long-term variability

    Returns:
        Tuple of (figure, stats_dict) for external display of statistics
    """
    go, _ = get_plotly_analysis()
    if go is None:
        return None, {}

    colors = _get_colors()
    rr = np.array(rr_intervals)
    rr_n = rr[:-1]  # RR[n]
    rr_n1 = rr[1:]  # RR[n+1]

    # Calculate SD1 and SD2
    diff_rr = rr_n1 - rr_n
    sum_rr = rr_n1 + rr_n

    sd1 = np.std(diff_rr) / np.sqrt(2)
    sd2 = np.std(sum_rr) / np.sqrt(2)
    sd_ratio = sd1 / sd2 if sd2 > 0 else 0

    # Stats for external display
    stats = {
        "SD1 (short-term)": f"{sd1:.1f} ms",
        "SD2 (long-term)": f"{sd2:.1f} ms",
        "SD1/SD2": f"{sd_ratio:.2f}",
        "N pairs": len(rr_n),
    }

    # Center of ellipse
    center_x = np.mean(rr_n)
    center_y = np.mean(rr_n1)

    # Create ellipse points (rotated 45 degrees)
    theta = np.linspace(0, 2 * np.pi, 100)
    a = sd2  # Semi-major axis (along identity line)
    b = sd1  # Semi-minor axis (perpendicular to identity line)

    cos_45 = np.cos(np.pi / 4)
    sin_45 = np.sin(np.pi / 4)

    ellipse_x = center_x + a * np.cos(theta) * cos_45 - b * np.sin(theta) * sin_45
    ellipse_y = center_y + a * np.cos(theta) * sin_45 + b * np.sin(theta) * cos_45

    # Create figure
    fig = go.Figure()

    # Add identity line
    min_val = min(np.min(rr_n), np.min(rr_n1)) - 50
    max_val = max(np.max(rr_n), np.max(rr_n1)) + 50
    fig.add_trace(
        go.Scatter(
            x=[min_val, max_val],
            y=[min_val, max_val],
            mode="lines",
            line=dict(color="#6C757D", width=1, dash="dash"),
            name="Identity Line",
            hoverinfo="skip",
        )
    )

    # Add SD1/SD2 ellipse
    fig.add_trace(
        go.Scatter(
            x=ellipse_x.tolist(),
            y=ellipse_y.tolist(),
            mode="lines",
            fill="toself",
            fillcolor=colors.get("section_fill", "rgba(46, 134, 171, 0.1)").replace(
                "0.1", "0.2"
            ),
            line=dict(color=colors["rr_line"], width=2),
            name="SD1/SD2 Ellipse",
            hoverinfo="name",
        )
    )

    # Add scatter points
    fig.add_trace(
        go.Scattergl(
            x=rr_n.tolist(),
            y=rr_n1.tolist(),
            mode="markers",
            marker=dict(size=5, color=colors["rr_line"], opacity=0.6),
            name="RR pairs",
            hovertemplate="RR[n]: %{x:.0f} ms<br>RR[n+1]: %{y:.0f} ms<extra></extra>",
        )
    )

    # Add center point
    fig.add_trace(
        go.Scatter(
            x=[center_x],
            y=[center_y],
            mode="markers",
            marker=dict(size=12, color=colors["exclusion"], symbol="cross"),
            name="Center",
            hovertemplate=f"Center<br>RR[n]: {center_x:.0f} ms<br>RR[n+1]: {center_y:.0f} ms<extra></extra>",
        )
    )

    # Add SD1 line (perpendicular to identity - short-term variability)
    sd1_x = [center_x - sd1 * sin_45, center_x + sd1 * sin_45]
    sd1_y = [center_y + sd1 * cos_45, center_y - sd1 * cos_45]
    fig.add_trace(
        go.Scatter(
            x=sd1_x,
            y=sd1_y,
            mode="lines",
            line=dict(color="#e74c3c", width=2),
            name=f"SD1 = {sd1:.1f} ms",
            hoverinfo="name",
        )
    )

    # Add SD2 line (along identity - long-term variability)
    sd2_x = [center_x - sd2 * cos_45, center_x + sd2 * cos_45]
    sd2_y = [center_y - sd2 * sin_45, center_y + sd2 * sin_45]
    fig.add_trace(
        go.Scatter(
            x=sd2_x,
            y=sd2_y,
            mode="lines",
            line=dict(color="#3498db", width=2),
            name=f"SD2 = {sd2:.1f} ms",
            hoverinfo="name",
        )
    )

    # Update layout - legend below plot
    theme = get_theme_colors()
    fig.update_layout(
        title=dict(
            text=f"<b>Poincaré Plot</b> — {section_label}",
            font=dict(size=16, color=theme["text"]),
        ),
        xaxis=dict(
            title=dict(text="RR[n] (ms)", font=dict(color=theme["text"])),
            showgrid=True,
            gridcolor=theme["grid"],
            scaleanchor="y",
            scaleratio=1,
            tickfont=dict(color=theme["text"]),
        ),
        yaxis=dict(
            title=dict(text="RR[n+1] (ms)", font=dict(color=theme["text"])),
            showgrid=True,
            gridcolor=theme["grid"],
            tickfont=dict(color=theme["text"]),
        ),
        height=500,
        margin=dict(l=60, r=20, t=50, b=100),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.18,
            xanchor="center",
            x=0.5,
            font=dict(color=theme["text"], size=11),
        ),
        plot_bgcolor=theme["bg"],
        paper_bgcolor=theme["bg"],
        font=dict(color=theme["text"]),
    )

    return fig, stats


def create_frequency_domain_plot(
    rr_intervals: list, section_label: str, sampling_rate: int = 4
):
    """Create a power spectral density plot with frequency bands highlighted.

    Frequency bands (standard):
    - VLF: 0.0033-0.04 Hz (very low frequency)
    - LF: 0.04-0.15 Hz (low frequency - sympathetic + parasympathetic)
    - HF: 0.15-0.4 Hz (high frequency - parasympathetic/vagal)

    Returns:
        Tuple of (figure, stats_dict) for external display, or (None, None) on error
    """
    go, _ = get_plotly_analysis()
    if go is None:
        return None, None

    colors = _get_colors()
    nk = get_neurokit()
    if nk is None:
        return None, None

    try:
        rr = np.array(rr_intervals)

        # Interpolate RR intervals to uniform time series
        time_rr = np.cumsum(rr) / 1000.0
        time_rr = time_rr - time_rr[0]

        duration = time_rr[-1]
        time_uniform = np.arange(0, duration, 1 / sampling_rate)

        rr_interp = np.interp(time_uniform, time_rr, rr)
        rr_detrend = rr_interp - np.mean(rr_interp)

        # Compute PSD using Welch's method
        from scipy import signal

        nperseg = min(256, len(rr_detrend) // 2)
        if nperseg < 16:
            nperseg = len(rr_detrend)

        freqs, psd = signal.welch(rr_detrend, fs=sampling_rate, nperseg=nperseg)

        # Filter to relevant frequency range
        mask = freqs <= 0.5
        freqs = freqs[mask]
        psd = psd[mask]

        # Calculate band powers
        vlf_mask = (freqs >= 0.0033) & (freqs < 0.04)
        lf_mask = (freqs >= 0.04) & (freqs < 0.15)
        hf_mask = (freqs >= 0.15) & (freqs <= 0.4)

        vlf_power = np.trapz(psd[vlf_mask], freqs[vlf_mask]) if np.any(vlf_mask) else 0
        lf_power = np.trapz(psd[lf_mask], freqs[lf_mask]) if np.any(lf_mask) else 0
        hf_power = np.trapz(psd[hf_mask], freqs[hf_mask]) if np.any(hf_mask) else 0
        total_power = vlf_power + lf_power + hf_power

        lf_hf_ratio = lf_power / hf_power if hf_power > 0 else 0
        lf_pct = 100 * lf_power / total_power if total_power > 0 else 0
        hf_pct = 100 * hf_power / total_power if total_power > 0 else 0

        # Stats for external display (tuples for values with percentage delta)
        stats = {
            "VLF Power": _format_power(vlf_power),
            "LF Power": (_format_power(lf_power), f"{lf_pct:.0f}%"),
            "HF Power": (_format_power(hf_power), f"{hf_pct:.0f}%"),
            "LF/HF Ratio": f"{lf_hf_ratio:.2f}",
            "Total Power": _format_power(total_power),
        }

        # Create figure
        fig = go.Figure()

        max_psd = np.max(psd) * 1.1

        # VLF band with label
        fig.add_trace(
            go.Scatter(
                x=[0.0033, 0.04, 0.04, 0.0033],
                y=[0, 0, max_psd, max_psd],
                fill="toself",
                fillcolor=colors["vlf_band"],
                line=dict(width=0),
                name=f"VLF ({_format_power(vlf_power)})",
                hoverinfo="name",
            )
        )

        # LF band with label
        fig.add_trace(
            go.Scatter(
                x=[0.04, 0.15, 0.15, 0.04],
                y=[0, 0, max_psd, max_psd],
                fill="toself",
                fillcolor=colors["lf_band"],
                line=dict(width=0),
                name=f"LF ({_format_power(lf_power)}, {lf_pct:.0f}%)",
                hoverinfo="name",
            )
        )

        # HF band with label
        fig.add_trace(
            go.Scatter(
                x=[0.15, 0.4, 0.4, 0.15],
                y=[0, 0, max_psd, max_psd],
                fill="toself",
                fillcolor=colors["hf_band"],
                line=dict(width=0),
                name=f"HF ({_format_power(hf_power)}, {hf_pct:.0f}%)",
                hoverinfo="name",
            )
        )

        # Add PSD line
        fig.add_trace(
            go.Scatter(
                x=freqs.tolist(),
                y=psd.tolist(),
                mode="lines",
                line=dict(color=colors["rr_line"], width=2.5),
                name="PSD",
                hovertemplate="Freq: %{x:.3f} Hz<br>Power: %{y:.1f} ms²/Hz<extra></extra>",
            )
        )

        # Add band boundary lines and labels
        for freq, label in [(0.04, "VLF|LF"), (0.15, "LF|HF"), (0.4, "HF")]:
            fig.add_vline(
                x=freq,
                line=dict(color="gray", width=1, dash="dot"),
                annotation_text=f"{freq}",
                annotation_position="top",
                annotation=dict(font_size=9, font_color="gray"),
            )

        # Update layout - legend below plot
        theme = get_theme_colors()
        fig.update_layout(
            title=dict(
                text=f"<b>Power Spectral Density</b> — {section_label}",
                font=dict(size=16, color=theme["text"]),
            ),
            xaxis=dict(
                title=dict(text="Frequency (Hz)", font=dict(color=theme["text"])),
                showgrid=True,
                gridcolor=theme["grid"],
                range=[0, 0.5],
                tickvals=[0, 0.04, 0.15, 0.4, 0.5],
                ticktext=["0", "0.04", "0.15", "0.4", "0.5"],
                tickfont=dict(color=theme["text"]),
            ),
            yaxis=dict(
                title=dict(text="Power (ms²/Hz)", font=dict(color=theme["text"])),
                showgrid=True,
                gridcolor=theme["grid"],
                rangemode="tozero",
                tickfont=dict(color=theme["text"]),
            ),
            height=420,
            margin=dict(l=60, r=20, t=50, b=90),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.18,
                xanchor="center",
                x=0.5,
                font=dict(color=theme["text"]),
            ),
            plot_bgcolor=theme["bg"],
            paper_bgcolor=theme["bg"],
            font=dict(color=theme["text"]),
        )

        return fig, stats

    except Exception:
        return None, None


def create_hr_distribution_plot(rr_intervals: list, section_label: str):
    """Create a heart rate distribution histogram with density curve.

    Returns:
        Tuple of (figure, stats_dict) for external display of statistics
    """
    go, make_subplots = get_plotly_analysis()
    if go is None:
        return None, {}

    colors = _get_colors()
    rr = np.array(rr_intervals)
    hr = 60000 / rr  # Convert to beats per minute

    # Calculate statistics
    mean_hr = np.mean(hr)
    std_hr = np.std(hr)
    min_hr = np.min(hr)
    max_hr = np.max(hr)

    # Stats for external display
    stats = {
        "Mean HR": f"{mean_hr:.1f} bpm",
        "SD": f"{std_hr:.1f} bpm",
        "Min": f"{min_hr:.0f} bpm",
        "Max": f"{max_hr:.0f} bpm",
        "Range": f"{max_hr - min_hr:.0f} bpm",
    }

    # Create figure with secondary y-axis
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # Add histogram
    fig.add_trace(
        go.Histogram(
            x=hr.tolist(),
            nbinsx=30,
            name="Distribution",
            marker_color=colors["rr_line"],
            opacity=0.7,
            hovertemplate="HR: %{x:.0f} bpm<br>Count: %{y}<extra></extra>",
        ),
        secondary_y=False,
    )

    # Add KDE (kernel density estimate) curve
    try:
        from scipy import stats as sp_stats

        kde = sp_stats.gaussian_kde(hr)
        x_kde = np.linspace(min_hr - 5, max_hr + 5, 200)
        y_kde = kde(x_kde)
        y_kde_scaled = y_kde * len(hr) * (max_hr - min_hr) / 30

        fig.add_trace(
            go.Scatter(
                x=x_kde.tolist(),
                y=y_kde_scaled.tolist(),
                mode="lines",
                name="Density",
                line=dict(color=colors["nn_line"], width=3),
                hoverinfo="skip",
            ),
            secondary_y=False,
        )
    except ImportError:
        pass

    # Add mean line
    fig.add_vline(
        x=mean_hr,
        line=dict(color=colors["exclusion"], width=2, dash="dash"),
        annotation_text=f"Mean: {mean_hr:.1f}",
        annotation_position="top",
    )

    # Update layout - legend below plot
    theme = get_theme_colors()
    fig.update_layout(
        title=dict(
            text=f"<b>Heart Rate Distribution</b> — {section_label}",
            font=dict(size=16, color=theme["text"]),
        ),
        xaxis=dict(
            title=dict(text="Heart Rate (bpm)", font=dict(color=theme["text"])),
            showgrid=True,
            gridcolor=theme["grid"],
            tickfont=dict(color=theme["text"]),
        ),
        yaxis=dict(
            title=dict(text="Count", font=dict(color=theme["text"])),
            showgrid=True,
            gridcolor=theme["grid"],
            tickfont=dict(color=theme["text"]),
        ),
        height=350,
        margin=dict(l=60, r=20, t=50, b=90),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.25,
            xanchor="center",
            x=0.5,
            font=dict(color=theme["text"]),
        ),
        plot_bgcolor=theme["bg"],
        paper_bgcolor=theme["bg"],
        font=dict(color=theme["text"]),
        bargap=0.05,
    )

    return fig, stats
