"""
aoe_designer/app.py – AOE Spell pattern designer with interactive hex grid.

Cell states (click to cycle):
    empty  → target → player → empty
    Right-click always resets to empty.

Patterns are saved under IDs to aoe_patterns.json next to this module.
Use \\AOE in a Sigil [\\AOE] to auto-import all saved pattern IDs as options.
"""

import math
import tkinter as tk
from tkinter import ttk, messagebox

from .models import load_patterns, save_patterns

# ── Cell state constants ───────────────────────────────────────────────────────

CELL_EMPTY  = "empty"
CELL_TARGET = "target"
CELL_PLAYER = "player"

_CYCLE  = [CELL_EMPTY, CELL_TARGET, CELL_PLAYER]
_COLORS = {
    CELL_EMPTY:  ("#2a2a2a", "#484848"),
    CELL_TARGET: ("#993300", "#ff6622"),
    CELL_PLAYER: ("#155a30", "#22cc66"),
}

# ── Hex math (flat-top axial coordinates) ─────────────────────────────────────

def _axial_to_pixel(q: int, r: int, size: float, cx: float, cy: float):
    x = cx + size * 1.5 * q
    y = cy + size * math.sqrt(3) * (r + q / 2.0)
    return x, y


def _pixel_to_axial(px: float, py: float, size: float, cx: float, cy: float):
    px -= cx
    py -= cy
    fq =  (2.0 / 3.0 * px) / size
    fr = (-1.0 / 3.0 * px + math.sqrt(3) / 3.0 * py) / size
    return _hex_round(fq, fr)


def _hex_round(q: float, r: float):
    s = -q - r
    rq, rr, rs = round(q), round(r), round(s)
    dq, dr, ds = abs(rq - q), abs(rr - r), abs(rs - s)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return int(rq), int(rr)


def _hex_corners(cx: float, cy: float, size: float) -> list:
    pts = []
    for i in range(6):
        a = math.pi / 3.0 * i
        pts += [cx + size * math.cos(a), cy + size * math.sin(a)]
    return pts


def _in_grid(q: int, r: int, radius: int) -> bool:
    return abs(q) <= radius and abs(r) <= radius and abs(q + r) <= radius


# ── Hex grid canvas widget ─────────────────────────────────────────────────────

class HexGridCanvas(tk.Canvas):
    """
    Interactive hex grid canvas.
    Left-click:  cycle cell state  empty → target → player → empty
    Right-click: reset cell to empty
    """

    HEX_SIZE = 30

    def __init__(self, parent, radius: int = 4, on_change=None, **kw):
        kw.setdefault("bg", "#111111")
        kw.setdefault("highlightthickness", 0)
        super().__init__(parent, **kw)
        self.radius    = radius
        self.on_change = on_change
        self._cells: dict  = {}        # (q,r) → state string
        self._polys: dict  = {}        # (q,r) → canvas item id
        self._ready        = False

        self.bind("<Configure>",  self._on_configure)
        self.bind("<Button-1>",   self._on_left_click)
        self.bind("<Button-3>",   self._on_right_click)

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _canvas_center(self):
        return self.winfo_width() / 2.0, self.winfo_height() / 2.0

    def _on_configure(self, _event=None):
        if self.winfo_width() < 10:
            self.after(80, self._draw)
            return
        self._draw()

    def _draw(self):
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10 or h < 10:
            self.after(80, self._draw)
            return

        self.delete("all")
        self._polys = {}
        cx, cy = w / 2.0, h / 2.0

        # Auto-scale hex size to fit grid in canvas
        r        = self.radius
        size     = min(w / (r * 3.5 + 1.5), h / (r * 3.5 + 1.5))
        size     = max(14.0, min(size, 40.0))
        self._size = size

        for q in range(-r, r + 1):
            for s in range(-r, r + 1):
                rr = -q - s
                if not _in_grid(q, rr, r):
                    continue
                state       = self._cells.get((q, rr), CELL_EMPTY)
                px, py      = _axial_to_pixel(q, rr, size, cx, cy)
                pts         = _hex_corners(px, py, size - 1.5)
                fill, outline = _COLORS[state]
                poly = self.create_polygon(pts, fill=fill, outline=outline,
                                           width=1.5, tags="hex")
                self._polys[(q, rr)] = poly

        # Center marker
        pcx, pcy = _axial_to_pixel(0, 0, size, cx, cy)
        self.create_text(pcx, pcy, text="⊕", fill="#555555",
                         font=("Arial", 8), tags="center_mark")

        self._ready = True

    def _update_cell(self, q: int, r: int):
        item = self._polys.get((q, r))
        if item is None:
            return
        state = self._cells.get((q, r), CELL_EMPTY)
        fill, outline = _COLORS[state]
        self.itemconfig(item, fill=fill, outline=outline)

    # ── Input handling ────────────────────────────────────────────────────────

    def _on_left_click(self, e):
        if not self._ready:
            return
        cx, cy = self._canvas_center()
        q, r   = _pixel_to_axial(e.x, e.y, self._size, cx, cy)
        if not _in_grid(q, r, self.radius):
            return
        state      = self._cells.get((q, r), CELL_EMPTY)
        next_state = _CYCLE[(_CYCLE.index(state) + 1) % len(_CYCLE)]
        if next_state == CELL_EMPTY:
            self._cells.pop((q, r), None)
        else:
            self._cells[(q, r)] = next_state
        self._update_cell(q, r)
        if self.on_change:
            self.on_change()

    def _on_right_click(self, e):
        if not self._ready:
            return
        cx, cy = self._canvas_center()
        q, r   = _pixel_to_axial(e.x, e.y, self._size, cx, cy)
        if _in_grid(q, r, self.radius):
            self._cells.pop((q, r), None)
            self._update_cell(q, r)
            if self.on_change:
                self.on_change()

    # ── Public API ────────────────────────────────────────────────────────────

    def get_cells(self) -> dict:
        """Return cells as {"q,r": state, ...} dict (only non-empty cells)."""
        return {f"{q},{r}": s for (q, r), s in self._cells.items()}

    def set_cells(self, cells_dict: dict):
        """Load cells from {"q,r": state, ...} dict."""
        self._cells = {}
        for key, state in cells_dict.items():
            if state == CELL_EMPTY:
                continue
            try:
                q, r = map(int, key.split(","))
                self._cells[(q, r)] = state
            except (ValueError, AttributeError):
                pass
        if self._ready:
            self._draw()
        else:
            self.after(120, self._draw)

    def set_radius(self, radius: int):
        self.radius = radius
        # Trim cells outside new radius
        self._cells = {
            (q, r): s for (q, r), s in self._cells.items()
            if _in_grid(q, r, radius)
        }
        self._draw()

    def clear(self):
        self._cells = {}
        if self._ready:
            self._draw()


# ── Main AOE Designer panel ────────────────────────────────────────────────────

class AoEDesigner(tk.Frame):
    """
    Top-level panel embedded into the main App window.
    Left: controls + saved pattern list.
    Right: interactive hex grid canvas.
    """

    def __init__(self, parent, **kw):
        kw.setdefault("bg", "#1a1a1a")
        super().__init__(parent, **kw)
        self._patterns = load_patterns()
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        # Left panel (fixed width)
        left = tk.Frame(self, bg="#1a1a1a", width=250)
        left.pack(side="left", fill="y", padx=(8, 4), pady=8)
        left.pack_propagate(False)

        # Right panel (canvas, expands)
        right = tk.Frame(self, bg="#111111")
        right.pack(side="left", fill="both", expand=True, padx=(4, 8), pady=8)

        self._grid = HexGridCanvas(right, radius=4, on_change=self._on_grid_change)
        self._grid.pack(fill="both", expand=True)

        self._build_controls(left)

    def _build_controls(self, parent):
        tk.Label(parent, text="AOE Designer",
                 bg="#1a1a1a", fg="#cc8833",
                 font=("Palatino Linotype", 13, "bold")).pack(pady=(6, 2))
        tk.Label(parent, text="Linksklick: Zustand wechseln\nRechtsklick: Feld leeren",
                 bg="#1a1a1a", fg="#555", font=("Arial", 8, "italic")).pack(pady=(0, 6))

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=4)

        # ── ID ────────────────────────────────────────────────────────────────
        tk.Label(parent, text="Pattern ID:",
                 bg="#1a1a1a", fg="#aaa", font=("Arial", 9, "bold")).pack(
            anchor="w", padx=6)
        self._id_var = tk.StringVar()
        tk.Entry(parent, textvariable=self._id_var,
                 bg="#2a2a2a", fg="white", insertbackground="white",
                 width=26, font=("Arial", 10)).pack(padx=6, pady=3, fill="x")

        # ── Save / Delete row ─────────────────────────────────────────────────
        btn_row = tk.Frame(parent, bg="#1a1a1a")
        btn_row.pack(fill="x", padx=6, pady=2)
        tk.Button(btn_row, text="💾 Speichern",
                  command=self._save,
                  bg="#1a6e3c", fg="white",
                  font=("Arial", 9), cursor="hand2").pack(
            side="left", fill="x", expand=True, padx=(0, 2))
        tk.Button(btn_row, text="🗑 Löschen",
                  command=self._delete,
                  bg="#8e1a1a", fg="white",
                  font=("Arial", 9), cursor="hand2").pack(
            side="left", fill="x", expand=True)

        tk.Button(parent, text="✕  Alles leeren",
                  command=self._clear_grid,
                  bg="#2a2a2a", fg="#aaa",
                  font=("Arial", 8), cursor="hand2").pack(
            fill="x", padx=6, pady=(2, 6))

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=4)

        # ── Grid radius ───────────────────────────────────────────────────────
        rad_f = tk.Frame(parent, bg="#1a1a1a")
        rad_f.pack(fill="x", padx=6, pady=4)
        tk.Label(rad_f, text="Grid Radius:", bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9)).pack(side="left")
        self._radius_var = tk.IntVar(value=4)
        sb = tk.Spinbox(rad_f, from_=2, to=7, textvariable=self._radius_var,
                        width=4, command=self._on_radius_change,
                        bg="#2a2a2a", fg="white", buttonbackground="#333")
        sb.pack(side="left", padx=(6, 0))
        self._radius_var.trace_add("write", lambda *_: self._on_radius_change())

        # ── Pattern CV (used by spell generator when AoE replaces Range) ─────
        cv_f = tk.Frame(parent, bg="#1a1a1a")
        cv_f.pack(fill="x", padx=6, pady=4)
        tk.Label(cv_f, text="CV:", bg="#1a1a1a", fg="#aaa",
                 font=("Arial", 9)).pack(side="left")
        self._cv_var = tk.StringVar(value="")
        tk.Entry(cv_f, textvariable=self._cv_var,
                  width=6, bg="#2a2a2a", fg="white",
                  insertbackground="white").pack(side="left", padx=(6, 0))
        tk.Label(cv_f, text="(leer = 0.5 × Zellenanzahl)",
                  bg="#1a1a1a", fg="#666",
                  font=("Arial", 8, "italic")).pack(side="left", padx=8)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=4)

        # ── Saved patterns list ───────────────────────────────────────────────
        tk.Label(parent, text="Gespeicherte Muster:",
                 bg="#1a1a1a", fg="#88ccff",
                 font=("Arial", 9, "bold")).pack(anchor="w", padx=6)

        list_outer = tk.Frame(parent, bg="#1a1a1a")
        list_outer.pack(fill="both", expand=True, padx=6, pady=2)

        vsb = tk.Scrollbar(list_outer, orient="vertical")
        vsb.pack(side="right", fill="y")
        self._listbox = tk.Listbox(
            list_outer, yscrollcommand=vsb.set,
            bg="#2a2a2a", fg="white",
            selectbackground="#1a3e8e", activestyle="dotbox",
            font=("Arial", 9), height=8, relief="flat")
        self._listbox.pack(side="left", fill="both", expand=True)
        vsb.config(command=self._listbox.yview)
        self._listbox.bind("<Double-Button-1>", lambda _: self._load_selected())

        tk.Button(parent, text="↺  Laden",
                  command=self._load_selected,
                  bg="#1a3e8e", fg="white",
                  font=("Arial", 9), cursor="hand2").pack(
            fill="x", padx=6, pady=(2, 6))

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=4)

        # ── Legend ────────────────────────────────────────────────────────────
        tk.Label(parent, text="Legende:", bg="#1a1a1a", fg="#666",
                 font=("Arial", 8, "bold")).pack(anchor="w", padx=6)
        for state, label in [
            (CELL_TARGET, "Target"),
            (CELL_PLAYER, "Spieler"),
            (CELL_EMPTY,  "Leer"),
        ]:
            fill, _ = _COLORS[state]
            leg = tk.Frame(parent, bg="#1a1a1a")
            leg.pack(anchor="w", padx=12, pady=1)
            tk.Label(leg, bg=fill, width=2, height=1,
                     relief="flat").pack(side="left", padx=(0, 4))
            tk.Label(leg, text=label, bg="#1a1a1a", fg="#888",
                     font=("Arial", 8)).pack(side="left")

        tk.Label(parent, text="Syntax:  [\\AOE]  in Sigil",
                 bg="#1a1a1a", fg="#555",
                 font=("Arial", 7, "italic")).pack(pady=(6, 2), padx=6)

        self._status_label = tk.Label(parent, text="", bg="#1a1a1a", fg="#aaa",
                                      font=("Arial", 8), wraplength=220)
        self._status_label.pack(padx=6, pady=2)

        self._refresh_list()

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _on_grid_change(self):
        pass  # Could show live cell count etc.

    def _on_radius_change(self):
        try:
            r = int(self._radius_var.get())
            r = max(2, min(7, r))
            self._grid.set_radius(r)
        except (ValueError, tk.TclError):
            pass

    def _save(self):
        pid = self._id_var.get().strip()
        if not pid:
            messagebox.showwarning("ID fehlt", "Bitte eine Pattern-ID eingeben.",
                                   parent=self)
            return
        if any(c in pid for c in (", \t\n")):
            messagebox.showwarning(
                "Ungültige ID",
                "ID darf keine Leerzeichen, Kommas oder Tabs enthalten.",
                parent=self)
            return

        # CV: blank → use default (0.5 × cell count); non-blank → parse
        cv_raw = self._cv_var.get().strip()
        cv_val = None
        if cv_raw:
            try:
                cv_val = float(cv_raw)
            except ValueError:
                messagebox.showwarning("Ungültige CV",
                                        f"Konnte CV '{cv_raw}' nicht parsen — "
                                        "verwende Default.",
                                        parent=self)

        entry = {
            "id":          pid,
            "cells":       self._grid.get_cells(),
            "grid_radius": int(self._radius_var.get()),
        }
        if cv_val is not None:
            entry["cv"] = cv_val
        self._patterns[pid] = entry
        save_patterns(self._patterns)
        self._refresh_list()
        self._set_status(f"✓ Gespeichert: {pid}", "#1a6e3c")

    def _delete(self):
        pid = self._id_var.get().strip()
        if pid not in self._patterns:
            messagebox.showinfo("Nicht gefunden",
                                f"Pattern '{pid}' ist nicht gespeichert.",
                                parent=self)
            return
        if not messagebox.askyesno("Löschen",
                                   f"Pattern '{pid}' wirklich löschen?",
                                   parent=self):
            return
        del self._patterns[pid]
        save_patterns(self._patterns)
        self._id_var.set("")
        self._grid.clear()
        self._refresh_list()
        self._set_status(f"Gelöscht: {pid}", "#8e1a1a")

    def _clear_grid(self):
        self._grid.clear()

    def _refresh_list(self):
        self._listbox.delete(0, "end")
        for pid in sorted(self._patterns.keys()):
            self._listbox.insert("end", pid)

    def _load_selected(self):
        sel = self._listbox.curselection()
        if not sel:
            return
        pid = self._listbox.get(sel[0])
        pat = self._patterns.get(pid)
        if not pat:
            return
        self._id_var.set(pid)
        r = pat.get("grid_radius", 4)
        self._radius_var.set(r)
        self._grid.set_radius(r)
        self._grid.set_cells(pat.get("cells", {}))
        # CV: blank field if not stored explicitly (default kicks in on save)
        cv = pat.get("cv")
        if cv is None:
            self._cv_var.set("")
        else:
            self._cv_var.set(str(cv))
        self._set_status(f"Geladen: {pid}", "#1a3e8e")

    def _set_status(self, msg: str, color: str = "#1a1a1a"):
        self._status_label.config(text=msg, bg=color, fg="white")
        self.after(3000, lambda: self._status_label.config(
            text="", bg="#1a1a1a", fg="#aaa"))
