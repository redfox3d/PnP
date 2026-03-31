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
                        ("triggers.json",   "Trigger")]:
        path = os.path.join(cc_dir, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            items = raw.get(key, raw.get(list(raw.keys())[0], []))
            # Migrate legacy key content_box → sigil
            for item in items:
                if "content_box" in item and "sigil" not in item:
                    item["sigil"] = item.pop("content_box")
                elif "content_box" in item:
                    item.pop("content_box")
            data[key] = items
        except Exception:
            data[key] = []
    return data


def _load_containers() -> dict:
    try:
        from container_manager.models import load_containers
        return load_containers()
    except Exception:
        return {}


def _render_card_summary(card: dict) -> str:
    """One-line summary for the card list."""
    el  = card.get("element", "?")
    cv  = card.get("_cv", "?")
    cmx = card.get("_complexity", "?")
    nb  = len(card.get("blocks", []))
    return f"{el:<8}  CV={cv:<6}  Cmplx={cmx:<5}  Boxen={nb}"


# ── Main panel ────────────────────────────────────────────────────────────────

class RandomBuilder(tk.Frame):

    def __init__(self, parent, **kw):
        kw.setdefault("bg", "#1a1a1a")
        super().__init__(parent, **kw)
        self._content_data  = _load_content_data()
        self._effects_lu    = _list_to_lookup(self._content_data.get("Effect", []))
        self._costs_lu      = _list_to_lookup(self._content_data.get("Cost",   []))
        self._containers    = _load_containers()
        self._content_probs = load_content_probs()
        self._box_config    = load_box_config()
        self._gen_config    = load_gen_config()
        self._cards: list   = load_random_cards()
        self._selected_idx  = None
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Left settings panel ───────────────────────────────────────────────
        left = tk.Frame(self, bg="#1a1a1a", width=290)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

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

        # ── Element ───────────────────────────────────────────────────────────
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

        self._sep(f)

        # ── Block Regeln ──────────────────────────────────────────────────────
        tk.Label(f, text="Box Regeln  (Wahrscheinlichkeit):",
                 bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(anchor="w", **pad)
        tk.Label(f, text="Wie oft erscheint jede Box auf einer Karte?",
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
        tk.Label(cv_row, text="  Box ≤", bg="#1a1a1a", fg="#888",
                 font=("Arial", 8)).pack(side="left", padx=(4, 0))
        self._cv_box_var = tk.StringVar(
            value=str(self._gen_config.get("cv_per_box_max", 3.0)))
        self._cv_box_var.trace_add("write", self._schedule_autosave)
        tk.Entry(cv_row, textvariable=self._cv_box_var, width=5,
                 bg="#2a2a2a", fg="white").pack(side="left", padx=4)

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

    def _sep(self, parent):
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=6)

    def _toggle_el_weights(self):
        state = "normal" if self._el_mode_var.get() == "custom" else "disabled"
        for w in self._el_weights_frame.winfo_children():
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
                             values=["Alle"] + ELEMENTS,
                             state="readonly", width=8)
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
            if el_filter == "Alle" or c.get("element") == el_filter
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
                if el_filter == "Alle" or c.get("element") == el_filter]
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
        save_random_cards(self._cards)
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

    def _open_content_editor(self, item_id: str, type_name: str):
        """Open ContentEditor for an effect or cost by ID."""
        lookup = {"Effect": self._effects_lu, "Cost": self._costs_lu}
        item = lookup.get(type_name, {}).get(item_id)
        if not item:
            return
        from CardContent.content_editor import ContentEditor

        def _on_save():
            # Reload lookup tables so rendered text updates on next card select
            self._content_data = _load_content_data()
            self._effects_lu   = _list_to_lookup(self._content_data.get("Effect", []))
            self._costs_lu     = _list_to_lookup(self._content_data.get("Cost",   []))

        ContentEditor(self.winfo_toplevel(), item, self._content_data,
                      on_save=_on_save)

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
        self._detail_header.config(
            text=f"🃏  {card.get('name', '?')}   [{card.get('element', '?')}]",
            fg="#cc8833")
        self._metrics_label.config(
            text=f"CV: {card.get('_cv', '?')}   Complexity: {card.get('_complexity', '?')}"
                 f"   Boxen: {len(card.get('blocks', []))}")

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
            save_random_cards(self._cards)
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
            save_random_cards(self._cards)
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
        save_gen_config(cfg)
        self._gen_config = cfg

    def _save_config(self):
        cfg = self._collect_config()
        save_gen_config(cfg)
        self._gen_config = cfg
        self._set_status("✓ Einstellungen gespeichert", "#1a6e3c")

    def _collect_config(self) -> dict:
        cfg = dict(self._gen_config)

        try:
            cfg["count"] = int(self._count_var.get())
        except Exception:
            pass
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

        return cfg

    def _generate(self):
        cfg = self._collect_config()
        count = cfg.get("count", 10)
        print(f"[generate] Starte Generierung: {count} Karten, cfg={cfg}")
        self._set_status(f"Generiere {count} Karten ...", "#1a3e8e")
        self.update_idletasks()

        # Reload live data
        print("[generate] Lade Content-Daten ...")
        self._content_data = _load_content_data()
        self._effects_lu   = _list_to_lookup(self._content_data.get("Effect", []))
        self._costs_lu     = _list_to_lookup(self._content_data.get("Cost",   []))
        self._containers   = _load_containers()
        self._box_config   = load_box_config()
        print(f"[generate] Effekte: {len(self._effects_lu)}, Kosten: {len(self._costs_lu)}, "
              f"Container: {len(self._containers)}, BoxConfig: {len(self._box_config)}")
        print(f"[generate] Triggers: {len(self._content_data.get('Trigger', []))}")

        gen = CardGenerator(self._content_data, self._containers,
                            self._box_config, cfg)
        print("[generate] Generator erstellt, starte generate() ...")
        new_cards = gen.generate(count)
        print(f"[generate] {len(new_cards)} Karten generiert")
        self._cards.extend(new_cards)
        save_random_cards(self._cards)

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
        clear_random_cards()
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
