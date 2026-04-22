"""
random_builder/app.py – Random Card Builder panel.

Layout (3 columns):
  ┌─────────────────┬──────────────────────────┬────────────────────────────┐
  │  EINSTELLUNGEN  │  GENERIERTE KARTEN        │  KARTEN DETAIL             │
  │  (links, 280px) │  (mitte, 300px)           │  (rechts, expandiert)      │
  └─────────────────┴──────────────────────────┴────────────────────────────┘
"""

import copy
import json
import os
import random
import tkinter as tk
from tkinter import ttk, messagebox

from .models import (
    load_random_cards, save_random_cards, clear_random_cards,
    load_gen_config, save_gen_config,
    load_box_config,
    load_content_probs, save_content_probs,
    GENERATOR_PROFILES, RECIPE_TYPES,
)
from .generator import CardGenerator
from .generator.base import list_to_lookup
from .cv_calc import cv_card, cv_content_item, complexity_card, complexity_content_item

from card_builder.constants import ELEMENTS

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Data loading ─────────────────────────────────────────────────────────────

def _load_content_data() -> dict:
    data = {}
    cc_dir = os.path.join(_ROOT, "CardContent", "cc_data")
    for fname, key in [("effects.json",    "Effect"),
                        ("costs.json",      "Cost"),
                        ("conditions.json", "Condition"),
                        ("triggers.json",   "Trigger"),
                        ("inserts.json",    "Insert")]:
        path = os.path.join(cc_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            items = raw.get(key, raw.get(list(raw.keys())[0], []))
            data[key] = items
        except Exception:
            data[key] = []
    return data


def _save_content_data(data: dict):
    cc_dir = os.path.join(_ROOT, "CardContent", "cc_data")
    for fname, key in [("effects.json",    "Effect"),
                        ("costs.json",      "Cost"),
                        ("conditions.json", "Condition"),
                        ("triggers.json",   "Trigger"),
                        ("inserts.json",    "Insert"),
                        ("enchants.json",   "Enchant"),
                        ("curses.json",     "Curse")]:
        if key not in data:
            continue
        path = os.path.join(cc_dir, fname)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({key: data[key]}, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[save_content_data] Fehler beim Schreiben {fname}: {e}")


def _load_containers() -> dict:
    try:
        from container_manager.models import load_containers
        return load_containers()
    except Exception:
        return {}


def _render_card_summary(card: dict) -> str:
    el  = card.get("recipe_type") or card.get("element") or card.get("card_type") or "?"
    cv  = card.get("_cv", "?")
    cmx = card.get("_complexity", "?")
    if card.get("ingredients") is not None:
        ni = len(card.get("ingredients", []))
        return f"{el:<10}  CV={cv:<6}  Cmplx={cmx:<5}  Zutaten={ni}"
    nb  = len(card.get("blocks", []))
    return f"{el:<10}  CV={cv:<6}  Cmplx={cmx:<5}  Sigils={nb}"


def render_effect(item: dict, vals: dict, opt_vals: dict,
                  fallback_id: str = "") -> str:
    from CardContent.template_parser import render_content_text, render_display_text
    if not item and not fallback_id:
        return ""
    sigil = item.get("sigil", "") if item else ""
    ct    = item.get("content_text", "") if item else ""
    if ct:
        text = render_display_text(ct, vals, opt_vals)
    elif sigil:
        text = render_content_text(sigil, vals, opt_vals)
    else:
        text = ""
    if not text:
        parts = [fallback_id or (item.get("id", "?") if item else "?")]
        for k, v in vals.items():
            parts.append(f"{k}={v}")
        for oi in sorted(opt_vals.keys()):
            parts.append(f"[{opt_vals[oi]}]")
        return " ".join(parts)
    return text.strip()


# ── Main panel ───────────────────────────────────────────────────────────────

class RandomBuilder(tk.Frame):

    def __init__(self, parent, **kw):
        kw.setdefault("bg", "#1a1a1a")
        super().__init__(parent, **kw)
        self._content_data   = _load_content_data()
        self._effects_lu     = list_to_lookup(self._content_data.get("Effect",    []))
        self._costs_lu       = list_to_lookup(self._content_data.get("Cost",      []))
        self._triggers_lu    = list_to_lookup(self._content_data.get("Trigger",   []))
        self._conditions_lu  = list_to_lookup(self._content_data.get("Condition", []))
        self._containers     = _load_containers()
        self._current_profile = "Spells"
        self._content_probs = load_content_probs()
        self._box_config    = load_box_config()
        self._gen_config    = load_gen_config(self._current_profile)
        self._cards: list   = load_random_cards(self._current_profile)
        self._selected_idx  = None
        self._build()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self):
        # ── Left settings panel ──────────────────────────────────────────────
        left = tk.Frame(self, bg="#1a1a1a", width=290)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        self._settings_parent = left

        ttk.Separator(self, orient="vertical").pack(side="left", fill="y")

        # ── Center card list ─────────────────────────────────────────────────
        center = tk.Frame(self, bg="#1a1a1a", width=340)
        center.pack(side="left", fill="y")
        center.pack_propagate(False)

        ttk.Separator(self, orient="vertical").pack(side="left", fill="y")

        # ── Right detail view ────────────────────────────────────────────────
        right = tk.Frame(self, bg="#1a1a1a")
        right.pack(side="left", fill="both", expand=True)

        self._build_profile_bar(left)
        self._build_settings(left)
        self._build_card_list(center)
        self._build_detail(right)

    # ── Profile bar ──────────────────────────────────────────────────────────

    def _build_profile_bar(self, parent):
        prof_bar = tk.Frame(parent, bg="#111")
        prof_bar.pack(fill="x", side="top")
        tk.Label(prof_bar, text="Generator:", bg="#111", fg="#666",
                 font=("Arial", 8)).pack(side="left", padx=4)
        self._profile_btns = {}
        for p in GENERATOR_PROFILES:
            btn = tk.Button(prof_bar, text=p, font=("Arial", 8),
                            relief="flat", cursor="hand2",
                            command=lambda name=p: self._switch_profile(name))
            btn.pack(side="left", padx=2, pady=2)
            self._profile_btns[p] = btn
        self._update_profile_btn_styles()

    def _update_profile_btn_styles(self):
        for p, btn in self._profile_btns.items():
            if p == self._current_profile:
                btn.config(bg="#1a6e3c", fg="white")
            else:
                btn.config(bg="#2a2a2a", fg="#888")

    def _switch_profile(self, name: str):
        if name == self._current_profile:
            return
        cfg = self._settings_panel.collect_config()
        save_gen_config(cfg, self._current_profile)
        save_random_cards(self._cards, self._current_profile)

        self._current_profile = name
        self._gen_config = load_gen_config(name)
        self._cards = load_random_cards(name)
        self._content_probs = load_content_probs()

        # Rebuild settings
        self._settings_panel.destroy()
        self._build_settings(self._settings_parent)
        self._update_profile_btn_styles()
        self._refresh_list()
        self._selected_idx = None
        self._clear_detail()

    # ── Settings panel ───────────────────────────────────────────────────────

    def _build_settings(self, parent):
        from .ui.settings import SettingsPanel
        self._settings_panel = SettingsPanel(
            parent,
            profile=self._current_profile,
            gen_config=self._gen_config,
            containers=self._containers,
            content_data=self._content_data,
            content_probs=self._content_probs,
            on_autosave=self._do_autosave,
            on_generate=self._generate,
            on_save=self._save_config,
            on_reload_containers=self._reload_containers,
            on_pick_effects=self._open_effects_picker_for_rule,
            on_pick_effect_id=self._pick_effect_id,
            on_open_ingredients=self._open_ingredient_editor,
        )
        self._settings_panel.pack(fill="both", expand=True)

    # ══════════════════════════════════════════════════════════════════════════
    # CENTER – Card list
    # ══════════════════════════════════════════════════════════════════════════

    def _build_card_list(self, parent):
        hdr = tk.Frame(parent, bg="#1a1a1a")
        hdr.pack(fill="x", padx=8, pady=(6, 2))
        tk.Label(hdr, text="Generierte Karten",
                 bg="#1a1a1a", fg="#88ccff",
                 font=("Arial", 10, "bold")).pack(side="left")
        tk.Button(hdr, text="🗑 Alle löschen",
                  command=self._delete_all,
                  bg="#5a1a1a", fg="#ff8888",
                  font=("Arial", 8), cursor="hand2",
                  relief="flat").pack(side="right")

        filter_f = tk.Frame(parent, bg="#1a1a1a")
        filter_f.pack(fill="x", padx=8, pady=2)
        tk.Label(filter_f, text="Element:", bg="#1a1a1a", fg="#888",
                 font=("Arial", 8)).pack(side="left")
        self._filter_el_var = tk.StringVar(value="Alle")
        el_cb = ttk.Combobox(filter_f, textvariable=self._filter_el_var,
                             values=["Alle"] + ELEMENTS + RECIPE_TYPES,
                             state="readonly", width=10)
        el_cb.pack(side="left", padx=2)
        el_cb.bind("<<ComboboxSelected>>", lambda _: self._refresh_list())

        tk.Label(filter_f, text="Sort:", bg="#1a1a1a", fg="#888",
                 font=("Arial", 8)).pack(side="left", padx=(6, 0))
        self._sort_var = tk.StringVar(value="Standard")
        sort_cb = ttk.Combobox(filter_f, textvariable=self._sort_var,
                               values=["Standard", "A → Z", "Z → A", "CV ↑", "CV ↓"],
                               state="readonly", width=9)
        sort_cb.pack(side="left", padx=2)
        sort_cb.bind("<<ComboboxSelected>>", lambda _: self._refresh_list())

        tk.Button(filter_f, text="🎲", command=self._random_pick,
                  bg="#2a2a2a", fg="#aaa", font=("Arial", 10),
                  cursor="hand2").pack(side="right", padx=2)

        self._count_label = tk.Label(parent, text="0 Karten",
                                     bg="#1a1a1a", fg="#555",
                                     font=("Arial", 8))
        self._count_label.pack(anchor="w", padx=8)

        list_f = tk.Frame(parent, bg="#1a1a1a")
        list_f.pack(fill="both", expand=True, padx=8, pady=4)
        vsb = tk.Scrollbar(list_f, orient="vertical")
        vsb.pack(side="right", fill="y")
        self._card_lb = tk.Listbox(
            list_f, yscrollcommand=vsb.set,
            bg="#2a2a2a", fg="white",
            selectbackground="#1a3e8e", activestyle="dotbox",
            font=("Consolas", 8), relief="flat")
        self._card_lb.pack(side="left", fill="both", expand=True)
        vsb.config(command=self._card_lb.yview)
        self._card_lb.bind("<<ListboxSelect>>", self._on_card_select)

        tk.Button(parent, text="🗑 Ausgewählte löschen",
                  command=self._delete_selected,
                  bg="#3a1a1a", fg="#cc6666",
                  font=("Arial", 8), cursor="hand2").pack(
            fill="x", padx=8, pady=(0, 4))

        self._refresh_list()

    def _refresh_list(self):
        self._card_lb.delete(0, "end")
        el_filter = self._filter_el_var.get()
        visible = [
            (i, c) for i, c in enumerate(self._cards)
            if el_filter == "Alle"
               or c.get("element") == el_filter
               or c.get("recipe_type") == el_filter
        ]
        sort_mode = getattr(self, "_sort_var", None)
        sort_mode = sort_mode.get() if sort_mode else "Standard"
        if sort_mode == "A → Z":
            visible.sort(key=lambda ic: ic[1].get("name", "").lower())
        elif sort_mode == "Z → A":
            visible.sort(key=lambda ic: ic[1].get("name", "").lower(), reverse=True)
        elif sort_mode == "CV ↑":
            visible.sort(key=lambda ic: float(ic[1].get("_cv", 0)))
        elif sort_mode == "CV ↓":
            visible.sort(key=lambda ic: float(ic[1].get("_cv", 0)), reverse=True)
        self._visible_indices = [i for i, _ in visible]
        for i, card in visible:
            self._card_lb.insert("end", f"{card.get('name', '?'):<26} "
                                        + _render_card_summary(card))
        self._count_label.config(text=f"{len(visible)} / {len(self._cards)} Karten")

    def _on_card_select(self, _=None):
        sel = self._card_lb.curselection()
        if not sel:
            return
        list_idx = sel[0]
        if list_idx < len(self._visible_indices):
            self._selected_idx = self._visible_indices[list_idx]
            self._show_detail(self._cards[self._selected_idx])

    def _random_pick(self):
        el_filter = self._filter_el_var.get()
        pool = [i for i, c in enumerate(self._cards)
                if el_filter == "Alle"
                   or c.get("element") == el_filter
                   or c.get("recipe_type") == el_filter]
        if not pool:
            return
        idx = random.choice(pool)
        self._selected_idx = idx
        list_pos = self._visible_indices.index(idx) if idx in self._visible_indices else None
        if list_pos is not None:
            self._card_lb.selection_clear(0, "end")
            self._card_lb.selection_set(list_pos)
            self._card_lb.see(list_pos)
        self._show_detail(self._cards[idx])

    def _delete_selected(self):
        if self._selected_idx is None:
            return
        del self._cards[self._selected_idx]
        self._selected_idx = None
        save_random_cards(self._cards, self._current_profile)
        self._refresh_list()
        self._clear_detail()

    def _delete_all(self):
        if not self._cards:
            return
        if not messagebox.askyesno(
                "Alle löschen",
                f"Alle {len(self._cards)} zufällig generierten Karten löschen?",
                parent=self):
            return
        self._cards = []
        clear_random_cards(self._current_profile)
        self._selected_idx = None
        self._refresh_list()
        self._clear_detail()
        self._settings_panel.set_status("Alle Karten gelöscht.", "#8e1a1a")

    # ══════════════════════════════════════════════════════════════════════════
    # RIGHT – Card detail
    # ══════════════════════════════════════════════════════════════════════════

    def _build_detail(self, parent):
        self._detail_header = tk.Label(
            parent, text="← Karte auswählen",
            bg="#1a1a1a", fg="#555",
            font=("Arial", 11, "italic"))
        self._detail_header.pack(anchor="w", padx=12, pady=(8, 4))

        self._metrics_label = tk.Label(
            parent, text="", bg="#1a1a1a", fg="#888",
            font=("Consolas", 9))
        self._metrics_label.pack(anchor="w", padx=12)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=6)

        content_row = tk.Frame(parent, bg="#1a1a1a")
        content_row.pack(fill="both", expand=True)

        from card_builder.card_preview import CardPreviewWidget
        self._card_preview = CardPreviewWidget(content_row, label="Vorschau", bg="#1a1a1a")
        self._card_preview.pack(side="left", anchor="n", padx=(8, 4), pady=4)

        outer = tk.Frame(content_row, bg="#1a1a1a")
        outer.pack(side="left", fill="both", expand=True)
        vsb = tk.Scrollbar(outer, orient="vertical")
        vsb.pack(side="right", fill="y")
        self._detail_canvas = tk.Canvas(outer, yscrollcommand=vsb.set,
                                        bg="#1a1a1a", highlightthickness=0)
        self._detail_canvas.pack(fill="both", expand=True)
        vsb.config(command=self._detail_canvas.yview)
        self._detail_canvas.bind(
            "<MouseWheel>",
            lambda e: self._detail_canvas.yview_scroll(int(-e.delta / 120), "units"))

        self._detail_inner = tk.Frame(self._detail_canvas, bg="#1a1a1a")
        self._detail_win = self._detail_canvas.create_window(
            (0, 0), window=self._detail_inner, anchor="nw")
        self._detail_inner.bind(
            "<Configure>",
            lambda e: self._detail_canvas.configure(
                scrollregion=self._detail_canvas.bbox("all")))
        self._detail_canvas.bind(
            "<Configure>",
            lambda e: self._detail_canvas.itemconfig(
                self._detail_win, width=e.width))

    def _clear_detail(self):
        self._detail_header.config(text="← Karte auswählen")
        self._card_preview.clear()
        self._metrics_label.config(text="")
        for w in self._detail_inner.winfo_children():
            w.destroy()

    def _show_detail(self, card: dict):
        rt = card.get("recipe_type", "")
        label = rt or card.get("element") or card.get("card_type", "?")
        self._detail_header.config(
            text=f"🃏  {card.get('name', '?')}   [{label}]", fg="#cc8833")

        if card.get("ingredients") is not None:
            n_ings = len(card.get("ingredients", []))
            self._metrics_label.config(
                text=f"CV: {card.get('_cv', '?')}   Complexity: {card.get('_complexity', '?')}"
                     f"   Zutaten: {n_ings}")
        else:
            self._metrics_label.config(
                text=f"CV: {card.get('_cv', '?')}   Complexity: {card.get('_complexity', '?')}"
                     f"   Sigils: {len(card.get('blocks', []))}")

        # Render visual card preview
        try:
            rc = self._to_render_card(card)
            self._card_preview.show(rc)
        except Exception as e:
            print(f"[detail] Vorschau FEHLER: {e}")
            import traceback; traceback.print_exc()
            self._card_preview.clear()

        for w in self._detail_inner.winfo_children():
            w.destroy()

        if card.get("ingredients") is not None:
            self._show_recipe_detail(card)
        else:
            self._show_spell_detail(card)

    def _show_recipe_detail(self, card: dict):
        BG = "#1e2a2a"
        parent = self._detail_inner

        ih = tk.Frame(parent, bg="#2a4a2a")
        ih.pack(fill="x", padx=8, pady=(8, 0))
        tk.Label(ih, text="  🧪  Zutaten", bg="#2a4a2a", fg="white",
                 font=("Arial", 10, "bold")).pack(side="left", padx=6, pady=3)

        for ing in card.get("ingredients", []):
            row = tk.Frame(parent, bg=BG, relief="groove", bd=1)
            row.pack(fill="x", padx=12, pady=1)
            mat = ing.get("material", "?")
            cv  = ing.get("cv", 4)
            tk.Label(row, text=f"  • {mat}", bg=BG, fg="#aaffaa",
                     font=("Arial", 9, "bold"), anchor="w").pack(side="left", padx=4, pady=2)
            tk.Label(row, text=f"CV {cv}", bg=BG, fg="#888",
                     font=("Consolas", 8)).pack(side="right", padx=8)

        effects = card.get("effects", [])
        if effects:
            eh = tk.Frame(parent, bg="#2a2a4a")
            eh.pack(fill="x", padx=8, pady=(8, 0))
            tk.Label(eh, text="  ◆  Effekte", bg="#2a2a4a", fg="white",
                     font=("Arial", 10, "bold")).pack(side="left", padx=6, pady=3)

            for eff in effects:
                eid = eff.get("effect_id", "?")
                item = self._effects_lu.get(eid, {})
                vals = eff.get("vals", {})
                opts = eff.get("opt_vals", {})
                text = render_effect(item, vals, opts, fallback_id=eid)

                row = tk.Frame(parent, bg="#1e1e2e", relief="groove", bd=1)
                row.pack(fill="x", padx=12, pady=1)
                tk.Button(row, text=f"  Eff: {eid}",
                          bg="#1e1e2e", fg="#88ff88", relief="flat", cursor="hand2",
                          font=("Consolas", 8), anchor="w",
                          command=lambda i=eid: self._open_content_editor(i, "Effect")
                          ).pack(side="left")
                tk.Label(row, text=f"→  {text}", bg="#1e1e2e", fg="#cccccc",
                         font=("Consolas", 8)).pack(side="left", padx=4)

                for vname, vval in vals.items():
                    vr = tk.Frame(parent, bg="#161622")
                    vr.pack(fill="x", padx=24, pady=0)
                    tk.Label(vr, text=f"{{{vname}}} = {vval}",
                             bg="#161622", fg="#888",
                             font=("Consolas", 8)).pack(side="left", padx=8)

        use_text = card.get("use_text", "")
        if use_text:
            uf = tk.Frame(parent, bg="#1e1e1e", relief="groove", bd=1)
            uf.pack(fill="x", padx=8, pady=(8, 4))
            tk.Label(uf, text="Use:", bg="#1e1e1e", fg="#888",
                     font=("Arial", 8, "bold")).pack(anchor="w", padx=4, pady=2)
            tk.Label(uf, text=use_text, bg="#1e1e1e", fg="white",
                     font=("Arial", 9), wraplength=400, justify="left",
                     anchor="w").pack(fill="x", padx=8, pady=2)

    def _show_spell_detail(self, card: dict):
        from card_builder.constants import BOX_COLORS as BLOCK_COLORS, BOX_SYMBOLS as BLOCK_SYMBOLS

        BG  = "#1e1e2e"
        BG2 = "#161622"

        for block in card.get("blocks", []):
            btype = block.get("type", "?")
            color = BLOCK_COLORS.get(btype, "#333")
            sym   = BLOCK_SYMBOLS.get(btype, "■")

            bh = tk.Frame(self._detail_inner, bg=color)
            bh.pack(fill="x", padx=8, pady=(8, 0))
            tk.Label(bh, text=f" {sym}  {btype}",
                     bg=color, fg="white",
                     font=("Arial", 10, "bold")).pack(side="left", padx=6, pady=3)

            for ab in block.get("abilities", []):
                ab_frame = tk.Frame(self._detail_inner, bg=BG, relief="groove", bd=1)
                ab_frame.pack(fill="x", padx=12, pady=2)

                ab_cv = 0
                try:
                    from .cv_calc import cv_ability as _cv_ability
                    ab_cv = _cv_ability(ab, self._effects_lu, self._costs_lu)
                except Exception:
                    pass
                # Complexity over all effects (groups + legacy)
                ab_cmplx = 0.0
                for g in ab.get("effect_groups", []):
                    # Support 'effects' list, 'primaries', or old 'primary'
                    effs = g.get("effects") or g.get("primaries", [])
                    if not effs and "primary" in g:
                        effs = [g["primary"]]
                    for e in effs:
                        peid = e.get("effect_id", "")
                        if peid in self._effects_lu:
                            ab_cmplx += complexity_content_item(self._effects_lu[peid])
                    for m in g.get("modifiers", []):
                        meid = m.get("effect_id", "")
                        if meid in self._effects_lu:
                            ab_cmplx += complexity_content_item(self._effects_lu[meid])
                for e in ab.get("effects", []):
                    if e.get("effect_id") in self._effects_lu:
                        ab_cmplx += complexity_content_item(
                            self._effects_lu[e["effect_id"]])
                for c in ab.get("costs", []):
                    if c.get("cost_id") in self._costs_lu:
                        ab_cmplx += complexity_content_item(
                            self._costs_lu[c["cost_id"]])

                ab_type = ab.get("ability_type", "Play")
                hrow = tk.Frame(ab_frame, bg=BG)
                hrow.pack(fill="x", padx=4, pady=(4, 2))
                tk.Label(hrow, text=f"  {ab_type}",
                         bg=BG, fg="#88aaff",
                         font=("Arial", 9, "bold")).pack(side="left")
                tk.Label(hrow,
                         text=f"CV={ab_cv:+.2f}   Cmplx={ab_cmplx:.1f}",
                         bg=BG, fg="#aaaaaa",
                         font=("Consolas", 8)).pack(side="right", padx=6)

                # Condition
                if ab.get("condition_id"):
                    cid2   = ab["condition_id"]
                    ci2    = self._conditions_lu.get(cid2, {})
                    ct2    = render_effect(ci2, ab.get("condition_vals", {}),
                                          ab.get("condition_opt_vals", {}),
                                          fallback_id=cid2)
                    c2_cmx = complexity_content_item(ci2) if ci2 else 0.0
                    cdrow  = tk.Frame(ab_frame, bg="#1e1424")
                    cdrow.pack(fill="x", padx=8, pady=1)
                    tk.Button(cdrow, text=f"  ◈ Cond: {cid2}",
                              bg="#1e1424", fg="#cc88ff", relief="flat", cursor="hand2",
                              font=("Consolas", 8), anchor="w",
                              command=lambda i=cid2: self._open_content_editor(i, "Condition")
                              ).pack(side="left")
                    tk.Label(cdrow, text=f"→  {ct2}",
                             bg="#1e1424", fg="#ddaaff",
                             font=("Consolas", 8)).pack(side="left", padx=4)
                    tk.Label(cdrow, text=f"Cx={c2_cmx:.1f}",
                             bg="#1e1424", fg="#886699",
                             font=("Consolas", 7)).pack(side="right", padx=6)

                # Trigger
                if ab.get("trigger_id"):
                    tid2   = ab["trigger_id"]
                    ti2    = self._triggers_lu.get(tid2, {})
                    tt2    = render_effect(ti2, ab.get("trigger_vals", {}),
                                          ab.get("trigger_opt_vals", {}),
                                          fallback_id=tid2)
                    t2_cmx = complexity_content_item(ti2) if ti2 else 0.0
                    trrow  = tk.Frame(ab_frame, bg="#141e14")
                    trrow.pack(fill="x", padx=8, pady=1)
                    tk.Button(trrow, text=f"  ⚡ Trig: {tid2}",
                              bg="#141e14", fg="#aaff88", relief="flat", cursor="hand2",
                              font=("Consolas", 8), anchor="w",
                              command=lambda i=tid2: self._open_content_editor(i, "Trigger")
                              ).pack(side="left")
                    tk.Label(trrow, text=f"→  {tt2}",
                             bg="#141e14", fg="#ccffaa",
                             font=("Consolas", 8)).pack(side="left", padx=4)
                    tk.Label(trrow, text=f"Cx={t2_cmx:.1f}",
                             bg="#141e14", fg="#668844",
                             font=("Consolas", 7)).pack(side="right", padx=6)

                # Costs
                for cost in ab.get("costs", []):
                    cid   = cost.get("cost_id", "?")
                    cvals = cost.get("vals", {})
                    citem = self._costs_lu.get(cid, {})
                    copt  = cost.get("opt_vals", {})
                    ctext = render_effect(citem, cvals, copt, fallback_id=cid)
                    c_cv  = cv_content_item(citem, cvals, copt) if citem else 0.0
                    c_cmx = complexity_content_item(citem) if citem else 0.0
                    crow  = tk.Frame(ab_frame, bg=BG2)
                    crow.pack(fill="x", padx=8, pady=1)
                    tk.Button(crow, text=f"  Cost: {cid}",
                              bg=BG2, fg="#ffaa44", relief="flat", cursor="hand2",
                              font=("Consolas", 8), anchor="w",
                              command=lambda i=cid: self._open_content_editor(i, "Cost")
                              ).pack(side="left")
                    tk.Label(crow, text=f"→  {ctext}",
                             bg=BG2, fg="#ffcc77",
                             font=("Consolas", 8)).pack(side="left", padx=4)
                    tk.Label(crow, text=f"CV={c_cv:+.2f}  Cx={c_cmx:.1f}",
                             bg=BG2, fg="#886633",
                             font=("Consolas", 7)).pack(side="right", padx=6)

                # Effect groups (new format)
                for gi, grp in enumerate(ab.get("effect_groups", [])):
                    tt = grp.get("target_type", "")
                    gh = tk.Frame(ab_frame, bg="#1a2030")
                    gh.pack(fill="x", padx=8, pady=(2, 0))
                    tk.Label(gh, text=f"  ▸ {tt}",
                             bg="#1a2030", fg="#6699cc",
                             font=("Consolas", 8, "bold")).pack(side="left")

                    # Effects list (support 'effects', 'primaries', 'primary')
                    effs = grp.get("effects") or grp.get("primaries", [])
                    if not effs and "primary" in grp:
                        effs = [grp["primary"]]
                    for eff_item_d in effs:
                        eid   = eff_item_d.get("effect_id", "?")
                        evals = eff_item_d.get("vals", {})
                        eopt  = eff_item_d.get("opt_vals", {})
                        eitem = self._effects_lu.get(eid, {})
                        etext = render_effect(eitem, evals, eopt, fallback_id=eid)
                        e_cv  = cv_content_item(eitem, evals, eopt) if eitem else 0.0
                        e_cmx = complexity_content_item(eitem) if eitem else 0.0

                        erow = tk.Frame(ab_frame, bg=BG)
                        erow.pack(fill="x", padx=16, pady=1)
                        tk.Button(erow, text=f"  Eff: {eid}",
                                  bg=BG, fg="#88ff88", relief="flat", cursor="hand2",
                                  font=("Consolas", 8), anchor="w",
                                  command=lambda i=eid: self._open_content_editor(i, "Effect")
                                  ).pack(side="left")
                        tk.Label(erow, text=f"→  {etext}",
                                 bg=BG, fg="#ccffcc",
                                 font=("Consolas", 8)).pack(side="left", padx=4)
                        tk.Label(erow, text=f"CV={e_cv:+.2f}  Cx={e_cmx:.1f}",
                                 bg=BG, fg="#448844",
                                 font=("Consolas", 7)).pack(side="right", padx=6)

                        for vk, vv in evals.items():
                            vrow = tk.Frame(ab_frame, bg=BG)
                            vrow.pack(fill="x", padx=32, pady=0)
                            tk.Label(vrow, text=f"  {{{vk}}} =",
                                     bg=BG, fg="#558855",
                                     font=("Consolas", 7)).pack(side="left")
                            btn_v = tk.Button(vrow, text=str(vv),
                                      bg=BG, fg="#88ff88", relief="flat", cursor="hand2",
                                      font=("Consolas", 7, "underline"))
                            btn_v.config(command=lambda b=btn_v, d=eff_item_d, k=vk:
                                         self._inline_edit_var(b, card, d, k, eid, "Effect"))
                            btn_v.pack(side="left", padx=2)

                    # Modifiers
                    for mod in grp.get("modifiers", []):
                        mid   = mod.get("effect_id", "?")
                        mvals = mod.get("vals", {})
                        mopt  = mod.get("opt_vals", {})
                        mitem = self._effects_lu.get(mid, {})
                        mtext = render_effect(mitem, mvals, mopt, fallback_id=mid)
                        m_cv  = cv_content_item(mitem, mvals, mopt) if mitem else 0.0
                        m_cmx = complexity_content_item(mitem) if mitem else 0.0

                        mrow = tk.Frame(ab_frame, bg="#181a28")
                        mrow.pack(fill="x", padx=24, pady=0)
                        tk.Button(mrow, text=f"  + {mid}",
                                  bg="#181a28", fg="#aaccff", relief="flat", cursor="hand2",
                                  font=("Consolas", 8), anchor="w",
                                  command=lambda i=mid: self._open_content_editor(i, "Effect")
                                  ).pack(side="left")
                        tk.Label(mrow, text=f"→  {mtext}",
                                 bg="#181a28", fg="#cce0ff",
                                 font=("Consolas", 8)).pack(side="left", padx=4)
                        tk.Label(mrow, text=f"CV={m_cv:+.2f}  Cx={m_cmx:.1f}",
                                 bg="#181a28", fg="#446688",
                                 font=("Consolas", 7)).pack(side="right", padx=6)

                    # Per-group sub-sigil (Option A)
                    self._render_sub_sigil_block(ab_frame, grp.get("sub_sigil"),
                                                 label="Sub-Sigil (group)",
                                                 indent_px=16)

                # Legacy flat effects
                for eff in ab.get("effects", []):
                    eid   = eff.get("effect_id", "?")
                    evals = eff.get("vals", {})
                    eopt  = eff.get("opt_vals", {})
                    eitem = self._effects_lu.get(eid, {})
                    etext = render_effect(eitem, evals, eopt, fallback_id=eid)
                    e_cv  = cv_content_item(eitem, evals, eopt) if eitem else 0.0
                    e_cmx = complexity_content_item(eitem) if eitem else 0.0

                    erow = tk.Frame(ab_frame, bg=BG)
                    erow.pack(fill="x", padx=8, pady=1)
                    tk.Button(erow, text=f"  Eff: {eid}",
                              bg=BG, fg="#88ff88", relief="flat", cursor="hand2",
                              font=("Consolas", 8), anchor="w",
                              command=lambda i=eid: self._open_content_editor(i, "Effect")
                              ).pack(side="left")
                    tk.Label(erow, text=f"→  {etext}",
                             bg=BG, fg="#ccffcc",
                             font=("Consolas", 8)).pack(side="left", padx=4)
                    tk.Label(erow, text=f"CV={e_cv:+.2f}  Cx={e_cmx:.1f}",
                             bg=BG, fg="#448844",
                             font=("Consolas", 7)).pack(side="right", padx=6)

                    for vk, vv in evals.items():
                        vrow = tk.Frame(ab_frame, bg=BG)
                        vrow.pack(fill="x", padx=24, pady=0)
                        tk.Label(vrow, text=f"  {{{vk}}} =",
                                 bg=BG, fg="#558855",
                                 font=("Consolas", 7)).pack(side="left")
                        btn_v = tk.Button(vrow, text=str(vv),
                                  bg=BG, fg="#88ff88", relief="flat", cursor="hand2",
                                  font=("Consolas", 7, "underline"))
                        btn_v.config(command=lambda b=btn_v, d=eff, k=vk:
                                     self._inline_edit_var(b, card, d, k, eid, "Effect"))
                        btn_v.pack(side="left", padx=2)

                    for oi, choice in sorted(eopt.items()):
                        orow = tk.Frame(ab_frame, bg=BG)
                        orow.pack(fill="x", padx=24, pady=0)
                        tk.Label(orow, text=f"  [opt{oi}] =",
                                 bg=BG, fg="#558888",
                                 font=("Consolas", 7)).pack(side="left")
                        btn_o = tk.Button(orow, text=str(choice),
                                  bg=BG, fg="#88cccc", relief="flat", cursor="hand2",
                                  font=("Consolas", 7, "underline"))
                        btn_o.config(command=lambda b=btn_o, d=eff, k=oi:
                                     self._inline_edit_opt(b, card, d, k, eid, "Effect"))
                        btn_o.pack(side="left", padx=2)

                # Legacy per-ability sub-sigil (old cards)
                self._render_sub_sigil_block(ab_frame, ab.get("sub_sigil"),
                                             label="Sub-Sigil")
                # Global sub-sigil (Option B/C)
                self._render_sub_sigil_block(ab_frame, ab.get("sub_sigil_global"),
                                             label="Sub-Sigil (Global)")

                tk.Frame(ab_frame, bg=BG, height=3).pack()

        # Raw JSON toggle
        def _toggle_json(f=self._detail_inner, c=card):
            txt = tk.Text(f, bg="#111", fg="#aaa",
                          font=("Consolas", 7), height=20, wrap="none")
            txt.pack(fill="x", padx=8, pady=4)
            txt.insert("end", json.dumps(c, indent=2, ensure_ascii=False))
            txt.config(state="disabled")

        tk.Button(self._detail_inner, text="{ } JSON anzeigen",
                  command=_toggle_json,
                  bg="#2a2a2a", fg="#666",
                  font=("Arial", 7)).pack(anchor="w", padx=8, pady=4)

    # ══════════════════════════════════════════════════════════════════════════
    # Actions & helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _to_render_card(self, card: dict) -> dict:
        import re
        rc = copy.deepcopy(card)
        rc.setdefault("name", card.get("name", "?"))
        rc.setdefault("artwork", "")
        rc.setdefault("card_type", "Spells")
        for blk in rc.get("blocks", []):
            for ab in blk.get("abilities", []):
                for eff in ab.get("effects", []):
                    eid = eff.get("effect_id", "")
                    item = self._effects_lu.get(eid, {})
                    evals = eff.get("vals", {})
                    eopt = eff.get("opt_vals", {})
                    eff["content_text"] = render_effect(item, evals, eopt, fallback_id=eid)
                for cost in ab.get("costs", []):
                    cid = cost.get("cost_id", "")
                    item = self._costs_lu.get(cid, {})
                    cvals = cost.get("vals", {})
                    copt = cost.get("opt_vals", {})
                    cost["content_text"] = render_effect(item, cvals, copt, fallback_id=cid)
        return rc

    def _render_sub_sigil_block(self, parent, sub: dict, label: str = "Sub-Sigil",
                                indent_px: int = 8):
        """Render a sub-sigil (header + condition + costs + effect groups)
        into `parent`. Used for per-group, global, and legacy sub-sigils.
        """
        if not sub:
            return
        # Header
        sh = tk.Frame(parent, bg="#2a1a10")
        sh.pack(fill="x", padx=indent_px, pady=(4, 1))
        tgt = sub.get("target_type", "")
        header = f"  \u25c6 {label}" + (f"  [{tgt}]" if tgt else "")
        tk.Label(sh, text=header,
                 bg="#2a1a10", fg="#ffcc66",
                 font=("Consolas", 8, "bold")).pack(side="left")

        inner_pad = indent_px + 8

        # Condition (sub-sigils may have one)
        scid = sub.get("condition_id")
        if scid:
            scitem = self._conditions_lu.get(scid, {})
            sctext = render_effect(scitem,
                                   sub.get("condition_vals", {}),
                                   sub.get("condition_opt_vals", {}),
                                   fallback_id=scid)
            crow = tk.Frame(parent, bg="#1e1408")
            crow.pack(fill="x", padx=inner_pad, pady=0)
            tk.Label(crow, text=f"  \u25c8 Cond: {scid} \u2192  {sctext}",
                     bg="#1e1408", fg="#ddaaff",
                     font=("Consolas", 8)).pack(side="left", padx=4)

        # Costs
        for scost in sub.get("costs", []):
            cid   = scost.get("cost_id", "?")
            cvals = scost.get("vals", {})
            copt  = scost.get("opt_vals", {})
            citem = self._costs_lu.get(cid, {})
            ctext = render_effect(citem, cvals, copt, fallback_id=cid)
            c_cv  = cv_content_item(citem, cvals, copt) if citem else 0.0
            c_cmx = complexity_content_item(citem) if citem else 0.0
            # For Mana, fall back to element name if rendered text is empty
            if cid == "Mana" and not ctext:
                ctext = cvals.get("element") or copt.get("0", "Mana")
            crow = tk.Frame(parent, bg="#1e1408")
            crow.pack(fill="x", padx=inner_pad, pady=0)
            tk.Label(crow, text=f"  Cost: {cid} \u2192  {ctext}",
                     bg="#1e1408", fg="#ffcc77",
                     font=("Consolas", 8)).pack(side="left", padx=4)
            tk.Label(crow, text=f"CV={c_cv:+.2f}  Cx={c_cmx:.1f}",
                     bg="#1e1408", fg="#886633",
                     font=("Consolas", 7)).pack(side="right", padx=6)

        # Effect groups
        for sgrp in sub.get("effect_groups", []):
            stt = sgrp.get("target_type", "")
            sgh = tk.Frame(parent, bg="#201a08")
            sgh.pack(fill="x", padx=inner_pad, pady=0)
            tk.Label(sgh, text=f"  \u25b8 {stt}",
                     bg="#201a08", fg="#cc9944",
                     font=("Consolas", 8, "bold")).pack(side="left")
            # Support 'effects' list or old 'primary'
            seffs = sgrp.get("effects") or sgrp.get("primaries", [])
            if not seffs and "primary" in sgrp:
                seffs = [sgrp["primary"]]
            for sp in seffs:
                eid   = sp.get("effect_id", "?")
                evals = sp.get("vals", {})
                eopt  = sp.get("opt_vals", {})
                eitem = self._effects_lu.get(eid, {})
                etext = render_effect(eitem, evals, eopt, fallback_id=eid)
                e_cv  = cv_content_item(eitem, evals, eopt) if eitem else 0.0
                e_cmx = complexity_content_item(eitem) if eitem else 0.0
                erow  = tk.Frame(parent, bg="#181408")
                erow.pack(fill="x", padx=inner_pad + 8, pady=0)
                tk.Label(erow, text=f"  Eff: {eid} \u2192  {etext}",
                         bg="#181408", fg="#eedd88",
                         font=("Consolas", 8)).pack(side="left", padx=4)
                tk.Label(erow, text=f"CV={e_cv:+.2f}  Cx={e_cmx:.1f}",
                         bg="#181408", fg="#886633",
                         font=("Consolas", 7)).pack(side="right", padx=6)
            # Modifiers inside sub-sigil group
            for mod in sgrp.get("modifiers", []):
                mid   = mod.get("effect_id", "?")
                mvals = mod.get("vals", {})
                mopt  = mod.get("opt_vals", {})
                mitem = self._effects_lu.get(mid, {})
                mtext = render_effect(mitem, mvals, mopt, fallback_id=mid)
                mrow  = tk.Frame(parent, bg="#181408")
                mrow.pack(fill="x", padx=inner_pad + 16, pady=0)
                tk.Label(mrow, text=f"  + {mid} \u2192  {mtext}",
                         bg="#181408", fg="#ccaa77",
                         font=("Consolas", 8)).pack(side="left", padx=4)

    def _open_content_editor(self, item_id: str, type_name: str):
        lookup = {
            "Effect":    self._effects_lu,
            "Cost":      self._costs_lu,
            "Trigger":   self._triggers_lu,
            "Condition": self._conditions_lu,
        }
        item = lookup.get(type_name, {}).get(item_id)
        if not item:
            return
        from CardContent.content_editor import ContentEditor
        ContentEditor(self.winfo_toplevel(), item, self._content_data,
                      on_save=self._refresh_content_and_recalculate)

    def _refresh_content_and_recalculate(self):
        _save_content_data(self._content_data)
        self._content_data  = _load_content_data()
        self._effects_lu    = list_to_lookup(self._content_data.get("Effect",    []))
        self._costs_lu      = list_to_lookup(self._content_data.get("Cost",      []))
        self._triggers_lu   = list_to_lookup(self._content_data.get("Trigger",   []))
        self._conditions_lu = list_to_lookup(self._content_data.get("Condition", []))
        for card in self._cards:
            self._recompute_card(card)
        save_random_cards(self._cards, self._current_profile)
        self._refresh_list()
        sel = self._card_lb.curselection()
        if sel:
            vis_idx = sel[0]
            if 0 <= vis_idx < len(self._visible_indices):
                self._show_detail(self._cards[self._visible_indices[vis_idx]])

    def _recompute_card(self, card: dict):
        card["_cv"] = round(cv_card(card, self._box_config,
                                    self._effects_lu, self._costs_lu), 3)
        card["_complexity"] = round(complexity_card(card, self._effects_lu,
                                                    self._costs_lu), 3)

    def _reload_containers(self):
        self._containers = _load_containers()
        self._content_probs = load_content_probs()

    def _open_ingredient_editor(self):
        from card_builder.ingredient_editor import IngredientEditor
        IngredientEditor(self.winfo_toplevel())

    # ── Inline editing ───────────────────────────────────────────────────────

    def _inline_edit_var(self, btn, card, data_dict, key, item_id, type_name):
        import re
        btn.pack_forget()
        parent = btn.master
        var = tk.StringVar(value=str(data_dict.get("vals", {}).get(key, 0)))
        ent = tk.Entry(parent, textvariable=var, width=8,
                       bg="#2a3a2a", fg="white", font=("Consolas", 7),
                       insertbackground="white")
        ent.pack(side="left", padx=2)
        ent.focus_set()
        ent.select_range(0, "end")

        def _commit(_=None):
            try:
                new_val = int(var.get())
            except ValueError:
                try:
                    new_val = int(float(var.get()))
                except ValueError:
                    return
            data_dict.setdefault("vals", {})[key] = new_val
            self._recompute_card(card)
            save_random_cards(self._cards, self._current_profile)
            self._refresh_list()
            self._show_detail(card)

        ent.bind("<Return>",   _commit)
        ent.bind("<FocusOut>", _commit)
        ent.bind("<Escape>",   lambda _: self._show_detail(card))

    def _inline_edit_opt(self, btn, card, data_dict, opt_key, item_id, type_name):
        import re
        btn.pack_forget()
        parent = btn.master
        lu = self._effects_lu if type_name == "Effect" else self._costs_lu
        item = lu.get(item_id, {})
        cb_text = item.get("sigil", "")
        opt_lists = [[c.strip() for c in m.split(",")]
                     for m in re.findall(r'\[([^\]]+)\]', cb_text)]
        try:
            idx = int(opt_key)
            choices = opt_lists[idx] if idx < len(opt_lists) else []
        except (ValueError, IndexError):
            choices = []

        current = data_dict.get("opt_vals", {}).get(str(opt_key),
                  choices[0] if choices else "")
        var = tk.StringVar(value=current)
        cb = ttk.Combobox(parent, textvariable=var,
                          values=choices, width=12,
                          font=("Consolas", 7), state="readonly")
        cb.pack(side="left", padx=2)
        cb.focus_set()

        def _commit(_=None):
            data_dict.setdefault("opt_vals", {})[str(opt_key)] = var.get()
            self._recompute_card(card)
            save_random_cards(self._cards, self._current_profile)
            self._refresh_list()
            self._show_detail(card)

        cb.bind("<<ComboboxSelected>>", _commit)
        cb.bind("<FocusOut>",           _commit)
        cb.bind("<Escape>",             lambda _: self._show_detail(card))

    # ── Config management ────────────────────────────────────────────────────

    def _do_autosave(self):
        cfg = self._settings_panel.collect_config()
        save_gen_config(cfg, self._current_profile)
        self._gen_config = cfg

    def _save_config(self):
        cfg = self._settings_panel.collect_config()
        save_gen_config(cfg, self._current_profile)
        save_random_cards(self._cards, self._current_profile)
        self._gen_config = cfg
        self._settings_panel.set_status("✓ Einstellungen gespeichert", "#1a6e3c")

    def _generate(self):
        cfg = self._settings_panel.collect_config()
        count = cfg.get("count", 10)
        print(f"[generate] Profil={self._current_profile}, Anzahl={count}")
        self._settings_panel.set_status(f"Generiere {count} Karten ...", "#1a3e8e")
        self.update_idletasks()

        # Reload live data
        self._content_data  = _load_content_data()
        self._effects_lu    = list_to_lookup(self._content_data.get("Effect",    []))
        self._costs_lu      = list_to_lookup(self._content_data.get("Cost",      []))
        self._triggers_lu   = list_to_lookup(self._content_data.get("Trigger",   []))
        self._conditions_lu = list_to_lookup(self._content_data.get("Condition", []))
        self._containers    = _load_containers()
        self._box_config    = load_box_config()

        gen = CardGenerator(self._content_data, self._containers,
                            self._box_config, cfg)
        new_cards = gen.generate(count)
        print(f"[generate] {len(new_cards)}/{count} Karten generiert")
        self._cards.extend(new_cards)
        save_random_cards(self._cards, self._current_profile)

        self._refresh_list()
        self._settings_panel.set_status(
            f"✓ {len(new_cards)} Karten generiert. Gesamt: {len(self._cards)}", "#1a6e3c")

    # ── Dialogs ──────────────────────────────────────────────────────────────

    def _open_effects_picker_for_rule(self, rule: dict, rebuild_callback=None):
        all_effect_ids = sorted(
            item["id"] for item in self._content_data.get("Effect", []) if "id" in item
        )
        if not all_effect_ids:
            return

        top = tk.Toplevel(self.winfo_toplevel())
        top.title("Effekte für Regel auswählen")
        top.configure(bg="#1a1a1a")
        top.grab_set()

        tk.Label(top, text="Effekte wählen (Strg+Klick für Mehrfachauswahl):",
                 bg="#1a1a1a", fg="#ccc", font=("Arial", 9)).pack(padx=10, pady=(8, 2))

        lb = tk.Listbox(top, selectmode="multiple", bg="#2a2a2a", fg="white",
                        font=("Consolas", 9), height=min(20, len(all_effect_ids) + 2),
                        width=36, activestyle="dotbox",
                        selectbackground="#1a4a1a", selectforeground="#88ff88")
        lb.pack(padx=10, pady=4)

        current = set(rule.get("effects", []))
        for eid in all_effect_ids:
            lb.insert("end", eid)
            if eid in current:
                lb.selection_set(lb.size() - 1)

        btn_row = tk.Frame(top, bg="#1a1a1a")
        btn_row.pack(pady=(2, 8))

        def _ok():
            sel = [all_effect_ids[i] for i in lb.curselection()]
            rule["effects"] = sel
            rule.pop("container", None)
            if rebuild_callback:
                rebuild_callback()
            top.destroy()

        tk.Button(btn_row, text="✓ OK", command=_ok,
                  bg="#1a4a1a", fg="#88ff88",
                  font=("Arial", 9, "bold"), cursor="hand2",
                  width=10).pack(side="left", padx=4)
        tk.Button(btn_row, text="Abbrechen", command=top.destroy,
                  bg="#2a2a2a", fg="#aaa",
                  font=("Arial", 9), cursor="hand2",
                  width=10).pack(side="left", padx=4)

        top.bind("<Return>", lambda e: _ok())
        top.bind("<Escape>", lambda e: top.destroy())

    def _pick_effect_id(self) -> str:
        all_ids = (
            [item["id"] for item in self._content_data.get("Effect", [])] +
            [item["id"] for item in self._content_data.get("Cost",   [])]
        )
        if not all_ids:
            return ""
        top = tk.Toplevel(self.winfo_toplevel())
        top.title("Effekt/Cost auswählen")
        top.configure(bg="#1a1a1a")
        top.grab_set()
        result = [""]
        lb = tk.Listbox(top, bg="#2a2a2a", fg="white",
                        font=("Consolas", 9), height=20, width=36)
        lb.pack(padx=8, pady=8)
        for iid in sorted(all_ids):
            lb.insert("end", iid)

        def _ok():
            sel = lb.curselection()
            if sel:
                result[0] = lb.get(sel[0])
            top.destroy()

        tk.Button(top, text="OK", command=_ok,
                  bg="#1a6e3c", fg="white", font=("Arial", 9)).pack(pady=(0, 8))
        top.wait_window()
        return result[0]
