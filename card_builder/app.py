"""
app.py – CardBuilder: main window, CRUD, card list.
"""

import copy
import tkinter as tk
from tkinter import ttk, messagebox

from .constants import CARD_W, CARD_H, BLOCK_TYPES
from .models import (
    empty_card, empty_block, load_cards, save_cards,
    ALL_CARD_TYPES, CARD_TYPE_PARENT,
)
from .CardTypes import get_editor, get_renderer


class CardBuilder:

    def __init__(self, root: tk.Tk = None,
                 container_frame: tk.Frame = None) -> None:
        if container_frame is not None:
            self.root       = root
            self._container = container_frame
        else:
            self.root       = root
            self._container = root
            self.root.title("Card Builder")
            self.root.geometry("1460x860")
            self.root.configure(bg="#1a1a1a")

        self.cards_by_type: dict = {ct: load_cards(ct) for ct in ALL_CARD_TYPES}

        # Default to Spells
        self.current_type: str      = "Spells"
        self.current_card: dict     = empty_card("Spells")
        self.current_idx:  int|None = None

        self._current_editor   = None
        self._current_renderer = None

        self._build_ui()
        self._refresh_card_list()
        self._refresh_preview()

    # ── UI skeleton ───────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._build_topbar()
        main = tk.Frame(self._container, bg="#1a1a1a")
        main.pack(fill="both", expand=True)
        self._build_card_list(main)
        self._build_editor_panel(main)
        self._build_preview_panel(main)

    def _build_topbar(self) -> None:
        top = tk.Frame(self._container, bg="#111", pady=4)
        top.pack(fill="x")
        tk.Label(top, text="✦ CARD BUILDER ✦", bg="#111", fg="gold",
                 font=("Palatino Linotype", 14, "bold")).pack(side="left", padx=12)
        for text, cmd, color in (
            ("💾 Save Card",   self._save_card,   "#1a6e3c"),
            ("📄 New Card",    self._new_card,    "#1a3e8e"),
            ("🗑 Delete Card", self._delete_card, "#8e1a1a"),
        ):
            tk.Button(top, text=text, command=cmd,
                      bg=color, fg="white", font=("Arial", 9)).pack(
                side="right", padx=4)

    # ── Card list ─────────────────────────────────────────────────────────────

    def _build_card_list(self, parent: tk.Widget) -> None:
        left = tk.Frame(parent, bg="#111", width=190)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        sel = tk.Frame(left, bg="#111")
        sel.pack(fill="x", padx=4, pady=(6, 2))
        tk.Label(sel, text="Type:", bg="#111", fg="#aaa",
                 font=("Arial", 8)).pack(side="left")
        self._type_var = tk.StringVar(value=self.current_type)
        cb = ttk.Combobox(sel, textvariable=self._type_var,
                          values=ALL_CARD_TYPES, state="readonly",
                          width=11, font=("Arial", 8))
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", self._on_type_changed)

        self._cat_label = tk.Label(left,
                                   text=CARD_TYPE_PARENT.get(self.current_type, ""),
                                   bg="#111", fg="#555",
                                   font=("Arial", 7, "italic"))
        self._cat_label.pack()

        tk.Label(left, text="Cards", bg="#111", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(pady=(4, 2))
        self._card_listbox = tk.Listbox(
            left, bg="#1a1a1a", fg="white",
            selectbackground="#1a6e3c",
            font=("Arial", 8), activestyle="none",
            relief="flat", bd=0)
        self._card_listbox.pack(fill="both", expand=True, padx=4, pady=4)
        self._card_listbox.bind("<<ListboxSelect>>", self._load_card_from_list)

    def _on_type_changed(self, _=None) -> None:
        self.current_type = self._type_var.get()
        self._cat_label.config(text=CARD_TYPE_PARENT.get(self.current_type, ""))
        self.current_idx  = None
        # Create a fresh blank card WITHOUT autosaving it
        self.current_card = empty_card(self.current_type)
        self._refresh_card_list()
        self._load_editor()
        # Render preview but do NOT autosave
        self._render_only()

    # ── Editor panel ──────────────────────────────────────────────────────────

    def _build_editor_panel(self, parent: tk.Widget) -> None:
        self._editor_container = tk.Frame(parent, bg="#1a1a1a")
        self._editor_container.pack(side="left", fill="both", expand=True)
        self._load_editor()

    def _load_editor(self) -> None:
        for w in self._editor_container.winfo_children():
            w.destroy()
        self._current_editor = None
        EditorClass = get_editor(self.current_type)
        self._current_editor = EditorClass(
            self._editor_container,
            card=self.current_card,
            on_change=self._refresh_preview,
        )
        self._current_editor.pack(fill="both", expand=True)

    # ── Preview panel ─────────────────────────────────────────────────────────

    def _build_preview_panel(self, parent: tk.Widget) -> None:
        right = tk.Frame(parent, bg="#111", width=CARD_W + 20)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        tk.Label(right, text="Preview", bg="#111", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(pady=(6, 2))
        self._preview_canvas = tk.Canvas(right, width=CARD_W, height=CARD_H,
                                         bg="#000", highlightthickness=1,
                                         highlightbackground="#444")
        self._preview_canvas.pack(pady=8)
        self._current_renderer = get_renderer(self.current_type)(
            self._preview_canvas)

    def _render_only(self, *_) -> None:
        """Render preview without autosaving."""
        if not hasattr(self, "_current_renderer"):
            return
        ct = self.current_card.get("card_type", self.current_type)
        RendClass = get_renderer(ct)
        if not isinstance(self._current_renderer, RendClass):
            self._current_renderer = RendClass(self._preview_canvas)
        self._current_renderer.render(self.current_card)

    def _refresh_preview(self, *_) -> None:
        """Render preview AND autosave."""
        self._render_only()
        self._autosave()

    def _autosave(self) -> None:
        card = self.current_card
        if not card.get("name", "").strip() or card.get("name") == "New Card":
            return   # don't save blank/template cards
        card["card_type"] = self.current_type
        if self.current_idx is not None:
            self.cards[self.current_idx] = card
        else:
            self.cards.append(card)
            self.current_idx = len(self.cards) - 1
            self._refresh_card_list()
        try:
            save_cards(self.cards, self.current_type)
        except Exception:
            pass

    # ── Card list helpers ─────────────────────────────────────────────────────

    @property
    def cards(self) -> list:
        return self.cards_by_type[self.current_type]

    def _refresh_card_list(self) -> None:
        lb = self._card_listbox
        lb.delete(0, "end")
        for c in self.cards:
            lb.insert("end", c.get("name", "?"))
        if self.current_idx is not None:
            lb.selection_clear(0, "end")
            lb.selection_set(self.current_idx)

    def _load_card_from_list(self, _=None) -> None:
        sel = self._card_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.current_idx  = idx
        self.current_card = copy.deepcopy(self.cards[idx])
        self._load_editor()
        self._render_only()

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def _new_card(self) -> None:
        self.current_card = empty_card(self.current_type)
        self.current_idx  = None
        self._card_listbox.selection_clear(0, "end")
        self._load_editor()
        self._render_only()

    def _save_card(self) -> None:
        card = self.current_card
        if not card.get("name", "").strip():
            messagebox.showerror("Error", "Card needs a name.")
            return
        card["card_type"] = self.current_type
        if self.current_idx is not None:
            self.cards[self.current_idx] = copy.deepcopy(card)
        else:
            self.cards.append(copy.deepcopy(card))
            self.current_idx = len(self.cards) - 1
        save_cards(self.cards, self.current_type)
        self._refresh_card_list()
        self._show_status(f"Gespeichert ✓  [{self.current_type}]")

    def _delete_card(self) -> None:
        if self.current_idx is None:
            return
        if not messagebox.askyesno("Delete", "Diese Karte löschen?"):
            return
        self.cards.pop(self.current_idx)
        save_cards(self.cards, self.current_type)
        self.current_idx  = None
        self.current_card = empty_card(self.current_type)
        self._refresh_card_list()
        self._load_editor()
        self._render_only()

    def _show_status(self, msg: str, ms: int = 2000) -> None:
        bar = tk.Label(self.root, text=msg, bg="#1a6e3c", fg="white",
                       font=("Arial", 10, "bold"))
        bar.place(relx=0, rely=1.0, anchor="sw", relwidth=1)
        self.root.after(ms, bar.destroy)
