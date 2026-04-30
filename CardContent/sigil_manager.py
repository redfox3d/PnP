"""
sigil_manager.py – central manager for the sigil registry.

Single source of truth: ``cc_data/box_config.json``. The dialog edits all
sigil properties in one place:

  * core           – rarity, cv_modifier, color, symbol, description
  * card-types     – which card types (and StatusEffect subtypes) accept
                      this sigil, plus per-card-type probability weight
                      and a label override (``Play`` → ``Chant`` on Spells).
  * incompatible   – list of other sigils that must not co-exist on
                      the same card.

Changes are written back to ``box_config.json`` immediately on every
field-blur, so closing the dialog is non-destructive and there is no
"save" button needed.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, colorchooser

from CardContent.sigil_registry import (
    get_sigil_names, load_box_config, save_box_config,
    add_sigil, remove_sigil, update_sigil,
)


# Subtypes per card_type that should appear as separate columns
_SUBTYPES = {
    "StatusEffects": ("Condition", "Curse", "Blessing"),
}


def _get_card_types() -> list:
    try:
        from card_builder.constants import SIGILS_FOR_CARD_TYPE
        return list(SIGILS_FOR_CARD_TYPE.keys())
    except Exception:
        return ["Spells", "Prowess", "Potions", "Phials", "Tinctures",
                "Equipment", "Supplies", "Alchemy",
                "Tokens", "Creatures", "StatusEffects"]


class SigilManagerDialog(tk.Toplevel):

    def __init__(self, parent, on_close=None):
        super().__init__(parent)
        self.title("Sigil Manager")
        self.geometry("980x620")
        self._on_close = on_close
        self._current: str | None = None

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self):
        outer = tk.Frame(self); outer.pack(fill="both", expand=True)

        # ── Left: sigil list + add/remove ────────────────────────────────────
        left = tk.Frame(outer, bg="#1a1a1a")
        left.pack(side="left", fill="y", padx=4, pady=4)
        tk.Label(left, text="Sigils", bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 10, "bold")).pack(pady=(4, 2))

        list_box = tk.Frame(left, bg="#1a1a1a")
        list_box.pack(fill="both", expand=True)
        self._lb = tk.Listbox(list_box, width=22, exportselection=False,
                               bg="#222", fg="#ddd",
                               selectbackground="#2a4a6e",
                               font=("Consolas", 10))
        sb = ttk.Scrollbar(list_box, orient="vertical",
                            command=self._lb.yview)
        self._lb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y"); self._lb.pack(side="left",
                                                         fill="both",
                                                         expand=True)
        self._lb.bind("<<ListboxSelect>>", lambda _e: self._on_select())

        add_row = tk.Frame(left, bg="#1a1a1a")
        add_row.pack(fill="x", pady=4)
        self._new_var = tk.StringVar()
        tk.Entry(add_row, textvariable=self._new_var, width=14
                  ).pack(side="left", padx=2)
        tk.Button(add_row, text="+", width=3, command=self._add,
                  bg="#1a6e3c", fg="white").pack(side="left", padx=2)
        tk.Button(add_row, text="✕", width=3, command=self._remove,
                  bg="#6e1a1a", fg="white").pack(side="left", padx=2)

        # ── Right: tabbed details ────────────────────────────────────────────
        right = tk.Frame(outer); right.pack(side="left", fill="both",
                                              expand=True, padx=4, pady=4)
        self._right = right

        self._header = tk.Label(right, text="(kein Sigil ausgewählt)",
                                 font=("Arial", 12, "bold"),
                                 anchor="w")
        self._header.pack(fill="x", padx=4, pady=4)

        self._nb = ttk.Notebook(right)
        self._nb.pack(fill="both", expand=True)

        self._tab_core    = tk.Frame(self._nb)
        self._tab_types   = tk.Frame(self._nb)
        self._tab_incompat= tk.Frame(self._nb)
        self._nb.add(self._tab_core,     text="Core")
        self._nb.add(self._tab_types,    text="Card Types")
        self._nb.add(self._tab_incompat, text="Incompatible")

        self._build_core_tab(self._tab_core)
        self._build_types_tab(self._tab_types)
        self._build_incompat_tab(self._tab_incompat)

        # Bottom bar
        bot = tk.Frame(self); bot.pack(fill="x", padx=4, pady=4)
        tk.Label(bot,
                 text="Änderungen werden direkt in box_config.json gespeichert.",
                 fg="#888", font=("Arial", 8, "italic")).pack(side="left")
        tk.Button(bot, text="Fertig", command=self._close,
                  bg="#1a3e8e", fg="white",
                  font=("Arial", 10, "bold")).pack(side="right")

        self._refresh_list()

    # ── Tab: Core ────────────────────────────────────────────────────────────

    def _build_core_tab(self, parent):
        f = tk.Frame(parent); f.pack(fill="x", padx=8, pady=8)

        def _row(label):
            r = tk.Frame(f); r.pack(fill="x", pady=2)
            tk.Label(r, text=label, width=14, anchor="w",
                     font=("Arial", 9, "bold")).pack(side="left")
            return r

        self._rarity_var      = tk.StringVar()
        self._cv_mod_var      = tk.StringVar()
        self._color_var       = tk.StringVar()
        self._symbol_var      = tk.StringVar()
        self._desc_var        = tk.StringVar()

        r = _row("Rarity:")
        tk.Entry(r, textvariable=self._rarity_var, width=8
                  ).pack(side="left", padx=4)

        r = _row("CV-Modifier:")
        tk.Entry(r, textvariable=self._cv_mod_var, width=8
                  ).pack(side="left", padx=4)

        r = _row("Farbe (#hex):")
        tk.Entry(r, textvariable=self._color_var, width=10
                  ).pack(side="left", padx=4)
        self._color_swatch = tk.Label(r, text="    ", width=4, relief="ridge")
        self._color_swatch.pack(side="left", padx=4)
        tk.Button(r, text="Wählen…", command=self._pick_color
                  ).pack(side="left")

        r = _row("Symbol:")
        tk.Entry(r, textvariable=self._symbol_var, width=4,
                  font=("Arial", 12)).pack(side="left", padx=4)

        r = _row("Beschreibung:")
        tk.Entry(r, textvariable=self._desc_var, width=48
                  ).pack(side="left", padx=4, fill="x", expand=True)

        # Wire saves on focus-out / Return
        for var, key, conv in [
            (self._rarity_var, "rarity",      lambda v: int(float(v)) if v else None),
            (self._cv_mod_var, "cv_modifier", lambda v: float(v) if v else None),
            (self._color_var,  "color",       lambda v: v or None),
            (self._symbol_var, "symbol",      lambda v: v or None),
            (self._desc_var,   "description", lambda v: v or None),
        ]:
            var.trace_add("write", lambda *_, k=key, vv=var, cv=conv:
                            self._on_core_change(k, vv, cv))

    def _on_core_change(self, key, var, conv):
        if not self._current:
            return
        try:
            val = conv(var.get().strip())
        except (TypeError, ValueError):
            return
        update_sigil(self._current, **{key: val})
        if key == "color":
            self._color_swatch.configure(bg=var.get().strip() or "#222")

    def _pick_color(self):
        if not self._current:
            return
        col = colorchooser.askcolor(initialcolor=self._color_var.get() or "#888",
                                      parent=self)[1]
        if col:
            self._color_var.set(col)

    # ── Tab: Card Types ──────────────────────────────────────────────────────

    def _build_types_tab(self, parent):
        # Scrollable container so the ten-plus card-type rows fit
        canvas = tk.Canvas(parent, highlightthickness=0)
        sb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._types_frame = tk.Frame(canvas)
        win = canvas.create_window((0, 0), window=self._types_frame,
                                     anchor="nw")
        self._types_frame.bind("<Configure>",
                                lambda e: canvas.configure(
                                    scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win, width=e.width))

        # Rows are populated when a sigil is selected (depends on layout
        # being card-type list driven).
        self._type_widgets: dict = {}

    def _refresh_types_tab(self):
        for w in self._types_frame.winfo_children():
            w.destroy()
        self._type_widgets = {}
        if not self._current:
            return

        cfg = load_box_config().get(self._current, {})
        allowed = set(cfg.get("allowed_card_types") or [])
        weights = cfg.get("card_type_weights") or {}
        labels  = cfg.get("card_type_labels")  or {}
        sub_w   = cfg.get("subtype_weights")   or {}

        # Header
        hdr = tk.Frame(self._types_frame, bg="#222")
        hdr.pack(fill="x")
        for txt, w in [("Card Type", 18), ("✓", 4), ("Weight", 10),
                        ("Label", 16)]:
            tk.Label(hdr, text=txt, font=("Arial", 9, "bold"),
                     fg="#aaa", bg="#222", width=w, anchor="w"
                     ).pack(side="left", padx=2)

        for ct in _get_card_types():
            row = tk.Frame(self._types_frame, relief="groove", bd=1)
            row.pack(fill="x", pady=1)

            tk.Label(row, text=ct, width=18, anchor="w",
                     font=("Arial", 9, "bold"), fg="#cce4ff"
                     ).pack(side="left", padx=2)

            # Allowed checkbox
            allow_var = tk.BooleanVar(value=(ct in allowed))
            tk.Checkbutton(row, variable=allow_var,
                            command=lambda c=ct, v=allow_var:
                                self._set_allowed(c, v.get())
                            ).pack(side="left", padx=2)

            # Per-card-type weight
            w_init = str(weights.get(ct, "")) if ct in weights else ""
            w_var = tk.StringVar(value=w_init)
            we = tk.Entry(row, textvariable=w_var, width=8)
            we.pack(side="left", padx=2)
            def _save_w(_e=None, c=ct, vv=w_var):
                self._set_weight(c, vv.get().strip())
            we.bind("<FocusOut>", _save_w)
            we.bind("<Return>",   _save_w)

            # Label override
            lab_init = labels.get(ct, "")
            lab_var = tk.StringVar(value=lab_init)
            le = tk.Entry(row, textvariable=lab_var, width=14)
            le.pack(side="left", padx=2)
            def _save_l(_e=None, c=ct, vv=lab_var):
                self._set_label(c, vv.get().strip())
            le.bind("<FocusOut>", _save_l)
            le.bind("<Return>",   _save_l)

            # Subtype weights (StatusEffects → Condition / Curse / Blessing)
            for st in _SUBTYPES.get(ct, ()):
                tk.Label(row, text=st, fg="#888",
                         font=("Arial", 8, "italic")).pack(side="left",
                                                              padx=(8, 0))
                key = f"{ct}.{st}"
                sw_init = str(sub_w.get(key, ""))
                sw_var = tk.StringVar(value=sw_init)
                sw_e = tk.Entry(row, textvariable=sw_var, width=5)
                sw_e.pack(side="left", padx=2)
                def _save_sw(_e=None, k=key, vv=sw_var):
                    self._set_subtype_weight(k, vv.get().strip())
                sw_e.bind("<FocusOut>", _save_sw)
                sw_e.bind("<Return>",   _save_sw)

    def _set_allowed(self, ct: str, allowed: bool):
        if not self._current:
            return
        cfg = load_box_config()
        entry = cfg.get(self._current)
        if entry is None:
            return
        lst = list(entry.get("allowed_card_types") or [])
        if allowed and ct not in lst:
            lst.append(ct)
        elif not allowed and ct in lst:
            lst.remove(ct)
        entry["allowed_card_types"] = lst
        save_box_config(cfg)

    def _set_weight(self, ct: str, raw: str):
        if not self._current:
            return
        cfg = load_box_config()
        entry = cfg.get(self._current)
        if entry is None:
            return
        ctw = dict(entry.get("card_type_weights") or {})
        if raw == "":
            ctw.pop(ct, None)
        else:
            try:
                ctw[ct] = float(raw)
            except ValueError:
                return
        if ctw:
            entry["card_type_weights"] = ctw
        else:
            entry.pop("card_type_weights", None)
        save_box_config(cfg)

    def _set_label(self, ct: str, label: str):
        if not self._current:
            return
        cfg = load_box_config()
        entry = cfg.get(self._current)
        if entry is None:
            return
        labs = dict(entry.get("card_type_labels") or {})
        if label:
            labs[ct] = label
        else:
            labs.pop(ct, None)
        if labs:
            entry["card_type_labels"] = labs
        else:
            entry.pop("card_type_labels", None)
        save_box_config(cfg)

    def _set_subtype_weight(self, key: str, raw: str):
        if not self._current:
            return
        cfg = load_box_config()
        entry = cfg.get(self._current)
        if entry is None:
            return
        sw = dict(entry.get("subtype_weights") or {})
        if raw == "":
            sw.pop(key, None)
        else:
            try:
                sw[key] = float(raw)
            except ValueError:
                return
        if sw:
            entry["subtype_weights"] = sw
        else:
            entry.pop("subtype_weights", None)
        save_box_config(cfg)

    # ── Tab: Incompatible ────────────────────────────────────────────────────

    def _build_incompat_tab(self, parent):
        tk.Label(parent,
                 text="Diese Sigils dürfen NICHT zusammen mit dem aktuellen "
                      "Sigil auf einer Karte vorkommen.",
                 fg="#888", font=("Arial", 9, "italic"),
                 wraplength=620, justify="left"
                 ).pack(anchor="w", padx=8, pady=(8, 4))

        self._incompat_frame = tk.Frame(parent)
        self._incompat_frame.pack(fill="both", expand=True, padx=8, pady=4)

    def _refresh_incompat_tab(self):
        for w in self._incompat_frame.winfo_children():
            w.destroy()
        if not self._current:
            return
        cfg = load_box_config().get(self._current, {})
        existing = set(cfg.get("incompatible_with") or [])

        all_sigils = [s for s in get_sigil_names() if s != self._current]
        for sig in all_sigils:
            v = tk.BooleanVar(value=(sig in existing))
            cb = tk.Checkbutton(self._incompat_frame, text=sig,
                                  variable=v, anchor="w",
                                  command=lambda s=sig, vv=v:
                                      self._set_incompat(s, vv.get()))
            cb.pack(anchor="w", padx=4, pady=1)

    def _set_incompat(self, other: str, on: bool):
        if not self._current:
            return
        cfg = load_box_config()
        entry = cfg.get(self._current)
        if entry is None:
            return
        lst = list(entry.get("incompatible_with") or [])
        if on and other not in lst:
            lst.append(other)
        elif not on and other in lst:
            lst.remove(other)
        if lst:
            entry["incompatible_with"] = lst
        else:
            entry.pop("incompatible_with", None)
        save_box_config(cfg)
        # Mirror on the other sigil for symmetry
        other_entry = cfg.get(other)
        if other_entry is not None:
            other_lst = list(other_entry.get("incompatible_with") or [])
            if on and self._current not in other_lst:
                other_lst.append(self._current)
            elif not on and self._current in other_lst:
                other_lst.remove(self._current)
            if other_lst:
                other_entry["incompatible_with"] = other_lst
            else:
                other_entry.pop("incompatible_with", None)
            save_box_config(cfg)

    # ── List + selection plumbing ────────────────────────────────────────────

    def _refresh_list(self):
        prev = self._current
        self._lb.delete(0, tk.END)
        for n in get_sigil_names():
            self._lb.insert(tk.END, n)
        # Restore selection if possible
        if prev in get_sigil_names():
            idx = get_sigil_names().index(prev)
            self._lb.selection_set(idx)
            self._lb.see(idx)
            self._populate(prev)
        else:
            self._current = None

    def _on_select(self):
        sel = self._lb.curselection()
        if not sel:
            return
        name = self._lb.get(sel[0])
        self._populate(name)

    def _populate(self, name: str):
        self._current = name
        self._header.config(text=f"  ◆ {name}")
        cfg = load_box_config().get(name, {})

        # Core
        self._rarity_var.set(str(cfg.get("rarity", "")))
        self._cv_mod_var.set(str(cfg.get("cv_modifier", "")))
        self._color_var.set(cfg.get("color", "") or "")
        self._symbol_var.set(cfg.get("symbol", "") or "")
        self._desc_var.set(cfg.get("description", "") or "")
        self._color_swatch.configure(bg=cfg.get("color") or "#222")

        # Other tabs
        self._refresh_types_tab()
        self._refresh_incompat_tab()

    # ── Add / remove ─────────────────────────────────────────────────────────

    def _add(self):
        n = self._new_var.get().strip()
        if not n:
            return
        if not add_sigil(n):
            messagebox.showinfo("Sigil",
                                  f"Sigil '{n}' existiert bereits.",
                                  parent=self)
            return
        self._new_var.set("")
        self._refresh_list()

    def _remove(self):
        if not self._current:
            return
        if not messagebox.askyesno("Sigil entfernen",
                                      f"Sigil '{self._current}' wirklich "
                                      "entfernen?", parent=self):
            return
        remove_sigil(self._current)
        self._current = None
        self._refresh_list()

    def _close(self):
        if self._on_close:
            try: self._on_close()
            except Exception: pass
        self.destroy()
