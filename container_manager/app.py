"""
container_manager/app.py – Container Manager panel.

Left:  list of containers (CRUD).
Right: all available effects as checkboxes to assign to the selected container.
"""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from .models import load_containers, save_containers


def _load_effect_ids() -> list:
    """Load all effect IDs from effects.json."""
    try:
        import os, json
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "CardContent", "cc_data", "effects.json")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [item["id"] for item in data.get("Effect", [])]
    except Exception:
        return []


class ContainerManager(tk.Frame):
    """Top-level panel for managing Content Containers."""

    def __init__(self, parent, **kw):
        kw.setdefault("bg", "#1a1a1a")
        super().__init__(parent, **kw)
        self._data = load_containers()
        self._effect_ids = _load_effect_ids()
        self._selected = None          # currently selected container id
        self._check_vars: dict = {}    # effect_id → BooleanVar
        self._build()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        tk.Label(self, text="📦  Container Manager",
                 bg="#1a1a1a", fg="#cc8833",
                 font=("Palatino Linotype", 13, "bold")).pack(
            pady=(8, 2), anchor="w", padx=12)
        tk.Label(self, text="Gruppen ähnlicher Effekte · no_repeat = kein Effekt aus der Gruppe wird pro Karte wiederholt",
                 bg="#1a1a1a", fg="#555",
                 font=("Arial", 8, "italic")).pack(anchor="w", padx=12)

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=6)

        main = tk.Frame(self, bg="#1a1a1a")
        main.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Left: container list
        left = tk.Frame(main, bg="#1a1a1a", width=220)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)
        self._build_left(left)

        # Separator
        ttk.Separator(main, orient="vertical").pack(side="left", fill="y")

        # Right: effects assignment
        right = tk.Frame(main, bg="#1a1a1a")
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self._build_right(right)

    def _build_left(self, parent):
        tk.Label(parent, text="Container:", bg="#1a1a1a", fg="#88ccff",
                 font=("Arial", 10, "bold")).pack(anchor="w", pady=(4, 2))

        list_f = tk.Frame(parent, bg="#1a1a1a")
        list_f.pack(fill="both", expand=True, pady=(0, 4))
        vsb = tk.Scrollbar(list_f, orient="vertical")
        vsb.pack(side="right", fill="y")
        self._container_lb = tk.Listbox(
            list_f, yscrollcommand=vsb.set,
            bg="#2a2a2a", fg="white",
            selectbackground="#1a3e8e", activestyle="dotbox",
            font=("Arial", 10), relief="flat")
        self._container_lb.pack(side="left", fill="both", expand=True)
        vsb.config(command=self._container_lb.yview)
        self._container_lb.bind("<<ListboxSelect>>", self._on_select)

        btn_row = tk.Frame(parent, bg="#1a1a1a")
        btn_row.pack(fill="x", pady=2)
        tk.Button(btn_row, text="＋ Neu", command=self._new_container,
                  bg="#1a6e3c", fg="white", font=("Arial", 9),
                  cursor="hand2").pack(side="left", fill="x", expand=True, padx=(0, 2))
        tk.Button(btn_row, text="🗑", command=self._delete_container,
                  bg="#8e1a1a", fg="white", font=("Arial", 9),
                  cursor="hand2").pack(side="left")

        # no_repeat toggle
        self._no_repeat_var = tk.BooleanVar(value=True)
        self._no_repeat_cb = tk.Checkbutton(
            parent, text="No Repeat (pro Karte nur 1 Effekt)",
            variable=self._no_repeat_var,
            bg="#1a1a1a", fg="#aaa",
            font=("Arial", 8),
            command=self._on_no_repeat_change,
            state="disabled")
        self._no_repeat_cb.pack(anchor="w", pady=4)

        # Description
        tk.Label(parent, text="Beschreibung:", bg="#1a1a1a", fg="#888",
                 font=("Arial", 8)).pack(anchor="w", pady=(4, 0))
        self._desc_var = tk.StringVar()
        self._desc_entry = tk.Entry(parent, textvariable=self._desc_var,
                                    bg="#2a2a2a", fg="white",
                                    insertbackground="white",
                                    font=("Arial", 9), state="disabled")
        self._desc_entry.pack(fill="x", pady=2)
        self._desc_var.trace_add("write", self._on_desc_change)

        self._refresh_list()

    def _build_right(self, parent):
        hdr = tk.Frame(parent, bg="#1a1a1a")
        hdr.pack(fill="x", pady=(4, 6))
        tk.Label(hdr, text="Effekte im Container:",
                 bg="#1a1a1a", fg="#cc8833",
                 font=("Arial", 10, "bold")).pack(side="left")
        tk.Button(hdr, text="↺ Effekte neu laden",
                  command=self._reload_effects,
                  bg="#2a2a2a", fg="#aaa",
                  font=("Arial", 8)).pack(side="right")

        self._right_scroll_outer = tk.Frame(parent, bg="#1a1a1a")
        self._right_scroll_outer.pack(fill="both", expand=True)

        vsb = tk.Scrollbar(self._right_scroll_outer, orient="vertical")
        vsb.pack(side="right", fill="y")
        self._effects_canvas = tk.Canvas(
            self._right_scroll_outer,
            yscrollcommand=vsb.set,
            bg="#1a1a1a", highlightthickness=0)
        self._effects_canvas.pack(side="left", fill="both", expand=True)
        vsb.config(command=self._effects_canvas.yview)
        self._effects_canvas.bind(
            "<MouseWheel>",
            lambda e: self._effects_canvas.yview_scroll(int(-e.delta / 120), "units"))

        self._effects_inner = tk.Frame(self._effects_canvas, bg="#1a1a1a")
        self._effects_win = self._effects_canvas.create_window(
            (0, 0), window=self._effects_inner, anchor="nw")
        self._effects_inner.bind(
            "<Configure>",
            lambda e: self._effects_canvas.configure(
                scrollregion=self._effects_canvas.bbox("all")))
        self._effects_canvas.bind(
            "<Configure>",
            lambda e: self._effects_canvas.itemconfig(
                self._effects_win, width=e.width))

        self._rebuild_effects()

    # ── Container list ────────────────────────────────────────────────────────

    def _refresh_list(self):
        self._container_lb.delete(0, "end")
        for cid in sorted(self._data.keys()):
            self._container_lb.insert("end", cid)

    def _on_select(self, _=None):
        sel = self._container_lb.curselection()
        if not sel:
            return
        self._selected = self._container_lb.get(sel[0])
        cont = self._data[self._selected]
        self._no_repeat_var.set(cont.get("no_repeat", True))
        self._no_repeat_cb.config(state="normal")
        self._desc_var.set(cont.get("description", ""))
        self._desc_entry.config(state="normal")
        self._rebuild_effects()

    def _new_container(self):
        name = simpledialog.askstring("Neuer Container", "Container ID:",
                                      parent=self)
        if not name or not name.strip():
            return
        cid = name.strip()
        if cid in self._data:
            messagebox.showwarning("Existiert bereits",
                                   f"'{cid}' ist bereits vorhanden.", parent=self)
            return
        self._data[cid] = {
            "id": cid, "description": "", "effects": [], "no_repeat": True
        }
        save_containers(self._data)
        self._refresh_list()
        # Select the new container
        items = sorted(self._data.keys())
        idx = items.index(cid)
        self._container_lb.selection_clear(0, "end")
        self._container_lb.selection_set(idx)
        self._container_lb.see(idx)
        self._on_select()

    def _delete_container(self):
        if not self._selected:
            return
        if not messagebox.askyesno("Löschen",
                                   f"Container '{self._selected}' löschen?",
                                   parent=self):
            return
        del self._data[self._selected]
        self._selected = None
        save_containers(self._data)
        self._refresh_list()
        self._rebuild_effects()

    def _on_no_repeat_change(self):
        if self._selected:
            self._data[self._selected]["no_repeat"] = self._no_repeat_var.get()
            save_containers(self._data)

    def _on_desc_change(self, *_):
        if self._selected:
            self._data[self._selected]["description"] = self._desc_var.get()
            # Autosave on change (debounced via after)
            if hasattr(self, "_desc_save_job"):
                self.after_cancel(self._desc_save_job)
            self._desc_save_job = self.after(
                800, lambda: save_containers(self._data))

    # ── Effects list ──────────────────────────────────────────────────────────

    def _reload_effects(self):
        self._effect_ids = _load_effect_ids()
        self._rebuild_effects()

    def _rebuild_effects(self):
        for w in self._effects_inner.winfo_children():
            w.destroy()
        self._check_vars = {}

        if not self._selected:
            tk.Label(self._effects_inner,
                     text="← Zuerst einen Container auswählen",
                     bg="#1a1a1a", fg="#555",
                     font=("Arial", 10, "italic")).pack(padx=12, pady=20)
            return

        if not self._effect_ids:
            tk.Label(self._effects_inner,
                     text="Keine Effekte gefunden. Effekte zuerst im Content Editor anlegen.",
                     bg="#1a1a1a", fg="#888",
                     font=("Arial", 9)).pack(padx=12, pady=12)
            return

        assigned = set(self._data[self._selected].get("effects", []))

        for eff_id in self._effect_ids:
            row = tk.Frame(self._effects_inner, bg="#1a1a1a")
            row.pack(fill="x", padx=8, pady=1)

            bv = tk.BooleanVar(value=(eff_id in assigned))
            self._check_vars[eff_id] = bv
            bv.trace_add("write",
                         lambda *_, eid=eff_id, v=bv: self._on_effect_toggle(eid, v))
            tk.Checkbutton(
                row, text=eff_id, variable=bv,
                bg="#1a1a1a", fg="#e0e0e0" if eff_id in assigned else "#888",
                selectcolor="#2a2a3a",
                font=("Arial", 9),
                activebackground="#1a1a2a").pack(side="left")

    def _on_effect_toggle(self, eff_id: str, bv: tk.BooleanVar):
        if not self._selected:
            return
        effects = self._data[self._selected].setdefault("effects", [])
        if bv.get():
            if eff_id not in effects:
                effects.append(eff_id)
        else:
            if eff_id in effects:
                effects.remove(eff_id)
        save_containers(self._data)
