# main.py
"""Desktop entry point: launch the Newsletter Tool GUI."""
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk

from core import paths
from gui.app import App
from gui.theme.colors import APPEARANCE_MODE, COLOR_THEME


def main() -> None:
    log_dir = paths.data_root()
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(str(log_dir), "console.txt"), encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    logging.getLogger(__name__).info(f"QuIIN iniciado; pasta de dados: {log_dir}")
    if os.environ.get("QUIIN_SMOKE") == "1":
        try:
            from core.selfcheck import run_self_check

            run_self_check()
        except Exception:
            logging.getLogger(__name__).exception("QUIIN SMOKE FAILED")
            sys.exit(1)
        sys.exit(0)
    ctk.set_appearance_mode(APPEARANCE_MODE)
    ctk.set_default_color_theme(COLOR_THEME)
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
