"""
ingredient_editor.py – Toplevel dialog for configuring ingredients.

Per material row:
  Material  |  Effekt (Combobox)  |  CV Mult  |  Complexity
"""

import tkinter as tk
from tkinter import ttk

from card_builder.materials import merged_materials, load_material_effects, save_material_effects
from card_builder.data import get_content_data

# ── colour constants ──────────────────────────────────────────────────────────
BG       = "#1a1a1a"
FG       = "white"
ENTRY_BG = "#2a2a2a"
MAT_FG   = "#aaccff"

NONE_LABEL = "— keiner —"

# Column widths (characters)
COL_MAT_W    = 14
COL_COMBO_W  = 20
COL_CVMULT_W = 6
COL_CMPLX_W  = 6


class IngredientEditor(tk.Toplevel):
    """Dialog: assign one effect + CV multiplier + complexity to every material."""

    def __init__(self, parent, on_save=None):
        super().__init__(parent)
        self.on_save = on_save
        self.title("Ingredient Editor")
        self.configure(bg=BG)
        self.geometry("520x500")
        self.resizable(True, True)

        cd = get_content_data()
        self._effect_list  = cd.effects
        self._effect_ids   = [e["id"] for e in self._effect_list]
        self._combo_values = [NONE_LABEL] + self._effect_ids

        self._materials = merged_materials()
        self._saved     = load_material_effects()

        self._rows: dict = {}
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # title bar
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(top, text="Ingredient Editor", bg=BG, fg=FG,
                 font=("Segoe UI", 12, "bold")).pack(side="left")
        tk.Button(top, text="Speichern", bg="#2a4a2a", fg=FG,
                  activebackground="#3a6a3a", relief="flat", padx=10,
                  font=("Segoe UI", 9), command=self._on_save).pack(side="right")

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=4, pady=4)

        # scrollable area
        container = tk.Frame(self, bg=BG)
        container.pack(fill="both", expand=True, padx=4, pady=4)

        canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._inner = tk.Frame(canvas, bg=BG)
        self._inner_id = canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>",
                         lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(self._inner_id, width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        # ── header row (grid) ─────────────────────────────────────────────────
        hdr = tk.Frame(self._inner, bg="#222")
        hdr.pack(fill="x", padx=2, pady=(0, 2))

        hdr.columnconfigure(0, minsize=130)
        hdr.columnconfigure(1, minsize=170)
        hdr.columnconfigure(2, minsize=70)
        hdr.columnconfigure(3, minsize=70)

        hdr_font = ("Segoe UI", 9, "bold")
        tk.Label(hdr, text="Material",   bg="#222", fg="#aaa", font=hdr_font,
                 anchor="w").grid(row=0, column=0, sticky="w", padx=(8, 4), pady=4)
        tk.Label(hdr, text="Effekt",     bg="#222", fg="#aaa", font=hdr_font,
                 anchor="w").grid(row=0, column=1, sticky="w", padx=4, pady=4)
        tk.Label(hdr, text="CV Mult",    bg="#222", fg="#aaa", font=hdr_font,
                 anchor="w").grid(row=0, column=2, sticky="w", padx=4, pady=4)
        tk.Label(hdr, text="Cmplx",      bg="#222", fg="#aaa", font=hdr_font,
                 anchor="w").grid(row=0, column=3, sticky="w", padx=4, pady=4)

        # ── material rows ─────────────────────────────────────────────────────
        for mat in self._materials:
            self._build_row(mat)

    def _build_row(self, mat: str):
        saved = self._saved.get(mat, {})

        row_bg = "#1e1e1e"
        rf = tk.Frame(self._inner, bg=row_bg)
        rf.pack(fill="x", padx=2, pady=1)

        rf.columnconfigure(0, minsize=130)
        rf.columnconfigure(1, minsize=170)
        rf.columnconfigure(2, minsize=70)
        rf.columnconfigure(3, minsize=70)

        # col 0 – material name
        tk.Label(rf, text=mat, bg=row_bg, fg=MAT_FG, anchor="w",
                 font=("Segoe UI", 9, "bold")).grid(
            row=0, column=0, sticky="w", padx=(8, 4), pady=3)

        # col 1 – effect combobox
        combo_var = tk.StringVar(
            value=saved.get("effect_id", "") or NONE_LABEL)
        combo = ttk.Combobox(rf, textvariable=combo_var,
                             values=self._combo_values,
                             state="readonly", width=COL_COMBO_W)
        combo.grid(row=0, column=1, sticky="w", padx=4, pady=3)

        # col 2 – CV multiplier
        cv_mult_var = tk.StringVar(
            value=str(saved.get("cv_multiplier", 1.0)))
        tk.Entry(rf, textvariable=cv_mult_var, bg=ENTRY_BG, fg=FG,
                 insertbackground=FG, relief="flat", width=COL_CVMULT_W,
                 font=("Segoe UI", 9), justify="center").grid(
            row=0, column=2, sticky="w", padx=4, pady=3)

        # col 3 – complexity
        cmplx_var = tk.StringVar(
            value=str(saved.get("complexity", 0)))
        tk.Entry(rf, textvariable=cmplx_var, bg=ENTRY_BG, fg=FG,
                 insertbackground=FG, relief="flat", width=COL_CMPLX_W,
                 font=("Segoe UI", 9), justify="center").grid(
            row=0, column=3, sticky="w", padx=4, pady=3)

        self._rows[mat] = {
            "combo_var":      combo_var,
            "cv_mult_var":    cv_mult_var,
            "complexity_var": cmplx_var,
        }

    # ── save ─────────────────────────────────────────────────────────────────

    def _on_save(self):
        result = {}
        for mat, row in self._rows.items():
            chosen = row["combo_var"].get()
            if chosen == NONE_LABEL or not chosen:
                continue

            try:
                cv_mult = float(row["cv_mult_var"].get())
            except (ValueError, TypeError):
                cv_mult = 1.0

            try:
                cmplx = float(row["complexity_var"].get())
            except (ValueError, TypeError):
                cmplx = 0.0

            result[mat] = {
                "effect_id":     chosen,
                "cv_multiplier": cv_mult,
                "complexity":    cmplx,
            }

        save_material_effects(result)

        if self.on_save:
            self.on_save(result)

        self.destroy()
