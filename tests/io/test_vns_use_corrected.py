"""Tests for VNS Analyse `use_corrected` flag propagation (Cluster D3).

Builds a minimal synthetic VNS-Analyse text file with distinct raw +
corrected RR sections and asserts ``load_generic_rr`` returns the
expected series for each ``use_corrected`` value.
"""

from __future__ import annotations

from pathlib import Path

from rrational.io.generic_rr import load_generic_rr

VNS_CONTENT = """Pat.-Nr.\t12345
RR-Intervalle - Rohwerte
0.800
0.810
0.820
0.830
RR-Intervalle - Korrigierte Werte
0.700
0.710
0.720
0.730
Hauptparameter
RMSSD\t42.5
"""


def _write_vns(tmp_path: Path) -> Path:
    # Filename must look like VNS Analyse output for the parser's
    # date heuristic to fire (it falls back to a fixed date if not,
    # but a realistic name keeps the assertions concise).
    p = tmp_path / "01.01.2025 10.00 demo.txt"
    p.write_text(VNS_CONTENT, encoding="utf-8")
    return p


def test_load_generic_rr_use_corrected_true_returns_corrected_values(tmp_path):
    path = _write_vns(tmp_path)
    rec = load_generic_rr(path, source_app="vns_analyse", use_corrected=True)
    rr_values = [iv.rr_ms for iv in rec.rr_intervals]
    assert rr_values == [700, 710, 720, 730]
    assert rec.metadata["use_corrected"] is True


def test_load_generic_rr_use_corrected_false_returns_raw_values(tmp_path):
    path = _write_vns(tmp_path)
    rec = load_generic_rr(path, source_app="vns_analyse", use_corrected=False)
    rr_values = [iv.rr_ms for iv in rec.rr_intervals]
    assert rr_values == [800, 810, 820, 830]
    assert rec.metadata["use_corrected"] is False


def test_load_generic_rr_default_uses_corrected_for_vns(tmp_path):
    """D3 default flipped to True so the inspector matches the
    scientific norm of preferring the cleaned series when present."""
    path = _write_vns(tmp_path)
    rec = load_generic_rr(path, source_app="vns_analyse")
    rr_values = [iv.rr_ms for iv in rec.rr_intervals]
    assert rr_values == [700, 710, 720, 730]
