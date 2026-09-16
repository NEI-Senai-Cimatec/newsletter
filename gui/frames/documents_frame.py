# gui/frames/documents_frame.py
"""QuIIN documentos: lista paginada, detalhe com indicadores e notícia manual."""
import json
import logging
import queue
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core import repository
from core.audit import log_event
from core.briefs import build_client_from_config
from core.exports import build_newsletter, export_pdf, export_word
from core.repository import AREAS, add_manual_news
from core.scoring import INDICADORES, LABELS, area_of, indicators, load_weights, relevance
from core.utils import DOCUMENTS_JSON
from gui.theme.colors import NORMAL_FONT, SECTION_FONT, SMALL_FONT, TITLE_FONT

logger = logging.getLogger(__name__)

NEWSLETTER_TITLE = "GLOBAL QUANTUM INTELLIGENCE – QuIIN"
PAGE_SIZE = 20


class DocumentsFrame(ctk.CTkFrame):
    """Lista de documentos (20 por página) + detalhe + notícia manual.

    Usa a lista cacheada do shell (``app.refresh_documents()`` /
    ``app._cached_docs``); nunca lê o JSON diretamente na thread Tk.
    Exportações PDF/WORD rodam em worker threads com aviso via fila.
    """

    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.filtered: list = []
        self.shown: int = PAGE_SIZE
        self.selected: dict | None = None
        self._search_docs: list | None = None
        self._weights: dict = load_weights()
        self._ui_queue: queue.Queue = queue.Queue()

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkLabel(header, text="📄 Documentos",
                     font=ctk.CTkFont(**TITLE_FONT)).pack(side="left")
        self.add_button = ctk.CTkButton(header, text="Adicionar Notícia",
                                        command=self._open_add_dialog)
        self.add_button.pack(side="right")
        # Adicionar Notícia é admin-only (capability "add_news"): gating
        # manual via set_gated no on_show, como o Editar do dashboard.

        self.status_label = ctk.CTkLabel(self, text="",
                                         font=ctk.CTkFont(**NORMAL_FONT))
        self.status_label.pack(anchor="w", padx=20, pady=(0, 4))

        panes = ctk.CTkFrame(self, fg_color="transparent")
        panes.pack(fill="both", expand=True, padx=12, pady=8)
        panes.columnconfigure(0, weight=1)
        panes.columnconfigure(1, weight=2)
        panes.rowconfigure(0, weight=1)

        left = ctk.CTkFrame(panes)
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=4)
        ctk.CTkLabel(left, text="Lista de Documentos",
                     font=ctk.CTkFont(**SECTION_FONT)).pack(anchor="w", padx=12,
                                                            pady=(10, 2))
        ctk.CTkLabel(left, text="Data | Fonte | Área | Título | Relevância",
                     font=ctk.CTkFont(**SMALL_FONT)).pack(anchor="w", padx=12,
                                                          pady=(0, 4))
        self.list_box = ctk.CTkScrollableFrame(left)
        self.list_box.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self.count_label = ctk.CTkLabel(left, text="",
                                        font=ctk.CTkFont(**SMALL_FONT))
        self.count_label.pack(anchor="w", padx=12, pady=(0, 2))
        self.more_button = ctk.CTkButton(left, text="Mostrar mais documentos",
                                         command=self._show_more)
        self.more_button.pack(fill="x", padx=8, pady=(0, 8))

        right = ctk.CTkFrame(panes)
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=4)
        ctk.CTkLabel(right, text="Detalhes do Documento Selecionado",
                     font=ctk.CTkFont(**SECTION_FONT)).pack(anchor="w", padx=12,
                                                            pady=(10, 4))
        self.details_box = ctk.CTkTextbox(right, wrap="word")
        self.details_box.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self.details_box.configure(state="disabled")
        export_row = ctk.CTkFrame(right, fg_color="transparent")
        export_row.pack(fill="x", padx=8, pady=(0, 8))
        self.pdf_button = ctk.CTkButton(export_row, text="Exportar PDF",
                                        command=self._export_pdf)
        self.pdf_button.pack(side="left", padx=(0, 8))
        self.word_button = ctk.CTkButton(export_row, text="Exportar WORD",
                                         command=self._export_word)
        self.word_button.pack(side="left", padx=8)

        self.app.register_export_button("documents", self.pdf_button, "export")
        self.app.register_export_button("documents", self.word_button, "export")

        self.after(100, self._poll_ui)

    # -- ciclo de vida --------------------------------------------------
    def on_show(self) -> None:
        """Recarrega cache/pesos, reaplica gating e renderiza a página."""
        try:
            self.app.refresh_documents()
        except Exception:
            logger.debug("refresh_documents failed", exc_info=True)
        try:
            self._weights = load_weights()
        except Exception:
            logger.debug("load_weights failed", exc_info=True)
        try:
            self.app.set_gated(
                self.add_button,
                self.app.has_capability("add_news"),
                "Sem permissão: requer 'add_news'.")
        except Exception:
            logger.debug("Add gating skip", exc_info=True)
        if self._search_docs is not None:
            base = list(self._search_docs)
        else:
            base = self._cached_docs()
        try:
            base = repository.sort_documents(base, "date", desc=True)
        except Exception:
            logger.debug("sort skip", exc_info=True)
        self.filtered = base
        self.shown = PAGE_SIZE
        self._render_page()
        if self.filtered:
            keep = None
            if self.selected is not None:
                for doc in self.filtered:
                    if doc.get("hash") == self.selected.get("hash"):
                        keep = doc
                        break
            self._show_detail(keep or self.filtered[0])
        else:
            self._show_detail(None)

    def apply_search(self, docs: list) -> None:
        """Recebe a lista filtrada global do shell e renderiza a página."""
        self._search_docs = list(docs)
        try:
            ordered = repository.sort_documents(list(docs), "date", desc=True)
        except Exception:
            ordered = list(docs)
        self.filtered = ordered
        self.shown = PAGE_SIZE
        self._render_page()
        if self.filtered:
            self._show_detail(self.filtered[0])
        else:
            self._show_detail(None)

    # -- dados ----------------------------------------------------------
    def _cached_docs(self) -> list:
        try:
            docs = getattr(self.app, "_cached_docs", [])
            return list(docs) if isinstance(docs, list) else []
        except Exception:
            return []

    def _doc_relevance(self, doc: dict) -> int:
        try:
            return relevance(doc, self._weights)
        except (ValueError, AttributeError, TypeError):
            return 0

    def _current_user(self) -> str:
        try:
            return str((self.app.session or {}).get("username", "?"))
        except Exception:
            return "?"

    # -- paginação ------------------------------------------------------
    def _render_page(self) -> None:
        for child in self.list_box.winfo_children():
            child.destroy()
        page = self.filtered[: self.shown]
        for doc in page:
            date = doc.get("date") or doc.get("published") or "—"
            source = doc.get("source", "") or "—"
            try:
                area = area_of(doc)
            except Exception:
                area = "Outros"
            title = doc.get("newsletter") or doc.get("title", "(sem título)")
            rel = self._doc_relevance(doc)
            text = f"{date} | {source} | {area} | {title} | {rel}"
            ctk.CTkButton(self.list_box, text=text,
                          anchor="w", fg_color="transparent",
                          command=lambda d=doc: self._show_detail(d)).pack(
                              fill="x", padx=4, pady=1)
        remaining = max(0, len(self.filtered) - self.shown)
        self.more_button.configure(
            text=f"Mostrar mais documentos ({remaining} restantes)",
            state="normal" if self.shown < len(self.filtered) else "disabled")
        shown_now = min(self.shown, len(self.filtered))
        self.count_label.configure(
            text=f"Exibindo {shown_now} de {len(self.filtered)} documento(s).")

    def _show_more(self) -> None:
        self.shown += PAGE_SIZE
        self._render_page()

    # -- detalhe --------------------------------------------------------
    def _show_detail(self, doc: dict | None) -> None:
        self.selected = doc
        self.details_box.configure(state="normal")
        self.details_box.delete("1.0", "end")
        if doc is None:
            self.details_box.insert("end", "Nenhum documento selecionado.")
        else:
            self.details_box.insert("end", self._format_detail(doc))
        self.details_box.configure(state="disabled")

    def _format_detail(self, doc: dict) -> str:
        try:
            inds = indicators(doc)
        except Exception:
            inds = {k: 0.0 for k in INDICADORES}
        rel = self._doc_relevance(doc)
        try:
            area = area_of(doc)
        except Exception:
            area = "Outros"
        lines = [
            f"Título: {doc.get('newsletter') or doc.get('title', '')}",
            f"Fonte: {doc.get('source', '')}",
            f"Data: {doc.get('date') or doc.get('published', '')}",
            f"Área: {area}",
            f"Relevância: {rel}",
            f"URL: {doc.get('url', '')}",
            "",
            f"Resumo: {doc.get('summary', '')}",
            "",
            "Indicadores (I_k e contribuição w_k·I_k):",
        ]
        for key in INDICADORES:
            ik = float(inds.get(key, 0.0))
            wk = float(self._weights.get(key, 0))
            contrib = wk * ik
            lines.append(
                f"• {LABELS[key]}: I_k={ik:.2f}, w_k·I_k={contrib:.2f}")
        lines += ["", "Pontos-chave:"]
        for point in doc.get("key_points", []) or []:
            lines.append(f"• {point}")
        orgs = doc.get("organization", []) or []
        if orgs:
            lines += ["", "Organizações:"]
            for org in orgs:
                lines.append(
                    f"• {(org or {}).get('name', '')} "
                    f"({(org or {}).get('location', '')})")
        else:
            lines += ["", "Organizações: —"]
        events = doc.get("event", []) or []
        if events:
            lines += ["", "Eventos:"]
            for event in events:
                lines.append(
                    f"• {(event or {}).get('name', '')} — "
                    f"{(event or {}).get('location', '')} "
                    f"[{(event or {}).get('type', '')}]")
        else:
            lines += ["", "Eventos: —"]
        breakthroughs = doc.get("breakthrough", []) or []
        if breakthroughs:
            lines += ["", "Avanços:"]
            for item in breakthroughs:
                lines.append(f"• {item}")
        else:
            lines += ["", "Avanços: —"]
        financial = doc.get("financial_activity", []) or []
        if financial:
            lines += ["", "Atividades financeiras:"]
            for item in financial:
                if isinstance(item, dict):
                    lines.append(
                        f"• {item.get('description', '')} "
                        f"[{item.get('currency', '')}]")
                else:
                    lines.append(f"• {item}")
        else:
            lines += ["", "Atividades financeiras: —"]
        countries = doc.get("related_country", []) or []
        lines += ["", f"Países: {', '.join(countries) if countries else '—'}"]
        return "\n".join(lines)

    # -- notícia manual (admin) -----------------------------------------
    def _open_add_dialog(self) -> None:
        if not self.app.has_capability("add_news"):
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title("Adicionar Notícia")
        dialog.geometry("520x560")
        ctk.CTkLabel(dialog, text="Adicionar Notícia",
                     font=ctk.CTkFont(**SECTION_FONT)).pack(padx=20,
                                                            pady=(12, 4))
        ctk.CTkLabel(dialog, text="Título").pack(anchor="w", padx=20)
        title_entry = ctk.CTkEntry(dialog)
        title_entry.pack(padx=20, pady=(0, 6), fill="x")
        ctk.CTkLabel(dialog, text="URL").pack(anchor="w", padx=20)
        url_entry = ctk.CTkEntry(dialog)
        url_entry.pack(padx=20, pady=(0, 6), fill="x")
        ctk.CTkLabel(dialog, text="Área").pack(anchor="w", padx=20)
        area_menu = ctk.CTkOptionMenu(dialog, values=list(AREAS))
        area_menu.set(AREAS[0])
        area_menu.pack(padx=20, pady=(0, 6), fill="x")
        ctk.CTkLabel(dialog, text="Data (AAAA-MM-DD)").pack(anchor="w",
                                                            padx=20)
        date_entry = ctk.CTkEntry(dialog)
        date_entry.pack(padx=20, pady=(0, 6), fill="x")
        ctk.CTkLabel(dialog, text="Resumo").pack(anchor="w", padx=20)
        summary_box = ctk.CTkTextbox(dialog, height=120)
        summary_box.pack(padx=20, pady=(0, 6), fill="x")
        error = ctk.CTkLabel(dialog, text="", text_color="#F85149")
        error.pack(padx=20, pady=2)

        def _save() -> None:
            title = title_entry.get().strip()
            if not title:
                error.configure(text="Título é obrigatório.")
                return
            try:
                summary = summary_box.get("1.0", "end").strip()
            except Exception:
                summary = ""
            fields = {
                "title": title,
                "url": url_entry.get().strip(),
                "area": area_menu.get(),
                "date": date_entry.get().strip(),
                "summary": summary,
            }
            try:
                record = add_manual_news(fields)
            except Exception as exc:
                error.configure(text=f"Não foi possível criar: {exc}")
                return
            try:
                self._persist_manual(record)
            except (OSError, ValueError) as exc:
                error.configure(text=f"Não foi possível salvar: {exc}")
                return
            try:
                log_event(self._current_user(), "add_news",
                          f"título={title}")
            except Exception:
                logger.debug("Audit skip", exc_info=True)
            try:
                dialog.destroy()
            except Exception:
                pass
            try:
                self.app.refresh_documents()
            except Exception:
                logger.debug("refresh after manual failed", exc_info=True)
            if self._search_docs is not None:
                self._search_docs = None
            try:
                base = repository.sort_documents(self._cached_docs(), "date",
                                                 desc=True)
            except Exception:
                base = self._cached_docs()
            self.filtered = base
            self.shown = PAGE_SIZE
            self._render_page()
            for doc in self.filtered:
                if doc.get("hash") == record.get("hash"):
                    self._show_detail(doc)
                    break
            self._notify("Notícia manual adicionada.")

        row = ctk.CTkFrame(dialog, fg_color="transparent")
        row.pack(padx=20, pady=10, fill="x")
        ctk.CTkButton(row, text="Salvar", command=_save).pack(side="left",
                                                              padx=(0, 8))
        ctk.CTkButton(row, text="Cancelar", fg_color="transparent",
                      command=dialog.destroy).pack(side="left")

    def _persist_manual(self, record: dict) -> None:
        target = Path(DOCUMENTS_JSON)
        try:
            with open(target, "r", encoding="utf-8") as f:
                data = json.load(f)
            docs = data if isinstance(data, list) else []
        except (OSError, ValueError):
            docs = []
        docs.append(record)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(docs, f, indent=2, ensure_ascii=False)

    # -- exportação por documento ---------------------------------------
    def _export_pdf(self) -> None:
        if self.selected is None:
            self._notify("Nenhum documento selecionado.")
            return
        path = filedialog.asksaveasfilename(
            title="Exportar documento (PDF)",
            defaultextension=".pdf",
            initialfile="documento_quiin.pdf",
            filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")])
        if not path:
            return
        thread = threading.Thread(target=self._export_worker,
                                  args=(dict(self.selected),
                                        dict(self._weights), path, "pdf"),
                                  daemon=True)
        thread.start()

    def _export_word(self) -> None:
        if self.selected is None:
            self._notify("Nenhum documento selecionado.")
            return
        path = filedialog.asksaveasfilename(
            title="Exportar documento (WORD)",
            defaultextension=".docx",
            initialfile="documento_quiin.docx",
            filetypes=[("Word", "*.docx"), ("Todos", "*.*")])
        if not path:
            return
        thread = threading.Thread(target=self._export_worker,
                                  args=(dict(self.selected),
                                        dict(self._weights), path, "word"),
                                  daemon=True)
        thread.start()

    def _export_worker(self, doc: dict, weights: dict, path: str,
                       kind: str) -> None:
        try:
            try:
                client = build_client_from_config(self.app.config,
                                                  self.app.config_manager)
            except Exception:
                client = None
            structure = build_newsletter(
                [doc], weights, "documento", {"title": NEWSLETTER_TITLE},
                api_client=client,
                progress_cb=lambda i, n: self._notify(
                    f"Condensando resumo {i}/{n}..."))
            self._notify("Newsletter gerada: 1 documentos (documento).")
            if kind == "word":
                export_word(structure, path)
            else:
                export_pdf(structure, path)
            log_event(self._current_user(), "generate_newsletter",
                      "modo=documento documentos=1")
            self._notify(f"Documento exportado para {path}.")
        except Exception as exc:
            logger.debug("Document export failed", exc_info=True)
            self._notify(f"Falha ao exportar documento: {exc}")

    # -- fila Tk ---------------------------------------------------------
    def _notify(self, text: str) -> None:
        """Atualização de status thread-safe (workers nunca tocam Tk)."""
        self._ui_queue.put(("status", text))

    def _poll_ui(self) -> None:
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        try:
            while True:
                item = self._ui_queue.get_nowait()
                if item[0] == "status":
                    self._set_status_safe(item[1])
        except queue.Empty:
            pass
        except Exception:
            logger.debug("Documents UI poll failed", exc_info=True)
        try:
            if self.winfo_exists():
                self.after(100, self._poll_ui)
        except Exception:
            pass

    def _set_status_safe(self, text: str) -> None:
        try:
            if self.winfo_exists():
                self.status_label.configure(text=text)
        except Exception:
            pass
        try:
            self.app.status_bar.set_status(text)
        except Exception:
            pass
