# gui/frames/dashboard_frame.py
"""QuIIN analytics dashboard: cards, charts, filters, table, weights, newsletter."""
import logging
import queue
import tempfile
import threading
from pathlib import Path
from tkinter import filedialog

import matplotlib

matplotlib.use("Agg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import customtkinter as ctk

from core import repository
from core.audit import log_event
from core.config_manager import PROVIDERS
from core.exports import build_newsletter, export_pdf, print_pdf, share_package
from core.repository import AREAS
from core.scoring import INDICADORES, LABELS, load_weights, relevance, save_weights, validate_weights
from gui.theme.colors import MONO_FONT, NORMAL_FONT, SECTION_FONT, SMALL_FONT, TITLE_FONT

logger = logging.getLogger(__name__)

NEWSLETTER_TITLE = "GLOBAL QUANTUM INTELLIGENCE – QuIIN"
TABLE_PAGE = 100

SORT_COLUMNS = (("date", "Data"), ("area", "Área"), ("relevance", "Relevância"))


class DashboardFrame(ctk.CTkFrame):
    """Analytics dashboard refreshed on every visit.

    Heavy stats run in a worker thread; all Tk/matplotlib rendering
    happens on the main thread via ``after()``.
    """

    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._search_docs: list | None = None
        self._weights: dict = load_weights()
        self._sort_key = "relevance"
        self._sort_desc: dict[str, bool] = {"date": True, "area": False,
                                            "relevance": True}
        self._seq = 0
        self._ui_queue: queue.Queue = queue.Queue()  # workers -> GUI thread

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        ctk.CTkLabel(scroll, text="📊 Dashboard",
                     font=ctk.CTkFont(**TITLE_FONT)).pack(anchor="w", padx=8,
                                                          pady=(16, 4))
        self.status_label = ctk.CTkLabel(scroll, text="",
                                         font=ctk.CTkFont(**NORMAL_FONT))
        self.status_label.pack(anchor="w", padx=8, pady=(0, 8))

        # ---- Cards ----
        cards = ctk.CTkFrame(scroll, fg_color="transparent")
        cards.pack(pady=8, fill="x", padx=8)
        self.card_values: dict[str, ctk.CTkLabel] = {}
        for i, (key, caption) in enumerate(
            (("docs", "Documentos"), ("portals", "Portais ativos"),
             ("provider", "Provedor ativo"))
        ):
            card = ctk.CTkFrame(cards, width=200, height=110)
            card.grid(row=0, column=i, padx=10, sticky="ew")
            card.grid_propagate(False)
            value = ctk.CTkLabel(card, text="—",
                                 font=ctk.CTkFont(size=26, weight="bold"))
            value.pack(expand=True)
            ctk.CTkLabel(card, text=caption,
                         font=ctk.CTkFont(**NORMAL_FONT)).pack(pady=(0, 10))
            self.card_values[key] = value
        cards.columnconfigure((0, 1, 2), weight=1)

        # ---- Charts ----
        charts = ctk.CTkFrame(scroll, fg_color="transparent")
        charts.pack(fill="x", padx=8, pady=8)
        charts.columnconfigure((0, 1), weight=1)
        bar_outer = ctk.CTkFrame(charts)
        bar_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        ctk.CTkLabel(bar_outer, text="Documentos por mês e área",
                     font=ctk.CTkFont(**SECTION_FONT)).pack(anchor="w", padx=12,
                                                            pady=(10, 2))
        self.bar_box = ctk.CTkFrame(bar_outer, fg_color="transparent",
                                    height=320)
        self.bar_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        donut_outer = ctk.CTkFrame(charts)
        donut_outer.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        ctk.CTkLabel(donut_outer, text="Participação por área (%)",
                     font=ctk.CTkFont(**SECTION_FONT)).pack(anchor="w", padx=12,
                                                            pady=(10, 2))
        self.donut_box = ctk.CTkFrame(donut_outer, fg_color="transparent",
                                      height=320)
        self.donut_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # ---- Advanced stats + countries ----
        mid = ctk.CTkFrame(scroll, fg_color="transparent")
        mid.pack(fill="x", padx=8, pady=8)
        mid.columnconfigure((0, 1), weight=1)
        adv_outer = ctk.CTkFrame(mid)
        adv_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 4))
        ctk.CTkLabel(adv_outer, text="Estatística avançada",
                     font=ctk.CTkFont(**SECTION_FONT)).pack(anchor="w", padx=12,
                                                            pady=(10, 2))
        self._check_vars: dict[str, ctk.BooleanVar] = {}
        for key in INDICADORES:
            var = ctk.BooleanVar(value=True)
            self._check_vars[key] = var
            ctk.CTkCheckBox(adv_outer, text=LABELS[key], variable=var,
                            command=self._on_filter_change,
                            font=ctk.CTkFont(**NORMAL_FONT)).pack(
                                anchor="w", padx=12, pady=2)
        ctk.CTkLabel(
            adv_outer,
            text="Desmarcar zera o peso do indicador na visualização.",
            font=ctk.CTkFont(**SMALL_FONT)).pack(anchor="w", padx=12,
                                                 pady=(2, 8))
        loc_outer = ctk.CTkFrame(mid)
        loc_outer.grid(row=0, column=1, sticky="nsew", padx=(4, 0))
        ctk.CTkLabel(loc_outer, text="Localização das notícias",
                     font=ctk.CTkFont(**SECTION_FONT)).pack(anchor="w", padx=12,
                                                            pady=(10, 2))
        self.countries_box = ctk.CTkFrame(loc_outer, fg_color="transparent")
        self.countries_box.pack(fill="x", padx=12, pady=(0, 8))

        # ---- Table ----
        table_outer = ctk.CTkFrame(scroll)
        table_outer.pack(fill="both", expand=True, padx=8, pady=8)
        ctk.CTkLabel(table_outer, text="Documentos",
                     font=ctk.CTkFont(**SECTION_FONT)).pack(anchor="w", padx=12,
                                                            pady=(10, 2))
        header = ctk.CTkFrame(table_outer, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(0, 4))
        header.columnconfigure((0, 1, 2), weight=1)
        self._header_buttons: dict[str, ctk.CTkButton] = {}
        for col, (key, caption) in enumerate(SORT_COLUMNS):
            btn = ctk.CTkButton(header, text=caption, fg_color="transparent",
                                anchor="w",
                                command=lambda k=key: self._on_sort(k))
            btn.grid(row=0, column=col, sticky="ew", padx=2)
            self._header_buttons[key] = btn
        self.table_box = ctk.CTkTextbox(table_outer, height=220,
                                          font=ctk.CTkFont(**MONO_FONT))
        self.table_box.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self.table_box.configure(state="disabled")
        self.table_count = ctk.CTkLabel(table_outer, text="",
                                        font=ctk.CTkFont(**SMALL_FONT))
        self.table_count.pack(anchor="w", padx=12, pady=(0, 8))

        # ---- Weights ----
        weights_outer = ctk.CTkFrame(scroll)
        weights_outer.pack(fill="x", padx=8, pady=8)
        weights_head = ctk.CTkFrame(weights_outer, fg_color="transparent")
        weights_head.pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(weights_head, text="Índice de seleção multicritério",
                     font=ctk.CTkFont(**SECTION_FONT)).pack(side="left")
        self.edit_weights_button = ctk.CTkButton(weights_head, text="Editar",
                                                 width=90,
                                                 command=self._edit_weights)
        self.edit_weights_button.pack(side="right")
        self.weight_labels: dict[str, ctk.CTkLabel] = {}
        for key in INDICADORES:
            row = ctk.CTkLabel(weights_outer, text="",
                               font=ctk.CTkFont(**NORMAL_FONT))
            row.pack(anchor="w", padx=24, pady=1)
            self.weight_labels[key] = row

        # ---- Newsletter + Print/Share ----
        actions_outer = ctk.CTkFrame(scroll)
        actions_outer.pack(fill="x", padx=8, pady=(8, 16))
        ctk.CTkLabel(actions_outer, text="Gerar Newsletter",
                     font=ctk.CTkFont(**SECTION_FONT)).pack(anchor="w", padx=12,
                                                            pady=(10, 2))
        btn_row = ctk.CTkFrame(actions_outer, fg_color="transparent")
        btn_row.pack(fill="x", padx=12, pady=(0, 4))
        self.auto_button = ctk.CTkButton(btn_row, text="Automático",
                                         command=self._newsletter_auto)
        self.auto_button.pack(side="left", padx=(0, 8))
        self.custom_button = ctk.CTkButton(btn_row, text="Personalizado",
                                           command=self._newsletter_custom)
        self.custom_button.pack(side="left", padx=8)
        share_row = ctk.CTkFrame(actions_outer, fg_color="transparent")
        share_row.pack(fill="x", padx=12, pady=(4, 10))
        self.print_button = ctk.CTkButton(share_row, text="Print",
                                          command=self._print_dashboard)
        self.print_button.pack(side="left", padx=(0, 8))
        self.share_button = ctk.CTkButton(share_row, text="Share",
                                          command=self._share_dashboard)
        self.share_button.pack(side="left", padx=8)

        self.app.register_export_button("dashboard", self.print_button,
                                        "print")
        self.app.register_export_button("dashboard", self.share_button,
                                        "share")
        self.app.register_export_button("dashboard", self.auto_button,
                                        "generate_newsletter")
        self.app.register_export_button("dashboard", self.custom_button,
                                        "generate_newsletter")

        self._refresh_weight_labels()
        self._update_header_arrows()
        self.after(100, self._poll_ui)

    # -- lifecycle ------------------------------------------------------
    def on_show(self) -> None:
        """Refresh cards, weights and charts from the shell's cached docs."""
        try:
            self.app.refresh_documents()
        except Exception:
            logger.debug("refresh_documents failed", exc_info=True)
        self._weights = load_weights()
        self._refresh_cards()
        self._refresh_weight_labels()
        try:
            self.app.set_gated(
                self.edit_weights_button,
                self.app.has_capability("edit_weights"),
                "Sem permissão: requer 'edit_weights'.")
        except Exception:
            logger.debug("Edit gating skip", exc_info=True)
        self._schedule_refresh()

    def apply_search(self, docs: list) -> None:
        """Receive the shell's globally filtered list and refresh the view."""
        self._search_docs = list(docs)
        self._schedule_refresh()

    # -- data helpers ---------------------------------------------------
    def _cached_docs(self) -> list:
        try:
            docs = getattr(self.app, "_cached_docs", [])
            return list(docs) if isinstance(docs, list) else []
        except Exception:
            return []

    def _effective_docs(self) -> list:
        if self._search_docs is not None:
            return list(self._search_docs)
        return self._cached_docs()

    def _view_weights(self) -> dict:
        """Base weights with unchecked indicators zeroed, renormalized to 100."""
        checked = [k for k in INDICADORES if self._check_vars[k].get()]
        total = sum(self._weights.get(k, 0) for k in checked)
        if total <= 0:
            return {k: 0 for k in INDICADORES}
        view = {k: (round(self._weights.get(k, 0) * 100 / total)
                    if k in checked else 0)
                for k in INDICADORES}
        drift = 100 - sum(view.values())
        if drift and checked:
            biggest = max(checked, key=lambda k: self._weights.get(k, 0))
            view[biggest] += drift
        return view

    def _export_weights(self) -> dict:
        """Weights safe for relevance/export: view when valid, else base."""
        view = self._view_weights()
        if sum(view.values()) == 100:
            return view
        return dict(self._weights)

    @staticmethod
    def _view_relevance(doc: dict, weights: dict) -> int:
        if sum(weights.values()) <= 0:
            return 0
        try:
            return relevance(doc, weights)
        except ValueError:
            return 0

    def _current_user(self) -> str:
        try:
            return str((self.app.session or {}).get("username", "?"))
        except Exception:
            return "?"

    # -- cards ----------------------------------------------------------
    def _refresh_cards(self) -> None:
        docs = self._effective_docs()
        self.card_values["docs"].configure(text=str(len(docs)))
        active = sum(1 for on in self.app.config.get("portals", {}).values()
                     if on)
        self.card_values["portals"].configure(text=str(active))
        provider_key = self.app.config.get("provider", "groq")
        self.card_values["provider"].configure(
            text=PROVIDERS.get(provider_key, {}).get("name", provider_key))

    def _refresh_weight_labels(self) -> None:
        for key in INDICADORES:
            self.weight_labels[key].configure(
                text=f"{LABELS[key]}: {self._weights.get(key, 0)}")

    # -- worker compute + main-thread render ----------------------------
    def _on_filter_change(self) -> None:
        self._refresh_cards()
        self._schedule_refresh()

    def _on_sort(self, key: str) -> None:
        if key == self._sort_key:
            self._sort_desc[key] = not self._sort_desc[key]
        else:
            self._sort_key = key
        self._update_header_arrows()
        self._schedule_refresh()

    def _update_header_arrows(self) -> None:
        captions = dict(SORT_COLUMNS)
        for key, btn in self._header_buttons.items():
            text = captions[key]
            if key == self._sort_key:
                text += " ▼" if self._sort_desc[key] else " ▲"
            try:
                btn.configure(text=text)
            except Exception:
                pass

    def _schedule_refresh(self) -> None:
        self._seq += 1
        seq = self._seq
        docs = self._effective_docs()
        weights = self._view_weights()
        sort_key = self._sort_key
        sort_desc = self._sort_desc[sort_key]
        try:
            self.status_label.configure(text="Atualizando...")
        except Exception:
            pass
        thread = threading.Thread(target=self._compute_worker,
                                  args=(seq, docs, weights,
                                        sort_key, sort_desc),
                                  daemon=True)
        thread.start()

    def _compute_worker(self, seq: int, docs: list, weights: dict,
                        sort_key: str, sort_desc: bool) -> None:
        try:
            monthly = repository.stats_monthly(docs, list(AREAS))
            share = repository.stats_area_share(docs)
            if docs:
                assert abs(sum(share.values()) - 100.0) < 0.6
            countries = repository.stats_countries(docs)
            if sort_key == "relevance" and sum(weights.values()) <= 0:
                ordered = list(docs)
            else:
                ordered = repository.sort_documents(docs, sort_key,
                                                    desc=sort_desc,
                                                    weights=weights)
            rows = [((d.get("date") or d.get("published") or "—"),
                     repository.area_of(d),
                     self._view_relevance(d, weights)) for d in ordered]
            payload = {"monthly": monthly, "share": share,
                       "countries": countries, "rows": rows,
                       "total": len(ordered)}
        except Exception:
            logger.debug("Dashboard compute failed", exc_info=True)
            return
        self._ui_queue.put(("render", seq, payload))

    def _poll_ui(self) -> None:
        """Main-thread pump: render worker payloads, apply status notes."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        try:
            while True:
                item = self._ui_queue.get_nowait()
                kind = item[0]
                if kind == "render":
                    _, seq, payload = item
                    if seq == self._seq:
                        self._render(seq, payload)
                elif kind == "status":
                    self._set_status_safe(item[1])
        except queue.Empty:
            pass
        except Exception:
            logger.debug("Dashboard UI poll failed", exc_info=True)
        try:
            if self.winfo_exists():
                self.after(100, self._poll_ui)
        except Exception:
            pass

    def _notify(self, text: str) -> None:
        """Thread-safe status update (workers must not touch Tk)."""
        self._ui_queue.put(("status", text))

    def _render(self, seq: int, payload: dict) -> None:
        try:
            if seq != self._seq or not self.winfo_exists():
                return
        except Exception:
            return
        try:
            self._render_bar(payload["monthly"])
            self._render_donut(payload["share"])
            self._render_countries(payload["countries"])
            self._render_table(payload["rows"], payload["total"])
            self._refresh_cards()
            self.status_label.configure(
                text=f"{payload['total']} documento(s) na visualização atual.")
        except Exception:
            logger.debug("Dashboard render failed", exc_info=True)

    @staticmethod
    def _clear(box) -> None:
        for child in box.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass

    def _render_bar(self, monthly: dict) -> None:
        self._clear(self.bar_box)
        if not monthly:
            ctk.CTkLabel(self.bar_box, text="Sem dados para exibir.").pack(
                pady=20)
            return
        figure = Figure(figsize=(5, 3), dpi=100)
        axes = figure.add_subplot(111)
        months = list(monthly)
        width = 0.2
        for i, area in enumerate(AREAS):
            axes.bar([x + i * width for x in range(len(months))],
                     [monthly[m][area] for m in months], width=width,
                     label=area)
        axes.set_xticks([x + width * 1.5 for x in range(len(months))])
        axes.set_xticklabels(months, rotation=30, ha="right")
        axes.set_ylabel("Documentos")
        axes.legend()
        figure.subplots_adjust(left=0.12, right=0.95, top=0.92, bottom=0.28)
        canvas = FigureCanvasTkAgg(figure, master=self.bar_box)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _render_donut(self, share: dict) -> None:
        self._clear(self.donut_box)
        if not share or sum(share.values()) <= 0:
            ctk.CTkLabel(self.donut_box, text="Sem dados para exibir.").pack(
                pady=20)
            return
        figure = Figure(figsize=(5, 3), dpi=100)
        axes = figure.add_subplot(111)
        axes.pie([share[a] for a in AREAS], labels=list(AREAS),
                 autopct="%1.1f%%",
                 wedgeprops=dict(width=0.4, edgecolor="white"))
        figure.subplots_adjust(left=0.05, right=0.95, top=0.92, bottom=0.08)
        canvas = FigureCanvasTkAgg(figure, master=self.donut_box)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

    def _render_countries(self, countries: list) -> None:
        self._clear(self.countries_box)
        if not countries:
            ctk.CTkLabel(self.countries_box, text="Sem dados para exibir.",
                         font=ctk.CTkFont(**NORMAL_FONT)).pack(anchor="w")
            return
        for name, count in countries:
            ctk.CTkLabel(self.countries_box, text=f"{name}: {count}",
                         font=ctk.CTkFont(**NORMAL_FONT)).pack(anchor="w")

    def _render_table(self, rows: list, total: int) -> None:
        shown = rows[:TABLE_PAGE]
        lines = [f"{date:<12}  {area:<18}  {relevance:>3}"
                 for date, area, relevance in shown]
        try:
            self.table_box.configure(state="normal")
            self.table_box.delete("1.0", "end")
            self.table_box.insert("end", "\n".join(lines))
            self.table_box.configure(state="disabled")
        except Exception:
            pass
        if total > len(shown):
            self.table_count.configure(
                text=f"Exibindo {len(shown)} de {total} documentos.")
        else:
            self.table_count.configure(text=f"{total} documento(s).")

    # -- weights editor -------------------------------------------------
    def _edit_weights(self) -> None:
        if not self.app.has_capability("edit_weights"):
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title("Editar pesos")
        dialog.geometry("460x340")
        ctk.CTkLabel(dialog, text="Índice de seleção multicritério",
                     font=ctk.CTkFont(**SECTION_FONT)).pack(padx=20, pady=(12, 4))
        entries: dict[str, ctk.CTkEntry] = {}
        for key in INDICADORES:
            ctk.CTkLabel(dialog, text=LABELS[key]).pack(anchor="w", padx=20)
            entry = ctk.CTkEntry(dialog)
            entry.insert(0, str(self._weights.get(key, 0)))
            entry.pack(padx=20, pady=(0, 6), fill="x")
            entries[key] = entry
        error = ctk.CTkLabel(dialog, text="", text_color="#F85149")
        error.pack(padx=20, pady=2)

        def _save() -> None:
            try:
                candidate = {}
                for key, entry in entries.items():
                    raw = entry.get().strip()
                    value = int(raw)
                    if not 0 <= value <= 100:
                        raise ValueError("range")
                    candidate[key] = value
                validate_weights(candidate)
            except (ValueError, AttributeError):
                total = 0
                try:
                    total = sum(int(e.get().strip()) for e in entries.values())
                except (ValueError, AttributeError):
                    error.configure(
                        text="Pesos devem ser números inteiros de 0 a 100.")
                    return
                error.configure(
                    text=f"A soma dos pesos deve ser 100 (atual: {total}).")
                return
            try:
                save_weights(candidate)
                log_event(self._current_user(), "edit_weights",
                          f"pesos={candidate}")
            except (OSError, ValueError) as exc:
                error.configure(text=f"Não foi possível salvar: {exc}")
                return
            self._weights = dict(candidate)
            self._refresh_weight_labels()
            try:
                dialog.destroy()
            except Exception:
                pass
            self._schedule_refresh()

        row = ctk.CTkFrame(dialog, fg_color="transparent")
        row.pack(padx=20, pady=10, fill="x")
        ctk.CTkButton(row, text="Salvar", command=_save).pack(side="left",
                                                              padx=(0, 8))
        ctk.CTkButton(row, text="Cancelar", fg_color="transparent",
                      command=dialog.destroy).pack(side="left")

    # -- print / share --------------------------------------------------
    def _dashboard_structure(self, docs: list, weights: dict) -> dict:
        ranked = sorted(docs,
                        key=lambda d: self._view_relevance(d, weights),
                        reverse=True)[:20]
        return build_newsletter(ranked, weights, "dashboard",
                                {"title": NEWSLETTER_TITLE})

    def _print_dashboard(self) -> None:
        docs = self._effective_docs()
        weights = self._export_weights()
        thread = threading.Thread(target=self._print_worker,
                                  args=(docs, weights), daemon=True)
        thread.start()

    def _print_worker(self, docs: list, weights: dict) -> None:
        try:
            structure = self._dashboard_structure(docs, weights)
            tmp = Path(tempfile.mkdtemp(prefix="quiin_")) / "dashboard.pdf"
            export_pdf(structure, tmp)
            print_pdf(tmp)
            log_event(self._current_user(), "print_dashboard",
                      f"documentos={len(structure['sections'])}")
            self._notify("Impressão enviada.")
        except Exception as exc:
            logger.debug("Print failed", exc_info=True)
            self._notify(f"Falha ao imprimir: {exc}")

    def _share_dashboard(self) -> None:
        target = filedialog.askdirectory(title="Compartilhar pacote")
        if not target:
            return
        docs = self._effective_docs()
        weights = self._export_weights()
        thread = threading.Thread(target=self._share_worker,
                                  args=(docs, weights, target), daemon=True)
        thread.start()

    def _share_worker(self, docs: list, weights: dict, target: str) -> None:
        try:
            structure = self._dashboard_structure(docs, weights)
            path = share_package(structure, target)
            log_event(self._current_user(), "share_dashboard", f"pacote={path}")
            self._notify(f"Pacote compartilhado em {path}.")
        except Exception as exc:
            logger.debug("Share failed", exc_info=True)
            self._notify(f"Falha ao compartilhar: {exc}")

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

    # -- newsletter seam (Task 9 owns the flows) ------------------------
    def _newsletter_auto(self) -> None:
        """Seam: automatic newsletter from the filtered top-20 (Task 9)."""
        path = filedialog.asksaveasfilename(
            title="Exportar newsletter (PDF)",
            defaultextension=".pdf",
            initialfile="newsletter_quiin.pdf",
            filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")])
        if not path:
            return
        docs = self._effective_docs()
        weights = self._export_weights()
        thread = threading.Thread(target=self._newsletter_export_worker,
                                  args=(docs, weights, "automatico", path),
                                  daemon=True)
        thread.start()

    def _newsletter_custom(self) -> None:
        """Seam: personalized newsletter (Task 9 adds the modal)."""
        path = filedialog.asksaveasfilename(
            title="Exportar newsletter personalizada (PDF)",
            defaultextension=".pdf",
            initialfile="newsletter_personalizada.pdf",
            filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")])
        if not path:
            return
        docs = self._effective_docs()
        weights = self._export_weights()
        thread = threading.Thread(target=self._newsletter_export_worker,
                                  args=(docs, weights, "personalizado", path),
                                  daemon=True)
        thread.start()

    def _newsletter_export_worker(self, docs: list, weights: dict,
                                  mode: str, path: str) -> None:
        try:
            ranked = sorted(
                docs, key=lambda d: self._view_relevance(d, weights),
                reverse=True)[:20]
            structure = build_newsletter(ranked, weights, mode,
                                         {"title": NEWSLETTER_TITLE})
            export_pdf(structure, path)
            log_event(self._current_user(), "generate_newsletter",
                      f"modo={mode} documentos={len(structure['sections'])}")
            self._notify(f"Newsletter ({mode}) exportada para {path}.")
        except Exception as exc:
            logger.debug("Newsletter export failed", exc_info=True)
            self._notify(f"Falha ao exportar newsletter: {exc}")
