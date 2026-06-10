"""Tests for the WelcomeWidget landing screen.

Covers the "Try with sample data" entry point introduced as F11:
clicking the welcome button (or invoking the equivalent File-menu
action) builds a synthetic dataset, registers it on the workspace
and switches the active index to it.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def isolated_settings(qapp, tmp_path):
    from rrational.inspector import settings

    settings.enable_test_mode(tmp_path)
    yield


@pytest.fixture
def main_window(qtbot):
    from rrational.inspector.main_window import MainWindow

    win = MainWindow()
    win.test_mode = True
    qtbot.addWidget(win)
    win.show()
    qtbot.waitExposed(win)
    return win


def test_make_demo_dataset_shape():
    """Helper returns a Dataset with the documented 5-min layout."""
    from rrational.inspector.welcome_widget import (
        DEMO_DATASET_NAME,
        make_demo_dataset,
    )

    ds = make_demo_dataset()
    assert ds.name == DEMO_DATASET_NAME
    assert ds.path is None  # synthetic — no on-disk source
    # 60 + 180 + 60 = 300 beats spanning ~5 minutes.
    assert ds.data.t.shape == (300,)
    assert ds.data.v.shape == (300,)
    assert [s.name for s in ds.data.sections] == [
        "rest_pre",
        "music",
        "rest_post",
    ]
    assert [e.label for e in ds.data.events] == [
        "rest_pre_start",
        "music_start",
        "rest_post_start",
    ]
    # Music section pushes mean RR down (higher HR) vs the rest blocks.
    music_mean = ds.data.v[60:240].mean()
    rest_pre_mean = ds.data.v[:60].mean()
    assert music_mean < rest_pre_mean


def test_welcome_widget_demo_button_loads_dataset(main_window, qtbot):
    """Clicking the welcome button populates _datasets + activates it."""
    from rrational.inspector.welcome_widget import (
        DEMO_DATASET_NAME,
        WelcomeWidget,
    )

    # The BrowseTab embeds a WelcomeWidget; rather than digging through
    # the tab hierarchy, instantiate one bound to the test main window
    # — same code path that real users hit when the widget is visible.
    welcome = WelcomeWidget(main_window)
    qtbot.addWidget(welcome)

    assert main_window._datasets == []
    welcome._try_demo_btn.click()

    assert len(main_window._datasets) == 1
    assert main_window._datasets[0].name == DEMO_DATASET_NAME
    assert main_window._active_idx == 0


def test_load_demo_dataset_method(main_window):
    """The MainWindow API entry returns the new index and switches to it."""
    from rrational.inspector.welcome_widget import DEMO_DATASET_NAME

    idx = main_window.load_demo_dataset()

    assert idx == 0
    assert main_window._active_idx == 0
    assert main_window._datasets[idx].name == DEMO_DATASET_NAME


def test_file_menu_try_demo_action_loads_dataset(main_window):
    """File menu entry triggers the same demo-load behaviour."""
    from rrational.inspector.welcome_widget import DEMO_DATASET_NAME

    main_window._try_demo_act.trigger()

    assert len(main_window._datasets) == 1
    assert main_window._datasets[0].name == DEMO_DATASET_NAME
    assert main_window._active_idx == 0


def test_welcome_layout_is_vertically_centered(main_window, qtbot):
    """Round 16 (L2) — outer QVBoxLayout must bracket the content with
    equal-weight stretchers so the title block sits on the optical
    centre instead of the upper third.
    """
    from qtpy.QtWidgets import QSpacerItem
    from rrational.inspector.welcome_widget import WelcomeWidget

    welcome = WelcomeWidget(main_window)
    qtbot.addWidget(welcome)
    root = welcome.layout()

    # First and last items must both be stretches.
    first = root.itemAt(0)
    last = root.itemAt(root.count() - 1)
    # A QSpacerItem with stretch=1 has the same isEmpty()/spacerItem()
    # signature regardless of which addStretch() variant produced it.
    assert isinstance(first.spacerItem(), QSpacerItem)
    assert isinstance(last.spacerItem(), QSpacerItem)
    # Stretch factors must match (1:1) so the content stays centered.
    assert root.stretch(0) == root.stretch(root.count() - 1)


def test_welcome_empty_recent_label_is_italic(main_window, qtbot):
    """Round 16 (L4) — empty-state hint reads as a deliberate state."""
    from rrational.inspector.welcome_widget import WelcomeWidget

    welcome = WelcomeWidget(main_window)
    qtbot.addWidget(welcome)
    assert welcome._empty_recent_label.font().italic() is True
    # Carries the QSS ``hint`` property so the theme paints it in
    # the muted-secondary colour.
    assert welcome._empty_recent_label.property("hint") is True
