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

    def __init__(self, master, on_navigate: Callable[[str], None], **kwargs) -> None:
        super().__init__(master, width=SIDEBAR_WIDTH, corner_radius=0, **kwargs)
        self._on_navigate = on_navigate
        self._buttons: dict[str, ctk.CTkButton] = {}

        title = ctk.CTkLabel(self, text="📰 Newsletter", font=ctk.CTkFont(**SECTION_FONT))
        title.pack(padx=16, pady=(20, 24), anchor="w")

        for key, label in NAV_ITEMS:
            button = ctk.CTkButton(
                self,
                text=label,
                anchor="w",
                fg_color="transparent",
                command=lambda k=key: self._select(k),
            )
            button.pack(fill="x", padx=12, pady=4)
            self._buttons[key] = button

        self.set_active(NAV_ITEMS[0][0])

    def _select(self, key: str) -> None:
        self.set_active(key)
        self._on_navigate(key)

    def set_active(self, key: str) -> None:
        """Highlight the button for ``key``."""
        for name, button in self._buttons.items():
            button.configure(fg_color=ACTIVE_NAV_COLOR if name == key else "transparent")

    @property
    def items(self) -> list[str]:
        return [key for key, _ in NAV_ITEMS]
