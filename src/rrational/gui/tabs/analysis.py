"""Analysis tab - HRV analysis with NeuroKit2.

This module contains the render function for the Analysis tab.
Provides HRV metrics computation and visualization.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from rrational.gui.shared import (  # noqa: E402
    NEUROKIT_AVAILABLE,
    get_neurokit,
    get_matplotlib,
    get_participant_list,
    get_summary_dict,
    extract_section_rr_intervals,
    filter_exclusion_zones,
    detect_artifacts_fixpeaks,
    show_toast,
    cached_discover_recordings,
    cached_load_recording,
    cached_load_vns_recording,
)
from rrational.gui.help_text import ANALYSIS_HELP  # noqa: E402
from rrational.gui.rrational_export import (  # noqa: E402
    find_rrational_files,
    load_rrational,
    load_rrational_v2,
    get_rrational_version,
    RRATIONAL_VERSION_V2,
)
from rrational.analysis.hrv_metrics import (  # noqa: E402
    ParticipantSectionResult,
    HRV_METRICS_CATALOG,
    HRV_METRIC_PRESETS,
    ALL_HRV_METRICS,
    HRV_REFERENCE_VALUES,
    MIN_BEATS_TIME_DOMAIN,
    MIN_BEATS_FREQUENCY_DOMAIN,
    MIN_DURATION_FREQUENCY_DOMAIN_SEC,
    get_metric_info,
    format_power as _format_power,
    format_duration as _format_duration,
    generate_overlapping_windows_beats,
    aggregate_hrv_results,
)
from rrational.analysis.hrv_compute import (  # noqa: E402
    calculate_hrv_metrics as _calculate_hrv_metrics,
    results_to_long_df as _results_to_long_df,
    results_to_wide_df as _results_to_wide_df,
    calculate_group_stats as _calculate_group_stats,
)
from rrational.gui.plots.analysis_plots import (  # noqa: E402
    get_theme_colors,
    get_plotly_analysis,
    create_professional_tachogram,
    create_poincare_plot,
    create_frequency_domain_plot,
    create_hr_distribution_plot,
)
from rrational.gui.plots.group_plots import (  # noqa: E402
    _create_group_bar_chart,
    _create_box_violin_plot,
    _create_sd1_sd2_scatter,
    _create_raincloud_plot,
)


# =============================================================================
# NOTE: HRV metric catalogs, presets, constants, window generation, and
# compute functions have been extracted to:
#   rrational.analysis.hrv_metrics
#   rrational.analysis.hrv_compute
# They are imported at the top of this file.
# =============================================================================


# Window generation and aggregation functions are now in rrational.analysis.hrv_metrics
# and imported at the top of this file.


# =============================================================================
# PROFESSIONAL HRV VISUALIZATION FUNCTIONS
# =============================================================================


# _format_power imported from rrational.analysis.hrv_metrics


# Educational resources for HRV visualizations
VISUALIZATION_RESOURCES = {
    "tachogram": {
        "title": "Tachogram (RR Interval Plot)",
        "description": """
The tachogram displays beat-to-beat RR intervals over time. It's the primary visualization
for inspecting raw HRV data and identifying artifacts, trends, and patterns.

**What to look for:**
- **Stable baseline**: Healthy HRV shows regular oscillation around the mean
- **Sudden spikes/drops**: May indicate artifacts, ectopic beats, or missed detections
- **Trends**: Gradual changes may reflect autonomic shifts (e.g., relaxation, stress)
- **±1 SD band**: ~68% of intervals should fall within this range
- **±2 SD band**: ~95% of intervals should fall within this range
        """,
        "references": [
            (
                "Task Force (1996) - HRV Standards",
                "https://doi.org/10.1161/01.CIR.93.5.1043",
            ),
            (
                "Shaffer & Ginsberg (2017) - HRV Overview",
                "https://doi.org/10.3389/fpubh.2017.00258",
            ),
        ],
    },
    "poincare": {
        "title": "Poincaré Plot (Return Map)",
        "description": """
The Poincaré plot shows each RR interval against the next one (RR[n] vs RR[n+1]).
It visualizes short-term and long-term variability in a single view.

**Key measures:**
- **SD1** (perpendicular to identity line): Short-term, beat-to-beat variability
  - Reflects parasympathetic (vagal) activity
  - Related to RMSSD
- **SD2** (along identity line): Long-term variability
  - Reflects overall HRV including sympathetic influences
  - Related to SDNN
- **SD1/SD2 ratio**: Shape of the ellipse
  - Low ratio (<0.5): Reduced short-term variability
  - Normal ratio (0.5-1.0): Balanced variability
        """,
        "references": [
            (
                "Brennan et al. (2001) - Poincaré Plot Analysis",
                "https://doi.org/10.1109/10.959330",
            ),
            (
                "Guzik et al. (2007) - Poincaré Plot Asymmetry",
                "https://doi.org/10.1088/0967-3334/28/3/N01",
            ),
        ],
    },
    "frequency": {
        "title": "Power Spectral Density (Frequency Domain)",
        "description": """
Frequency domain analysis decomposes HRV into oscillatory components using spectral analysis.
Different frequency bands reflect different physiological mechanisms.

**Frequency bands:**
- **VLF (0.0033-0.04 Hz)**: Very Low Frequency
  - Thermoregulation, hormonal fluctuations
  - Requires long recordings (>5 min) for reliable estimation
- **LF (0.04-0.15 Hz)**: Low Frequency
  - Mixed sympathetic and parasympathetic activity
  - Baroreflex activity, blood pressure regulation
- **HF (0.15-0.4 Hz)**: High Frequency
  - Primarily parasympathetic (vagal) activity
  - Respiratory sinus arrhythmia

**LF/HF Ratio interpretation:**
- <1.0: Parasympathetic dominant
- 1.0-2.0: Balanced autonomic activity
- >2.0: Sympathetic dominant
        """,
        "references": [
            (
                "Task Force (1996) - Frequency Bands",
                "https://doi.org/10.1161/01.CIR.93.5.1043",
            ),
            (
                "Laborde et al. (2017) - HRV and Cardiac Vagal Tone",
                "https://doi.org/10.3389/fpsyg.2017.00213",
            ),
        ],
    },
    "hr_distribution": {
        "title": "Heart Rate Distribution",
        "description": """
The heart rate distribution histogram shows the frequency of different heart rate values
during the recording period.

**What to look for:**
- **Normal distribution**: Most healthy recordings show approximately normal distribution
- **Skewness**: May indicate periods of sustained high or low HR
- **Multiple peaks**: Could indicate distinct activity states or artifacts
- **Width (SD)**: Reflects overall HR variability

**Normal resting HR ranges:**
- Adults: 60-100 BPM (athletes may have lower)
- Well-trained athletes: 40-60 BPM
        """,
        "references": [
            (
                "Nunan et al. (2010) - Normal HR Values",
                "https://doi.org/10.1097/HJR.0b013e32833e4598",
            ),
        ],
    },
}


def display_hrv_metrics_professional(
    hrv_results: pd.DataFrame,
    n_beats: int,
    artifact_info: dict = None,
    recording_duration_sec: float = None,
) -> None:
    """Display HRV metrics using pure Streamlit native components.

    Clean, professional design that works in both light and dark modes.
    Uses only native Streamlit components - no custom HTML/CSS.
    """

    # Extract key metrics
    rmssd = (
        hrv_results.get("HRV_RMSSD", [0]).iloc[0]
        if "HRV_RMSSD" in hrv_results.columns
        else 0
    )
    sdnn = (
        hrv_results.get("HRV_SDNN", [0]).iloc[0]
        if "HRV_SDNN" in hrv_results.columns
        else 0
    )
    pnn50 = (
        hrv_results.get("HRV_pNN50", [0]).iloc[0]
        if "HRV_pNN50" in hrv_results.columns
        else 0
    )
    lf_hf = (
        hrv_results.get("HRV_LFHF", [0]).iloc[0]
        if "HRV_LFHF" in hrv_results.columns
        else 0
    )
    hf = (
        hrv_results.get("HRV_HF", [0]).iloc[0] if "HRV_HF" in hrv_results.columns else 0
    )
    lf = (
        hrv_results.get("HRV_LF", [0]).iloc[0] if "HRV_LF" in hrv_results.columns else 0
    )
    mean_hr = (
        hrv_results.get("HRV_MeanNN", [0]).iloc[0]
        if "HRV_MeanNN" in hrv_results.columns
        else 0
    )
    if mean_hr > 0:
        mean_hr_bpm = 60000 / mean_hr  # Convert ms to BPM
    else:
        mean_hr_bpm = 0

    # Calculate total power for percentages
    total_power = lf + hf if (lf + hf) > 0 else 1
    lf_pct = (lf / total_power) * 100
    hf_pct = (hf / total_power) * 100

    # Duration display
    duration_min = recording_duration_sec / 60 if recording_duration_sec else 0

    # Data quality assessment
    quality_issues = []
    if n_beats < MIN_BEATS_TIME_DOMAIN:
        quality_issues.append(
            f"Low beat count: {n_beats} (min: {MIN_BEATS_TIME_DOMAIN})"
        )
    if n_beats < MIN_BEATS_FREQUENCY_DOMAIN:
        quality_issues.append(
            f"Insufficient for frequency domain: {n_beats}/{MIN_BEATS_FREQUENCY_DOMAIN} beats"
        )
    if (
        recording_duration_sec
        and recording_duration_sec < MIN_DURATION_FREQUENCY_DOMAIN_SEC
    ):
        quality_issues.append(
            f"Short recording: {duration_min:.1f} min (recommended: ≥5 min)"
        )

    # === RECORDING SUMMARY ===
    st.markdown("##### Recording Summary")

    # Summary metrics row
    sum_col1, sum_col2, sum_col3, sum_col4 = st.columns(4)
    with sum_col1:
        st.metric("Total Beats", f"{n_beats:,}")
    with sum_col2:
        st.metric("Duration", f"{duration_min:.1f} min")
    with sum_col3:
        st.metric("Mean HR", f"{mean_hr_bpm:.0f} BPM")
    with sum_col4:
        if artifact_info:
            # Support both 'artifact_rate' (v2) and 'artifact_ratio' (v1) keys
            artifact_rate = artifact_info.get(
                "artifact_rate", artifact_info.get("artifact_ratio", 0)
            )
            artifact_count = artifact_info.get("total_artifacts", 0)
            artifact_pct = artifact_rate * 100
            st.metric("Artifacts", f"{artifact_count} ({artifact_pct:.2f}%)")
        else:
            # Data quality indicator
            if not quality_issues:
                st.metric("Data Quality", "Good", delta="*", delta_color="normal")
            elif len(quality_issues) == 1:
                st.metric("Data Quality", "Fair", delta="!", delta_color="off")
            else:
                st.metric("Data Quality", "Limited", delta="(!)", delta_color="inverse")

    # Show quality warnings if any
    if quality_issues:
        with st.expander("Data Quality Notes", expanded=False):
            for issue in quality_issues:
                st.warning(issue)

    st.divider()

    # === TIME DOMAIN METRICS ===
    st.markdown("##### Time Domain")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        rmssd_ref = HRV_REFERENCE_VALUES["RMSSD"]
        # Interpretation
        if rmssd >= rmssd_ref["high"]:
            delta_text = "High"
            delta_color = "normal"
        elif rmssd >= rmssd_ref["low"]:
            delta_text = "Normal"
            delta_color = "off"
        else:
            delta_text = "Low"
            delta_color = "inverse"
        st.metric(
            "RMSSD",
            f"{rmssd:.1f} ms",
            delta=delta_text,
            delta_color=delta_color,
            help=f"Parasympathetic indicator. Reference: {rmssd_ref['low']}–{rmssd_ref['high']} ms",
        )

    with col2:
        sdnn_ref = HRV_REFERENCE_VALUES["SDNN"]
        if sdnn >= sdnn_ref["low"]:
            delta_text = "Normal"
            delta_color = "off"
        else:
            delta_text = "Low"
            delta_color = "inverse"
        st.metric(
            "SDNN",
            f"{sdnn:.1f} ms",
            delta=delta_text,
            delta_color=delta_color,
            help=f"Overall HRV. Reference: ≥{sdnn_ref['low']} ms",
        )

    with col3:
        pnn_ref = HRV_REFERENCE_VALUES["pNN50"]
        if pnn50 >= pnn_ref["high"]:
            delta_text = "High"
            delta_color = "normal"
        elif pnn50 >= pnn_ref["low"]:
            delta_text = "Normal"
            delta_color = "off"
        else:
            delta_text = "Low"
            delta_color = "inverse"
        st.metric(
            "pNN50",
            f"{pnn50:.1f}%",
            delta=delta_text,
            delta_color=delta_color,
            help=f"% of RR differences >50ms. Reference: {pnn_ref['low']}–{pnn_ref['high']}%",
        )

    with col4:
        # Heart rate interpretation
        if 60 <= mean_hr_bpm <= 100:
            delta_text = "Normal"
            delta_color = "off"
        elif mean_hr_bpm < 60:
            delta_text = "Bradycardia"
            delta_color = "off"
        else:
            delta_text = "Elevated"
            delta_color = "off"
        st.metric(
            "Mean HR",
            f"{mean_hr_bpm:.0f} BPM",
            delta=delta_text,
            delta_color=delta_color,
            help="Average heart rate. Normal resting: 60–100 BPM",
        )

    st.divider()

    # === FREQUENCY DOMAIN METRICS ===
    st.markdown("##### Frequency Domain")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "LF Power",
            _format_power(lf),
            delta=f"{lf_pct:.0f}%",
            delta_color="off",
            help="Low Frequency (0.04–0.15 Hz). Mixed sympathetic/parasympathetic.",
        )

    with col2:
        st.metric(
            "HF Power",
            _format_power(hf),
            delta=f"{hf_pct:.0f}%",
            delta_color="off",
            help="High Frequency (0.15–0.4 Hz). Parasympathetic/vagal activity.",
        )

    with col3:
        lf_hf_ref = HRV_REFERENCE_VALUES["LF_HF"]
        if lf_hf < lf_hf_ref["low"]:
            lfhf_delta = "PNS dominant"
        elif lf_hf < lf_hf_ref["high"]:
            lfhf_delta = "Balanced"
        else:
            lfhf_delta = "SNS dominant"
        st.metric(
            "LF/HF Ratio",
            f"{lf_hf:.2f}",
            delta=lfhf_delta,
            delta_color="off",
            help="Sympathovagal balance. <0.5: PNS dominant, 0.5–3.0: Balanced, >3.0: SNS dominant",
        )

    # Autonomic balance indicator using progress bar
    st.caption("Autonomic Balance")
    balance_col1, balance_col2, balance_col3 = st.columns([1, 3, 1])
    with balance_col1:
        st.caption("PNS")
    with balance_col2:
        # Use HF percentage as indicator (higher = more parasympathetic)
        st.progress(min(1.0, hf_pct / 100))
    with balance_col3:
        st.caption("SNS")


def create_hrv_metrics_card(
    hrv_results: pd.DataFrame,
    n_beats: int,
    artifact_info: dict = None,
    recording_duration_sec: float = None,
) -> str:
    """Legacy function - returns empty string. Use display_hrv_metrics_professional() instead."""
    return ""


def display_visualization_info(viz_type: str) -> None:
    """Display educational information about a visualization type.

    Args:
        viz_type: One of 'tachogram', 'poincare', 'frequency', 'hr_distribution'
    """
    if viz_type not in VISUALIZATION_RESOURCES:
        return

    info = VISUALIZATION_RESOURCES[viz_type]

    with st.expander(f"About: {info['title']}", expanded=False):
        st.markdown(info["description"])

        if info.get("references"):
            st.markdown("**References:**")
            for title, url in info["references"]:
                st.markdown(f"- [{title}]({url})")


class AnalysisDocumentation:
    """Generates documentation for HRV analysis procedures.

    This class captures all analysis parameters and generates a markdown
    report that can be exported for reproducibility and publication.
    """

    def __init__(self, participant_id: str):
        self.participant_id = participant_id
        self.timestamp = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        self.sections_analyzed = []
        self.cleaning_config = {}
        self.artifact_correction = False
        self.artifact_results = {}
        self.exclusion_zones = []
        self.hrv_results = {}
        self.data_source = ""
        self.total_beats_raw = 0
        self.total_beats_analyzed = 0
        self.recording_duration_sec = 0

    def set_data_source(self, source: str, raw_beats: int, duration_sec: float):
        """Set data source information."""
        self.data_source = source
        self.total_beats_raw = raw_beats
        self.recording_duration_sec = duration_sec

    def set_cleaning_config(self, config):
        """Set cleaning configuration used."""
        if config is None:
            self.cleaning_config = {}
        elif isinstance(config, dict):
            self.cleaning_config = config.copy()
        elif hasattr(config, "__dict__"):
            # Handle dataclass or object with attributes
            self.cleaning_config = {
                "rr_min_ms": getattr(config, "rr_min_ms", 200),
                "rr_max_ms": getattr(config, "rr_max_ms", 2000),
                "sudden_change_pct": getattr(config, "sudden_change_pct", 100),
            }
        else:
            self.cleaning_config = {}

    def set_artifact_correction(self, enabled: bool, results: dict = None):
        """Set artifact correction settings."""
        self.artifact_correction = enabled
        if results:
            self.artifact_results = results.copy()

    def add_section(
        self,
        name: str,
        label: str,
        start_event: str,
        end_events: list,
        beats_extracted: int,
        beats_after_cleaning: int,
    ):
        """Add a section to the documentation."""
        self.sections_analyzed.append(
            {
                "name": name,
                "label": label,
                "start_event": start_event,
                "end_events": end_events,
                "beats_extracted": beats_extracted,
                "beats_after_cleaning": beats_after_cleaning,
            }
        )
        self.total_beats_analyzed += beats_after_cleaning

    def add_exclusion_zones(self, zones: list):
        """Add exclusion zones used."""
        self.exclusion_zones = zones.copy() if zones else []

    def add_hrv_results(self, section_name: str, results: pd.DataFrame):
        """Add HRV results for a section."""
        if not results.empty:
            self.hrv_results[section_name] = results.to_dict("records")[0]

    def generate_markdown(self) -> str:
        """Generate a complete markdown documentation report."""
        lines = []

        # Header
        lines.append("# HRV Analysis Report")
        lines.append("")
        lines.append(f"**Participant:** {self.participant_id}")
        lines.append(f"**Generated:** {self.timestamp}")
        lines.append("**Software:** Music HRV Toolkit v0.6.8")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Data Source
        lines.append("## 1. Data Source")
        lines.append("")
        lines.append(f"- **Source Application:** {self.data_source}")
        lines.append(f"- **Total Raw Beats:** {self.total_beats_raw:,}")
        lines.append(
            f"- **Recording Duration:** {self.recording_duration_sec / 60:.1f} minutes"
        )
        lines.append("")

        # Data Preparation
        lines.append("## 2. Data Preparation")
        lines.append("")
        lines.append("### 2.1 Cleaning Thresholds")
        lines.append("")
        if self.cleaning_config:
            lines.append("| Parameter | Value |")
            lines.append("|-----------|-------|")
            lines.append(
                f"| Minimum RR | {self.cleaning_config.get('rr_min_ms', 200)} ms |"
            )
            lines.append(
                f"| Maximum RR | {self.cleaning_config.get('rr_max_ms', 2000)} ms |"
            )
            lines.append(
                f"| Sudden Change Threshold | {self.cleaning_config.get('sudden_change_pct', 100)}% |"
            )
        else:
            lines.append("*Default cleaning thresholds applied (200-2000 ms)*")
        lines.append("")

        # Exclusion Zones
        if self.exclusion_zones:
            lines.append("### 2.2 Exclusion Zones")
            lines.append("")
            lines.append("| Start | End | Reason |")
            lines.append("|-------|-----|--------|")
            for zone in self.exclusion_zones:
                start = zone.get("start", "N/A")
                end = zone.get("end", "N/A")
                reason = zone.get("reason", "Not specified")
                lines.append(f"| {start} | {end} | {reason} |")
            lines.append("")

        # Artifact Correction
        lines.append("### 2.3 Artifact Correction")
        lines.append("")
        if self.artifact_correction:
            lines.append("- **Method:** NeuroKit2 Kubios Algorithm")
            lines.append("- **Status:** Applied")
            if self.artifact_results:
                lines.append(
                    f"- **Artifacts Detected:** {self.artifact_results.get('total_artifacts', 'N/A')}"
                )
                lines.append(
                    f"- **Artifact Rate:** {self.artifact_results.get('artifact_ratio', 0) * 100:.1f}%"
                )
                if "artifact_types" in self.artifact_results:
                    lines.append("- **Artifact Types:**")
                    for atype, count in self.artifact_results["artifact_types"].items():
                        lines.append(f"  - {atype}: {count}")
        else:
            lines.append("- **Status:** Not applied (raw RR intervals used)")
        lines.append("")

        # Sections Analyzed
        lines.append("## 3. Sections Analyzed")
        lines.append("")
        if self.sections_analyzed:
            for section in self.sections_analyzed:
                lines.append(f"### {section['label']}")
                lines.append("")
                lines.append(f"- **Section Name:** {section['name']}")
                lines.append(f"- **Start Event:** `{section['start_event']}`")
                lines.append(
                    f"- **End Event(s):** `{', '.join(section['end_events'])}`"
                )
                lines.append(f"- **Beats Extracted:** {section['beats_extracted']:,}")
                lines.append(
                    f"- **Beats After Cleaning:** {section['beats_after_cleaning']:,}"
                )
                lines.append(
                    f"- **Data Retention:** {100 * section['beats_after_cleaning'] / max(section['beats_extracted'], 1):.1f}%"
                )
                lines.append("")
        else:
            lines.append("*No sections analyzed*")
            lines.append("")

        # HRV Results
        lines.append("## 4. HRV Results")
        lines.append("")
        if self.hrv_results:
            for section_name, results in self.hrv_results.items():
                label = (
                    section_name if section_name != "_combined" else "Combined Sections"
                )
                lines.append(f"### {label}")
                lines.append("")
                lines.append("#### Time Domain")
                lines.append("")
                lines.append("| Metric | Value | Unit |")
                lines.append("|--------|-------|------|")
                if "HRV_RMSSD" in results:
                    lines.append(f"| RMSSD | {results['HRV_RMSSD']:.2f} | ms |")
                if "HRV_SDNN" in results:
                    lines.append(f"| SDNN | {results['HRV_SDNN']:.2f} | ms |")
                if "HRV_pNN50" in results:
                    lines.append(f"| pNN50 | {results['HRV_pNN50']:.2f} | % |")
                if "HRV_MeanNN" in results:
                    mean_hr = (
                        60000 / results["HRV_MeanNN"]
                        if results["HRV_MeanNN"] > 0
                        else 0
                    )
                    lines.append(f"| Mean NN | {results['HRV_MeanNN']:.2f} | ms |")
                    lines.append(f"| Mean HR | {mean_hr:.1f} | BPM |")
                lines.append("")

                lines.append("#### Frequency Domain")
                lines.append("")
                lines.append("| Metric | Value | Unit |")
                lines.append("|--------|-------|------|")
                if "HRV_LF" in results:
                    lines.append(f"| LF Power | {results['HRV_LF']:.2f} | ms² |")
                if "HRV_HF" in results:
                    lines.append(f"| HF Power | {results['HRV_HF']:.2f} | ms² |")
                if "HRV_LFHF" in results:
                    lines.append(f"| LF/HF Ratio | {results['HRV_LFHF']:.2f} | - |")
                lines.append("")
        else:
            lines.append("*No HRV results available*")
            lines.append("")

        # Methods Summary
        lines.append("## 5. Methods Summary")
        lines.append("")
        lines.append("### For Publication")
        lines.append("")
        artifact_text = (
            "with Kubios artifact correction (NeuroKit2)"
            if self.artifact_correction
            else "without artifact correction"
        )
        sections_text = (
            ", ".join([s["label"] for s in self.sections_analyzed])
            if self.sections_analyzed
            else "all data"
        )

        lines.append("> HRV analysis was performed using Music HRV Toolkit (v0.6.8). ")
        lines.append(
            f"> RR intervals were extracted from {self.data_source} recordings "
        )
        lines.append(
            f"> and cleaned using threshold filtering (RR: {self.cleaning_config.get('rr_min_ms', 200)}-{self.cleaning_config.get('rr_max_ms', 2000)} ms). "
        )
        if self.exclusion_zones:
            lines.append(
                f"> {len(self.exclusion_zones)} exclusion zone(s) were applied to remove artifacts. "
            )
        lines.append(
            f"> Time-domain and frequency-domain HRV metrics were computed {artifact_text} "
        )
        lines.append("> using NeuroKit2 (Makowski et al., 2021). ")
        lines.append(
            f"> Analysis was performed on the following section(s): {sections_text}."
        )
        lines.append("")

        # References
        lines.append("## 6. References")
        lines.append("")
        lines.append(
            "- Makowski, D., et al. (2021). NeuroKit2: A Python toolbox for neurophysiological signal processing. *Behavior Research Methods*. https://doi.org/10.3758/s13428-020-01516-y"
        )
        lines.append(
            "- Task Force of ESC and NASPE (1996). Heart rate variability: Standards of measurement. *Circulation*, 93(5), 1043-1065."
        )
        lines.append(
            "- Quigley, K. S., et al. (2024). Publication guidelines for heart rate variability studies. *Psychophysiology*, 61(9), e14604."
        )
        lines.append("")

        lines.append("---")
        lines.append("*Report generated by RRational HRV Analysis Toolkit*")

        return "\n".join(lines)

    def generate_html(self, plots: dict[str, object] | None = None) -> str:
        """Generate a standalone HTML report with optional embedded Plotly charts.

        Args:
            plots: Optional dict mapping section names to Plotly figure objects.
                   Charts are embedded as interactive HTML (no external dependencies).
        """
        import html as html_module
        from rrational import __version__

        md_content = self.generate_markdown()

        # Convert markdown tables to HTML tables
        html_body_lines = []
        in_table = False
        table_rows = []

        for line in md_content.split("\n"):
            if line.startswith("|") and "|" in line[1:]:
                cells = [c.strip() for c in line.split("|")[1:-1]]
                if all(set(c) <= {"-", " ", ":"} for c in cells):
                    continue  # Skip separator row
                if not in_table:
                    in_table = True
                    table_rows = []
                    table_rows.append(
                        f"<tr>{''.join(f'<th>{html_module.escape(c)}</th>' for c in cells)}</tr>"
                    )
                else:
                    table_rows.append(
                        f"<tr>{''.join(f'<td>{html_module.escape(c)}</td>' for c in cells)}</tr>"
                    )
            else:
                if in_table:
                    html_body_lines.append(f"<table>{''.join(table_rows)}</table>")
                    in_table = False
                    table_rows = []

                # Convert markdown to HTML
                if line.startswith("# "):
                    html_body_lines.append(f"<h1>{html_module.escape(line[2:])}</h1>")
                elif line.startswith("## "):
                    html_body_lines.append(f"<h2>{html_module.escape(line[3:])}</h2>")
                elif line.startswith("### "):
                    html_body_lines.append(f"<h3>{html_module.escape(line[4:])}</h3>")
                elif line.startswith("#### "):
                    html_body_lines.append(f"<h4>{html_module.escape(line[5:])}</h4>")
                elif line.startswith("- "):
                    content = line[2:]
                    # Bold markers
                    while "**" in content:
                        content = content.replace("**", "<b>", 1).replace(
                            "**", "</b>", 1
                        )
                    html_body_lines.append(f"<li>{content}</li>")
                elif line.startswith("  - "):
                    html_body_lines.append(
                        f"<li style='margin-left:20px'>{html_module.escape(line[4:])}</li>"
                    )
                elif line.startswith("---"):
                    html_body_lines.append("<hr>")
                elif line.startswith("*") and line.endswith("*"):
                    html_body_lines.append(
                        f"<em>{html_module.escape(line.strip('*'))}</em>"
                    )
                elif line.strip():
                    content = line
                    while "**" in content:
                        content = content.replace("**", "<b>", 1).replace(
                            "**", "</b>", 1
                        )
                    while "`" in content:
                        content = content.replace("`", "<code>", 1).replace(
                            "`", "</code>", 1
                        )
                    html_body_lines.append(f"<p>{content}</p>")

        if in_table:
            html_body_lines.append(f"<table>{''.join(table_rows)}</table>")

        body_html = "\n".join(html_body_lines)

        # Embed Plotly charts
        plot_html = ""
        if plots:
            for section_name, fig in plots.items():
                if fig is not None:
                    try:
                        chart_html = fig.to_html(
                            full_html=False,
                            include_plotlyjs=False,
                            config={"displayModeBar": False},
                        )
                        plot_html += f"<h3>Chart: {html_module.escape(section_name)}</h3>\n{chart_html}\n"
                    except Exception:
                        pass

        # Build final HTML
        plotly_js = (
            '<script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>'
            if plots
            else ""
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HRV Analysis Report - {html_module.escape(self.participant_id)}</title>
{plotly_js}
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 900px; margin: 40px auto; padding: 0 20px; color: #333; line-height: 1.6; }}
  h1 {{ color: #2E86AB; border-bottom: 2px solid #2E86AB; padding-bottom: 8px; }}
  h2 {{ color: #444; margin-top: 30px; }}
  h3 {{ color: #555; }}
  table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
  th {{ background: #f5f5f5; font-weight: 600; }}
  tr:nth-child(even) {{ background: #fafafa; }}
  code {{ background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
  hr {{ border: none; border-top: 1px solid #ddd; margin: 30px 0; }}
  li {{ margin: 4px 0; }}
  .plotly-chart {{ margin: 20px 0; }}
  @media print {{ body {{ max-width: none; }} }}
</style>
</head>
<body>
{body_html}
{plot_html}
<footer style="margin-top:40px;padding-top:10px;border-top:1px solid #ddd;color:#888;font-size:0.85em">
Generated by RRational v{__version__} | {self.timestamp}
</footer>
</body>
</html>"""


def display_documentation_panel(
    doc: AnalysisDocumentation, plots: dict | None = None
) -> None:
    """Display the analysis documentation panel with preview and export.

    Args:
        doc: AnalysisDocumentation instance with populated data
        plots: Optional dict of section_name -> Plotly figure for HTML embedding
    """
    st.markdown("---")
    st.subheader("Analysis Documentation")

    with st.expander("Preview & Export Analysis Report", expanded=False):
        st.markdown("""
        This report documents all analysis parameters for reproducibility.
        Export as Markdown (.md) or HTML (with embedded charts) for publication.
        """)

        # Generate markdown
        md_content = doc.generate_markdown()

        # Preview tabs
        preview_tab, raw_tab = st.tabs(["Preview", "Raw Markdown"])

        with preview_tab:
            st.markdown(md_content)

        with raw_tab:
            st.code(md_content, language="markdown")

        # Download buttons
        ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="Download Markdown (.md)",
                data=md_content,
                file_name=f"hrv_report_{doc.participant_id}_{ts}.md",
                mime="text/markdown",
                key=f"download_doc_md_{doc.participant_id}",
            )
        with col2:
            html_content = doc.generate_html(plots=plots)
            st.download_button(
                label="Download HTML Report",
                data=html_content,
                file_name=f"hrv_report_{doc.participant_id}_{ts}.html",
                mime="text/html",
                key=f"download_doc_html_{doc.participant_id}",
            )


def _get_exclusion_zones(participant_id: str) -> list[dict]:
    """Get exclusion zones for a participant from session state."""
    if "participant_events" not in st.session_state:
        return []
    participant_data = st.session_state.participant_events.get(participant_id, {})
    return participant_data.get("exclusion_zones", [])


def _render_repeating_section_analysis():
    """Render the Repeating Section Analysis UI.

    Protocol-based analysis of repeating condition sections with validation.
    """
    from rrational.analysis.repeating_sections import (
        ProtocolConfig,
        DurationMismatchStrategy,
        extract_repeating_sections,
        get_sections_by_condition,
    )
    from rrational.gui.persistence import load_protocol, save_protocol

    st.markdown("""
    Analyze HRV metrics for each **repeating condition section** based on your protocol.
    This mode automatically extracts sections using measurement events and validates data quality.
    """)

    # Protocol Settings
    with st.expander("Protocol Settings", expanded=False):
        protocol_data = load_protocol()

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            expected_duration = st.number_input(
                "Expected total duration (min)",
                min_value=30.0,
                max_value=180.0,
                value=float(protocol_data.get("expected_duration_min", 90.0)),
                step=5.0,
                key="protocol_expected_duration",
                help="Total expected duration of the measurement session",
            )
            section_length = st.number_input(
                "Section length (min)",
                min_value=1.0,
                max_value=15.0,
                value=float(protocol_data.get("section_length_min", 5.0)),
                step=1.0,
                key="protocol_section_length",
                help="Duration of each condition section",
            )
            pre_pause_sections = st.number_input(
                "Pre-pause sections",
                min_value=1,
                max_value=20,
                value=int(protocol_data.get("pre_pause_sections", 9)),
                step=1,
                key="protocol_pre_pause",
                help="Number of condition sections before the pause",
            )

        with col_p2:
            post_pause_sections = st.number_input(
                "Post-pause sections",
                min_value=1,
                max_value=20,
                value=int(protocol_data.get("post_pause_sections", 9)),
                step=1,
                key="protocol_post_pause",
                help="Number of condition sections after the pause",
            )
            min_section_duration = st.number_input(
                "Minimum valid section duration (min)",
                min_value=1.0,
                max_value=10.0,
                value=float(protocol_data.get("min_section_duration_min", 4.0)),
                step=0.5,
                key="protocol_min_duration",
                help="Sections shorter than this are flagged as incomplete",
            )
            min_section_beats = st.number_input(
                "Minimum beats per section",
                min_value=50,
                max_value=500,
                value=int(protocol_data.get("min_section_beats", 100)),
                step=10,
                key="protocol_min_beats",
                help="Sections with fewer beats are flagged as incomplete",
            )

        # Duration mismatch handling
        mismatch_options = {
            "Flag only (include all, mark incomplete)": DurationMismatchStrategy.FLAG_ONLY,
            "Strict (exclude incomplete sections)": DurationMismatchStrategy.STRICT,
            "Proportional (scale sections to fit)": DurationMismatchStrategy.PROPORTIONAL,
        }
        current_strategy = protocol_data.get(
            "mismatch_strategy", DurationMismatchStrategy.FLAG_ONLY
        )
        current_label = next(
            (k for k, v in mismatch_options.items() if v == current_strategy),
            "Flag only (include all, mark incomplete)",
        )
        mismatch_strategy = st.radio(
            "Duration mismatch handling",
            options=list(mismatch_options.keys()),
            index=list(mismatch_options.keys()).index(current_label),
            key="protocol_mismatch_strategy",
            horizontal=True,
            help="How to handle recordings that don't match expected duration",
        )

        if st.button("Save Protocol Settings", key="save_protocol_btn"):
            new_protocol = {
                "expected_duration_min": expected_duration,
                "section_length_min": section_length,
                "pre_pause_sections": pre_pause_sections,
                "post_pause_sections": post_pause_sections,
                "min_section_duration_min": min_section_duration,
                "min_section_beats": min_section_beats,
                "mismatch_strategy": mismatch_options[mismatch_strategy],
            }
            save_protocol(new_protocol)
            st.success("Protocol settings saved!")

    # Build protocol config from current values
    protocol = ProtocolConfig(
        expected_duration_min=st.session_state.get("protocol_expected_duration", 90.0),
        section_length_min=st.session_state.get("protocol_section_length", 5.0),
        pre_pause_sections=st.session_state.get("protocol_pre_pause", 9),
        post_pause_sections=st.session_state.get("protocol_post_pause", 9),
        min_section_duration_min=st.session_state.get("protocol_min_duration", 4.0),
        min_section_beats=st.session_state.get("protocol_min_beats", 100),
    )

    st.markdown("---")

    # Participant/Sequence selection
    col_sel1, col_sel2 = st.columns(2)

    with col_sel1:
        participant_list = get_participant_list()
        selected_participant = st.selectbox(
            "Select Participant",
            options=participant_list,
            key="repeating_analysis_participant",
        )

    with col_sel2:
        # Get participant's event sequence
        participant_seq = st.session_state.get("participant_sequences", {}).get(
            selected_participant, ""
        ) or st.session_state.get("participant_randomizations", {}).get(
            selected_participant, ""
        )
        event_sequences = st.session_state.get("event_sequences", {})

        if participant_seq and participant_seq in event_sequences:
            seq_data = event_sequences[participant_seq]
            condition_order = seq_data.get(
                "condition_order",
                seq_data.get(
                    "music_order", ["condition_a", "condition_b", "condition_c"]
                ),
            )
            seq_label = seq_data.get("label", participant_seq)
            st.info(f"**Sequence:** {seq_label}")
            st.caption(f"Condition order: {' → '.join(condition_order)}")
        else:
            st.warning("No event sequence assigned. Using default condition order.")
            condition_order = ["condition_a", "condition_b", "condition_c"]

    # Artifact correction option
    apply_correction = st.checkbox(
        "Apply artifact correction (NeuroKit2 Kubios)",
        value=False,
        key="repeating_analysis_correction",
        help="Recommended for data with quality issues",
    )

    # Analyze button
    if st.button(
        "Analyze Repeating Sections", key="analyze_repeating_btn", type="primary"
    ):
        with st.status("Extracting repeating sections...", expanded=True) as status:
            try:
                st.write("Loading recording data...")

                # Get participant's recording data
                summary = get_summary_dict().get(selected_participant)
                if not summary:
                    st.error(f"No data found for participant {selected_participant}")
                    return

                source_app = getattr(summary, "source_app", "HRV Logger")
                is_vns = source_app == "VNS Analyse"

                # Load recording
                if is_vns:
                    vns_paths = getattr(summary, "vns_paths", None)
                    if vns_paths:
                        recording_data = cached_load_vns_recording(
                            tuple(str(p) for p in vns_paths),
                            selected_participant,
                            use_corrected=st.session_state.get(
                                "vns_use_corrected", False
                            ),
                        )
                    elif getattr(summary, "vns_path", None):
                        # Fallback: single path (old cached summary)
                        recording_data = cached_load_vns_recording(
                            (str(summary.vns_path),),
                            selected_participant,
                            use_corrected=st.session_state.get(
                                "vns_use_corrected", False
                            ),
                        )
                    else:
                        # Re-discover VNS recordings
                        from rrational.io.vns_analyse import discover_vns_recordings
                        from pathlib import Path

                        vns_bundles = discover_vns_recordings(
                            Path(st.session_state.data_dir),
                            pattern=st.session_state.id_pattern,
                        )
                        vns_bundle = next(
                            (
                                b
                                for b in vns_bundles
                                if b.participant_id == selected_participant
                            ),
                            None,
                        )
                        if not vns_bundle:
                            st.error(
                                f"No VNS recording found for {selected_participant}"
                            )
                            return
                        recording_data = cached_load_vns_recording(
                            tuple(str(p) for p in vns_bundle.file_paths),
                            selected_participant,
                            use_corrected=st.session_state.get(
                                "vns_use_corrected", False
                            ),
                        )
                else:
                    bundles = cached_discover_recordings(
                        st.session_state.data_dir, st.session_state.id_pattern
                    )
                    bundle = next(
                        (
                            b
                            for b in bundles
                            if b.participant_id == selected_participant
                        ),
                        None,
                    )
                    if not bundle:
                        st.error(
                            f"No recording bundle found for {selected_participant}"
                        )
                        return
                    recording_data = cached_load_recording(
                        tuple(str(p) for p in bundle.rr_paths),
                        tuple(str(p) for p in bundle.events_paths),
                        selected_participant,
                    )

                # Build RR intervals and events dict
                from rrational.io.hrv_logger import RRInterval

                rr_intervals = [
                    RRInterval(timestamp=ts, rr_ms=rr, elapsed_ms=elapsed)
                    for ts, rr, elapsed in recording_data["rr_intervals"]
                ]

                # Build events dictionary (canonical -> timestamp)
                events_dict = {}
                stored_events = st.session_state.participant_events.get(
                    selected_participant, {}
                )
                all_events = stored_events.get("events", []) + stored_events.get(
                    "manual", []
                )

                for evt in all_events:
                    canonical = evt.canonical if hasattr(evt, "canonical") else None
                    if canonical and evt.first_timestamp:
                        events_dict[canonical] = evt.first_timestamp

                st.write(f"Found {len(rr_intervals)} RR intervals")
                st.write(f"Events: {', '.join(events_dict.keys()) or 'None'}")

                # Extract repeating sections
                st.write("Extracting repeating sections...")
                mismatch_strategy_value = mismatch_options.get(
                    st.session_state.get(
                        "protocol_mismatch_strategy",
                        "Flag only (include all, mark incomplete)",
                    ),
                    DurationMismatchStrategy.FLAG_ONLY,
                )

                analysis = extract_repeating_sections(
                    rr_intervals=rr_intervals,
                    events=events_dict,
                    condition_order=condition_order,
                    protocol=protocol,
                    mismatch_strategy=mismatch_strategy_value,
                )

                # Show warnings
                if analysis.warnings:
                    for warning in analysis.warnings:
                        st.warning(f"{warning}")

                st.write(
                    f"Extracted {len(analysis.sections)} sections "
                    f"({analysis.valid_sections} valid, {analysis.incomplete_sections} incomplete)"
                )

                status.update(label="Section extraction complete", state="complete")

                # Display results
                st.markdown("---")
                st.subheader("Repeating Section Analysis Results")

                # Duration overview
                col_dur1, col_dur2, col_dur3 = st.columns(3)
                with col_dur1:
                    st.metric(
                        "Expected Duration", f"{protocol.expected_duration_min:.0f} min"
                    )
                with col_dur2:
                    st.metric(
                        "Actual Duration",
                        f"{analysis.actual_total_duration_s / 60:.1f} min",
                        delta=f"{-analysis.duration_mismatch_s / 60:.1f} min"
                        if analysis.duration_mismatch_s > 60
                        else None,
                        delta_color="inverse",
                    )
                with col_dur3:
                    st.metric(
                        "Valid Sections",
                        f"{analysis.valid_sections}/{len(analysis.sections)}",
                    )

                # Section details table
                st.markdown("### Section Details")

                section_data = []
                for section in analysis.sections:
                    status_icon = "[OK]" if section.is_valid else "(!)"
                    section_data.append(
                        {
                            "Status": status_icon,
                            "Section": section.label,
                            "Condition": section.condition_type,
                            "Phase": section.phase.replace("_", " ").title(),
                            "Duration (min)": f"{section.actual_duration_s / 60:.1f}",
                            "Beats": section.beat_count,
                            "Duration %": f"{section.duration_ratio * 100:.0f}%",
                            "Warnings": "; ".join(section.validation_warnings)
                            if section.validation_warnings
                            else "-",
                        }
                    )

                df_sections = pd.DataFrame(section_data)
                st.dataframe(df_sections, width="stretch", hide_index=True)

                # HRV Analysis for valid sections
                st.markdown("### HRV Metrics by Section")

                nk = get_neurokit()
                if nk is None:
                    st.error("NeuroKit2 not available for HRV computation")
                    return

                hrv_results = []
                for section in analysis.sections:
                    if not section.is_valid or section.beat_count < 50:
                        continue

                    rr_values = [rr.rr_ms for rr in section.rr_intervals]

                    # Apply artifact correction if requested
                    if apply_correction:
                        try:
                            import numpy as np

                            # Convert RR intervals to peak indices for signal_fixpeaks
                            rr_array = np.array(rr_values, dtype=float)
                            peak_indices = np.cumsum(rr_array).astype(int)
                            peak_indices = np.insert(peak_indices, 0, 0)

                            # Call signal_fixpeaks with correct format
                            info, corrected_peaks = nk.signal_fixpeaks(
                                peak_indices,
                                sampling_rate=1000,
                                iterative=True,
                                method="Kubios",
                                show=False,
                            )
                            # Use corrected RR intervals from NeuroKit2
                            rr_values = list(np.diff(corrected_peaks))
                        except Exception:
                            pass  # Use original if correction fails

                    try:
                        # Convert RR intervals to peaks for NeuroKit2
                        peaks = nk.intervals_to_peaks(rr_values, sampling_rate=1000)

                        # Compute HRV metrics using peaks
                        hrv_time = nk.hrv_time(peaks, sampling_rate=1000, show=False)
                        hrv_freq = nk.hrv_frequency(
                            peaks, sampling_rate=1000, show=False
                        )

                        hrv_results.append(
                            {
                                "Section": section.label,
                                "Condition": section.condition_type,
                                "Phase": section.phase.replace("_", " ").title(),
                                "Beats": section.beat_count,
                                "RMSSD": f"{hrv_time['HRV_RMSSD'].values[0]:.1f}",
                                "SDNN": f"{hrv_time['HRV_SDNN'].values[0]:.1f}",
                                "pNN50": f"{hrv_time['HRV_pNN50'].values[0]:.1f}",
                                "HF (ms²)": f"{hrv_freq['HRV_HF'].values[0]:.1f}",
                                "LF (ms²)": f"{hrv_freq['HRV_LF'].values[0]:.1f}",
                                "LF/HF": f"{hrv_freq['HRV_LFHF'].values[0]:.2f}",
                            }
                        )
                    except Exception as e:
                        st.warning(f"Could not compute HRV for {section.label}: {e}")

                if hrv_results:
                    df_hrv = pd.DataFrame(hrv_results)
                    st.dataframe(df_hrv, width="stretch", hide_index=True)

                    # Download button
                    csv_hrv = df_hrv.to_csv(index=False)
                    st.download_button(
                        "Download HRV Results (CSV)",
                        data=csv_hrv,
                        file_name=f"repeating_sections_hrv_{selected_participant}.csv",
                        mime="text/csv",
                    )

                    # Summary by condition type
                    st.markdown("### Summary by Condition")
                    sections_by_type = get_sections_by_condition(
                        analysis, valid_only=True
                    )

                    for cond_type, sections in sections_by_type.items():
                        with st.expander(
                            f"{cond_type} ({len(sections)} sections)", expanded=False
                        ):
                            type_results = [
                                r for r in hrv_results if r["Condition"] == cond_type
                            ]
                            if type_results:
                                df_type = pd.DataFrame(type_results)
                                st.dataframe(df_type, width="stretch", hide_index=True)

                                # Compute averages
                                try:
                                    avg_rmssd = sum(
                                        float(r["RMSSD"]) for r in type_results
                                    ) / len(type_results)
                                    avg_sdnn = sum(
                                        float(r["SDNN"]) for r in type_results
                                    ) / len(type_results)
                                    st.markdown(
                                        f"**Averages:** RMSSD={avg_rmssd:.1f} ms, SDNN={avg_sdnn:.1f} ms"
                                    )
                                except (ValueError, ZeroDivisionError):
                                    pass

                else:
                    st.warning("No valid sections for HRV analysis")

            except Exception as e:
                status.update(label="Error during analysis", state="error")
                st.error(f"Error: {e}")
                import traceback

                st.code(traceback.format_exc())


def render_analysis_tab():
    """Render the Analysis tab content.

    This tab contains:
    - Individual participant HRV analysis
    - Music section analysis (protocol-based)
    - Group-level HRV analysis
    """
    st.header("HRV Analysis")

    with st.expander("Help - HRV Analysis & Scientific Best Practices", expanded=False):
        st.markdown(ANALYSIS_HELP)

    if not NEUROKIT_AVAILABLE:
        st.error(
            "NeuroKit2 is not installed. Please install it to use HRV analysis features."
        )
        st.code("uv add neurokit2")
        return

    if not st.session_state.summaries:
        st.info("Load data from the 'Data & Groups' tab to perform analysis")
    else:
        st.markdown(
            "Select a participant, choose multiple sections, and analyze HRV metrics for each section individually and combined."
        )

        # Initialize analysis results in session state
        if "analysis_results" not in st.session_state:
            st.session_state.analysis_results = {}

        # Selection mode
        analysis_mode = st.radio(
            "Analysis Mode",
            options=[
                "Single Participant",
                "Repeating Section Analysis",
                "Group Analysis",
                "Sequence Comparison",
            ],
            horizontal=True,
        )

        if analysis_mode == "Single Participant":
            _render_single_participant_analysis()

        elif analysis_mode == "Repeating Section Analysis":
            _render_repeating_section_analysis()

        elif analysis_mode == "Group Analysis":
            _render_group_analysis()

        else:  # Sequence Comparison
            _render_sequence_comparison()


def _render_single_participant_analysis():
    """Render single participant HRV analysis."""
    from rrational.cleaning.rr import clean_rr_intervals, RRInterval
    from rrational.io.hrv_logger import HRVLoggerRecording, EventMarker

    # Participant selection
    participant_list = get_participant_list()
    selected_participant = st.selectbox(
        "Select Participant", options=participant_list, key="analysis_participant"
    )

    # Check for .rrational ready files
    ready_files = []
    use_ready_file = False
    selected_ready_file = None
    ready_file_version = "1.0"
    selected_v2_sections = []  # For v2.0 section selection

    if selected_participant:
        data_dir = st.session_state.get("data_dir")
        ready_files = find_rrational_files(selected_participant, data_dir)

    if ready_files:
        with st.expander(
            f"Ready Files ({len(ready_files)} found)", expanded=True
        ):  # Expanded by default
            st.info(
                "Ready files contain pre-inspected data with artifact detection "
                "and corrected NN intervals. Using a ready file provides the highest "
                "data quality for analysis."
            )

            data_source = st.radio(
                "Data source",
                options=["ready", "raw"],  # Ready file is default when available
                format_func=lambda x: "Use ready file (.rrational)"
                if x == "ready"
                else "Use raw data (extract from recording)",
                key="analysis_data_source",
                horizontal=True,
            )
            use_ready_file = data_source == "ready"

            if use_ready_file:
                # Format file options for display
                file_options = []
                for f in ready_files:
                    # Extract segment name from filename
                    name = f.stem  # e.g., "0123ABCD_rest_pre" or "VP01"
                    segment = name.replace(f"{selected_participant}_", "") or name
                    # Get version
                    try:
                        version = get_rrational_version(f)
                    except Exception:
                        version = "1.0"
                    file_options.append((f, segment, version, f.stat().st_mtime))

                selected_file_idx = st.selectbox(
                    "Select ready file",
                    options=range(len(file_options)),
                    format_func=lambda i: f"{file_options[i][1]} (v{file_options[i][2]}) - {file_options[i][0].name}",
                    key="analysis_ready_file_select",
                )
                selected_ready_file = file_options[selected_file_idx][0]
                ready_file_version = file_options[selected_file_idx][2]

                # Show file info based on version
                try:
                    if ready_file_version == RRATIONAL_VERSION_V2:
                        # V2.0 file - load and show sections
                        ready_data_v2 = load_rrational_v2(selected_ready_file)

                        # Count sections with NN data
                        sections_with_nn = sum(
                            1
                            for s in ready_data_v2.sections.values()
                            if len(s.nn_intervals.data) > 0
                        )
                        total_sections = len(ready_data_v2.sections)

                        if sections_with_nn == total_sections:
                            st.success(
                                f"**v2.0 Export** - {total_sections} section(s) with NN data"
                            )
                        elif sections_with_nn > 0:
                            st.success(
                                f"**v2.0 Export** - {sections_with_nn}/{total_sections} sections with NN data"
                            )
                        else:
                            st.warning(
                                f"**v2.0 Export** - {total_sections} sections validated, but no NN data saved"
                            )

                        # Try to supplement artifact data from _artifacts.yml if missing
                        # This handles old .rrational files that didn't save artifact counts
                        import os

                        participant_id = ready_data_v2.metadata.participant_id
                        artifacts_dir = os.path.dirname(str(selected_ready_file))
                        artifacts_file = os.path.join(
                            artifacts_dir, f"{participant_id}_artifacts.yml"
                        )
                        supplemental_artifacts = {}
                        if os.path.exists(artifacts_file):
                            try:
                                import yaml

                                with open(artifacts_file, "r", encoding="utf-8") as f:
                                    artifacts_data = yaml.safe_load(f) or {}
                                supplemental_artifacts = artifacts_data.get(
                                    "sections", {}
                                )
                            except Exception:
                                pass

                        # Show available sections with quality info
                        section_info = []
                        for sec_name, sec_data in ready_data_v2.sections.items():
                            nn_count = len(sec_data.nn_intervals.data)
                            quality = sec_data.quality.grade
                            artifact_count = sec_data.final_artifacts.count
                            artifact_rate = sec_data.final_artifacts.rate

                            # Supplement from _artifacts.yml if count is 0 but file has data
                            if (
                                artifact_count == 0
                                and sec_name in supplemental_artifacts
                            ):
                                sec_artifacts = supplemental_artifacts[sec_name]
                                algo_count = len(
                                    sec_artifacts.get("algorithm_artifact_indices", [])
                                )
                                manual_count = len(
                                    sec_artifacts.get("manual_artifacts", [])
                                )
                                excluded_count = len(
                                    sec_artifacts.get("excluded_artifact_indices", [])
                                )
                                artifact_count = (
                                    algo_count + manual_count - excluded_count
                                )
                                if nn_count > 0:
                                    artifact_rate = artifact_count / nn_count

                            # Determine data source status
                            data_status = "NN" if nn_count > 0 else "(needs raw)"

                            section_info.append(
                                {
                                    "Section": sec_name,
                                    "Data": data_status,
                                    "Beats": nn_count if nn_count > 0 else "-",
                                    "Artifacts": artifact_count
                                    if nn_count > 0
                                    else "-",
                                    "Artifact %": f"{artifact_rate * 100:.2f}%"
                                    if nn_count > 0
                                    else "-",
                                    "Quality": quality.capitalize()
                                    if nn_count > 0
                                    else "-",
                                }
                            )

                        if section_info:
                            st.dataframe(
                                pd.DataFrame(section_info),
                                use_container_width=True,
                                hide_index=True,
                            )

                        # Let user select which sections to analyze
                        available_sections = list(ready_data_v2.sections.keys())
                        selected_v2_sections = st.multiselect(
                            "Select section(s) to analyze",
                            options=available_sections,
                            default=available_sections,  # Select all sections by default
                            key="analysis_v2_sections",
                        )

                        # Check which sections have no NN intervals
                        sections_without_nn = [
                            s
                            for s in available_sections
                            if len(ready_data_v2.sections[s].nn_intervals.data) == 0
                        ]

                        # Option to use raw data fallback for sections without NN
                        allow_raw_fallback_v2 = False
                        if sections_without_nn:
                            st.info(
                                f"ℹ️ Sections without NN intervals: {', '.join(sections_without_nn)}"
                            )
                            allow_raw_fallback_v2 = st.checkbox(
                                "Use raw RR data for sections without NN intervals",
                                value=True,
                                key="allow_raw_fallback_v2",
                                help="When enabled, sections without corrected NN intervals will be analyzed using raw RR data from the recording",
                            )

                        # Store the loaded data for later use
                        st.session_state._analysis_ready_v2_data = ready_data_v2
                        st.session_state._analysis_allow_raw_fallback = (
                            allow_raw_fallback_v2
                        )

                        if ready_data_v2.audit_trail:
                            with st.expander("Audit Trail"):
                                for entry in ready_data_v2.audit_trail[
                                    -5:
                                ]:  # Last 5 entries
                                    st.write(f"**{entry.action}**: {entry.details}")

                        # Overlapping window options for v2.0 ready files
                        with st.expander("Window Analysis Settings", expanded=True):
                            # Analysis mode selection
                            analysis_mode = st.radio(
                                "Analysis mode",
                                options=["aggregated", "per_segment"],
                                format_func=lambda x: {
                                    "aggregated": "Aggregated (mean across windows)",
                                    "per_segment": "Per-segment (individual results)",
                                }[x],
                                horizontal=True,
                                key="analysis_mode_v2",
                                help="Aggregated: average across all windows. Per-segment: individual HRV results per segment.",
                            )

                            use_overlapping_windows = True  # always use windowing

                            if analysis_mode == "per_segment":
                                st.caption(
                                    "Each segment from artifact detection is analyzed individually."
                                )
                                # Use segments from artifact detection
                                window_mode = "time"
                                window_duration_min = None
                                overlap_percent = None
                                window_beats = None
                                step_beats = None
                            else:
                                st.caption(
                                    "**Recommended:** 5-minute time-based windows with 50% overlap"
                                )
                                col1, col2 = st.columns(2)
                                with col1:
                                    window_duration_min = st.slider(
                                        "Window duration (minutes)",
                                        1,
                                        10,
                                        5,
                                        key="overlap_window_duration_v2",
                                    )
                                with col2:
                                    overlap_percent = st.slider(
                                        "Overlap (%)",
                                        0,
                                        75,
                                        50,
                                        step=25,
                                        key="overlap_percent_v2",
                                    )
                                step_size_min = window_duration_min * (
                                    1 - overlap_percent / 100
                                )
                                st.caption(f"Step size: {step_size_min:.1f} minutes")
                                window_mode = "time"
                                window_beats = None
                                step_beats = None
                    else:
                        # V1.0 file - original behavior
                        ready_data = load_rrational(selected_ready_file)
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Beats", ready_data.n_beats)
                        with col2:
                            artifact_rate = ready_data.quality.artifact_rate_final * 100
                            st.metric("Artifact Rate", f"{artifact_rate:.1f}%")
                        with col3:
                            st.metric(
                                "Quality", ready_data.quality.quality_grade.capitalize()
                            )

                        if ready_data.processing_steps:
                            with st.expander("Audit Trail"):
                                for step in ready_data.processing_steps:
                                    st.write(f"**{step.action}**: {step.details}")

                        # Overlapping window options for v1.0 ready files
                        with st.expander("Window Analysis Settings", expanded=True):
                            use_overlapping_windows = True

                            st.caption(
                                "**Recommended:** 5-minute time-based windows with 50% overlap"
                            )
                            col1, col2 = st.columns(2)
                            with col1:
                                window_duration_min = st.slider(
                                    "Window duration (minutes)",
                                    1,
                                    10,
                                    5,
                                    key="overlap_window_duration_v1",
                                )
                            with col2:
                                overlap_percent = st.slider(
                                    "Overlap (%)",
                                    0,
                                    75,
                                    50,
                                    step=25,
                                    key="overlap_percent_v1",
                                )
                            step_size_min = window_duration_min * (
                                1 - overlap_percent / 100
                            )
                            st.caption(f"Step size: {step_size_min:.1f} minutes")
                            window_mode = "time"
                            window_beats = None
                            step_beats = None
                except Exception as e:
                    st.error(f"Error loading ready file: {e}")
                    use_ready_file = False

    # Section selection (only when NOT using ready file)
    selected_sections = []
    apply_artifact_correction = False

    if not use_ready_file:
        # Show warning about using raw data
        if ready_files:
            st.warning(
                "You have ready files available but are using raw data. "
                "For best results, use the ready file with pre-inspected artifact correction. "
                "Raw data analysis may include artifacts that affect HRV metrics."
            )
        else:
            st.info(
                "No ready file found. To create one, go to the Participants tab and "
                "use the 'Export for Analysis' button after reviewing artifacts."
            )

        available_sections = list(st.session_state.sections.keys())
        if not available_sections:
            st.warning(
                "No sections defined. Please define sections in the Sections tab first."
            )
            return

        # Default to all validated sections for the selected participant
        default_sections = available_sections  # fallback: all sections
        _analysis_pid = st.session_state.get("analysis_participant_single")
        if _analysis_pid:
            from rrational.gui.shared import (
                get_validated_sections_for_participant as _get_vals,
            )

            _val_results = _get_vals(
                participant_id=_analysis_pid,
                sections_config=st.session_state.sections,
                normalizer=st.session_state.get("normalizer"),
            )
            _valid = [s for s, r in _val_results.items() if r.is_valid]
            if _valid:
                default_sections = _valid

        selected_sections = st.multiselect(
            "Select Sections to Analyze",
            options=available_sections,
            default=default_sections,
            key="analysis_sections_single",
        )

        # Artifact correction options
        with st.expander("Artifact Correction (signal_fixpeaks)", expanded=False):
            st.markdown("""
            Uses NeuroKit2's `signal_fixpeaks()` with the **Kubios algorithm** to detect and correct:
            - **Ectopic beats** (premature/delayed beats)
            - **Missed beats** (undetected R-peaks)
            - **Extra beats** (false positive detections)
            - **Long/short intervals** (physiologically implausible)
            """)
            apply_artifact_correction = st.checkbox(
                "Apply artifact correction before HRV analysis",
                value=False,
                key="apply_artifact_correction",
                help="Recommended for data with known quality issues",
            )

    # Overlapping window analysis options (only for raw data - ready files have their own controls)
    if not use_ready_file:
        with st.expander("Window Analysis Settings", expanded=True):
            use_overlapping_windows = True

            analysis_mode_raw = st.radio(
                "Analysis mode",
                options=["aggregated", "per_segment"],
                format_func=lambda x: {
                    "aggregated": "Aggregated (mean across windows)",
                    "per_segment": "Per-segment (individual results)",
                }[x],
                horizontal=True,
                key="analysis_mode_raw",
                help="Aggregated: average across all windows. Per-segment: individual HRV results per segment.",
            )

            if analysis_mode_raw == "per_segment":
                st.caption(
                    "Each segment from artifact detection is analyzed individually."
                )
                window_duration_min = None
                overlap_percent = None
            else:
                st.caption(
                    "**Recommended:** 5-minute time-based windows with 50% overlap"
                )
                col1, col2 = st.columns(2)
                with col1:
                    window_duration_min = st.slider(
                        "Window duration (minutes)",
                        min_value=1,
                        max_value=10,
                        value=5,
                        step=1,
                        key="overlap_window_duration",
                        help="Duration of each analysis window",
                    )
                with col2:
                    overlap_percent = st.slider(
                        "Overlap (%)",
                        min_value=0,
                        max_value=75,
                        value=50,
                        step=25,
                        key="overlap_percent",
                        help="Percentage overlap between consecutive windows",
                    )
                step_size_min = window_duration_min * (1 - overlap_percent / 100)
                st.caption(
                    f"Step size: {step_size_min:.1f} minutes between window starts"
                )

            window_mode = "time"
            window_beats = None
            step_beats = None

    if st.button("Analyze HRV", key="analyze_single_btn", type="primary"):
        # Validate inputs
        if use_ready_file:
            if not selected_ready_file:
                st.error("Please select a ready file")
                return
            # For v2.0 files, need section selection
            if ready_file_version == RRATIONAL_VERSION_V2 and not selected_v2_sections:
                st.error("Please select at least one section from the v2.0 file")
                return
        else:
            if not selected_sections:
                st.error("Please select at least one section")
                return

        # ===== READY FILE ANALYSIS PATH =====
        if use_ready_file and selected_ready_file:
            # Check file version and use appropriate loading path
            if ready_file_version == RRATIONAL_VERSION_V2:
                # ===== V2.0 ANALYSIS PATH =====
                status_msg = "Analyzing HRV from v2.0 export..."
                with st.status(status_msg, expanded=True) as status:
                    try:
                        st.write(f"Loading v2.0 export: {selected_ready_file.name}")
                        progress = st.progress(0)

                        # Get cached v2.0 data or reload
                        ready_data_v2 = st.session_state.get("_analysis_ready_v2_data")
                        if ready_data_v2 is None:
                            ready_data_v2 = load_rrational_v2(selected_ready_file)
                        progress.progress(10)

                        # Load supplemental artifact data from _artifacts.yml if available
                        import os

                        participant_id = ready_data_v2.metadata.participant_id
                        artifacts_dir = os.path.dirname(str(selected_ready_file))
                        artifacts_file = os.path.join(
                            artifacts_dir, f"{participant_id}_artifacts.yml"
                        )
                        supplemental_artifacts = {}
                        if os.path.exists(artifacts_file):
                            try:
                                import yaml

                                with open(artifacts_file, "r", encoding="utf-8") as f:
                                    artifacts_data = yaml.safe_load(f) or {}
                                supplemental_artifacts = artifacts_data.get(
                                    "sections", {}
                                )
                            except Exception:
                                pass

                        section_results = {}
                        total_sections = len(selected_v2_sections)
                        nk = get_neurokit()

                        # Get raw data fallback setting (read directly from checkbox key)
                        allow_raw_fallback_v2 = st.session_state.get(
                            "allow_raw_fallback_v2", False
                        )

                        for idx, sec_name in enumerate(selected_v2_sections):
                            st.write(f"Analyzing section: {sec_name}")
                            sec_data = ready_data_v2.sections[sec_name]

                            # Extract NN intervals from v2.0 format
                            # Data format: [[timestamp_ms, nn_ms, was_corrected], ...]
                            nn_intervals_ms = [
                                item[1] for item in sec_data.nn_intervals.data
                            ]
                            data_source_label = "NN"  # Track whether using NN or raw

                            if not nn_intervals_ms:
                                # Try raw data fallback if enabled
                                # Uses same approach as "Use raw data" mode: load recording, extract section
                                if allow_raw_fallback_v2:
                                    try:
                                        from rrational.io.hrv_logger import (
                                            HRVLoggerRecording,
                                            RRInterval,
                                            EventMarker,
                                        )
                                        from rrational.gui.persistence import (
                                            load_participant_events,
                                        )
                                        from rrational.cleaning.rr import (
                                            clean_rr_intervals,
                                        )

                                        # Get participant ID from metadata
                                        pid = ready_data_v2.metadata.participant_id

                                        # Get summary to determine source type
                                        summary = get_summary_dict().get(pid)
                                        source_app = (
                                            getattr(summary, "source_app", "HRV Logger")
                                            if summary
                                            else "HRV Logger"
                                        )
                                        is_vns = source_app == "VNS Analyse"

                                        recording_data = None
                                        if is_vns:
                                            # Load VNS Analyse recording
                                            vns_paths = getattr(
                                                summary, "vns_paths", None
                                            )
                                            if vns_paths:
                                                recording_data = cached_load_vns_recording(
                                                    tuple(str(p) for p in vns_paths),
                                                    pid,
                                                    use_corrected=st.session_state.get(
                                                        "vns_use_corrected", False
                                                    ),
                                                )
                                            elif getattr(summary, "vns_path", None):
                                                recording_data = cached_load_vns_recording(
                                                    (str(summary.vns_path),),
                                                    pid,
                                                    use_corrected=st.session_state.get(
                                                        "vns_use_corrected", False
                                                    ),
                                                )
                                            else:
                                                # Re-discover VNS recordings
                                                from rrational.io.vns_analyse import (
                                                    discover_vns_recordings,
                                                )

                                                vns_bundles = discover_vns_recordings(
                                                    Path(st.session_state.data_dir),
                                                    pattern=st.session_state.id_pattern,
                                                )
                                                vns_bundle = next(
                                                    (
                                                        b
                                                        for b in vns_bundles
                                                        if b.participant_id == pid
                                                    ),
                                                    None,
                                                )
                                                if vns_bundle:
                                                    recording_data = cached_load_vns_recording(
                                                        tuple(
                                                            str(p)
                                                            for p in vns_bundle.file_paths
                                                        ),
                                                        pid,
                                                        use_corrected=st.session_state.get(
                                                            "vns_use_corrected", False
                                                        ),
                                                    )
                                        else:
                                            # Load HRV Logger recording
                                            bundles = cached_discover_recordings(
                                                st.session_state.data_dir,
                                                st.session_state.id_pattern,
                                            )
                                            bundle = next(
                                                (
                                                    b
                                                    for b in bundles
                                                    if b.participant_id == pid
                                                ),
                                                None,
                                            )
                                            if bundle:
                                                recording_data = cached_load_recording(
                                                    tuple(
                                                        str(p) for p in bundle.rr_paths
                                                    ),
                                                    tuple(
                                                        str(p)
                                                        for p in bundle.events_paths
                                                    ),
                                                    pid,
                                                )

                                        if recording_data:
                                            # Reconstruct recording object (same as "Use raw data" mode)
                                            rr_intervals = [
                                                RRInterval(
                                                    timestamp=ts,
                                                    rr_ms=rr,
                                                    elapsed_ms=elapsed,
                                                )
                                                for ts, rr, elapsed in recording_data[
                                                    "rr_intervals"
                                                ]
                                            ]

                                            # Load saved events for this participant
                                            saved_events = load_participant_events(
                                                pid, st.session_state.data_dir
                                            )
                                            all_stored = []
                                            if saved_events:
                                                all_stored = saved_events.get(
                                                    "events", []
                                                ) + saved_events.get("manual", [])

                                            # Convert to EventMarker objects
                                            events = []
                                            for evt in all_stored:
                                                ts = (
                                                    evt.get("first_timestamp")
                                                    if isinstance(evt, dict)
                                                    else getattr(
                                                        evt, "first_timestamp", None
                                                    )
                                                )
                                                label = (
                                                    (
                                                        evt.get("canonical")
                                                        or evt.get(
                                                            "raw_label", "unknown"
                                                        )
                                                    )
                                                    if isinstance(evt, dict)
                                                    else (
                                                        getattr(evt, "canonical", None)
                                                        or getattr(
                                                            evt, "raw_label", "unknown"
                                                        )
                                                    )
                                                )
                                                if ts:
                                                    if isinstance(ts, str):
                                                        from datetime import datetime

                                                        ts = datetime.fromisoformat(ts)
                                                    events.append(
                                                        EventMarker(
                                                            label=label,
                                                            timestamp=ts,
                                                            offset_s=None,
                                                        )
                                                    )

                                            recording = HRVLoggerRecording(
                                                participant_id=pid,
                                                rr_intervals=rr_intervals,
                                                events=events,
                                            )

                                            # Build section definition from .rrational data
                                            # Note: end_event is singular in v2 format, convert to end_events list
                                            section_def = {
                                                "name": sec_name,
                                                "start_event": sec_data.definition.start_event,
                                                "end_events": [
                                                    sec_data.definition.end_event
                                                ],
                                                "label": sec_data.definition.label,
                                            }

                                            # Extract section using same logic as "Use raw data" mode
                                            section_rr = extract_section_rr_intervals(
                                                recording,
                                                section_def,
                                                st.session_state.normalizer,
                                                saved_events=all_stored,
                                                participant_id=pid,
                                            )

                                            if section_rr:
                                                # Clean RR intervals
                                                cleaned_rr, stats = clean_rr_intervals(
                                                    section_rr,
                                                    st.session_state.cleaning_config,
                                                )
                                                if cleaned_rr:
                                                    nn_intervals_ms = [
                                                        rr.rr_ms for rr in cleaned_rr
                                                    ]
                                                    data_source_label = "Raw"
                                                    st.info(
                                                        f"Section {sec_name}: Using raw RR data ({len(nn_intervals_ms)} intervals)"
                                                    )
                                                else:
                                                    st.warning(
                                                        f"Section {sec_name}: No valid RR intervals after cleaning"
                                                    )
                                            else:
                                                st.warning(
                                                    f"Section {sec_name}: Could not extract section from raw data (check event markers)"
                                                )
                                        else:
                                            st.warning(
                                                f"Section {sec_name}: Could not load raw recording data"
                                            )
                                    except Exception as e:
                                        st.warning(
                                            f"Section {sec_name}: Failed to load raw data fallback: {e}"
                                        )

                                if not nn_intervals_ms:
                                    st.warning(
                                        f"Section {sec_name} has no NN intervals and raw data fallback failed, skipping..."
                                    )
                                    continue

                            # Quality check
                            quality_grade = sec_data.quality.grade
                            meets_time = sec_data.quality.meets_time_domain_min
                            meets_freq = sec_data.quality.meets_freq_domain_min
                            # Update quality thresholds for raw data
                            if data_source_label == "Raw":
                                meets_time = len(nn_intervals_ms) >= 100
                                meets_freq = (
                                    len(nn_intervals_ms) >= 300
                                    and sum(nn_intervals_ms) / 1000 >= 120
                                )

                            if quality_grade == "poor":
                                st.warning(
                                    f"Section {sec_name} has poor quality - results may be unreliable"
                                )

                            # Get artifact info - supplement from _artifacts.yml if count is 0
                            artifact_count = sec_data.final_artifacts.count
                            artifact_rate = sec_data.final_artifacts.rate
                            if (
                                artifact_count == 0
                                and sec_name in supplemental_artifacts
                            ):
                                sec_artifacts = supplemental_artifacts[sec_name]
                                algo_count = len(
                                    sec_artifacts.get("algorithm_artifact_indices", [])
                                )
                                manual_count = len(
                                    sec_artifacts.get("manual_artifacts", [])
                                )
                                excluded_count = len(
                                    sec_artifacts.get("excluded_artifact_indices", [])
                                )
                                artifact_count = (
                                    algo_count + manual_count - excluded_count
                                )
                                if len(nn_intervals_ms) > 0:
                                    artifact_rate = artifact_count / len(
                                        nn_intervals_ms
                                    )

                            section_artifact_info = {
                                "total_artifacts": artifact_count,
                                "artifact_rate": artifact_rate,
                                "method": sec_data.artifact_detection.method
                                if sec_data.artifact_detection
                                else "manual",
                            }

                            # Calculate HRV metrics - with optional overlapping windows
                            st.write(
                                f"  Computing HRV for {len(nn_intervals_ms)} NN intervals..."
                            )

                            if use_overlapping_windows:
                                import numpy as np
                                from rrational.gui.segmentation import (
                                    generate_segments as gen_segs,
                                )

                                analysis_mode_v2 = st.session_state.get(
                                    "analysis_mode_v2", "aggregated"
                                )

                                if analysis_mode_v2 == "per_segment":
                                    # Use segments from artifact detection
                                    artifact_data = st.session_state.get(
                                        f"artifacts_{selected_participant}", {}
                                    )
                                    det_segments = artifact_data.get("segments", [])
                                    seg_inclusion = st.session_state.get(
                                        f"segment_inclusion_{selected_participant}", {}
                                    )

                                    if det_segments:
                                        # Filter to included segments
                                        nn_arr = np.asarray(
                                            nn_intervals_ms, dtype=np.float64
                                        )
                                        windows = []
                                        for seg in det_segments:
                                            if seg_inclusion.get(seg.idx, seg.included):
                                                sliced = nn_arr[
                                                    seg.beat_start : seg.beat_end
                                                ].tolist()
                                                if len(sliced) >= 30:
                                                    windows.append(
                                                        (seg.idx, seg.start_ms, sliced)
                                                    )
                                        window_info_str = (
                                            f"per-segment ({len(windows)} included)"
                                        )
                                    else:
                                        # No segments from artifact detection, fall back to time-based
                                        w_s = 300.0
                                        segs = gen_segs(
                                            np.asarray(nn_intervals_ms),
                                            window_s=w_s,
                                            overlap_pct=0.0,
                                        )
                                        windows = [
                                            (
                                                s.idx,
                                                s.start_ms,
                                                list(
                                                    np.asarray(nn_intervals_ms)[
                                                        s.beat_start : s.beat_end
                                                    ]
                                                ),
                                            )
                                            for s in segs
                                            if s.n_beats >= 30
                                        ]
                                        window_info_str = "5min segments, no overlap"

                                elif (
                                    window_mode == "beats" and window_beats is not None
                                ):
                                    windows = generate_overlapping_windows_beats(
                                        nn_intervals_ms, window_beats, step_beats
                                    )
                                    window_info_str = (
                                        f"{window_beats} beats, {step_beats}-beat step"
                                    )
                                else:
                                    # Time-based windows (default)
                                    w_dur_min = (
                                        window_duration_min
                                        if window_duration_min
                                        else 5
                                    )
                                    o_pct = (
                                        overlap_percent
                                        if overlap_percent is not None
                                        else 50
                                    )
                                    nn_arr = np.asarray(
                                        nn_intervals_ms, dtype=np.float64
                                    )
                                    segs = gen_segs(
                                        nn_arr,
                                        window_s=w_dur_min * 60.0,
                                        overlap_pct=float(o_pct),
                                    )
                                    windows = [
                                        (
                                            s.idx,
                                            s.start_ms,
                                            nn_arr[s.beat_start : s.beat_end].tolist(),
                                        )
                                        for s in segs
                                        if s.n_beats >= 30
                                    ]
                                    window_info_str = (
                                        f"{w_dur_min}min, {o_pct}% overlap"
                                    )

                                if len(windows) >= 1:
                                    st.write(
                                        f"    Analyzing {len(windows)} overlapping windows ({window_info_str})..."
                                    )

                                    window_hrv_results = []
                                    window_details = []

                                    for win_idx, win_start, win_rr in windows:
                                        if len(win_rr) < 30:
                                            continue

                                        try:
                                            win_peaks = nk.intervals_to_peaks(
                                                win_rr, sampling_rate=1000
                                            )
                                            win_hrv_time = nk.hrv_time(
                                                win_peaks,
                                                sampling_rate=1000,
                                                show=False,
                                            )
                                            if meets_freq:
                                                win_hrv_freq = nk.hrv_frequency(
                                                    win_peaks,
                                                    sampling_rate=1000,
                                                    show=False,
                                                )
                                                win_hrv = pd.concat(
                                                    [win_hrv_time, win_hrv_freq], axis=1
                                                )
                                            else:
                                                win_hrv = win_hrv_time

                                            window_hrv_results.append(win_hrv)
                                            detail = {
                                                "window_idx": win_idx,
                                                "n_beats": len(win_rr),
                                                "duration_s": sum(win_rr) / 1000,
                                                "hrv_results": win_hrv,
                                            }
                                            if window_mode == "beats":
                                                detail["start_beat"] = win_start
                                            else:
                                                detail["start_ms"] = win_start
                                            window_details.append(detail)
                                        except Exception as e:
                                            st.write(
                                                f"      Window {win_idx + 1} failed: {e}"
                                            )
                                            continue

                                    if window_hrv_results:
                                        hrv_results, hrv_std = aggregate_hrv_results(
                                            window_hrv_results
                                        )
                                        st.write(
                                            f"    Aggregated results from {len(window_hrv_results)} valid windows"
                                        )

                                        section_results[sec_name] = {
                                            "hrv_results": hrv_results,
                                            "hrv_std": hrv_std,
                                            "rr_intervals": nn_intervals_ms,
                                            "n_beats": len(nn_intervals_ms),
                                            "label": sec_data.definition.label
                                            or sec_name,
                                            "artifact_info": section_artifact_info,
                                            "ready_file": str(selected_ready_file),
                                            "quality_grade": quality_grade,
                                            "data_source": data_source_label,  # "NN" or "Raw"
                                            "quality": {
                                                "meets_time_domain": meets_time,
                                                "meets_freq_domain": meets_freq,
                                                "usable_beats": sec_data.quality.usable_beats
                                                if data_source_label == "NN"
                                                else len(nn_intervals_ms),
                                                "usable_duration_s": sec_data.quality.usable_duration_s
                                                if data_source_label == "NN"
                                                else sum(nn_intervals_ms) / 1000,
                                            },
                                            "overlapping_analysis": True,
                                            "n_windows": len(window_hrv_results),
                                            "window_mode": window_mode,
                                            "window_duration_min": window_duration_min,
                                            "overlap_percent": overlap_percent,
                                            "window_beats": window_beats,
                                            "step_beats": step_beats,
                                            "window_details": window_details,
                                            "version": "2.0",
                                        }
                                        # Update progress and continue to next section
                                        progress.progress(
                                            10 + int(80 * (idx + 1) / total_sections)
                                        )
                                        continue
                                    else:
                                        st.warning(
                                            f"    No valid windows for section '{sec_name}', falling back to single analysis"
                                        )
                                else:
                                    st.warning(
                                        "    Section too short for overlapping windows, using single analysis"
                                    )

                            # Standard single analysis (fallback or when overlapping disabled)
                            peaks = nk.intervals_to_peaks(
                                nn_intervals_ms, sampling_rate=1000
                            )
                            hrv_time = nk.hrv_time(
                                peaks, sampling_rate=1000, show=False
                            )

                            # Only compute frequency metrics if enough data
                            if meets_freq:
                                hrv_freq = nk.hrv_frequency(
                                    peaks, sampling_rate=1000, show=False
                                )
                                hrv_results = pd.concat([hrv_time, hrv_freq], axis=1)
                            else:
                                st.info(
                                    f"  Section {sec_name}: frequency domain skipped (insufficient data)"
                                )
                                hrv_results = hrv_time

                            # Store results
                            section_results[sec_name] = {
                                "hrv_results": hrv_results,
                                "rr_intervals": nn_intervals_ms,
                                "n_beats": len(nn_intervals_ms),
                                "label": sec_data.definition.label or sec_name,
                                "artifact_info": section_artifact_info,
                                "ready_file": str(selected_ready_file),
                                "quality_grade": quality_grade,
                                "data_source": data_source_label,  # "NN" or "Raw"
                                "quality": {
                                    "meets_time_domain": meets_time,
                                    "meets_freq_domain": meets_freq,
                                    "usable_beats": sec_data.quality.usable_beats
                                    if data_source_label == "NN"
                                    else len(nn_intervals_ms),
                                    "usable_duration_s": sec_data.quality.usable_duration_s
                                    if data_source_label == "NN"
                                    else sum(nn_intervals_ms) / 1000,
                                },
                                "analysis_segments": [
                                    {
                                        "id": seg.segment_id,
                                        "type": seg.type,
                                        "nn_count": seg.nn_count,
                                        "duration_s": seg.duration_s,
                                    }
                                    for seg in sec_data.analysis_segments
                                ],
                                "version": "2.0",
                            }

                            # Update progress
                            progress.progress(10 + int(80 * (idx + 1) / total_sections))

                        if not section_results:
                            st.error("No sections could be analyzed")
                            status.update(label="Analysis failed", state="error")
                            return

                        progress.progress(100)
                        st.session_state.analysis_results[selected_participant] = (
                            section_results
                        )
                        status.update(
                            label=f"Analysis complete! ({len(section_results)} sections)",
                            state="complete",
                        )
                        show_toast(
                            f"v2.0 analysis complete: {len(section_results)} section(s)",
                            icon="success",
                        )

                    except Exception as e:
                        status.update(label="Error during v2.0 analysis", state="error")
                        st.error(f"Error analyzing v2.0 file: {e}")
                        import traceback

                        st.code(traceback.format_exc())

            else:
                # ===== V1.0 ANALYSIS PATH (original behavior) =====
                status_msg = "Analyzing HRV from ready file..."
                with st.status(status_msg, expanded=True) as status:
                    try:
                        st.write(f"Loading ready file: {selected_ready_file.name}")
                        progress = st.progress(0)

                        # Load ready file
                        ready_data = load_rrational(selected_ready_file)
                        progress.progress(20)

                        # Get clean RR intervals (exclude artifact indices)
                        artifact_indices = set(ready_data.final_artifact_indices)
                        clean_rr_ms = []
                        for i, rr in enumerate(ready_data.rr_intervals):
                            if i not in artifact_indices:
                                clean_rr_ms.append(rr.rr_ms)

                        if not clean_rr_ms:
                            st.error("No clean RR intervals after removing artifacts")
                            status.update(
                                label="Analysis failed - no clean data", state="error"
                            )
                            return

                        st.write(
                            f"Using {len(clean_rr_ms)} clean beats ({len(artifact_indices)} artifacts removed)"
                        )
                        progress.progress(40)

                        # Get segment name
                        segment_name = "ready_file"
                        if ready_data.segment:
                            if ready_data.segment.section_name:
                                segment_name = ready_data.segment.section_name
                            elif ready_data.segment.time_range:
                                segment_name = ready_data.segment.time_range.get(
                                    "label", "custom_range"
                                )

                        # Calculate HRV metrics - with optional overlapping windows
                        st.write("Computing HRV metrics...")
                        nk = get_neurokit()

                        if use_overlapping_windows:
                            import numpy as np
                            from rrational.gui.segmentation import (
                                generate_segments as gen_segs,
                            )

                            # Time-based windows (default)
                            w_dur_min = (
                                window_duration_min if window_duration_min else 5
                            )
                            o_pct = (
                                overlap_percent if overlap_percent is not None else 50
                            )
                            nn_arr = np.asarray(clean_rr_ms, dtype=np.float64)
                            segs = gen_segs(
                                nn_arr,
                                window_s=w_dur_min * 60.0,
                                overlap_pct=float(o_pct),
                            )
                            windows = [
                                (
                                    s.idx,
                                    s.start_ms,
                                    nn_arr[s.beat_start : s.beat_end].tolist(),
                                )
                                for s in segs
                                if s.n_beats >= 30
                            ]
                            window_info_str = f"{w_dur_min}min, {o_pct}% overlap"

                            if len(windows) >= 1:
                                st.write(
                                    f"  Analyzing {len(windows)} overlapping windows ({window_info_str})..."
                                )

                                window_hrv_results = []
                                window_details = []

                                for win_idx, win_start, win_rr in windows:
                                    if len(win_rr) < 30:
                                        continue

                                    try:
                                        win_peaks = nk.intervals_to_peaks(
                                            win_rr, sampling_rate=1000
                                        )
                                        win_hrv_time = nk.hrv_time(
                                            win_peaks, sampling_rate=1000, show=False
                                        )
                                        win_hrv_freq = nk.hrv_frequency(
                                            win_peaks, sampling_rate=1000, show=False
                                        )
                                        win_hrv = pd.concat(
                                            [win_hrv_time, win_hrv_freq], axis=1
                                        )

                                        window_hrv_results.append(win_hrv)
                                        detail = {
                                            "window_idx": win_idx,
                                            "n_beats": len(win_rr),
                                            "duration_s": sum(win_rr) / 1000,
                                            "hrv_results": win_hrv,
                                        }
                                        detail["start_ms"] = win_start
                                        window_details.append(detail)
                                    except Exception as e:
                                        st.write(
                                            f"    Window {win_idx + 1} failed: {e}"
                                        )
                                        continue

                                if window_hrv_results:
                                    hrv_results, hrv_std = aggregate_hrv_results(
                                        window_hrv_results
                                    )
                                    st.write(
                                        f"  Aggregated results from {len(window_hrv_results)} valid windows"
                                    )
                                    progress.progress(80)

                                    section_results = {
                                        segment_name: {
                                            "hrv_results": hrv_results,
                                            "hrv_std": hrv_std,
                                            "rr_intervals": clean_rr_ms,
                                            "n_beats": len(clean_rr_ms),
                                            "label": segment_name,
                                            "artifact_info": {
                                                "total_artifacts": len(
                                                    artifact_indices
                                                ),
                                                "artifact_rate": ready_data.quality.artifact_rate_final,
                                                "method": ready_data.artifact_detection.method
                                                if ready_data.artifact_detection
                                                else "manual",
                                            },
                                            "ready_file": str(selected_ready_file),
                                            "quality_grade": ready_data.quality.quality_grade,
                                            "audit_trail": ready_data.processing_steps,
                                            "overlapping_analysis": True,
                                            "n_windows": len(window_hrv_results),
                                            "window_mode": "time",
                                            "window_duration_min": window_duration_min,
                                            "overlap_percent": overlap_percent,
                                            "window_beats": window_beats,
                                            "step_beats": step_beats,
                                            "window_details": window_details,
                                            "version": "1.0",
                                        }
                                    }

                                    progress.progress(100)
                                    st.session_state.analysis_results[
                                        selected_participant
                                    ] = section_results
                                    status.update(
                                        label="Analysis complete from ready file!",
                                        state="complete",
                                    )
                                    show_toast(
                                        "Ready file analysis complete (overlapping windows)",
                                        icon="success",
                                    )
                                    return  # Exit early, skip standard analysis
                                else:
                                    st.warning(
                                        "  No valid windows, falling back to single analysis"
                                    )
                            else:
                                st.warning(
                                    "  Data too short for overlapping windows, using single analysis"
                                )

                        # Standard single analysis (fallback or when overlapping disabled)
                        peaks = nk.intervals_to_peaks(clean_rr_ms, sampling_rate=1000)
                        hrv_time = nk.hrv_time(peaks, sampling_rate=1000, show=False)
                        hrv_freq = nk.hrv_frequency(
                            peaks, sampling_rate=1000, show=False
                        )
                        hrv_results = pd.concat([hrv_time, hrv_freq], axis=1)
                        progress.progress(80)

                        # Store results
                        section_results = {
                            segment_name: {
                                "hrv_results": hrv_results,
                                "rr_intervals": clean_rr_ms,
                                "n_beats": len(clean_rr_ms),
                                "label": segment_name,
                                "artifact_info": {
                                    "total_artifacts": len(artifact_indices),
                                    "artifact_rate": ready_data.quality.artifact_rate_final,
                                    "method": ready_data.artifact_detection.method
                                    if ready_data.artifact_detection
                                    else "manual",
                                },
                                "ready_file": str(selected_ready_file),
                                "quality_grade": ready_data.quality.quality_grade,
                                "audit_trail": ready_data.processing_steps,
                                "version": "1.0",
                            }
                        }

                        progress.progress(100)
                        st.session_state.analysis_results[selected_participant] = (
                            section_results
                        )
                        status.update(
                            label="Analysis complete from ready file!", state="complete"
                        )
                        show_toast("Ready file analysis complete", icon="success")

                    except Exception as e:
                        status.update(label="Error during analysis", state="error")
                        st.error(f"Error analyzing ready file: {e}")
                        import traceback

                        st.code(traceback.format_exc())

        # ===== SECTION-BASED ANALYSIS PATH =====
        else:
            # Use status context for multi-step analysis
            with st.status(
                "Analyzing HRV for selected sections...", expanded=True
            ) as status:
                try:
                    st.write("Loading recording data...")
                    progress = st.progress(0)

                    # Check source type from summary
                    summary = get_summary_dict().get(selected_participant)
                    source_app = (
                        getattr(summary, "source_app", "HRV Logger")
                        if summary
                        else "HRV Logger"
                    )
                    is_vns = source_app == "VNS Analyse"

                    if is_vns:
                        vns_paths = getattr(summary, "vns_paths", None)
                        if vns_paths:
                            recording_data = cached_load_vns_recording(
                                tuple(str(p) for p in vns_paths),
                                selected_participant,
                                use_corrected=st.session_state.get(
                                    "vns_use_corrected", False
                                ),
                            )
                        elif getattr(summary, "vns_path", None):
                            # Fallback: single path (old cached summary)
                            recording_data = cached_load_vns_recording(
                                (str(summary.vns_path),),
                                selected_participant,
                                use_corrected=st.session_state.get(
                                    "vns_use_corrected", False
                                ),
                            )
                        else:
                            # Re-discover VNS recordings
                            from rrational.io.vns_analyse import discover_vns_recordings
                            from pathlib import Path

                            vns_bundles = discover_vns_recordings(
                                Path(st.session_state.data_dir),
                                pattern=st.session_state.id_pattern,
                            )
                            vns_bundle = next(
                                (
                                    b
                                    for b in vns_bundles
                                    if b.participant_id == selected_participant
                                ),
                                None,
                            )
                            if not vns_bundle:
                                st.error(
                                    f"No VNS recording found for {selected_participant}"
                                )
                                return
                            recording_data = cached_load_vns_recording(
                                tuple(str(p) for p in vns_bundle.file_paths),
                                selected_participant,
                                use_corrected=st.session_state.get(
                                    "vns_use_corrected", False
                                ),
                            )
                    else:
                        # Load HRV Logger recording
                        bundles = cached_discover_recordings(
                            st.session_state.data_dir, st.session_state.id_pattern
                        )
                        bundle = next(
                            b
                            for b in bundles
                            if b.participant_id == selected_participant
                        )
                        recording_data = cached_load_recording(
                            tuple(str(p) for p in bundle.rr_paths),
                            tuple(str(p) for p in bundle.events_paths),
                            selected_participant,
                        )

                    # Reconstruct recording object from cached data
                    rr_intervals = [
                        RRInterval(timestamp=ts, rr_ms=rr, elapsed_ms=elapsed)
                        for ts, rr, elapsed in recording_data["rr_intervals"]
                    ]

                    # Load stored/saved events from YAML - REQUIRED for analysis
                    # User must review and save events in Participants tab first
                    if selected_participant not in st.session_state.participant_events:
                        from rrational.gui.persistence import load_participant_events
                        from rrational.prep.summaries import EventStatus
                        from datetime import datetime as dt

                        saved = load_participant_events(
                            selected_participant, st.session_state.data_dir
                        )
                        if saved:
                            # Convert dicts to EventStatus objects (same as app.py)
                            def dict_to_event(d):
                                ts = d.get("first_timestamp")
                                if ts and isinstance(ts, str):
                                    ts = dt.fromisoformat(ts)
                                last_ts = d.get("last_timestamp")
                                if last_ts and isinstance(last_ts, str):
                                    last_ts = dt.fromisoformat(last_ts)
                                return EventStatus(
                                    raw_label=d.get("raw_label", ""),
                                    canonical=d.get("canonical"),
                                    first_timestamp=ts,
                                    last_timestamp=last_ts,
                                )

                            st.session_state.participant_events[
                                selected_participant
                            ] = {
                                "events": [
                                    dict_to_event(e) for e in saved.get("events", [])
                                ],
                                "manual": [
                                    dict_to_event(e) for e in saved.get("manual", [])
                                ],
                                "music_events": [
                                    dict_to_event(e)
                                    for e in saved.get("music_events", [])
                                ],
                                "exclusion_zones": saved.get("exclusion_zones", []),
                            }

                    stored_events = st.session_state.participant_events.get(
                        selected_participant, {}
                    )
                    all_stored = stored_events.get("events", []) + stored_events.get(
                        "manual", []
                    )

                    if not all_stored:
                        # No saved events - STOP and warn user
                        st.error(f"No saved events found for {selected_participant}!")
                        st.warning(
                            "**Please review and save the participant's data first:**\n"
                            "1. Go to the **Participants** tab\n"
                            "2. Select this participant\n"
                            "3. Review and edit events as needed\n"
                            "4. Click **Save Events** to save your changes\n\n"
                            "Analysis requires processed/saved events to ensure data quality."
                        )
                        status.update(
                            label="Analysis stopped - no saved events", state="error"
                        )
                        return

                    # Use saved/processed events (with canonical labels)
                    st.write(
                        f"Using {len(all_stored)} saved events for {selected_participant}"
                    )
                    events = []
                    for evt in all_stored:
                        # Handle both dict (from YAML) and object formats
                        if isinstance(evt, dict):
                            ts = evt.get("first_timestamp")
                            label = evt.get("canonical") or evt.get(
                                "raw_label", "unknown"
                            )
                        else:
                            ts = getattr(evt, "first_timestamp", None)
                            label = getattr(evt, "canonical", None) or getattr(
                                evt, "raw_label", "unknown"
                            )

                        if ts:
                            # Convert string timestamps from YAML to datetime
                            if isinstance(ts, str):
                                from datetime import datetime

                                ts = datetime.fromisoformat(ts)
                            events.append(
                                EventMarker(label=label, timestamp=ts, offset_s=None)
                            )

                    # Debug: show event labels
                    with st.expander("Debug: Event labels", expanded=False):
                        for evt in events:
                            st.write(f"  - '{evt.label}' at {evt.timestamp}")

                    recording = HRVLoggerRecording(
                        participant_id=selected_participant,
                        rr_intervals=rr_intervals,
                        events=events,
                    )
                    progress.progress(20)

                    # Store results for each section
                    section_results = {}
                    combined_rr = []

                    st.write(f"Analyzing {len(selected_sections)} section(s)...")

                    # Analyze each section individually
                    for idx, section_name in enumerate(selected_sections):
                        progress.progress(20 + int((idx / len(selected_sections)) * 60))
                        st.write(f"  • Processing section: {section_name}")

                        section_def = st.session_state.sections[section_name]
                        start_evt = section_def.get("start_event")
                        end_evts = section_def.get("end_events", []) or [
                            section_def.get("end_event")
                        ]
                        st.write(
                            f"    Looking for: start='{start_evt}', end={end_evts}"
                        )

                        # Add section name to def for centralized validation
                        section_def_with_name = {**section_def, "name": section_name}
                        section_rr = extract_section_rr_intervals(
                            recording,
                            section_def_with_name,
                            st.session_state.normalizer,
                            saved_events=all_stored,
                            participant_id=selected_participant,  # Use centralized validation
                        )

                        if section_rr:
                            # Apply exclusion zone filtering
                            exclusion_zones = _get_exclusion_zones(selected_participant)
                            if exclusion_zones:
                                section_rr, excl_stats = filter_exclusion_zones(
                                    section_rr, exclusion_zones
                                )
                                if excl_stats["n_excluded"] > 0:
                                    st.write(
                                        f"    Excluded {excl_stats['n_excluded']} intervals ({excl_stats['excluded_duration_ms'] / 1000:.1f}s) from {excl_stats['zones_applied']} zone(s)"
                                    )

                            # Clean RR intervals for this section
                            cleaned_section_rr, stats = clean_rr_intervals(
                                section_rr, st.session_state.cleaning_config
                            )

                            if cleaned_section_rr:
                                rr_ms = [rr.rr_ms for rr in cleaned_section_rr]

                                # Apply artifact correction if enabled
                                artifact_info = None
                                if apply_artifact_correction:
                                    st.write("    Applying artifact correction...")
                                    artifact_result = detect_artifacts_fixpeaks(rr_ms)
                                    if artifact_result["correction_applied"]:
                                        rr_ms = artifact_result["corrected_rr"]
                                        artifact_info = artifact_result
                                        st.write(
                                            f"    * Corrected {artifact_result['total_artifacts']} artifacts"
                                        )

                                combined_rr.extend(rr_ms)

                                # Calculate HRV metrics
                                nk = get_neurokit()

                                # Check if overlapping window analysis is enabled
                                if use_overlapping_windows:
                                    import numpy as np
                                    from rrational.gui.segmentation import (
                                        generate_segments as gen_segs,
                                    )

                                    analysis_mode_raw_val = st.session_state.get(
                                        "analysis_mode_raw", "aggregated"
                                    )
                                    nn_arr = np.asarray(rr_ms, dtype=np.float64)

                                    if analysis_mode_raw_val == "per_segment":
                                        # Use segments from artifact detection if available
                                        selected_participant = st.session_state.get(
                                            "selected_participant", ""
                                        )
                                        artifact_data = st.session_state.get(
                                            f"artifacts_{selected_participant}", {}
                                        )
                                        det_segments = artifact_data.get("segments", [])
                                        seg_inclusion = st.session_state.get(
                                            f"segment_inclusion_{selected_participant}",
                                            {},
                                        )

                                        if det_segments:
                                            windows = []
                                            for seg in det_segments:
                                                if seg_inclusion.get(
                                                    seg.idx, seg.included
                                                ):
                                                    sliced = nn_arr[
                                                        seg.beat_start : seg.beat_end
                                                    ].tolist()
                                                    if len(sliced) >= 30:
                                                        windows.append(
                                                            (
                                                                seg.idx,
                                                                seg.start_ms,
                                                                sliced,
                                                            )
                                                        )
                                            window_info_str = (
                                                f"per-segment ({len(windows)} included)"
                                            )
                                        else:
                                            # No segments from artifact detection — generate fresh
                                            segs = gen_segs(
                                                nn_arr, window_s=300.0, overlap_pct=0.0
                                            )
                                            windows = [
                                                (
                                                    s.idx,
                                                    s.start_ms,
                                                    nn_arr[
                                                        s.beat_start : s.beat_end
                                                    ].tolist(),
                                                )
                                                for s in segs
                                                if s.n_beats >= 30
                                            ]
                                            window_info_str = (
                                                "5min segments, no overlap"
                                            )
                                    else:
                                        w_dur_min = (
                                            window_duration_min
                                            if window_duration_min
                                            else 5
                                        )
                                        o_pct = (
                                            overlap_percent
                                            if overlap_percent is not None
                                            else 50
                                        )
                                        segs = gen_segs(
                                            nn_arr,
                                            window_s=w_dur_min * 60.0,
                                            overlap_pct=float(o_pct),
                                        )
                                        windows = [
                                            (
                                                s.idx,
                                                s.start_ms,
                                                nn_arr[
                                                    s.beat_start : s.beat_end
                                                ].tolist(),
                                            )
                                            for s in segs
                                            if s.n_beats >= 30
                                        ]
                                        window_info_str = (
                                            f"{w_dur_min}min, {o_pct}% overlap"
                                        )

                                    if len(windows) >= 1:
                                        st.write(
                                            f"    Analyzing {len(windows)} overlapping windows ({window_info_str})..."
                                        )

                                        window_hrv_results = []
                                        window_details = []

                                        for win_idx, win_start, win_rr in windows:
                                            if (
                                                len(win_rr) < 30
                                            ):  # Skip windows with too few beats
                                                continue

                                            try:
                                                win_peaks = nk.intervals_to_peaks(
                                                    win_rr, sampling_rate=1000
                                                )
                                                win_hrv_time = nk.hrv_time(
                                                    win_peaks,
                                                    sampling_rate=1000,
                                                    show=False,
                                                )
                                                win_hrv_freq = nk.hrv_frequency(
                                                    win_peaks,
                                                    sampling_rate=1000,
                                                    show=False,
                                                )
                                                win_hrv = pd.concat(
                                                    [win_hrv_time, win_hrv_freq], axis=1
                                                )

                                                window_hrv_results.append(win_hrv)
                                                detail = {
                                                    "window_idx": win_idx,
                                                    "n_beats": len(win_rr),
                                                    "duration_s": sum(win_rr) / 1000,
                                                    "hrv_results": win_hrv,
                                                }
                                                if window_mode == "beats":
                                                    detail["start_beat"] = win_start
                                                else:
                                                    detail["start_ms"] = win_start
                                                window_details.append(detail)
                                            except Exception as e:
                                                st.write(
                                                    f"      Window {win_idx + 1} failed: {e}"
                                                )
                                                continue

                                        if window_hrv_results:
                                            # Aggregate results across windows
                                            hrv_results, hrv_std = (
                                                aggregate_hrv_results(
                                                    window_hrv_results
                                                )
                                            )
                                            st.write(
                                                f"    Aggregated results from {len(window_hrv_results)} valid windows"
                                            )

                                            section_results[section_name] = {
                                                "hrv_results": hrv_results,
                                                "hrv_std": hrv_std,
                                                "rr_intervals": rr_ms,
                                                "n_beats": len(rr_ms),
                                                "label": section_def.get(
                                                    "label", section_name
                                                ),
                                                "artifact_info": artifact_info,
                                                "overlapping_analysis": True,
                                                "n_windows": len(window_hrv_results),
                                                "window_mode": window_mode,
                                                "window_duration_min": window_duration_min,
                                                "overlap_percent": overlap_percent,
                                                "window_beats": window_beats,
                                                "step_beats": step_beats,
                                                "window_details": window_details,
                                            }
                                        else:
                                            st.warning(
                                                f"    No valid windows for section '{section_name}'"
                                            )
                                    else:
                                        st.warning(
                                            "    Section too short for overlapping windows, using single analysis"
                                        )
                                        # Fall back to single analysis
                                        peaks = nk.intervals_to_peaks(
                                            rr_ms, sampling_rate=1000
                                        )
                                        hrv_time = nk.hrv_time(
                                            peaks, sampling_rate=1000, show=False
                                        )
                                        hrv_freq = nk.hrv_frequency(
                                            peaks, sampling_rate=1000, show=False
                                        )
                                        hrv_results = pd.concat(
                                            [hrv_time, hrv_freq], axis=1
                                        )

                                        section_results[section_name] = {
                                            "hrv_results": hrv_results,
                                            "rr_intervals": rr_ms,
                                            "n_beats": len(rr_ms),
                                            "label": section_def.get(
                                                "label", section_name
                                            ),
                                            "artifact_info": artifact_info,
                                        }
                                else:
                                    # Standard single-window analysis
                                    peaks = nk.intervals_to_peaks(
                                        rr_ms, sampling_rate=1000
                                    )
                                    hrv_time = nk.hrv_time(
                                        peaks, sampling_rate=1000, show=False
                                    )
                                    hrv_freq = nk.hrv_frequency(
                                        peaks, sampling_rate=1000, show=False
                                    )
                                    hrv_results = pd.concat(
                                        [hrv_time, hrv_freq], axis=1
                                    )

                                    section_results[section_name] = {
                                        "hrv_results": hrv_results,
                                        "rr_intervals": rr_ms,
                                        "n_beats": len(rr_ms),
                                        "label": section_def.get("label", section_name),
                                        "artifact_info": artifact_info,
                                    }
                        else:
                            st.write(
                                f"  Could not find events for section '{section_name}'"
                            )

                    # Analyze combined sections if multiple selected
                    if len(selected_sections) > 1 and combined_rr:
                        progress.progress(80)
                        st.write("Computing combined analysis...")
                        nk = get_neurokit()
                        peaks = nk.intervals_to_peaks(combined_rr, sampling_rate=1000)
                        hrv_time = nk.hrv_time(peaks, sampling_rate=1000, show=False)
                        hrv_freq = nk.hrv_frequency(
                            peaks, sampling_rate=1000, show=False
                        )
                        combined_hrv = pd.concat([hrv_time, hrv_freq], axis=1)
                        section_results["_combined"] = {
                            "hrv_results": combined_hrv,
                            "rr_intervals": combined_rr,
                            "n_beats": len(combined_rr),
                            "label": "Combined Sections",
                        }

                    # Store in session state
                    progress.progress(100)
                    st.session_state.analysis_results[selected_participant] = (
                        section_results
                    )

                    status.update(
                        label=f"Analysis complete for {len(section_results)} section(s)!",
                        state="complete",
                    )
                    show_toast(
                        f"Analysis complete for {len(section_results)} section(s)",
                        icon="success",
                    )

                except Exception as e:
                    status.update(label="Error during analysis", state="error")
                    st.error(f"Error during analysis: {e}")
                    import traceback

                    st.code(traceback.format_exc())

    # Display results if available
    if selected_participant in st.session_state.analysis_results:
        _display_single_participant_results(selected_participant)


def _display_stats_row(stats: dict, key_prefix: str = ""):
    """Display statistics as a row of metrics below a plot.

    Stats can be either:
    - Simple string values: {"Label": "123 ms"}
    - Tuple with delta: {"Label": ("123 ms", "45%")} for value with delta
    """
    if not stats:
        return
    n_cols = min(len(stats), 5)  # Max 5 columns
    cols = st.columns(n_cols)
    for i, (label, value) in enumerate(stats.items()):
        with cols[i % n_cols]:
            if isinstance(value, tuple) and len(value) == 2:
                # Value with delta (e.g., ("651 ms²", "38%"))
                st.metric(label, value[0], delta=value[1], delta_color="off")
            else:
                st.metric(label, value)


def _display_single_participant_results(selected_participant: str):
    """Display HRV analysis results for a single participant with professional visualizations."""
    st.markdown("---")
    st.subheader(f"Results for {selected_participant}")

    section_results = st.session_state.analysis_results[selected_participant]

    # Create documentation object if we have results
    if section_results:
        doc = AnalysisDocumentation(selected_participant)

        # Try to get data source info
        summary = get_summary_dict().get(selected_participant)
        source_app = (
            getattr(summary, "source_app", "HRV Logger") if summary else "HRV Logger"
        )
        total_raw_beats = sum(r.get("n_beats", 0) for r in section_results.values())
        total_duration = sum(
            sum(r.get("rr_intervals", [])) / 1000.0 for r in section_results.values()
        )

        doc.set_data_source(source_app, total_raw_beats, total_duration)
        doc.set_cleaning_config(st.session_state.get("cleaning_config", {}))

        # Check if artifact correction was applied
        artifact_correction_applied = any(
            r.get("artifact_info") is not None for r in section_results.values()
        )
        if artifact_correction_applied:
            first_artifact = next(
                (
                    r.get("artifact_info")
                    for r in section_results.values()
                    if r.get("artifact_info")
                ),
                None,
            )
            doc.set_artifact_correction(True, first_artifact)
        else:
            doc.set_artifact_correction(False)

        # Add exclusion zones
        exclusion_zones = _get_exclusion_zones(selected_participant)
        doc.add_exclusion_zones(exclusion_zones)

    for section_name, result_data in section_results.items():
        section_label = result_data["label"]
        hrv_results = result_data["hrv_results"]
        rr_intervals = result_data["rr_intervals"]
        n_beats = result_data["n_beats"]
        artifact_info = result_data.get("artifact_info")

        # Calculate recording duration from RR intervals (sum of intervals)
        recording_duration_sec = sum(rr_intervals) / 1000.0 if rr_intervals else 0

        # Add to documentation
        if section_results:
            section_def = st.session_state.sections.get(section_name, {})
            doc.add_section(
                name=section_name,
                label=section_label,
                start_event=section_def.get("start_event", "N/A"),
                end_events=section_def.get("end_events", [])
                or [section_def.get("end_event", "N/A")],
                beats_extracted=n_beats,
                beats_after_cleaning=n_beats,
            )
            doc.add_hrv_results(section_name, hrv_results)

        with st.expander(
            f"{section_label} ({n_beats} beats, {recording_duration_sec / 60:.1f} min)",
            expanded=True,
        ):
            # Show overlapping window analysis info if used
            if result_data.get("overlapping_analysis"):
                n_windows = result_data.get("n_windows", 0)
                window_mode = result_data.get("window_mode", "time")
                hrv_std = result_data.get("hrv_std")

                if window_mode == "beats":
                    window_beats = result_data.get("window_beats", 300)
                    step_beats = result_data.get("step_beats", 150)
                    window_info = f"{window_beats} beats, {step_beats}-beat step"
                else:
                    window_duration = result_data.get("window_duration_min")
                    overlap_pct = result_data.get("overlap_percent")
                    if window_duration is not None and overlap_pct is not None:
                        window_info = f"{window_duration}min, {overlap_pct}% overlap"
                    else:
                        window_info = "per-segment"

                # Get segment info from analysis_segments if available
                analysis_segments = result_data.get("analysis_segments", [])
                gap_segments = len(
                    [s for s in analysis_segments if s.get("type") == "usable"]
                )
                exclusion_segments = len(
                    [s for s in analysis_segments if s.get("type") == "exclusion"]
                )

                st.info(
                    f"**Overlapping Window Analysis:** {n_windows} windows analyzed ({window_info})"
                )
                if analysis_segments:
                    st.caption(
                        f"Based on {gap_segments} usable segment(s)"
                        + (
                            f", {exclusion_segments} exclusion zone(s)"
                            if exclusion_segments
                            else ""
                        )
                    )

                # Show std values if available
                if hrv_std is not None and not hrv_std.empty:
                    with st.expander("Window Variability (Std Dev)", expanded=False):
                        st.caption("Standard deviation across overlapping windows:")
                        # Show key metrics with std
                        key_metrics = [
                            "HRV_MeanNN",
                            "HRV_SDNN",
                            "HRV_RMSSD",
                            "HRV_pNN50",
                            "HRV_LF",
                            "HRV_HF",
                        ]
                        std_display = {}
                        for m in key_metrics:
                            if m in hrv_std.columns:
                                std_display[m.replace("HRV_", "")] = (
                                    f"±{hrv_std[m].values[0]:.2f}"
                                )
                        if std_display:
                            cols = st.columns(len(std_display))
                            for i, (name, val) in enumerate(std_display.items()):
                                cols[i].metric(name, val)

            # Show ready file info if this came from a .rrational file
            ready_file_path = result_data.get("ready_file")
            quality_grade = result_data.get("quality_grade")
            audit_trail = result_data.get("audit_trail")

            if ready_file_path:
                st.caption(f"Source: {ready_file_path}")
                if quality_grade:
                    grade_colors = {
                        "excellent": "green",
                        "good": "blue",
                        "moderate": "orange",
                        "poor": "red",
                    }
                    st.markdown(
                        f"Quality grade: **:{grade_colors.get(quality_grade, 'gray')}[{quality_grade.upper()}]**"
                    )

                if audit_trail:
                    with st.expander("Audit Trail", expanded=False):
                        for step in audit_trail:
                            st.write(f"**{step.action}**: {step.details}")

            # Display HRV metrics using professional layout
            if not hrv_results.empty:
                display_hrv_metrics_professional(
                    hrv_results,
                    n_beats,
                    artifact_info,
                    recording_duration_sec=recording_duration_sec,
                )

            # Visualization tabs for professional plots
            if get_plotly_analysis()[0] is not None and len(rr_intervals) > 10:
                plot_tabs = st.tabs(
                    ["Tachogram", "Poincaré", "Frequency", "HR Distribution", "Data"]
                )

                with plot_tabs[0]:
                    # Educational info
                    display_visualization_info("tachogram")
                    # Professional Tachogram
                    artifact_indices = None
                    if artifact_info and "artifact_indices" in artifact_info:
                        artifact_indices = artifact_info["artifact_indices"]
                    fig_tach, tach_stats = create_professional_tachogram(
                        rr_intervals, section_label, artifact_indices
                    )
                    st.plotly_chart(fig_tach, use_container_width=True)
                    _display_stats_row(tach_stats, f"tach_{section_name}")

                with plot_tabs[1]:
                    # Educational info
                    display_visualization_info("poincare")
                    # Poincaré Plot
                    if len(rr_intervals) > 20:
                        fig_poincare, poincare_stats = create_poincare_plot(
                            rr_intervals, section_label
                        )
                        st.plotly_chart(fig_poincare, use_container_width=True)
                        _display_stats_row(poincare_stats, f"poincare_{section_name}")
                    else:
                        st.warning(
                            "Not enough data points for Poincaré plot (need >20 beats)"
                        )

                with plot_tabs[2]:
                    # Educational info
                    display_visualization_info("frequency")
                    # Frequency Domain Plot
                    if len(rr_intervals) > 100:
                        fig_freq, freq_stats = create_frequency_domain_plot(
                            rr_intervals, section_label
                        )
                        if fig_freq:
                            st.plotly_chart(fig_freq, use_container_width=True)
                            _display_stats_row(freq_stats, f"freq_{section_name}")
                    else:
                        st.warning(
                            "Not enough data for reliable frequency analysis (need >100 beats, ideally >300)"
                        )

                with plot_tabs[3]:
                    # Educational info
                    display_visualization_info("hr_distribution")
                    # Heart Rate Distribution
                    fig_hr, hr_stats = create_hr_distribution_plot(
                        rr_intervals, section_label
                    )
                    st.plotly_chart(fig_hr, use_container_width=True)
                    _display_stats_row(hr_stats, f"hr_{section_name}")

                with plot_tabs[4]:
                    # Full results table and download
                    if not hrv_results.empty:
                        st.markdown("**Complete HRV Metrics:**")
                        st.dataframe(hrv_results.T, use_container_width=True)

                        # Download buttons
                        col_dl1, col_dl2 = st.columns(2)
                        with col_dl1:
                            csv_hrv = hrv_results.to_csv(index=True)
                            st.download_button(
                                label="Download HRV Results (CSV)",
                                data=csv_hrv,
                                file_name=f"hrv_{selected_participant}_{section_name}.csv",
                                mime="text/csv",
                                key=f"download_hrv_{selected_participant}_{section_name}",
                            )
                        with col_dl2:
                            # Download RR intervals
                            rr_df = pd.DataFrame(
                                {
                                    "beat_index": range(len(rr_intervals)),
                                    "rr_ms": rr_intervals,
                                }
                            )
                            csv_rr = rr_df.to_csv(index=False)
                            st.download_button(
                                label="Download RR Intervals (CSV)",
                                data=csv_rr,
                                file_name=f"rr_{selected_participant}_{section_name}.csv",
                                mime="text/csv",
                                key=f"download_rr_{selected_participant}_{section_name}",
                            )

            else:
                # Fallback to matplotlib if Plotly not available
                if not hrv_results.empty:
                    st.markdown("**Key Metrics:**")
                    cols = st.columns(3)
                    metrics = [
                        ("HRV_RMSSD", "RMSSD"),
                        ("HRV_SDNN", "SDNN"),
                        ("HRV_pNN50", "pNN50"),
                    ]
                    for i, (col_name, label) in enumerate(metrics):
                        if col_name in hrv_results.columns:
                            with cols[i]:
                                st.metric(label, f"{hrv_results[col_name].iloc[0]:.2f}")

                    st.dataframe(hrv_results.T, use_container_width=True)

                # Simple matplotlib plot
                st.markdown("**Tachogram:**")
                plt = get_matplotlib()
                fig, ax = plt.subplots(figsize=(12, 4))
                ax.plot(
                    rr_intervals, marker="o", markersize=2, linestyle="-", linewidth=0.5
                )
                ax.set_xlabel("Beat Index")
                ax.set_ylabel("RR Interval (ms)")
                ax.set_title(f"Tachogram - {section_label}")
                ax.grid(True, alpha=0.3)
                st.pyplot(fig)
                plt.close(fig)

    # Display documentation panel at the end
    if section_results:
        display_documentation_panel(doc)


# =============================================================================
# GROUP ANALYSIS HELPER FUNCTIONS
# =============================================================================


def _collect_group_participants(selected_groups: list[str]) -> dict[str, list[str]]:
    """Collect participants for each selected group.

    Args:
        selected_groups: List of group names to collect

    Returns:
        Dict mapping group name to list of participant IDs
    """
    result = {}
    for group in selected_groups:
        participants = [
            pid
            for pid, gname in st.session_state.participant_groups.items()
            if gname == group
        ]
        result[group] = participants
    return result


def _find_rrational_v2_file(
    participant_id: str,
    project_path: str | None = None,
    data_dir: str | None = None,
) -> str | None:
    """Find the .rrational v2 file for a participant.

    Args:
        participant_id: The participant ID
        project_path: Path to the project folder
        data_dir: Alternative data directory

    Returns:
        Path to the .rrational v2 file, or None if not found
    """
    from pathlib import Path

    files = find_rrational_files(
        participant_id,
        data_dir=data_dir,
        project_path=Path(project_path) if project_path else None,
    )

    # Find v2 file
    for f in files:
        try:
            version = get_rrational_version(f)
            if version == RRATIONAL_VERSION_V2:
                return str(f)
        except Exception:
            continue

    return None


def _load_nn_from_rrational_v2(
    file_path: str,
    section_name: str,
) -> tuple[list[float] | None, dict]:
    """Load NN intervals from a v2 .rrational file for a specific section.

    Args:
        file_path: Path to the .rrational v2 file
        section_name: Name of the section to load

    Returns:
        Tuple of (nn_ms_list, info_dict) where:
        - nn_ms_list: List of NN interval values in ms, or None if not found
        - info_dict: Contains quality_grade, artifact_rate, n_beats, duration_s
    """
    try:
        export_data = load_rrational_v2(file_path)

        if section_name not in export_data.sections:
            return None, {"error": f"Section '{section_name}' not found in file"}

        section = export_data.sections[section_name]
        nn_data = section.nn_intervals.data

        if not nn_data:
            return None, {"error": "No NN intervals in section"}

        # Extract NN values (format: [[timestamp_ms, nn_ms, was_corrected], ...])
        nn_ms_list = [entry[1] for entry in nn_data]

        # Get quality info
        quality = section.quality
        info = {
            "quality_grade": quality.grade,
            "artifact_rate": (
                section.artifact_detection.artifact_rate_detected
                if section.artifact_detection
                else 0.0
            ),
            "n_beats": len(nn_ms_list),
            "duration_s": quality.usable_duration_s,
            "meets_time_domain": quality.meets_time_domain_min,
            "meets_freq_domain": quality.meets_freq_domain_min,
        }

        return nn_ms_list, info

    except Exception as e:
        return None, {"error": str(e)}


def _extract_nn_from_loaded_v2(
    export_data,
    section_name: str,
) -> tuple[list[float] | None, dict]:
    """Extract NN intervals from an already-loaded v2 export object.

    Same as _load_nn_from_rrational_v2 but avoids re-reading the YAML file.
    Used by Group Analysis to load the file once per participant.
    """
    try:
        if section_name not in export_data.sections:
            return None, {"error": f"Section '{section_name}' not found in file"}

        section = export_data.sections[section_name]
        nn_data = section.nn_intervals.data

        if not nn_data:
            return None, {"error": "No NN intervals in section"}

        nn_ms_list = [entry[1] for entry in nn_data]

        quality = section.quality
        info = {
            "quality_grade": quality.grade,
            "artifact_rate": (
                section.artifact_detection.artifact_rate_detected
                if section.artifact_detection
                else 0.0
            ),
            "n_beats": len(nn_ms_list),
            "duration_s": quality.usable_duration_s,
            "meets_time_domain": quality.meets_time_domain_min,
            "meets_freq_domain": quality.meets_freq_domain_min,
        }

        return nn_ms_list, info

    except Exception as e:
        return None, {"error": str(e)}


# _calculate_hrv_metrics is now imported from rrational.analysis.hrv_compute

# =============================================================================
# GROUP ANALYSIS MAIN PIPELINE
# =============================================================================


# _format_duration imported from rrational.analysis.hrv_metrics


def _load_raw_section_data(
    pid: str,
    section_name: str,
    rrational_path: str,
    project_path,
    data_dir,
) -> tuple[list[float] | None, dict]:
    """Load raw RR data for a section using on-demand recording loading.

    This is a fallback when NN intervals are not available. It loads the
    original recording on-demand and extracts the section using section definitions.
    Uses the same approach as "Use raw data" mode in single participant analysis.

    Returns:
        Tuple of (rr_ms_list, info_dict) where:
        - rr_ms_list: List of raw RR interval values in ms, or None if not found
        - info_dict: Contains n_beats, duration_s, data_source info
    """
    from datetime import datetime
    from rrational.io.hrv_logger import HRVLoggerRecording, RRInterval, EventMarker
    from rrational.gui.persistence import load_participant_events
    from rrational.cleaning.rr import clean_rr_intervals
    from rrational.gui.rrational_export import load_rrational_v2

    try:
        # Load .rrational to get section definition
        export_data = load_rrational_v2(rrational_path)

        if section_name not in export_data.sections:
            return None, {"error": f"Section '{section_name}' not in .rrational file"}

        section = export_data.sections[section_name]

        # Get section definition for extraction
        if not section.definition:
            return None, {"error": "No section definition in .rrational file"}

        # Load recording data on-demand (same as single participant analysis)
        summary = get_summary_dict().get(pid)
        source_app = (
            getattr(summary, "source_app", "HRV Logger") if summary else "HRV Logger"
        )
        is_vns = source_app == "VNS Analyse"

        recording_data = None
        if is_vns:
            # Load VNS Analyse recording
            vns_paths = getattr(summary, "vns_paths", None)
            if vns_paths:
                recording_data = cached_load_vns_recording(
                    tuple(str(p) for p in vns_paths),
                    pid,
                    use_corrected=st.session_state.get("vns_use_corrected", False),
                )
            elif getattr(summary, "vns_path", None):
                recording_data = cached_load_vns_recording(
                    (str(summary.vns_path),),
                    pid,
                    use_corrected=st.session_state.get("vns_use_corrected", False),
                )
            else:
                # Re-discover VNS recordings
                from rrational.io.vns_analyse import discover_vns_recordings

                vns_bundles = discover_vns_recordings(
                    Path(st.session_state.data_dir), pattern=st.session_state.id_pattern
                )
                vns_bundle = next(
                    (b for b in vns_bundles if b.participant_id == pid), None
                )
                if vns_bundle:
                    recording_data = cached_load_vns_recording(
                        tuple(str(p) for p in vns_bundle.file_paths),
                        pid,
                        use_corrected=st.session_state.get("vns_use_corrected", False),
                    )
        else:
            # Load HRV Logger recording
            bundles = cached_discover_recordings(
                st.session_state.data_dir, st.session_state.id_pattern
            )
            bundle = next((b for b in bundles if b.participant_id == pid), None)
            if bundle:
                recording_data = cached_load_recording(
                    tuple(str(p) for p in bundle.rr_paths),
                    tuple(str(p) for p in bundle.events_paths),
                    pid,
                )

        if not recording_data:
            return None, {"error": "Could not load raw recording data"}

        # Reconstruct recording object
        rr_intervals = [
            RRInterval(timestamp=ts, rr_ms=rr, elapsed_ms=elapsed)
            for ts, rr, elapsed in recording_data["rr_intervals"]
        ]

        # Load saved events for this participant
        saved_events = load_participant_events(pid, st.session_state.data_dir)
        all_stored = []
        if saved_events:
            all_stored = saved_events.get("events", []) + saved_events.get("manual", [])

        # Convert to EventMarker objects
        events = []
        for evt in all_stored:
            ts = (
                evt.get("first_timestamp")
                if isinstance(evt, dict)
                else getattr(evt, "first_timestamp", None)
            )
            label = (
                (evt.get("canonical") or evt.get("raw_label", "unknown"))
                if isinstance(evt, dict)
                else (
                    getattr(evt, "canonical", None)
                    or getattr(evt, "raw_label", "unknown")
                )
            )
            if ts:
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts)
                events.append(EventMarker(label=label, timestamp=ts, offset_s=None))

        recording = HRVLoggerRecording(
            participant_id=pid, rr_intervals=rr_intervals, events=events
        )

        # Build section definition from .rrational data
        # Note: end_event is singular in v2 format, convert to end_events list
        section_def = {
            "name": section_name,
            "start_event": section.definition.start_event,
            "end_events": [section.definition.end_event],
            "label": section.definition.label,
        }

        # Extract section using same logic as "Use raw data" mode
        section_rr = extract_section_rr_intervals(
            recording,
            section_def,
            st.session_state.normalizer,
            saved_events=all_stored,
            participant_id=pid,
        )

        if not section_rr:
            return None, {
                "error": "Could not extract section from raw data (check event markers)"
            }

        # Clean RR intervals
        cleaning_config = st.session_state.get("cleaning_config", {})
        cleaned_rr, stats = clean_rr_intervals(section_rr, cleaning_config)

        if not cleaned_rr:
            return None, {"error": "No valid RR intervals after cleaning"}

        rr_values = [rr.rr_ms for rr in cleaned_rr]
        duration_s = sum(rr_values) / 1000.0

        return rr_values, {
            "n_beats": len(rr_values),
            "duration_s": duration_s,
            "quality_grade": "raw",
            "artifact_rate": 0.0,  # Unknown for raw data
            "data_source": "Raw",
        }

    except Exception as e:
        return None, {"error": f"Error loading raw data: {e}"}


def _run_group_analysis(
    config: dict,
    progress_callback: callable | None = None,
) -> tuple[list[ParticipantSectionResult], dict, dict]:
    """Run HRV analysis for multiple groups.

    Args:
        config: Configuration dict with keys:
            - selected_groups: List of group names
            - sections_per_group: Dict mapping group -> list of section names
            - use_overlapping_windows: bool
            - window_beats: int
            - overlap_percent: float
            - completeness_filter: bool
            - selected_metrics: List of metric names to calculate
            - allow_raw_fallback: bool - If True, use raw RR data when NN is unavailable
        progress_callback: Optional callback function(current, total, message) for progress updates

    Returns:
        Tuple of (results, missing, excluded)
        - results: List of ParticipantSectionResult
        - missing: Dict of {participant_id: {section: reason}}
        - excluded: Dict of {participant_id: reason}
    """
    results = []
    missing = {}
    excluded = {}

    project_path = st.session_state.get("project_path")
    data_dir = st.session_state.get("data_dir")
    selected_metrics = config.get("selected_metrics")
    allow_raw_fallback = config.get("allow_raw_fallback", False)

    group_participants = _collect_group_participants(config["selected_groups"])

    # Calculate total work units for progress tracking
    # Work units per participant: 1 (find file) + sections × 2 (load + calculate per section)
    total_sections_per_participant = {
        g: len(config["sections_per_group"].get(g, []))
        for g in config["selected_groups"]
    }
    total_work = sum(
        len(group_participants.get(g, [])) * (1 + total_sections_per_participant[g] * 2)
        for g in config["selected_groups"]
    )
    current_work = 0

    def update_progress(increment: int, message: str):
        nonlocal current_work
        current_work += increment
        if progress_callback:
            progress_callback(current_work, total_work, message)

    for group in config["selected_groups"]:
        sections = config["sections_per_group"].get(group, [])
        participants = group_participants.get(group, [])

        for pid in participants:
            update_progress(0, f"[{pid}] Finding .rrational file...")

            # Find .rrational v2 file
            rrational_path = _find_rrational_v2_file(
                pid, project_path=project_path, data_dir=data_dir
            )

            if not rrational_path:
                missing[pid] = {
                    "_all": f"No .rrational v2 file found (project_path={project_path}, data_dir={data_dir})"
                }
                # Skip all work for this participant
                update_progress(1 + len(sections) * 2, f"[{pid}] Skipped (no file)")
                continue

            update_progress(1, f"[{pid}] Loading file...")

            # Load .rrational file ONCE for all sections (avoids repeated YAML parsing)
            try:
                export_data = load_rrational_v2(rrational_path)
            except Exception as e:
                missing[pid] = {"_all": f"Failed to load file: {e}"}
                update_progress(len(sections) * 2, f"[{pid}] Load failed: {e}")
                continue

            # Extract NN data from already-loaded export (fast — no file I/O per section)
            available = []
            for section in sections:
                update_progress(0, f"[{pid}] Loading {section}...")

                nn_data, info = _extract_nn_from_loaded_v2(export_data, section)
                if nn_data and len(nn_data) >= MIN_BEATS_TIME_DOMAIN:
                    info["data_source"] = "NN"
                    available.append((section, nn_data, info))
                    update_progress(1, f"[{pid}] Loaded {section} (NN)")
                elif allow_raw_fallback:
                    update_progress(0, f"[{pid}] Loading {section} (raw fallback)...")
                    raw_data, raw_info = _load_raw_section_data(
                        pid, section, rrational_path, project_path, data_dir
                    )
                    if raw_data and len(raw_data) >= MIN_BEATS_TIME_DOMAIN:
                        available.append((section, raw_data, raw_info))
                        update_progress(1, f"[{pid}] Loaded {section} (Raw)")
                    else:
                        nn_error = info.get("error", "No NN data")
                        raw_error = (
                            raw_info.get("error", "No raw data")
                            if raw_info
                            else "Raw fallback failed"
                        )
                        missing.setdefault(pid, {})[section] = (
                            f"NN: {nn_error}; Raw: {raw_error}"
                        )
                        update_progress(1, f"[{pid}] {section} failed")
                else:
                    error_detail = info.get("error", "Insufficient data")
                    missing.setdefault(pid, {})[section] = error_detail
                    update_progress(1, f"[{pid}] {section} failed: {error_detail}")

            # Completeness filter
            if config["completeness_filter"] and len(available) < len(sections):
                excluded[pid] = (
                    f"Missing {len(sections) - len(available)} of {len(sections)} sections"
                )
                # Skip HRV calculation work
                update_progress(len(sections), f"[{pid}] Excluded (incomplete)")
                continue

            # Calculate HRV for each available section
            for section, rr_data, info in available:
                update_progress(0, f"[{pid}] Calculating HRV for {section}...")

                metrics, std, n_win = _calculate_hrv_metrics(
                    rr_data,
                    config["use_overlapping_windows"],
                    config["window_beats"],
                    config["overlap_percent"],
                    selected_metrics=selected_metrics,
                )

                results.append(
                    ParticipantSectionResult(
                        participant_id=pid,
                        group=group,
                        section_name=section,
                        n_beats=info.get("n_beats", len(rr_data)),
                        duration_s=info.get("duration_s", sum(rr_data) / 1000),
                        quality_grade=info.get("quality_grade", "unknown"),
                        artifact_rate=info.get("artifact_rate", 0.0),
                        hrv_metrics=metrics,
                        hrv_std=std,
                        n_windows=n_win,
                        data_source=info.get("data_source", "NN"),
                    )
                )

                update_progress(1, f"[{pid}] Completed {section}")

            # Account for skipped sections (already counted during loading)
            # No need to add more - skipped sections already counted in loading phase

    update_progress(0, "Analysis complete!")
    return results, missing, excluded


def _render_hypothesis_tests(long_df):
    """Render the hypothesis testing UI within the Statistics tab.

    Lets the user:
    - Pick a metric
    - Run between-groups comparison per section (or across all sections)
    - Apply multiple-comparisons correction
    - See test name, statistic, p-value, effect size, and sample sizes
    """
    from rrational.analysis.group_statistics import (
        adjust_pvalues,
        compare_groups,
        should_log_transform,
    )

    st.markdown("### Hypothesis Tests")

    if long_df.empty:
        st.info("No data available for hypothesis testing.")
        return

    # Identify available metrics (exclude metadata)
    exclude_cols = {
        "participant_id",
        "group",
        "section",
        "data_source",
        "n_beats",
        "duration_s",
        "quality",
        "artifact_rate",
        "n_windows",
    }
    metric_cols = [
        c for c in long_df.columns if c not in exclude_cols and not c.endswith("_sd")
    ]
    if not metric_cols:
        st.info("No metric columns found.")
        return

    groups = sorted(long_df["group"].dropna().unique().tolist())
    if len(groups) < 2:
        st.info(
            f"Hypothesis testing needs at least 2 groups — only {len(groups)} found."
        )
        return

    sections = sorted(long_df["section"].dropna().unique().tolist())

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        selected_metrics = st.multiselect(
            "Metrics to test",
            options=metric_cols,
            default=[m for m in ["rmssd", "sdnn", "hf", "lf_hf"] if m in metric_cols][
                :3
            ],
            format_func=lambda s: s.upper(),
            key="group_test_metrics",
            help="Select one or more HRV metrics to test for group differences.",
        )
    with col2:
        selected_sections = st.multiselect(
            "Sections to test",
            options=sections,
            default=sections,
            key="group_test_sections",
            help="Run a separate test per section.",
        )
    with col3:
        correction = st.selectbox(
            "Correction",
            options=["none", "holm", "bonferroni", "fdr_bh"],
            index=1,
            key="group_test_correction",
            help=(
                "Multiple-comparisons correction when running many tests.\n"
                "- holm: Holm-Bonferroni (conservative, controls family-wise error)\n"
                "- bonferroni: simplest, most conservative\n"
                "- fdr_bh: Benjamini-Hochberg (less conservative, controls FDR)\n"
                "- none: no correction (valid only for a single planned test)"
            ),
        )

    if not selected_metrics or not selected_sections:
        st.info("Select at least one metric and one section.")
        return

    # Run tests
    results = []
    errors = []
    for metric in selected_metrics:
        metric_upper = metric.upper()
        log_transform = should_log_transform(metric_upper)
        for section in selected_sections:
            subset = long_df[long_df["section"] == section]
            values_per_group = {}
            for g in groups:
                g_vals = subset[subset["group"] == g][metric].dropna().tolist()
                if g_vals:
                    values_per_group[g] = g_vals
            if len(values_per_group) < 2:
                continue
            try:
                result = compare_groups(
                    values_per_group,
                    metric=metric_upper,
                    section=section,
                    log_transform=log_transform,
                )
                results.append(result)
            except ValueError as e:
                errors.append(f"{metric_upper} / {section}: {e}")

    if not results:
        st.warning("No valid comparisons could be run.")
        if errors:
            with st.expander("Errors"):
                for err in errors:
                    st.text(err)
        return

    # Apply correction across the batch
    if correction != "none":
        adjust_pvalues(results, method=correction)

    # Display results table
    import pandas as pd

    rows = []
    for r in results:
        row = {
            "Metric": r.metric,
            "Section": r.section,
            "Test": r.test_name,
            "Statistic": f"{r.statistic:.3f}",
            "p": f"{r.p_value:.4g}",
            "Sig": r.significance,
            r.effect_size_name: (
                f"{r.effect_size:.3f}" if r.effect_size is not None else "—"
            ),
        }
        for g, n in r.n_per_group.items():
            row[f"n_{g}"] = n
        for g, m in r.means.items():
            row[f"M_{g}"] = f"{m:.2f}"
        row["Note"] = r.note or ""
        rows.append(row)

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True)

    # Legend
    st.caption(
        "**Significance**: `***` p≤.001, `**` p≤.01, `*` p≤.05, `ns` not significant. "
        "**Effect size**: Cohen's d — small (0.2), medium (0.5), large (0.8). "
        "η² — small (.01), medium (.06), large (.14)."
    )

    # Download
    st.download_button(
        label="Download Tests CSV",
        data=df.to_csv(index=False),
        file_name="hrv_group_hypothesis_tests.csv",
        mime="text/csv",
        key="download_group_tests",
    )

    if errors:
        with st.expander(f"{len(errors)} test(s) could not be run"):
            for err in errors:
                st.text(err)


def _render_group_analysis():
    """Render group-level HRV analysis with multi-group support."""
    # Help expander
    with st.expander("**Group Analysis Best Practices**", expanded=False):
        st.markdown("""
**Overview:**
Group analysis allows you to compare HRV metrics across multiple groups and sections.
This feature uses `.rrational` v2 files which contain pre-processed NN intervals.

**Requirements:**
- Participants must have `.rrational` v2 files exported (from the Participants tab)
- At least 100 beats per section for time-domain metrics
- At least 300 beats per section for frequency-domain metrics

**Overlapping Windows:**
Using overlapping windows improves the reliability of HRV estimates by providing:
- Multiple measurements per participant per section
- Standard deviation as a measure of within-participant variability
- Reduced impact of transient artifacts

**Recommended settings:** 5 min/window, 50% overlap (time-based)
        """)

    # Check prerequisites
    available_sections = list(st.session_state.sections.keys())
    if not available_sections:
        st.warning(
            "No sections defined. Please define sections in the Sections tab first."
        )
        return

    group_list = list(st.session_state.groups.keys())
    if not group_list:
        st.warning(
            "No groups defined. Please define groups in the Participants tab first."
        )
        return

    # -------------------------------------------------------------------------
    # Step 1: Select Groups
    # -------------------------------------------------------------------------
    st.markdown("### Step 1: Select Groups")

    # Count participants per group
    group_counts = {}
    for group in group_list:
        count = sum(
            1 for g in st.session_state.participant_groups.values() if g == group
        )
        group_counts[group] = count

    # Multi-select with counts
    group_options = [f"{g} ({group_counts[g]} participants)" for g in group_list]
    group_map = {f"{g} ({group_counts[g]} participants)": g for g in group_list}

    selected_group_labels = st.multiselect(
        "Select groups to analyze",
        options=group_options,
        default=group_options,  # All groups selected by default
        key="group_analysis_groups",
    )
    selected_groups = [group_map[label] for label in selected_group_labels]

    if not selected_groups:
        st.info("Please select at least one group to analyze.")
        return

    # -------------------------------------------------------------------------
    # Step 2: Configure Sections per Group
    # -------------------------------------------------------------------------
    st.markdown("### Step 2: Configure Sections")

    sections_per_group = {}
    for group in selected_groups:
        with st.expander(f"**{group}** - Select sections", expanded=True):
            sections_per_group[group] = st.multiselect(
                f"Sections for {group}",
                options=available_sections,
                default=available_sections,  # All sections by default
                key=f"group_analysis_sections_{group}",
                label_visibility="collapsed",
            )

    # Check if any sections selected
    total_sections = sum(len(s) for s in sections_per_group.values())
    if total_sections == 0:
        st.info("Please select at least one section for at least one group.")
        return

    # -------------------------------------------------------------------------
    # Step 3: Analysis Options
    # -------------------------------------------------------------------------
    st.markdown("### Step 3: Analysis Options")

    # Metric preset selection
    st.markdown("**HRV Metrics**")
    preset_names = list(HRV_METRIC_PRESETS.keys())
    preset_col1, preset_col2 = st.columns([1, 2])

    with preset_col1:
        selected_preset = st.selectbox(
            "Metric preset",
            options=preset_names,
            index=1,  # Default to "Time + Frequency"
            key="group_analysis_metric_preset",
            help="Choose a preset or select 'Custom' to pick individual metrics",
        )

    # Show preset description
    with preset_col2:
        preset_info = HRV_METRIC_PRESETS[selected_preset]
        st.caption(preset_info["description"])

    # Custom metric selection
    if selected_preset == "Custom":
        # Organize by category for easier selection
        st.markdown("**Select metrics:**")
        metric_cols = st.columns(4)

        selected_metrics = []
        categories = [
            ("Time (Basic)", "time_basic"),
            ("Time (Extended)", "time_extended"),
            ("Frequency", "frequency"),
            ("Nonlinear", "nonlinear"),
        ]

        for i, (cat_label, cat_key) in enumerate(categories):
            with metric_cols[i]:
                st.markdown(f"*{cat_label}*")
                for metric_name in HRV_METRICS_CATALOG[cat_key].keys():
                    metric_info = HRV_METRICS_CATALOG[cat_key][metric_name]
                    if st.checkbox(
                        metric_info["label"],
                        value=metric_name
                        in ["RMSSD", "SDNN", "MeanHR"],  # Default selection
                        key=f"group_metric_{metric_name}",
                        help=metric_info["description"],
                    ):
                        selected_metrics.append(metric_name)
    else:
        selected_metrics = HRV_METRIC_PRESETS[selected_preset]["metrics"]

    # Show selected metrics summary
    if selected_metrics:
        st.caption(
            f"**Selected:** {', '.join(selected_metrics[:8])}{'...' if len(selected_metrics) > 8 else ''} ({len(selected_metrics)} metrics)"
        )
    else:
        st.warning("Please select at least one metric.")
        return

    st.markdown("**Analysis Settings**")
    col1, col2, col3 = st.columns(3)
    with col1:
        use_overlapping = st.checkbox(
            "Use overlapping windows",
            value=True,
            key="group_analysis_overlapping",
            help="Calculate HRV using overlapping windows for more reliable estimates",
        )
    with col2:
        completeness_filter = st.checkbox(
            "Only complete participants",
            value=False,
            key="group_analysis_completeness",
            help="Exclude participants missing any selected sections",
        )
    with col3:
        allow_raw_fallback = st.checkbox(
            "Allow raw data fallback",
            value=False,
            key="group_analysis_raw_fallback",
            help="When NN intervals are unavailable, use raw (uncorrected) RR data. "
            "Recommended: OFF — prepare each participant with 'Export for Analysis' first.",
        )

    if use_overlapping:
        col1, col2 = st.columns(2)
        with col1:
            window_beats = st.number_input(
                "Window size (beats)",
                min_value=100,
                max_value=1000,
                value=300,
                step=50,
                key="group_analysis_window_beats",
                help="Use 300+ beats for frequency domain metrics",
            )
        with col2:
            overlap_pct = st.slider(
                "Overlap (%)",
                min_value=0,
                max_value=90,
                value=75,
                step=5,
                key="group_analysis_overlap",
            )
    else:
        window_beats = 300
        overlap_pct = 75

    # -------------------------------------------------------------------------
    # Run Analysis Button
    # -------------------------------------------------------------------------
    st.divider()

    if st.button(
        "**Analyze Groups**",
        key="run_group_analysis_btn",
        type="primary",
        use_container_width=True,
    ):
        import time

        # Build configuration
        config = {
            "selected_groups": selected_groups,
            "sections_per_group": sections_per_group,
            "use_overlapping_windows": use_overlapping,
            "window_beats": window_beats,
            "overlap_percent": overlap_pct,
            "completeness_filter": completeness_filter,
            "selected_metrics": selected_metrics,
            "allow_raw_fallback": allow_raw_fallback,
        }

        # Count total participants
        total_participants = sum(group_counts[g] for g in selected_groups)
        total_sections_count = sum(
            len(sections_per_group.get(g, [])) for g in selected_groups
        )

        # Create progress UI elements
        progress_bar = st.progress(0, text="Starting analysis...")
        status_container = st.empty()

        start_time = time.time()
        last_update_time = [start_time]  # Use list to allow modification in closure

        def progress_callback(current: int, total: int, message: str):
            """Update progress bar with elapsed/remaining time estimation."""
            try:
                if total <= 0:
                    return

                progress_pct = min(current / total, 1.0)

                # Calculate time estimates
                now = time.time()
                elapsed = now - start_time

                # Build status text
                if progress_pct > 0.05 and current < total:
                    estimated_total = elapsed / progress_pct
                    remaining = estimated_total - elapsed
                    elapsed_str = _format_duration(elapsed)
                    remaining_str = _format_duration(remaining)
                    time_info = f"Elapsed: {elapsed_str} | Remaining: ~{remaining_str}"
                elif current >= total:
                    elapsed_str = _format_duration(elapsed)
                    time_info = f"Completed in {elapsed_str}"
                else:
                    elapsed_str = _format_duration(elapsed)
                    time_info = f"Elapsed: {elapsed_str} | Estimating..."

                # Update UI (throttled to avoid flicker)
                if now - last_update_time[0] >= 0.1 or current >= total or current == 0:
                    last_update_time[0] = now
                    # Use progress bar text parameter for cleaner display
                    pct_display = int(progress_pct * 100)
                    progress_bar.progress(
                        progress_pct, text=f"{pct_display}% - {message}"
                    )
                    status_container.caption(time_info)
            except Exception:
                # Silently ignore UI update errors to prevent crashes
                pass

        # Run the analysis with progress tracking
        results, missing, excluded = _run_group_analysis(config, progress_callback)

        # Final progress update
        elapsed_total = time.time() - start_time
        try:
            progress_bar.progress(1.0, text="100% - Analysis complete!")
            status_container.caption(f"Completed in {_format_duration(elapsed_total)}")
        except Exception:
            pass  # Ignore UI errors

        # Store results in session state for persistence
        st.session_state.group_analysis_results = {
            "results": results,
            "missing": missing,
            "excluded": excluded,
            "config": config,
        }

        show_toast(
            f"Analysis complete: {len(results)} participant-section results",
            icon="success",
        )

    # -------------------------------------------------------------------------
    # Display Results
    # -------------------------------------------------------------------------
    if "group_analysis_results" not in st.session_state:
        return

    stored = st.session_state.group_analysis_results
    results = stored["results"]
    missing = stored["missing"]
    excluded = stored["excluded"]
    config = stored["config"]

    if not results:
        st.warning("No results available. Check the missing sections report below.")
        # Show missing info
        if missing or excluded:
            with st.expander("**Missing / Excluded Participants**", expanded=True):
                if excluded:
                    st.markdown("**Excluded (completeness filter):**")
                    for pid, reason in excluded.items():
                        st.write(f"- `{pid}`: {reason}")
                if missing:
                    st.markdown("**Missing data:**")
                    for pid, sections in missing.items():
                        section_list = ", ".join(
                            f"{s}: {r}" for s, r in sections.items()
                        )
                        st.write(f"- `{pid}`: {section_list}")
        return

    # Summary
    st.markdown("---")
    st.markdown("### Results Summary")

    # Build participant count matrix (group x section)
    count_data = {}
    for r in results:
        key = (r.group, r.section_name)
        if key not in count_data:
            count_data[key] = set()
        count_data[key].add(r.participant_id)

    # Get unique groups and sections
    all_groups = sorted(set(r.group for r in results))
    all_result_sections = sorted(set(r.section_name for r in results))

    # Create count matrix
    count_matrix = []
    for group in all_groups:
        row = {"Group": group}
        group_total = set()
        for section in all_result_sections:
            participants = count_data.get((group, section), set())
            row[section] = len(participants)
            group_total.update(participants)
        row["Total Participants"] = len(group_total)
        count_matrix.append(row)

    # Add totals row
    totals_row = {"Group": "**TOTAL**"}
    for section in all_result_sections:
        totals_row[section] = sum(row[section] for row in count_matrix)
    totals_row["Total Participants"] = len(set(r.participant_id for r in results))
    count_matrix.append(totals_row)

    count_df = pd.DataFrame(count_matrix)

    # Display summary metrics
    n_participants = len(set(r.participant_id for r in results))
    n_groups = len(all_groups)
    n_sections = len(all_result_sections)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Participants", n_participants)
    with col2:
        st.metric("Groups", n_groups)
    with col3:
        st.metric("Sections", n_sections)
    with col4:
        st.metric("Data Points", len(results))

    # Data source breakdown
    nn_count = sum(1 for r in results if r.data_source == "NN")
    raw_count = sum(1 for r in results if r.data_source == "Raw")
    if raw_count > 0:
        st.info(
            f"Data sources: **{nn_count} NN** (artifact-corrected) | **{raw_count} Raw** (uncorrected)"
        )

    # Participant count table
    st.markdown("**Participants Analyzed per Group & Section:**")
    st.dataframe(
        count_df,
        use_container_width=True,
        hide_index=True,
    )

    # Create visualization of counts
    if n_groups > 0 and n_sections > 0:
        go, _ = get_plotly_analysis()
        if go is not None:
            # Create grouped bar chart showing participant counts
            theme = get_theme_colors()
            colors = [
                "#2E86AB",
                "#A23B72",
                "#F18F01",
                "#C73E1D",
                "#6C757D",
                "#28A745",
                "#17A2B8",
                "#FFC107",
            ]

            fig = go.Figure()

            for i, section in enumerate(all_result_sections):
                counts = [
                    count_data.get((group, section), set()) for group in all_groups
                ]
                counts = [len(c) for c in counts]

                fig.add_trace(
                    go.Bar(
                        name=section,
                        x=all_groups,
                        y=counts,
                        marker_color=colors[i % len(colors)],
                        text=counts,
                        textposition="auto",
                    )
                )

            fig.update_layout(
                title=dict(
                    text="Participant Count by Group and Section",
                    font=dict(size=16),
                ),
                xaxis_title="Group",
                yaxis_title="Number of Participants",
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
                height=350,
            )

            fig.update_xaxes(gridcolor=theme["grid"])
            fig.update_yaxes(gridcolor=theme["grid"])

            st.plotly_chart(fig, use_container_width=True)

    # Missing sections (collapsible) - with actionable feedback
    if missing or excluded:
        with st.expander(
            f"**Missing / Excluded ({len(missing) + len(excluded)} participants)**",
            expanded=False,
        ):
            if excluded:
                st.markdown("### Excluded (completeness filter)")
                st.caption(
                    "These participants were excluded because they don't have all selected sections."
                )
                for pid, reason in excluded.items():
                    st.write(f"- `{pid}`: {reason}")
                st.info(
                    "**Fix:** Uncheck 'Only complete participants' to include partial data, or validate the missing sections in the Sections tab."
                )

            if missing:
                st.markdown("### Missing Data")
                st.caption(
                    "These sections could not be analyzed. Common reasons and fixes:"
                )

                # Categorize missing issues
                no_rrational = {}
                no_nn_data = {}
                no_validation = {}
                too_few_beats = {}
                other_issues = {}

                for pid, sections in missing.items():
                    for section, reason in sections.items():
                        reason_lower = reason.lower() if isinstance(reason, str) else ""
                        key = (pid, section)
                        if (
                            "no .rrational" in reason_lower
                            or "rrational v2 file" in reason_lower
                        ):
                            no_rrational[key] = reason
                        elif (
                            "not found in file" in reason_lower
                            or "not in .rrational" in reason_lower
                        ):
                            no_validation[key] = reason
                        elif (
                            "no validation" in reason_lower
                            or "no validation timestamps" in reason_lower
                            or "missing start/end" in reason_lower
                        ):
                            no_validation[key] = reason
                        elif "no nn" in reason_lower or "nn intervals" in reason_lower:
                            no_nn_data[key] = reason
                        elif (
                            "too few" in reason_lower
                            or "< 100" in reason_lower
                            or "insufficient" in reason_lower
                        ):
                            too_few_beats[key] = reason
                        elif (
                            "no rr data" in reason_lower
                            or "no rr intervals" in reason_lower
                        ):
                            no_nn_data[key] = reason
                        else:
                            other_issues[key] = reason

                if no_rrational:
                    st.markdown("**No .rrational file found:**")
                    for (pid, section), reason in no_rrational.items():
                        st.write(f"  - `{pid}` / {section}")
                    st.info(
                        "**Fix:** Process this participant in the Data tab first, then validate sections."
                    )

                if no_validation:
                    st.markdown("**Section not validated:**")
                    for (pid, section), reason in no_validation.items():
                        st.write(f"  - `{pid}` / {section}")
                    st.info(
                        "**Fix:** Go to Sections tab, select participant, validate section boundaries."
                    )

                if no_nn_data:
                    st.markdown("**No NN intervals saved:**")
                    for (pid, section), reason in no_nn_data.items():
                        st.write(f"  - `{pid}` / {section}")
                    if config.get("allow_raw_fallback"):
                        st.info(
                            "Raw fallback is enabled but these sections still couldn't be loaded. Check if the section has been validated and saved."
                        )
                    else:
                        st.info(
                            "**Fix:** Go to **Analysis tab → Single Participant**, select each missing participant, "
                            "run the analysis for the relevant sections, and click **Export for Analysis**. "
                            "This saves corrected NN intervals to the .rrational file."
                        )

                if too_few_beats:
                    st.markdown("**Too few beats (< 100):**")
                    for (pid, section), reason in too_few_beats.items():
                        st.write(f"  - `{pid}` / {section}")
                    st.info(
                        "**Note:** Sections with < 100 beats cannot produce reliable HRV metrics. Consider using longer recording segments."
                    )

                if other_issues:
                    st.markdown("**Other issues:**")
                    for (pid, section), reason in other_issues.items():
                        st.write(f"  - `{pid}` / {section}: {reason}")

    # Convert to DataFrames
    long_df = _results_to_long_df(results)
    wide_df = _results_to_wide_df(results)
    stats_df = _calculate_group_stats(long_df)

    # Tabs for different views
    tab_data, tab_stats, tab_chart = st.tabs(
        ["**Data**", "**Statistics**", "**Chart**"]
    )

    with tab_data:
        # Format toggle
        format_choice = st.radio(
            "Data format",
            options=["Long (one row per section)", "Wide (one row per participant)"],
            horizontal=True,
            key="group_analysis_format",
        )

        if "Long" in format_choice:
            st.dataframe(long_df, use_container_width=True, height=400)
            csv_data = long_df.to_csv(index=False)
            filename = "hrv_group_results_long.csv"
        else:
            st.dataframe(wide_df, use_container_width=True, height=400)
            csv_data = wide_df.to_csv(index=False)
            filename = "hrv_group_results_wide.csv"

        st.download_button(
            label="Download CSV",
            data=csv_data,
            file_name=filename,
            mime="text/csv",
            key="download_group_data",
        )

    with tab_stats:
        st.markdown("**Descriptive Statistics by Group and Section**")
        st.dataframe(stats_df, use_container_width=True, height=400)

        stats_csv = stats_df.to_csv(index=False)
        st.download_button(
            label="Download Statistics CSV",
            data=stats_csv,
            file_name="hrv_group_statistics.csv",
            mime="text/csv",
            key="download_group_stats",
        )

        # Hypothesis Testing
        st.divider()
        _render_hypothesis_tests(long_df)

        # HTML Report download
        st.divider()
        if st.button("Generate HTML Report", key="gen_group_html_report"):
            from rrational import __version__

            ts = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

            html_tables = stats_df.to_html(
                index=False, classes="styled-table", border=0
            )
            data_table = long_df.to_html(index=False, classes="styled-table", border=0)

            html_report = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>HRV Group Analysis Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         max-width: 1000px; margin: 40px auto; padding: 0 20px; color: #333; line-height: 1.6; }}
  h1 {{ color: #2E86AB; border-bottom: 2px solid #2E86AB; padding-bottom: 8px; }}
  h2 {{ color: #444; margin-top: 30px; }}
  .styled-table {{ border-collapse: collapse; width: 100%; margin: 15px 0; font-size: 0.9em; }}
  .styled-table th, .styled-table td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
  .styled-table th {{ background: #f5f5f5; font-weight: 600; }}
  .styled-table tr:nth-child(even) {{ background: #fafafa; }}
  .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
  .summary-card {{ background: #f8f9fa; border-radius: 8px; padding: 15px 20px; text-align: center; flex: 1; }}
  .summary-card .value {{ font-size: 1.8em; font-weight: 700; color: #2E86AB; }}
  .summary-card .label {{ font-size: 0.85em; color: #666; }}
  @media print {{ body {{ max-width: none; }} }}
</style>
</head>
<body>
<h1>HRV Group Analysis Report</h1>
<p><b>Generated:</b> {ts} | <b>Software:</b> RRational v{__version__}</p>

<div class="summary">
  <div class="summary-card"><div class="value">{n_participants}</div><div class="label">Participants</div></div>
  <div class="summary-card"><div class="value">{n_groups}</div><div class="label">Groups</div></div>
  <div class="summary-card"><div class="value">{n_sections}</div><div class="label">Sections</div></div>
  <div class="summary-card"><div class="value">{len(results)}</div><div class="label">Data Points</div></div>
</div>

<h2>Descriptive Statistics</h2>
{html_tables}

<h2>Individual Results</h2>
{data_table}

<footer style="margin-top:40px;padding-top:10px;border-top:1px solid #ddd;color:#888;font-size:0.85em">
Generated by RRational v{__version__}
</footer>
</body>
</html>"""

            st.download_button(
                label="Download HTML Report",
                data=html_report,
                file_name=f"hrv_group_report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.html",
                mime="text/html",
                key="download_group_html",
            )

    with tab_chart:
        # Visualization type selector
        viz_type = st.radio(
            "Visualization type",
            options=[
                "Bar Chart",
                "Box Plot",
                "Violin Plot",
                "Raincloud Plot",
                "SD1/SD2 Scatter",
            ],
            horizontal=True,
            key="group_analysis_viz_type",
        )

        # Build available metrics from actual data columns
        available_metrics = []
        for col in long_df.columns:
            col_upper = col.upper()
            if col_upper in ALL_HRV_METRICS and long_df[col].notna().any():
                available_metrics.append(col_upper)

        # Ensure basic metrics are first
        priority_order = [
            "RMSSD",
            "SDNN",
            "PNN50",
            "MEANNN",
            "MEANHR",
            "LF",
            "HF",
            "LF_HF",
            "SD1",
            "SD2",
        ]
        available_metrics = sorted(
            available_metrics,
            key=lambda x: priority_order.index(x) if x in priority_order else 100,
        )

        if viz_type == "SD1/SD2 Scatter":
            # Special handling for SD1/SD2 scatter
            if "sd1" in long_df.columns and "sd2" in long_df.columns:
                color_by = st.radio(
                    "Color by",
                    options=["group", "section"],
                    horizontal=True,
                    key="group_analysis_scatter_color",
                )

                fig = _create_sd1_sd2_scatter(long_df, color_by=color_by)
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info(
                        "No SD1/SD2 data available. Select 'Poincaré Focus' or 'Full' preset to include these metrics."
                    )
            else:
                st.info(
                    "SD1 and SD2 metrics not available. Run analysis with 'Poincaré Focus' or 'Full (with nonlinear)' preset."
                )
        else:
            # Metric selector for other charts
            if not available_metrics:
                st.warning("No metrics available in the results.")
            else:
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    selected_chart_metric = st.selectbox(
                        "Select metric to visualize",
                        options=available_metrics,
                        key="group_analysis_chart_metric",
                    )
                with col2:
                    error_bar_type = st.selectbox(
                        "Error bars",
                        options=["SEM", "SD", "CI95", "None"],
                        index=0,
                        key="group_analysis_error_bar_type",
                        help=(
                            "SEM (Standard Error of Mean) = SD/√n — recommended "
                            "for comparing group means. SD shows sample spread. "
                            "CI95 = 95% confidence interval around the mean."
                        ),
                    )

                # Section filter
                all_sections = sorted(long_df["section"].unique().tolist())
                chart_sections = st.multiselect(
                    "Sections to include",
                    options=all_sections,
                    default=all_sections,
                    key="group_analysis_chart_sections",
                )

                if not chart_sections:
                    st.info("Select at least one section to display the chart.")
                else:
                    # Filter data for selected sections
                    filtered_df = long_df[long_df["section"].isin(chart_sections)]

                    if viz_type == "Bar Chart":
                        fig = _create_group_bar_chart(
                            stats_df,
                            selected_chart_metric,
                            chart_sections,
                            error_bar_type=error_bar_type,
                        )
                    elif viz_type == "Box Plot":
                        fig = _create_box_violin_plot(
                            filtered_df,
                            selected_chart_metric,
                            plot_type="box",
                            group_by="group",
                            color_by="section",
                        )
                    elif viz_type == "Violin Plot":
                        fig = _create_box_violin_plot(
                            filtered_df,
                            selected_chart_metric,
                            plot_type="violin",
                            group_by="group",
                            color_by="section",
                        )
                    elif viz_type == "Raincloud Plot":
                        fig = _create_raincloud_plot(
                            filtered_df,
                            selected_chart_metric,
                            group_by="group",
                            color_by="section",
                        )
                    else:
                        fig = None

                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info(
                            f"No data available for {selected_chart_metric} in selected sections."
                        )


def _get_condition_display_name(condition_id: str, condition_labels: dict) -> str:
    """Get display name for a condition, handling dict-style label values."""
    label = condition_labels.get(condition_id, condition_id)
    if isinstance(label, dict):
        return label.get("description", label.get("label", condition_id))
    return str(label)


def _render_sequence_comparison():
    """Render Event Sequence Group Comparison analysis.

    Compares HRV metrics across event sequences, grouping participants by their
    assigned sequence and analyzing per-condition differences.
    """
    with st.expander("**Sequence Comparison Overview**", expanded=False):
        st.markdown("""
**Overview:**
Compare HRV metrics between participants assigned to different event sequences.
Each sequence defines a condition order (e.g., A-B-A-B vs B-A-B-A).
This analysis groups participants by sequence and compares conditions within and across sequences.

**Requirements:**
- Event sequences defined in Setup > Sequences
- Participants assigned to sequences
- Sections validated for each participant
- `.rrational` v2 files exported (from the Participants tab)

**Use case:** Counterbalanced designs where condition order might affect HRV.
        """)

    # Check prerequisites
    event_sequences = st.session_state.get("event_sequences", {})
    if not event_sequences:
        st.warning(
            "No event sequences defined. Go to Setup > Sequences to create them."
        )
        return

    participant_sequences = st.session_state.get("participant_sequences", {})
    if not participant_sequences:
        st.warning(
            "No participants assigned to sequences. Assign participants in the Participants tab."
        )
        return

    condition_labels = st.session_state.get("condition_labels", {})

    # -------------------------------------------------------------------------
    # Step 1: Select Sequences
    # -------------------------------------------------------------------------
    st.markdown("### Step 1: Select Sequences")

    # Count participants per sequence
    seq_counts = {}
    for seq_id in event_sequences:
        count = sum(1 for s in participant_sequences.values() if s == seq_id)
        seq_counts[seq_id] = count

    seq_options = [f"{sid} ({seq_counts[sid]} participants)" for sid in event_sequences]
    seq_map = {
        f"{sid} ({seq_counts[sid]} participants)": sid for sid in event_sequences
    }

    selected_seq_labels = st.multiselect(
        "Select sequences to compare",
        options=seq_options,
        default=seq_options,
        key="seq_comparison_sequences",
    )
    selected_sequences = [seq_map[label] for label in selected_seq_labels]

    if not selected_sequences:
        st.info("Please select at least one sequence.")
        return

    # Optional: Filter by groups
    group_list = list(st.session_state.get("groups", {}).keys())
    selected_groups = None
    if group_list:
        with st.expander("**Filter by Group** (optional)", expanded=False):
            st.caption(
                "Compare conditions across groups — e.g., how does RMSSD during 'Music' differ between Group A and Group B?"
            )
            use_group_filter = st.checkbox(
                "Include group in comparison",
                value=False,
                key="seq_comparison_use_groups",
            )
            if use_group_filter:
                group_counts = {}
                for g in group_list:
                    group_counts[g] = sum(
                        1
                        for pg in st.session_state.get(
                            "participant_groups", {}
                        ).values()
                        if pg == g
                    )
                group_options = [f"{g} ({group_counts[g]})" for g in group_list]
                g_map = {f"{g} ({group_counts[g]})": g for g in group_list}
                selected_group_labels = st.multiselect(
                    "Select groups",
                    options=group_options,
                    default=group_options,
                    key="seq_comparison_groups",
                )
                selected_groups = [g_map[l] for l in selected_group_labels]
                if not selected_groups:
                    st.info("Select at least one group.")
                    return

    # -------------------------------------------------------------------------
    # Step 2: Select Conditions
    # -------------------------------------------------------------------------
    st.markdown("### Step 2: Select Conditions")

    # Collect all unique conditions across selected sequences
    all_conditions = set()
    for seq_id in selected_sequences:
        seq_data = event_sequences.get(seq_id, {})
        condition_order = seq_data.get("condition_order", [])
        # Ensure we only get string condition names (skip dicts/nested data)
        for c in condition_order:
            if isinstance(c, str):
                all_conditions.add(c)

    all_conditions = sorted(all_conditions)
    if not all_conditions:
        st.warning("Selected sequences have no conditions defined.")
        return

    # Show condition labels
    condition_display = []
    for cond in all_conditions:
        label = condition_labels.get(cond, cond)
        condition_display.append(f"{label}" if label != cond else cond)

    selected_conditions = st.multiselect(
        "Select conditions to analyze",
        options=all_conditions,
        default=all_conditions,
        format_func=lambda c: _get_condition_display_name(c, condition_labels),
        key="seq_comparison_conditions",
    )

    if not selected_conditions:
        st.info("Please select at least one condition.")
        return

    # -------------------------------------------------------------------------
    # Step 3: Analysis Options
    # -------------------------------------------------------------------------
    st.markdown("### Step 3: Analysis Options")

    st.markdown("**HRV Metrics**")
    preset_names = list(HRV_METRIC_PRESETS.keys())
    preset_col1, preset_col2 = st.columns([1, 2])

    with preset_col1:
        selected_preset = st.selectbox(
            "Metric preset",
            options=preset_names,
            index=1,
            key="seq_comparison_metric_preset",
        )

    with preset_col2:
        st.caption(HRV_METRIC_PRESETS[selected_preset]["description"])

    if selected_preset == "Custom":
        selected_metrics = []
        metric_cols = st.columns(4)
        categories = [
            ("Time (Basic)", "time_basic"),
            ("Time (Extended)", "time_extended"),
            ("Frequency", "frequency"),
            ("Nonlinear", "nonlinear"),
        ]
        for i, (cat_label, cat_key) in enumerate(categories):
            with metric_cols[i]:
                st.markdown(f"*{cat_label}*")
                for metric_name in HRV_METRICS_CATALOG[cat_key].keys():
                    metric_info = HRV_METRICS_CATALOG[cat_key][metric_name]
                    if st.checkbox(
                        metric_info["label"],
                        value=metric_name in ["RMSSD", "SDNN", "MeanHR"],
                        key=f"seq_metric_{metric_name}",
                    ):
                        selected_metrics.append(metric_name)
    else:
        selected_metrics = HRV_METRIC_PRESETS[selected_preset]["metrics"]

    if not selected_metrics:
        st.warning("Please select at least one metric.")
        return

    st.caption(
        f"**Selected:** {', '.join(selected_metrics[:8])}{'...' if len(selected_metrics) > 8 else ''}"
    )

    st.markdown("**Analysis Settings**")
    col1, col2 = st.columns(2)
    with col1:
        use_overlapping = st.checkbox(
            "Use overlapping windows",
            value=True,
            key="seq_comparison_overlapping",
        )
    with col2:
        allow_raw_fallback = st.checkbox(
            "Allow raw data fallback",
            value=False,
            key="seq_comparison_raw_fallback",
            help="When NN intervals are unavailable, use raw (uncorrected) RR data. "
            "Recommended: OFF — prepare each participant with 'Export for Analysis' first.",
        )

    if use_overlapping:
        col1, col2 = st.columns(2)
        with col1:
            window_beats = st.number_input(
                "Window size (beats)",
                min_value=100,
                max_value=1000,
                value=300,
                step=50,
                key="seq_comparison_window_beats",
            )
        with col2:
            overlap_pct = st.slider(
                "Overlap (%)",
                min_value=0,
                max_value=90,
                value=75,
                step=5,
                key="seq_comparison_overlap",
            )
    else:
        window_beats = 300
        overlap_pct = 75

    # -------------------------------------------------------------------------
    # Run Analysis
    # -------------------------------------------------------------------------
    st.divider()

    if st.button(
        "**Compare Sequences**",
        key="run_seq_comparison_btn",
        type="primary",
        use_container_width=True,
    ):
        import time as _time

        project_path = st.session_state.get("project_path")
        data_dir = st.session_state.get("data_dir")
        results = []
        missing = {}

        # Collect participants per sequence (optionally filtered by group)
        participant_groups = st.session_state.get("participant_groups", {})
        seq_participants = {}
        for seq_id in selected_sequences:
            pids = [pid for pid, s in participant_sequences.items() if s == seq_id]
            if selected_groups:
                pids = [
                    pid
                    for pid in pids
                    if participant_groups.get(pid) in selected_groups
                ]
            seq_participants[seq_id] = pids

        total_work = sum(
            len(pids) * len(selected_conditions) for pids in seq_participants.values()
        )
        current_work = [0]

        progress_bar = st.progress(0, text="Starting sequence comparison...")
        status_container = st.empty()
        start_time = _time.time()

        for seq_id in selected_sequences:
            seq_data = event_sequences.get(seq_id, {})
            pids = seq_participants.get(seq_id, [])

            for pid in pids:
                # Find .rrational file
                rrational_path = _find_rrational_v2_file(
                    pid, project_path=project_path, data_dir=data_dir
                )
                if not rrational_path:
                    missing[pid] = "No .rrational v2 file"
                    current_work[0] += len(selected_conditions)
                    continue

                # For each selected condition, try to load section data
                for condition in selected_conditions:
                    current_work[0] += 1
                    pct = min(current_work[0] / max(total_work, 1), 1.0)
                    cond_label = _get_condition_display_name(
                        condition, condition_labels
                    )
                    progress_bar.progress(
                        pct, text=f"{int(pct * 100)}% - [{pid}] {cond_label}"
                    )

                    # Try loading condition-specific section (section name = condition label or condition id)
                    section_name = cond_label if cond_label != condition else condition
                    nn_data, info = _load_nn_from_rrational_v2(
                        rrational_path, section_name
                    )

                    # Also try with condition id directly
                    if not nn_data or len(nn_data) < MIN_BEATS_TIME_DOMAIN:
                        nn_data, info = _load_nn_from_rrational_v2(
                            rrational_path, condition
                        )

                    if not nn_data or len(nn_data) < MIN_BEATS_TIME_DOMAIN:
                        if allow_raw_fallback:
                            raw_data, raw_info = _load_raw_section_data(
                                pid,
                                section_name,
                                rrational_path,
                                project_path,
                                data_dir,
                            )
                            if not raw_data or len(raw_data) < MIN_BEATS_TIME_DOMAIN:
                                raw_data, raw_info = _load_raw_section_data(
                                    pid,
                                    condition,
                                    rrational_path,
                                    project_path,
                                    data_dir,
                                )
                            if raw_data and len(raw_data) >= MIN_BEATS_TIME_DOMAIN:
                                nn_data = raw_data
                                info = raw_info or {}
                                info["data_source"] = "Raw"

                    if not nn_data or len(nn_data) < MIN_BEATS_TIME_DOMAIN:
                        missing.setdefault(pid, {})[condition] = info.get(
                            "error", "Insufficient data"
                        )
                        continue

                    # Calculate HRV
                    metrics, std, n_win = _calculate_hrv_metrics(
                        nn_data,
                        use_overlapping,
                        window_beats,
                        overlap_pct,
                        selected_metrics=selected_metrics,
                    )

                    seq_label = seq_data.get("label", seq_id)
                    # When group filter is active, include group in the label
                    if selected_groups:
                        pid_group = participant_groups.get(pid, "unknown")
                        group_label = f"{seq_label} / {pid_group}"
                    else:
                        group_label = seq_label
                    results.append(
                        ParticipantSectionResult(
                            participant_id=pid,
                            group=group_label,  # Sequence (+ group) as "group" for reuse
                            section_name=cond_label,  # Condition as "section" for reuse
                            n_beats=info.get("n_beats", len(nn_data)),
                            duration_s=info.get("duration_s", sum(nn_data) / 1000),
                            quality_grade=info.get("quality_grade", "unknown"),
                            artifact_rate=info.get("artifact_rate", 0.0),
                            hrv_metrics=metrics,
                            hrv_std=std,
                            n_windows=n_win,
                            data_source=info.get("data_source", "NN"),
                        )
                    )

        elapsed = _time.time() - start_time
        progress_bar.progress(1.0, text="100% - Complete!")
        status_container.caption(f"Completed in {_format_duration(elapsed)}")

        st.session_state.seq_comparison_results = {
            "results": results,
            "missing": missing,
        }

        show_toast(
            f"Sequence comparison complete: {len(results)} results", icon="success"
        )

    # -------------------------------------------------------------------------
    # Display Results
    # -------------------------------------------------------------------------
    if "seq_comparison_results" not in st.session_state:
        return

    stored = st.session_state.seq_comparison_results
    results = stored["results"]
    missing = stored["missing"]

    if not results:
        st.warning(
            "No results. Check prerequisites: .rrational files exported, sections validated, conditions matching section names."
        )
        if missing:
            with st.expander("**Missing Data Details**", expanded=True):
                for pid, info in missing.items():
                    if isinstance(info, dict):
                        for section, reason in info.items():
                            st.write(f"- `{pid}` / {section}: {reason}")
                    else:
                        st.write(f"- `{pid}`: {info}")
        return

    # Summary
    st.markdown("---")
    st.markdown("### Results")

    n_participants = len(set(r.participant_id for r in results))
    n_sequences = len(set(r.group for r in results))
    n_conditions = len(set(r.section_name for r in results))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Participants", n_participants)
    with col2:
        st.metric("Sequences", n_sequences)
    with col3:
        st.metric("Conditions", n_conditions)
    with col4:
        st.metric("Data Points", len(results))

    # Convert to DataFrames (reuse existing functions)
    long_df = _results_to_long_df(results)
    stats_df = _calculate_group_stats(long_df)

    # Rename columns for clarity
    long_df = long_df.rename(columns={"group": "sequence", "section": "condition"})
    stats_df = stats_df.rename(columns={"group": "sequence", "section": "condition"})

    # Missing data
    if missing:
        with st.expander(
            f"**Missing Data ({len(missing)} participants)**", expanded=False
        ):
            for pid, info in missing.items():
                if isinstance(info, dict):
                    for section, reason in info.items():
                        st.write(f"- `{pid}` / {section}: {reason}")
                else:
                    st.write(f"- `{pid}`: {info}")

    # Tabs for results
    tab_data, tab_stats, tab_chart = st.tabs(
        ["**Data**", "**Statistics**", "**Chart**"]
    )

    with tab_data:
        st.dataframe(long_df, use_container_width=True, height=400)
        csv_data = long_df.to_csv(index=False)
        st.download_button(
            label="Download CSV",
            data=csv_data,
            file_name="hrv_sequence_comparison.csv",
            mime="text/csv",
            key="download_seq_data",
        )

    with tab_stats:
        st.markdown("**Descriptive Statistics by Sequence and Condition**")
        st.dataframe(stats_df, use_container_width=True, height=400)
        stats_csv = stats_df.to_csv(index=False)
        st.download_button(
            label="Download Statistics CSV",
            data=stats_csv,
            file_name="hrv_sequence_statistics.csv",
            mime="text/csv",
            key="download_seq_stats",
        )

    with tab_chart:
        # Rename back for plot compatibility (group_plots expects "group" and "section")
        plot_df = long_df.rename(columns={"sequence": "group", "condition": "section"})

        viz_type = st.radio(
            "Visualization type",
            options=[
                "Bar Chart",
                "Box Plot",
                "Violin Plot",
                "Raincloud Plot",
                "SD1/SD2 Scatter",
            ],
            horizontal=True,
            key="seq_comparison_viz_type",
        )

        available_metrics = []
        for col in plot_df.columns:
            col_upper = col.upper()
            if col_upper in ALL_HRV_METRICS and plot_df[col].notna().any():
                available_metrics.append(col_upper)

        priority_order = [
            "RMSSD",
            "SDNN",
            "PNN50",
            "MEANNN",
            "MEANHR",
            "LF",
            "HF",
            "LF_HF",
            "SD1",
            "SD2",
        ]
        available_metrics = sorted(
            available_metrics,
            key=lambda x: priority_order.index(x) if x in priority_order else 100,
        )

        if viz_type == "SD1/SD2 Scatter":
            if "sd1" in plot_df.columns and "sd2" in plot_df.columns:
                fig = _create_sd1_sd2_scatter(plot_df, color_by="group")
                if fig:
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info(
                    "SD1/SD2 metrics not available. Use a preset that includes nonlinear metrics."
                )
        elif available_metrics:
            selected_chart_metric = st.selectbox(
                "Select metric",
                options=available_metrics,
                format_func=lambda m: f"{m} ({get_metric_info(m).get('unit', '')})"
                if get_metric_info(m)
                else m,
                key="seq_comparison_chart_metric",
            )

            # Filter DataFrame
            metric_col = selected_chart_metric.lower()
            if metric_col in plot_df.columns:
                filtered_df = plot_df[plot_df[metric_col].notna()].copy()

                if viz_type == "Bar Chart":
                    # Recompute stats for the plot df
                    plot_stats = _calculate_group_stats(plot_df)
                    fig = _create_group_bar_chart(plot_stats, selected_chart_metric)
                elif viz_type == "Box Plot":
                    fig = _create_box_violin_plot(
                        filtered_df, selected_chart_metric, plot_type="box"
                    )
                elif viz_type == "Violin Plot":
                    fig = _create_box_violin_plot(
                        filtered_df, selected_chart_metric, plot_type="violin"
                    )
                elif viz_type == "Raincloud Plot":
                    fig = _create_raincloud_plot(
                        filtered_df,
                        selected_chart_metric,
                        group_by="group",
                        color_by="section",
                    )
                else:
                    fig = None

                if fig:
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info(f"No data for {selected_chart_metric}.")
        else:
            st.warning("No metrics available.")
