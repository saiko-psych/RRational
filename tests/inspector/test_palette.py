"""Tests for the Okabe-Ito colorblind-safe palette helper (Cluster A5)."""

from __future__ import annotations

from rrational.inspector.palette import OKABE_ITO, palette


def test_okabe_ito_has_eight_colors():
    """Reference Okabe-Ito set is exactly 8 hues."""
    assert len(OKABE_ITO) == 8


def test_okabe_ito_first_color_is_orange():
    """Canonical first colour of the Okabe-Ito sequence."""
    assert OKABE_ITO[0] == "#E69F00"


def test_palette_returns_n_colors():
    """``palette(n)`` returns exactly n colours when n <= 8."""
    assert len(palette(3)) == 3
    assert len(palette(8)) == 8


def test_palette_cycles_beyond_eight():
    """When n > 8, the palette must cycle through the 8 base colours."""
    out = palette(15)
    assert len(out) == 15
    # Element 8 must wrap back to element 0.
    assert out[8] == out[0]
    # Element 9 wraps to element 1, etc.
    assert out[9] == out[1]


def test_palette_zero_returns_empty():
    """Boundary: palette(0) returns an empty list so callers do not branch."""
    assert palette(0) == []


def test_palette_negative_returns_empty():
    """Boundary: negative n is treated as 0 (defensive guard)."""
    assert palette(-3) == []


def test_palette_returns_hex_strings():
    """Every returned colour must be a hex string starting with '#'."""
    for color in palette(8):
        assert isinstance(color, str)
        assert color.startswith("#")
        # 7 chars: '#' + RRGGBB
        assert len(color) == 7
