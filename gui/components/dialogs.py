# gui/components/dialogs.py
"""Native confirmation/error popups (thin wrappers over tkinter.messagebox)."""
import tkinter.messagebox as messagebox


def show_error(parent, message: str, title: str = "Erro") -> None:
    """Show a modal error dialog."""
    messagebox.showerror(title, message, parent=parent)


def show_warning(parent, message: str, title: str = "Atenção") -> None:
    """Show a modal warning dialog."""
    messagebox.showwarning(title, message, parent=parent)


def show_info(parent, message: str, title: str = "Informação") -> None:
    """Show a modal information dialog."""
    messagebox.showinfo(title, message, parent=parent)


def ask_confirm(parent, message: str, title: str = "Confirmar") -> bool:
    """Show a yes/no dialog; return True when the user confirms."""
    return messagebox.askyesno(title, message, parent=parent)
