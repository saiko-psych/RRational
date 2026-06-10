"""Colorblind-safe palette constants for Inspector plots.

Cluster A5 — defaults to the Okabe-Ito 8-colour palette, a CUD-vetted
set distinguishable by viewers with deuteranopia, protanopia, and
tritanopia (Okabe & Ito 2002, ``https://jfly.uni-koeln.de/color/``).
The palette is used by ``ColorScheme.group_palette`` whenever the
"Colorblind-safe palette" setting is enabled in Preferences.

The colours are sequenced so adjacent indices stay visually distinct
under typical colour-vision deficiencies — orange, sky-blue, bluish
green, yellow, blue, vermillion, reddish-purple, black.

This module deliberately exposes only data + a thin helper so the
import is cheap (no Qt, no dataclass machinery) and the constant can
be referenced from tests, docs, and the analysis layer without
dragging in the inspector UI tree.
"""

from __future__ import annotations

# Order matches the Okabe-Ito reference figure. Black is last because
# it doubles as the "extra series" fallback after the first seven hues
# are exhausted.
OKABE_ITO: tuple[str, ...] = (
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#009E73",  # bluish green
    "#F0E442",  # yellow
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#CC79A7",  # reddish purple
    "#000000",  # black
)


def palette(n: int) -> list[str]:
    """Return ``n`` Okabe-Ito hex colours, cycling when ``n`` > 8.

    ``n`` is clamped to ``>= 0``; ``palette(0)`` returns an empty list
    so callers can build palettes from runtime sizes (e.g.
    ``palette(len(groups))``) without branching on emptiness.
    """
    if n <= 0:
        return []
    if n <= len(OKABE_ITO):
        return list(OKABE_ITO[:n])
    # Cycle through the palette for n > 8. Group-comparison plots rarely
    # exceed 4-5 conditions; cycling beyond 8 is a degraded mode where
    # the user should pick a custom palette anyway.
    return [OKABE_ITO[i % len(OKABE_ITO)] for i in range(n)]
