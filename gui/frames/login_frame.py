# gui/frames/login_frame.py
import customtkinter as ctk

from core import database
from core.database import DB_FILE, is_admin_user


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
        username = self.user_entry.get().strip()
        password = self.pass_entry.get()
        if not username or not password:
            self._fail("Informe usuário e senha.")
            return
        try:
            database.create_user(DB_FILE, username, username,
                                 "QuIIN", True, "basico", password,
                                 created_by="signup", status="pendente")
        except ValueError:
            self._fail("Nome de usuário já existe.")
            return
        self._fail("Conta criada. Aguarde aprovação de um administrador.")

    def _recovery(self) -> None:
        username = self.user_entry.get().strip()
        try:
            admin = bool(username) and is_admin_user(DB_FILE, username)
        except Exception:
            admin = False
        if not admin:
            self._fail("Contate um administrador para redefinir sua senha.")
            return
        self._open_admin_recovery_dialog(username)

    def _open_admin_recovery_dialog(self, username: str) -> None:
        """Recuperação do admin via código de uso único + nova senha."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Recuperar administrador")
        dialog.geometry("420x280")
        try:
            dialog.transient(self)
            dialog.grab_set()
        except Exception:
            pass
        ctk.CTkLabel(dialog,
                     text=f"Código de recuperação para {username}:").pack(
                         padx=20, pady=(12, 4))
        code_entry = ctk.CTkEntry(dialog, placeholder_text="Código de recuperação")
        code_entry.pack(padx=20, pady=4, fill="x")
        ctk.CTkLabel(dialog, text="Nova senha:").pack(padx=20, pady=(8, 4))
        new_pass_entry = ctk.CTkEntry(dialog, placeholder_text="Nova senha",
                                      show="*")
        new_pass_entry.pack(padx=20, pady=4, fill="x")
        error = ctk.CTkLabel(dialog, text="")
        error.pack(padx=20, pady=2)

        def _confirm() -> None:
            code = code_entry.get().strip()
            new_password = new_pass_entry.get()
            if not code or not new_password:
                error.configure(text="Informe o código e a nova senha.")
                return
            try:
                ok = database.reset_admin_via_recovery_code(
                    DB_FILE, code, new_password)
            except Exception as exc:
                error.configure(text=f"Não foi possível redefinir: {exc}")
                return
            if not ok:
                error.configure(text="Código inválido.")
                return
            try:
                dialog.destroy()
            except Exception:
                pass
            self._fail("Senha redefinida. Entre com a nova senha.")

        row = ctk.CTkFrame(dialog, fg_color="transparent")
        row.pack(padx=20, pady=10, fill="x")
        ctk.CTkButton(row, text="Redefinir", command=_confirm).pack(
            side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Cancelar", fg_color="transparent",
                      command=dialog.destroy).pack(side="left")

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
        try:
            dialog.transient(self)
            dialog.grab_set()
        except Exception:
            pass

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
            try:
                done.transient(self)
                done.grab_set()
            except Exception:
                pass
            ctk.CTkLabel(done, text="Código de recuperação (exibido uma única vez):").pack(padx=20, pady=8)
            ctk.CTkLabel(done, text=code, font=ctk.CTkFont(size=14, weight="bold")).pack(padx=20, pady=8)
            ctk.CTkLabel(done, text="Guarde em local seguro. Ele recupera o admin.").pack(padx=20, pady=8)

        ctk.CTkButton(dialog, text="Criar administrador", command=_create).pack(padx=20, pady=12)
