"""
content_editor.py – ContentEditor window and sub-dialogs.
"""

import json as _json
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox


def _get_generator_profiles():
    try:
        _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if _root not in sys.path:
            sys.path.insert(0, _root)
        from random_builder.models import GENERATOR_PROFILES
        return GENERATOR_PROFILES
    except Exception:
        return ["Spells", "Prowess", "Recipes"]


def _get_recipe_types():
    try:
        _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if _root not in sys.path:
            sys.path.insert(0, _root)
        from random_builder.models import RECIPE_TYPES
        return RECIPE_TYPES
    except Exception:
        return ["Potions", "Phials", "Tinctures"]

_HERE = os.path.dirname(os.path.abspath(__file__))

from CardContent.template_parser import (
    parse_template, render_content_text,
    make_default_stat, sync_item_template,
    collect_all_ids, find_references,
    rename_id_everywhere, rename_content_id,
)
from CardContent.window_memory import wm
from CardContent.template_syntax_help import SyntaxHelpWindow

from card_builder.constants import BOX_TYPES, ELEMENTS

DEFAULT_ELEMENT_WEIGHT = 10   # used by auto-generator when field is empty


def get_element_weight(weights: dict, el: str) -> float:
    """Return element weight, falling back to DEFAULT_ELEMENT_WEIGHT if missing/empty."""
    v = weights.get(el, "")
    if v == "" or v is None:
        return DEFAULT_ELEMENT_WEIGHT
    try:
        return float(v)
    except (ValueError, TypeError):
        return DEFAULT_ELEMENT_WEIGHT


class ContentEditor(tk.Toplevel):

    def __init__(self, parent, item: dict, data: dict, on_save=None):
        super().__init__(parent)
        self.item         = item
        self.data         = data
        self.on_save      = on_save
        self._original_id = item.get("id", "")
        self.title(f"Edit – {item.get('id', '?')}")
        wm.restore(self, "content_editor", "860x700")
        self._build()

    # ── Scrollable layout ──────────────────────────────────────────────────────

    def _build(self):
        outer = tk.Frame(self)
        outer.pack(fill="both", expand=True)
        vsb   = tk.Scrollbar(outer, orient="vertical")
        vsb.pack(side="right", fill="y")
        canvas = tk.Canvas(outer, yscrollcommand=vsb.set, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        vsb.config(command=canvas.yview)

        self._f  = tk.Frame(canvas)
        win_id   = canvas.create_window((0, 0), window=self._f, anchor="nw")
        self._f.bind("<Configure>",
                     lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        self._f.columnconfigure(1, weight=1)
        self._row = 0
        # Sync variables/options from the sigil template on every open,
        # so items created before this feature existed get their {X} detected.
        sync_item_template(self.item)
        self._build_basic_fields()
        self._sep()
        self._build_var_section()
        self._sep()
        self._build_opt_section()
        self._sep()
        self._build_allowed_blocks_section()
        self._sep()
        tk.Button(self._f, text="💾 Save", command=self._save,
                  bg="#1a6e3c", fg="white", font=("Arial", 10, "bold"),
                  width=20).grid(row=self._row, column=0, columnspan=6, pady=14)

    def _sep(self):
        ttk.Separator(self._f, orient="horizontal").grid(
            row=self._row, column=0, columnspan=6, sticky="ew", pady=6)
        self._row += 1

    # ── Basic fields ───────────────────────────────────────────────────────────

    def _build_basic_fields(self):
        def lbl(text):
            tk.Label(self._f, text=text, font=("Arial", 9, "bold")).grid(
                row=self._row, column=0, sticky="w", padx=8, pady=3)

        lbl("ID")
        self._id_var = tk.StringVar(value=self.item.get("id", ""))
        tk.Entry(self._f, textvariable=self._id_var, width=36).grid(
            row=self._row, column=1, columnspan=3, sticky="we", padx=8, pady=3)
        tk.Button(self._f, text="⧉",
                  command=lambda: (self.clipboard_clear(),
                                   self.clipboard_append(self._id_var.get()),
                                   self._flash(f"Kopiert: {self._id_var.get()}")),
                  font=("Arial", 8), padx=2, pady=0).grid(
            row=self._row, column=4, sticky="w", padx=2)
        tk.Label(self._f, text="(Umbenennen propagiert alle Child-IDs)",
                 fg="#888", font=("Arial", 8)).grid(
            row=self._row, column=5, sticky="w", padx=4)
        self._row += 1

        lbl("Content Box")
        self._cb_var = tk.StringVar(value=self.item.get("sigil", ""))  # stored as "sigil"
        tk.Entry(self._f, textvariable=self._cb_var, width=52).grid(
            row=self._row, column=1, columnspan=4, sticky="we", padx=8, pady=3)
        tk.Button(self._f, text="?", command=lambda: SyntaxHelpWindow(self),
                  font=("Arial", 9, "bold"), width=2,
                  bg="#334", fg="#88ccff").grid(row=self._row, column=5, padx=2)
        self._cb_var.trace_add("write", self._on_cb_change)
        self._row += 1

        lbl("Content Text")
        self._ct_var = tk.StringVar(value=self.item.get("content_text", ""))
        ct_f = tk.Frame(self._f)
        ct_f.grid(row=self._row, column=1, columnspan=5, sticky="we", padx=8, pady=3)
        tk.Entry(ct_f, textvariable=self._ct_var, width=52).pack(
            side="left", fill="x", expand=True)
        tk.Button(ct_f, text="↺", command=self._scaffold_content_text,
                  font=("Arial", 8), width=2).pack(side="left", padx=2)
        tk.Button(ct_f, text="?", command=lambda: SyntaxHelpWindow(self),
                  font=("Arial", 9, "bold"), width=2,
                  bg="#334", fg="#88ccff").pack(side="left", padx=2)
        self._row += 1

        lbl("Reminder Text")
        self._rt_var = tk.StringVar(value=self.item.get("reminder_text", ""))
        rt_f = tk.Frame(self._f)
        rt_f.grid(row=self._row, column=1, columnspan=5, sticky="we", padx=8, pady=3)
        tk.Entry(rt_f, textvariable=self._rt_var, width=52).pack(
            side="left", fill="x", expand=True)
        tk.Button(rt_f, text="?", command=lambda: SyntaxHelpWindow(self),
                  font=("Arial", 9, "bold"), width=2,
                  bg="#334", fg="#88ccff").pack(side="left", padx=2)
        self._row += 1

        lbl("Rarity")
        self._rar_var = tk.StringVar(value=str(self.item.get("rarity", 10)))
        tk.Entry(self._f, textvariable=self._rar_var, width=10).grid(
            row=self._row, column=1, sticky="w", padx=8, pady=3)
        self._row += 1

        lbl("Complexity Base")
        self._cpx_var = tk.StringVar(value=str(self.item.get("complexity_base", 1.0)))
        tk.Entry(self._f, textvariable=self._cpx_var, width=10).grid(
            row=self._row, column=1, sticky="w", padx=8, pady=3)
        self._row += 1

        # CV – single item-level constant (no polynomial terms at item level)
        lbl("CV")
        # Backward-compat: fall back to cv1 if cv not present
        _cv_raw = self.item.get("cv", self.item.get("cv1", ""))
        self._cv_var = tk.StringVar(
            value="" if (_cv_raw == "" or _cv_raw is None) else str(_cv_raw))
        tk.Entry(self._f, textvariable=self._cv_var, width=10).grid(
            row=self._row, column=1, sticky="w", padx=8, pady=3)
        tk.Label(self._f, text="(Konstanter Basiswert, unabhängig von Variablen)",
                 fg="#888", font=("Arial", 8)).grid(
            row=self._row, column=2, columnspan=3, sticky="w", padx=4)
        self._row += 1

        bf = tk.Frame(self._f)
        bf.grid(row=self._row, column=1, columnspan=5, sticky="w", padx=8, pady=4)
        tk.Button(bf, text="◈ Effect Conditions",
                  command=self._edit_effect_conditions,
                  bg="#553300", fg="white").pack(side="left", padx=4)
        self._row += 1

        # ── Primary Types (target types this effect is valid for) ─────────────
        _PRIMARY_TYPES = ["Target Enemy", "Target Ally", "Non Targeting", "Target Neutral"]
        tk.Label(self._f, text="Primary Types", font=("Arial", 9, "bold")).grid(
            row=self._row, column=0, sticky="nw", padx=8, pady=3)
        pt_frame = tk.Frame(self._f)
        pt_frame.grid(row=self._row, column=1, columnspan=5, sticky="w", padx=8, pady=3)
        self._primary_type_vars = {}
        current_pts = self.item.get("primary_types", [])
        for pt in _PRIMARY_TYPES:
            var = tk.BooleanVar(value=(pt in current_pts))
            self._primary_type_vars[pt] = var
            color = {"Target Enemy": "#cc4444", "Target Ally": "#44aa44",
                     "Non Targeting": "#aaaaaa", "Target Neutral": "#aaaa44"}.get(pt, "#888")
            tk.Checkbutton(pt_frame, text=pt, variable=var,
                           fg=color, font=("Arial", 9), selectcolor="#222").pack(
                side="left", padx=6)
        self._row += 1

        # ── Collapsible weights section ────────────────────────────────────────
        self._build_weights_section()

    def _build_weights_section(self):
        """Collapsible generator weights section.

        Layout: 3 columns (Spells | Prowess | Recipes)
        Each column has a checkbox at top (allowed for this generator),
        and below it the subcategory weights for that generator
        (elements for Spells, nothing for Prowess, recipe types for Recipes).
        """
        _state_key = "weights_open"
        is_open = self.item.get(_state_key, False)

        container = tk.Frame(self._f, relief="groove", bd=1)
        container.grid(row=self._row, column=0, columnspan=6,
                       sticky="ew", padx=8, pady=4)
        self._row += 1

        header = tk.Frame(container, bg="#1a1a2a")
        header.pack(fill="x")

        self._weights_open = tk.BooleanVar(value=is_open)
        self._weights_body = tk.Frame(container)

        def _toggle():
            if self._weights_open.get():
                self._weights_body.pack(fill="x", padx=8, pady=4)
                toggle_btn.config(text="▼  Generator Gewichtungen")
            else:
                self._weights_body.pack_forget()
                toggle_btn.config(text="▶  Generator Gewichtungen")
            self.item[_state_key] = self._weights_open.get()

        toggle_btn = tk.Button(
            header,
            text=("▼" if is_open else "▶") + "  Generator Gewichtungen",
            command=lambda: (
                self._weights_open.set(not self._weights_open.get()),
                _toggle()
            ),
            bg="#1a1a2a", fg="#aaaacc",
            font=("Arial", 9, "bold"), relief="flat", anchor="w",
        )
        toggle_btn.pack(fill="x", padx=4, pady=4)

        body = self._weights_body

        tk.Label(body,
                 text="Checkbox an = erlaubt für diesen Generator (aus = kommt dort nie vor).  "
                      "Gewicht: leer = Standard (10), 0 = nie.",
                 fg="#888", font=("Arial", 8)).pack(anchor="w", pady=(2, 4))

        _profiles = _get_generator_profiles()
        _recipe_types = _get_recipe_types()
        allowed_ct = self.item.get("allowed_card_types", [])
        el_weights = self.item.get("element_weights", {})
        rt_weights = self.item.get("recipe_type_weights", {})

        # 3-column grid
        cols_frame = tk.Frame(body)
        cols_frame.pack(fill="x")
        for c in range(3):
            cols_frame.columnconfigure(c, weight=1)

        self._allowed_ct_vars = {}
        self._el_vars    = {}
        self._el_weights = {}
        self._rt_weights = {}

        def _make_gen_header(parent, label: str, var: tk.BooleanVar,
                             fg: str, hdr_bg: str):
            """Render the clickable enable-header for a generator column."""
            hdr = tk.Frame(parent, bg=hdr_bg)
            hdr.pack(fill="x")
            tk.Checkbutton(hdr, text=label, variable=var,
                           font=("Arial", 10, "bold"), fg=fg,
                           bg=hdr_bg, activebackground=hdr_bg,
                           selectcolor="#ffffff", cursor="hand2",
                           padx=6, pady=4).pack(anchor="w")

        # ── Column 0: Spells ──────────────────────────────────────────────────
        spells_col = tk.Frame(cols_frame, relief="ridge", bd=1)
        spells_col.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        enabled = ("Spells" in allowed_ct) if allowed_ct else True
        sv = tk.BooleanVar(value=enabled)
        self._allowed_ct_vars["Spells"] = sv
        _make_gen_header(spells_col, "Spells", sv, "#5588cc", "#e8eef8")

        ttk.Separator(spells_col, orient="horizontal").pack(fill="x", padx=4, pady=2)

        for el in ELEMENTS:
            row_f = tk.Frame(spells_col)
            row_f.pack(fill="x", padx=4, pady=1)
            tk.Label(row_f, text=el, width=7, anchor="w",
                     font=("Arial", 8)).pack(side="left")
            raw_w = el_weights.get(el, "")
            wv = tk.StringVar(value="" if raw_w == "" or raw_w is None
                              or raw_w == 0 else str(raw_w))
            self._el_weights[el] = wv
            tk.Entry(row_f, textvariable=wv, width=5,
                     font=("Arial", 8)).pack(side="left", padx=2)

        # ── Column 1: Prowess ─────────────────────────────────────────────────
        prowess_col = tk.Frame(cols_frame, relief="ridge", bd=1)
        prowess_col.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)

        enabled = ("Prowess" in allowed_ct) if allowed_ct else True
        pv = tk.BooleanVar(value=enabled)
        self._allowed_ct_vars["Prowess"] = pv
        _make_gen_header(prowess_col, "Prowess", pv, "#cc6633", "#f8ece4")

        ttk.Separator(prowess_col, orient="horizontal").pack(fill="x", padx=4, pady=2)
        tk.Label(prowess_col, text="(keine Subtypen)",
                 fg="#666", font=("Arial", 8, "italic")).pack(anchor="w", padx=8, pady=4)

        # ── Column 2: Recipes ─────────────────────────────────────────────────
        recipes_col = tk.Frame(cols_frame, relief="ridge", bd=1)
        recipes_col.grid(row=0, column=2, sticky="nsew", padx=2, pady=2)

        enabled = ("Recipes" in allowed_ct) if allowed_ct else True
        rv = tk.BooleanVar(value=enabled)
        self._allowed_ct_vars["Recipes"] = rv
        _make_gen_header(recipes_col, "Recipes", rv, "#cc8833", "#f8efe0")

        ttk.Separator(recipes_col, orient="horizontal").pack(fill="x", padx=4, pady=2)

        for rt in _recipe_types:
            row_f = tk.Frame(recipes_col)
            row_f.pack(fill="x", padx=4, pady=1)
            tk.Label(row_f, text=rt, width=9, anchor="w",
                     font=("Arial", 8)).pack(side="left")
            raw_w = rt_weights.get(rt, "")
            wv = tk.StringVar(value="" if raw_w == "" or raw_w is None
                              else str(raw_w))
            self._rt_weights[rt] = wv
            tk.Entry(row_f, textvariable=wv, width=5,
                     font=("Arial", 8)).pack(side="left", padx=2)

        # Show/hide body based on initial state
        if is_open:
            self._weights_body.pack(fill="x", padx=8, pady=4)

    def _scaffold_content_text(self):
        """
        Generate a conditional content-text scaffold from the content-box template.

        For each {X} variable  →  [if X=1]...[else]{X}[/if]
        For each [a,b,c] option →  [if OPT0=a]a[elif OPT0=b]b[else]c[/if]

        Called by the ↺ button.  Overwrites whatever is currently in Content Text.
        """
        sigil = self._cb_var.get().strip()
        if not sigil:
            return
        parsed = parse_template(sigil)
        parts: list[str] = []

        # ── Variables ─────────────────────────────────────────────────────────
        for var in parsed["variables"]:
            parts.append(f"[if {var}=1]...[else]{{{var}}}[/if]")

        # ── Options ───────────────────────────────────────────────────────────
        for i, choices in enumerate(parsed["options"]):
            if not choices:
                continue
            opt = f"OPT{i}"
            if len(choices) == 1:
                parts.append(choices[0])
            elif len(choices) == 2:
                a, b = choices
                parts.append(f"[if {opt}={a}]{a}[else]{b}[/if]")
            else:
                # First choice
                scaffold = f"[if {opt}={choices[0]}]{choices[0]}"
                # Middle choices
                for c in choices[1:-1]:
                    scaffold += f"[elif {opt}={c}]{c}"
                # Last choice via [else]
                scaffold += f"[else]{choices[-1]}[/if]"
                parts.append(scaffold)

        self._ct_var.set(" ".join(parts) if parts else sigil)

    # ── Sections ───────────────────────────────────────────────────────────────

    def _build_var_section(self):
        tk.Label(self._f, text="Variables  {X}",
                 font=("Arial", 10, "bold"), fg="#5588cc").grid(
            row=self._row, column=0, sticky="w", padx=8)
        self._row += 1
        self._var_frame = tk.Frame(self._f)
        self._var_frame.grid(row=self._row, column=0, columnspan=6,
                             sticky="ew", padx=8)
        self._row += 1
        self._rebuild_vars()

    def _build_opt_section(self):
        tk.Label(self._f, text="Options  [a, b, c]",
                 font=("Arial", 10, "bold"), fg="#cc8833").grid(
            row=self._row, column=0, sticky="w", padx=8)
        self._row += 1
        self._opt_frame = tk.Frame(self._f)
        self._opt_frame.grid(row=self._row, column=0, columnspan=6,
                             sticky="ew", padx=8)
        self._row += 1
        self._rebuild_opts()

    def _on_cb_change(self, *_):
        self.item["sigil"] = self._cb_var.get()
        sync_item_template(self.item)
        self._rebuild_vars()
        self._rebuild_opts()

    def _build_allowed_blocks_section(self):
        """Build checkbox section for allowed_in_blocks."""
        # Use centrally-defined BOX_TYPES (imported at top of file)
        block_types = list(BOX_TYPES)

        # Initialize missing fields with default True (all enabled)
        allowed_blocks = self.item.setdefault("allowed_in_blocks", {})
        for bt in block_types:
            allowed_blocks.setdefault(bt, True)

        # Header with toggle-all buttons
        hdr_frame = tk.Frame(self._f, bg=self._f.cget("bg"))
        hdr_frame.grid(row=self._row, column=0, columnspan=6,
                       sticky="ew", padx=8, pady=(4, 2))
        tk.Label(hdr_frame, text="Allowed in Block Types",
                 font=("Arial", 10, "bold"), fg="#88ccff").pack(side="left")
        tk.Button(hdr_frame, text="All", font=("Arial", 8),
                  command=lambda: self._toggle_all_blocks(True),
                  padx=6).pack(side="right", padx=2)
        tk.Button(hdr_frame, text="None", font=("Arial", 8),
                  command=lambda: self._toggle_all_blocks(False),
                  padx=6).pack(side="right", padx=2)
        self._row += 1

        # Create a frame with checkboxes in a grid (3 columns)
        cb_frame = tk.Frame(self._f, bg=self._f.cget("bg"))
        cb_frame.grid(row=self._row, column=0, columnspan=6,
                      sticky="ew", padx=8, pady=4)

        self._allowed_block_vars = {}
        for idx, block_type in enumerate(block_types):
            # Create checkbox variable
            var = tk.BooleanVar(value=allowed_blocks.get(block_type, True))
            self._allowed_block_vars[block_type] = var

            # Create checkbox with callback
            def make_callback(bt):
                def callback():
                    self.item["allowed_in_blocks"][bt] = self._allowed_block_vars[bt].get()
                return callback

            cb = tk.Checkbutton(cb_frame, text=block_type, variable=var,
                               command=make_callback(block_type),
                               font=("Arial", 9))
            # Place in 3-column grid
            col = idx % 3
            row_offset = idx // 3
            cb.grid(row=row_offset, column=col, sticky="w", padx=4, pady=2)

        self._row += (len(block_types) + 2) // 3 + 1

    def _toggle_all_blocks(self, value: bool) -> None:
        """Set all block type checkboxes to the given value."""
        if not hasattr(self, "_allowed_block_vars"):
            return
        for bt, var in self._allowed_block_vars.items():
            var.set(value)
            self.item.setdefault("allowed_in_blocks", {})[bt] = value

    # ── Stat header & row ──────────────────────────────────────────────────────

    # Grid-column pixel minsizes shared between header and every data row.
    # Columns: Name | Prefix | ID-entry | CopyBtn | Rarity | Cmplx | ×x | ×x² | ×x³ | Cond | 🎲? | 🎲! | Del
    _SC = [80, 98, 78, 26, 56, 56, 56, 56, 56, 50, 38, 38, 26]

    @staticmethod
    def _apply_stat_cols(frame):
        for i, ms in enumerate(ContentEditor._SC):
            frame.columnconfigure(i, minsize=ms)

    def _stat_header(self, parent, stat_type: str = "variable"):
        hdr = tk.Frame(parent)
        hdr.pack(fill="x", pady=(2, 0))
        self._apply_stat_cols(hdr)
        # "ID" always spans the prefix + entry columns
        tk.Label(hdr, text="ID", font=("Arial", 8, "bold"),
                 anchor="w").grid(row=0, column=1, columnspan=2, sticky="w", padx=2)
        if stat_type == "variable":
            # Variables: no Rarity (always picked); polynomial CV coefficients
            label_cols = [
                (0,  "Name"),
                (5,  "Cmplx"),
                (6,  "×x"),
                (7,  "×x²"),
                (8,  "×x³"),
                (10, "🎲?"),
                (11, "🎲!"),
            ]
        else:  # "choice" – options are selected, not evaluated as polynomial
            label_cols = [
                (0,  "Name"),
                (4,  "Rarity"),
                (5,  "Cmplx"),
                (6,  "CV"),
            ]
        for col, txt in label_cols:
            tk.Label(hdr, text=txt, font=("Arial", 8, "bold"),
                     anchor="w").grid(row=0, column=col, sticky="w", padx=2)

    def _stat_row(self, parent, label: str, label_color: str,
                  stat: dict,
                  stat_type: str = "variable",
                  choices: list  = None,
                  can_delete: bool = False,
                  on_delete = None,
                  id_prefix: str = ""):

        row = tk.Frame(parent, relief="groove", bd=1)
        row.pack(fill="x", pady=1)
        self._apply_stat_cols(row)

        # Col 0 – Name label
        tk.Label(row, text=label, fg=label_color,
                 font=("Arial", 9, "bold"), anchor="w").grid(
            row=0, column=0, sticky="w", padx=4, pady=2)

        full_id = stat.get("id", "")
        ext_val = full_id[len(id_prefix):] if (id_prefix and full_id.startswith(id_prefix)) else full_id

        # Col 1 – Prefix label (with tooltip)
        if id_prefix:
            display_pfx = id_prefix if len(id_prefix) <= 14 else "…" + id_prefix[-12:]
            pfx_lbl = tk.Label(row, text=display_pfx, fg="#666688",
                               font=("Arial", 7), anchor="e")
            pfx_lbl.grid(row=0, column=1, sticky="ew", padx=(2, 0))
            def _enter(e, w=pfx_lbl, full=id_prefix):
                w._tip = tk.Toplevel(w); w._tip.wm_overrideredirect(True)
                x, y = w.winfo_rootx(), w.winfo_rooty() + 18
                w._tip.geometry(f"+{x}+{y}")
                tk.Label(w._tip, text=full, bg="#333355", fg="white",
                         font=("Arial", 8), relief="solid", bd=1).pack()
            def _leave(e, w=pfx_lbl):
                if hasattr(w, "_tip"): w._tip.destroy(); del w._tip
            pfx_lbl.bind("<Enter>", _enter)
            pfx_lbl.bind("<Leave>", _leave)

        # Col 2 – ID entry
        id_var   = tk.StringVar(value=ext_val)
        id_entry = tk.Entry(row, textvariable=id_var, width=10,
                            font=("Arial", 8), fg="#aaaaff", bg="#1a1a2e")
        id_entry.grid(row=0, column=2, sticky="ew", padx=2, pady=1)

        # Col 3 – Copy button
        def _copy_id(fid=full_id):
            self.clipboard_clear()
            self.clipboard_append(fid)
            self._flash(f"Kopiert: {fid}")
        tk.Button(row, text="⧉", command=_copy_id,
                  font=("Arial", 7), padx=1, pady=0).grid(row=0, column=3, padx=1)

        old_ref = [full_id]

        def _on_id(_e, s=stat, iv=id_var, ref=old_ref, pfx=id_prefix):
            ext = iv.get().strip()
            new = pfx + ext if pfx else ext
            old = ref[0]
            if ext and new != old:
                n = rename_id_everywhere(old, new, self.data)
                s["id"] = new
                ref[0]  = new
                if n:
                    self._flash(f"'{old}' → '{new}'  ({n} Refs aktualisiert)")

        id_entry.bind("<FocusOut>", _on_id)
        id_entry.bind("<Return>",   _on_id)

        # Cols 4-8 – numeric stat fields (layout depends on stat_type)
        if stat_type == "variable":
            # Variables are always used → no Rarity; polynomial CV coefficients
            fields = [
                ("complexity", tk.StringVar(value=str(stat.get("complexity", 1.0))), 5),
                ("cv1",        tk.StringVar(value=str(stat.get("cv1", 1.0))),        6),
                ("cv2",        tk.StringVar(value=str(stat.get("cv2", 0.0))),        7),
                ("cv3",        tk.StringVar(value=str(stat.get("cv3", 0.0))),        8),
            ]
            casts = {"complexity": float, "cv1": float, "cv2": float, "cv3": float}
        else:
            # Choices are selected, not evaluated as a polynomial → single flat CV
            _cv_init = stat.get("cv", stat.get("cv1", 0.0))
            fields = [
                ("rarity",     tk.StringVar(value=str(stat.get("rarity", 10))),   4),
                ("complexity", tk.StringVar(value=str(stat.get("complexity", 1.0))), 5),
                ("cv",         tk.StringVar(value=str(_cv_init)),                  6),
            ]
            casts = {"rarity": int, "complexity": float, "cv": float}

        def _trace(*_, s=stat, fl=fields, ca=casts, st=stat_type):
            for key, var, _ in fl:
                try:    s[key] = ca[key](var.get())
                except: pass
            if st != "variable":
                # Remove legacy polynomial keys from choice stats
                for _k in ("cv1", "cv2", "cv3"):
                    s.pop(_k, None)

        for key, var, col in fields:
            var.trace_add("write", _trace)
            tk.Entry(row, textvariable=var, width=6).grid(
                row=0, column=col, sticky="ew", padx=1, pady=1)

        # Col 9 – Conditions button
        tk.Button(
            row, text="Cond.",
            command=lambda s=stat, st=stat_type, ch=choices: ConditionsEditor(
                self, s, self.data, stat_type=st, choices=ch or []),
            font=("Arial", 8)
        ).grid(row=0, column=9, padx=3, pady=1)

        # Cols 10-11 – Dice checkboxes (variables only)
        if stat_type == "variable":
            for col, (dk, dl) in zip([10, 11], [
                ("dice_allowed", "🎲?"),
                ("dice_only",    "🎲!"),
            ]):
                bv = tk.BooleanVar(value=bool(stat.get(dk, False)))
                bv.trace_add("write",
                             lambda *_, k=dk, v=bv, s=stat: s.__setitem__(k, v.get()))
                tk.Checkbutton(row, text=dl, variable=bv,
                               font=("Arial", 7),
                               activebackground="#2a2a3a").grid(
                    row=0, column=col, padx=1, pady=1)

        # Col 12 – Delete button
        if can_delete and on_delete:
            tk.Button(row, text="✕", fg="red",
                      command=lambda s=stat: on_delete(s),
                      font=("Arial", 8, "bold"), width=2).grid(
                row=0, column=12, padx=2)

    # ── Rebuild vars ───────────────────────────────────────────────────────────

    def _rebuild_vars(self):
        for w in self._var_frame.winfo_children():
            w.destroy()
        variables = self.item.get("variables", {})
        if not variables:
            tk.Label(self._var_frame, text="(none – use {X} in Content Box)",
                     fg="#888").pack(anchor="w", padx=4)
            return

        self._stat_header(self._var_frame, "variable")
        for vname, stat in variables.items():
            if not stat.get("id"):
                stat["id"] = f"{self.item.get('id', 'item')}.{vname}"

            def _del(s, n=vname):
                refs = find_references(s.get("id", ""), self.data)
                if refs:
                    messagebox.showerror("Löschen nicht möglich",
                        "Noch referenziert in:\n" +
                        "\n".join(r["location"] for r in refs))
                    return
                del self.item["variables"][n]
                self._cb_var.set(self._cb_var.get().replace(f"{{{n}}}", ""))
                self._rebuild_vars()

            self._stat_row(self._var_frame, label=f"{{{vname}}}",
                           label_color="#5588cc", stat=stat,
                           stat_type="variable", can_delete=True, on_delete=_del,
                           id_prefix=f"{self.item.get('id', 'item')}.")

    # ── Rebuild opts ───────────────────────────────────────────────────────────

    def _rebuild_opts(self):
        for w in self._opt_frame.winfo_children():
            w.destroy()
        options = self.item.get("options", {})
        if not options:
            tk.Label(self._opt_frame, text="(none – use [a, b, c] in Content Box)",
                     fg="#888").pack(anchor="w", padx=4)
            return

        for opt_key, opt in options.items():
            choices    = opt.get("choices", [])
            per_choice = opt.setdefault("per_choice", {})

            grp = tk.LabelFrame(self._opt_frame,
                                text=f"Option {opt_key}:  [{', '.join(choices)}]",
                                font=("Arial", 9, "bold"), fg="#cc8833")
            grp.pack(fill="x", pady=3)
            self._stat_header(grp, "choice")

            for choice in choices:
                stat = per_choice.setdefault(choice, make_default_stat())
                if not stat.get("id"):
                    stat["id"] = f"{self.item.get('id', 'item')}.{opt_key}.{choice}"

                def _del(s, c=choice, ok=opt_key):
                    refs = find_references(s.get("id", ""), self.data)
                    if refs:
                        messagebox.showerror("Löschen nicht möglich",
                            "Noch referenziert in:\n" +
                            "\n".join(r["location"] for r in refs))
                        return
                    self.item["options"][ok]["choices"].remove(c)
                    self.item["options"][ok]["per_choice"].pop(c, None)
                    if not self.item["options"][ok]["choices"]:
                        self.item["options"].pop(ok, None)
                    self._rebuild_opts()

                self._stat_row(grp, label=choice, label_color="#cc8833",
                               stat=stat, stat_type="choice", choices=choices,
                               id_prefix=f"{self.item.get('id', 'item')}.{opt_key}.",
                               can_delete=True, on_delete=_del)

    # ── Sub-editors ────────────────────────────────────────────────────────────

    def _edit_effect_conditions(self):
        ConditionsEditor(self, self.item, self.data, stat_type="effect")

    def _flash(self, msg: str):
        bar = tk.Label(self, text=msg, bg="#1a3e8e", fg="white", font=("Arial", 9))
        bar.pack(side="bottom", fill="x")
        self.after(3000, bar.destroy)

    # ── Save ───────────────────────────────────────────────────────────────────

    def _save(self):
        new_id = self._id_var.get().strip()
        old_id = self._original_id
        if new_id and new_id != old_id:
            n = rename_content_id(old_id, new_id, self.data)
            if n:
                self._flash(f"Content ID '{old_id}' → '{new_id}'  ({n} Änderungen)")

        self.item["id"]              = new_id
        self.item["sigil"]            = self._cb_var.get()
        self.item["content_text"]    = self._ct_var.get()
        self.item["reminder_text"]   = self._rt_var.get()
        try:    self.item["rarity"]          = int(self._rar_var.get())
        except: pass
        try:    self.item["complexity_base"] = float(self._cpx_var.get())
        except: pass

        # CV – single item-level constant; remove legacy cv1/cv2/cv3 keys
        _cv_raw = self._cv_var.get().strip()
        if _cv_raw:
            try:    self.item["cv"] = float(_cv_raw)
            except: pass
        else:
            self.item.pop("cv", None)
        for _legacy in ("cv1", "cv2", "cv3"):
            self.item.pop(_legacy, None)

        # Element weights (from collapsible section)
        if hasattr(self, "_el_weights"):
            ew = {}
            for el in ELEMENTS:
                raw = self._el_weights[el].get().strip()
                if raw:
                    try:    ew[el] = float(raw)
                    except: pass
            if ew:
                self.item["element_weights"] = ew
            else:
                self.item.pop("element_weights", None)

        # Recipe type weights
        if hasattr(self, "_rt_weights"):
            rtw = {}
            for rt, wv in self._rt_weights.items():
                raw = wv.get().strip()
                if raw:
                    try:    rtw[rt] = float(raw)
                    except: pass
            if rtw:
                self.item["recipe_type_weights"] = rtw
            else:
                self.item.pop("recipe_type_weights", None)

        # Primary types
        if hasattr(self, "_primary_type_vars"):
            selected_pts = [pt for pt, v in self._primary_type_vars.items() if v.get()]
            if selected_pts:
                self.item["primary_types"] = selected_pts
            else:
                self.item.pop("primary_types", None)

        # Generator type restrictions
        if hasattr(self, "_allowed_ct_vars"):
            _profiles = _get_generator_profiles()
            checked = [gp for gp, v in self._allowed_ct_vars.items() if v.get()]
            if set(checked) >= set(_profiles):
                # All checked = everywhere allowed = empty list
                self.item.pop("allowed_card_types", None)
            elif checked:
                self.item["allowed_card_types"] = checked
            else:
                # Nothing checked = treat as all allowed
                self.item.pop("allowed_card_types", None)

        # ── Write directly to disk (always, regardless of caller) ────────────
        self._flush_to_disk()

        self.destroy()
        if self.on_save:
            self.on_save()

    def _flush_to_disk(self):
        """Write every content type back to its JSON file immediately."""
        _FILES = {
            "Effect":    os.path.join(_HERE, "cc_data", "effects.json"),
            "Trigger":   os.path.join(_HERE, "cc_data", "triggers.json"),
            "Condition": os.path.join(_HERE, "cc_data", "conditions.json"),
            "Cost":      os.path.join(_HERE, "cc_data", "costs.json"),
            "Insert":    os.path.join(_HERE, "cc_data", "inserts.json"),
        }
        for type_name, path in _FILES.items():
            items = self.data.get(type_name)
            if items is None:
                continue
            try:
                with open(path, "w", encoding="utf-8") as f:
                    _json.dump({type_name: items}, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"[ContentEditor] Fehler beim Speichern {path}: {e}")


# ── Conditions Editor ──────────────────────────────────────────────────────────

class ConditionsEditor(tk.Toplevel):
    """
    stat_type:
        "effect"    – item-level (no var_min/max, no excluded_choices)
        "variable"  – has var_min / var_max
        "choice"    – has excluded_choices checklist
    """

    def __init__(self, parent, stat_or_item: dict, data: dict,
                 stat_type: str = "variable", choices: list = None):
        super().__init__(parent)
        self.data      = data
        self.stat_type = stat_type
        self.choices   = choices or []
        self.title({
            "effect":   "Effect Conditions",
            "variable": "Variable Conditions",
            "choice":   "Choice Conditions",
        }.get(stat_type, "Conditions"))
        wm.restore(self, "conditions_editor", "540x660")
        self.cond = stat_or_item.setdefault("conditions", {})
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._save_and_close)

    def _build(self):
        outer = tk.Frame(self)
        outer.pack(fill="both", expand=True)
        vsb   = tk.Scrollbar(outer, orient="vertical")
        vsb.pack(side="right", fill="y")
        canvas = tk.Canvas(outer, yscrollcommand=vsb.set, highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        vsb.config(command=canvas.yview)
        f = tk.Frame(canvas)
        wid = canvas.create_window((0, 0), window=f, anchor="nw")
        f.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(wid, width=e.width))
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
        f.columnconfigure(1, weight=1)
        row = 0

        # ── Mana range ────────────────────────────────────────────────────────
        tk.Label(f, text="Mana Kosten", font=("Arial", 9, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=8, pady=(8,2)); row += 1
        for label, key in [("Min", "min_mana"), ("Max", "max_mana")]:
            tk.Label(f, text=label).grid(row=row, column=0, sticky="w", padx=16)
            var = tk.StringVar(value=str(self.cond.get(key, "")))
            tk.Entry(f, textvariable=var, width=8).grid(
                row=row, column=1, sticky="w", padx=8)
            setattr(self, f"_{key}_var", var)
            row += 1

        ttk.Separator(f, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=6); row += 1

        # ── Variable min/max ──────────────────────────────────────────────────
        if self.stat_type == "variable":
            tk.Label(f, text="Variablen Wertebereich",
                     font=("Arial", 9, "bold")).grid(
                row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1
            tk.Label(f, text="Leer = kein Limit",
                     fg="#888", font=("Arial", 8)).grid(
                row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1
            for label, key in [("Min Wert", "var_min"), ("Max Wert", "var_max")]:
                tk.Label(f, text=label).grid(row=row, column=0, sticky="w", padx=16)
                var = tk.StringVar(value=str(self.cond.get(key, "")))
                tk.Entry(f, textvariable=var, width=8).grid(
                    row=row, column=1, sticky="w", padx=8)
                setattr(self, f"_{key}_var", var)
                row += 1
            ttk.Separator(f, orient="horizontal").grid(
                row=row, column=0, columnspan=3, sticky="ew", pady=6); row += 1

        # ── Excluded choices ──────────────────────────────────────────────────
        elif self.stat_type == "choice":
            tk.Label(f, text="Erlaubte Choices",
                     font=("Arial", 9, "bold")).grid(
                row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1
            tk.Label(f, text="Deaktiviert = wird nie vom Auto-Generator gewählt",
                     fg="#888", font=("Arial", 8)).grid(
                row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1
            excluded = self.cond.get("excluded_choices", [])
            self._choice_vars: dict = {}
            for c in self.choices:
                v = tk.BooleanVar(value=(c not in excluded))
                self._choice_vars[c] = v
                tk.Checkbutton(f, text=c, variable=v).grid(
                    row=row, column=0, columnspan=3, sticky="w", padx=16)
                row += 1
            ttk.Separator(f, orient="horizontal").grid(
                row=row, column=0, columnspan=3, sticky="ew", pady=6); row += 1

        # ── Element weights & allowed (variables/choices only) ───────────────
        # For effects the element weights live at item level (main editor's
        # "Kartentyp & Element Gewichtungen") which the generator reads directly.
        # Showing them here too would be a duplicate that the generator ignores.
        if self.stat_type != "effect":
            tk.Label(f, text="Elemente – Erlaubt & Häufigkeit",
                     font=("Arial", 9, "bold")).grid(
                row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1
            tk.Label(f,
                     text="☑ = erlaubt   Gewicht leer = Standard (10)   0 = nie",
                     fg="#888", font=("Arial", 8)).grid(
                row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1

            # header
            hdr = tk.Frame(f)
            hdr.grid(row=row, column=0, columnspan=3, sticky="w", padx=16); row += 1
            for txt, w in [("Element", 10), ("Erlaubt", 6), ("Gewicht", 8), ("", 12)]:
                tk.Label(hdr, text=txt, font=("Arial", 8, "bold"),
                         width=w, anchor="w").pack(side="left", padx=2)

            allowed         = self.cond.get("allowed_elements", [])
            stored_weights  = self.cond.get("element_weights", {})
            self._el_vars    = {}
            self._el_weights = {}

            el_f = tk.Frame(f)
            el_f.grid(row=row, column=0, columnspan=3, sticky="w", padx=16); row += 1

            for el in ELEMENTS:
                ef = tk.Frame(el_f)
                ef.pack(fill="x", pady=1)

                enabled = (el in allowed) if allowed else True
                v = tk.BooleanVar(value=enabled)
                self._el_vars[el] = v
                tk.Checkbutton(ef, text=el, variable=v, width=10,
                               anchor="w").pack(side="left")

                raw_w = stored_weights.get(el, "")
                wv = tk.StringVar(value="" if raw_w == "" or raw_w is None
                                  else str(raw_w))
                self._el_weights[el] = wv

                entry = tk.Entry(ef, textvariable=wv, width=6)
                entry.pack(side="left", padx=4)

                bar = tk.Label(ef, text="", bg="#1a6e3c", height=1, width=1)
                bar.pack(side="left", padx=2)

                def _upd(ev=None, b=bar, wvar=wv):
                    raw = wvar.get().strip()
                    try:    val = max(0, min(20, int(float(raw)))) if raw else DEFAULT_ELEMENT_WEIGHT
                    except: val = 0
                    b.config(width=max(1, val))

                wv.trace_add("write", lambda *_, fn=_upd: fn())
                _upd()

            ttk.Separator(f, orient="horizontal").grid(
                row=row, column=0, columnspan=3, sticky="ew", pady=6); row += 1

        # ── Allowed box types ─────────────────────────────────────────────────
        tk.Label(f, text="Erlaubte Sigil-Typen",
                 font=("Arial", 9, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1
        tk.Label(f, text="☑ = erlaubt   (leer = alle erlaubt)",
                 fg="#888", font=("Arial", 8)).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1

        allowed_bt = self.cond.get("allowed_box_types", [])
        self._bt_vars = {}
        bt_f = tk.Frame(f)
        bt_f.grid(row=row, column=0, columnspan=3, sticky="w", padx=16); row += 1
        for i, bt in enumerate(BOX_TYPES):
            enabled = (bt in allowed_bt) if allowed_bt else True
            v = tk.BooleanVar(value=enabled)
            self._bt_vars[bt] = v
            tk.Checkbutton(bt_f, text=bt, variable=v, anchor="w",
                           width=14).grid(row=i // 3, column=i % 3, sticky="w")

        ttk.Separator(f, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=6); row += 1

        # ── ID Conditions ─────────────────────────────────────────────────────
        tk.Label(f, text="ID Bedingungen", font=("Arial", 9, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1
        tk.Label(f, text="✓ Muss aktiv = grün   ✗ Ausschluss = rot",
                 fg="#888", font=("Arial", 8)).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1

        self._ids_frame = tk.Frame(f)
        self._ids_frame.grid(row=row, column=0, columnspan=3,
                             sticky="ew", padx=8); row += 1

        raw = self.cond.get("id_conditions", [])
        if raw and isinstance(raw[0], str):
            raw = [{"id": r, "mode": "required"} for r in raw]
        self._id_conditions = [dict(r) for r in raw]
        self._rebuild_id_ui()

        add_f = tk.Frame(f)
        add_f.grid(row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1

        all_ids    = collect_all_ids(self.data)
        var_ids    = [k for k, v in all_ids.items() if v["type"] == "variable"]
        choice_ids = [k for k, v in all_ids.items() if v["type"] == "choice"]
        item_ids   = [k for k, v in all_ids.items() if v["type"] == "item"]

        self._new_id_var   = tk.StringVar()
        self._new_mode_var = tk.StringVar(value="required")

        ttk.Combobox(add_f, textvariable=self._new_id_var,
                     values=sorted(item_ids) + var_ids + choice_ids,
                     width=24).pack(side="left", padx=4)
        ttk.Combobox(add_f, textvariable=self._new_mode_var,
                     values=["required", "exclude"],
                     state="readonly", width=10).pack(side="left", padx=4)
        tk.Button(add_f, text="＋ Add", command=self._add_id).pack(side="left")

        ttk.Separator(f, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=6); row += 1

        # ── Card-level ID Conditions ─────────────────────────────────────────
        # Same logic as id_conditions, but applied across ALL sigils of a card
        # (instead of just within one sigil/ability).
        tk.Label(f, text="Karten-weite ID Bedingungen",
                 font=("Arial", 9, "bold")).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1
        tk.Label(f, text="Gilt über alle Sigils einer Karte hinweg "
                         "(z.B. 'dieser Effekt darf max. einmal pro Karte vorkommen').",
                 fg="#888", font=("Arial", 8)).grid(
            row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1

        self._card_ids_frame = tk.Frame(f)
        self._card_ids_frame.grid(row=row, column=0, columnspan=3,
                                  sticky="ew", padx=8); row += 1

        raw_c = self.cond.get("card_id_conditions", [])
        if raw_c and isinstance(raw_c[0], str):
            raw_c = [{"id": r, "mode": "required"} for r in raw_c]
        self._card_id_conditions = [dict(r) for r in raw_c]
        self._rebuild_card_id_ui()

        add_cf = tk.Frame(f)
        add_cf.grid(row=row, column=0, columnspan=3, sticky="w", padx=8); row += 1

        self._new_card_id_var   = tk.StringVar()
        self._new_card_mode_var = tk.StringVar(value="required")

        ttk.Combobox(add_cf, textvariable=self._new_card_id_var,
                     values=sorted(item_ids) + var_ids + choice_ids,
                     width=24).pack(side="left", padx=4)
        ttk.Combobox(add_cf, textvariable=self._new_card_mode_var,
                     values=["required", "exclude"],
                     state="readonly", width=10).pack(side="left", padx=4)
        tk.Button(add_cf, text="＋ Add",
                  command=self._add_card_id).pack(side="left")

        ttk.Separator(f, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=6); row += 1

        # ── Notes ─────────────────────────────────────────────────────────────
        tk.Label(f, text="Notizen", font=("Arial", 9, "bold")).grid(
            row=row, column=0, sticky="w", padx=8); row += 1
        self._notes_var = tk.StringVar(value=self.cond.get("notes", ""))
        tk.Entry(f, textvariable=self._notes_var, width=46).grid(
            row=row, column=0, columnspan=3, sticky="we", padx=8); row += 1

        tk.Button(self, text="Save", command=self._save_and_close,
                  bg="#1a6e3c", fg="white", width=14).pack(pady=10)

    # ── ID condition UI ────────────────────────────────────────────────────────

    def _rebuild_id_ui(self):
        for w in self._ids_frame.winfo_children():
            w.destroy()
        all_ids    = collect_all_ids(self.data)
        var_ids    = [k for k, v in all_ids.items() if v["type"] == "variable"]
        choice_ids = [k for k, v in all_ids.items() if v["type"] == "choice"]
        item_ids   = [k for k, v in all_ids.items() if v["type"] == "item"]

        for entry in self._id_conditions:
            sid  = entry["id"]
            mode = entry["mode"]
            rf   = tk.Frame(self._ids_frame)
            rf.pack(fill="x", pady=1)

            exists = sid in all_ids
            color  = "#88ff88" if (exists and mode == "required") else \
                     "#ff8888" if (exists and mode == "exclude")  else "#ffaaaa"

            tk.Label(rf, text=sid, fg=color, font=("Arial", 9, "bold"),
                     width=24, anchor="w").pack(side="left", padx=4)

            def _toggle(e=entry):
                e["mode"] = "exclude" if e["mode"] == "required" else "required"
                self._rebuild_id_ui()

            tk.Button(rf,
                      text="✓ Muss" if mode == "required" else "✗ Ausschluss",
                      bg="#1a6e3c" if mode == "required" else "#8e1a1a",
                      fg="white", font=("Arial", 8), width=12,
                      command=_toggle).pack(side="left", padx=4)

            if not exists:
                rv = tk.StringVar()
                ttk.Combobox(rf, textvariable=rv,
                             values=sorted(item_ids) + var_ids + choice_ids,
                             width=20).pack(side="left", padx=2)
                def _reassign(old=sid, rv=rv, e=entry):
                    new = rv.get().strip()
                    if new and new != old:
                        e["id"] = new
                        self._rebuild_id_ui()
                tk.Button(rf, text="Reassign", command=_reassign,
                          font=("Arial", 8)).pack(side="left", padx=2)
            else:
                info = all_ids[sid]
                tk.Label(rf, text=f"({info['type']}  {info['item_id']})",
                         fg="#888", font=("Arial", 8)).pack(side="left", padx=4)

            # val_min / val_max for this id_condition
            for lbl, fkey in [("Min", "val_min"), ("Max", "val_max")]:
                tk.Label(rf, text=lbl, font=("Arial", 7), fg="#aaaaaa").pack(
                    side="left", padx=(4, 0))
                vv = tk.StringVar(value=str(entry.get(fkey, "")))
                ev = tk.Entry(rf, textvariable=vv, width=5, font=("Arial", 8))
                ev.pack(side="left", padx=1)

                def _on_val(_, e=entry, k=fkey, v=vv):
                    raw = v.get().strip()
                    if raw:
                        try:    e[k] = float(raw)
                        except: pass
                    else:
                        e.pop(k, None)

                ev.bind("<FocusOut>", _on_val)
                ev.bind("<Return>",   _on_val)

            tk.Button(rf, text="✕", fg="red",
                      command=lambda e=entry: self._remove_id(e),
                      font=("Arial", 8, "bold"), width=2).pack(side="left", padx=2)

    def _add_id(self):
        sid  = self._new_id_var.get().strip()
        mode = self._new_mode_var.get()
        if sid and not any(e["id"] == sid for e in self._id_conditions):
            self._id_conditions.append({"id": sid, "mode": mode})
            self._new_id_var.set("")
            self._rebuild_id_ui()

    def _remove_id(self, entry: dict):
        self._id_conditions = [e for e in self._id_conditions if e is not entry]
        self._rebuild_id_ui()

    # ── Save ───────────────────────────────────────────────────────────────────

    def _commit(self):
        """Persist all fields into self.cond without closing the window."""
        # Mana
        for key in ("min_mana", "max_mana"):
            var = getattr(self, f"_{key}_var")
            try:    self.cond[key] = int(var.get())
            except: self.cond.pop(key, None)

        # Variable min/max
        if self.stat_type == "variable":
            for key in ("var_min", "var_max"):
                var = getattr(self, f"_{key}_var", None)
                if var:
                    try:    self.cond[key] = float(var.get())
                    except: self.cond.pop(key, None)

        # Excluded choices
        if self.stat_type == "choice":
            excl = [c for c, v in self._choice_vars.items() if not v.get()]
            if excl: self.cond["excluded_choices"] = excl
            else:    self.cond.pop("excluded_choices", None)

        # Allowed elements + element weights (only for variables/choices)
        if self.stat_type != "effect":
            sel = [el for el, v in self._el_vars.items() if v.get()]
            if len(sel) < len(ELEMENTS):
                self.cond["allowed_elements"] = sel
            else:
                self.cond.pop("allowed_elements", None)

            weights = {}
            for el in ELEMENTS:
                raw = self._el_weights[el].get().strip()
                if raw != "":
                    try:    weights[el] = float(raw)
                    except: pass
            if weights:
                self.cond["element_weights"] = weights
            else:
                self.cond.pop("element_weights", None)

        # Allowed box types – only save if not all checked
        sel_bt = [bt for bt, v in self._bt_vars.items() if v.get()]
        if len(sel_bt) < len(BOX_TYPES):
            self.cond["allowed_box_types"] = sel_bt
        else:
            self.cond.pop("allowed_box_types", None)

        # ID conditions
        if self._id_conditions:
            self.cond["id_conditions"] = list(self._id_conditions)
        else:
            self.cond.pop("id_conditions", None)

        # Notes
        notes = self._notes_var.get()
        if notes: self.cond["notes"] = notes
        else:     self.cond.pop("notes", None)

    def _save_and_close(self):
        self._commit()
        self.destroy()