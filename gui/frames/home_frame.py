# gui/frames/home_frame.py
"""Dashboard: counters, status, and quick-start guide."""
import json
from datetime import datetime
from pathlib import Path

import customtkinter as ctk

from core.config_manager import PROVIDERS
from core.utils import ARTICLES_JSON, DOCUMENTS_JSON
from gui.theme.colors import NORMAL_FONT, SECTION_FONT, TITLE_FONT


class HomeFrame(ctk.CTkFrame):
    """Landing screen with live counters refreshed on every visit."""

    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app

        ctk.CTkLabel(self, text="🏠 Newsletter Tool",
                     font=ctk.CTkFont(**TITLE_FONT)).pack(pady=(24, 4))
        ctk.CTkLabel(
            self,
            text="Bem-vindo à Ferramenta de Processamento de Notícias",
            font=ctk.CTkFont(**NORMAL_FONT),
        ).pack(pady=(0, 20))

        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.pack(pady=8)
        self.card_values: dict[str, ctk.CTkLabel] = {}
        for i, (key, caption) in enumerate(
            (("articles", "Artigos"), ("portals", "Portais"), ("provider", "Provedor"))
        ):
            card = ctk.CTkFrame(cards, width=160, height=110)
            card.grid(row=0, column=i, padx=10)
            card.grid_propagate(False)
            value = ctk.CTkLabel(card, text="—", font=ctk.CTkFont(size=26, weight="bold"))
            value.pack(expand=True)
            ctk.CTkLabel(card, text=caption, font=ctk.CTkFont(**NORMAL_FONT)).pack(pady=(0, 10))
            self.card_values[key] = value

        self.status_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(**NORMAL_FONT))
        self.status_label.pack(pady=(16, 4))
        self.last_run_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(**NORMAL_FONT))
        self.last_run_label.pack(pady=4)

        guide = ctk.CTkFrame(self)
        guide.pack(pady=16, padx=24, fill="x")
        ctk.CTkLabel(guide, text="Início Rápido",
                     font=ctk.CTkFont(**SECTION_FONT)).pack(anchor="w", padx=16, pady=(12, 4))
        steps = (
            "1. Configure seu provedor de IA em ⚙️ Configurações\n"
            "2. Selecione os portais desejados\n"
            "3. Clique em 🚀 Execução para iniciar\n"
            "4. Acompanhe o progresso em tempo real\n"
            "5. Veja os resultados em 📊 Resultados"
        )
        ctk.CTkLabel(guide, text=steps, justify="left",
                     font=ctk.CTkFont(**NORMAL_FONT)).pack(anchor="w", padx=16, pady=(0, 12))

    def on_show(self) -> None:
        """Refresh counters from disk and config."""
        config = self.app.config
        self.card_values["articles"].configure(text=str(self._count_final_articles()))
        active = sum(1 for on in config.get("portals", {}).values() if on)
        self.card_values["portals"].configure(text=str(active))
        provider_key = config.get("provider", "groq")
        self.card_values["provider"].configure(
            text=PROVIDERS.get(provider_key, {}).get("name", provider_key))
        has_key = bool(self.app.config_manager.get_api_key(provider_key))
        ready = active > 0 and has_key
        self.status_label.configure(
            text=("Status: Pronto para execução" if ready
                  else "Status: Configure a API key e ao menos um portal"))
        last_run = config.get("last_run", "")
        self.last_run_label.configure(
            text=f"Última execução: {self._format_last_run(last_run)}" if last_run
            else "Última execução: —")

    @staticmethod
    def _count_final_articles() -> int:
        for path in (DOCUMENTS_JSON, ARTICLES_JSON):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return len(data)
            except (OSError, ValueError):
                continue
        return 0

    @staticmethod
    def _format_last_run(last_run: str) -> str:
        try:
            return datetime.fromisoformat(last_run).strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            return last_run
