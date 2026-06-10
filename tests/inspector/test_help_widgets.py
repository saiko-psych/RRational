"""Round 17 — Help-Expander content coverage for Participant tab.

Asserts that the ParticipantTab now exposes three HelpExpander panels:
- "Per-participant workflow" (existing)
- "Keyboard shortcuts" (Round 17)
- "Overview bar" (Round 17)

Each new expander must carry the body text spelled out in the audit so
users get the full Cluster-A keyboard reference in-context.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path, monkeypatch):
    from rrational.gui import persistence as gui_persistence
    from rrational.inspector import persistence, settings

    settings.enable_test_mode(tmp_path)
    persistence.set_inspector_config_dir(tmp_path)
    monkeypatch.setattr(gui_persistence, "CONFIG_DIR", tmp_path / "gui_config")
    monkeypatch.setattr(
        gui_persistence, "SETTINGS_FILE", tmp_path / "gui_config" / "settings.yml"
    )
    yield
    persistence.set_inspector_config_dir(None)


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


def _all_help_titles(widget):
    """Walk widget tree and yield the title of every HelpExpander descendant."""
    from rrational.inspector.help_widgets import HelpExpander

    titles: list[str] = []
    for child in widget.findChildren(HelpExpander):
        titles.append(child.title())
    return titles


def _all_help_bodies(widget):
    """Walk widget tree and yield the body HTML of every HelpExpander."""
    from rrational.inspector.help_widgets import HelpExpander

    bodies: list[str] = []
    for child in widget.findChildren(HelpExpander):
        bodies.append(child.body_label().text())
    return bodies


def test_participant_tab_keyboard_shortcuts_expander(main_window):
    titles = _all_help_titles(main_window._participant_tab)
    assert "Keyboard shortcuts" in titles


def test_participant_tab_overview_bar_expander(main_window):
    titles = _all_help_titles(main_window._participant_tab)
    assert "Overview bar" in titles


def test_keyboard_shortcuts_body_lists_zen_and_hud_keys(main_window):
    bodies = _all_help_bodies(main_window._participant_tab)
    matches = [b for b in bodies if "Reset zoom" in b and "Zen mode" in b]
    assert matches, "Keyboard-shortcuts expander missing R/Z key rows"
    body = matches[0]
    # Cluster A reference keys must be present.
    for token in ("R", "1 / 2 / 3", "A", "E", "H", "C", "Z", "Home / End"):
        assert token in body, f"shortcut '{token}' missing from help body"


def test_overview_bar_body_describes_viewport_drag(main_window):
    bodies = _all_help_bodies(main_window._participant_tab)
    matches = [b for b in bodies if "Overview Bar" in b or "Overview bar" in b]
    assert matches, "Overview-bar expander body missing"
    body = matches[0]
    assert "viewport" in body.lower()
    assert "exclusion" in body.lower() or "annotation" in body.lower()
