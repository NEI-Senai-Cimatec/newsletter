# gui/frames/scraper_frame.py
"""Pipeline execution screen: preflight, options, progress, start/cancel."""
import queue
import threading
import time

import customtkinter as ctk

from core.api_client import APIClient
from core.preflight import run_preflight_checks
from core.task_runner import TaskRunner
from gui.theme.colors import NORMAL_FONT, SECTION_FONT, STATUS_ERROR, STATUS_OK, STATUS_WARNING, TITLE_FONT


class ScraperFrame(ctk.CTkFrame):
    """Runs preflight on show and the pipeline in a worker thread."""

    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.runner: TaskRunner | None = None
        self._polling = False
        self._start_time = 0.0
        self._preflight_ok = False
        self._preflight_results: queue.Queue = queue.Queue()  # worker -> GUI thread

        ctk.CTkLabel(self, text="🚀 Execução",
                     font=ctk.CTkFont(**TITLE_FONT)).pack(anchor="w", padx=20, pady=(16, 8))

        # ---- Preflight ----
        _pre_outer, pre_body = self._build_section("Pré-voo")
        self.preflight_box = ctk.CTkScrollableFrame(pre_body, height=150)
        self.preflight_box.pack(fill="x", padx=12, pady=(0, 4))
        pre_buttons = ctk.CTkFrame(pre_body, fg_color="transparent")
        pre_buttons.pack(fill="x", padx=12, pady=(0, 8))
        ctk.CTkButton(pre_buttons, text="🔄 Verificar novamente", width=180,
                      command=self._run_preflight).pack(side="left")

        # ---- Options ----
        _opt_outer, opt_body = self._build_section("Opções")
        self.ignore_cache_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(opt_body, text="Ignorar cache (re-baixar tudo)",
                        variable=self.ignore_cache_var).pack(anchor="w", padx=12, pady=4)
        self.debug_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(opt_body, text="Modo debug (logs detalhados)",
                        variable=self.debug_var).pack(anchor="w", padx=12, pady=4)
        date_row = ctk.CTkFrame(opt_body, fg_color="transparent")
        date_row.pack(anchor="w", padx=12, pady=4, fill="x")
        ctk.CTkLabel(date_row, text="A partir de:",
                     font=ctk.CTkFont(**NORMAL_FONT)).pack(side="left")
        self.min_date_entry = ctk.CTkEntry(date_row, width=150,
                                           placeholder_text="AAAA-MM-DD (vazio = tudo)")
        self.min_date_entry.pack(side="left", padx=8)

        # ---- Progress ----
        _prog_outer, prog_body = self._build_section("Progresso")
        self.portal_label = ctk.CTkLabel(prog_body, text="Portal atual: —",
                                         font=ctk.CTkFont(**NORMAL_FONT))
        self.portal_label.pack(anchor="w", padx=12, pady=(4, 2))
        self.progress_bar = ctk.CTkProgressBar(prog_body)
        self.progress_bar.pack(fill="x", padx=12, pady=4)
        self.progress_bar.set(0)
        self.article_label = ctk.CTkLabel(prog_body, text="",
                                          font=ctk.CTkFont(**NORMAL_FONT))
        self.article_label.pack(anchor="w", padx=12, pady=2)
        self.elapsed_label = ctk.CTkLabel(prog_body, text="",
                                          font=ctk.CTkFont(**NORMAL_FONT))
        self.elapsed_label.pack(anchor="w", padx=12, pady=(2, 8))

        # ---- Actions ----
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(pady=12)
        self.start_button = ctk.CTkButton(actions, text="▶ Iniciar Pipeline",
                                          command=self._start_pipeline, state="disabled")
        self.start_button.pack(side="left", padx=8)
        self.cancel_button = ctk.CTkButton(actions, text="⏹ Cancelar",
                                           command=self._cancel_pipeline, state="disabled")
        self.cancel_button.pack(side="left", padx=8)
        self.results_button = ctk.CTkButton(actions, text="📊 Ver Resultados",
                                            command=lambda: app.show_frame("results"),
                                            state="disabled")
        self.results_button.pack(side="left", padx=8)

    def _build_section(self, title: str) -> tuple[ctk.CTkFrame, ctk.CTkFrame]:
        """Create a titled section; return ``(outer_box, body)``."""
        outer = ctk.CTkFrame(self)
        outer.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(outer, text=title, font=ctk.CTkFont(**SECTION_FONT)).pack(
            anchor="w", padx=12, pady=(10, 2))
        body = ctk.CTkFrame(outer, fg_color="transparent")
        body.pack(fill="x", padx=0, pady=(0, 10))
        return outer, body

    # -- lifecycle ------------------------------------------------------
    def on_show(self) -> None:
        """Reload options from config and re-run preflight."""
        config = self.app.config
        self.ignore_cache_var.set(bool(config.get("scraper_settings", {}).get("ignore_cache")))
        self.debug_var.set(bool(config.get("scraper_settings", {}).get("debug")))
        self.min_date_entry.delete(0, "end")
        self.min_date_entry.insert(0, config.get("scraper_settings", {}).get("min_date", ""))
        self._run_preflight()
        if not self._polling:
            self._polling = True
            self._poll_queues()

    # -- preflight ------------------------------------------------------
    def _run_preflight(self) -> None:
        for child in self.preflight_box.winfo_children():
            child.destroy()
        ctk.CTkLabel(self.preflight_box, text="Verificando...").pack(anchor="w")
        self.start_button.configure(state="disabled")
        thread = threading.Thread(target=self._preflight_worker, daemon=True)
        thread.start()

    def _preflight_worker(self) -> None:
        config = self.app.config
        api_key = self.app.config_manager.get_api_key(config.get("provider", "groq"))
        results = run_preflight_checks(config, api_key)
        self._preflight_results.put(results)  # main thread picks this up in _poll_queues

    def _show_preflight(self, results: list) -> None:
        for child in self.preflight_box.winfo_children():
            child.destroy()
        self._preflight_ok = True
        for item in results:
            status = item.get("status", "error")
            icon = {"ok": "✅", "warning": "⚠️"}.get(status, "❌")
            color = {"ok": STATUS_OK, "warning": STATUS_WARNING}.get(status, STATUS_ERROR)
            if status == "error":
                self._preflight_ok = False
            row = ctk.CTkLabel(
                self.preflight_box,
                text=f"{icon} {item.get('check')}: {item.get('message')}",
                text_color=color,
                font=ctk.CTkFont(**NORMAL_FONT),
                anchor="w",
                justify="left",
                wraplength=700,
            )
            row.pack(anchor="w", padx=4, pady=1)
        if self._preflight_ok and (self.runner is None or not self.runner.is_running):
            self.start_button.configure(state="normal")

    # -- pipeline -------------------------------------------------------
    def _start_pipeline(self) -> None:
        if not self._preflight_ok:
            return
        config = self.app.config
        config["scraper_settings"]["ignore_cache"] = bool(self.ignore_cache_var.get())
        config["scraper_settings"]["debug"] = bool(self.debug_var.get())
        config["scraper_settings"]["min_date"] = self.min_date_entry.get().strip()
        self.app.save_config()

        api_key = self.app.config_manager.get_api_key(config.get("provider", "groq"))
        try:
            model = APIClient(
                provider=config.get("provider", "groq"),
                api_key=api_key or "",
                model=config.get("model", ""),
                base_url=config.get("custom_endpoint") or None,
                **config.get("llm_settings", {}),
            )
        except ValueError as e:
            self.portal_label.configure(text=f"❌ Configuração inválida: {e}")
            return

        self.runner = TaskRunner(self.app.progress_queue, self.app.log_queue)
        self._start_time = time.monotonic()
        self.progress_bar.set(0)
        self.article_label.configure(text="")
        self.results_button.configure(state="disabled")
        self.start_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.app.status_bar.set_status("Executando pipeline...")
        self.runner.start(model, config)

    def _cancel_pipeline(self) -> None:
        if self.runner is not None:
            self.runner.cancel()
            self.cancel_button.configure(state="disabled")
            self.portal_label.configure(text="Cancelando... aguarde o artigo atual.")

    def _poll_queues(self) -> None:
        try:
            while True:
                item = self.app.progress_queue.get_nowait()
                self._handle_progress(item)
        except Exception:
            pass
        try:
            while True:
                self._show_preflight(self._preflight_results.get_nowait())
        except Exception:
            pass
        if self._start_time:
            elapsed = int(time.monotonic() - self._start_time)
            self.elapsed_label.configure(
                text=f"Tempo decorrido: {elapsed // 3600:02d}:{(elapsed % 3600) // 60:02d}:{elapsed % 60:02d}")
        self.after(100, self._poll_queues)

    def _handle_progress(self, item: dict) -> None:
        kind = item.get("type")
        if kind == "article":
            current, total = item.get("current", 0), item.get("total", 0)
            if total:
                self.progress_bar.set(current / total)
                self.article_label.configure(text=f"Artigo {current}/{total}")
            return
        if kind != "stage":
            return
        stage = item.get("stage")
        message = item.get("message", "")
        if stage == "portal_start":
            self.portal_label.configure(text=f"Portal atual: {item.get('portal', '—')}")
        elif stage in ("done", "cancelled", "error"):
            self._finish(message, stage == "done")
        elif stage == "portal_error":
            self.portal_label.configure(text=f"⚠️ {message}")

    def _finish(self, message: str, success: bool) -> None:
        self._start_time = 0
        self.elapsed_label.configure(text="")
        self.cancel_button.configure(state="disabled")
        self.app.status_bar.set_status("Pronto")
        if success:
            from datetime import datetime
            self.app.config["last_run"] = datetime.now().isoformat(timespec="seconds")
            self.app.save_config()
            self.progress_bar.set(1)
            self.article_label.configure(text="")
            self.portal_label.configure(text=f"✅ {message}")
            self.results_button.configure(state="normal")
            self.start_button.configure(state="normal")
        else:
            self.portal_label.configure(text=f"❌ {message}")
            self.start_button.configure(state="normal")
