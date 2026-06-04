"""Tests for inspector.color_scheme_persistence — YAML-backed color
scheme preferences.

Color preferences are user-level (NOT project-scoped), so the
``isolated_color_dir`` fixture redirects only the dedicated override
hook and asserts no leak into the user's real ~/.rrational/inspector/.
"""

from __future__ import annotations

import pytest

from rrational.gui.color_scheme import PRESET_THEMES, ColorScheme
from rrational.inspector.color_scheme_persistence import (
    COLOR_SCHEME_FILENAME,
    CUSTOM_PRESET_NAME,
    DEFAULT_PRESET_NAME,
    load_color_scheme,
    save_color_scheme,
    set_color_scheme_config_dir,
)


@pytest.fixture(autouse=True)
def isolated_color_dir(tmp_path):
    set_color_scheme_config_dir(tmp_path)
    yield
    set_color_scheme_config_dir(None)


def test_load_returns_defaults_when_no_file():
    preset, scheme = load_color_scheme()
    assert preset == DEFAULT_PRESET_NAME
    assert isinstance(scheme, ColorScheme)
    # The Scientific default uses #2E86AB as rr_line — same dataclass default
    assert scheme.rr_line == PRESET_THEMES[DEFAULT_PRESET_NAME].rr_line


def test_save_then_load_roundtrips_known_preset(tmp_path):
    save_color_scheme("Colorful", PRESET_THEMES["Colorful"])
    assert (tmp_path / COLOR_SCHEME_FILENAME).exists()
    preset, scheme = load_color_scheme()
    assert preset == "Colorful"
    assert scheme.rr_line == PRESET_THEMES["Colorful"].rr_line


def test_save_then_load_roundtrips_custom_scheme():
    custom = ColorScheme(
        rr_line="#abcdef",
        artifact="#123456",
        nn_line="#fedcba",
    )
    save_color_scheme(CUSTOM_PRESET_NAME, custom)
    preset, scheme = load_color_scheme()
    assert preset == CUSTOM_PRESET_NAME
    assert scheme.rr_line == "#abcdef"
    assert scheme.artifact == "#123456"
    assert scheme.nn_line == "#fedcba"


def test_load_survives_corrupted_yaml(tmp_path):
    (tmp_path / COLOR_SCHEME_FILENAME).write_text(
        "this is :: not :: yaml :: at all", encoding="utf-8"
    )
    preset, scheme = load_color_scheme()
    assert preset == DEFAULT_PRESET_NAME
    assert isinstance(scheme, ColorScheme)


def test_unknown_preset_with_no_custom_returns_default(tmp_path):
    (tmp_path / COLOR_SCHEME_FILENAME).write_text(
        "preset_name: NotARealPreset\ncustom_scheme: null\n",
        encoding="utf-8",
    )
    preset, scheme = load_color_scheme()
    assert preset == DEFAULT_PRESET_NAME
    assert scheme.rr_line == PRESET_THEMES[DEFAULT_PRESET_NAME].rr_line


def test_save_creates_directory_if_missing(tmp_path):
    new_dir = tmp_path / "fresh" / "deep"
    set_color_scheme_config_dir(new_dir)
    save_color_scheme(DEFAULT_PRESET_NAME, PRESET_THEMES[DEFAULT_PRESET_NAME])
    assert (new_dir / COLOR_SCHEME_FILENAME).exists()


def test_save_known_preset_omits_custom_payload(tmp_path):
    """Saving a preset by name should not bake the dict into YAML.

    This way a future preset re-tweak (in code) is automatically picked
    up by users who only chose the preset name.
    """
    import yaml

    save_color_scheme("Pastel", PRESET_THEMES["Pastel"])
    raw = yaml.safe_load((tmp_path / COLOR_SCHEME_FILENAME).read_text("utf-8"))
    assert raw == {"preset_name": "Pastel", "custom_scheme": None}


def test_save_custom_writes_full_dict(tmp_path):
    import yaml

    custom = ColorScheme(rr_line="#000011")
    save_color_scheme(CUSTOM_PRESET_NAME, custom)
    raw = yaml.safe_load((tmp_path / COLOR_SCHEME_FILENAME).read_text("utf-8"))
    assert raw["preset_name"] == CUSTOM_PRESET_NAME
    assert raw["custom_scheme"]["rr_line"] == "#000011"
