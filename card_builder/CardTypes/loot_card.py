"""
loot_card.py – Editor and renderer for Loot and Equipment cards.

Loot:
  - Up to 3 elements (colored circles stacked top-left)
  - Per element: optional sacrifice effect shown as  (icon) → text
  - Artwork, Name, Materials (multi-select), Value (centered bottom)
  - Effects selected via checkbox list from global effect IDs

Equipment:
  - element_sources, object_type, materials, effect_text, equip_text,
    equip_cost_text, value  (legacy style, unchanged)
"""

import tkinter as tk
from tkinter import ttk

from card_builder.CardTypes.base_card import BaseCardEditor, TagSelector, ArtworkPicker
from card_builder.dialogs import EffectPickerDialog
from card_builder.constants import (
    CARD_W, CARD_H, ELEMENTS, ELEMENT_COLORS, ELEMENT_ICONS,
    GENERIC_MANA_ICON, GENERIC_MANA_COLOR,
)
from card_builder.materials import merged_materials, save_central_materials, load_central_materials

try:
    from PIL import Image, ImageTk
    _PIL = True
except ImportError:
    _PIL = False

_ELEMENT_OPTIONS = [e for e in ELEMENTS if e != "Generic"]


# ═══════════════════════════════════════════════════════════════════════════════
#  LOOT CARD EDITOR
# ═══════════════════════════════════════════════════════════════════════════════

class LootCardEditor(BaseCardEditor):
    """
    Editor for Loot cards.
    Card dict structure:
        {
            "name":             str,
            "card_type":        "Loot",
            "artwork":          str,
            "elements":         [str, ...],           # up to 3
            "sacrifice_effects": {                     # keyed by element name
                "Fire": {"effect_id": str, "vals": {}, "opt_vals": {}},
                ...
            },
            "materials":        [str, ...],
            "value":            int,
        }
    """

    def _build_type_fields(self):
        card = self.card
        f    = self._f

        # ── Elements ──────────────────────────────────────────────────────────
        self._lbl("Elemente (max 3):").pack(anchor="w", padx=8, pady=(6, 0))
        self._el_frame = tk.Frame(f, bg=self.BG)
        self._el_frame.pack(fill="x", padx=8, pady=2)
        self._rebuild_element_rows()

        add_btn = tk.Button(
            f, text="＋ Element hinzufügen",
            command=self._add_element,
            bg="#1a2a1a", fg="#88ff88",
            font=("Arial", 8), cursor="hand2",
        )
        add_btn.pack(anchor="w", padx=8, pady=2)
        self._add_el_btn = add_btn

        self._sep()

        # ── Neutral effects ──────────────────────────────────────────────────
        self._lbl("Neutrale Effekte:").pack(anchor="w", padx=8)
        tk.Label(f, text="Effekte ohne Element (werden in neutraler Box angezeigt)",
                 bg=self.BG, fg="#555", font=("Arial", 7, "italic")).pack(
            anchor="w", padx=16)

        neutral = card.setdefault("neutral_effects", [])
        self._neutral_frame = tk.Frame(f, bg=self.BG)
        self._neutral_frame.pack(fill="x", padx=8, pady=2)
        self._rebuild_neutral_rows()

        tk.Button(f, text="＋ Neutraler Effekt",
                  command=self._add_neutral_effect,
                  bg="#1a2a2a", fg="#88aaff",
                  font=("Arial", 8), cursor="hand2").pack(
            anchor="w", padx=8, pady=2)

        # Neutral manual text
        self._lbl("Neutraler Freitext:").pack(anchor="w", padx=8, pady=(4, 0))
        self._neutral_text = tk.Text(f, height=3, bg="#2a2a2a", fg="white",
                                     insertbackground="white", font=("Arial", 9),
                                     wrap="word")
        self._neutral_text.insert("1.0", card.get("neutral_text", ""))
        self._neutral_text.bind("<KeyRelease>", self._on_neutral_text_change)
        self._neutral_text.pack(fill="x", padx=8, pady=2)

        self._sep()

        # ── Materials ─────────────────────────────────────────────────────────
        self._lbl("Materialien:").pack(anchor="w", padx=8)
        all_mats = merged_materials()
        self._materials = TagSelector(
            f, values=all_mats,
            selected=list(card.get("materials", [])),
            on_change=self._on_materials_change,
            bg=self.BG,
        )
        self._materials.pack(fill="x", padx=8, pady=2)

        self._sep()

        # ── Value ─────────────────────────────────────────────────────────────
        r = self._row()
        self._lbl("Wert (0-999):", r).pack(side="left")
        self._value_var = tk.StringVar(value=str(card.get("value", 0)))
        self._value_var.trace_add("write", self._on_value_change)
        tk.Spinbox(r, from_=0, to=999, textvariable=self._value_var,
                   width=6, bg="#2a2a2a", fg="white",
                   insertbackground="white",
                   buttonbackground="#2a2a2a").pack(side="left", padx=4)

    # ── Element rows ──────────────────────────────────────────────────────────

    def _rebuild_element_rows(self):
        for w in self._el_frame.winfo_children():
            w.destroy()

        elements = self.card.get("elements", [])
        sac      = self.card.get("sacrifice_effects", {})

        for idx, el in enumerate(elements):
            eff_data = sac.get(el)
            self._build_element_row(idx, el, eff_data)

        # Disable Add button when already at 3
        if hasattr(self, "_add_el_btn"):
            self._add_el_btn.config(
                state="normal" if len(elements) < 3 else "disabled"
            )

    def _build_element_row(self, idx: int, element: str, eff_data: dict):
        """Element block: header row + optional manual text entry."""
        bg = "#1e1e2a"
        outer = tk.Frame(self._el_frame, bg=bg, relief="groove", bd=1)
        outer.pack(fill="x", pady=2)

        # ── Header row: [✕] [icon] [combo] [effect label] [Edit] ─────────────
        row = tk.Frame(outer, bg=bg)
        row.pack(fill="x")

        # Remove element button (FIRST so it's always visible)
        tk.Button(row, text="✕", font=("Arial", 8), cursor="hand2",
                  bg="#3a1a1a", fg="#ff8888", width=2,
                  command=lambda i=idx: self._remove_element(i)
                  ).pack(side="left", padx=(2, 0), pady=2)

        # Element colour swatch
        col  = ELEMENT_COLORS.get(element, GENERIC_MANA_COLOR)
        icon = ELEMENT_ICONS.get(element, "◎")
        tk.Label(row, text=icon, bg=col, fg="white",
                 font=("Arial", 11), width=3).pack(side="left", padx=2, pady=2)

        # Element combobox
        el_var = tk.StringVar(value=element)
        cb = ttk.Combobox(row, textvariable=el_var,
                          values=_ELEMENT_OPTIONS,
                          state="readonly", width=9)
        cb.pack(side="left", padx=4, pady=2)

        def _on_el_change(*_, iv=idx, v=el_var):
            elems = self.card.get("elements", [])
            old_el = elems[iv] if iv < len(elems) else ""
            new_el = v.get()
            sac = self.card.setdefault("sacrifice_effects", {})
            if old_el in sac:
                sac[new_el] = sac.pop(old_el)
            elems[iv] = new_el
            self._rebuild_element_rows()
            self._changed()

        cb.bind("<<ComboboxSelected>>", _on_el_change)

        # Sacrifice effect label (truncated preview)
        eff_text = self._render_effect_short(eff_data)
        eff_lbl  = tk.Label(row, text=eff_text or "—",
                            bg=bg, fg="#88ff88" if eff_text else "#555",
                            font=("Arial", 8), anchor="w")
        eff_lbl.pack(side="left", padx=4, fill="x", expand=True)

        # Edit effect button
        tk.Button(row, text="✎", font=("Arial", 8), cursor="hand2",
                  bg="#2a3a2a", fg="#88ff88",
                  command=lambda el=element, lbl=eff_lbl: self._open_effect_picker(el, lbl)
                  ).pack(side="right", padx=2, pady=2)

        # ── Manual text entry below header ────────────────────────────────────
        manual_text = (eff_data or {}).get("manual_text", "")
        mt_row = tk.Frame(outer, bg=bg)
        mt_row.pack(fill="x", padx=4, pady=(0, 2))
        tk.Label(mt_row, text="Freitext:", bg=bg, fg="#666",
                 font=("Arial", 7)).pack(side="left", padx=2)
        mt_entry = tk.Entry(mt_row, bg="#2a2a2a", fg="#ffcc88",
                            insertbackground="white", font=("Arial", 8))
        mt_entry.insert(0, manual_text)
        mt_entry.pack(side="left", fill="x", expand=True, padx=2)

        def _on_manual_change(*_, el=element, entry=mt_entry):
            sac = self.card.setdefault("sacrifice_effects", {})
            data = sac.setdefault(el, {})
            txt = entry.get().strip()
            if txt:
                data["manual_text"] = txt
            else:
                data.pop("manual_text", None)
            self._changed()

        mt_entry.bind("<KeyRelease>", _on_manual_change)

    def _render_effect_short(self, eff_data: dict) -> str:
        """Return a short display string for the effect, or ''."""
        if not eff_data or not eff_data.get("effect_id"):
            return ""
        eid = eff_data["effect_id"]
        try:
            from card_builder.data import get_content_data
            cd = get_content_data()
            item = cd.get("effect", eid)
            if item:
                from card_builder.CardTypes.base_card import _render_content
                text = _render_content(item, {
                    "var_values": eff_data.get("vals", {}),
                    "opt_values": eff_data.get("opt_vals", {}),
                })
                return text[:32] + ("…" if len(text) > 32 else "")
        except Exception:
            pass
        return eid

    # ── Effect picker dialog ──────────────────────────────────────────────────

    def _open_effect_picker(self, element: str, lbl_widget: tk.Label):
        """
        Dialog showing all effect IDs with checkboxes (radio behaviour).
        Below the list: variable value inputs for the selected effect.
        """
        try:
            from card_builder.data import get_content_data
            cd   = get_content_data()
            effs = cd.effects
        except Exception:
            effs = []

        if not effs:
            return

        top = tk.Toplevel(self.winfo_toplevel())
        top.title(f"Opfer-Effekt für {element}")
        top.configure(bg="#1a1a1a")
        top.grab_set()
        top.resizable(True, True)

        # Current selection
        sac      = self.card.get("sacrifice_effects", {})
        cur_data = dict(sac.get(element) or {})
        cur_id   = cur_data.get("effect_id", "")

        # ── Search bar ────────────────────────────────────────────────────────
        search_var = tk.StringVar()
        sf = tk.Frame(top, bg="#1a1a1a")
        sf.pack(fill="x", padx=8, pady=(8, 2))
        tk.Label(sf, text="🔍", bg="#1a1a1a", fg="#aaa").pack(side="left")
        tk.Entry(sf, textvariable=search_var, bg="#2a2a2a", fg="white",
                 insertbackground="white", font=("Arial", 9), width=28).pack(
            side="left", padx=4, fill="x", expand=True)

        # ── Effect list (scrollable) ──────────────────────────────────────────
        list_outer = tk.Frame(top, bg="#1a1a1a")
        list_outer.pack(fill="both", expand=True, padx=8, pady=4)

        vsb = tk.Scrollbar(list_outer, orient="vertical")
        vsb.pack(side="right", fill="y")
        canvas = tk.Canvas(list_outer, bg="#1a1a1a",
                           yscrollcommand=vsb.set, highlightthickness=0,
                           width=420, height=320)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.config(command=canvas.yview)

        inner = tk.Frame(canvas, bg="#1a1a1a")
        inner_win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(inner_win, width=e.width))
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        # Radio variable (holds selected effect_id, or "" for none)
        sel_var = tk.StringVar(value=cur_id)

        # ── Variable inputs panel (shown below list when effect selected) ──────
        var_frame = tk.LabelFrame(top, text="Variablen", bg="#1a1a1a",
                                  fg="#88aaff", font=("Arial", 8))
        var_frame.pack(fill="x", padx=8, pady=4)
        var_vals: dict = dict(cur_data.get("vals", {}))
        var_widgets: dict = {}  # var_name → StringVar

        def _rebuild_var_inputs():
            for w in var_frame.winfo_children():
                w.destroy()
            var_widgets.clear()
            eid = sel_var.get()
            if not eid:
                return
            try:
                item = cd.get("effect", eid)
            except Exception:
                item = None
            if not item:
                return
            variables = item.get("variables", {})
            if not variables:
                tk.Label(var_frame, text="(keine Variablen)",
                         bg="#1a1a1a", fg="#555", font=("Arial", 8)).pack(
                    anchor="w", padx=6)
                return
            for vname in variables:
                r = tk.Frame(var_frame, bg="#1a1a1a")
                r.pack(fill="x", padx=6, pady=1)
                tk.Label(r, text=f"{{{vname}}}:",
                         bg="#1a1a1a", fg="#88aaff",
                         font=("Arial", 8, "bold"), width=10).pack(side="left")
                vv = tk.StringVar(value=str(var_vals.get(vname, "")))
                var_widgets[vname] = vv
                tk.Entry(r, textvariable=vv, width=8,
                         bg="#2a2a2a", fg="white",
                         insertbackground="white",
                         font=("Arial", 8)).pack(side="left", padx=4)

        def _on_select(eid):
            sel_var.set(eid)
            _rebuild_row_highlights()
            _rebuild_var_inputs()

        effect_rows: dict = {}  # eid → frame

        def _rebuild_row_highlights():
            cur = sel_var.get()
            for eid, fr in effect_rows.items():
                fr.config(bg="#1a4a1a" if eid == cur else "#1e1e1e")

        def _populate_list(filter_text=""):
            for w in inner.winfo_children():
                w.destroy()
            effect_rows.clear()
            ft = filter_text.lower()
            for item in effs:
                eid = item.get("id", "")
                if ft and ft not in eid.lower():
                    continue
                # Short preview of content_text
                ct = item.get("content_text") or item.get("effect_text", "")
                is_sel = (eid == sel_var.get())
                bg = "#1a4a1a" if is_sel else "#1e1e1e"

                fr = tk.Frame(inner, bg=bg, cursor="hand2")
                fr.pack(fill="x", pady=1, padx=2)
                effect_rows[eid] = fr

                # Checkbox (radio behaviour)
                chk_var = tk.BooleanVar(value=is_sel)
                chk = tk.Checkbutton(fr, variable=chk_var,
                                     bg=bg, activebackground=bg,
                                     selectcolor="#1a4a1a",
                                     command=lambda e=eid, cv=chk_var: (
                                         _on_select(e) if cv.get() else _on_select("")
                                     ))
                chk.pack(side="left", padx=4)

                tk.Label(fr, text=eid, bg=bg, fg="#88ff88",
                         font=("Consolas", 9, "bold"), width=22,
                         anchor="w").pack(side="left")
                tk.Label(fr, text=ct[:40] if ct else "—",
                         bg=bg, fg="#aaa",
                         font=("Arial", 8), anchor="w").pack(side="left", padx=4)

                fr.bind("<Button-1>", lambda _, e=eid: _on_select(e))

        _populate_list()
        _rebuild_var_inputs()

        search_var.trace_add("write",
                             lambda *_: _populate_list(search_var.get()))

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = tk.Frame(top, bg="#1a1a1a")
        btn_row.pack(fill="x", padx=8, pady=(2, 8))

        def _ok():
            eid = sel_var.get()
            sac = self.card.setdefault("sacrifice_effects", {})
            if eid:
                vals = {k: v.get() for k, v in var_widgets.items()}
                sac[element] = {"effect_id": eid, "vals": vals, "opt_vals": {}}
            else:
                sac.pop(element, None)
            lbl_widget.config(
                text=self._render_effect_short(sac.get(element)) or "— kein Opfer-Effekt",
                fg="#88ff88" if sac.get(element) else "#555",
            )
            self._changed()
            top.destroy()

        def _clear():
            sel_var.set("")
            _rebuild_row_highlights()
            _rebuild_var_inputs()

        def _cancel():
            top.destroy()

        tk.Button(btn_row, text="✓ OK", command=_ok,
                  bg="#1a4a1a", fg="#88ff88",
                  font=("Arial", 9, "bold"), cursor="hand2",
                  width=10).pack(side="left", padx=4)
        tk.Button(btn_row, text="✕ Löschen", command=_clear,
                  bg="#3a1a1a", fg="#ff8888",
                  font=("Arial", 9), cursor="hand2",
                  width=10).pack(side="left", padx=4)
        tk.Button(btn_row, text="Abbrechen", command=_cancel,
                  bg="#2a2a2a", fg="#aaa",
                  font=("Arial", 9), cursor="hand2",
                  width=10).pack(side="left", padx=4)

        top.bind("<Return>", lambda _: _ok())
        top.bind("<Escape>", lambda _: _cancel())

    # ── Neutral effects ──────────────────────────────────────────────────────

    def _rebuild_neutral_rows(self):
        for w in self._neutral_frame.winfo_children():
            w.destroy()
        neutrals = self.card.get("neutral_effects", [])
        for idx, neff in enumerate(neutrals):
            self._build_neutral_row(idx, neff)

    def _build_neutral_row(self, idx: int, neff: dict):
        bg = "#1e2a2a"
        row = tk.Frame(self._neutral_frame, bg=bg, relief="groove", bd=1)
        row.pack(fill="x", pady=1)

        tk.Button(row, text="✕", font=("Arial", 8), cursor="hand2",
                  bg="#3a1a1a", fg="#ff8888", width=2,
                  command=lambda i=idx: self._remove_neutral_effect(i)
                  ).pack(side="left", padx=2, pady=2)

        eid = neff.get("effect_id", "")
        label_text = self._render_effect_short(neff) if eid else "—"
        lbl = tk.Label(row, text=label_text, bg=bg,
                       fg="#88aaff" if eid else "#555",
                       font=("Arial", 8), anchor="w")
        lbl.pack(side="left", padx=4, fill="x", expand=True)

        tk.Button(row, text="✎", font=("Arial", 8), cursor="hand2",
                  bg="#2a2a3a", fg="#88aaff",
                  command=lambda i=idx, l=lbl: self._open_neutral_picker(i, l)
                  ).pack(side="right", padx=2, pady=2)

    def _add_neutral_effect(self):
        neutrals = self.card.setdefault("neutral_effects", [])
        neutrals.append({})
        self._rebuild_neutral_rows()
        self._changed()

    def _remove_neutral_effect(self, idx: int):
        neutrals = self.card.get("neutral_effects", [])
        if 0 <= idx < len(neutrals):
            neutrals.pop(idx)
        self._rebuild_neutral_rows()
        self._changed()

    def _open_neutral_picker(self, idx: int, lbl_widget: tk.Label):
        """Effect picker for neutral effects — reuses sacrifice picker logic."""
        try:
            from card_builder.data import get_content_data
            cd   = get_content_data()
            effs = cd.effects
        except Exception:
            effs = []
        if not effs:
            return

        neutrals = self.card.setdefault("neutral_effects", [])
        cur_data = dict(neutrals[idx]) if idx < len(neutrals) else {}
        cur_id   = cur_data.get("effect_id", "")

        top = tk.Toplevel(self.winfo_toplevel())
        top.title(f"Neutraler Effekt #{idx+1}")
        top.configure(bg="#1a1a1a")
        top.grab_set()
        top.resizable(True, True)

        sel_var = tk.StringVar(value=cur_id)
        search_var = tk.StringVar()

        sf = tk.Frame(top, bg="#1a1a1a")
        sf.pack(fill="x", padx=8, pady=(8, 2))
        tk.Label(sf, text="🔍", bg="#1a1a1a", fg="#aaa").pack(side="left")
        tk.Entry(sf, textvariable=search_var, bg="#2a2a2a", fg="white",
                 insertbackground="white", font=("Arial", 9), width=28).pack(
            side="left", padx=4, fill="x", expand=True)

        list_outer = tk.Frame(top, bg="#1a1a1a")
        list_outer.pack(fill="both", expand=True, padx=8, pady=4)
        vsb = tk.Scrollbar(list_outer, orient="vertical")
        vsb.pack(side="right", fill="y")
        canvas = tk.Canvas(list_outer, bg="#1a1a1a",
                           yscrollcommand=vsb.set, highlightthickness=0,
                           width=420, height=280)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.config(command=canvas.yview)
        inner = tk.Frame(canvas, bg="#1a1a1a")
        inner_win = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(inner_win, width=e.width))
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        var_frame = tk.LabelFrame(top, text="Variablen", bg="#1a1a1a",
                                  fg="#88aaff", font=("Arial", 8))
        var_frame.pack(fill="x", padx=8, pady=4)
        var_vals = dict(cur_data.get("vals", {}))
        var_widgets = {}
        effect_rows = {}

        def _rebuild_var_inputs():
            for w in var_frame.winfo_children():
                w.destroy()
            var_widgets.clear()
            eid = sel_var.get()
            if not eid:
                return
            try:
                item = cd.get("effect", eid)
            except Exception:
                item = None
            if not item:
                return
            variables = item.get("variables", {})
            if not variables:
                return
            for vname in variables:
                r = tk.Frame(var_frame, bg="#1a1a1a")
                r.pack(fill="x", padx=6, pady=1)
                tk.Label(r, text=f"{{{vname}}}:", bg="#1a1a1a", fg="#88aaff",
                         font=("Arial", 8, "bold"), width=10).pack(side="left")
                vv = tk.StringVar(value=str(var_vals.get(vname, "")))
                var_widgets[vname] = vv
                tk.Entry(r, textvariable=vv, width=8, bg="#2a2a2a", fg="white",
                         insertbackground="white",
                         font=("Arial", 8)).pack(side="left", padx=4)

        def _on_select(eid):
            sel_var.set(eid)
            for eid2, fr in effect_rows.items():
                fr.config(bg="#1a4a1a" if eid2 == eid else "#1e1e1e")
            _rebuild_var_inputs()

        def _populate(ft=""):
            for w in inner.winfo_children():
                w.destroy()
            effect_rows.clear()
            ft = ft.lower()
            for item in effs:
                eid = item.get("id", "")
                if ft and ft not in eid.lower():
                    continue
                ct = item.get("content_text") or item.get("effect_text", "")
                is_sel = (eid == sel_var.get())
                bg = "#1a4a1a" if is_sel else "#1e1e1e"
                fr = tk.Frame(inner, bg=bg, cursor="hand2")
                fr.pack(fill="x", pady=1, padx=2)
                effect_rows[eid] = fr
                chk_var = tk.BooleanVar(value=is_sel)
                tk.Checkbutton(fr, variable=chk_var, bg=bg, activebackground=bg,
                               selectcolor="#1a4a1a",
                               command=lambda e=eid, cv=chk_var: (
                                   _on_select(e) if cv.get() else _on_select("")
                               )).pack(side="left", padx=4)
                tk.Label(fr, text=eid, bg=bg, fg="#88aaff",
                         font=("Consolas", 9, "bold"), width=22,
                         anchor="w").pack(side="left")
                tk.Label(fr, text=ct[:40] if ct else "—", bg=bg, fg="#aaa",
                         font=("Arial", 8), anchor="w").pack(side="left", padx=4)
                fr.bind("<Button-1>", lambda _, e=eid: _on_select(e))

        _populate()
        _rebuild_var_inputs()
        search_var.trace_add("write", lambda *_: _populate(search_var.get()))

        btn_row = tk.Frame(top, bg="#1a1a1a")
        btn_row.pack(fill="x", padx=8, pady=(2, 8))

        def _ok():
            eid = sel_var.get()
            if eid:
                vals = {k: v.get() for k, v in var_widgets.items()}
                neutrals[idx] = {"effect_id": eid, "vals": vals, "opt_vals": {}}
            else:
                neutrals[idx] = {}
            lbl_widget.config(
                text=self._render_effect_short(neutrals[idx]) or "—",
                fg="#88aaff" if neutrals[idx].get("effect_id") else "#555",
            )
            self._changed()
            top.destroy()

        tk.Button(btn_row, text="✓ OK", command=_ok,
                  bg="#1a4a1a", fg="#88ff88",
                  font=("Arial", 9, "bold"), cursor="hand2",
                  width=10).pack(side="left", padx=4)
        tk.Button(btn_row, text="✕ Löschen",
                  command=lambda: (sel_var.set(""), _on_select("")),
                  bg="#3a1a1a", fg="#ff8888",
                  font=("Arial", 9), cursor="hand2",
                  width=10).pack(side="left", padx=4)
        tk.Button(btn_row, text="Abbrechen", command=top.destroy,
                  bg="#2a2a2a", fg="#aaa",
                  font=("Arial", 9), cursor="hand2",
                  width=10).pack(side="left", padx=4)
        top.bind("<Return>", lambda _: _ok())
        top.bind("<Escape>", lambda _: top.destroy())

    def _on_neutral_text_change(self, *_):
        self.card["neutral_text"] = self._neutral_text.get("1.0", "end-1c")
        self._changed()

    # ── CRUD helpers ──────────────────────────────────────────────────────────

    def _add_element(self):
        elems = self.card.setdefault("elements", [])
        if len(elems) >= 3:
            return
        # Pick first unused element
        used = set(elems)
        for el in _ELEMENT_OPTIONS:
            if el not in used:
                elems.append(el)
                break
        else:
            elems.append(_ELEMENT_OPTIONS[0])
        self._rebuild_element_rows()
        self._changed()

    def _remove_element(self, idx: int):
        elems = self.card.get("elements", [])
        if 0 <= idx < len(elems):
            el = elems.pop(idx)
            self.card.get("sacrifice_effects", {}).pop(el, None)
        self._rebuild_element_rows()
        self._changed()

    def _on_materials_change(self):
        mats = self._materials.get()
        self.card["materials"] = mats
        # Save new materials to central list
        existing = load_central_materials()
        save_central_materials(existing + mats)
        self._changed()

    def _on_value_change(self, *_):
        try:
            self.card["value"] = max(0, min(999, int(self._value_var.get())))
        except (ValueError, AttributeError):
            pass
        self._changed()

    def _changed(self, *_):
        if self.on_change:
            self.on_change()


# ═══════════════════════════════════════════════════════════════════════════════
#  EQUIPMENT CARD EDITOR  (legacy, unchanged)
# ═══════════════════════════════════════════════════════════════════════════════

class EquipmentCardEditor(BaseCardEditor):

    def _build_type_fields(self):
        ef   = self._f
        card = self.card

        EL_SOURCE_VALUES = ELEMENTS
        r = self._row()
        self._lbl("Element-Quellen (max 3):", r).pack(side="left")
        self._el_src = TagSelector(
            self._f, values=EL_SOURCE_VALUES,
            selected=card.get("element_sources", []),
            on_change=self._changed, max_items=3, bg=self.BG)
        self._el_src.pack(fill="x", padx=8, pady=2)

        r = self._row()
        self._lbl("Objekt-Typ:", r).pack(side="left")
        known = ["Schwert", "Dolch", "Bogen", "Schild", "Rüstung",
                 "Münze", "Ring", "Stab", "Trank", "Buch", "Werkzeug"]
        self._obj_type = TagSelector(
            self._f, values=known,
            selected=card.get("object_type", []),
            on_change=self._changed, bg=self.BG)
        self._obj_type.pack(fill="x", padx=8, pady=2)

        r = self._row()
        self._lbl("Materialien:", r).pack(side="left")
        all_mats = merged_materials()
        self._materials = TagSelector(
            self._f, values=all_mats,
            selected=card.get("materials", []),
            on_change=self._changed, bg=self.BG)
        self._materials.pack(fill="x", padx=8, pady=2)

        self._sep()

        self._lbl("Effekt-Text:").pack(anchor="w", padx=8)
        self._effect_text = tk.Text(ef, height=4, bg="#2a2a2a", fg="white",
                                    insertbackground="white", font=("Arial", 9),
                                    wrap="word")
        self._effect_text.insert("1.0", card.get("effect_text", ""))
        self._effect_text.bind("<KeyRelease>", self._changed)
        self._effect_text.pack(fill="x", padx=8, pady=2)

        self._sep()
        self._lbl("Equip Box:").pack(anchor="w", padx=8)
        self._equip_text = tk.Text(ef, height=3, bg="#2a2a2a", fg="white",
                                   insertbackground="white", font=("Arial", 9),
                                   wrap="word")
        self._equip_text.insert("1.0", card.get("equip_text", ""))
        self._equip_text.bind("<KeyRelease>", self._changed)
        self._equip_text.pack(fill="x", padx=8, pady=2)

        self._lbl("Equip Cost:").pack(anchor="w", padx=8)
        self._equip_cost = tk.Text(ef, height=2, bg="#2a2a2a", fg="white",
                                   insertbackground="white", font=("Arial", 9),
                                   wrap="word")
        self._equip_cost.insert("1.0", card.get("equip_cost_text", ""))
        self._equip_cost.bind("<KeyRelease>", self._changed)
        self._equip_cost.pack(fill="x", padx=8, pady=2)

        self._sep()

        r = self._row()
        self._lbl("Wert (0-999):", r).pack(side="left")
        self._value_var = tk.StringVar(value=str(card.get("value", 0)))
        self._value_var.trace_add("write", self._changed)
        tk.Spinbox(r, from_=0, to=999, textvariable=self._value_var,
                   width=6, bg="#2a2a2a", fg="white",
                   insertbackground="white",
                   buttonbackground="#2a2a2a").pack(side="left", padx=4)

    def _changed(self, *_):
        card = self.card
        if hasattr(self, "_el_src"):
            card["element_sources"] = self._el_src.get()
        if hasattr(self, "_obj_type"):
            card["object_type"] = self._obj_type.get()
        if hasattr(self, "_materials"):
            card["materials"] = self._materials.get()
            save_central_materials(load_central_materials() + card["materials"])
        if hasattr(self, "_effect_text"):
            card["effect_text"] = self._effect_text.get("1.0", "end-1c")
        if hasattr(self, "_equip_text"):
            card["equip_text"] = self._equip_text.get("1.0", "end-1c")
        if hasattr(self, "_equip_cost"):
            card["equip_cost_text"] = self._equip_cost.get("1.0", "end-1c")
        try:
            card["value"] = max(0, min(999, int(self._value_var.get())))
        except (ValueError, AttributeError):
            pass
        if self.on_change:
            self.on_change()


# ═══════════════════════════════════════════════════════════════════════════════
#  LOOT CARD RENDERER
# ═══════════════════════════════════════════════════════════════════════════════

class LootCardRenderer:
    FF     = "Palatino Linotype"
    FF_ALT = "Arial"
    PAD    = 10

    def __init__(self, canvas: tk.Canvas):
        self.canvas = canvas
        self.W      = CARD_W
        self.H      = CARD_H
        self._img   = [None]

    def render(self, card: dict):
        c  = self.canvas
        ct = card.get("card_type", "Loot")
        c.delete("all")

        if ct == "Equipment":
            self._render_equipment(card)
        else:
            self._render_loot(card)

    # ── Loot renderer ─────────────────────────────────────────────────────────

    def _render_loot(self, card: dict):
        c  = self.canvas
        P  = self.PAD
        W, H = self.W, self.H

        # Background
        c.create_rectangle(0, 0, W, H, fill="#12121e", outline="")
        c.create_rectangle(2, 2, W-2, H-2, outline="#666", width=2)

        elements = card.get("elements", [])
        sac      = card.get("sacrifice_effects", {})

        # ── Name (top) ────────────────────────────────────────────────────────
        name_x = P + 4
        c.create_text(name_x, P + 4, text=card.get("name", ""),
                      anchor="nw",
                      font=(self.FF, 14, "bold"), fill="white")

        # ── Element circles (horizontal row below name, ABOVE artwork) ────────
        el_r   = 14
        el_gap = el_r * 2 + 6
        el_y   = P + 30   # below name
        el_x   = P + el_r + 2
        for el in elements[:3]:
            col  = ELEMENT_COLORS.get(el, GENERIC_MANA_COLOR)
            icon = ELEMENT_ICONS.get(el, "◎")
            c.create_oval(el_x-el_r, el_y-el_r, el_x+el_r, el_y+el_r,
                          fill=col, outline="gold", width=1)
            c.create_text(el_x, el_y, text=icon,
                          font=("Arial", 11), anchor="center")
            el_x += el_gap

        # ── Artwork ───────────────────────────────────────────────────────────
        art_y0 = el_y + el_r + 6 if elements else P + 30
        art_y1 = H - 160
        self._draw_artwork(card, P, art_y0, W - P, art_y1)

        # ── Materials (pill tags below artwork) ───────────────────────────────
        y     = art_y1 + 6
        mats  = card.get("materials", [])
        tx    = P
        if mats:
            for mat in mats:
                tw = len(mat) * 7 + 10
                if tx + tw > W - P:
                    tx = P; y += 22
                c.create_rectangle(tx, y, tx+tw, y+18,
                                   fill="#1a1a2a", outline="#6688aa")
                c.create_text(tx + tw // 2, y + 9, text=mat,
                              fill="#aaccff", font=("Arial", 8))
                tx += tw + 4
            y += 24
        else:
            y += 4

        # ── Sacrifice effects ─────────────────────────────────────────────────
        # Include elements that have either an effect_id or manual_text
        active_elements = [
            el for el in elements[:3]
            if sac.get(el) and (sac[el].get("effect_id") or sac[el].get("manual_text"))
        ]

        sac_y0 = y
        badge_y = H - 36 - 8
        r2 = 9
        line_h = r2 * 2 + 8

        for el in active_elements:
            eff_data = sac[el]
            col  = ELEMENT_COLORS.get(el, GENERIC_MANA_COLOR)
            icon = ELEMENT_ICONS.get(el, "◎")

            if y + line_h > badge_y:
                break

            # Circle icon
            c.create_oval(P, y+1, P + r2*2, y+1 + r2*2,
                          fill=col, outline="gold", width=1)
            c.create_text(P + r2, y + 1 + r2, text=icon,
                          font=("Arial", 9), anchor="center")

            # Arrow
            c.create_text(P + r2*2 + 6, y + r2, text="→",
                          fill="#888", font=("Arial", 10), anchor="w")

            # Effect text — manual_text takes priority over effect_id
            manual = eff_data.get("manual_text", "")
            if manual:
                eff_text = manual
            else:
                eff_text = self._render_eff_text(eff_data)
            text_x   = P + r2*2 + 22
            max_w    = W - text_x - P
            c.create_text(text_x, y + r2,
                          text=eff_text, anchor="w",
                          font=(self.FF_ALT, 9), fill="white",
                          width=max_w)
            y += line_h

            # Reminder text (only for non-manual effects)
            if not manual:
                rt = self._render_eff_reminder(eff_data)
                if rt and y + 14 <= badge_y:
                    c.create_text(text_x, y,
                                  text=f"({rt})", anchor="nw",
                                  font=(self.FF_ALT, 8, "italic"), fill="#888899",
                                  width=max_w)
                    y += 14

        # ── Neutral effects ───────────────────────────────────────────────────
        neutral_effs = card.get("neutral_effects", [])
        neutral_text = card.get("neutral_text", "").strip()
        has_neutral  = any(ne.get("effect_id") for ne in neutral_effs) or neutral_text

        if has_neutral and y + line_h <= badge_y:
            # Separator
            if y > sac_y0:
                c.create_line(P, y + 2, W - P, y + 2, fill="#333", width=1)
                y += 6

            # Neutral effects from effect picker
            for neff in neutral_effs:
                if not neff.get("effect_id"):
                    continue
                if y + line_h > badge_y:
                    break
                text_x = P + 6
                max_w  = W - text_x - P
                eff_text = self._render_eff_text(neff)
                c.create_text(text_x, y + r2,
                              text=f"◆ {eff_text}", anchor="w",
                              font=(self.FF_ALT, 9), fill="#cccccc",
                              width=max_w)
                y += line_h

            # Neutral free text
            if neutral_text and y + 14 <= badge_y:
                text_x = P + 6
                max_w  = W - text_x - P
                for line in self._wrap(neutral_text, max_w):
                    if y + 14 > badge_y:
                        break
                    c.create_text(text_x, y,
                                  text=line, anchor="nw",
                                  font=(self.FF_ALT, 9), fill="#cccccc",
                                  width=max_w)
                    y += 16

        # Separator line above value if there were effects
        if y > sac_y0:
            c.create_line(P, y + 2, W - P, y + 2, fill="#333", width=1)
            y += 6

        # ── Value badge (centered at bottom) ──────────────────────────────────
        val     = card.get("value", 0)
        badge_w = 80
        badge_h = 28
        bx      = (W - badge_w) // 2
        by      = H - badge_h - 8
        c.create_rectangle(bx, by, bx + badge_w, by + badge_h,
                           fill="#1a1500", outline="gold", width=2)
        c.create_text(bx + badge_w // 2, by + badge_h // 2,
                      text=f"✦ {val}",
                      fill="gold", font=(self.FF, 13, "bold"))

    def _draw_artwork(self, card, x0, y0, x1, y1):
        import os
        c = self.canvas
        c.create_rectangle(x0, y0, x1, y1, fill="#0d0d18", outline="#333")

        path = card.get("artwork", "")
        if path and _PIL and os.path.exists(path):
            try:
                img    = Image.open(path)
                w, h   = x1 - x0, y1 - y0
                iw, ih = img.size
                s      = max(w / iw, h / ih)
                nw, nh = int(iw * s), int(ih * s)
                img    = img.resize((nw, nh), Image.LANCZOS)
                lf, tp = (nw - w) // 2, (nh - h) // 2
                img    = img.crop((lf, tp, lf + w, tp + h))
                self._img[0] = ImageTk.PhotoImage(img)
                c.create_image(x0, y0, image=self._img[0], anchor="nw")
            except Exception:
                c.create_text((x0+x1)//2, (y0+y1)//2, text="Artwork",
                              fill="#444", font=(self.FF, 11))
        else:
            c.create_text((x0+x1)//2, (y0+y1)//2, text="Artwork",
                          fill="#333", font=(self.FF, 11))

    def _render_eff_text(self, eff_data: dict) -> str:
        eid = eff_data.get("effect_id", "")
        try:
            from card_builder.data import get_content_data
            from card_builder.CardTypes.base_card import _render_content
            cd   = get_content_data()
            item = cd.get("effect", eid)
            if item:
                return _render_content(item, {
                    "var_values": eff_data.get("vals", {}),
                    "opt_values": eff_data.get("opt_vals", {}),
                })
        except Exception:
            pass
        return eid

    def _render_eff_reminder(self, eff_data: dict) -> str:
        """Return reminder text with variable substitution, or ''."""
        eid = eff_data.get("effect_id", "")
        try:
            from card_builder.data import get_content_data
            cd   = get_content_data()
            item = cd.get("effect", eid)
            if item:
                rt = item.get("reminder_text", "")
                if rt:
                    vals = eff_data.get("vals", {})
                    for k, v in vals.items():
                        rt = rt.replace(f"{{{k}}}", str(v))
                    return rt
        except Exception:
            pass
        return ""

    # ── Equipment renderer (legacy) ───────────────────────────────────────────

    def _render_equipment(self, card: dict):
        c  = self.canvas
        P  = self.PAD
        W, H = self.W, self.H

        c.create_rectangle(0, 0, W, H, fill="#1a1a2a", outline="")
        c.create_rectangle(2, 2, W-2, H-2, outline="#888", width=2)

        c.create_text(P, P, text=card.get("name", ""), anchor="nw",
                      font=(self.FF, 16, "bold"), fill="white")

        AY0, AY1 = 36, 240
        self._draw_artwork(card, P, AY0, W-P, AY1)

        # Mana icons inside artwork
        srcs = card.get("element_sources", [])
        r    = 10
        ix   = P + r + 3
        iy   = AY0 + r + 4
        for el in srcs[:3]:
            col  = ELEMENT_COLORS.get(el, GENERIC_MANA_COLOR)
            icon = ELEMENT_ICONS.get(el, GENERIC_MANA_ICON)
            c.create_oval(ix-r, iy-r, ix+r, iy+r,
                          fill=col, outline="gold", width=1)
            c.create_text(ix, iy, text=icon, font=("Arial", 10))
            iy += r * 2 + 4

        y    = AY1 + 6
        tags = card.get("object_type", []) + card.get("materials", [])
        tx   = P
        for tag in tags:
            tw = len(tag) * 7 + 10
            if tx + tw > W - P:
                tx = P; y += 22
            c.create_rectangle(tx, y, tx+tw, y+18,
                               fill="#2a3a2a", outline="#aaffaa")
            c.create_text(tx+tw//2, y+9, text=tag, fill="#aaffaa",
                          font=("Arial", 9))
            tx += tw + 4
        y += 26

        BOX_BOTTOM = H - 40
        MID = W // 2

        equip_cost_h  = 36
        equip_box_bot = BOX_BOTTOM - equip_cost_h - 2

        self._text_box(P, y, MID-2, BOX_BOTTOM,
                       card.get("effect_text", ""),
                       fill="#111", outline="#555",
                       color="white", header="Effekt")

        self._text_box(MID+2, y, W-P, equip_box_bot,
                       card.get("equip_text", ""),
                       fill="#1a1100", outline="#997700",
                       color="#ffdd88", header="Equip")

        c.create_rectangle(MID+2, equip_box_bot+2, W-P, BOX_BOTTOM,
                           fill="#0d0a00", outline="#997700")
        c.create_text(MID+6, equip_box_bot+4, text="Cost:", anchor="nw",
                      fill="#997700", font=(self.FF, 8, "bold"))
        ec = card.get("equip_cost_text", "")
        if ec:
            c.create_text(MID+46, (equip_box_bot+2+BOX_BOTTOM)//2, text=ec,
                          anchor="w", fill="#ffdd88",
                          font=(self.FF, 11))

        val = card.get("value", 0)
        c.create_rectangle(W-64, H-36, W-P, H-P,
                           fill="#2a2200", outline="gold", width=2)
        c.create_text(W-34, H-18, text=f"✦ {val}",
                      fill="gold", font=(self.FF, 12, "bold"))

    def _text_box(self, x0, y0, x1, y1, text, fill, outline,
                  color="white", header=None):
        c  = self.canvas
        P  = 4
        c.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline)
        ty = y0 + P
        if header:
            c.create_text(x0+P, ty, text=header, anchor="nw",
                          fill="#888", font=(self.FF, 9, "bold"))
            ty += 16
        if not text:
            return
        font   = (self.FF, 11)
        line_h = 16
        max_w  = x1 - x0 - P * 2
        lines  = self._wrap(text, max_w)
        total  = len(lines) * line_h
        avail  = y1 - ty - P
        sy     = ty + max(0, (avail - total) // 2)
        for line in lines:
            if sy + line_h > y1 - P:
                break
            c.create_text(x0+P, sy, text=line, anchor="nw",
                          font=font, fill=color)
            sy += line_h

    def _wrap(self, text: str, max_w: int) -> list:
        words, lines, line = text.split(), [], ""
        for word in words:
            test = (line + " " + word).strip()
            if len(test) * 11 * 0.55 > max_w and line:
                lines.append(line)
                line = word
            else:
                line = test
        if line:
            lines.append(line)
        return lines


# Legacy alias so old imports don't break
SuppliesCardEditor = EquipmentCardEditor
