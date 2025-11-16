"""Flet-based landing page for the Music HRV Toolkit."""

from __future__ import annotations

import flet as ft

ASCII_ART = r"""
 __  __           _             _   _ _   _    _   _ _____     _____     _ _ _   
|  \/  | ___  ___| |_ _ __ __ _| |_(_) |_(_)  | | | |_   _|__ |_   _|_ _(_) | |_ 
| |\/| |/ _ \/ __| __| '__/ _` | __| | __| |  | |_| | | |/ _ \  | |/ _` | | | __|
| |  | |  __/\__ \ |_| | | (_| | |_| | |_| |  |  _  | | |  __/  | | (_| | | | |_ 
|_|  |_|\___||___/\__|_|  \__,_|\__|_|\__|_|  |_| |_| |_| \___|  |_|\__,_|_|_|\__|
"""

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

    hero_card = ft.Container(
        width=900,
        padding=20,
        border_radius=30,
        gradient=NEON_GRADIENT,
        shadow=ft.BoxShadow(
            blur_radius=45,
            spread_radius=5,
            color=ft.colors.with_opacity(0.35, "#ff4dff"),
        ),
        content=ft.Column(
            [
                ft.Text(
                    "MUSIC HRV TOOLKIT",
                    size=40,
                    weight=ft.FontWeight.BOLD,
                    color="#04010d",
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Text(
                    "Hyperpop Hardtekk edition · RR segmentation · NeuroKit ready",
                    size=16,
                    color="#04010d",
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=4,
        ),
    )

    ascii_banner = ft.Container(
        margin=ft.margin.only(top=30),
        padding=20,
        bgcolor="#07001b",
        border_radius=20,
        content=ft.Text(
            ASCII_ART.strip("\n"),
            font_family="RobotoMono",
            size=14,
            color="#f6f5ff",
            text_align=ft.TextAlign.CENTER,
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
        "Crank the BPM, keep the data clean. Future GUI hooks will land here.",
        size=16,
        color="#c7c6ff",
        text_align=ft.TextAlign.CENTER,
    )

    page.snack_bar = ft.SnackBar(ft.Text("CLI integration coming soon — stay tuned!"))

    page.add(
        hero_card,
        ascii_banner,
        ft.Container(
            content=ft.Column(
                [
                    vibe_text,
                    ft.Divider(height=30, color="#322259"),
                    actions,
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
