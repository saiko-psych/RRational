# Inspector Standalone App

The **Inspector** is a lightweight desktop signal browser for `.rrational`
files. It runs alongside the main Streamlit web app and shares the same
HRV analysis backend, but it boots in under two seconds and gives you
keyboard-driven, per-beat navigation through a recording — handy for
quickly checking artifacts, scrubbing to specific events, or comparing
sections side-by-side without spinning up a browser.

## Download

Pre-built standalone executables are published on GitHub Releases for
every tagged version:

[Latest release on GitHub](https://github.com/saiko-psych/rrational/releases/latest){ .md-button }

Pick the archive that matches your platform:

| Platform | File | Architecture |
|----------|------|--------------|
| Windows 10 / 11 | `RRational-Inspector-Windows.zip` | x86_64 |
| macOS (Intel) | `RRational-Inspector-macOS-Intel.zip` | x86_64 |
| macOS (Apple Silicon M1 / M2 / M3 / M4) | `RRational-Inspector-macOS-AppleSilicon.zip` | arm64 |
| Linux (Ubuntu 22.04 + / Debian 12 +) | `RRational-Inspector-Linux.tar.gz` | x86_64 |

### Which macOS build do I need?

Click the Apple menu, then **About This Mac**, and read the **Chip** line:

- `Apple M1`, `M2`, `M3`, or `M4` — download **Apple Silicon**.
- `Intel Core …` — download **Intel**.

Running the wrong build produces the error `Bad CPU type in executable`.

## Run

1. Download and extract the archive for your platform.
2. Launch the binary:
    - **Windows:** double-click `RRational-Inspector.exe`.
    - **macOS:** double-click `RRational-Inspector`. The first launch is
      blocked by Gatekeeper because the binary is not yet code-signed —
      right-click the binary and choose **Open**, or run
      `xattr -dr com.apple.quarantine /path/to/RRational-Inspector` once
      in Terminal.
    - **Linux:** run `./RRational-Inspector` from a terminal, or set the
      executable bit (`chmod +x RRational-Inspector`) and double-click in
      your file manager.

No Python installation is required — the executable bundles its own
Python runtime, Qt 6, PyQtGraph, NeuroKit2, and SciPy.

### Opening a file at startup

You can pass a `.rrational` file on the command line. This is what your
operating system passes when you register the inspector as the default
opener for `.rrational` files:

```bash
RRational-Inspector --file path/to/recording.rrational
```

A bare positional argument is also accepted for backwards compatibility
(`RRational-Inspector path/to/recording.rrational`).

## When to use the Inspector vs. the Streamlit app

- Use the **Streamlit web app** for group analysis, statistics,
  multi-participant pipelines, and report generation.
- Use the **Inspector** for fast visual review of a single recording:
  scrolling through beats, inspecting individual artifacts, jumping to
  events / sections, and exporting screenshots.

Both apps read the same project folder layout, so you can use them
side-by-side on the same data without conversion.

## Running from source

If you prefer to run the inspector from the source tree instead of a
standalone build (for example, while contributing patches):

```bash
git clone https://github.com/saiko-psych/rrational.git
cd rrational
uv sync --extra inspector
uv run python -m rrational.inspector
```

The `--extra inspector` flag pulls in PySide6, PyQtGraph, and qtpy in
addition to the core dependencies.
