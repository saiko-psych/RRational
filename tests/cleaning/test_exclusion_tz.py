"""Regression test for tz symmetry in filter_exclusion_zones.

Round 30 fix: exclusion-zone comparison must be SYMMETRIC across timezones.
The old code stripped ``tzinfo`` from both the beat timestamp and the zone
bounds *without* converting to a common frame first, so a UTC beat compared
against a zone expressed in a different offset (e.g. +02:00) silently shifted
by that offset and excluded the wrong beats (or none at all).

These tests build tz-AWARE UTC beats and an exclusion zone expressed in a
+02:00 offset. After correct UTC normalization exactly one beat falls inside
the window; under the old asymmetric strip zero beats would match.
"""

from datetime import datetime, timedelta, timezone

from rrational.cleaning.quality import filter_exclusion_zones
from rrational.io.hrv_logger import RRInterval

_UTC = timezone.utc
_PLUS2 = timezone(timedelta(hours=2))


def build_utc_beats():
    """Three beats 30s apart, all tz-aware UTC on 2024-06-01."""
    return [
        RRInterval(
            timestamp=datetime(2024, 6, 1, 10, 0, 0, tzinfo=_UTC),
            rr_ms=800,
            elapsed_ms=0,
        ),
        RRInterval(
            timestamp=datetime(2024, 6, 1, 10, 0, 30, tzinfo=_UTC),
            rr_ms=810,
            elapsed_ms=800,
        ),
        RRInterval(
            timestamp=datetime(2024, 6, 1, 10, 1, 0, tzinfo=_UTC),
            rr_ms=820,
            elapsed_ms=1610,
        ),
    ]


def test_exclusion_zone_in_different_tz_offset_excludes_correct_beat():
    """A +02:00 zone must be UTC-converted before comparison, not just stripped.

    Zone 12:00:15..12:00:45 +02:00 == 10:00:15..10:00:45 UTC, which straddles
    only the middle beat (10:00:30 UTC). The first/last beats sit outside.

    Under the old asymmetric strip the naive zone (12:00:15..12:00:45) never
    overlapped the naive beats (10:00:00..10:01:00), so n_excluded would be 0
    and this assertion would FAIL.
    """
    beats = build_utc_beats()
    zones = [
        {
            "start": datetime(2024, 6, 1, 12, 0, 15, tzinfo=_PLUS2),
            "end": datetime(2024, 6, 1, 12, 0, 45, tzinfo=_PLUS2),
        }
    ]

    filtered, stats = filter_exclusion_zones(beats, zones)

    # Exactly the middle beat (10:00:30 UTC) is inside the converted window.
    assert stats["n_excluded"] == 1
    assert stats["n_original"] == 3
    assert stats["n_remaining"] == 2
    assert stats["excluded_duration_ms"] == 810
    assert stats["zones_applied"] == 1

    remaining_ts = [rr.timestamp for rr in filtered]
    assert datetime(2024, 6, 1, 10, 0, 30, tzinfo=_UTC) not in remaining_ts
    assert datetime(2024, 6, 1, 10, 0, 0, tzinfo=_UTC) in remaining_ts
    assert datetime(2024, 6, 1, 10, 1, 0, tzinfo=_UTC) in remaining_ts


def test_exclusion_zone_string_in_different_tz_offset():
    """Same symmetry guarantee when the zone bounds arrive as ISO strings.

    pandas parses the +02:00 offset into a tz-aware Timestamp, which must be
    converted to UTC (not merely stripped) before comparison.
    """
    beats = build_utc_beats()
    zones = [
        {
            "start": "2024-06-01T12:00:15+02:00",
            "end": "2024-06-01T12:00:45+02:00",
        }
    ]

    _filtered, stats = filter_exclusion_zones(beats, zones)

    assert stats["n_excluded"] == 1
    assert stats["n_remaining"] == 2
    assert stats["excluded_duration_ms"] == 810
