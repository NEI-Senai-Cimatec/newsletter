# gui/frames/log_frame.py
"""Real-time log console with per-level colors."""
import logging
from datetime import datetime
from tkinter import filedialog

import customtkinter as ctk

from gui.theme.colors import LOG_COLORS, MONO_FONT, TITLE_FONT

MAX_LINES = 5000


class LogFrame(ctk.CTkFrame):
    """Textbox fed from ``app.log_queue`` via ``after()`` polling."""

    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._polling = False

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(header, text="🧾 Logs",
                     font=ctk.CTkFont(**TITLE_FONT)).pack(side="left")
        ctk.CTkButton(header, text="Salvar logs", width=110,
                      command=self._save_logs).pack(side="right", padx=4)
        ctk.CTkButton(header, text="Limpar", width=90,
                      command=self._clear).pack(side="right", padx=4)

        self.textbox = ctk.CTkTextbox(self, font=ctk.CTkFont(**MONO_FONT), wrap="word")
        self.textbox.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        for level, color in LOG_COLORS.items():
            self.textbox.tag_config(level, foreground=color)
        self.textbox.configure(state="disabled")

    def on_show(self) -> None:
        """Start polling the shared log queue (idempotent)."""
        if not self._polling:
            self._polling = True
            self._poll()

    def _poll(self) -> None:
        try:
            while True:
                item = self.app.log_queue.get_nowait()
                self._append(item.get("level", "INFO"), item.get("message", ""))
        except Exception:
            pass
        self.after(100, self._poll)

    def _append(self, level: str, message: str) -> None:
        tag = level if level in LOG_COLORS else "INFO"
        self.textbox.configure(state="normal")
        self.textbox.insert("end", message + "\n", tag)
        self._trim()
        self.textbox.see("end")
        self.textbox.configure(state="disabled")

    def _trim(self) -> None:
        try:
            lines = int(self.textbox.index("end-1c").split(".")[0])
        except (ValueError, AttributeError):
            return
        if lines > MAX_LINES:
            self.textbox.delete("1.0", f"end-{MAX_LINES - 1000}l")

    def _clear(self) -> None:
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")

    def _save_logs(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Salvar logs",
            defaultextension=".txt",
            initialfile=f"newsletter_logs_{datetime.now():%Y%m%d_%H%M%S}.txt",
            filetypes=[("Texto", "*.txt"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.textbox.get("1.0", "end-1c"))
        except OSError as e:
            logging.getLogger(__name__).error(f"Could not save logs: {e}")
