"""Flet-based landing page for the Music HRV Toolkit."""

from __future__ import annotations

from pathlib import Path

import flet as ft

ASCII_DIR = Path(__file__).resolve().parents[3] / "docs" / "ascii"


def load_ascii_art(name: str) -> str:
    """Read ASCII art from docs/ascii."""

    path = ASCII_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8") if path.exists() else name

def main(page: ft.Page) -> None:
    """Render a Hyperpop / Hardtekk-flavoured landing page."""

    page.title = "Music HRV Toolkit"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#04010d"
    page.scroll = "adaptive"
    page.padding = 40
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    main_ascii = load_ascii_art("mobius_main").strip("\n")
    hero_ascii = ft.Text(
        main_ascii,
        font_family="RobotoMono",
        size=24,
        weight=ft.FontWeight.W_700,
        color="#f6f5ff",
        text_align=ft.TextAlign.CENTER,
        no_wrap=True,
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
