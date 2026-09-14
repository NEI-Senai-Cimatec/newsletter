# gui/frames/settings_frame.py
"""Provider, model, portal, and LLM-parameter configuration screen."""
import logging
import queue
import threading
import webbrowser

import customtkinter as ctk

from core import database
from core.api_client import APIClient
from core.audit import log_event
from core.config_manager import PROVIDERS
from core.database import DB_FILE
from core.permissions import can
from core.scoring import (DEFAULT_WEIGHTS, INDICADORES, LABELS, load_weights,
                          save_weights, validate_weights)
from gui.theme.colors import NORMAL_FONT, SECTION_FONT, SMALL_FONT, TITLE_FONT

logger = logging.getLogger(__name__)

PORTAL_LABELS = [
    ("thequantuminsider", "The Quantum Insider"),
    ("quantamagazine", "Quanta Magazine"),
    ("quantumzeitgeist", "Quantum Zeitgeist"),
    ("insidequantumtechnology", "Inside Quantum Technology"),
]

SOBRE_LINES = (
    "Nome: GLOBAL QUANTUM INTELLIGENCE – QuIIN",
    "Criação: 27/04/2025",
    "Publicação: 09/05/2025",
    "Linguagem: Python (web scraping, PLN e automação de relatórios)",
    "Campo: IF01 – Informação científica, tecnológica, bibliográfica e estratégica",
    "Tipo: IA01 – Inteligência Artificial / GI01 – Gerenciador de Informações",
    "Proprietário: Quantum Industrial Innovation",
    "Autores: Mabel Diz Marques Mota / João Carlos Passos / Alexandre de Santa Barbara",
)


class SettingsFrame(ctk.CTkFrame):
    """All settings persist through ConfigManager (auto-save on leave)."""

    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._testing = False
        self._test_results: queue.Queue = queue.Queue()  # worker -> GUI thread

        ctk.CTkLabel(self, text="⚙️ Configurações",
                     font=ctk.CTkFont(**TITLE_FONT)).pack(anchor="w", padx=20, pady=(16, 8))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._ai_widgets: list = []
        self._pipeline_widgets: list = []

        # ---- Perfil ----
        _perfil_outer, perfil_box = self._section(scroll, "Perfil")
        ctk.CTkLabel(perfil_box, text="Nome:",
                     font=ctk.CTkFont(**NORMAL_FONT)).grid(row=0, column=0, sticky="w",
                                                           padx=12, pady=8)
        self.profile_name_entry = ctk.CTkEntry(perfil_box, width=320,
                                               placeholder_text="Nome completo")
        self.profile_name_entry.grid(row=0, column=1, sticky="ew", padx=12, pady=8)
        ctk.CTkLabel(perfil_box, text="Organização:",
                     font=ctk.CTkFont(**NORMAL_FONT)).grid(row=1, column=0, sticky="w",
                                                           padx=12, pady=8)
        self.profile_org_entry = ctk.CTkEntry(perfil_box, width=320,
                                              placeholder_text="Organização")
        self.profile_org_entry.grid(row=1, column=1, sticky="ew", padx=12, pady=8)
        self.profile_status = ctk.CTkLabel(perfil_box, text="",
                                           font=ctk.CTkFont(**SMALL_FONT))
        self.profile_status.grid(row=2, column=1, sticky="w", padx=12, pady=(0, 4))
        perfil_box.columnconfigure(1, weight=1)

        # ---- Provider section ----
        _provider_outer, provider_box = self._section(scroll, "Provedor de IA")
        self.provider_names = [info["name"] for info in PROVIDERS.values()]
        self.provider_keys = list(PROVIDERS)
        self.provider_var = ctk.StringVar(value=self.provider_names[0])
        ctk.CTkLabel(provider_box, text="Provedor:",
                     font=ctk.CTkFont(**NORMAL_FONT)).grid(row=0, column=0, sticky="w",
                                                           padx=12, pady=8)
        self.provider_menu = ctk.CTkOptionMenu(
            provider_box, values=self.provider_names, variable=self.provider_var,
            command=self._on_provider_change)
        self.provider_menu.grid(row=0, column=1, sticky="ew", padx=12, pady=8)

        ctk.CTkLabel(provider_box, text="API Key:",
                     font=ctk.CTkFont(**NORMAL_FONT)).grid(row=1, column=0, sticky="w",
                                                           padx=12, pady=8)
        key_row = ctk.CTkFrame(provider_box, fg_color="transparent")
        key_row.grid(row=1, column=1, sticky="ew", padx=12, pady=8)
        key_row.columnconfigure(0, weight=1)
        self.key_visible = False
        self.key_entry = ctk.CTkEntry(key_row, show="•")
        self.key_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.key_toggle_button = ctk.CTkButton(key_row, text="👁", width=40,
                                              command=self._toggle_key)
        self.key_toggle_button.grid(row=0, column=1, padx=(0, 6))
        self.key_save_button = ctk.CTkButton(key_row, text="Salvar", width=70,
                                             command=self._save_key)
        self.key_save_button.grid(row=0, column=2)

        ctk.CTkLabel(provider_box, text="Modelo:",
                     font=ctk.CTkFont(**NORMAL_FONT)).grid(row=2, column=0, sticky="w",
                                                           padx=12, pady=8)
        self.model_var = ctk.StringVar(value="")
        self.model_combo = ctk.CTkComboBox(provider_box, variable=self.model_var, values=[])
        self.model_combo.grid(row=2, column=1, sticky="ew", padx=12, pady=8)
        provider_box.columnconfigure(1, weight=1)

        self.docs_button = ctk.CTkButton(provider_box, text="🔑 Obter chave",
                                         width=130, fg_color="transparent",
                                         command=self._open_docs)
        self.docs_button.grid(row=3, column=1, sticky="e", padx=12, pady=(0, 4))
        self.docs_hint = ctk.CTkLabel(provider_box, text="",
                                      font=ctk.CTkFont(**SMALL_FONT))
        self.docs_hint.grid(row=4, column=1, sticky="e", padx=12, pady=(0, 4))

        test_row = ctk.CTkFrame(provider_box, fg_color="transparent")
        test_row.grid(row=5, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
        self.test_button = ctk.CTkButton(test_row, text="🔗 Testar Conexão",
                                         command=self._test_connection)
        self.test_button.pack(side="left")
        self.test_label = ctk.CTkLabel(test_row, text="", font=ctk.CTkFont(**NORMAL_FONT))
        self.test_label.pack(side="left", padx=12)

        # ---- Custom endpoint (only for provider "custom") ----
        self.custom_box, custom_body = self._section(scroll, "Endpoint Personalizado")
        ctk.CTkLabel(custom_body, text="URL Base:",
                     font=ctk.CTkFont(**NORMAL_FONT)).grid(row=0, column=0, sticky="w",
                                                           padx=12, pady=8)
        self.endpoint_entry = ctk.CTkEntry(custom_body, width=320,
                                           placeholder_text="https://meu-servidor.com/v1")
        self.endpoint_entry.grid(row=0, column=1, sticky="ew", padx=12, pady=8)

        # ---- Portals ----
        _portals_outer, portals_box = self._section(scroll, "Portais de Notícias")
        self.portal_vars: dict[str, ctk.BooleanVar] = {}
        self.portal_boxes: list = []
        for i, (key, label) in enumerate(PORTAL_LABELS):
            var = ctk.BooleanVar(value=False)
            box = ctk.CTkCheckBox(portals_box, text=label, variable=var)
            box.grid(row=i, column=0, sticky="w", padx=12, pady=4)
            self.portal_vars[key] = var
            self.portal_boxes.append(box)

        # ---- LLM parameters ----
        _llm_outer, llm_box = self._section(scroll, "Parâmetros do LLM")
        ctk.CTkLabel(llm_box, text="Max Tokens:",
                     font=ctk.CTkFont(**NORMAL_FONT)).grid(row=0, column=0, sticky="w",
                                                           padx=12, pady=8)
        self.max_tokens_entry = ctk.CTkEntry(llm_box, width=120)
        self.max_tokens_entry.grid(row=0, column=1, sticky="w", padx=12, pady=8)

        ctk.CTkLabel(llm_box, text="Temperature:",
                     font=ctk.CTkFont(**NORMAL_FONT)).grid(row=1, column=0, sticky="w",
                                                           padx=12, pady=8)
        self.temp_var = ctk.DoubleVar(value=0.8)
        self.temp_slider = ctk.CTkSlider(llm_box, from_=0.0, to=1.5, number_of_steps=30,
                                         variable=self.temp_var,
                                         command=lambda v: self._slider_label(
                                             self.temp_label, float(v)))
        self.temp_slider.grid(row=1, column=1, sticky="ew", padx=12, pady=8)
        self.temp_label = ctk.CTkLabel(llm_box, text="0.80", width=50,
                                       font=ctk.CTkFont(**NORMAL_FONT))
        self.temp_label.grid(row=1, column=2, padx=(0, 12))

        ctk.CTkLabel(llm_box, text="Top P:",
                     font=ctk.CTkFont(**NORMAL_FONT)).grid(row=2, column=0, sticky="w",
                                                           padx=12, pady=8)
        self.top_p_var = ctk.DoubleVar(value=0.95)
        self.top_p_slider = ctk.CTkSlider(llm_box, from_=0.0, to=1.0, number_of_steps=100,
                                          variable=self.top_p_var,
                                          command=lambda v: self._slider_label(
                                              self.top_p_label, float(v)))
        self.top_p_slider.grid(row=2, column=1, sticky="ew", padx=12, pady=8)
        self.top_p_label = ctk.CTkLabel(llm_box, text="0.95", width=50,
                                        font=ctk.CTkFont(**NORMAL_FONT))
        self.top_p_label.grid(row=2, column=2, padx=(0, 12))
        llm_box.columnconfigure(1, weight=1)

        # ---- Collection filter ----
        _filter_outer, filter_box = self._section(scroll, "Filtro de Coleta")
        ctk.CTkLabel(filter_box, text="A partir de:",
                     font=ctk.CTkFont(**NORMAL_FONT)).grid(row=0, column=0, sticky="w",
                                                           padx=12, pady=8)
        self.min_date_entry = ctk.CTkEntry(filter_box, width=160,
                                           placeholder_text="AAAA-MM-DD (vazio = tudo)")
        self.min_date_entry.grid(row=0, column=1, sticky="w", padx=12, pady=8)

        # ---- Índice multicritério (mesmo editor do dashboard) ----
        _weights_outer, weights_box = self._section(scroll, "Índice multicritério")
        self.weights_edit_button = ctk.CTkButton(weights_box, text="Editar",
                                                 width=90,
                                                 command=self._edit_weights)
        self.weights_edit_button.grid(row=0, column=2, padx=12, pady=4,
                                       sticky="e")
        self._weights: dict = load_weights()
        self.weight_labels: dict[str, ctk.CTkLabel] = {}
        for i, key in enumerate(INDICADORES, start=1):
            row_label = ctk.CTkLabel(weights_box, text="",
                                     font=ctk.CTkFont(**NORMAL_FONT))
            row_label.grid(row=i, column=0, columnspan=3, sticky="w",
                           padx=12, pady=1)
            self.weight_labels[key] = row_label
        self._refresh_weight_labels()

        # ---- Sobre / Registro do Software ----
        _sobre_outer, sobre_box = self._section(scroll, "Sobre / Registro do Software")
        for line in SOBRE_LINES:
            ctk.CTkLabel(sobre_box, text=line,
                         font=ctk.CTkFont(**NORMAL_FONT),
                         wraplength=640, justify="left").pack(anchor="w",
                                                              padx=12, pady=1)

        # Registra os widgets gated APÓS criar todas as seções (o bloco de
        # IA acima permanece intacto; só ganhou referências nomeadas).
        self._ai_widgets = [self.provider_menu, self.key_entry,
                            self.key_toggle_button, self.key_save_button,
                            self.model_combo, self.docs_button,
                            self.test_button, self.endpoint_entry]
        self._pipeline_widgets = [*self.portal_boxes,
                                  self.max_tokens_entry, self.temp_slider,
                                  self.top_p_slider, self.min_date_entry]

        self.save_button = ctk.CTkButton(self, text="💾 Salvar configurações",
                                            command=self.save)
        self.save_button.pack(pady=(0, 16))

    @staticmethod
    def _section(master, title: str) -> tuple[ctk.CTkFrame, ctk.CTkFrame]:
        """Create a titled section; return ``(outer_box, grid_body)``."""
        box = ctk.CTkFrame(master)
        box.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(box, text=title, font=ctk.CTkFont(**SECTION_FONT)).pack(
            anchor="w", padx=12, pady=(10, 2))
        body = ctk.CTkFrame(box, fg_color="transparent")
        body.pack(fill="x", padx=0, pady=(0, 10))
        body.columnconfigure(1, weight=1)
        return box, body

    @staticmethod
    def _slider_label(label: ctk.CTkLabel, value: float) -> None:
        label.configure(text=f"{value:.2f}")

    # -- lifecycle ------------------------------------------------------
    def on_show(self) -> None:
        """Load widgets from the current config (and stored API key)."""
        self._load_from_config()
        self._apply_role_gating()
        self.test_label.configure(text="")
        self.profile_status.configure(text="")

    def on_hide(self) -> None:
        """Auto-save when leaving the screen."""
        self.save(silent=True)

    # -- config binding -------------------------------------------------
    def _current_provider_key(self) -> str:
        try:
            return self.provider_keys[self.provider_names.index(self.provider_var.get())]
        except ValueError:
            return "groq"

    def _load_from_config(self) -> None:
        config = self.app.config
        provider_key = config.get("provider", "groq")
        if provider_key not in PROVIDERS:
            provider_key = "groq"
        self.provider_var.set(PROVIDERS[provider_key]["name"])
        self._refresh_provider_widgets(provider_key)

        stored_key = self.app.config_manager.get_api_key(provider_key) or ""
        self.key_entry.delete(0, "end")
        self.key_entry.insert(0, stored_key)

        model = config.get("model", "") or PROVIDERS[provider_key]["default_model"]
        self.model_var.set(model)
        self.endpoint_entry.delete(0, "end")
        self.endpoint_entry.insert(0, config.get("custom_endpoint", ""))

        for key, var in self.portal_vars.items():
            var.set(bool(config.get("portals", {}).get(key, False)))

        llm = config.get("llm_settings", {})
        self.max_tokens_entry.delete(0, "end")
        self.max_tokens_entry.insert(0, str(llm.get("max_tokens", 10000)))
        self.temp_var.set(float(llm.get("temperature", 0.8)))
        self.top_p_var.set(float(llm.get("top_p", 0.95)))
        self._slider_label(self.temp_label, self.temp_var.get())
        self._slider_label(self.top_p_label, self.top_p_var.get())

        self.min_date_entry.delete(0, "end")
        self.min_date_entry.insert(0, config.get("scraper_settings", {}).get("min_date", ""))

        try:
            self._weights = load_weights()
        except Exception:
            logger.debug("load_weights failed", exc_info=True)
            self._weights = dict(DEFAULT_WEIGHTS)
        self._refresh_weight_labels()
        self._load_profile()

    def save(self, silent: bool = False) -> None:
        """Persist widgets to config (API key saved separately via Salvar).

        AI block writes require ``configure_ai``; portals/LLM/min-date
        require ``run_pipeline``. Profile save is always allowed.
        """
        role = self._current_role()
        ai_ok = can(role, "configure_ai")
        pipe_ok = can(role, "run_pipeline")
        config = self.app.config
        if ai_ok:
            provider_key = self._current_provider_key()
            config["provider"] = provider_key
            model = self.model_var.get().strip() or PROVIDERS[provider_key]["default_model"]
            config["model"] = model
            config["custom_endpoint"] = self.endpoint_entry.get().strip()
        if pipe_ok:
            for key, var in self.portal_vars.items():
                config["portals"][key] = bool(var.get())
            try:
                config["llm_settings"]["max_tokens"] = max(
                    1, int(self.max_tokens_entry.get().strip()))
            except (ValueError, TypeError):
                config["llm_settings"]["max_tokens"] = 10000
            config["llm_settings"]["temperature"] = round(float(self.temp_var.get()), 2)
            config["llm_settings"]["top_p"] = round(float(self.top_p_var.get()), 2)
            config["scraper_settings"]["min_date"] = self.min_date_entry.get().strip()
        self._save_profile()
        self.app.save_config()
        self.app.refresh_provider_status()
        if not silent:
            self.test_label.configure(text="✅ Configurações salvas.")

    # -- gating + perfil + pesos ---------------------------------------
    def _current_user(self) -> str:
        try:
            return str((self.app.session or {}).get("username", ""))
        except Exception:
            return ""

    def _current_role(self) -> str:
        try:
            return str((self.app.session or {}).get("role", "basico"))
        except Exception:
            return "basico"

    def _gate(self, widget, allowed: bool, denied_tip: str) -> None:
        """Disable ``widget`` when not ``allowed`` (reuse shell helper)."""
        try:
            if hasattr(self.app, "set_gated"):
                self.app.set_gated(widget, allowed, denied_tip)
            else:
                widget.configure(state="normal" if allowed else "disabled")
        except Exception:
            logger.debug("Gating skip", exc_info=True)

    def _apply_role_gating(self) -> None:
        """Gate AI/pipeline/weights controls by the session role."""
        role = self._current_role()
        ai_ok = can(role, "configure_ai")
        pipe_ok = can(role, "run_pipeline")
        for widget in self._ai_widgets:
            self._gate(widget, ai_ok, "Sem permissão: requer 'configure_ai'.")
        for widget in self._pipeline_widgets:
            self._gate(widget, pipe_ok, "Sem permissão: requer 'run_pipeline'.")
        self._gate(self.weights_edit_button, can(role, "edit_weights"),
                   "Sem permissão: requer 'edit_weights'.")
        # Salvar só persiste IA/pipeline para quem tem a capacidade; o
        # perfil salva sempre (também no on_hide). Sem nada gravável
        # além do perfil, o botão fica desabilitado.
        self._gate(self.save_button, ai_ok or pipe_ok,
                   "Sem permissão: nada para salvar neste papel.")
        # O bloco de endpoint personalizado só faz sentido com IA liberada.
        try:
            if not ai_ok:
                self.custom_box.pack_forget()
            elif self._current_provider_key() == "custom":
                self.custom_box.pack(fill="x", padx=8, pady=8)
        except Exception:
            logger.debug("Custom box gating skip", exc_info=True)

    def _load_profile(self) -> None:
        """Fill Perfil entries from ``users.db`` for the logged user."""
        username = self._current_user()
        name, org = "", ""
        if username:
            try:
                for user in database.list_users(DB_FILE):
                    if user.get("username") == username:
                        name = user.get("name", "") or ""
                        org = user.get("org", "") or ""
                        break
            except Exception:
                logger.debug("Profile load failed", exc_info=True)
        for entry, value in ((self.profile_name_entry, name),
                             (self.profile_org_entry, org)):
            try:
                entry.delete(0, "end")
                entry.insert(0, value)
            except Exception:
                logger.debug("Profile fill failed", exc_info=True)

    def _save_profile(self) -> None:
        """Persist Perfil entries to ``users.db`` for the logged user."""
        username = self._current_user()
        if not username:
            return
        try:
            name = self.profile_name_entry.get().strip()
            org = self.profile_org_entry.get().strip()
        except Exception:
            return
        try:
            current = {}
            for user in database.list_users(DB_FILE):
                if user.get("username") == username:
                    current = user
                    break
            if (current.get("name", "") or "") == name and (
                    current.get("org", "") or "") == org:
                return
            database.update_profile(DB_FILE, username, name, org)
            try:
                self.app.session["name"] = name
                self.app.session["org"] = org
                self.app.welcome_label.configure(text=f"Bem vindo, {name}")
                self.app.org_label.configure(text=str(org))
            except Exception:
                pass
            log_event(username, "update_profile", f"nome={name} org={org}")
            self.profile_status.configure(text="✅ Perfil salvo.")
        except Exception as exc:
            logger.debug("Profile save failed", exc_info=True)
            try:
                self.profile_status.configure(
                    text=f"Não foi possível salvar o perfil: {exc}")
            except Exception:
                pass

    def _refresh_weight_labels(self) -> None:
        for key in INDICADORES:
            try:
                self.weight_labels[key].configure(
                    text=f"{LABELS[key]}: {self._weights.get(key, 0)}")
            except Exception:
                logger.debug("Weight label skip", exc_info=True)

    def _edit_weights(self) -> None:
        if not can(self._current_role(), "edit_weights"):
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

        row = ctk.CTkFrame(dialog, fg_color="transparent")
        row.pack(padx=20, pady=10, fill="x")
        ctk.CTkButton(row, text="Salvar", command=_save).pack(side="left",
                                                              padx=(0, 8))
        ctk.CTkButton(row, text="Cancelar", fg_color="transparent",
                      command=dialog.destroy).pack(side="left")

    # -- provider widgets -----------------------------------------------
    def _on_provider_change(self, _name: str) -> None:
        provider_key = self._current_provider_key()
        self._refresh_provider_widgets(provider_key)
        # Preload stored key + default model for the newly selected provider.
        stored_key = self.app.config_manager.get_api_key(provider_key) or ""
        self.key_entry.delete(0, "end")
        self.key_entry.insert(0, stored_key)
        if not self.model_var.get().strip():
            self.model_var.set(PROVIDERS[provider_key]["default_model"])
        self.test_label.configure(text="")

    def _refresh_provider_widgets(self, provider_key: str) -> None:
        info = PROVIDERS[provider_key]
        models = list(info["models"]) or ([info["default_model"]] if info["default_model"] else [])
        self.model_combo.configure(values=models)
        docs_url = info["docs_url"]
        if docs_url:
            self.docs_button.configure(state="normal")
            self.docs_hint.configure(text=docs_url)
        else:
            self.docs_button.configure(state="disabled")
            self.docs_hint.configure(text="")
        if provider_key == "custom":
            self.custom_box.pack(fill="x", padx=8, pady=8)
        else:
            self.custom_box.pack_forget()

    def _toggle_key(self) -> None:
        self.key_visible = not self.key_visible
        self.key_entry.configure(show="" if self.key_visible else "•")

    def _save_key(self) -> None:
        if not can(self._current_role(), "configure_ai"):
            self.test_label.configure(text="❌ Sem permissão: requer 'configure_ai'.")
            return
        provider_key = self._current_provider_key()
        self.app.config_manager.set_api_key(provider_key, self.key_entry.get())
        self.test_label.configure(text="✅ API key salva no cofre do sistema.")
        self.app.refresh_provider_status()

    def _open_docs(self) -> None:
        url = PROVIDERS[self._current_provider_key()]["docs_url"]
        if url:
            webbrowser.open(url)

    # -- connection test (background thread) ----------------------------
    def _test_connection(self) -> None:
        if self._testing:
            return
        self._testing = True
        self.test_button.configure(state="disabled", text="Testando...")
        self.test_label.configure(text="")
        provider_key = self._current_provider_key()
        api_key = self.key_entry.get().strip()
        model = self.model_var.get().strip() or PROVIDERS[provider_key]["default_model"]
        base_url = self.endpoint_entry.get().strip() or None
        try:
            max_tokens = max(1, int(self.max_tokens_entry.get().strip()))
        except (ValueError, TypeError):
            max_tokens = 10000
        settings = {
            "max_tokens": max_tokens,
            "temperature": round(float(self.temp_var.get()), 2),
            "top_p": round(float(self.top_p_var.get()), 2),
        }
        thread = threading.Thread(
            target=self._test_worker,
            args=(provider_key, api_key, model, base_url, settings),
            daemon=True,
        )
        thread.start()
        self._poll_test()

    def _poll_test(self) -> None:
        """Apply the worker's result on the GUI thread (no Tk calls in workers)."""
        try:
            ok, message = self._test_results.get_nowait()
        except Exception:
            self.after(100, self._poll_test)
            return
        self._finish_test(ok, message)

    def _test_worker(self, provider_key: str, api_key: str, model: str,
                     base_url: str | None, settings: dict) -> None:
        try:
            client = APIClient(provider=provider_key, api_key=api_key, model=model,
                               base_url=base_url, **settings)
            ok, message = client.test_connection()
        except Exception as e:  # never crash the worker on bad input
            ok, message = False, f"Erro: {e}"
        self._test_results.put((ok, message))

    def _finish_test(self, ok: bool, message: str) -> None:
        self._testing = False
        self.test_button.configure(state="normal", text="🔗 Testar Conexão")
        prefix = "✅" if ok else "❌"
        self.test_label.configure(text=f"{prefix} {message}")
