"""Regression test for issue #18: "Reset to Original" left stale event mappings.

The event rows use keyed widgets whose key is derived from label + timestamp.
After a reset the reloaded events get the same keys, so Streamlit kept showing
the old dropdown values although the events were unassigned ("!" marker), and
re-selecting the same value did nothing because no change was detected.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from rrational.gui import persistence  # noqa: E402
from rrational.gui.shared import clear_event_widget_state  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
APP_PATH = REPO / "src" / "rrational" / "gui" / "app.py"
DEMO = REPO / "data" / "demo" / "hrv_logger"
T = 120.0


def test_clear_event_widget_state_only_drops_that_participants_rows():
    state = {
        "canonical_P1_0123abcd_0": "rest_pre_start",
        "raw_P1_0123abcd_0": "Ruhe Start",
        "time_P1_0123abcd_0": "10:00:00",
        "canonical_P10_0123abcd_0": "keep",  # other participant (prefix!)
        "delete_P1_0123abcd_0": False,  # button, not a value widget
        "selected_participant": "P1",
    }
    assert clear_event_widget_state("P1", state) == 3
    assert set(state) == {
        "canonical_P10_0123abcd_0",
        "delete_P1_0123abcd_0",
        "selected_participant",
    }


def _canonical_mismatches(at: AppTest) -> list[tuple]:
    pe = at.session_state["participant_events"]
    out = []
    for sb in at.selectbox:
        if not (sb.key or "").startswith("canonical_"):
            continue
        rest = sb.key[len("canonical_") :]
        pid, _hash, idx = rest.rsplit("_", 2)
        data = pe[pid]
        evt = (data["events"] + data.get("manual", []))[int(idx)]
        truth = evt.canonical or "unmatched"
        if truth not in sb.options:
            truth = "unmatched"  # the app renders unknown values as unmatched
        if sb.value != truth:
            out.append((evt.raw_label, sb.value, truth))
    return out


def test_reset_to_original_refreshes_event_mapping_dropdowns(tmp_path, monkeypatch):
    # Isolate all writes: a copy of the demo data and a temp app-config file
    data_dir = tmp_path / "raw"
    shutil.copytree(DEMO, data_dir)
    monkeypatch.setattr(
        persistence, "PARTICIPANT_EVENTS_FILE", tmp_path / "participant_events.yml"
    )
    monkeypatch.setattr(sys, "argv", ["app.py", "--test-mode"])

    at = AppTest.from_file(str(APP_PATH), default_timeout=T)
    at.session_state["data_dir"] = str(data_dir)
    at.run(timeout=T)
    at.session_state["active_page"] = "Participants"
    at.run(timeout=T)
    assert not at.exception, [e.message for e in at.exception]

    boxes = [s for s in at.selectbox if (s.key or "").startswith("canonical_")]
    if not boxes:
        pytest.skip("demo data rendered no event rows")
    target = boxes[0]
    new = next(o for o in target.options if o not in (target.value, "unmatched"))
    target.select(new).run(timeout=T)
    assert _canonical_mismatches(at) == []

    reset = next(
        b
        for b in at.button
        if (b.key or "").startswith("reset_") and b.label == "Reset to Original"
    )
    reset.click().run(timeout=T)
    assert not at.exception, [e.message for e in at.exception]
    assert _canonical_mismatches(at) == []
