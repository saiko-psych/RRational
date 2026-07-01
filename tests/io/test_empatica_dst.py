"""Regression test: Empatica IBI.csv start time is tz-aware UTC.

Round 30 fixed a DST-drift bug in :func:`_parse_empatica`. The header's
unix start timestamp was previously converted with a naive
``datetime.fromtimestamp(start_unix)`` — which interprets the epoch in the
machine's *local* timezone. Downstream wall-clock conversions then drifted
by the local UTC offset (and by a whole extra hour across a DST boundary).

The correct behaviour anchors the recording to UTC:
``datetime.fromtimestamp(start_unix, tz=timezone.utc)``. These tests pin
that contract so a regression to naive-local parsing fails loudly,
independent of the machine timezone the suite runs on.
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from rrational.io.generic_rr import load_generic_rr

# Header unix start (2026-04-03 02:00:00 UTC) chosen to sit shortly after the
# 2026 EU spring-forward so a naive-local parse on a European box drifts by
# two hours, not merely one — but the assertions below are machine-agnostic.
_START_UNIX = 1775181600.000000
_OFFSET_S = 7.734375
_IBI_S = 0.875000

# The instant the first beat must land on when the start is read as UTC.
_EXPECTED_FIRST_TS = datetime.fromtimestamp(_START_UNIX, tz=timezone.utc) + timedelta(
    seconds=_OFFSET_S
)


def _write_ibi(tmp_path: Path) -> Path:
    """Write a minimal Empatica E4 IBI.csv and return its path."""
    path = tmp_path / "IBI.csv"
    path.write_text(
        f"{_START_UNIX:.6f}, IBI\n{_OFFSET_S:.6f},{_IBI_S:.6f}\n",
        encoding="utf-8",
    )
    return path


class TestEmpaticaStartIsUtc:
    """The Empatica recording start must be interpreted as UTC, not local."""

    def test_first_beat_timestamp_is_tz_aware_utc(self, tmp_path):
        rec = load_generic_rr(_write_ibi(tmp_path), participant_id="EMPA_DST")

        assert rec.source_app == "empatica"
        assert len(rec.rr_intervals) == 1

        ts = rec.rr_intervals[0].timestamp
        assert ts is not None
        # Buggy naive-local parse yields tzinfo=None — fail there directly.
        assert ts.tzinfo is not None, "Empatica beat timestamp must be tz-aware"
        assert ts.utcoffset() == timedelta(0), "Empatica start must be anchored to UTC"

    def test_first_beat_matches_utc_wall_clock(self, tmp_path):
        rec = load_generic_rr(_write_ibi(tmp_path), participant_id="EMPA_DST")

        ts = rec.rr_intervals[0].timestamp
        assert ts is not None and ts.tzinfo is not None

        # Same instant as the UTC interpretation of the unix start + offset.
        assert ts == _EXPECTED_FIRST_TS
        # And the UTC wall-clock reads 02:00:07.734375 — a local parse on any
        # non-UTC machine would print a different hour here.
        assert ts.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") == (
            "2026-04-03 02:00:07"
        )

    def test_metadata_recording_start_is_utc_iso(self, tmp_path):
        rec = load_generic_rr(_write_ibi(tmp_path), participant_id="EMPA_DST")

        recording_start = rec.metadata.get("recording_start")
        assert recording_start is not None
        parsed = datetime.fromisoformat(recording_start)
        assert parsed.tzinfo is not None
        assert parsed.utcoffset() == timedelta(0)
        assert parsed == datetime.fromtimestamp(_START_UNIX, tz=timezone.utc)
