"""
app.py – CardBuilder: the main application window.
"""

import copy
import tkinter as tk
from tkinter import ttk, messagebox

from .constants import ELEMENTS, BLOCK_TYPES, CARD_W, CARD_H
from .models import empty_card, empty_block, load_cards, save_cards
from .renderer import CardRenderer
from .widgets import BlockEditor


class CardBuilder:
    """Main window: card list (left) | scrollable editor (centre) | preview (right)."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Card Builder")
        self.root.geometry("1380x820")
        self.root.configure(bg="#1a1a1a")

        self.cards:        list = load_cards()
        self.current_card: dict = empty_card()
        self.current_idx:  int | None = None

        self._build_ui()
        self._refresh_card_list()
        self._refresh_preview()

    # ── UI skeleton ───────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self._build_topbar()

        main = tk.Frame(self.root, bg="#1a1a1a")
        main.pack(fill="both", expand=True)

        self._build_card_list(main)
        self._build_editor_panel(main)
        self._build_preview_panel(main)

    def _build_topbar(self) -> None:
        top = tk.Frame(self.root, bg="#111", pady=4)
        top.pack(fill="x")

        tk.Label(top, text="✦ CARD BUILDER ✦",
                 bg="#111", fg="gold",
                 font=("Palatino Linotype", 14, "bold")).pack(side="left", padx=12)

        for text, cmd, color in (
            ("💾 Save Card",   self._save_card,   "#1a6e3c"),
            ("📄 New Card",    self._new_card,    "#1a3e8e"),
            ("🗑 Delete Card", self._delete_card, "#8e1a1a"),
        ):
            tk.Button(top, text=text, command=cmd,
                      bg=color, fg="white", font=("Arial", 9)).pack(
                side="right", padx=4)

    # ── Card list (left panel) ────────────────────────────────────────────────

    def _build_card_list(self, parent: tk.Widget) -> None:
        left = tk.Frame(parent, bg="#111", width=160)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        tk.Label(left, text="Cards", bg="#111", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(pady=(6, 2))

        self._card_listbox = tk.Listbox(
            left, bg="#1a1a1a", fg="white",
            selectbackground="#1a6e3c",
            font=("Arial", 8), activestyle="none",
            relief="flat", bd=0,
        )
        self._card_listbox.pack(fill="both", expand=True, padx=4, pady=4)
        self._card_listbox.bind("<<ListboxSelect>>", self._load_card_from_list)

    # ── Scrollable editor (centre panel) ─────────────────────────────────────

    def _build_editor_panel(self, parent: tk.Widget) -> None:
        outer = tk.Frame(parent, bg="#1a1a1a")
        outer.pack(side="left", fill="both", expand=True)

        scrollbar = tk.Scrollbar(outer, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self._center_canvas = tk.Canvas(
            outer, bg="#1a1a1a",
            yscrollcommand=scrollbar.set,
            highlightthickness=0,
        )
        self._center_canvas.pack(fill="both", expand=True)
        scrollbar.config(command=self._center_canvas.yview)

        self._editor_frame = tk.Frame(self._center_canvas, bg="#1a1a1a")
        self._editor_win   = self._center_canvas.create_window(
            (0, 0), window=self._editor_frame, anchor="nw")

        self._editor_frame.bind("<Configure>", self._on_editor_resize)
        self._center_canvas.bind("<Configure>", self._on_canvas_resize)
        self._center_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._center_canvas.bind("<Button-4>",   self._on_mousewheel)
        self._center_canvas.bind("<Button-5>",   self._on_mousewheel)

        self._build_editor()

    def _on_editor_resize(self, _=None) -> None:
        self._center_canvas.configure(
            scrollregion=self._center_canvas.bbox("all"))

    def _on_canvas_resize(self, event) -> None:
        self._center_canvas.itemconfig(self._editor_win, width=event.width)

    def _on_mousewheel(self, event) -> None:
        if event.num == 4:
            self._center_canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._center_canvas.yview_scroll(1, "units")
        else:
            self._center_canvas.yview_scroll(
                int(-1 * (event.delta / 120)), "units")

    # ── Preview (right panel) ────────────────────────────────────────────────

    def _build_preview_panel(self, parent: tk.Widget) -> None:
        right = tk.Frame(parent, bg="#111", width=CARD_W + 20)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        tk.Label(right, text="Preview", bg="#111", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(pady=(6, 2))

        self._preview_canvas = tk.Canvas(
            right, width=CARD_W, height=CARD_H,
            bg="#000", highlightthickness=1,
            highlightbackground="#444",
        )
        self._preview_canvas.pack(pady=8)
        self._renderer = CardRenderer(self._preview_canvas)

    # ── Editor content ────────────────────────────────────────────────────────

    def _build_editor(self) -> None:
        ef   = self._editor_frame
        card = self.current_card

        for w in ef.winfo_children():
            w.destroy()

        # ── Metadata row ──────────────────────────────────────────────────────
        meta = tk.Frame(ef, bg="#1a1a1a")
        meta.pack(fill="x", padx=8, pady=6)

        tk.Label(meta, text="Name:", bg="#1a1a1a", fg="#ccc",
                 font=("Arial", 9)).pack(side="left")
        self._name_var = tk.StringVar(value=card.get("name", ""))
        self._name_var.trace_add("write", self._name_changed)
        tk.Entry(meta, textvariable=self._name_var, width=24,
                 bg="#2a2a2a", fg="white",
                 insertbackground="white",
                 font=("Arial", 9)).pack(side="left", padx=(2, 12))

        tk.Label(meta, text="Element:", bg="#1a1a1a", fg="#ccc",
                 font=("Arial", 9)).pack(side="left")
        self._elem_var = tk.StringVar(value=card.get("element", "Fire"))
        self._elem_var.trace_add("write", self._elem_changed)
        ttk.Combobox(meta, textvariable=self._elem_var,
                     values=ELEMENTS, width=10,
                     state="readonly").pack(side="left", padx=2)

        # ── Block controls ────────────────────────────────────────────────────
        blk_ctrl = tk.Frame(ef, bg="#1a1a1a")
        blk_ctrl.pack(fill="x", padx=8, pady=2)

        tk.Label(blk_ctrl, text="Add Block:", bg="#1a1a1a", fg="#ccc",
                 font=("Arial", 9, "bold")).pack(side="left")
        self._new_block_var = tk.StringVar(value=BLOCK_TYPES[0])
        ttk.Combobox(blk_ctrl, textvariable=self._new_block_var,
                     values=BLOCK_TYPES, width=18,
                     state="readonly").pack(side="left", padx=4)
        tk.Button(blk_ctrl, text="+ Add Block",
                  command=self._add_block,
                  bg="#1a6e3c", fg="white",
                  font=("Arial", 8)).pack(side="left", padx=4)

        count = len(card.get("blocks", []))
        tk.Label(blk_ctrl, text=f"({count}/4 blocks)",
                 bg="#1a1a1a", fg="#888",
                 font=("Arial", 8)).pack(side="left")

        # ── Block editors ─────────────────────────────────────────────────────
        for idx, blk in enumerate(card.get("blocks", [])):
            BlockEditor(
                ef, blk,
                on_change=self._refresh_preview,
                on_delete=lambda i=idx: self._del_block(i),
                bg="#212121",
            ).pack(fill="x", padx=8, pady=4)

    # ── Metadata change handlers ──────────────────────────────────────────────

    def _name_changed(self, *_) -> None:
        self.current_card["name"] = self._name_var.get()
        self._refresh_preview()

    def _elem_changed(self, *_) -> None:
        self.current_card["element"] = self._elem_var.get()
        self._refresh_preview()

    # ── Block mutations ───────────────────────────────────────────────────────

    def _add_block(self) -> None:
        if len(self.current_card.get("blocks", [])) >= 4:
            messagebox.showwarning("Limit", "A card can have at most 4 blocks.")
            return
        btype = self._new_block_var.get()
        self.current_card.setdefault("blocks", []).append(empty_block(btype))
        self._build_editor()
        self._refresh_preview()

    def _del_block(self, idx: int) -> None:
        self.current_card["blocks"].pop(idx)
        self._build_editor()
        self._refresh_preview()

    def _refresh_preview(self, *_) -> None:
        self._renderer.render(self.current_card)

    # ── Card list ─────────────────────────────────────────────────────────────

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
        self._build_editor()
        self._refresh_preview()

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def _new_card(self) -> None:
        self.current_card = empty_card()
        self.current_idx  = None
        self._card_listbox.selection_clear(0, "end")
        self._build_editor()
        self._refresh_preview()

    def _save_card(self) -> None:
        card = self.current_card
        if not card.get("name", "").strip():
            messagebox.showerror("Error", "Card needs a name.")
            return
        if self.current_idx is not None:
            self.cards[self.current_idx] = copy.deepcopy(card)
        else:
            self.cards.append(copy.deepcopy(card))
            self.current_idx = len(self.cards) - 1
        save_cards(self.cards)
        self._refresh_card_list()
        self._show_status("Card saved ✓")

    def _delete_card(self) -> None:
        if self.current_idx is None:
            return
        if not messagebox.askyesno("Delete", "Delete this card?"):
            return
        self.cards.pop(self.current_idx)
        save_cards(self.cards)
        self.current_idx  = None
        self.current_card = empty_card()
        self._refresh_card_list()
        self._build_editor()
        self._refresh_preview()

    # ── Status bar ────────────────────────────────────────────────────────────

    def _show_status(self, msg: str, ms: int = 2000) -> None:
        bar = tk.Label(self.root, text=msg,
                       bg="#1a6e3c", fg="white",
                       font=("Arial", 10, "bold"))
        bar.place(relx=0, rely=1.0, anchor="sw", relwidth=1)
        self.root.after(ms, bar.destroy)
