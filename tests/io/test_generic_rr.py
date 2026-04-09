"""Tests for generic RR interval parsers."""

from pathlib import Path
import pytest

from rrational.io.generic_rr import detect_format, load_generic_rr

DEMO_DIR = Path(__file__).parent.parent.parent / "data" / "demo"


class TestDetectFormat:
    """Test auto-detection of file formats."""

    def test_polar_sensor_logger(self):
        path = DEMO_DIR / "polar" / "polar_h10_rr_sample.csv"
        assert detect_format(path) == "polar_sensor_logger"

    def test_polar_flow(self):
        path = DEMO_DIR / "polar" / "polar_flow_hrv_export.csv"
        assert detect_format(path) == "polar_flow"

    def test_empatica(self):
        path = DEMO_DIR / "empatica" / "IBI.csv"
        assert detect_format(path) == "empatica"

    def test_elite_hrv(self):
        path = DEMO_DIR / "elite_hrv" / "rr_intervals.txt"
        assert detect_format(path) == "plain_rr"

    def test_kubios(self):
        path = DEMO_DIR / "kubios" / "kubios_hrv_export.txt"
        assert detect_format(path) == "kubios"


class TestPolarSensorLogger:
    """Test Polar Sensor Logger CSV parser."""

    def test_load(self):
        path = DEMO_DIR / "polar" / "polar_h10_rr_sample.csv"
        rec = load_generic_rr(path, participant_id="POLAR01")
        assert rec.source_app == "polar_sensor_logger"
        assert rec.participant_id == "POLAR01"
        assert len(rec.rr_intervals) > 0
        # Check first interval
        rr = rec.rr_intervals[0]
        assert 200 < rr.rr_ms < 2000
        assert rr.timestamp is not None

    def test_timestamps_are_sequential(self):
        path = DEMO_DIR / "polar" / "polar_h10_rr_sample.csv"
        rec = load_generic_rr(path)
        timestamps = [rr.timestamp for rr in rec.rr_intervals if rr.timestamp]
        for i in range(1, len(timestamps)):
            assert timestamps[i] >= timestamps[i - 1]


class TestPolarFlow:
    """Test Polar Flow HRV export parser."""

    def test_load(self):
        path = DEMO_DIR / "polar" / "polar_flow_hrv_export.csv"
        rec = load_generic_rr(path, participant_id="POLAR02")
        assert rec.source_app == "polar_flow"
        assert len(rec.rr_intervals) > 0
        rr = rec.rr_intervals[0]
        assert 200 < rr.rr_ms < 2000
        assert rr.timestamp is None  # No absolute timestamps
        assert rr.elapsed_ms is not None


class TestEmpatica:
    """Test Empatica E4 IBI.csv parser."""

    def test_load(self):
        path = DEMO_DIR / "empatica" / "IBI.csv"
        rec = load_generic_rr(path, participant_id="EMPA01")
        assert rec.source_app == "empatica"
        assert len(rec.rr_intervals) > 0
        rr = rec.rr_intervals[0]
        assert 200 < rr.rr_ms < 2000
        assert rr.timestamp is not None  # Computed from unix start + offset

    def test_units_converted_to_ms(self):
        """Empatica stores in seconds — verify conversion to ms."""
        path = DEMO_DIR / "empatica" / "IBI.csv"
        rec = load_generic_rr(path)
        for rr in rec.rr_intervals:
            assert rr.rr_ms > 100, f"RR {rr.rr_ms} ms seems too low — unit conversion issue?"


class TestPlainRR:
    """Test plain-text RR interval parser (Elite HRV etc.)."""

    def test_load(self):
        path = DEMO_DIR / "elite_hrv" / "rr_intervals.txt"
        rec = load_generic_rr(path, participant_id="ELITE01")
        assert rec.source_app == "plain_rr"
        assert len(rec.rr_intervals) > 0
        rr = rec.rr_intervals[0]
        assert 200 < rr.rr_ms < 2000

    def test_auto_detect_ms(self):
        """Values > 100 should be detected as milliseconds."""
        path = DEMO_DIR / "elite_hrv" / "rr_intervals.txt"
        rec = load_generic_rr(path)
        assert rec.metadata.get("detected_unit") == "milliseconds"


class TestKubios:
    """Test Kubios HRV export parser."""

    def test_load(self):
        path = DEMO_DIR / "kubios" / "kubios_hrv_export.txt"
        rec = load_generic_rr(path, participant_id="KUBIOS01")
        assert rec.source_app == "kubios"
        assert len(rec.rr_intervals) > 0
        rr = rec.rr_intervals[0]
        assert 200 < rr.rr_ms < 2000

    def test_metadata(self):
        path = DEMO_DIR / "kubios" / "kubios_hrv_export.txt"
        rec = load_generic_rr(path)
        assert "Kubios" in rec.metadata.get("source", "")
