# gui/frames/results_frame.py
"""Browse the consolidated database (documents-data.json)."""
import csv
import json
import logging
import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.utils import APP_ROOT, DOCUMENTS_JSON
from gui.theme.colors import NORMAL_FONT, SECTION_FONT, SMALL_FONT, TITLE_FONT

CLASS_DOTS = {
    "Technological": "🔵",
    "Business": "🟢",
    "Scientific": "🟡",
    "Tecnológico": "🔵",
    "Negócios": "🟢",
    "Científico": "🟡",
}


class ResultsFrame(ctk.CTkFrame):
    """Article list (left) + selected-article details (right)."""

    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.articles: list = []

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkLabel(header, text="📊 Resultados",
                     font=ctk.CTkFont(**TITLE_FONT)).pack(side="left")
        self.summary_label = ctk.CTkLabel(header, text="",
                                          font=ctk.CTkFont(**NORMAL_FONT))
        self.summary_label.pack(side="left", padx=16)

        panes = ctk.CTkFrame(self, fg_color="transparent")
        panes.pack(fill="both", expand=True, padx=12, pady=8)
        panes.columnconfigure(0, weight=1)
        panes.columnconfigure(1, weight=2)
        panes.rowconfigure(0, weight=1)

        left = ctk.CTkFrame(panes)
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=4)
        ctk.CTkLabel(left, text="Lista de Artigos",
                     font=ctk.CTkFont(**SECTION_FONT)).pack(anchor="w", padx=12, pady=(10, 4))
        self.list_box = ctk.CTkScrollableFrame(left)
        self.list_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        right = ctk.CTkFrame(panes)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=4)
        ctk.CTkLabel(right, text="Detalhes do Artigo Selecionado",
                     font=ctk.CTkFont(**SECTION_FONT)).pack(anchor="w", padx=12, pady=(10, 4))
        self.details_box = ctk.CTkTextbox(right, wrap="word")
        self.details_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.details_box.configure(state="disabled")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(pady=(0, 16))
        ctk.CTkButton(footer, text="📂 Abrir Pasta de Dados",
                      command=self._open_data_dir).pack(side="left", padx=8)
        ctk.CTkButton(footer, text="📋 Exportar CSV",
                      command=self._export_csv).pack(side="left", padx=8)

    def on_show(self) -> None:
        """Reload the database from disk."""
        self.articles = self._load_articles()
        for child in self.list_box.winfo_children():
            child.destroy()
        if not self.articles:
            self.summary_label.configure(text="Nenhum resultado ainda. Execute o pipeline.")
            self._show_details(None)
            return
        try:
            mtime = datetime.fromtimestamp(Path(DOCUMENTS_JSON).stat().st_mtime)
            updated = mtime.strftime("%Y-%m-%d %H:%M")
        except OSError:
            updated = "—"
        self.summary_label.configure(
            text=f"Base: documents-data.json ({len(self.articles)} artigos) · {updated}")
        for index, article in enumerate(self.articles):
            dot = CLASS_DOTS.get((article.get("classification") or [""])[0], "⚪")
            title = (article.get("newsletter") or article.get("title") or "(sem título)")
            ctk.CTkButton(
                self.list_box, text=f"{dot} {title}", anchor="w",
                fg_color="transparent",
                command=lambda i=index: self._show_details(self.articles[i]),
            ).pack(fill="x", padx=4, pady=1)
        self._show_details(self.articles[0])

    @staticmethod
    def _load_articles() -> list:
        try:
            with open(DOCUMENTS_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def _show_details(self, article: dict | None) -> None:
        self.details_box.configure(state="normal")
        self.details_box.delete("1.0", "end")
        if article is None:
            self.details_box.insert("end", "Nenhum artigo selecionado.")
        else:
            self.details_box.insert("end", self._format_article(article))
        self.details_box.configure(state="disabled")

    @staticmethod
    def _format_article(article: dict) -> str:
        weights = article.get("classification_weight", {}) or {}
        classification = article.get("classification") or list(weights)
        lines = [
            f"Título: {article.get('newsletter') or article.get('title', '')}",
            f"Fonte: {article.get('source', '')}",
            f"Data: {article.get('date') or article.get('published', '')}",
            f"URL: {article.get('url', '')}",
            "Classificação: " + (", ".join(
                f"{name} ({weights.get(name, 0)})" for name in classification) or "—"),
            f"Score: {article.get('total_score', '—')}",
            "",
            f"Resumo: {article.get('summary', '')}",
            "",
            "Pontos-chave:",
        ]
        for point in article.get("key_points", []) or []:
            lines.append(f"• {point}")
        orgs = article.get("organization", []) or []
        if orgs:
            lines += ["", "Organizações:"]
            lines += [f"• {o.get('name', '')} ({o.get('location', '')})" for o in orgs]
        events = article.get("event", []) or []
        if events:
            lines += ["", "Eventos:"]
            lines += [f"• {e.get('name', '')} — {e.get('location', '')} [{e.get('type', '')}]"
                      for e in events]
        countries = article.get("related_country", []) or []
        lines += ["", f"Países: {', '.join(countries) if countries else '—'}"]
        return "\n".join(lines)

    @staticmethod
    def _open_data_dir() -> None:
        path = str(APP_ROOT)
        try:
            if platform.system() == "Windows":
                os.startfile(path)  # noqa: S606
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except (OSError, subprocess.SubprocessError) as e:
            logging.getLogger(__name__).error(f"Could not open data dir: {e}")

    def _export_csv(self) -> None:
        if not self.articles:
            return
        path = filedialog.asksaveasfilename(
            title="Exportar CSV",
            defaultextension=".csv",
            initialfile="newsletter_export.csv",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["title", "source", "date", "score", "classification",
                                 "summary", "url"])
                for article in self.articles:
                    weights = article.get("classification_weight", {}) or {}
                    classification = article.get("classification") or list(weights)
                    writer.writerow([
                        article.get("newsletter") or article.get("title", ""),
                        article.get("source", ""),
                        article.get("date") or article.get("published", ""),
                        article.get("total_score", ""),
                        "; ".join(f"{n} ({weights.get(n, 0)})" for n in classification),
                        article.get("summary", ""),
                        article.get("url", ""),
                    ])
        except OSError as e:
            logging.getLogger(__name__).error(f"Could not export CSV: {e}")
