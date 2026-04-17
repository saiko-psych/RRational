"""Group analysis visualization functions.

Returns Plotly figures — no Streamlit dependency.
"""

from __future__ import annotations

import pandas as pd

from rrational.analysis.hrv_metrics import get_metric_info
from rrational.gui.plots.analysis_plots import get_theme_colors, get_plotly_analysis


def _get_group_palette() -> list[str]:
    """Get group color palette from user config or defaults."""
    try:
        from rrational.gui.theme import get_plot_colors

        from rrational.gui.color_scheme import ColorScheme

        return get_plot_colors().get("group_palette", ColorScheme().group_palette)
    except Exception:
        from rrational.gui.color_scheme import ColorScheme

        return ColorScheme().group_palette


def _compute_error_values(sd: float, n: int, error_type: str) -> float:
    """Compute error bar magnitude from SD and n.

    Args:
        sd: Standard deviation
        n: Sample size
        error_type: "SD" | "SEM" | "CI95" | "None"

    Returns:
        Error bar half-width (symmetric around mean)
    """
    import math

    if error_type == "None" or sd is None or n is None or n < 1:
        return 0.0
    if error_type == "SD":
        return sd
    sem = sd / math.sqrt(n) if n > 0 else 0.0
    if error_type == "SEM":
        return sem
    if error_type == "CI95":
        # 1.96 for large n; t-critical would be more precise for small n
        # but Welch approximation works fine for typical HRV group sizes (n≥10)
        return 1.96 * sem
    return sd


def _create_group_bar_chart(
    stats_df: pd.DataFrame,
    metric: str,
    sections: list[str] | None = None,
    error_bar_type: str = "SD",
    long_df: pd.DataFrame | None = None,
    show_points: bool = False,
    log_y: bool = False,
):
    """Create a grouped bar chart for HRV metrics.

    Args:
        stats_df: DataFrame from _calculate_group_stats (must include 'n' column)
        metric: Metric to plot (e.g., "RMSSD", "SDNN")
        sections: Optional list of sections to include
        error_bar_type: "SD" | "SEM" | "CI95" | "None"
        long_df: Long-format per-participant data. Required for show_points.
        show_points: If True, overlay individual participant data points on bars.
        log_y: If True, use logarithmic y-axis (useful for LF/HF power).

    Returns:
        Plotly Figure object
    """
    go, _ = get_plotly_analysis()
    if go is None:
        return None

    import numpy as np

    # Filter to specific metric
    df = stats_df[stats_df["metric"] == metric.upper()].copy()
    if df.empty:
        return None

    # Filter sections if specified
    if sections:
        df = df[df["section"].isin(sections)]

    # Get unique groups and sections
    groups = df["group"].unique().tolist()
    section_list = df["section"].unique().tolist()

    # Colors for sections
    colors = _get_group_palette()

    fig = go.Figure()

    show_error_bars = error_bar_type != "None"
    n_sections = len(section_list)

    # Plotly grouped bars use a negative-to-positive offset range.
    # For N sections, centers are at: -0.375 + (i+0.5) * 0.75/N (default gap)
    # Simpler: compute offset index and use x-jitter around category center.
    bar_width_fraction = 0.75  # default Plotly barmode="group" group width

    for i, section in enumerate(section_list):
        section_df = df[df["section"] == section]

        # Align with groups (may have missing data)
        means = []
        errors = []
        for group in groups:
            group_row = section_df[section_df["group"] == group]
            if not group_row.empty:
                mean_val = group_row["mean"].values[0]
                sd_val = group_row["sd"].values[0]
                n_val = int(group_row["n"].values[0]) if "n" in group_row.columns else 1
                means.append(mean_val)
                errors.append(_compute_error_values(sd_val, n_val, error_bar_type))
            else:
                means.append(None)
                errors.append(None)

        fig.add_trace(
            go.Bar(
                name=section,
                x=groups,
                y=means,
                error_y=dict(type="data", array=errors, visible=show_error_bars),
                marker_color=colors[i % len(colors)],
                opacity=0.8 if show_points else 1.0,
            )
        )

    # Overlay individual data points if requested
    if show_points and long_df is not None and not long_df.empty:
        metric_lower = metric.lower()
        if metric_lower in long_df.columns:
            rng = np.random.default_rng(42)  # Reproducible jitter
            for i, section in enumerate(section_list):
                # Section offset within the group cluster
                # Plotly's default: bars centered at -0.5 + (i+0.5)/N inside each category
                section_offset = (i - (n_sections - 1) / 2) * (
                    bar_width_fraction / n_sections
                )

                for group_idx, group in enumerate(groups):
                    subset = long_df[
                        (long_df["group"] == group) & (long_df["section"] == section)
                    ]
                    values = subset[metric_lower].dropna().tolist()
                    if not values:
                        continue

                    n_points = len(values)
                    # Jitter within ± half the per-section slot width
                    jitter_spread = (bar_width_fraction / n_sections) * 0.3
                    jitter = rng.uniform(-jitter_spread, jitter_spread, size=n_points)
                    x_positions = [group_idx + section_offset + j for j in jitter]

                    fig.add_trace(
                        go.Scatter(
                            x=x_positions,
                            y=values,
                            mode="markers",
                            marker=dict(
                                size=4,
                                color="rgba(0,0,0,0.6)",
                                line=dict(width=0),
                            ),
                            name=f"{section} points",
                            showlegend=False,
                            hovertemplate=(
                                f"<b>{group}</b> — {section}<br>"
                                "%{y:.2f}<extra></extra>"
                            ),
                        )
                    )

    # Get theme colors
    theme = get_theme_colors()

    fig.update_layout(
        title=dict(
            text=f"{metric.upper()} by Group and Section",
            font=dict(size=16),
        ),
        xaxis_title="Group",
        yaxis_title=f"{metric.upper()} (ms)"
        if metric.upper() not in ["LF_HF", "PNN50"]
        else metric.upper(),
        barmode="group",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        plot_bgcolor=theme["bg"],
        paper_bgcolor=theme["bg"],
        font=dict(color=theme["text"]),
        margin=dict(l=60, r=20, t=80, b=60),
    )

    fig.update_xaxes(
        gridcolor=theme["grid"], showline=True, linewidth=1, linecolor=theme["grid"]
    )
    fig.update_yaxes(
        gridcolor=theme["grid"],
        showline=True,
        linewidth=1,
        linecolor=theme["grid"],
        type="log" if log_y else "linear",
    )

    return fig


def _create_box_violin_plot(
    long_df: pd.DataFrame,
    metric: str,
    plot_type: str = "box",
    group_by: str = "group",
    color_by: str = "section",
):
    """Create a box plot or violin plot for HRV metrics.

    Args:
        long_df: Long-format DataFrame from _results_to_long_df
        metric: Metric column name (lowercase)
        plot_type: "box" or "violin"
        group_by: Column to use for x-axis grouping
        color_by: Column to use for color grouping

    Returns:
        Plotly Figure object
    """
    go, _ = get_plotly_analysis()
    if go is None:
        return None

    metric_lower = metric.lower()
    if metric_lower not in long_df.columns:
        return None

    # Filter out NaN values
    df = long_df[long_df[metric_lower].notna()].copy()
    if df.empty:
        return None

    theme = get_theme_colors()
    colors = _get_group_palette()

    fig = go.Figure()

    color_categories = df[color_by].unique().tolist()

    for i, color_cat in enumerate(color_categories):
        subset = df[df[color_by] == color_cat]

        if plot_type == "violin":
            fig.add_trace(
                go.Violin(
                    x=subset[group_by],
                    y=subset[metric_lower],
                    name=str(color_cat),
                    legendgroup=str(color_cat),
                    scalegroup=str(color_cat),
                    line_color=colors[i % len(colors)],
                    fillcolor=colors[i % len(colors)],
                    opacity=0.6,
                    box_visible=True,
                    meanline_visible=True,
                    points="all",
                    pointpos=0,
                    jitter=0.05,
                )
            )
        else:  # box plot
            fig.add_trace(
                go.Box(
                    x=subset[group_by],
                    y=subset[metric_lower],
                    name=str(color_cat),
                    legendgroup=str(color_cat),
                    marker_color=colors[i % len(colors)],
                    line_color=colors[i % len(colors)],
                    boxpoints="all",
                    jitter=0.3,
                    pointpos=-1.8,
                )
            )

    # Get metric info for labels
    metric_info = get_metric_info(metric.upper())
    unit_str = f" ({metric_info['unit']})" if metric_info.get("unit") else ""

    fig.update_layout(
        title=dict(
            text=f"{metric.upper()} Distribution by {group_by.title()}",
            font=dict(size=16),
        ),
        xaxis_title=group_by.title(),
        yaxis_title=f"{metric.upper()}{unit_str}",
        boxmode="group" if plot_type == "box" else None,
        violinmode="group" if plot_type == "violin" else None,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        plot_bgcolor=theme["bg"],
        paper_bgcolor=theme["bg"],
        font=dict(color=theme["text"]),
        margin=dict(l=60, r=20, t=80, b=60),
    )

    fig.update_xaxes(
        gridcolor=theme["grid"], showline=True, linewidth=1, linecolor=theme["grid"]
    )
    fig.update_yaxes(
        gridcolor=theme["grid"], showline=True, linewidth=1, linecolor=theme["grid"]
    )

    return fig


def _create_sd1_sd2_scatter(
    long_df: pd.DataFrame,
    color_by: str = "group",
):
    """Create SD1 vs SD2 scatter plot (Poincaré-derived measures).

    Args:
        long_df: Long-format DataFrame from _results_to_long_df
        color_by: Column to use for color grouping ("group" or "section")

    Returns:
        Plotly Figure object
    """
    go, _ = get_plotly_analysis()
    if go is None:
        return None

    # Check if SD1 and SD2 are available
    if "sd1" not in long_df.columns or "sd2" not in long_df.columns:
        return None

    # Filter out NaN values
    df = long_df[long_df["sd1"].notna() & long_df["sd2"].notna()].copy()
    if df.empty:
        return None

    theme = get_theme_colors()
    colors = _get_group_palette()

    fig = go.Figure()

    categories = df[color_by].unique().tolist()

    for i, cat in enumerate(categories):
        subset = df[df[color_by] == cat]

        fig.add_trace(
            go.Scatter(
                x=subset["sd2"],
                y=subset["sd1"],
                mode="markers",
                name=str(cat),
                marker=dict(
                    size=10,
                    color=colors[i % len(colors)],
                    opacity=0.7,
                    line=dict(width=1, color="white"),
                ),
                text=subset["participant_id"],
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "SD1: %{y:.2f} ms<br>"
                    "SD2: %{x:.2f} ms<br>"
                    "<extra></extra>"
                ),
            )
        )

    # Add reference line (SD1 = SD2 means circular Poincaré)
    max_val = max(df["sd1"].max(), df["sd2"].max()) * 1.1
    fig.add_trace(
        go.Scatter(
            x=[0, max_val],
            y=[0, max_val],
            mode="lines",
            name="SD1 = SD2",
            line=dict(color="gray", dash="dash", width=1),
            showlegend=True,
        )
    )

    fig.update_layout(
        title=dict(
            text="Poincaré Plot Measures: SD1 vs SD2",
            font=dict(size=16),
        ),
        xaxis_title="SD2 (ms) - Long-term variability",
        yaxis_title="SD1 (ms) - Short-term variability",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        plot_bgcolor=theme["bg"],
        paper_bgcolor=theme["bg"],
        font=dict(color=theme["text"]),
        margin=dict(l=60, r=20, t=80, b=60),
    )

    fig.update_xaxes(
        gridcolor=theme["grid"], showline=True, linewidth=1, linecolor=theme["grid"]
    )
    fig.update_yaxes(
        gridcolor=theme["grid"],
        showline=True,
        linewidth=1,
        linecolor=theme["grid"],
        scaleanchor="x",
    )

    return fig


def _create_raincloud_plot(
    long_df: pd.DataFrame,
    metric: str,
    group_by: str = "group",
    color_by: str = "section",
):
    """Create a raincloud plot (half-violin + box + strip).

    Raincloud plots combine:
    - Half-violin showing distribution
    - Box plot showing quartiles
    - Individual points (strip/jitter)

    Args:
        long_df: Long-format DataFrame from _results_to_long_df
        metric: Metric column name (lowercase)
        group_by: Column for x-axis grouping
        color_by: Column for color grouping

    Returns:
        Plotly Figure object
    """
    go, _ = get_plotly_analysis()
    if go is None:
        return None

    metric_lower = metric.lower()
    if metric_lower not in long_df.columns:
        return None

    # Filter out NaN values
    df = long_df[long_df[metric_lower].notna()].copy()
    if df.empty:
        return None

    theme = get_theme_colors()
    colors = _get_group_palette()

    fig = go.Figure()

    color_categories = df[color_by].unique().tolist()

    for i, color_cat in enumerate(color_categories):
        subset = df[df[color_by] == color_cat]
        color = colors[i % len(colors)]

        # Half violin (positive side only)
        fig.add_trace(
            go.Violin(
                x=subset[group_by],
                y=subset[metric_lower],
                name=str(color_cat),
                legendgroup=str(color_cat),
                side="positive",
                line_color=color,
                fillcolor=color,
                opacity=0.5,
                meanline_visible=False,
                points=False,
                width=0.8,
            )
        )

        # Box plot (narrow, on left side)
        fig.add_trace(
            go.Box(
                x=subset[group_by],
                y=subset[metric_lower],
                name=str(color_cat),
                legendgroup=str(color_cat),
                marker_color=color,
                line_color=color,
                boxpoints=False,
                width=0.15,
                showlegend=False,
            )
        )

        # Individual points (strip with jitter)
        fig.add_trace(
            go.Scatter(
                x=[f"{g}" for g in subset[group_by]],
                y=subset[metric_lower],
                mode="markers",
                name=str(color_cat),
                legendgroup=str(color_cat),
                marker=dict(
                    size=5,
                    color=color,
                    opacity=0.6,
                ),
                showlegend=False,
                # Add jitter
                hovertemplate=(
                    f"<b>{color_cat}</b><br>"
                    f"{metric.upper()}: %{{y:.2f}}<br>"
                    "<extra></extra>"
                ),
            )
        )

    # Get metric info for labels
    metric_info = get_metric_info(metric.upper())
    unit_str = f" ({metric_info['unit']})" if metric_info.get("unit") else ""

    fig.update_layout(
        title=dict(
            text=f"{metric.upper()} Raincloud Plot by {group_by.title()}",
            font=dict(size=16),
        ),
        xaxis_title=group_by.title(),
        yaxis_title=f"{metric.upper()}{unit_str}",
        violinmode="group",
        boxmode="group",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
        plot_bgcolor=theme["bg"],
        paper_bgcolor=theme["bg"],
        font=dict(color=theme["text"]),
        margin=dict(l=60, r=20, t=80, b=60),
    )

    fig.update_xaxes(
        gridcolor=theme["grid"], showline=True, linewidth=1, linecolor=theme["grid"]
    )
    fig.update_yaxes(
        gridcolor=theme["grid"], showline=True, linewidth=1, linecolor=theme["grid"]
    )

    return fig
