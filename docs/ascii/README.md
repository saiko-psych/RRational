# ANSI Art Workflow

The toolkit renders ANSI/ASCII hero art inside the GUI landing page. Keep these guidelines so we can regenerate or swap assets without breaking the layout.

## Generating ANSI art with `ansiart`

1. Activate the project virtual environment (`source .venv/bin/activate`) and install the helper if it is missing: `pip install ansiart`.
2. Run a short helper script to convert any PNG/JPG into ANSI escapes:

    ```python
    from pathlib import Path
    from ansiart import image_to_ansi, save_ansi_art

    INPUT = Path("img/mobius.png")
    OUTPUT = Path("docs/ascii/mobius_main.ans")

    ansi = image_to_ansi(str(INPUT), width=140, aspect_ratio=0.5)
    save_ansi_art(str(OUTPUT), ansi)
    ```

   - Tweak `width` (characters) and `aspect_ratio` until the preview in your terminal looks balanced.
   - For 256-colour terminals use `truecolor_to_256color(ansi)` before saving.
3. Store the resulting `.ans` file under `docs/ascii/` (the CLI loader also accepts `.txt`).

## Integrating ANSI art inside the GUI

`src/music_hrv/gui/app.py` provides two helpers:

- `load_ascii_art(name)` pulls assets from `docs/ascii`.
- `parse_ansi_art(raw)` converts ANSI colour escapes into line-by-line spans for Flet.

You can swap the artwork shown on the landing page by changing the argument to `load_ascii_art("mobius_main")`. The renderer automatically:

- Uses the monospaced `RobotoMono` font with HRV palette colours.
- Scales the font size based on the available browser width so resizing the window keeps each line intact.
- Provides keyboard selection so the art can be copied into chats or documentation.

When testing changes run `python -m src.gui.app` and resize the browser. The art should remain centered without wrapping; if it does not, lower the `width` parameter when generating the ANSI or adjust the base font constants near the top of `app.py`.

## Quick checklist

- [ ] Source artwork anonymised and approved for public sharing.
- [ ] `.ans` file saved inside `docs/ascii/` and referenced by name only (no extensions) in the GUI.
- [ ] Responsive preview confirmed by running the GUI and shrinking the browser window.
- [ ] Documented any asset-specific quirks inside this README if future maintainers need the context.
