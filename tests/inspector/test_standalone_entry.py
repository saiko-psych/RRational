"""Smoke tests for the PyInstaller-friendly inspector entry point.

These tests do NOT run PyInstaller (that lives in CI). They exercise the
Python-level invariants that the standalone build relies on:

- ``rrational.inspector.app`` imports cleanly with the inspector extras.
- ``main`` and ``run`` are callable module-level symbols.
- The argument parser accepts ``--file`` and ``--help`` without crashing.
- ``MainWindow()`` constructs under the offscreen QPA used in CI.

If any of these regress, the GH Actions job ``build-inspector`` will
either fail to package or produce an artifact that crashes at startup.
"""

from __future__ import annotations


import pytest

pytest.importorskip("pytestqt")
pytest.importorskip("pyqtgraph")


@pytest.fixture(autouse=True)
def _force_offscreen_qpa(monkeypatch):
    """Mirror the CI environment so QApplication boots without a display.

    pytest-qt usually sets this for us, but the standalone smoke test
    instantiates QApplication directly and we want the behaviour to be
    deterministic regardless of whether pytest-qt's fixture has run.
    """
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    yield


def test_app_module_exposes_main_callable():
    """PyInstaller's spec references ``rrational.inspector.app.main``.

    If a refactor accidentally moves it elsewhere the bundled exe will
    still build, but it will exit immediately at launch. This test
    catches that before the slow CI build does.
    """
    from rrational.inspector import app as app_module

    assert callable(app_module.main), "main() must be importable from app.py"
    assert callable(app_module.run), "run() must be importable from app.py"
    # Belt + braces: the __init__.py re-export should also resolve.
    from rrational import inspector as pkg

    assert callable(pkg.main)


def test_app_main_has_if_main_shim(tmp_path):
    """``app.py`` must end with the ``if __name__ == "__main__"`` shim.

    PyInstaller's one-file mode invokes the script via its ``__main__``
    bootstrap; without the shim, ``main()`` is never called and the
    process exits before showing a window.
    """
    import inspect

    from rrational.inspector import app as app_module

    src = inspect.getsource(app_module)
    assert 'if __name__ == "__main__"' in src, (
        "app.py is missing the PyInstaller-required __main__ shim"
    )
    assert "sys.exit(main())" in src, (
        "app.py's __main__ shim should call sys.exit(main()) so the OS "
        "sees the correct Qt exit code"
    )


def test_parser_accepts_file_flag():
    """``--file`` is the supported flag for OS file-association launches."""
    from rrational.inspector.app import _build_parser

    parser = _build_parser()
    args = parser.parse_args(["--file", "demo.rrational"])
    assert str(args.file_path).endswith("demo.rrational")
    # Positional remains supported for backwards compatibility.
    args2 = parser.parse_args(["legacy.rrational"])
    assert str(args2.path).endswith("legacy.rrational")


def test_parser_help_exits_cleanly(capsys):
    """``--help`` should not crash the process, just print and SystemExit(0).

    argparse raises SystemExit on --help; we assert the exit code is 0
    (success) so the CI smoke check can use ``--help`` as a tiny "did the
    bundle wire up correctly" probe.

    We deliberately do NOT mock ``sys.exit`` here: argparse calls it
    internally via ``parser.exit()`` and intercepting it would prevent
    the SystemExit that pytest.raises expects. The brief from Phase 9
    asks for a smoke test that exercises ``--help`` "without crashing" —
    SystemExit(0) qualifies.
    """
    from rrational.inspector.app import run

    with pytest.raises(SystemExit) as excinfo:
        run(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "rrational-inspect" in out
    assert "--file" in out


def test_main_window_constructs_under_offscreen(qtbot, tmp_path):
    """The window must construct without a real display.

    PyInstaller-built executables on a fresh user's machine run with
    whatever QPA the system provides; if MainWindow's constructor grew
    a hidden requirement (a screen DPI lookup, say) the bundle would
    crash on startup. Constructing under the offscreen QPA is the
    closest proxy we have to "first launch in a sandboxed container".
    """
    from rrational.inspector import settings
    from rrational.inspector.main_window import MainWindow

    # The autouse fixture in conftest.py already redirects color scheme
    # persistence; we also redirect QSettings so the test doesn't pollute
    # the developer's registry / plist.
    settings.enable_test_mode(tmp_path)

    win = MainWindow()
    qtbot.addWidget(win)
    # Just constructing + showing is the smoke test; if Qt blows up here
    # (missing plugin, bad signal connection) the bundle would too.
    win.show()
    assert win.windowTitle() == "RRational Inspector"
