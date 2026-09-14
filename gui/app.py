# gui/app.py
"""Main CustomTkinter application window."""
import logging
import queue

import customtkinter as ctk

from core.config_manager import PROVIDERS, ConfigManager
from core.task_runner import QueueHandler
from gui.components.sidebar import Sidebar
from gui.components.status_bar import StatusBar
from gui.frames.home_frame import HomeFrame
from gui.frames.log_frame import LogFrame
from gui.frames.results_frame import ResultsFrame
from gui.frames.scraper_frame import ScraperFrame
from gui.frames.settings_frame import SettingsFrame
from gui.theme.colors import APPEARANCE_MODE, APP_GEOMETRY, APP_MINSIZE, APP_TITLE, COLOR_THEME

logger = logging.getLogger(__name__)


class App(ctk.CTk):
    """Root window: sidebar + dynamic content area + status bar.

    Owns the shared config, the GUI queues, and the root-log handler so
    every log record is visible in the Logs screen.
    """

    def __init__(self, config_manager: ConfigManager | None = None) -> None:
        ctk.set_appearance_mode(APPEARANCE_MODE)
        ctk.set_default_color_theme(COLOR_THEME)
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(APP_GEOMETRY)
        self.minsize(*APP_MINSIZE)

        self.config_manager = config_manager or ConfigManager()
        self.config = self.config_manager.load()

        self.progress_queue: queue.Queue = queue.Queue()
        self.log_queue: queue.Queue = queue.Queue()
        handler = QueueHandler(self.log_queue)
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logging.getLogger().addHandler(handler)

        self.sidebar = Sidebar(self, on_navigate=self.show_frame)
        self.sidebar.pack(side="left", fill="y")

        self.status_bar = StatusBar(self)
        self.status_bar.pack(side="bottom", fill="x")

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(side="left", fill="both", expand=True)

        self.frames = {
            "home": HomeFrame(self.container, self),
            "settings": SettingsFrame(self.container, self),
            "scraper": ScraperFrame(self.container, self),
            "results": ResultsFrame(self.container, self),
            "logs": LogFrame(self.container, self),
        }
        self._current: str | None = None
        self.refresh_provider_status()
        self.show_frame("home")

    def show_frame(self, frame_name: str) -> None:
        """Display ``frame_name``; the previous frame auto-saves via on_hide."""
        if frame_name not in self.frames:
            logger.error(f"Unknown frame: {frame_name}")
            return
        if self._current is not None and self._current != frame_name:
            previous = self.frames[self._current]
            if hasattr(previous, "on_hide"):
                previous.on_hide()
        for frame in self.frames.values():
            frame.pack_forget()
        frame = self.frames[frame_name]
        frame.pack(fill="both", expand=True)
        self._current = frame_name
        self.sidebar.set_active(frame_name)
        if hasattr(frame, "on_show"):
            frame.on_show()

    def save_config(self) -> None:
        """Persist the in-memory config to disk."""
        self.config_manager.save(self.config)

    def refresh_provider_status(self) -> None:
        """Update the status-bar provider summary from the current config."""
        provider_key = self.config.get("provider", "groq")
        name = PROVIDERS.get(provider_key, {}).get("name", provider_key)
        model = self.config.get("model", "") or PROVIDERS.get(provider_key, {}).get(
            "default_model", "")
        has_key = bool(self.config_manager.get_api_key(provider_key))
        state = "🔑" if has_key else "⚠️ sem chave"
        self.status_bar.set_provider(f"{name} · {model} · {state}".strip(" ·"))
