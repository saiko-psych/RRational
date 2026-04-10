"""Tests for color scheme system."""

from rrational.gui.color_scheme import ColorScheme, PRESET_THEMES, get_preset_names


class TestColorScheme:
    def test_default_scheme_has_all_fields(self):
        scheme = ColorScheme()
        assert scheme.rr_line
        assert scheme.artifact
        assert scheme.event_marker
        assert scheme.section_fill
        assert scheme.nn_line
        assert scheme.exclusion
        assert len(scheme.group_palette) >= 6

    def test_preset_themes_exist(self):
        names = get_preset_names()
        assert "Scientific" in names
        assert "Colorful" in names
        assert "High Contrast" in names
        assert "Monochrome" in names
        assert "Pastel" in names

    def test_preset_returns_color_scheme(self):
        for name, scheme in PRESET_THEMES.items():
            assert isinstance(scheme, ColorScheme), f"{name} is not a ColorScheme"
            assert scheme.rr_line != "", f"{name} has empty rr_line"

    def test_dark_variant(self):
        scheme = ColorScheme()
        dark = scheme.dark_variant()
        # Dark variant should lighten colors for visibility on dark bg
        assert dark.rr_line != scheme.rr_line
        assert dark.nn_line != scheme.nn_line

    def test_to_dict_roundtrip(self):
        scheme = ColorScheme()
        d = scheme.to_dict()
        restored = ColorScheme.from_dict(d)
        assert restored.rr_line == scheme.rr_line
        assert restored.artifact == scheme.artifact
        assert restored.group_palette == scheme.group_palette
        assert restored.lf_band == scheme.lf_band

    def test_from_dict_partial(self):
        """Missing keys should use defaults."""
        partial = {"rr_line": "#FF0000"}
        scheme = ColorScheme.from_dict(partial)
        assert scheme.rr_line == "#FF0000"
        assert scheme.artifact == ColorScheme().artifact

    def test_from_dict_legacy_line_key(self):
        """Old 'line' key should map to rr_line for backward compat."""
        legacy = {"line": "#123456"}
        scheme = ColorScheme.from_dict(legacy)
        assert scheme.rr_line == "#123456"

    def test_lighten_produces_valid_hex(self):
        from rrational.gui.color_scheme import _lighten

        result = _lighten("#000000", 40)
        assert result.startswith("#")
        assert len(result) == 7

    def test_lighten_clamps_to_255(self):
        from rrational.gui.color_scheme import _lighten

        result = _lighten("#FFFFFF", 40)
        assert result == "#ffffff"

    def test_all_presets_have_valid_palettes(self):
        for name, scheme in PRESET_THEMES.items():
            assert len(scheme.group_palette) >= 6, f"{name} palette too short"
            for color in scheme.group_palette:
                assert color.startswith("#"), (
                    f"{name} has invalid palette color: {color}"
                )
