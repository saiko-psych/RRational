# -*- coding: utf-8 -*-
"""Regression tests for the cp1252 / latin-1 text-decoding fallback.

Round 28-30 hardening: every RR/event loader used to read files with
``errors="ignore"`` on UTF-8, which silently *dropped* every non-ASCII
byte.  German-market VNS Analyse exports and Windows-1252 CSVs from
Excel routinely carry umlauts in header fields (participant names, notes)
and event labels, so a name like ``Müller`` (bytes ``b"M\xfcller"``)
became ``Mller`` with no error raised.

``_read_text_with_fallback`` now tries utf-8-sig -> utf-8 -> cp1252 ->
latin-1, so the umlaut round-trips.  These tests build synthetic files
with an umlaut byte encoded as cp1252/latin-1, load them through the
*public* loader, and assert the umlaut survives.

They fail against the old ``errors="ignore"`` behaviour (which would
yield ``Mller``) and pass against the current fallback chain.  No Qt, no
network, everything under ``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

from rrational.io.generic_rr import _read_text_with_fallback, load_generic_rr

# "Müller" — the umlaut encodes to the single byte 0xfc in BOTH cp1252 and
# latin-1, and is exactly the byte utf-8 would reject and errors="ignore"
# would drop.
UMLAUT_NAME = "Müller"
UMLAUT_BYTE = b"\xfc"


# --------------------------------------------------------------------------
# Direct helper contract
# --------------------------------------------------------------------------
def test_read_text_with_fallback_decodes_cp1252_umlaut(tmp_path: Path) -> None:
    """The helper must decode a lone cp1252 umlaut byte, not drop it."""
    p = tmp_path / "note_cp1252.txt"
    p.write_bytes(("Notiz: " + UMLAUT_NAME).encode("cp1252"))
    assert UMLAUT_BYTE in p.read_bytes()  # sanity: the raw byte is present

    text = _read_text_with_fallback(p)
    assert "ü" in text
    assert text == "Notiz: " + UMLAUT_NAME


def test_read_text_with_fallback_decodes_latin1_umlaut(tmp_path: Path) -> None:
    """latin-1 is the last real fallback before replacement — cover it too."""
    p = tmp_path / "note_latin1.txt"
    p.write_bytes(UMLAUT_NAME.encode("latin-1"))
    assert _read_text_with_fallback(p) == UMLAUT_NAME


# --------------------------------------------------------------------------
# VNS Analyse: umlaut in a header value AND in a "Notiz:" event label
# --------------------------------------------------------------------------
def _write_vns_cp1252(tmp_path: Path) -> Path:
    # Header value carries the umlaut; a "Notiz:" line becomes an event
    # marker whose label also carries the umlaut.  Filename matches the
    # VNS date heuristic so the parser is happy.
    content = (
        f"Pat.-Nr.\t{UMLAUT_NAME}\n"
        "RR-Intervalle - Korrigierte Werte\n"
        "0.800\n"
        f"0.810\tNotiz: Ende Ruhephase {UMLAUT_NAME}\n"
        "0.820\n"
    )
    p = tmp_path / "01.01.2025 10.00 demo.txt"
    p.write_bytes(content.encode("cp1252"))
    assert UMLAUT_BYTE in p.read_bytes()  # sanity: really cp1252-encoded
    return p


def test_vns_cp1252_header_value_keeps_umlaut(tmp_path: Path) -> None:
    """A cp1252 umlaut in a VNS header field survives into metadata."""
    path = _write_vns_cp1252(tmp_path)
    rec = load_generic_rr(path, source_app="vns_analyse", use_corrected=True)

    header_value = rec.metadata.get("Pat.-Nr.")
    assert header_value == UMLAUT_NAME
    assert "ü" in header_value  # NOT dropped to "Mller"


def test_vns_cp1252_notiz_event_label_keeps_umlaut(tmp_path: Path) -> None:
    """A cp1252 umlaut in a VNS 'Notiz:' label survives as an event label."""
    path = _write_vns_cp1252(tmp_path)
    rec = load_generic_rr(path, source_app="vns_analyse", use_corrected=True)

    labels = [e["label"] for e in rec.metadata.get("events", [])]
    assert labels == [f"Ende Ruhephase {UMLAUT_NAME}"]
    assert "ü" in labels[0]


# --------------------------------------------------------------------------
# HRV Logger: umlaut in a companion Events file label (cp1252)
# --------------------------------------------------------------------------
def test_hrv_logger_cp1252_event_label_keeps_umlaut(tmp_path: Path) -> None:
    """A cp1252 umlaut in an HRV Logger Events label survives the load.

    Exercises _parse_hrv_logger -> _load_events_flexible, which reads the
    companion Events file with the same fallback chain.
    """
    # Unix-ms RR file (ASCII) — this is the file the user opens.
    rr_text = "timestamp,rr,since_start\n1700000000000,800,0\n1700000000800,810,800\n"
    rr_path = tmp_path / "demo_RR.csv"
    rr_path.write_bytes(rr_text.encode("utf-8"))

    # Companion Events file carries the umlaut, encoded as cp1252.
    ev_text = f"timestamp,label\n1700000000000,Beginn {UMLAUT_NAME}\n"
    ev_path = tmp_path / "demo_Events.csv"
    ev_path.write_bytes(ev_text.encode("cp1252"))
    assert UMLAUT_BYTE in ev_path.read_bytes()  # sanity: really cp1252

    rec = load_generic_rr(rr_path, source_app="hrv_logger")

    assert rec.metadata.get("events_file") == "demo_Events.csv"
    labels = [e["label"] for e in rec.metadata.get("events", [])]
    assert labels == [f"Beginn {UMLAUT_NAME}"]
    assert "ü" in labels[0]
