"""
random_builder/app.py – Random Spell Card Builder panel.

Layout (3 columns):
  ┌─────────────────┬──────────────────────────┬────────────────────────────┐
  │  EINSTELLUNGEN  │  GENERIERTE KARTEN        │  KARTEN DETAIL             │
  │  (links, 280px) │  (mitte, 300px)           │  (rechts, expandiert)      │
  └─────────────────┴──────────────────────────┴────────────────────────────┘
"""

import json
import os
import random
import tkinter as tk
from tkinter import ttk, messagebox

from .models import (
    load_random_cards, save_random_cards, clear_random_cards,
    load_gen_config, save_gen_config,
    load_box_config, save_box_config,
    load_content_probs, save_content_probs,
    GENERATOR_PROFILES, RECIPE_TYPES,
)
from .generator import CardGenerator, ELEMENTS
from .cv_calc import cv_card, complexity_card
from .generator import _list_to_lookup

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_content_data() -> dict:
    """Load all cc_data JSON files and merge into one dict."""
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
    """Write all cc_data back to their JSON files."""
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
    """One-line summary for the card list."""
    el  = card.get("recipe_type") or card.get("element") or "?"
    cv  = card.get("_cv", "?")
    cmx = card.get("_complexity", "?")
    if card.get("ingredients") is not None:
        ni = len(card.get("ingredients", []))
        return f"{el:<10}  CV={cv:<6}  Cmplx={cmx:<5}  Zutaten={ni}"
    nb  = len(card.get("blocks", []))
    return f"{el:<10}  CV={cv:<6}  Cmplx={cmx:<5}  Sigils={nb}"


# ── Main panel ────────────────────────────────────────────────────────────────

class RandomBuilder(tk.Frame):

    def __init__(self, parent, **kw):
        kw.setdefault("bg", "#1a1a1a")
        super().__init__(parent, **kw)
        self._content_data   = _load_content_data()
        self._effects_lu     = _list_to_lookup(self._content_data.get("Effect",    []))
        self._costs_lu       = _list_to_lookup(self._content_data.get("Cost",      []))
        self._triggers_lu    = _list_to_lookup(self._content_data.get("Trigger",   []))
        self._conditions_lu  = _list_to_lookup(self._content_data.get("Condition", []))
        self._containers     = _load_containers()
        self._current_profile = "Spells"
        self._content_probs = load_content_probs()
        self._box_config    = load_box_config()
        self._gen_config    = load_gen_config(self._current_profile)
        self._cards: list   = load_random_cards(self._current_profile)
        self._selected_idx  = None
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Left settings panel ───────────────────────────────────────────────
        left = tk.Frame(self, bg="#1a1a1a", width=290)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        self._settings_parent = left

        ttk.Separator(self, orient="vertical").pack(side="left", fill="y")

        # ── Center card list ──────────────────────────────────────────────────
        center = tk.Frame(self, bg="#1a1a1a", width=340)
        center.pack(side="left", fill="y")
        center.pack_propagate(False)

        ttk.Separator(self, orient="vertical").pack(side="left", fill="y")

        # ── Right detail view ─────────────────────────────────────────────────
        right = tk.Frame(self, bg="#1a1a1a")
        right.pack(side="left", fill="both", expand=True)

        self._build_settings(left)
        self._build_card_list(center)
        self._build_detail(right)

    # ══════════════════════════════════════════════════════════════════════════
    # LEFT – Settings
    # ══════════════════════════════════════════════════════════════════════════

    def _build_settings(self, parent):
        # ── Profile bar ───────────────────────────────────────────────────────
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

        outer = tk.Frame(parent, bg="#1a1a1a")
        outer.pack(fill="both", expand=True)

        # Scrollable
        vsb = tk.Scrollbar(outer, orient="vertical")
        vsb.pack(side="right", fill="y")
        canvas = tk.Canvas(outer, yscrollcommand=vsb.set,
                           bg="#1a1a1a", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        vsb.config(command=canvas.yview)
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        f = tk.Frame(canvas, bg="#1a1a1a")
        win = canvas.create_window((0, 0), window=f, anchor="nw")
        f.bind("<Configure>",
               lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win, width=e.width))

        pad = {"padx": 8, "pady": 2}

        # Title
        tk.Label(f, text="🎲 Random Builder",
                 bg="#1a1a1a", fg="#cc8833",
                 font=("Palatino Linotype", 12, "bold")).pack(anchor="w", **pad)

        self._sep(f)

        # ── Anzahl ────────────────────────────────────────────────────────────
        tk.Label(f, text="Anzahl Karten:", bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(anchor="w", **pad)
        self._count_var = tk.IntVar(value=self._gen_config.get("count", 10))
        self._count_var.trace_add("write", self._schedule_autosave)
        tk.Spinbox(f, from_=1, to=500, textvariable=self._count_var,
                   width=8, bg="#2a2a2a", fg="white",
                   buttonbackground="#333").pack(anchor="w", **pad)

        self._sep(f)

        # ── Element / Recipe Type Verteilung ─────────────────────────────────
        _is_recipes = (self._current_profile == "Recipes")
        _is_prowess = (self._current_profile == "Prowess")

        if _is_prowess:
            # Prowess has no elements or subcategories — skip this section
            pass
        elif not _is_recipes:
            tk.Label(f, text="Element Verteilung:", bg="#1a1a1a", fg="#aaa",
                     font=("Arial", 9, "bold")).pack(anchor="w", **pad)
            self._el_mode_var = tk.StringVar(
                value=self._gen_config.get("element_mode", "equal"))
            self._el_mode_var.trace_add("write", self._schedule_autosave)
            for val, lbl in [("equal", "Alle gleich"), ("custom", "Eigene Gewichte")]:
                tk.Radiobutton(f, text=lbl, variable=self._el_mode_var, value=val,
                               bg="#1a1a1a", fg="#ccc", selectcolor="#2a2a3a",
                               activebackground="#1a1a2a",
                               command=self._toggle_el_weights).pack(
                    anchor="w", padx=16)

            self._el_weights_frame = tk.Frame(f, bg="#1a1a1a")
            self._el_weights_frame.pack(fill="x", **pad)
            self._el_weight_vars = {}
            for el in ELEMENTS:
                row = tk.Frame(self._el_weights_frame, bg="#1a1a1a")
                row.pack(fill="x", pady=1)
                tk.Label(row, text=el, bg="#1a1a1a", fg="#888",
                         width=8, anchor="w", font=("Arial", 8)).pack(side="left")
                v = tk.StringVar(value=str(
                    self._gen_config.get("custom_element_weights", {}).get(el, 10)))
                v.trace_add("write", self._schedule_autosave)
                self._el_weight_vars[el] = v
                tk.Entry(row, textvariable=v, width=6,
                         bg="#2a2a2a", fg="white").pack(side="left", padx=2)
            self._toggle_el_weights()
        else:
            tk.Label(f, text="Recipe Type Verteilung:", bg="#1a1a1a", fg="#aaa",
                     font=("Arial", 9, "bold")).pack(anchor="w", **pad)
            self._rt_mode_var = tk.StringVar(
                value=self._gen_config.get("recipe_type_mode", "equal"))
            self._rt_mode_var.trace_add("write", self._schedule_autosave)
            for val, lbl in [("equal", "Alle gleich"), ("custom", "Eigene Gewichte")]:
                tk.Radiobutton(f, text=lbl, variable=self._rt_mode_var, value=val,
                               bg="#1a1a1a", fg="#ccc", selectcolor="#2a2a3a",
                               activebackground="#1a1a2a",
                               command=self._toggle_rt_weights).pack(
                    anchor="w", padx=16)

            self._rt_weights_frame = tk.Frame(f, bg="#1a1a1a")
            self._rt_weights_frame.pack(fill="x", **pad)
            self._rt_weight_vars = {}
            for rt in RECIPE_TYPES:
                row = tk.Frame(self._rt_weights_frame, bg="#1a1a1a")
                row.pack(fill="x", pady=1)
                tk.Label(row, text=rt, bg="#1a1a1a", fg="#888",
                         width=10, anchor="w", font=("Arial", 8)).pack(side="left")
                v = tk.StringVar(value=str(
                    self._gen_config.get("recipe_type_weights", {}).get(rt, 10)))
                v.trace_add("write", self._schedule_autosave)
                self._rt_weight_vars[rt] = v
                tk.Entry(row, textvariable=v, width=6,
                         bg="#2a2a2a", fg="white").pack(side="left", padx=2)
            self._toggle_rt_weights()

        self._sep(f)

        # ── Block Regeln ──────────────────────────────────────────────────────
        tk.Label(f, text="Sigil Regeln  (Wahrscheinlichkeit):",
                 bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(anchor="w", **pad)
        tk.Label(f, text="Wie oft erscheint jedes Sigil auf einer Karte?",
                 bg="#1a1a1a", fg="#555", font=("Arial", 7, "italic")).pack(
            anchor="w", padx=16)

        self._block_rule_vars = {}
        block_rules = {r["block_type"]: r["probability"]
                       for r in self._gen_config.get("block_rules", [])}
        from card_builder.constants import BOX_TYPES as BLOCK_TYPES
        for bt in BLOCK_TYPES:
            row = tk.Frame(f, bg="#1a1a1a")
            row.pack(fill="x", padx=12, pady=1)
            tk.Label(row, text=bt, bg="#1a1a1a", fg="#ccc",
                     width=13, anchor="w", font=("Arial", 8)).pack(side="left")
            v = tk.StringVar(value=str(block_rules.get(bt, 0.0)))
            v.trace_add("write", self._schedule_autosave)
            self._block_rule_vars[bt] = v
            tk.Entry(row, textvariable=v, width=6,
                     bg="#2a2a2a", fg="white", font=("Arial", 8)).pack(
                side="left", padx=2)

        self._sep(f)

        # ── Content Regeln (Containers) ───────────────────────────────────────
        tk.Label(f, text="Content Regeln  (Container → %):",
                 bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(anchor="w", **pad)
        tk.Label(f, text="Wie oft soll ein Effekt aus diesem Container erscheinen?",
                 bg="#1a1a1a", fg="#555", font=("Arial", 7, "italic")).pack(
            anchor="w", padx=16)

        self._content_rules_frame = tk.Frame(f, bg="#1a1a1a")
        self._content_rules_frame.pack(fill="x", **pad)
        self._content_rule_vars = {}
        self._rebuild_content_rules()

        tk.Button(f, text="↺ Container neu laden",
                  command=self._reload_containers,
                  bg="#2a2a2a", fg="#aaa",
                  font=("Arial", 8)).pack(anchor="w", padx=12, pady=2)

        self._sep(f)

        # ── Kosten Regeln ─────────────────────────────────────────────────────
        tk.Label(f, text="Kosten Regeln  (Cost-ID → %):",
                 bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(anchor="w", **pad)
        tk.Label(f, text="Wie oft soll dieser Cost auf der Karte sein?",
                 bg="#1a1a1a", fg="#555", font=("Arial", 7, "italic")).pack(
            anchor="w", padx=16)

        self._cost_rules_frame = tk.Frame(f, bg="#1a1a1a")
        self._cost_rules_frame.pack(fill="x", **pad)
        self._cost_rule_vars = {}
        self._rebuild_cost_rules()

        self._sep(f)

        # ── CV Ziel ───────────────────────────────────────────────────────────
        tk.Label(f, text="CV Ziel:", bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(anchor="w", **pad)
        cv_row = tk.Frame(f, bg="#1a1a1a")
        cv_row.pack(fill="x", padx=12, pady=2)
        tk.Label(cv_row, text="Karte ≥", bg="#1a1a1a", fg="#888",
                 font=("Arial", 8)).pack(side="left")
        self._cv_min_var = tk.StringVar(
            value=str(self._gen_config.get("cv_card_min", -999.0)))
        self._cv_min_var.trace_add("write", self._schedule_autosave)
        tk.Entry(cv_row, textvariable=self._cv_min_var, width=5,
                 bg="#2a2a2a", fg="white").pack(side="left", padx=4)
        tk.Label(cv_row, text="≤", bg="#1a1a1a", fg="#888",
                 font=("Arial", 8)).pack(side="left")
        self._cv_target_var = tk.StringVar(
            value=str(self._gen_config.get("cv_target", 3.0)))
        self._cv_target_var.trace_add("write", self._schedule_autosave)
        tk.Entry(cv_row, textvariable=self._cv_target_var, width=5,
                 bg="#2a2a2a", fg="white").pack(side="left", padx=4)
        tk.Label(cv_row, text="  Sigil ≤", bg="#1a1a1a", fg="#888",
                 font=("Arial", 8)).pack(side="left", padx=(4, 0))
        self._cv_box_var = tk.StringVar(
            value=str(self._gen_config.get("cv_per_box_max", 3.0)))
        self._cv_box_var.trace_add("write", self._schedule_autosave)
        tk.Entry(cv_row, textvariable=self._cv_box_var, width=5,
                 bg="#2a2a2a", fg="white").pack(side="left", padx=4)

        self._sep(f)

        # ── Kosten Limits ─────────────────────────────────────────────────────
        tk.Label(f, text="Kosten Limits:", bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(anchor="w", **pad)
        tk.Label(f, text="Mana ist unabhängig von anderen Kosten",
                 bg="#1a1a1a", fg="#555", font=("Arial", 7, "italic")).pack(
            anchor="w", padx=16)

        # Mana Chance
        mana_row = tk.Frame(f, bg="#1a1a1a")
        mana_row.pack(fill="x", padx=12, pady=2)
        tk.Label(mana_row, text="Mana Chance", bg="#1a1a1a", fg="#ccc",
                 width=16, anchor="w", font=("Arial", 8)).pack(side="left")
        self._mana_chance_var = tk.StringVar(
            value=str(self._gen_config.get("mana_chance", 0.95)))
        self._mana_chance_var.trace_add("write", self._schedule_autosave)
        tk.Entry(mana_row, textvariable=self._mana_chance_var, width=6,
                 bg="#2a2a2a", fg="white", font=("Arial", 8)).pack(side="left", padx=2)
        tk.Label(mana_row, text="(0–1)", bg="#1a1a1a", fg="#555",
                 font=("Arial", 7)).pack(side="left", padx=2)

        # Mana Hauptwert (peak of distribution)
        mana_main_row = tk.Frame(f, bg="#1a1a1a")
        mana_main_row.pack(fill="x", padx=12, pady=2)
        tk.Label(mana_main_row, text="Mana Hauptwert", bg="#1a1a1a", fg="#ccc",
                 width=16, anchor="w", font=("Arial", 8)).pack(side="left")
        self._mana_main_var = tk.StringVar(
            value=str(self._gen_config.get("mana_main_count", 2)))
        self._mana_main_var.trace_add("write", self._schedule_autosave)
        tk.Spinbox(mana_main_row, from_=0, to=10, textvariable=self._mana_main_var,
                   width=5, bg="#2a2a2a", fg="white",
                   buttonbackground="#333", font=("Arial", 8)).pack(side="left", padx=2)
        tk.Label(mana_main_row, text="(häufigster Wert)", bg="#1a1a1a", fg="#555",
                 font=("Arial", 7)).pack(side="left", padx=2)

        # Mana max Anzahl (hard cap)
        mana_max_row = tk.Frame(f, bg="#1a1a1a")
        mana_max_row.pack(fill="x", padx=12, pady=2)
        tk.Label(mana_max_row, text="Mana max Anzahl", bg="#1a1a1a", fg="#ccc",
                 width=16, anchor="w", font=("Arial", 8)).pack(side="left")
        self._mana_max_var = tk.StringVar(
            value=str(self._gen_config.get("mana_max_count", 6)))
        self._mana_max_var.trace_add("write", self._schedule_autosave)
        tk.Spinbox(mana_max_row, from_=1, to=10, textvariable=self._mana_max_var,
                   width=5, bg="#2a2a2a", fg="white",
                   buttonbackground="#333", font=("Arial", 8)).pack(side="left", padx=2)
        tk.Label(mana_max_row, text="Kreise (max)", bg="#1a1a1a", fg="#555",
                 font=("Arial", 7)).pack(side="left", padx=2)

        # Andere Kosten max
        other_row = tk.Frame(f, bg="#1a1a1a")
        other_row.pack(fill="x", padx=12, pady=2)
        tk.Label(other_row, text="Andere Kosten max", bg="#1a1a1a", fg="#ccc",
                 width=16, anchor="w", font=("Arial", 8)).pack(side="left")
        self._max_other_costs_var = tk.StringVar(
            value=str(self._gen_config.get("max_other_costs", 1)))
        self._max_other_costs_var.trace_add("write", self._schedule_autosave)
        tk.Spinbox(other_row, from_=0, to=10, textvariable=self._max_other_costs_var,
                   width=5, bg="#2a2a2a", fg="white",
                   buttonbackground="#333", font=("Arial", 8)).pack(side="left", padx=2)
        tk.Label(other_row, text="verschiedene", bg="#1a1a1a", fg="#555",
                 font=("Arial", 7)).pack(side="left", padx=2)

        # Effekte max
        eff_row = tk.Frame(f, bg="#1a1a1a")
        eff_row.pack(fill="x", padx=12, pady=2)
        tk.Label(eff_row, text="Effekte max", bg="#1a1a1a", fg="#ccc",
                 width=16, anchor="w", font=("Arial", 8)).pack(side="left")
        self._max_effects_var = tk.StringVar(
            value=str(self._gen_config.get("max_effects", -1)))
        self._max_effects_var.trace_add("write", self._schedule_autosave)
        tk.Spinbox(eff_row, from_=-1, to=50, textvariable=self._max_effects_var,
                   width=5, bg="#2a2a2a", fg="white",
                   buttonbackground="#333", font=("Arial", 8)).pack(side="left", padx=2)
        tk.Label(eff_row, text="(-1 = unbegrenzt)", bg="#1a1a1a", fg="#555",
                 font=("Arial", 7)).pack(side="left", padx=2)

        # Effekte min
        eff_min_row = tk.Frame(f, bg="#1a1a1a")
        eff_min_row.pack(fill="x", padx=12, pady=2)
        tk.Label(eff_min_row, text="Effekte min", bg="#1a1a1a", fg="#ccc",
                 width=16, anchor="w", font=("Arial", 8)).pack(side="left")
        self._min_effects_var = tk.StringVar(
            value=str(self._gen_config.get("min_effects", 0)))
        self._min_effects_var.trace_add("write", self._schedule_autosave)
        tk.Spinbox(eff_min_row, from_=0, to=50, textvariable=self._min_effects_var,
                   width=5, bg="#2a2a2a", fg="white",
                   buttonbackground="#333", font=("Arial", 8)).pack(side="left", padx=2)

        # Sigils min
        sig_min_row = tk.Frame(f, bg="#1a1a1a")
        sig_min_row.pack(fill="x", padx=12, pady=2)
        tk.Label(sig_min_row, text="Sigils min", bg="#1a1a1a", fg="#ccc",
                 width=16, anchor="w", font=("Arial", 8)).pack(side="left")
        self._min_blocks_var = tk.StringVar(
            value=str(self._gen_config.get("min_blocks", 1)))
        self._min_blocks_var.trace_add("write", self._schedule_autosave)
        tk.Spinbox(sig_min_row, from_=1, to=4, textvariable=self._min_blocks_var,
                   width=5, bg="#2a2a2a", fg="white",
                   buttonbackground="#333", font=("Arial", 8)).pack(side="left", padx=2)
        tk.Label(sig_min_row, text="(1–4)", bg="#1a1a1a", fg="#555",
                 font=("Arial", 7)).pack(side="left", padx=2)

        # Condition Chance
        cond_row = tk.Frame(f, bg="#1a1a1a")
        cond_row.pack(fill="x", padx=12, pady=2)
        tk.Label(cond_row, text="Condition Chance", bg="#1a1a1a", fg="#ccc",
                 width=16, anchor="w", font=("Arial", 8)).pack(side="left")
        self._cond_chance_var = tk.StringVar(
            value=str(self._gen_config.get("condition_chance", 0.15)))
        self._cond_chance_var.trace_add("write", self._schedule_autosave)
        tk.Entry(cond_row, textvariable=self._cond_chance_var, width=6,
                 bg="#2a2a2a", fg="white", font=("Arial", 8)).pack(side="left", padx=2)

        # Choose N Chance
        choose_row = tk.Frame(f, bg="#1a1a1a")
        choose_row.pack(fill="x", padx=12, pady=2)
        tk.Label(choose_row, text="Choose N Chance", bg="#1a1a1a", fg="#ccc",
                 width=16, anchor="w", font=("Arial", 8)).pack(side="left")
        self._choose_chance_var = tk.StringVar(
            value=str(self._gen_config.get("choose_n_chance", 0.10)))
        self._choose_chance_var.trace_add("write", self._schedule_autosave)
        tk.Entry(choose_row, textvariable=self._choose_chance_var, width=6,
                 bg="#2a2a2a", fg="white", font=("Arial", 8)).pack(side="left", padx=2)
        tk.Label(choose_row, text="(0–1)", bg="#1a1a1a", fg="#555",
                 font=("Arial", 7)).pack(side="left", padx=2)

        self._sep(f)

        # ── Sigil Regeln ──────────────────────────────────────────────────────
        tk.Label(f, text="Sigil Regeln:", bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(anchor="w", **pad)

        self._sigil_rules_data = {
            bt: [dict(r) for r in rules]
            for bt, rules in self._gen_config.get("sigil_rules", {}).items()
        }
        self._incompatible_pairs = [list(p)
                                    for p in self._gen_config.get("incompatible_pairs", [])]

        # Block types from box_config or block_rules
        box_cfg = self._box_config if self._box_config else {}
        bt_names = sorted(box_cfg.keys()) if box_cfg else [
            r["block_type"] for r in self._gen_config.get("block_rules", [])
            if r.get("block_type")
        ]
        if not bt_names:
            bt_names = ["Play", "Hand", "Lost", "Discard", "Forgotten",
                        "Concentration", "Excavate", "Enchantment",
                        "Equipped", "Exhausted"]

        # Sigil selector + Add button
        self._sigil_rules_var = tk.StringVar(value=bt_names[0] if bt_names else "")
        sig_ctrl_row = tk.Frame(f, bg="#1a1a1a")
        sig_ctrl_row.pack(fill="x", padx=8, pady=2)
        sig_cb = ttk.Combobox(sig_ctrl_row, textvariable=self._sigil_rules_var,
                               values=bt_names, state="readonly", width=12)
        sig_cb.pack(side="left")
        sig_cb.bind("<<ComboboxSelected>>", lambda _: self._rebuild_sigil_rules_panel())
        tk.Button(sig_ctrl_row, text="+ Regel", font=("Arial", 8),
                  bg="#1a3a1a", fg="#88ff88", cursor="hand2",
                  command=self._add_sigil_rule).pack(side="left", padx=4)

        # Rules panel (inner frame refreshed per sigil)
        rules_border = tk.Frame(f, bg="#333", bd=1, relief="sunken")
        rules_border.pack(fill="x", padx=8, pady=2)
        self._sigil_rules_inner = tk.Frame(rules_border, bg="#1a1a1a")
        self._sigil_rules_inner.pack(fill="x", padx=1, pady=1)

        # Incompatible pairs
        tk.Label(f, text="Unverträgliche Paare:",
                 bg="#1a1a1a", fg="#ffcc44", font=("Arial", 8)).pack(
            anchor="w", padx=12, pady=(6, 0))
        self._incompat_frame = tk.Frame(f, bg="#1a1a1a")
        self._incompat_frame.pack(fill="x", padx=12, pady=1)
        self._incompat_lb = tk.Listbox(self._incompat_frame, height=3,
                                        bg="#2a2a1a", fg="#ffcc44",
                                        selectbackground="#5a5a2a",
                                        font=("Consolas", 8))
        self._incompat_lb.pack(side="left", fill="x", expand=True)
        ic_btn_f = tk.Frame(self._incompat_frame, bg="#1a1a1a")
        ic_btn_f.pack(side="left", padx=2)
        tk.Button(ic_btn_f, text="+", width=2, font=("Arial", 8),
                  bg="#2a2a2a", fg="#aaa", cursor="hand2",
                  command=self._add_incompat_pair).pack()
        tk.Button(ic_btn_f, text="✕", width=2, font=("Arial", 8),
                  bg="#2a2a2a", fg="#aaa", cursor="hand2",
                  command=self._remove_incompat_pair).pack(pady=1)

        for pair in self._incompatible_pairs:
            self._incompat_lb.insert("end", f"{pair[0]}  ↔  {pair[1]}")

        self._rebuild_sigil_rules_panel()

        self._sep(f)

        # ── Action buttons ────────────────────────────────────────────────────
        tk.Button(f, text="🎲  Karten generieren!",
                  command=self._generate,
                  bg="#1a6e3c", fg="white",
                  font=("Arial", 11, "bold"),
                  cursor="hand2").pack(fill="x", padx=8, pady=4)

        tk.Button(f, text="💾  Einstellungen speichern",
                  command=self._save_config,
                  bg="#2a2a3a", fg="#aaa",
                  font=("Arial", 8)).pack(fill="x", padx=8, pady=2)

        self._status = tk.Label(f, text="", bg="#1a1a1a", fg="#aaa",
                                font=("Arial", 8), wraplength=260)
        self._status.pack(padx=8, pady=4)

        # Ensure profile button styles are current after (re)build
        self._update_profile_btn_styles()

    def _sep(self, parent):
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=6)

    # ── Profile management ────────────────────────────────────────────────────

    def _update_profile_btn_styles(self):
        for p, btn in self._profile_btns.items():
            if p == self._current_profile:
                btn.config(bg="#1a6e3c", fg="white")
            else:
                btn.config(bg="#2a2a2a", fg="#888")

    def _switch_profile(self, name: str):
        if name == self._current_profile:
            return
        # Save current profile state
        cfg = self._collect_config()
        save_gen_config(cfg, self._current_profile)
        save_random_cards(self._cards, self._current_profile)
        # Switch to new profile
        self._current_profile = name
        self._gen_config = load_gen_config(name)
        self._cards = load_random_cards(name)
        self._content_probs = load_content_probs()
        # Rebuild settings panel
        for w in self._settings_parent.winfo_children():
            w.destroy()
        self._build_settings(self._settings_parent)
        self._refresh_list()
        if self._selected_idx is not None:
            self._selected_idx = None
            self._clear_detail()

    def _toggle_el_weights(self):
        state = "normal" if self._el_mode_var.get() == "custom" else "disabled"
        for w in self._el_weights_frame.winfo_children():
            for ww in w.winfo_children():
                try:
                    ww.config(state=state)
                except Exception:
                    pass

    def _toggle_rt_weights(self):
        state = "normal" if self._rt_mode_var.get() == "custom" else "disabled"
        for w in self._rt_weights_frame.winfo_children():
            for ww in w.winfo_children():
                try:
                    ww.config(state=state)
                except Exception:
                    pass

    def _rebuild_content_rules(self):
        for w in self._content_rules_frame.winfo_children():
            w.destroy()
        self._content_rule_vars = {}   # key → StringVar
        self._content_rule_types = {}  # key → "container" | "effect" | ...

        # Saved probs: first from content_probs.json, then fall back to gen_config
        saved_probs = {}
        for r in self._gen_config.get("content_rules", []):
            if "container" in r:
                saved_probs[r["container"]] = r["probability"]
            elif "effect_id" in r:
                saved_probs[r["effect_id"]] = r["probability"]
        saved_probs.update(self._content_probs)  # content_probs.json overrides

        # ── Containers ────────────────────────────────────────────────────────
        if self._containers:
            tk.Label(self._content_rules_frame, text="Container:",
                     bg="#1a1a1a", fg="#888",
                     font=("Arial", 7, "bold italic")).pack(anchor="w", padx=2)
            for cid in sorted(self._containers.keys()):
                # Default = 1.0 (equal) if not customised
                self._add_rule_row(self._content_rules_frame, cid,
                                   saved_probs.get(cid, 1.0), kind="container",
                                   fg="#88ccff")

        # ── Ungrouped items (auto-containers) — all content types ─────────────
        _type_cfg = [
            ("Effect",    "effects",    "#88ff88", "effect"),
            ("Cost",      "costs",      "#ffaa44", "cost"),
            ("Condition", "conditions", "#88aaff", "condition"),
            ("Trigger",   "triggers",   "#ff88cc", "trigger"),
        ]
        any_ungrouped = False
        for ctype, list_key, color, kind in _type_cfg:
            in_containers = set()
            for cont in self._containers.values():
                in_containers.update(cont.get(list_key, []))

            all_ids = [item["id"] for item in self._content_data.get(ctype, [])]
            ungrouped = [iid for iid in all_ids if iid not in in_containers]
            if not ungrouped:
                continue
            any_ungrouped = True
            tk.Label(self._content_rules_frame,
                     text=f"Einzelne {ctype}s (kein Container):",
                     bg="#1a1a1a", fg=color,
                     font=("Arial", 7, "bold italic")).pack(
                anchor="w", padx=2, pady=(4, 0))
            for iid in ungrouped:
                self._add_rule_row(self._content_rules_frame, iid,
                                   saved_probs.get(iid, 1.0), kind=kind,
                                   fg="#cccccc")

        if not self._containers and not any_ungrouped:
            tk.Label(self._content_rules_frame,
                     text="Kein Content gefunden. Erst im Content Editor anlegen.",
                     bg="#1a1a1a", fg="#555", font=("Arial", 8)).pack(
                anchor="w", padx=4)

    def _add_rule_row(self, parent, key: str, prob: float,
                      kind: str, fg: str):
        row = tk.Frame(parent, bg="#1a1a1a")
        row.pack(fill="x", pady=1)
        tk.Label(row, text=key, bg="#1a1a1a", fg=fg,
                 width=18, anchor="w", font=("Arial", 8)).pack(side="left")
        v = tk.StringVar(value=str(prob))
        self._content_rule_vars[key]  = v
        self._content_rule_types[key] = kind

        def _on_prob_change(*_, k=key, var=v):
            try:
                self._content_probs[k] = float(var.get())
                save_content_probs(self._content_probs)
            except ValueError:
                pass

        v.trace_add("write", _on_prob_change)
        v.trace_add("write", self._schedule_autosave)
        tk.Entry(row, textvariable=v, width=6,
                 bg="#2a2a2a", fg="white", font=("Arial", 8)).pack(
            side="left", padx=2)

    def _rebuild_cost_rules(self):
        for w in self._cost_rules_frame.winfo_children():
            w.destroy()
        self._cost_rule_vars = {}

        rules = {r["cost_id"]: r["probability"]
                 for r in self._gen_config.get("cost_rules", [])}

        cost_ids = [item["id"] for item in self._content_data.get("Cost", [])]
        if not cost_ids:
            tk.Label(self._cost_rules_frame,
                     text="Keine Costs. Erst im Content Editor anlegen.",
                     bg="#1a1a1a", fg="#555", font=("Arial", 8)).pack(
                anchor="w", padx=4)
            return

        for cid in cost_ids:
            row = tk.Frame(self._cost_rules_frame, bg="#1a1a1a")
            row.pack(fill="x", pady=1)
            tk.Label(row, text=cid, bg="#1a1a1a", fg="#ccc",
                     width=16, anchor="w", font=("Arial", 8)).pack(side="left")
            v = tk.StringVar(value=str(rules.get(cid, 0.0)))
            v.trace_add("write", self._schedule_autosave)
            self._cost_rule_vars[cid] = v
            tk.Entry(row, textvariable=v, width=6,
                     bg="#2a2a2a", fg="white", font=("Arial", 8)).pack(
                side="left", padx=2)

    def _reload_containers(self):
        self._containers    = _load_containers()
        self._content_probs = load_content_probs()
        self._rebuild_content_rules()

    # ── Sigil rules helpers ───────────────────────────────────────────────────

    def _rebuild_sigil_rules_panel(self):
        bt = self._sigil_rules_var.get()
        frame = self._sigil_rules_inner
        for w in frame.winfo_children():
            w.destroy()

        rules = self._sigil_rules_data.get(bt, [])
        container_choices = list(self._containers.keys()) if self._containers else []

        if not rules:
            tk.Label(frame, text="Keine Regeln — '+ Regel' klicken.",
                     bg="#1a1a1a", fg="#555", font=("Arial", 8)).pack(
                anchor="w", padx=6, pady=4)
            return

        for idx, rule in enumerate(rules):
            row = tk.Frame(frame, bg="#1e1e2a")
            row.pack(fill="x", padx=2, pady=1)

            # ── Mode: "container" or "effects" ────────────────────────────────
            # Determine current mode from rule keys
            mode = "effects" if "effects" in rule and rule.get("effects") else "container"

            mode_btn_var = tk.StringVar(value=mode)

            # We'll use a holder frame to swap the middle widget when mode changes
            holder = tk.Frame(row, bg="#1e1e2a")

            def _build_holder(holder=holder, rule=rule, idx=idx,
                              mode_btn_var=mode_btn_var, mode_btn_ref=[None]):
                for w in holder.winfo_children():
                    w.destroy()
                m = mode_btn_var.get()
                if m == "container":
                    c_var = tk.StringVar(value=rule.get("container", ""))
                    cb = ttk.Combobox(holder, textvariable=c_var,
                                      values=container_choices, width=13)
                    cb.pack(side="left")
                    def _sync_c(*_, r=rule, cv=c_var):
                        r["container"] = cv.get()
                        r.pop("effects", None)
                        self._schedule_autosave()
                    c_var.trace_add("write", _sync_c)
                else:  # effects mode
                    effs = rule.get("effects", [])
                    lbl_text = f"🎯 {len(effs)} Effekt(e)" if effs else "🎯 Keine"
                    lbl = tk.Label(holder, text=lbl_text,
                                   bg="#1e2a1e", fg="#88ff88",
                                   font=("Arial", 8), cursor="hand2",
                                   width=13, anchor="w", relief="groove")
                    lbl.pack(side="left")
                    lbl.bind("<Button-1>",
                             lambda e, r=rule: self._open_effects_picker_for_rule(r))

            # Mode toggle button
            def _toggle_mode(rule=rule, mv=mode_btn_var,
                             holder=holder, bld=_build_holder,
                             btn_ref=[None]):
                current = mv.get()
                new_mode = "effects" if current == "container" else "container"
                mv.set(new_mode)
                # Migrate data
                if new_mode == "effects":
                    rule.setdefault("effects", [])
                    rule.pop("container", None)
                else:
                    rule.setdefault("container",
                                    container_choices[0] if container_choices else "")
                    rule.pop("effects", None)
                bld()
                # Update button label
                if btn_ref[0]:
                    btn_ref[0].config(
                        text="📦" if new_mode == "container" else "🎯",
                        fg="#88ccff" if new_mode == "container" else "#88ff88",
                    )
                self._schedule_autosave()

            mode_btn = tk.Button(
                row, width=2, font=("Arial", 8), cursor="hand2",
                text="📦" if mode == "container" else "🎯",
                fg="#88ccff" if mode == "container" else "#88ff88",
                bg="#2a2a2a",
                command=_toggle_mode,
            )
            mode_btn.pack(side="left", padx=(2, 0))
            holder.pack(side="left", padx=2)
            _build_holder()
            # Give _toggle_mode access to the button so it can relabel it
            # (we pass btn_ref via closure default mutation)
            _toggle_mode.__defaults__[-1][0] = mode_btn  # btn_ref[0]

            tk.Label(row, text="P:", bg="#1e1e2a", fg="#888",
                     font=("Arial", 7)).pack(side="left")
            p_var = tk.StringVar(value=str(rule.get("probability", 1.0)))
            tk.Entry(row, textvariable=p_var, width=5,
                     bg="#2a2a2a", fg="white", font=("Arial", 8)).pack(side="left")

            tk.Label(row, text="↓", bg="#1e1e2a", fg="#888",
                     font=("Arial", 7)).pack(side="left", padx=(4, 0))
            min_var = tk.StringVar(value=str(rule.get("min", 1)))
            tk.Spinbox(row, textvariable=min_var, from_=0, to=20, width=3,
                       bg="#2a2a2a", fg="white", font=("Arial", 8),
                       buttonbackground="#2a2a2a").pack(side="left")

            tk.Label(row, text="↑", bg="#1e1e2a", fg="#888",
                     font=("Arial", 7)).pack(side="left", padx=(2, 0))
            max_var = tk.StringVar(value=str(rule.get("max", 1)))
            tk.Spinbox(row, textvariable=max_var, from_=0, to=20, width=3,
                       bg="#2a2a2a", fg="white", font=("Arial", 8),
                       buttonbackground="#2a2a2a").pack(side="left")

            tk.Button(row, text="✕", width=2, font=("Arial", 8),
                      bg="#3a1a1a", fg="#ff8888", cursor="hand2",
                      command=lambda i=idx: self._remove_sigil_rule(i)
                      ).pack(side="right", padx=2)

            # Sync prob/min/max vars → rule dict on change
            def _sync_nums(*_, r=rule, pv=p_var, mnv=min_var, mxv=max_var):
                try:
                    r["probability"] = float(pv.get())
                    r["min"] = int(mnv.get())
                    r["max"] = int(mxv.get())
                except Exception:
                    pass
                self._schedule_autosave()

            for _v in (p_var, min_var, max_var):
                _v.trace_add("write", _sync_nums)

    def _add_sigil_rule(self):
        bt = self._sigil_rules_var.get()
        container_choices = list(self._containers.keys()) if self._containers else []
        default_c = container_choices[0] if container_choices else ""
        self._sigil_rules_data.setdefault(bt, []).append(
            {"container": default_c, "probability": 1.0, "min": 1, "max": 1}
        )
        self._rebuild_sigil_rules_panel()
        self._schedule_autosave()

    def _open_effects_picker_for_rule(self, rule: dict):
        """
        Open a multi-select dialog to pick effect IDs for an inline effects pool.
        Modifies rule["effects"] in place and refreshes the panel.
        """
        all_effect_ids = sorted(
            item["id"] for item in self._content_data.get("Effect", []) if "id" in item
        )
        if not all_effect_ids:
            return

        top = tk.Toplevel(self.winfo_toplevel())
        top.title("Effekte für Regel auswählen")
        top.configure(bg="#1a1a1a")
        top.grab_set()
        top.resizable(False, False)

        tk.Label(top, text="Effekte wählen (Strg+Klick für Mehrfachauswahl):",
                 bg="#1a1a1a", fg="#ccc", font=("Arial", 9)).pack(
            padx=10, pady=(8, 2))

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
            self._rebuild_sigil_rules_panel()
            self._schedule_autosave()
            top.destroy()

        def _cancel():
            top.destroy()

        tk.Button(btn_row, text="✓ OK", command=_ok,
                  bg="#1a4a1a", fg="#88ff88",
                  font=("Arial", 9, "bold"), cursor="hand2",
                  width=10).pack(side="left", padx=4)
        tk.Button(btn_row, text="Abbrechen", command=_cancel,
                  bg="#2a2a2a", fg="#aaa",
                  font=("Arial", 9), cursor="hand2",
                  width=10).pack(side="left", padx=4)

        top.bind("<Return>", lambda e: _ok())
        top.bind("<Escape>", lambda e: _cancel())

    def _remove_sigil_rule(self, idx: int):
        bt = self._sigil_rules_var.get()
        rules = self._sigil_rules_data.get(bt, [])
        if 0 <= idx < len(rules):
            rules.pop(idx)
        self._rebuild_sigil_rules_panel()
        self._schedule_autosave()

    def _pick_effect_id(self) -> str:
        """Show a Toplevel with effect/cost IDs to pick from."""
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

    def _add_incompat_pair(self):
        eid1 = self._pick_effect_id()
        if not eid1:
            return
        eid2 = self._pick_effect_id()
        if not eid2 or eid2 == eid1:
            return
        pair = sorted([eid1, eid2])
        if pair not in [sorted(p) for p in self._incompatible_pairs]:
            self._incompatible_pairs.append(pair)
            self._incompat_lb.insert("end", f"{pair[0]}  ↔  {pair[1]}")
        self._schedule_autosave()

    def _remove_incompat_pair(self):
        sel = self._incompat_lb.curselection()
        if not sel:
            return
        idx = sel[0]
        self._incompat_lb.delete(idx)
        if 0 <= idx < len(self._incompatible_pairs):
            self._incompatible_pairs.pop(idx)
        self._schedule_autosave()

    # ══════════════════════════════════════════════════════════════════════════
    # CENTER – Card list
    # ══════════════════════════════════════════════════════════════════════════

    def _build_card_list(self, parent):
        # Header row with title + delete-all button
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

        # Filter bar
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

        tk.Button(filter_f, text="🎲", command=self._random_pick,
                  bg="#2a2a2a", fg="#aaa", font=("Arial", 10),
                  cursor="hand2").pack(side="right", padx=2)

        # Card count label
        self._count_label = tk.Label(parent, text="0 Karten",
                                     bg="#1a1a1a", fg="#555",
                                     font=("Arial", 8))
        self._count_label.pack(anchor="w", padx=8)

        # Listbox
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

        # Delete selected button
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
        # Select in listbox
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

    # ══════════════════════════════════════════════════════════════════════════
    # RIGHT – Card detail
    # ══════════════════════════════════════════════════════════════════════════

    def _build_detail(self, parent):
        self._detail_header = tk.Label(
            parent, text="← Karte auswählen",
            bg="#1a1a1a", fg="#555",
            font=("Arial", 11, "italic"))
        self._detail_header.pack(anchor="w", padx=12, pady=(8, 4))

        # Metrics bar
        self._metrics_label = tk.Label(
            parent, text="", bg="#1a1a1a", fg="#888",
            font=("Consolas", 9))
        self._metrics_label.pack(anchor="w", padx=12)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=6)

        # ── Card preview (rendered card image) + scrollable block detail ──────
        content_row = tk.Frame(parent, bg="#1a1a1a")
        content_row.pack(fill="both", expand=True)

        # Left: card preview
        from card_builder.card_preview import CardPreviewWidget
        self._card_preview = CardPreviewWidget(content_row, label="Vorschau", bg="#1a1a1a")
        self._card_preview.pack(side="left", anchor="n", padx=(8, 4), pady=4)

        # Right: scrollable block detail
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
            lambda e: self._detail_canvas.yview_scroll(
                int(-e.delta / 120), "units"))

        self._detail_inner = tk.Frame(self._detail_canvas, bg="#1a1a1a")
        self._detail_win   = self._detail_canvas.create_window(
            (0, 0), window=self._detail_inner, anchor="nw")
        self._detail_inner.bind(
            "<Configure>",
            lambda e: self._detail_canvas.configure(
                scrollregion=self._detail_canvas.bbox("all")))
        self._detail_canvas.bind(
            "<Configure>",
            lambda e: self._detail_canvas.itemconfig(
                self._detail_win, width=e.width))

    def _refresh_content_and_recalculate(self):
        """Save content data to disk, reload, and recalculate CV/complexity for all cards."""
        _save_content_data(self._content_data)
        self._content_data  = _load_content_data()
        self._effects_lu    = _list_to_lookup(self._content_data.get("Effect",    []))
        self._costs_lu      = _list_to_lookup(self._content_data.get("Cost",      []))
        self._triggers_lu   = _list_to_lookup(self._content_data.get("Trigger",   []))
        self._conditions_lu = _list_to_lookup(self._content_data.get("Condition", []))
        for card in self._cards:
            self._recompute_card(card)
        save_random_cards(self._cards, self._current_profile)
        self._refresh_list()
        # Re-show detail panel if a card is selected
        sel = self._card_lb.curselection()
        if sel:
            vis_idx = sel[0]
            if 0 <= vis_idx < len(self._visible_indices):
                self._show_detail(self._cards[self._visible_indices[vis_idx]])

    def _show_recipe_detail(self, card: dict):
        """Render detail view for Recipe cards (ingredients + effects)."""
        BG = "#1e2a2a"
        parent = self._detail_inner

        # Ingredients
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

        # Effects
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
                text = _render_effect(item, vals, opts, fallback_id=eid)

                row = tk.Frame(parent, bg="#1e1e2e", relief="groove", bd=1)
                row.pack(fill="x", padx=12, pady=1)
                tk.Button(row, text=f"  Eff: {eid}",
                          bg="#1e1e2e", fg="#88ff88", relief="flat", cursor="hand2",
                          font=("Consolas", 8), anchor="w",
                          command=lambda i=eid: self._open_content_editor(i, "Effect")
                          ).pack(side="left")
                tk.Label(row, text=f"→  {text}", bg="#1e1e2e", fg="#cccccc",
                         font=("Consolas", 8)).pack(side="left", padx=4)

                # Variable values
                for vname, vval in vals.items():
                    vr = tk.Frame(parent, bg="#161622")
                    vr.pack(fill="x", padx=24, pady=0)
                    tk.Label(vr, text=f"{{{vname}}} = {vval}",
                             bg="#161622", fg="#888",
                             font=("Consolas", 8)).pack(side="left", padx=8)

        # Use text
        use_text = card.get("use_text", "")
        if use_text:
            uf = tk.Frame(parent, bg="#1e1e1e", relief="groove", bd=1)
            uf.pack(fill="x", padx=8, pady=(8, 4))
            tk.Label(uf, text="Use:", bg="#1e1e1e", fg="#888",
                     font=("Arial", 8, "bold")).pack(anchor="w", padx=4, pady=2)
            tk.Label(uf, text=use_text, bg="#1e1e1e", fg="white",
                     font=("Arial", 9), wraplength=400, justify="left",
                     anchor="w").pack(fill="x", padx=8, pady=2)

    def _open_content_editor(self, item_id: str, type_name: str):
        """Open ContentEditor for an effect, cost, trigger, or condition by ID."""
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

    def _to_render_card(self, card: dict) -> dict:
        """Convert random card format → card_builder renderer format."""
        import copy, re
        rc = copy.deepcopy(card)
        rc.setdefault("name",      card.get("name", "?"))
        rc.setdefault("artwork",   "")
        rc.setdefault("card_type", "Spells")
        for blk in rc.get("blocks", []):
            for ab in blk.get("abilities", []):
                for eff in ab.get("effects", []):
                    eid   = eff.get("effect_id", "")
                    item  = self._effects_lu.get(eid, {})
                    evals = eff.get("vals", {})
                    eopt  = eff.get("opt_vals", {})
                    eff["content_text"] = _render_effect(item, evals, eopt, fallback_id=eid)
                for cost in ab.get("costs", []):
                    cid   = cost.get("cost_id", "")
                    item  = self._costs_lu.get(cid, {})
                    cvals = cost.get("vals", {})
                    copt  = cost.get("opt_vals", {})
                    cost["content_text"] = _render_effect(item, cvals, copt, fallback_id=cid)
        return rc

    def _clear_detail(self):
        self._detail_header.config(text="← Karte auswählen")
        self._card_preview.clear()
        self._metrics_label.config(text="")
        for w in self._detail_inner.winfo_children():
            w.destroy()

    def _show_detail(self, card: dict):
        rt = card.get("recipe_type", "")
        label = rt or card.get("element", "?")
        self._detail_header.config(
            text=f"🃏  {card.get('name', '?')}   [{label}]",
            fg="#cc8833")
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
            print(f"[detail] Rendere Vorschau für {card.get('name')} ...")
            rc = self._to_render_card(card)
            self._card_preview.show(rc)
            print(f"[detail] Vorschau OK")
        except Exception as e:
            print(f"[detail] Vorschau FEHLER: {e}")
            import traceback; traceback.print_exc()
            self._card_preview.clear()

        for w in self._detail_inner.winfo_children():
            w.destroy()

        # Recipe cards have ingredients, not blocks
        if card.get("ingredients") is not None:
            self._show_recipe_detail(card)
            return

        from card_builder.constants import BOX_COLORS as BLOCK_COLORS, BOX_SYMBOLS as BLOCK_SYMBOLS
        from .cv_calc import cv_content_item, cv_ability, complexity_content_item

        BG   = "#1e1e2e"
        BG2  = "#161622"

        for block in card.get("blocks", []):
            btype = block.get("type", "?")
            color = BLOCK_COLORS.get(btype, "#333")
            sym   = BLOCK_SYMBOLS.get(btype, "■")

            # ── Block header ──────────────────────────────────────────────────
            bh = tk.Frame(self._detail_inner, bg=color)
            bh.pack(fill="x", padx=8, pady=(8, 0))
            tk.Label(bh, text=f" {sym}  {btype}",
                     bg=color, fg="white",
                     font=("Arial", 10, "bold")).pack(side="left", padx=6, pady=3)

            # ── Abilities ─────────────────────────────────────────────────────
            for ab in block.get("abilities", []):
                ab_frame = tk.Frame(self._detail_inner, bg=BG, relief="groove", bd=1)
                ab_frame.pack(fill="x", padx=12, pady=2)

                # Compute ability-level stats
                ab_cv = cv_ability(ab, self._effects_lu, self._costs_lu)
                ab_cmplx = (
                    sum(complexity_content_item(self._effects_lu[e["effect_id"]])
                        for e in ab.get("effects", [])
                        if e.get("effect_id") in self._effects_lu)
                    + sum(complexity_content_item(self._costs_lu[c["cost_id"]])
                          for c in ab.get("costs", [])
                          if c.get("cost_id") in self._costs_lu)
                )

                # Ability type header row
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

                # ── Condition ─────────────────────────────────────────────────
                if ab.get("condition_id"):
                    cid2   = ab["condition_id"]
                    cv2    = ab.get("condition_vals", {})
                    co2    = ab.get("condition_opt_vals", {})
                    ci2    = self._conditions_lu.get(cid2, {})
                    ct2    = _render_effect(ci2, cv2, co2, fallback_id=cid2)
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

                # ── Trigger ────────────────────────────────────────────────────
                if ab.get("trigger_id"):
                    tid2   = ab["trigger_id"]
                    tv2    = ab.get("trigger_vals", {})
                    to2    = ab.get("trigger_opt_vals", {})
                    ti2    = self._triggers_lu.get(tid2, {})
                    tt2    = _render_effect(ti2, tv2, to2, fallback_id=tid2)
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
                    for vk2, vv2 in tv2.items():
                        tvrow = tk.Frame(ab_frame, bg="#141e14")
                        tvrow.pack(fill="x", padx=24, pady=0)
                        tk.Label(tvrow, text=f"  {{{vk2}}} = {vv2}",
                                 bg="#141e14", fg="#88bb66",
                                 font=("Consolas", 7)).pack(side="left")
                    for oi2, ch2 in sorted(to2.items()):
                        torow = tk.Frame(ab_frame, bg="#141e14")
                        torow.pack(fill="x", padx=24, pady=0)
                        tk.Label(torow, text=f"  [opt{oi2}] = {ch2}",
                                 bg="#141e14", fg="#88aa66",
                                 font=("Consolas", 7)).pack(side="left")

                # ── Costs ─────────────────────────────────────────────────────
                for cost in ab.get("costs", []):
                    cid    = cost.get("cost_id", "?")
                    cvals  = cost.get("vals", {})
                    citem  = self._costs_lu.get(cid, {})
                    copt   = cost.get("opt_vals", {})
                    ctext  = _render_effect(citem, cvals, copt, fallback_id=cid)
                    c_cv   = cv_content_item(citem, cvals, copt) if citem else 0.0
                    c_cmplx = complexity_content_item(citem) if citem else 0.0
                    crow   = tk.Frame(ab_frame, bg=BG2)
                    crow.pack(fill="x", padx=8, pady=1)
                    # Clickable cost ID
                    tk.Button(crow, text=f"  Cost: {cid}",
                              bg=BG2, fg="#ffaa44", relief="flat", cursor="hand2",
                              font=("Consolas", 8), anchor="w",
                              command=lambda i=cid: self._open_content_editor(i, "Cost")
                              ).pack(side="left")
                    tk.Label(crow, text=f"→  {ctext}",
                             bg=BG2, fg="#ffcc77",
                             font=("Consolas", 8)).pack(side="left", padx=4)
                    tk.Label(crow, text=f"CV={c_cv:+.2f}  Cmplx={c_cmplx:.1f}",
                             bg=BG2, fg="#aaaaaa",
                             font=("Consolas", 8)).pack(side="right", padx=4)
                    for vk, vv in cvals.items():
                        vrow = tk.Frame(ab_frame, bg=BG2)
                        vrow.pack(fill="x", padx=24, pady=0)
                        tk.Button(vrow, text=f"  {{{vk}}} = {vv}",
                                  bg=BG2, fg="#886644", relief="flat", cursor="hand2",
                                  font=("Consolas", 7),
                                  command=lambda i=cid: self._open_content_editor(i, "Cost")
                                  ).pack(side="left")
                    for oi, ch in sorted(copt.items()):
                        orow = tk.Frame(ab_frame, bg=BG2)
                        orow.pack(fill="x", padx=24, pady=0)
                        tk.Button(orow, text=f"  [opt{oi}] = {ch}",
                                  bg=BG2, fg="#886688", relief="flat", cursor="hand2",
                                  font=("Consolas", 7),
                                  command=lambda i=cid: self._open_content_editor(i, "Cost")
                                  ).pack(side="left")

                # ── Effects ───────────────────────────────────────────────────
                for eff in ab.get("effects", []):
                    eid      = eff.get("effect_id", "?")
                    evals    = eff.get("vals", {})
                    eopt     = eff.get("opt_vals", {})
                    eitem    = self._effects_lu.get(eid, {})
                    etext    = _render_effect(eitem, evals, eopt, fallback_id=eid)
                    e_cv     = cv_content_item(eitem, evals, eopt) if eitem else 0.0
                    e_cmplx  = complexity_content_item(eitem) if eitem else 0.0

                    erow = tk.Frame(ab_frame, bg=BG)
                    erow.pack(fill="x", padx=8, pady=1)
                    # Clickable effect ID
                    tk.Button(erow, text=f"  Eff: {eid}",
                              bg=BG, fg="#88ff88", relief="flat", cursor="hand2",
                              font=("Consolas", 8), anchor="w",
                              command=lambda i=eid: self._open_content_editor(i, "Effect")
                              ).pack(side="left")
                    tk.Label(erow, text=f"→  {etext}",
                             bg=BG, fg="#ccffcc",
                             font=("Consolas", 8)).pack(side="left", padx=4)
                    tk.Label(erow,
                             text=f"CV={e_cv:+.2f}  Cmplx={e_cmplx:.1f}",
                             bg=BG, fg="#aaaaaa",
                             font=("Consolas", 8)).pack(side="right", padx=4)

                    # Variable values indented – inline edit on click
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
                    # Option values indented – inline combobox on click
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
    # Actions
    # ══════════════════════════════════════════════════════════════════════════

    # ══════════════════════════════════════════════════════════════════════════
    # Inline editing of variable values and option choices
    # ══════════════════════════════════════════════════════════════════════════

    def _recompute_card(self, card: dict):
        """Recompute _cv and _complexity for a card after manual edits."""
        card["_cv"]         = round(cv_card(card, self._box_config,
                                            self._effects_lu, self._costs_lu), 3)
        card["_complexity"] = round(complexity_card(card, self._effects_lu,
                                                    self._costs_lu), 3)

    def _inline_edit_var(self, btn, card, data_dict, key, item_id, type_name):
        """Replace a variable-value button with an inline Entry."""
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

        ent.bind("<Return>",    _commit)
        ent.bind("<FocusOut>",  _commit)
        ent.bind("<Escape>",    lambda _: self._show_detail(card))

    def _inline_edit_opt(self, btn, card, data_dict, opt_key, item_id, type_name):
        """Replace an option button with an inline Combobox."""
        import re
        btn.pack_forget()
        parent = btn.master
        lu = self._effects_lu if type_name == "Effect" else self._costs_lu
        item = lu.get(item_id, {})
        cb_text = item.get("sigil", "")
        # Extract all option lists from sigil
        opt_lists = [
            [c.strip() for c in m.split(",")]
            for m in re.findall(r'\[([^\]]+)\]', cb_text)
        ]
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

    def _schedule_autosave(self, *_):
        """Debounced auto-save: saves 800 ms after last change."""
        if hasattr(self, "_autosave_job") and self._autosave_job:
            self.after_cancel(self._autosave_job)
        self._autosave_job = self.after(800, self._do_autosave)

    def _do_autosave(self):
        self._autosave_job = None
        cfg = self._collect_config()
        save_gen_config(cfg, self._current_profile)
        self._gen_config = cfg

    def _save_config(self):
        cfg = self._collect_config()
        save_gen_config(cfg, self._current_profile)
        save_random_cards(self._cards, self._current_profile)
        self._gen_config = cfg
        self._set_status("✓ Einstellungen gespeichert", "#1a6e3c")

    def _collect_config(self) -> dict:
        cfg = dict(self._gen_config)

        try:
            cfg["count"] = int(self._count_var.get())
        except Exception:
            pass

        if self._current_profile == "Recipes":
            cfg["recipe_type_mode"] = self._rt_mode_var.get()
            rtw = {}
            for rt, v in self._rt_weight_vars.items():
                try:
                    rtw[rt] = float(v.get())
                except Exception:
                    rtw[rt] = 10.0
            cfg["recipe_type_weights"] = rtw
        elif hasattr(self, "_el_mode_var"):
            cfg["element_mode"] = self._el_mode_var.get()
            ew = {}
            for el, v in self._el_weight_vars.items():
                try:
                    ew[el] = float(v.get())
                except Exception:
                    ew[el] = 10.0
            cfg["custom_element_weights"] = ew

        block_rules = []
        for bt, v in self._block_rule_vars.items():
            try:
                p = float(v.get())
            except Exception:
                p = 0.0
            if p > 0:
                block_rules.append({"block_type": bt, "probability": p})
        cfg["block_rules"] = block_rules

        content_rules = []
        for key, v in self._content_rule_vars.items():
            try:
                p = float(v.get())
            except Exception:
                p = 0.0
            if p > 0:
                kind = getattr(self, "_content_rule_types", {}).get(key, "container")
                if kind == "container":
                    content_rules.append({"container": key, "probability": p})
                elif kind == "effect":
                    content_rules.append({"effect_id": key, "probability": p})
                elif kind == "cost":
                    content_rules.append({"cost_id": key, "probability": p})
                elif kind == "condition":
                    content_rules.append({"condition_id": key, "probability": p})
                elif kind == "trigger":
                    content_rules.append({"trigger_id": key, "probability": p})
        cfg["content_rules"] = content_rules

        cost_rules = []
        for cid, v in self._cost_rule_vars.items():
            try:
                p = float(v.get())
            except Exception:
                p = 0.0
            if p > 0:
                cost_rules.append({"cost_id": cid, "probability": p})
        cfg["cost_rules"] = cost_rules

        try:
            cfg["cv_target"] = float(self._cv_target_var.get())
        except Exception:
            pass
        try:
            cfg["cv_per_box_max"] = float(self._cv_box_var.get())
        except Exception:
            pass
        try:
            cfg["cv_card_min"] = float(self._cv_min_var.get())
        except Exception:
            pass
        try:
            cfg["mana_chance"] = float(self._mana_chance_var.get())
        except Exception:
            pass
        try:
            cfg["mana_main_count"] = int(self._mana_main_var.get())
        except Exception:
            pass
        try:
            cfg["mana_max_count"] = int(self._mana_max_var.get())
        except Exception:
            pass
        try:
            cfg["max_other_costs"] = int(self._max_other_costs_var.get())
        except Exception:
            pass
        try:
            cfg["max_effects"] = int(self._max_effects_var.get())
        except Exception:
            pass
        try:
            cfg["min_effects"] = int(self._min_effects_var.get())
        except Exception:
            pass
        try:
            cfg["condition_chance"] = float(self._cond_chance_var.get())
        except Exception:
            pass
        try:
            cfg["choose_n_chance"] = float(self._choose_chance_var.get())
        except Exception:
            pass

        # Sigil rules (guarded – vars might not exist if build is incomplete)
        try:
            sigil_rules = {}
            for bt, rules in self._sigil_rules_data.items():
                clean = [
                    {k: v for k, v in r.items() if k != "_vars"}
                    for r in rules
                ]
                if clean:
                    sigil_rules[bt] = clean
            cfg["sigil_rules"] = sigil_rules
            cfg["incompatible_pairs"] = [list(p) for p in self._incompatible_pairs]
        except AttributeError:
            pass

        try:
            cfg["min_blocks"] = int(self._min_blocks_var.get())
        except Exception:
            pass

        return cfg

    def _generate(self):
        cfg = self._collect_config()
        count = cfg.get("count", 10)
        print(f"[generate] Profil={self._current_profile}, Anzahl={count}")
        self._set_status(f"Generiere {count} Karten ...", "#1a3e8e")
        self.update_idletasks()

        # Reload live data
        self._content_data  = _load_content_data()
        self._effects_lu    = _list_to_lookup(self._content_data.get("Effect",    []))
        self._costs_lu      = _list_to_lookup(self._content_data.get("Cost",      []))
        self._triggers_lu   = _list_to_lookup(self._content_data.get("Trigger",   []))
        self._conditions_lu = _list_to_lookup(self._content_data.get("Condition", []))
        self._containers    = _load_containers()
        self._box_config    = load_box_config()

        gen = CardGenerator(self._content_data, self._containers,
                            self._box_config, cfg)
        new_cards = gen.generate(count)
        print(f"[generate] {len(new_cards)}/{count} Karten generiert")
        self._cards.extend(new_cards)
        save_random_cards(self._cards, self._current_profile)

        self._refresh_list()
        self._set_status(f"✓ {len(new_cards)} Karten generiert. "
                         f"Gesamt: {len(self._cards)}", "#1a6e3c")

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
        self._set_status("Alle Karten gelöscht.", "#8e1a1a")

    def _set_status(self, msg: str, color: str = "#1a1a1a"):
        self._status.config(text=msg, bg=color,
                            fg="white" if color != "#1a1a1a" else "#aaa")
        self.after(4000, lambda: self._status.config(
            text="", bg="#1a1a1a", fg="#aaa"))


# ── Rendering helper ──────────────────────────────────────────────────────────

def _render_effect(item: dict, vals: dict, opt_vals: dict,
                   fallback_id: str = "") -> str:
    """
    Render a content item's display text using the template_parser functions:
      - content_text  → render_display_text  (handles [if OPT0=…] conditionals)
      - sigil         → render_content_text  (handles [a,b,c] dropdown choices)
    Falls back to 'ID var=val [opt]' when no content is defined.
    """
    from CardContent.template_parser import render_content_text, render_display_text
    import re

    if not item and not fallback_id:
        return ""

    sigil = item.get("sigil", "") if item else ""
    ct    = item.get("content_text", "") if item else ""

    if ct:
        # content_text uses [if OPT0=…] conditional syntax
        text = render_display_text(ct, vals, opt_vals)
    elif sigil:
        # sigil uses [a,b,c] dropdown syntax
        text = render_content_text(sigil, vals, opt_vals)
    else:
        text = ""

    if not text:
        # No content defined — build a readable fallback from ID + vals + opts
        parts = [fallback_id or (item.get("id", "?") if item else "?")]
        for k, v in vals.items():
            parts.append(f"{k}={v}")
        for oi in sorted(opt_vals.keys()):
            parts.append(f"[{opt_vals[oi]}]")
        return " ".join(parts)

    return text.strip()
