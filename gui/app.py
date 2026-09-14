# gui/app.py
"""Main CustomTkinter application window: QuIIN session shell."""
import logging
import queue

import customtkinter as ctk

from core import repository
from core.config_manager import PROVIDERS, ConfigManager
from core.permissions import can
from core.task_runner import QueueHandler
from core.utils import DOCUMENTS_JSON
from gui.components.sidebar import Sidebar
from gui.components.status_bar import StatusBar
from gui.frames.dashboard_frame import DashboardFrame
from gui.frames.home_frame import HomeFrame
from gui.frames.login_frame import LoginFrame
from gui.frames.log_frame import LogFrame
from gui.frames.results_frame import ResultsFrame
from gui.frames.scraper_frame import ScraperFrame
from gui.frames.settings_frame import SettingsFrame
from gui.theme.colors import APPEARANCE_MODE, APP_GEOMETRY, APP_MINSIZE, APP_TITLE, COLOR_THEME

logger = logging.getLogger(__name__)

HYBRID_NAV = [
    ("dashboard", "📊 Dashboard"),
    ("documents", "📄 Documentos"),
    ("scraper", "🚀 Execução"),
    ("results", "📊 Resultados"),
    ("logs", "🧾 Logs"),
    ("accounts", "👥 Contas"),
    ("settings", "⚙️ Configurações"),
]

# Allowlist copy for App.session (defense in depth: never store password_hash/salt).
SESSION_KEYS = ("id", "username", "name", "org", "internal", "role",
                "status", "created_at", "created_by")

SEARCH_DEBOUNCE_MS = 200


class _PlaceholderFrame(ctk.CTkFrame):
    """Stand-in for a future QuIIN module (documents/accounts).

    Tasks 10/11 replace these placeholders with the real frames. The stub
    honors the established frame contract (``__init__(master, app)``,
    ``on_show``) plus ``apply_search`` so the header global search can
    forward filtered lists without crashing.
    """

    def __init__(self, master, app, title: str, note: str) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._docs: list = []
        ctk.CTkLabel(self, text=title,
                     font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(24, 4))
        ctk.CTkLabel(self, text=note).pack(pady=(0, 12))
        self.count_label = ctk.CTkLabel(self, text="")
        self.count_label.pack(pady=8)

    def on_show(self) -> None:
        total = len(self._docs) if self._docs else 0
        self.count_label.configure(
            text=f"{total} documento(s) na busca atual." if self._docs else "")

    def apply_search(self, docs: list) -> None:
        self._docs = list(docs)
        self.count_label.configure(text=f"{len(self._docs)} documento(s) na busca atual.")


class App(ctk.CTk):
    """Root window: session shell with header + hybrid sidebar + content area.

    Owns the shared config, the GUI queues, the root-log handler, and the
    in-memory ``session`` (identity dict from ``core.database.authenticate``,
    without password hash/salt). Starts on the ``login`` frame when
    ``session is None``.
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

        self.session: dict | None = None
        self.search_results: list = []
        self._cached_docs: list = []
        self._search_after: str | None = None
        self._export_registry: list = []
        self._gated_prev: dict = {}
        self._gated_bound_tip: dict = {}

        self.progress_queue: queue.Queue = queue.Queue()
        self.log_queue: queue.Queue = queue.Queue()
        handler = QueueHandler(self.log_queue)
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logging.getLogger().addHandler(handler)

        self.sidebar = Sidebar(self, on_navigate=self.show_frame, items=[])
        self.sidebar.pack(side="left", fill="y")

        self.header = ctk.CTkFrame(self, corner_radius=0)
        self.header.pack(side="top", fill="x")

        top_row = ctk.CTkFrame(self.header, fg_color="transparent")
        top_row.pack(fill="x", padx=12, pady=(8, 2))
        self.title_label = ctk.CTkLabel(top_row, text="GLOBAL QUANTUM INTELLIGENCE",
                                        font=ctk.CTkFont(size=16, weight="bold"))
        self.title_label.pack(side="left")
        self.logout_button = ctk.CTkButton(top_row, text="Log Out", width=90,
                                           command=self.logout)
        self.logout_button.pack(side="right")
        self.search_entry = ctk.CTkEntry(top_row, width=240,
                                         placeholder_text="Pesquise aqui")
        self.search_entry.pack(side="right", padx=8)
        self.search_entry.bind("<KeyRelease>", self._on_search)

        session_row = ctk.CTkFrame(self.header, fg_color="transparent")
        session_row.pack(fill="x", padx=12, pady=(2, 8))
        self.welcome_label = ctk.CTkLabel(session_row, text="")
        self.welcome_label.pack(side="left", padx=(0, 12))
        self.org_label = ctk.CTkLabel(session_row, text="")
        self.org_label.pack(side="left", padx=(0, 12))
        self.id_label = ctk.CTkLabel(session_row, text="")
        self.id_label.pack(side="left")

        self.status_bar = StatusBar(self)
        self.status_bar.pack(side="bottom", fill="x")

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(side="left", fill="both", expand=True)

        self.frames: dict = {}
        self._current: str | None = None
        self._rebuild_frames()
        self.refresh_provider_status()
        self.show_frame("login")

    # -- session ------------------------------------------------------
    def login(self, user: dict) -> None:
        self.session = {k: user.get(k) for k in SESSION_KEYS if k in user}
        self._rebuild_frames()
        self.show_frame("dashboard")

    def logout(self) -> None:
        self.session = None
        self.search_results = []
        self._cached_docs = []
        self._rebuild_frames()
        self.show_frame("login")

    def _visible_nav(self) -> list[tuple[str, str]]:
        if self.session is not None and self.session.get("role") == "admin":
            return list(HYBRID_NAV)
        return [item for item in HYBRID_NAV if item[0] != "accounts"]

    def has_capability(self, capability: str) -> bool:
        """Wrap ``core.permissions.can`` for the current session role."""
        role = (self.session or {}).get("role", "basico")
        return can(role, capability)

    def set_gated(self, widget, allowed: bool, denied_tip: str) -> None:
        """Disable ``widget`` when not ``allowed``; hover shows ``denied_tip``.

        Status-bar approach (no third-party tooltip dependency): binds
        ``<Enter>``/``<Leave>`` to display the denial reason in the shell's
        own ``StatusBar`` while hovering a disabled export button.
        Tasks 8/9 MUST reuse this helper for PDF/WORD/Print/Share buttons.
        """
        try:
            widget.configure(state="normal" if allowed else "disabled")
        except Exception:  # never break frame build on gating
            logger.debug("Gating skip: configure", exc_info=True)
            return
        key = id(widget)
        if allowed:
            self._gated_prev.pop(key, None)
            self._gated_bound_tip.pop(key, None)
            try:
                widget.unbind("<Enter>")
                widget.unbind("<Leave>")
            except Exception:
                pass
            return
        self._gated_prev[key] = denied_tip

        def _on_enter(_event=None, _w=widget, _tip=denied_tip) -> None:
            try:
                _w._gated_saved = self.status_bar.status_label.cget("text")
            except Exception:
                pass
            self.status_bar.set_status(_tip)

        def _on_leave(_event=None, _w=widget) -> None:
            try:
                prev = getattr(_w, "_gated_saved", "Pronto")
            except Exception:
                prev = "Pronto"
            self.status_bar.set_status(prev)

        try:
            if self._gated_bound_tip.get(key) != denied_tip:
                try:
                    widget.unbind("<Enter>")
                    widget.unbind("<Leave>")
                except Exception:
                    pass
                widget.bind("<Enter>", _on_enter)
                widget.bind("<Leave>", _on_leave)
                self._gated_bound_tip[key] = denied_tip
        except Exception:
            logger.debug("Gating skip: bind", exc_info=True)

    def register_export_button(self, frame_name: str, widget, capability: str) -> None:
        """Register an export-capable button for capability gating.

        Tasks 8/9 MUST reuse this registry (do not invent a second
        mechanism). ``capability`` is checked via ``has_capability()`` /
        ``core.permissions.can()``. Gating is applied immediately and
        re-applied after every ``show_frame``.
        """
        self._export_registry = [e for e in self._export_registry if e[1] is not widget]
        self._export_registry.append((frame_name, widget, capability))
        self.set_gated(widget, self.has_capability(capability),
                       f"Sem permissão: requer '{capability}'.")

    def _rebuild_frames(self) -> None:
        """Recreate content frames and refresh sidebar/header for the session."""
        for child in self.container.winfo_children():
            child.destroy()
        self._export_registry = []
        self.frames = {
            "login": LoginFrame(self.container, self),
            "home": HomeFrame(self.container, self),
            "dashboard": DashboardFrame(self.container, self),
            "documents": _PlaceholderFrame(
                self.container, self, "📄 Documentos",
                "Módulo Documentos em construção (FASE 5)."),
            "settings": SettingsFrame(self.container, self),
            "scraper": ScraperFrame(self.container, self),
            "results": ResultsFrame(self.container, self),
            "logs": LogFrame(self.container, self),
            "accounts": _PlaceholderFrame(
                self.container, self, "👥 Contas",
                "Módulo Contas em construção (FASE 6, visível só para admin)."),
        }
        if self.session is None:
            self.sidebar.pack_forget()
            self.welcome_label.configure(text="")
            self.org_label.configure(text="")
            self.id_label.configure(text="")
            self.search_entry.configure(state="disabled")
            self.logout_button.configure(state="disabled")
            self._cached_docs = []
        else:
            # Re-pack shell in creation order so the sidebar stays leftmost
            # across logout→login→logout→login cycles (pack_forget + pack
            # would otherwise move the sidebar to the end of pack order).
            for shell in (self.sidebar, self.header, self.status_bar, self.container):
                shell.pack_forget()
            self.sidebar.pack(side="left", fill="y")
            self.header.pack(side="top", fill="x")
            self.status_bar.pack(side="bottom", fill="x")
            self.container.pack(side="left", fill="both", expand=True)
            self.sidebar.set_items(self._visible_nav())
            self.welcome_label.configure(
                text=f"Bem vindo, {self.session.get('name', '')}")
            self.org_label.configure(text=str(self.session.get("org", "")))
            self.id_label.configure(text=f"ID: {self.session.get('id', '')}")
            self.search_entry.configure(state="normal")
            self.logout_button.configure(state="normal")
            self.refresh_documents()
        self._current = None
        self._apply_export_gating()

    def _apply_export_gating(self) -> None:
        """Apply capability gating to all registered export buttons."""
        for _frame_name, widget, capability in list(self._export_registry):
            try:
                if widget.winfo_exists():
                    self.set_gated(widget, self.has_capability(capability),
                                   f"Sem permissão: requer '{capability}'.")
            except Exception:
                logger.debug("Gating skip: registry entry", exc_info=True)

    # -- global search ------------------------------------------------
    def _load_documents_safe(self) -> list:
        """Load documents JSON defensively; ``[]`` on missing/corrupt data."""
        try:
            docs = repository.load_documents(DOCUMENTS_JSON)
            return list(docs) if isinstance(docs, list) else []
        except Exception:
            logger.debug("Search docs unavailable", exc_info=True)
            return []

    def refresh_documents(self) -> None:
        """Reload the cached document list (login/rebuild + explicit refresh)."""
        self._cached_docs = self._load_documents_safe()

    def _on_search(self, _event=None) -> None:
        if self._search_after is not None:
            try:
                self.after_cancel(self._search_after)
            except Exception:
                pass
            self._search_after = None
        self._search_after = self.after(SEARCH_DEBOUNCE_MS, self._do_search)

    def _do_search(self) -> None:
        self._search_after = None
        try:
            text = self.search_entry.get()
        except Exception:
            text = ""
        try:
            filtered = repository.search(self._cached_docs, text)
        except Exception:
            logger.debug("Search failed", exc_info=True)
            filtered = []
        self.search_results = filtered
        for key in ("dashboard", "documents"):
            frame = self.frames.get(key)
            if frame is not None and hasattr(frame, "apply_search"):
                try:
                    frame.apply_search(filtered)
                except Exception:
                    logger.debug("apply_search skip: %s", key, exc_info=True)

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
        if frame_name in self.sidebar.items:
            self.sidebar.set_active(frame_name)
        if hasattr(frame, "on_show"):
            frame.on_show()
        self._apply_export_gating()

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
