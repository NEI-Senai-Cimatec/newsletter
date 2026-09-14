# gui/components/sidebar.py
"""Left navigation menu."""
from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from gui.theme.colors import ACTIVE_NAV_COLOR, SECTION_FONT, SIDEBAR_WIDTH

NAV_ITEMS: list[tuple[str, str]] = [
    ("home", "🏠 Início"),
    ("settings", "⚙️ Configurações"),
    ("scraper", "🚀 Execução"),
    ("results", "📊 Resultados"),
    ("logs", "🧾 Logs"),
]


class Sidebar(ctk.CTkFrame):
    """Vertical menu that notifies ``on_navigate(frame_name)`` on clicks."""

    def __init__(self, master, on_navigate: Callable[[str], None],
                 items: list[tuple[str, str]] | None = None, **kwargs) -> None:
        super().__init__(master, width=SIDEBAR_WIDTH, corner_radius=0, **kwargs)
        self._on_navigate = on_navigate
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._items: list[tuple[str, str]] = list(items) if items is not None else list(NAV_ITEMS)

        title = ctk.CTkLabel(self, text="📰 Newsletter", font=ctk.CTkFont(**SECTION_FONT))
        title.pack(padx=16, pady=(20, 24), anchor="w")

        self._nav_box = ctk.CTkFrame(self, fg_color="transparent")
        self._nav_box.pack(fill="x")
        self.set_items(self._items)

    def _select(self, key: str) -> None:
        self.set_active(key)
        self._on_navigate(key)

    def set_active(self, key: str) -> None:
        """Highlight the button for ``key``."""
        for name, button in self._buttons.items():
            button.configure(fg_color=ACTIVE_NAV_COLOR if name == key else "transparent")

    def set_items(self, items: list[tuple[str, str]]) -> None:
        """Rebuild the nav buttons for ``items`` (hybrid nav per session role)."""
        for button in self._buttons.values():
            button.destroy()
        self._buttons = {}
        self._items = list(items)
        for key, label in self._items:
            button = ctk.CTkButton(
                self._nav_box,
                text=label,
                anchor="w",
                fg_color="transparent",
                command=lambda k=key: self._select(k),
            )
            button.pack(fill="x", padx=12, pady=4)
            self._buttons[key] = button
        if self._items:
            self.set_active(self._items[0][0])

    @property
    def items(self) -> list[str]:
        return [key for key, _ in self._items]
