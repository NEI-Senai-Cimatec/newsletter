# main.py
"""Desktop entry point: launch the Newsletter Tool GUI."""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk

from gui.app import App
from gui.theme.colors import APPEARANCE_MODE, COLOR_THEME

APP_ROOT = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(APP_ROOT, "console.txt"), encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    ctk.set_appearance_mode(APPEARANCE_MODE)
    ctk.set_default_color_theme(COLOR_THEME)
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
