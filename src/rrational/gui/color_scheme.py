"""Color scheme definitions and preset themes.

Centralizes all plot color configuration for RRational.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def _lighten(hex_color: str, amount: int = 40) -> str:
    """Lighten a hex color for dark mode visibility."""
    hex_color = hex_color.lstrip("#")
    r = min(255, int(hex_color[:2], 16) + amount)
    g = min(255, int(hex_color[2:4], 16) + amount)
    b = min(255, int(hex_color[4:6], 16) + amount)
    return f"#{r:02x}{g:02x}{b:02x}"


@dataclass
class ColorScheme:
    """Complete color configuration for all plot elements."""

    # Core plot colors
    rr_line: str = "#2E86AB"
    artifact: str = "#FF6B6B"
    nn_line: str = "#28A745"
    exclusion: str = "#FFA500"

    # Event and section colors
    event_marker: str = "#E91E63"
    section_fill: str = "rgba(46, 134, 171, 0.1)"
    section_border: str = "#2E86AB"

    # Frequency domain
    vlf_band: str = "rgba(108, 117, 125, 0.2)"
    lf_band: str = "rgba(255, 193, 7, 0.3)"
    hf_band: str = "rgba(46, 134, 171, 0.3)"

    # Group/category palette (cycled for multiple groups)
    group_palette: list[str] = field(
        default_factory=lambda: [
            "#2E86AB",
            "#A23B72",
            "#F18F01",
            "#C73E1D",
            "#6C757D",
            "#28A745",
            "#17A2B8",
            "#FFC107",
        ]
    )

    def dark_variant(self) -> ColorScheme:
        """Return a variant with colors adjusted for dark backgrounds."""
        return ColorScheme(
            rr_line=_lighten(self.rr_line),
            artifact=_lighten(self.artifact, 30),
            nn_line=_lighten(self.nn_line),
            exclusion=_lighten(self.exclusion),
            event_marker=_lighten(self.event_marker),
            section_fill=self.section_fill.replace("0.1", "0.15"),
            section_border=_lighten(self.section_border),
            vlf_band=self.vlf_band,
            lf_band=self.lf_band,
            hf_band=self.hf_band,
            group_palette=[_lighten(c) for c in self.group_palette],
        )

    def to_dict(self) -> dict:
        """Serialize to dict for YAML persistence."""
        return {
            "rr_line": self.rr_line,
            "artifact": self.artifact,
            "nn_line": self.nn_line,
            "exclusion": self.exclusion,
            "event_marker": self.event_marker,
            "section_fill": self.section_fill,
            "section_border": self.section_border,
            "vlf_band": self.vlf_band,
            "lf_band": self.lf_band,
            "hf_band": self.hf_band,
            "group_palette": list(self.group_palette),
        }

    @classmethod
    def from_dict(cls, d: dict) -> ColorScheme:
        """Deserialize from dict, using defaults for missing keys."""
        defaults = cls()
        # Backward compat: old "line" key maps to "rr_line"
        rr_line = d.get("rr_line", d.get("line", defaults.rr_line))
        return cls(
            rr_line=rr_line,
            artifact=d.get("artifact", defaults.artifact),
            nn_line=d.get("nn_line", defaults.nn_line),
            exclusion=d.get("exclusion", defaults.exclusion),
            event_marker=d.get("event_marker", defaults.event_marker),
            section_fill=d.get("section_fill", defaults.section_fill),
            section_border=d.get("section_border", defaults.section_border),
            vlf_band=d.get("vlf_band", defaults.vlf_band),
            lf_band=d.get("lf_band", defaults.lf_band),
            hf_band=d.get("hf_band", defaults.hf_band),
            group_palette=d.get("group_palette", defaults.group_palette),
        )


PRESET_THEMES: dict[str, ColorScheme] = {
    "Scientific": ColorScheme(),
    "Colorful": ColorScheme(
        rr_line="#6366F1",
        artifact="#EF4444",
        nn_line="#10B981",
        exclusion="#F59E0B",
        event_marker="#EC4899",
        section_border="#6366F1",
        section_fill="rgba(99, 102, 241, 0.1)",
        group_palette=[
            "#6366F1",
            "#EC4899",
            "#14B8A6",
            "#F97316",
            "#8B5CF6",
            "#06B6D4",
            "#84CC16",
            "#F43F5E",
        ],
    ),
    "High Contrast": ColorScheme(
        rr_line="#0000FF",
        artifact="#FF0000",
        nn_line="#008000",
        exclusion="#FF8C00",
        event_marker="#FF00FF",
        section_border="#0000FF",
        section_fill="rgba(0, 0, 255, 0.1)",
        group_palette=[
            "#0000FF",
            "#FF0000",
            "#008000",
            "#FF8C00",
            "#800080",
            "#008080",
            "#FFD700",
            "#FF1493",
        ],
    ),
    "Monochrome": ColorScheme(
        rr_line="#333333",
        artifact="#999999",
        nn_line="#666666",
        exclusion="#AAAAAA",
        event_marker="#555555",
        section_border="#333333",
        section_fill="rgba(51, 51, 51, 0.08)",
        group_palette=[
            "#222222",
            "#444444",
            "#666666",
            "#888888",
            "#AAAAAA",
            "#CCCCCC",
        ],
    ),
    "Pastel": ColorScheme(
        rr_line="#7CB9E8",
        artifact="#F4A4A4",
        nn_line="#77DD77",
        exclusion="#FFD699",
        event_marker="#DDA0DD",
        section_border="#7CB9E8",
        section_fill="rgba(124, 185, 232, 0.1)",
        group_palette=[
            "#7CB9E8",
            "#F4A4A4",
            "#77DD77",
            "#FFD699",
            "#DDA0DD",
            "#87CEEB",
            "#98D8C8",
            "#F7DC6F",
        ],
    ),
}


def get_preset_names() -> list[str]:
    """Return sorted list of preset theme names."""
    return sorted(PRESET_THEMES.keys())
