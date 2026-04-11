"""
CardContent/effect_type_panel.py – Panel for assigning primary effect types.

Columns (grid-aligned):  Effekt ID  |  Non Targeting  |  Target Enemy  |  Target Ally  |  Target Neutral  |  (sep)  |  Tränke  |  Skills  |  Loot
"""

import json
import os
import tkinter as tk
from tkinter import ttk

from CardContent.window_memory import wm

_HERE         = os.path.dirname(os.path.abspath(__file__))
_EFFECTS_FILE = os.path.join(_HERE, "cc_data", "effects.json")

PRIMARY_TYPES = ["Non Targeting", "Target Enemy", "Target Ally", "Target Neutral"]

_LABELS = {
    "Non Targeting":  "Non\nTargeting",
    "Target Enemy":   "Target\nEnemy",
    "Target Ally":    "Target\nAlly",
    "Target Neutral": "Target\nNeutral",
}
_COLORS = {
    "Non Targeting":  "#88ccff",
    "Target Enemy":   "#ff8888",
    "Target Ally":    "#88ff88",
    "Target Neutral": "#ffcc44",
}

# Column widths in pixels
_COL_ID    = 160
_COL_TYPE  = 90


def _apply_cols(frame: tk.Frame):
    frame.columnconfigure(0, minsize=_COL_ID)
    for i in range(1, len(PRIMARY_TYPES) + 1):
        frame.columnconfigure(i, minsize=_COL_TYPE)


class EffectTypePanel(tk.Toplevel):

    def __init__(self, parent, data: dict, on_save=None):
        super().__init__(parent)
        self.data    = data
        self.on_save = on_save
        self.title("Effekt Primärtypen")
        self.configure(bg="#1a1a1a")
        wm.restore(self, "effect_type_panel", "760x500")
        self._row_vars: list[tuple[dict, dict, dict]] = []
        self._build()

    # ── Build ──────────────────────────────────────────────────────────────────

    def _build(self):
        top = tk.Frame(self, bg="#1a1a1a")
        top.pack(fill="x", padx=8, pady=6)
        tk.Label(top, text="Effekt Primärtypen",
                 bg="#1a1a1a", fg="#88ccff",
                 font=("Arial", 11, "bold")).pack(side="left")
        tk.Button(top, text="💾 Speichern", command=self._save,
                  bg="#1a6e3c", fg="white",
                  font=("Arial", 9, "bold"), cursor="hand2").pack(side="right")

        # Scrollable area
        outer = tk.Frame(self, bg="#1a1a1a")
        outer.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        vsb = tk.Scrollbar(outer, orient="vertical", bg="#333")
        vsb.pack(side="right", fill="y")
        canvas = tk.Canvas(outer, bg="#1a1a1a",
                           yscrollcommand=vsb.set, highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.config(command=canvas.yview)

        inner = tk.Frame(canvas, bg="#1a1a1a")
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win_id, width=e.width))
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))

        self._fill_table(inner)

    def _fill_table(self, parent):
        # ── Header row ────────────────────────────────────────────────────────
        hdr = tk.Frame(parent, bg="#252525")
        hdr.pack(fill="x")
        _apply_cols(hdr)

        tk.Label(hdr, text="Effekt ID", bg="#252525", fg="#aaa",
                 font=("Arial", 8, "bold"), anchor="w").grid(
            row=0, column=0, sticky="w", padx=(8, 4), pady=6)

        for col, pt in enumerate(PRIMARY_TYPES, start=1):
            tk.Label(hdr, text=_LABELS[pt], bg="#252525", fg=_COLORS[pt],
                     font=("Arial", 8, "bold"), anchor="center",
                     justify="center").grid(
                row=0, column=col, sticky="ew", padx=2, pady=4)

        ttk.Separator(parent, orient="horizontal").pack(fill="x")

        # ── Data rows ─────────────────────────────────────────────────────────
        effects = self.data.get("Effect", [])
        self._row_vars = []

        for idx, item in enumerate(effects):
            bg = "#1e1e1e" if idx % 2 == 0 else "#242424"
            row_f = tk.Frame(parent, bg=bg)
            row_f.pack(fill="x")
            _apply_cols(row_f)

            tk.Label(row_f, text=item.get("id", "?"), bg=bg, fg="#cccccc",
                     font=("Consolas", 8), anchor="w").grid(
                row=0, column=0, sticky="w", padx=(8, 4), pady=3)

            saved_types = item.get("primary_types", [])
            type_vars:  dict[str, tk.BooleanVar] = {}

            for col, pt in enumerate(PRIMARY_TYPES, start=1):
                v = tk.BooleanVar(value=(pt in saved_types))
                type_vars[pt] = v
                tk.Checkbutton(
                    row_f, variable=v,
                    bg=bg, activebackground=bg,
                    selectcolor="#2a2a2a",
                    fg=_COLORS[pt],
                ).grid(row=0, column=col, sticky="ew", padx=2)

            self._row_vars.append((item, type_vars))

    # ── Save ───────────────────────────────────────────────────────────────────

    def _save(self):
        for item, type_vars in self._row_vars:
            types = [pt for pt, v in type_vars.items() if v.get()]
            if types:
                item["primary_types"] = types
            else:
                item.pop("primary_types", None)
            item.pop("cv_multiply", None)   # remove legacy field if present
            item.pop("allowed_in", None)    # removed feature

        os.makedirs(os.path.dirname(_EFFECTS_FILE), exist_ok=True)
        with open(_EFFECTS_FILE, "w", encoding="utf-8") as f:
            json.dump({"Effect": self.data["Effect"]}, f, indent=4, ensure_ascii=False)

        if self.on_save:
            self.on_save()
        self.destroy()
