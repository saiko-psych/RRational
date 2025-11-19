"""Flet-based landing page for the Music HRV Toolkit."""

from __future__ import annotations

import re
from pathlib import Path

import flet as ft

ASCII_DIR = Path(__file__).resolve().parents[3] / "docs" / "ascii"
ANSI_COLOR_PATTERN = re.compile(r"\x1b\[38;2;(\d+);(\d+);(\d+)m")


def load_ascii_art(name: str) -> str:
    """Read ASCII art from docs/ascii (supports .ans and .txt)."""

    for extension in (".ans", ".txt"):
        path = ASCII_DIR / f"{name}{extension}"
        if path.exists():
            return path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Missing ASCII art asset: {name}")


def parse_ansi_art(raw: str, *, default_color: str = "#f6f5ff") -> list[list[tuple[str, str]]]:
    """Convert ANSI color escapes into line-wise spans."""

    tokens = re.split(r"(\x1b\[38;2;\d+;\d+;\d+m|\x1b\[0m|\n)", raw)
    lines: list[list[tuple[str, str]]] = []
    current_color = default_color
    buffer = []
    spans: list[tuple[str, str]] = []

    def flush_buffer() -> None:
        if buffer:
            spans.append(("".join(buffer), current_color))
            buffer.clear()

    for token in tokens:
        if not token:
            continue
        if token == "\n":
            flush_buffer()
            if spans:
                lines.append(spans.copy())
            else:
                lines.append([])
            spans.clear()
            continue
        if token == "\x1b[0m":
            flush_buffer()
            current_color = default_color
            continue
        color_match = ANSI_COLOR_PATTERN.fullmatch(token)
        if color_match:
            flush_buffer()
            r, g, b = map(int, color_match.groups())
            current_color = f"#{r:02x}{g:02x}{b:02x}"
            continue
        buffer.append(token)

    flush_buffer()
    if spans:
        lines.append(spans)
    return lines

def main(page: ft.Page) -> None:
    """Render a Hyperpop / Hardtekk-flavoured landing page."""

    page.title = "Music HRV Toolkit"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#04010d"
    page.scroll = "adaptive"
    page.padding = 10
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    raw_art = load_ascii_art("mobius_main")
    ascii_lines = parse_ansi_art(raw_art)

    ascii_controls: list[ft.Control] = []
    for line in ascii_lines:
        if not line:
            ascii_controls.append(ft.Container(height=8))
            continue
        spans = [
            ft.TextSpan(
                text=span_text,
                style=ft.TextStyle(
                    color=color,
                    font_family="RobotoMono",
                    size=16,
                    weight=ft.FontWeight.W_600,
                ),
            )
            for span_text, color in line
        ]
        ascii_controls.append(
            ft.Text(
                spans=spans,
                text_align=ft.TextAlign.CENTER,
                width=2000,
                selectable=True,
            )
        )

    hero_ascii = ft.Column(
        ascii_controls,
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )

    social_row = ft.Row(
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=10,
        controls=[
            ft.IconButton(
                icon=ft.icons.CODE,
                tooltip="GitHub: saiko-psych",
                url="https://github.com/saiko-psych",
                icon_color="#ff4dff",
            ),
            ft.IconButton(
                icon=ft.icons.EMAIL,
                tooltip="david.matischek@edu.uni-graz.at",
                url="mailto:david.matischek@edu.uni-graz.at",
                icon_color="#05f0ff",
            ),
        ],
    )

    page.snack_bar = ft.SnackBar(ft.Text("CLI integration coming soon — stay tuned!"))

    page.add(hero_ascii, social_row)


def run(view: ft.AppView | None = None) -> None:
    """Launch the Flet app (browser view to avoid native deps by default)."""

    ft.app(target=main, view=view or ft.AppView.WEB_BROWSER)


if __name__ == "__main__":  # pragma: no cover
    run()
