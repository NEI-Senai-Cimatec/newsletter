# gui/components/status_bar.py
"""Bottom status bar: activity message (left) + provider summary (right)."""
import customtkinter as ctk

from gui.theme.colors import SMALL_FONT, STATUS_BAR_HEIGHT


class StatusBar(ctk.CTkFrame):
    """Thin bar pinned to the bottom of the main window."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, height=STATUS_BAR_HEIGHT, corner_radius=0, **kwargs)
        self.status_label = ctk.CTkLabel(
            self, text="Pronto", anchor="w", font=ctk.CTkFont(**SMALL_FONT)
        )
        self.status_label.pack(side="left", padx=12)
        self.provider_label = ctk.CTkLabel(
            self, text="", anchor="e", font=ctk.CTkFont(**SMALL_FONT)
        )
        self.provider_label.pack(side="right", padx=12)

    def set_status(self, text: str) -> None:
        """Show an activity message on the left."""
        self.status_label.configure(text=text)

    def set_provider(self, text: str) -> None:
        """Show the provider/model summary on the right."""
        self.provider_label.configure(text=text)
