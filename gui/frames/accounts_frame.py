# gui/frames/accounts_frame.py
"""QuIIN user governance: list, grant, approve, revoke, password reset."""
import logging

import customtkinter as ctk

from core import database
from core.audit import log_event
from core.database import DB_FILE
from gui.theme.colors import NORMAL_FONT, SECTION_FONT, SMALL_FONT, TITLE_FONT

logger = logging.getLogger(__name__)

ROLE_LABELS = {"admin": "Administrador", "premium": "Premium", "basico": "Básico"}

ROLE_OPTIONS = (
    ("admin", "Administrador (edita, visualiza e imprime)"),
    ("premium", "Premium (visualiza e imprime)"),
    ("basico", "Básico (visualiza)"),
)


class AccountsFrame(ctk.CTkFrame):
    """Admin-only user table + ``Fornecer acesso`` form + row actions.

    Every mutation (grant/approve/revoke/reset) is recorded via
    ``core.audit.log_event`` with the logged user as actor.
    """

    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._users: list = []

        ctk.CTkLabel(self, text="👥 Contas",
                     font=ctk.CTkFont(**TITLE_FONT)).pack(anchor="w", padx=20,
                                                          pady=(16, 4))
        self.status_label = ctk.CTkLabel(self, text="",
                                         font=ctk.CTkFont(**NORMAL_FONT))
        self.status_label.pack(anchor="w", padx=20, pady=(0, 8))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # ---- User table ----
        table_outer = ctk.CTkFrame(scroll)
        table_outer.pack(fill="both", expand=True, padx=8, pady=8)
        ctk.CTkLabel(table_outer, text="Usuários",
                     font=ctk.CTkFont(**SECTION_FONT)).pack(anchor="w", padx=12,
                                                            pady=(10, 2))
        ctk.CTkLabel(
            table_outer,
            text="Nome | Username | Tipo | Organização | Interno/Externo | Status",
            font=ctk.CTkFont(**SMALL_FONT)).pack(anchor="w", padx=12,
                                                 pady=(0, 4))
        self.table_box = ctk.CTkScrollableFrame(table_outer, height=220)
        self.table_box.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # ---- Fornecer acesso ----
        grant_outer = ctk.CTkFrame(scroll)
        grant_outer.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(grant_outer, text="Fornecer acesso",
                     font=ctk.CTkFont(**SECTION_FONT)).pack(anchor="w", padx=12,
                                                            pady=(10, 2))
        grant_body = ctk.CTkFrame(grant_outer, fg_color="transparent")
        grant_body.pack(fill="x", padx=0, pady=(0, 10))
        grant_body.columnconfigure(1, weight=1)

        ctk.CTkLabel(grant_body, text="Nome:",
                     font=ctk.CTkFont(**NORMAL_FONT)).grid(row=0, column=0,
                                                           sticky="w", padx=12,
                                                           pady=4)
        self.new_name_entry = ctk.CTkEntry(grant_body, width=280,
                                           placeholder_text="Nome completo")
        self.new_name_entry.grid(row=0, column=1, sticky="ew", padx=12, pady=4)

        ctk.CTkLabel(grant_body, text="Usuário:",
                     font=ctk.CTkFont(**NORMAL_FONT)).grid(row=1, column=0,
                                                           sticky="w", padx=12,
                                                           pady=4)
        self.new_user_entry = ctk.CTkEntry(grant_body, width=280,
                                           placeholder_text="Nome de usuário")
        self.new_user_entry.grid(row=1, column=1, sticky="ew", padx=12, pady=4)

        ctk.CTkLabel(grant_body, text="Senha:",
                     font=ctk.CTkFont(**NORMAL_FONT)).grid(row=2, column=0,
                                                           sticky="w", padx=12,
                                                           pady=4)
        self.new_pass_entry = ctk.CTkEntry(grant_body, width=280,
                                           placeholder_text="Senha inicial",
                                           show="*")
        self.new_pass_entry.grid(row=2, column=1, sticky="ew", padx=12, pady=4)

        ctk.CTkLabel(grant_body, text="Organização:",
                     font=ctk.CTkFont(**NORMAL_FONT)).grid(row=3, column=0,
                                                           sticky="w", padx=12,
                                                           pady=4)
        self.new_org_entry = ctk.CTkEntry(grant_body, width=280,
                                          placeholder_text="Organização")
        self.new_org_entry.grid(row=3, column=1, sticky="ew", padx=12, pady=4)

        self.internal_var = ctk.BooleanVar(value=True)
        self.internal_check = ctk.CTkCheckBox(grant_body, text="Usuário interno",
                                              variable=self.internal_var,
                                              font=ctk.CTkFont(**NORMAL_FONT))
        self.internal_check.grid(row=4, column=1, sticky="w", padx=12, pady=4)

        ctk.CTkLabel(grant_body, text="Tipo:",
                     font=ctk.CTkFont(**NORMAL_FONT)).grid(row=5, column=0,
                                                           sticky="nw", padx=12,
                                                           pady=4)
        role_box = ctk.CTkFrame(grant_body, fg_color="transparent")
        role_box.grid(row=5, column=1, sticky="w", padx=12, pady=4)
        self.role_var = ctk.StringVar(value=ROLE_OPTIONS[2][1])
        for _key, caption in ROLE_OPTIONS:
            ctk.CTkRadioButton(role_box, text=caption, variable=self.role_var,
                               value=caption,
                               font=ctk.CTkFont(**NORMAL_FONT)).pack(anchor="w",
                                                                     pady=2)

        ctk.CTkLabel(grant_body, text="Solicitante:",
                     font=ctk.CTkFont(**NORMAL_FONT)).grid(row=6, column=0,
                                                           sticky="w", padx=12,
                                                           pady=4)
        self.requester_entry = ctk.CTkEntry(grant_body, width=280)
        self.requester_entry.grid(row=6, column=1, sticky="ew", padx=12, pady=4)
        self.requester_entry.configure(state="disabled")

        ctk.CTkButton(grant_outer, text="Fornecer acesso",
                      command=self._grant_access).pack(anchor="w", padx=12,
                                                      pady=(0, 12))

    # -- lifecycle ------------------------------------------------------
    def on_show(self) -> None:
        """Reload the user list (admin only) and refresh the form."""
        try:
            self.requester_entry.configure(state="normal")
            self.requester_entry.delete(0, "end")
            self.requester_entry.insert(0, self._current_user())
            self.requester_entry.configure(state="disabled")
        except Exception:
            logger.debug("Requester refresh failed", exc_info=True)
        role = (self.app.session or {}).get("role", "")
        if role != "admin":
            self._users = []
            self._render_table()
            self.status_label.configure(
                text="Acesso restrito a administradores.")
            return
        try:
            self._users = database.list_users(DB_FILE)
        except Exception as exc:
            logger.debug("list_users failed", exc_info=True)
            self._users = []
            self.status_label.configure(
                text=f"Não foi possível carregar os usuários: {exc}")
            self._render_table()
            return
        self.status_label.configure(
            text=f"{len(self._users)} usuário(s) cadastrado(s).")
        self._render_table()

    # -- helpers --------------------------------------------------------
    def _current_user(self) -> str:
        try:
            return str((self.app.session or {}).get("username", ""))
        except Exception:
            return ""

    @staticmethod
    def _role_from_caption(caption: str) -> str:
        for key, text in ROLE_OPTIONS:
            if text == caption:
                return key
        return "basico"

    def _render_table(self) -> None:
        for child in self.table_box.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass
        if not self._users:
            ctk.CTkLabel(self.table_box,
                         text="Nenhum usuário para exibir.").pack(pady=20)
            return
        for user in self._users:
            username = user.get("username", "")
            name = user.get("name", "")
            role_label = ROLE_LABELS.get(user.get("role", ""), user.get("role", ""))
            org = user.get("org", "") or "—"
            kind = "Interno" if user.get("internal") else "Externo"
            status = user.get("status", "")
            row = ctk.CTkFrame(self.table_box)
            row.pack(fill="x", padx=4, pady=2)
            ctk.CTkLabel(
                row,
                text=f"{name} | {username} | {role_label} | {org} | {kind} | {status}",
                font=ctk.CTkFont(**NORMAL_FONT)).pack(side="left", padx=8,
                                                      pady=4)
            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.pack(side="right", padx=8, pady=4)
            if status == "pendente":
                ctk.CTkButton(actions, text="Aprovar", width=90,
                              command=lambda u=username: self._approve(u)).pack(
                                  side="left", padx=2)
            if status != "revogado":
                ctk.CTkButton(actions, text="Cancelar acesso", width=120,
                              command=lambda u=username: self._revoke(u)).pack(
                                  side="left", padx=2)
            ctk.CTkButton(actions, text="Redefinir senha", width=120,
                          command=lambda u=username: self._open_reset_dialog(u)).pack(
                              side="left", padx=2)

    # -- mutations (every action calls log_event) -----------------------
    def _grant_access(self) -> None:
        name = self.new_name_entry.get().strip()
        username = self.new_user_entry.get().strip()
        password = self.new_pass_entry.get()
        org = self.new_org_entry.get().strip()
        internal = bool(self.internal_var.get())
        role = self._role_from_caption(self.role_var.get())
        requester = self._current_user()
        if not name or not username or not password:
            self.status_label.configure(
                text="Preencha nome, usuário e senha para fornecer acesso.")
            return
        try:
            database.create_user(DB_FILE, username, name, org, internal, role,
                                 password, created_by=requester or "system",
                                 status="ativo")
        except ValueError as exc:
            self.status_label.configure(text=str(exc))
            return
        except Exception as exc:
            logger.debug("create_user failed", exc_info=True)
            self.status_label.configure(
                text=f"Não foi possível criar o usuário: {exc}")
            return
        log_event(requester, "grant_access", username)
        self.new_name_entry.delete(0, "end")
        self.new_user_entry.delete(0, "end")
        self.new_pass_entry.delete(0, "end")
        self.new_org_entry.delete(0, "end")
        self.on_show()
        self.status_label.configure(
            text=f"Acesso fornecido a {username} ({ROLE_LABELS[role]}).")

    def _approve(self, username: str) -> None:
        database.set_status(DB_FILE, username, "ativo")
        log_event(self.app.session["username"], "approve_user", username)
        self.on_show()

    def _revoke(self, username: str) -> None:
        database.set_status(DB_FILE, username, "revogado")
        log_event(self.app.session["username"], "revoke_user", username)
        self.on_show()

    def _open_reset_dialog(self, username: str) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Redefinir senha")
        dialog.geometry("420x200")
        ctk.CTkLabel(dialog,
                     text=f"Nova senha para {username}:").pack(padx=20,
                                                               pady=(12, 4))
        entry = ctk.CTkEntry(dialog, show="*")
        entry.pack(padx=20, pady=4, fill="x")
        error = ctk.CTkLabel(dialog, text="")
        error.pack(padx=20, pady=2)

        def _confirm() -> None:
            new_password = entry.get()
            if not new_password:
                error.configure(text="Informe a nova senha.")
                return
            try:
                self._reset_password(username, new_password)
            except (ValueError, OSError) as exc:
                error.configure(text=str(exc))
                return
            try:
                dialog.destroy()
            except Exception:
                pass

        row = ctk.CTkFrame(dialog, fg_color="transparent")
        row.pack(padx=20, pady=10, fill="x")
        ctk.CTkButton(row, text="Salvar", command=_confirm).pack(side="left",
                                                                 padx=(0, 8))
        ctk.CTkButton(row, text="Cancelar", fg_color="transparent",
                      command=dialog.destroy).pack(side="left")

    def _reset_password(self, username: str, new_password: str) -> None:
        database.set_password(DB_FILE, username, new_password)
        log_event(self.app.session["username"], "reset_password", username)
        self.on_show()
