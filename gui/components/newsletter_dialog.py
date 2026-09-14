# gui/components/newsletter_dialog.py
"""Modal de newsletter personalizada: seleção com checkboxes + ordem ↑/↓.

Task 9: lista os documentos filtrados em ordem de relevância; o usuário
marca os que entram e reordena com ↑/↓. Ao confirmar, ``on_confirm`` recebe
``(chosen, dialog)`` com os docs na ordem exibida — o chamador (Dashboard)
pede o destino e exporta no worker (nunca na thread Tk).
"""
import customtkinter as ctk

from gui.theme.colors import NORMAL_FONT, SECTION_FONT, SMALL_FONT


def open_newsletter_modal(parent, ranked: list, weights: dict,
                          view_relevance, on_confirm) -> None:
    """Abre o modal; chama ``on_confirm(chosen, dialog)`` ao exportar."""
    dialog = ctk.CTkToplevel(parent)
    dialog.title("Newsletter personalizada")
    dialog.geometry("640x520")
    try:
        dialog.transient(parent)
        dialog.grab_set()
    except Exception:
        pass
    ctk.CTkLabel(dialog, text="Selecionar documentos",
                 font=ctk.CTkFont(**SECTION_FONT)).pack(anchor="w",
                                                        padx=16, pady=(12, 0))
    ctk.CTkLabel(
        dialog,
        text="Marque os documentos e use ↑ ↓ para ordenar. "
             "A ordem da lista é a ordem do arquivo.",
        font=ctk.CTkFont(**SMALL_FONT)).pack(anchor="w", padx=16, pady=(0, 4))
    top = ctk.CTkFrame(dialog, fg_color="transparent")
    top.pack(fill="x", padx=16, pady=(0, 4))
    scroll = ctk.CTkScrollableFrame(dialog, height=300)
    scroll.pack(fill="both", expand=True, padx=16, pady=4)
    error = ctk.CTkLabel(dialog, text="", text_color="#F85149")
    error.pack(padx=16, pady=2)
    rows: list[dict] = []

    def _repack() -> None:
        for row in rows:
            try:
                row["frame"].pack_forget()
            except Exception:
                pass
        for row in rows:
            try:
                row["frame"].pack(fill="x", pady=1)
            except Exception:
                pass

    def _move(row: dict, delta: int) -> None:
        i = rows.index(row)
        j = i + delta
        if not 0 <= j < len(rows):
            return
        rows[i], rows[j] = rows[j], rows[i]
        _repack()

    for doc in ranked:
        title = str(doc.get("newsletter") or doc.get("title")
                    or "(sem título)")
        rel = view_relevance(doc, weights)
        frame = ctk.CTkFrame(scroll, fg_color="transparent")
        frame.pack(fill="x", pady=1)
        var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(frame, text=f"{rel:>3} · {title[:70]}",
                        variable=var,
                        font=ctk.CTkFont(**NORMAL_FONT)).pack(side="left",
                                                              fill="x",
                                                              expand=True)
        row = {"doc": doc, "var": var, "frame": frame}
        ctk.CTkButton(frame, text="↑", width=32,
                      command=lambda r=row: _move(r, -1)).pack(side="left",
                                                               padx=2)
        ctk.CTkButton(frame, text="↓", width=32,
                      command=lambda r=row: _move(r, 1)).pack(side="left",
                                                              padx=2)
        rows.append(row)

    def _select_all(value: bool) -> None:
        for row in rows:
            try:
                row["var"].set(value)
            except Exception:
                pass

    ctk.CTkButton(top, text="Selecionar todos",
                  command=lambda: _select_all(True)).pack(side="left",
                                                          padx=(0, 8))
    ctk.CTkButton(top, text="Limpar",
                  command=lambda: _select_all(False)).pack(side="left")

    def _confirm() -> None:
        chosen = [row["doc"] for row in rows if row["var"].get()]
        if not chosen:
            error.configure(text="Selecione ao menos um documento.")
            return
        on_confirm(chosen, dialog)

    bottom = ctk.CTkFrame(dialog, fg_color="transparent")
    bottom.pack(fill="x", padx=16, pady=(4, 12))
    ctk.CTkButton(bottom, text="Exportar",
                  command=_confirm).pack(side="left", padx=(0, 8))
    ctk.CTkButton(bottom, text="Cancelar", fg_color="transparent",
                  command=dialog.destroy).pack(side="left")
