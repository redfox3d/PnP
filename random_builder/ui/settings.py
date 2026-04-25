"""
random_builder/ui/settings.py – Left settings panel for the Random Builder.

Builds profile-specific settings (Spell/Prowess rules vs. Recipe rules)
inside a scrollable frame. All Tk variables are owned by this class;
the parent reads them via collect_config().
"""

import tkinter as tk
from tkinter import ttk

from card_builder.constants import ELEMENTS, RECIPE_TYPES, BOX_TYPES


class SettingsPanel(tk.Frame):
    """Scrollable left-side settings panel."""

    def __init__(self, parent, profile: str, gen_config: dict,
                 containers: dict, content_data: dict,
                 content_probs: dict,
                 on_autosave=None, on_generate=None,
                 on_save=None, on_reload_containers=None,
                 on_pick_effects=None, on_pick_effect_id=None,
                 on_open_ingredients=None,
                 **kw):
        kw.setdefault("bg", "#1a1a1a")
        super().__init__(parent, **kw)

        self.profile       = profile
        self._gen_config   = gen_config
        self._containers   = containers
        self._content_data = content_data
        self._content_probs = content_probs
        self._on_autosave  = on_autosave or (lambda: None)
        self._on_generate  = on_generate or (lambda: None)
        self._on_save      = on_save or (lambda: None)
        self._on_reload    = on_reload_containers or (lambda: None)
        self._on_pick_effects  = on_pick_effects   # callback(rule) → opens effect picker
        self._on_pick_effect_id = on_pick_effect_id  # callback() → str
        self._on_open_ingredients = on_open_ingredients or (lambda: None)

        self._autosave_job = None

        # Public variable holders (read by collect_config)
        self._vars = {}

        self._build()

    # ── Layout ───────────────────────────────────────────────────────────────

    def _build(self):
        outer = tk.Frame(self, bg="#1a1a1a")
        outer.pack(fill="both", expand=True)

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

        # ── Quick actions (top) ──────────────────────────────────────────────
        tk.Button(f, text="🎲  KARTEN GENERIEREN!",
                  command=self._on_generate,
                  bg="#1a6e3c", fg="white",
                  font=("Arial", 12, "bold"),
                  cursor="hand2").pack(fill="x", padx=6, pady=6)
        self._sep(f)

        # ── Anzahl ───────────────────────────────────────────────────────────
        tk.Label(f, text="Anzahl Karten:", bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(anchor="w", **pad)
        self._vars["count"] = v = tk.IntVar(value=self._gen_config.get("count", 10))
        v.trace_add("write", self._schedule_autosave)
        tk.Spinbox(f, from_=1, to=500, textvariable=v, width=8,
                   bg="#2a2a2a", fg="white", buttonbackground="#333").pack(anchor="w", **pad)
        self._sep(f)

        # ── Profile-specific sections ────────────────────────────────────────
        _is_recipes = (self.profile == "Recipes")
        _is_prowess = (self.profile == "Prowess")

        if _is_prowess:
            pass  # No elements or subcategories
        elif _is_recipes:
            self._build_recipe_type_weights(f, pad)
        else:
            self._build_element_weights(f, pad)

        self._sep(f)

        if _is_recipes:
            self._build_recipe_rules(f, pad)
        else:
            self._build_spell_rules(f, pad)

        self._sep(f)

        # ── Bottom action buttons ────────────────────────────────────────────
        tk.Button(f, text="💾  Einstellungen speichern",
                  command=self._on_save,
                  bg="#2a3a2a", fg="#88dd88",
                  font=("Arial", 9)).pack(fill="x", padx=8, pady=4)

        self._status = tk.Label(f, text="", bg="#1a1a1a", fg="#888",
                                font=("Arial", 8), wraplength=260, justify="left")
        self._status.pack(padx=8, pady=4)

    # ── Element weights (Spells) ─────────────────────────────────────────────

    def _build_element_weights(self, f, pad):
        tk.Label(f, text="Element Verteilung:", bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(anchor="w", **pad)
        self._vars["element_mode"] = mv = tk.StringVar(
            value=self._gen_config.get("element_mode", "equal"))
        mv.trace_add("write", self._schedule_autosave)
        for val, lbl in [("equal", "Alle gleich"), ("custom", "Eigene Gewichte")]:
            tk.Radiobutton(f, text=lbl, variable=mv, value=val,
                           bg="#1a1a1a", fg="#ccc", selectcolor="#2a2a3a",
                           activebackground="#1a1a2a",
                           command=self._toggle_el_weights).pack(anchor="w", padx=16)

        self._el_weights_frame = tk.Frame(f, bg="#1a1a1a")
        self._el_weights_frame.pack(fill="x", **pad)
        self._vars["el_weights"] = {}
        for el in ELEMENTS:
            row = tk.Frame(self._el_weights_frame, bg="#1a1a1a")
            row.pack(fill="x", pady=1)
            tk.Label(row, text=el, bg="#1a1a1a", fg="#888",
                     width=8, anchor="w", font=("Arial", 8)).pack(side="left")
            v = tk.StringVar(value=str(
                self._gen_config.get("custom_element_weights", {}).get(el, 10)))
            v.trace_add("write", self._schedule_autosave)
            self._vars["el_weights"][el] = v
            tk.Entry(row, textvariable=v, width=6,
                     bg="#2a2a2a", fg="white").pack(side="left", padx=2)
        self._toggle_el_weights()

        # ── H: per-card element COUNT weights (1..6 elements per card) ───────
        tk.Label(f, text="Element Anzahl pro Karte (Gewichte):",
                 bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(anchor="w", **pad)
        ec_frame = tk.Frame(f, bg="#1a1a1a")
        ec_frame.pack(fill="x", **pad)
        ec_cfg = self._gen_config.get("element_count_weights", {"1": 100})
        self._vars["element_count_weights"] = {}
        for n in range(1, 7):
            row = tk.Frame(ec_frame, bg="#1a1a1a")
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f"{n} Element{'e' if n != 1 else ''}",
                     bg="#1a1a1a", fg="#888",
                     width=12, anchor="w", font=("Arial", 8)).pack(side="left")
            v = tk.StringVar(value=str(ec_cfg.get(str(n), 0)))
            v.trace_add("write", self._schedule_autosave)
            self._vars["element_count_weights"][str(n)] = v
            tk.Entry(row, textvariable=v, width=6,
                     bg="#2a2a2a", fg="white").pack(side="left", padx=2)

    def _toggle_el_weights(self):
        state = "normal" if self._vars.get("element_mode", tk.StringVar()).get() == "custom" else "disabled"
        for w in self._el_weights_frame.winfo_children():
            for ww in w.winfo_children():
                try:
                    ww.config(state=state)
                except Exception:
                    pass

    # ── Recipe type weights ──────────────────────────────────────────────────

    def _build_recipe_type_weights(self, f, pad):
        tk.Label(f, text="Recipe Type Verteilung:", bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(anchor="w", **pad)
        self._vars["recipe_type_mode"] = mv = tk.StringVar(
            value=self._gen_config.get("recipe_type_mode", "equal"))
        mv.trace_add("write", self._schedule_autosave)
        for val, lbl in [("equal", "Alle gleich"), ("custom", "Eigene Gewichte")]:
            tk.Radiobutton(f, text=lbl, variable=mv, value=val,
                           bg="#1a1a1a", fg="#ccc", selectcolor="#2a2a3a",
                           activebackground="#1a1a2a",
                           command=self._toggle_rt_weights).pack(anchor="w", padx=16)

        self._rt_weights_frame = tk.Frame(f, bg="#1a1a1a")
        self._rt_weights_frame.pack(fill="x", **pad)
        self._vars["rt_weights"] = {}
        for rt in RECIPE_TYPES:
            row = tk.Frame(self._rt_weights_frame, bg="#1a1a1a")
            row.pack(fill="x", pady=1)
            tk.Label(row, text=rt, bg="#1a1a1a", fg="#888",
                     width=10, anchor="w", font=("Arial", 8)).pack(side="left")
            v = tk.StringVar(value=str(
                self._gen_config.get("recipe_type_weights", {}).get(rt, 10)))
            v.trace_add("write", self._schedule_autosave)
            self._vars["rt_weights"][rt] = v
            tk.Entry(row, textvariable=v, width=6,
                     bg="#2a2a2a", fg="white").pack(side="left", padx=2)
        self._toggle_rt_weights()

    def _toggle_rt_weights(self):
        state = "normal" if self._vars.get("recipe_type_mode", tk.StringVar()).get() == "custom" else "disabled"
        for w in self._rt_weights_frame.winfo_children():
            for ww in w.winfo_children():
                try:
                    ww.config(state=state)
                except Exception:
                    pass

    # ── Recipe-specific rules ────────────────────────────────────────────────

    def _build_recipe_rules(self, f, pad):
        hdr_row = tk.Frame(f, bg="#1a1a1a")
        hdr_row.pack(fill="x", **pad)
        tk.Label(hdr_row, text="Zutaten Regeln:", bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(side="left")
        tk.Button(hdr_row, text="Ingredient Editor",
                  bg="#2a4a4a", fg="#88dddd", relief="flat",
                  font=("Arial", 8), cursor="hand2",
                  command=self._on_open_ingredients).pack(side="right", padx=4)

        for label, key, default, lo, hi, inc in [
            ("Zutaten max",   "ingredient_max", 6,   1, 10, 1),
            ("Zutaten avg",   "ingredient_avg", 2.4, 1, 10, 0.1),
            ("CV pro Zutat",  "ingredient_cv",  4,   1, 20, 1),
        ]:
            row = tk.Frame(f, bg="#1a1a1a")
            row.pack(fill="x", padx=12, pady=2)
            tk.Label(row, text=label, bg="#1a1a1a", fg="#ccc",
                     width=16, anchor="w", font=("Arial", 8)).pack(side="left")
            v = tk.StringVar(value=str(self._gen_config.get(key, default)))
            v.trace_add("write", self._schedule_autosave)
            self._vars[key] = v
            tk.Spinbox(row, from_=lo, to=hi, increment=inc, textvariable=v,
                       width=5, bg="#2a2a2a", fg="white",
                       buttonbackground="#333", font=("Arial", 8)).pack(side="left", padx=2)

        self._sep(f)

        # CV filter
        tk.Label(f, text="CV Filter:", bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(anchor="w", **pad)
        cv_row = tk.Frame(f, bg="#1a1a1a")
        cv_row.pack(fill="x", padx=12, pady=2)
        tk.Label(cv_row, text="Karte ≥", bg="#1a1a1a", fg="#888",
                 font=("Arial", 8)).pack(side="left")
        self._vars["cv_card_min"] = v = tk.StringVar(
            value=str(self._gen_config.get("cv_card_min", -999.0)))
        v.trace_add("write", self._schedule_autosave)
        tk.Entry(cv_row, textvariable=v, width=5,
                 bg="#2a2a2a", fg="white").pack(side="left", padx=4)
        tk.Label(cv_row, text="≤", bg="#1a1a1a", fg="#888",
                 font=("Arial", 8)).pack(side="left")
        self._vars["cv_target"] = v2 = tk.StringVar(
            value=str(self._gen_config.get("cv_target", 999.0)))
        v2.trace_add("write", self._schedule_autosave)
        tk.Entry(cv_row, textvariable=v2, width=5,
                 bg="#2a2a2a", fg="white").pack(side="left", padx=4)

    # ── Spell/Prowess rules ──────────────────────────────────────────────────

    def _build_spell_rules(self, f, pad):
        # Sigil probability rules
        tk.Label(f, text="Sigil Regeln  (Wahrscheinlichkeit):",
                 bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(anchor="w", **pad)
        tk.Label(f, text="Wie oft erscheint jedes Sigil auf einer Karte?",
                 bg="#1a1a1a", fg="#555", font=("Arial", 7, "italic")).pack(
            anchor="w", padx=16)

        self._vars["block_rules"] = {}
        block_rules = {r["block_type"]: r["probability"]
                       for r in self._gen_config.get("block_rules", [])}
        for bt in BOX_TYPES:
            row = tk.Frame(f, bg="#1a1a1a")
            row.pack(fill="x", padx=12, pady=1)
            tk.Label(row, text=bt, bg="#1a1a1a", fg="#ccc",
                     width=13, anchor="w", font=("Arial", 8)).pack(side="left")
            v = tk.StringVar(value=str(block_rules.get(bt, 0.0)))
            v.trace_add("write", self._schedule_autosave)
            self._vars["block_rules"][bt] = v
            tk.Entry(row, textvariable=v, width=6,
                     bg="#2a2a2a", fg="white", font=("Arial", 8)).pack(
                side="left", padx=2)

        self._sep(f)

        # Container content rules
        tk.Label(f, text="Content Regeln  (Container → %):",
                 bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(anchor="w", **pad)

        self._content_rules_frame = tk.Frame(f, bg="#1a1a1a")
        self._content_rules_frame.pack(fill="x", **pad)
        self._vars["content_rules"] = {}
        self._content_rule_types = {}
        self._rebuild_content_rules()

        tk.Button(f, text="↺ Container neu laden",
                  command=self._reload_containers_cb,
                  bg="#2a2a2a", fg="#aaa",
                  font=("Arial", 8)).pack(anchor="w", padx=12, pady=2)

        self._sep(f)

        # Cost rules
        tk.Label(f, text="Kosten Regeln  (Cost-ID → %):",
                 bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(anchor="w", **pad)

        self._cost_rules_frame = tk.Frame(f, bg="#1a1a1a")
        self._cost_rules_frame.pack(fill="x", **pad)
        self._vars["cost_rules"] = {}
        self._rebuild_cost_rules()

        self._sep(f)

        # CV target
        tk.Label(f, text="CV Ziel:", bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(anchor="w", **pad)
        cv_row = tk.Frame(f, bg="#1a1a1a")
        cv_row.pack(fill="x", padx=12, pady=2)

        for label, key, default in [
            ("Karte ≥",  "cv_card_min", -999.0),
            ("≤",        "cv_target",     3.0),
        ]:
            tk.Label(cv_row, text=label, bg="#1a1a1a", fg="#888",
                     font=("Arial", 8)).pack(side="left")
            v = tk.StringVar(value=str(self._gen_config.get(key, default)))
            v.trace_add("write", self._schedule_autosave)
            self._vars[key] = v
            tk.Entry(cv_row, textvariable=v, width=5,
                     bg="#2a2a2a", fg="white").pack(side="left", padx=4)

        # Sigil CV row (separate line so the fields don't clip on narrow menus)
        sig_row = tk.Frame(f, bg="#1a1a1a")
        sig_row.pack(fill="x", padx=12, pady=2)
        for label, key, default in [
            ("Sigil ≥", "cv_per_sigil_min", 0.0),
            ("≤",       "cv_per_box_max",   3.0),
        ]:
            tk.Label(sig_row, text=label, bg="#1a1a1a", fg="#888",
                     font=("Arial", 8)).pack(side="left")
            v = tk.StringVar(value=str(self._gen_config.get(key, default)))
            v.trace_add("write", self._schedule_autosave)
            self._vars[key] = v
            tk.Entry(sig_row, textvariable=v, width=5,
                     bg="#2a2a2a", fg="white").pack(side="left", padx=4)

        self._sep(f)

        # Cost limits
        tk.Label(f, text="Kosten Limits:", bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9, "bold")).pack(anchor="w", **pad)

        limit_fields = [
            ("Mana Chance",       "mana_chance",      0.95, "(0–1)"),
            ("Mana Hauptwert",    "mana_main_count",  2,    "(häufigster Wert)"),
            ("Mana max Anzahl",   "mana_max_count",   6,    "Kreise (max)"),
            ("Andere Kosten max", "max_other_costs",  1,    "verschiedene"),
            ("Effekte max",       "max_effects",     -1,    "(-1 = unbegrenzt)"),
            ("Effekte min",       "min_effects",      0,    ""),
            ("Sigils min",        "min_blocks",       1,    "(1–4)"),
            ("Condition Chance",  "condition_chance",  0.15, ""),
            ("Choose N Chance",   "choose_n_chance",   0.10, "(0–1)"),
            # Sub-sigil category weights (mutually exclusive with Choose)
            ("Chance Choose",     "chance_choose",     0.40, "(0–1)"),
            ("Chance Enhance",    "chance_enhance",    0.20, "(0–1)"),
            ("Chance Doublecast", "chance_doublecast", 0.10, "(0–1)"),
            ("Chance Multicast",  "chance_multicast",  0.05, "(0–1)"),
            ("Chance keins",      "chance_no_subsigil", 0.60, "(Rest-Gewicht)"),
        ]
        for label, key, default, hint in limit_fields:
            row = tk.Frame(f, bg="#1a1a1a")
            row.pack(fill="x", padx=12, pady=2)
            tk.Label(row, text=label, bg="#1a1a1a", fg="#ccc",
                     width=16, anchor="w", font=("Arial", 8)).pack(side="left")
            v = tk.StringVar(value=str(self._gen_config.get(key, default)))
            v.trace_add("write", self._schedule_autosave)
            self._vars[key] = v
            if isinstance(default, float):
                tk.Entry(row, textvariable=v, width=6,
                         bg="#2a2a2a", fg="white", font=("Arial", 8)).pack(
                    side="left", padx=2)
            else:
                tk.Spinbox(row, from_=-1, to=50, textvariable=v,
                           width=5, bg="#2a2a2a", fg="white",
                           buttonbackground="#333", font=("Arial", 8)).pack(
                    side="left", padx=2)
            if hint:
                tk.Label(row, text=hint, bg="#1a1a1a", fg="#555",
                         font=("Arial", 7)).pack(side="left", padx=2)

        self._sep(f)

        # Sigil rules
        self._build_sigil_rules(f, pad)

        self._sep(f)

        tk.Button(f, text="⚙  Sigil Constraints Manager …",
                  command=self._open_sigil_constraints,
                  bg="#1a2a3a", fg="#5b9bd5",
                  font=("Arial", 9, "bold"),
                  cursor="hand2", relief="flat").pack(
            fill="x", padx=8, pady=4)

    def _open_sigil_constraints(self):
        from random_builder.ui.sigil_constraints import SigilConstraintsWindow
        # Sync current gen_config before opening
        cfg = self.collect_config()
        self._gen_config.update(cfg)
        win = SigilConstraintsWindow(
            self.winfo_toplevel(),
            gen_config=self._gen_config,
            content_data=self._content_data,
            on_change=self._schedule_autosave,
        )
        win.grab_set()

    # ── Sigil rules ──────────────────────────────────────────────────────────

    def _build_sigil_rules(self, f, pad):
        """Replace the old inline sigil-rules panel with a single launcher button."""
        # Store data locally so collect_config() can still read it
        self._sigil_rules_data = {
            bt: [dict(r) for r in rules]
            for bt, rules in self._gen_config.get("sigil_rules", {}).items()
        }
        self._incompatible_pairs = [list(p)
                                     for p in self._gen_config.get("incompatible_pairs", [])]

        btn = tk.Button(f,
                        text="⚡  Sigil Regeln  …",
                        bg="#1a2a3a", fg="#88ccff",
                        font=("Arial", 9, "bold"),
                        cursor="hand2", relief="flat",
                        command=self._open_sigil_rules_editor)
        btn.pack(fill="x", padx=8, pady=6)
        self._sigil_rules_btn = btn
        self._update_sigil_rules_btn()

    def _update_sigil_rules_btn(self):
        """Update button label to show how many rules are configured."""
        total = sum(len(v) for v in self._sigil_rules_data.values())
        ic    = len(self._incompatible_pairs)
        parts = []
        if total:
            parts.append(f"{total} Regel{'n' if total != 1 else ''}")
        if ic:
            parts.append(f"{ic} Paar{'e' if ic != 1 else ''}")
        suffix = f"  ({', '.join(parts)})" if parts else "  (keine)"
        if hasattr(self, "_sigil_rules_btn"):
            self._sigil_rules_btn.config(text=f"⚡  Sigil Regeln{suffix}  …")

    def _open_sigil_rules_editor(self):
        from random_builder.ui.sigil_rules_editor import SigilRulesEditor

        bt_names = [r["block_type"] for r in self._gen_config.get("block_rules", [])
                    if r.get("block_type")]
        if not bt_names:
            bt_names = list(BOX_TYPES)

        all_eids = []
        if self._content_data:
            try:
                all_eids = sorted(
                    item["id"] for item in self._content_data.get("Effect", [])
                    if item.get("id")
                )
            except Exception:
                all_eids = []

        def _on_save(new_rules, new_incompat):
            self._sigil_rules_data      = new_rules
            self._incompatible_pairs    = new_incompat
            self._update_sigil_rules_btn()
            self._schedule_autosave()

        SigilRulesEditor(
            self.winfo_toplevel(),
            sigil_rules       = self._sigil_rules_data,
            incompatible_pairs= self._incompatible_pairs,
            block_types       = bt_names,
            containers        = self._containers or {},
            effect_ids        = all_eids,
            on_save           = _on_save,
        )

    # ── Content/cost rule helpers ────────────────────────────────────────────

    def _rebuild_content_rules(self):
        for w in self._content_rules_frame.winfo_children():
            w.destroy()
        self._vars["content_rules"] = {}
        self._content_rule_types = {}

        saved_probs = {}
        for r in self._gen_config.get("content_rules", []):
            if "container" in r:
                saved_probs[r["container"]] = r["probability"]
            elif "effect_id" in r:
                saved_probs[r["effect_id"]] = r["probability"]
        saved_probs.update(self._content_probs)

        if self._containers:
            tk.Label(self._content_rules_frame, text="Container:",
                     bg="#1a1a1a", fg="#888",
                     font=("Arial", 7, "bold italic")).pack(anchor="w", padx=2)
            for cid in sorted(self._containers.keys()):
                self._add_rule_row(self._content_rules_frame, cid,
                                   saved_probs.get(cid, 1.0), kind="container",
                                   fg="#88ccff")

        _type_cfg = [
            ("Effect",    "effects",    "#88ff88", "effect"),
            ("Cost",      "costs",      "#ffaa44", "cost"),
            ("Condition", "conditions", "#88aaff", "condition"),
            ("Trigger",   "triggers",   "#ff88cc", "trigger"),
        ]
        for ctype, list_key, color, kind in _type_cfg:
            in_containers = set()
            for cont in self._containers.values():
                in_containers.update(cont.get(list_key, []))

            all_ids = [item["id"] for item in self._content_data.get(ctype, [])]
            ungrouped = [iid for iid in all_ids if iid not in in_containers]
            if not ungrouped:
                continue
            tk.Label(self._content_rules_frame,
                     text=f"Einzelne {ctype}s (kein Container):",
                     bg="#1a1a1a", fg=color,
                     font=("Arial", 7, "bold italic")).pack(
                anchor="w", padx=2, pady=(4, 0))
            for iid in ungrouped:
                self._add_rule_row(self._content_rules_frame, iid,
                                   saved_probs.get(iid, 1.0), kind=kind, fg="#cccccc")

    def _add_rule_row(self, parent, key: str, prob: float, kind: str, fg: str):
        row = tk.Frame(parent, bg="#1a1a1a")
        row.pack(fill="x", pady=1)
        tk.Label(row, text=key, bg="#1a1a1a", fg=fg,
                 width=18, anchor="w", font=("Arial", 8)).pack(side="left")
        v = tk.StringVar(value=str(prob))
        self._vars["content_rules"][key] = v
        self._content_rule_types[key] = kind

        def _on_prob_change(*_, k=key, var=v):
            try:
                self._content_probs[k] = float(var.get())
                from random_builder.models import save_content_probs
                save_content_probs(self._content_probs)
            except ValueError:
                pass

        v.trace_add("write", _on_prob_change)
        v.trace_add("write", self._schedule_autosave)
        tk.Entry(row, textvariable=v, width=6,
                 bg="#2a2a2a", fg="white", font=("Arial", 8)).pack(side="left", padx=2)

    def _rebuild_cost_rules(self):
        for w in self._cost_rules_frame.winfo_children():
            w.destroy()
        self._vars["cost_rules"] = {}

        rules = {r["cost_id"]: r["probability"]
                 for r in self._gen_config.get("cost_rules", [])}

        cost_ids = [item["id"] for item in self._content_data.get("Cost", [])]
        for cid in cost_ids:
            row = tk.Frame(self._cost_rules_frame, bg="#1a1a1a")
            row.pack(fill="x", pady=1)
            tk.Label(row, text=cid, bg="#1a1a1a", fg="#ccc",
                     width=16, anchor="w", font=("Arial", 8)).pack(side="left")
            v = tk.StringVar(value=str(rules.get(cid, 0.0)))
            v.trace_add("write", self._schedule_autosave)
            self._vars["cost_rules"][cid] = v
            tk.Entry(row, textvariable=v, width=6,
                     bg="#2a2a2a", fg="white", font=("Arial", 8)).pack(
                side="left", padx=2)

    def _reload_containers_cb(self):
        self._on_reload()
        self._rebuild_content_rules()

    # ── Autosave ─────────────────────────────────────────────────────────────

    def _schedule_autosave(self, *_):
        if self._autosave_job:
            self.after_cancel(self._autosave_job)
        self._autosave_job = self.after(800, lambda: self._on_autosave())

    def set_status(self, msg: str, color: str = "#1a1a1a"):
        try:
            self._status.config(text=msg, bg=color,
                                fg="white" if color != "#1a1a1a" else "#aaa")
            self.after(4000, lambda: self.set_status(""))
        except (tk.TclError, AttributeError):
            pass

    def _sep(self, parent):
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=6)

    # ── Config collection ────────────────────────────────────────────────────

    def collect_config(self) -> dict:
        """Read all Tk vars and return a gen_config dict."""
        cfg = dict(self._gen_config)

        try:
            cfg["count"] = int(self._vars["count"].get())
        except Exception:
            pass

        if self.profile == "Recipes":
            cfg["recipe_type_mode"] = self._vars.get("recipe_type_mode", tk.StringVar()).get()
            rtw = {}
            for rt, v in self._vars.get("rt_weights", {}).items():
                try:
                    rtw[rt] = float(v.get())
                except Exception:
                    rtw[rt] = 10.0
            cfg["recipe_type_weights"] = rtw
            for key in ("ingredient_max", "ingredient_cv"):
                try:
                    cfg[key] = int(self._vars[key].get())
                except Exception:
                    pass
            try:
                cfg["ingredient_avg"] = float(self._vars["ingredient_avg"].get())
            except Exception:
                pass
        elif "element_mode" in self._vars:
            cfg["element_mode"] = self._vars["element_mode"].get()
            ew = {}
            for el, v in self._vars.get("el_weights", {}).items():
                try:
                    ew[el] = float(v.get())
                except Exception:
                    ew[el] = 10.0
            cfg["custom_element_weights"] = ew

            # H: persist element_count_weights too
            ec = {}
            for n_str, v in self._vars.get("element_count_weights", {}).items():
                try:
                    ec[n_str] = float(v.get())
                except Exception:
                    ec[n_str] = 0.0
            # only keep entries with non-zero weight
            ec = {k: w for k, w in ec.items() if w > 0}
            if ec:
                cfg["element_count_weights"] = ec

        # Block rules
        block_rules = []
        for bt, v in self._vars.get("block_rules", {}).items():
            try:
                p = float(v.get())
            except Exception:
                p = 0.0
            if p > 0:
                block_rules.append({"block_type": bt, "probability": p})
        cfg["block_rules"] = block_rules

        # Content rules
        content_rules = []
        for key, v in self._vars.get("content_rules", {}).items():
            try:
                p = float(v.get())
            except Exception:
                p = 0.0
            if p > 0:
                kind = self._content_rule_types.get(key, "container")
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

        # Cost rules
        cost_rules = []
        for cid, v in self._vars.get("cost_rules", {}).items():
            try:
                p = float(v.get())
            except Exception:
                p = 0.0
            if p > 0:
                cost_rules.append({"cost_id": cid, "probability": p})
        cfg["cost_rules"] = cost_rules

        # Scalar vars
        float_keys = ["cv_target", "cv_per_box_max", "cv_card_min",
                       "cv_per_sigil_min",
                       "mana_chance", "condition_chance", "choose_n_chance",
                       "chance_choose", "chance_enhance",
                       "chance_doublecast", "chance_multicast",
                       "chance_no_subsigil"]
        int_keys = ["mana_main_count", "mana_max_count", "max_other_costs",
                     "max_effects", "min_effects", "min_blocks"]
        for key in float_keys:
            if key in self._vars:
                try:
                    cfg[key] = float(self._vars[key].get())
                except Exception:
                    pass
        for key in int_keys:
            if key in self._vars:
                try:
                    cfg[key] = int(self._vars[key].get())
                except Exception:
                    pass

        # Sigil rules
        try:
            sigil_rules = {}
            for bt, rules in self._sigil_rules_data.items():
                clean = [{k: v for k, v in r.items() if k != "_vars"} for r in rules]
                if clean:
                    sigil_rules[bt] = clean
            cfg["sigil_rules"] = sigil_rules
            cfg["incompatible_pairs"] = [list(p) for p in self._incompatible_pairs]
        except AttributeError:
            pass

        # Sigil constraints — managed by SigilConstraintsWindow, already in _gen_config
        cfg["sigil_constraints"] = self._gen_config.get("sigil_constraints", {})

        return cfg
