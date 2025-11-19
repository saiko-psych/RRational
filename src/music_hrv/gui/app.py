"""Flet-based landing page for the Music HRV Toolkit."""

from __future__ import annotations

from pathlib import Path

import flet as ft

ASCII_DIR = Path(__file__).resolve().parents[3] / "docs" / "ascii"


def load_ascii_art(name: str) -> str:
    """Read ASCII art from docs/ascii."""

    path = ASCII_DIR / f"{name}.txt"
    return path.read_text(encoding="utf-8") if path.exists() else name

NEON_GRADIENT = ft.LinearGradient(
    begin=ft.alignment.top_left,
    end=ft.alignment.bottom_right,
    colors=["#ff4dff", "#7b5bff", "#05f0ff"],
)


def main(page: ft.Page) -> None:
    """Render a Hyperpop / Hardtekk-flavoured landing page."""

    page.title = "Music HRV Toolkit"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#04010d"
    page.scroll = "adaptive"
    page.padding = 40
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    main_ascii = load_ascii_art("mobius_main").strip("\n")
    hero_card = ft.Container(
        width=980,
        padding=30,
        border_radius=30,
        gradient=NEON_GRADIENT,
        shadow=ft.BoxShadow(
            blur_radius=65,
            spread_radius=8,
            color=ft.colors.with_opacity(0.45, "#ff4dff"),
        ),
        content=ft.Column(
            [
                ft.Text(
                    main_ascii,
                    font_family="RobotoMono",
                    size=20,
                    weight=ft.FontWeight.W_700,
                    color="#04010d",
                    text_align=ft.TextAlign.CENTER,
                    no_wrap=True,
                ),
                ft.Text(
                    (
                        "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
                        "Vestibulum consectetur lorem at ipsum ultricies, non rutrum "
                        "odio imperdiet. Cras vitae mi a libero dignissim tempus. "
                        "Fusce sed justo vitae ipsum dapibus varius."
                    ),
                    size=16,
                    color="#04010d",
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            spacing=20,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )

    actions = ft.Row(
        controls=[
            ft.ElevatedButton(
                "Inspect Sections",
                icon=ft.icons.SEARCH,
                bgcolor="#ff4dff",
                color="#04010d",
                style=ft.ButtonStyle(
                    padding=20,
                    shape=ft.RoundedRectangleBorder(radius=20),
                ),
                tooltip="View detected section labels across your dataset",
                on_click=lambda _: page.snack_bar.open(),
            ),
            ft.OutlinedButton(
                "Launch Pipeline (soon)",
                icon=ft.icons.PLAY_ARROW,
                style=ft.ButtonStyle(
                    color="#05f0ff",
                    side={"color": "#05f0ff"},
                    padding=20,
                    shape=ft.RoundedRectangleBorder(radius=20),
                ),
            ),
        ],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=30,
    )

    vibe_text = ft.Text(
        "Neon-grade data prep for your sessions — more controls dropping soon.",
        size=16,
        color="#c7c6ff",
        text_align=ft.TextAlign.CENTER,
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

    page.add(
        hero_card,
        ft.Container(
            content=ft.Column(
                [
                    vibe_text,
                    ft.Divider(height=30, color="#322259"),
                    actions,
                    social_row,
                ],
                spacing=20,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ),
    )


def run(view: ft.AppView | None = None) -> None:
    """Launch the Flet app (browser view to avoid native deps by default)."""

    ft.app(target=main, view=view or ft.AppView.WEB_BROWSER)


if __name__ == "__main__":  # pragma: no cover
    run()
