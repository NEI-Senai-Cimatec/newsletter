# gui/frames/login_frame.py
import customtkinter as ctk

from core import database
from core.database import DB_FILE


class LoginFrame(ctk.CTkFrame):
    """Auth gate: login, Sign Up (basico/pendente), recovery, admin bootstrap."""

    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._bootstrap_dialog = None
        ctk.CTkLabel(self, text="GLOBAL QUANTUM INTELLIGENCE",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(32, 4))
        ctk.CTkLabel(self, text="Centro de Competências EMBRAPII CIMATEC em Tecnologias Quânticas").pack()
        ctk.CTkLabel(self, text="Quantum Industrial Innovation – QuIIN Associação Tecnológica").pack(pady=(0, 24))
        self.user_entry = ctk.CTkEntry(self, width=280, placeholder_text="Usuário")
        self.user_entry.pack(pady=6)
        self.pass_entry = ctk.CTkEntry(self, width=280, placeholder_text="Password", show="*")
        self.pass_entry.pack(pady=6)
        ctk.CTkButton(self, text="Entrar", width=280, command=self._login).pack(pady=(12, 6))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=6)
        ctk.CTkButton(row, text="Esqueci minha senha", width=136, fg_color="transparent",
                      command=self._recovery).pack(side="left", padx=4)
        ctk.CTkButton(row, text="Sign Up", width=136, fg_color="transparent",
                      command=self._signup).pack(side="left", padx=4)
        self.msg = ctk.CTkLabel(self, text="")
        self.msg.pack(pady=8)

    def on_show(self) -> None:
        database.init_db(DB_FILE)
        if not database.list_users(DB_FILE):
            self._bootstrap_wizard()

    def _fail(self, text: str) -> None:
        self.msg.configure(text=text)

    def _login(self) -> None:
        user = database.authenticate(DB_FILE, self.user_entry.get().strip(),
                                     self.pass_entry.get())
        if user is None:
            self._fail("Usuário ou senha inválidos.")
            return
        if user["status"] != "ativo":
            self._fail("Conta pendente ou revogada. Aguarde aprovação de um administrador.")
            return
        self.app.login(user)

    def _signup(self) -> None:
        try:
            database.create_user(DB_FILE, self.user_entry.get().strip(), self.user_entry.get().strip(),
                                 "QuIIN", True, "basico", self.pass_entry.get(),
                                 created_by="signup", status="pendente")
        except ValueError:
            self._fail("Nome de usuário já existe.")
            return
        self._fail("Conta criada. Aguarde aprovação de um administrador.")

    def _recovery(self) -> None:
        self._fail("Contate um administrador para redefinir sua senha.")

    def _bootstrap_wizard(self) -> None:
        if (self._bootstrap_dialog is not None
                and self._bootstrap_dialog.winfo_exists()):
            try:
                self._bootstrap_dialog.lift()
                self._bootstrap_dialog.focus_force()
            except Exception:
                pass
            return
        dialog = ctk.CTkToplevel(self)
        self._bootstrap_dialog = dialog
        dialog.title("Criar administrador inicial")
        dialog.geometry("420x360")

        def _on_close() -> None:
            self._bootstrap_dialog = None
            try:
                dialog.destroy()
            except Exception:
                pass

        try:
            dialog.protocol("WM_DELETE_WINDOW", _on_close)
        except Exception:
            pass
        name = ctk.CTkEntry(dialog, placeholder_text="Nome completo")
        name.pack(padx=20, pady=8, fill="x")
        username = ctk.CTkEntry(dialog, placeholder_text="Usuário")
        username.pack(padx=20, pady=8, fill="x")
        password = ctk.CTkEntry(dialog, placeholder_text="Senha", show="*")
        password.pack(padx=20, pady=8, fill="x")

        def _create() -> None:
            try:
                code = database.bootstrap_admin(DB_FILE, name.get().strip(),
                                                username.get().strip(), password.get())
            except ValueError as exc:
                self._fail(str(exc))
                return
            self._bootstrap_dialog = None
            dialog.destroy()
            done = ctk.CTkToplevel(self)
            done.title("Guarde este código")
            done.geometry("460x200")
            ctk.CTkLabel(done, text="Código de recuperação (exibido uma única vez):").pack(padx=20, pady=8)
            ctk.CTkLabel(done, text=code, font=ctk.CTkFont(size=14, weight="bold")).pack(padx=20, pady=8)
            ctk.CTkLabel(done, text="Guarde em local seguro. Ele recupera o admin.").pack(padx=20, pady=8)

        ctk.CTkButton(dialog, text="Criar administrador", command=_create).pack(padx=20, pady=12)
