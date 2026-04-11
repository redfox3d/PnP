"""
base_card.py – Shared widgets and BaseCardEditor used by all card type editors.

Shared widgets:
    ArtworkPicker   – browse + center-crop thumbnail
    TagSelector     – autocomplete multi-select with pills
    ContentSelector – picks a content item, shows {X} inputs + option dropdowns

BaseCardEditor – common header (name, artwork, type badge)
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog

try:
    from PIL import Image, ImageTk
    _PIL = True
except ImportError:
    _PIL = False


# ── ArtworkPicker ─────────────────────────────────────────────────────────────

class ArtworkPicker(tk.Frame):
    THUMB_W = 180
    THUMB_H = 130

    def __init__(self, parent, path: str, on_change=None, **kw):
        super().__init__(parent, bg="#1a1a1a", **kw)
        self._path      = path
        self._on_change = on_change
        self._img_ref   = None
        self._build()

    def get(self) -> str:
        return self._path

    def _build(self):
        self._canvas = tk.Canvas(self, width=self.THUMB_W, height=self.THUMB_H,
                                 bg="#222", highlightthickness=1,
                                 highlightbackground="#444")
        self._canvas.pack()
        self._canvas.bind("<Button-1>", self._browse)

        btn_row = tk.Frame(self, bg="#1a1a1a")
        btn_row.pack(fill="x", pady=2)
        tk.Button(btn_row, text="📁 Artwork", command=self._browse,
                  font=("Arial", 8), bg="#333", fg="white").pack(side="left", padx=2)
        tk.Button(btn_row, text="✕", command=self._clear,
                  font=("Arial", 8), bg="#333", fg="#ff6666").pack(side="left", padx=2)
        self._path_label = tk.Label(self, text=self._short(),
                                    bg="#1a1a1a", fg="#666",
                                    font=("Arial", 7), wraplength=180)
        self._path_label.pack()
        self._render()

    def _browse(self, _=None):
        path = filedialog.askopenfilename(
            title="Artwork wählen",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All", "*.*")])
        if path:
            self._path = path
            self._path_label.config(text=self._short())
            self._render()
            if self._on_change:
                self._on_change()

    def _clear(self):
        self._path = ""
        self._path_label.config(text="")
        self._canvas.delete("all")
        self._img_ref = None
        if self._on_change:
            self._on_change()

    def _short(self) -> str:
        return os.path.basename(self._path) if self._path else "(kein Artwork)"

    def _render(self):
        """Center-crop image to fill the thumbnail exactly."""
        self._canvas.delete("all")
        if not self._path or not os.path.exists(self._path):
            self._canvas.create_text(self.THUMB_W//2, self.THUMB_H//2,
                                     text="Artwork\n(klicken)",
                                     fill="#555", justify="center")
            return
        if not _PIL:
            self._canvas.create_text(self.THUMB_W//2, self.THUMB_H//2,
                                     text="PIL fehlt", fill="#f55")
            return
        try:
            img = Image.open(self._path)
            tw, th = self.THUMB_W, self.THUMB_H
            # center crop
            iw, ih = img.size
            scale  = max(tw / iw, th / ih)
            nw, nh = int(iw * scale), int(ih * scale)
            img    = img.resize((nw, nh), Image.LANCZOS)
            left   = (nw - tw) // 2
            top    = (nh - th) // 2
            img    = img.crop((left, top, left + tw, top + th))
            self._img_ref = ImageTk.PhotoImage(img)
            self._canvas.create_image(0, 0, image=self._img_ref, anchor="nw")
        except Exception as e:
            self._canvas.create_text(self.THUMB_W//2, self.THUMB_H//2,
                                     text=f"Fehler:\n{e}", fill="#f55",
                                     justify="center")


# ── TagSelector ───────────────────────────────────────────────────────────────

class TagSelector(tk.Frame):
    def __init__(self, parent, values: list, selected: list,
                 on_change=None, max_items: int = 0, **kw):
        super().__init__(parent, **kw)
        self._all     = list(values)
        self._sel     = list(selected)
        self._change  = on_change
        self._max     = max_items
        self._build()

    def get(self) -> list:
        return list(self._sel)

    def set_values(self, values: list):
        self._all = list(values)
        self._cb["values"] = self._all

    def _build(self):
        row = tk.Frame(self, bg=self.cget("bg"))
        row.pack(fill="x")
        self._var = tk.StringVar()
        self._cb  = ttk.Combobox(row, textvariable=self._var,
                                  values=self._all, width=18)
        self._cb.pack(side="left", padx=2)
        self._cb.bind("<Tab>",               self._tab)
        self._cb.bind("<Return>",            self._add)
        self._cb.bind("<<ComboboxSelected>>", self._add)
        self._cb.bind("<KeyRelease>",        self._filter)
        tk.Button(row, text="＋", command=self._add,
                  font=("Arial", 8), width=2).pack(side="left", padx=2)
        self._tags = tk.Frame(self, bg=self.cget("bg"))
        self._tags.pack(fill="x", pady=2)
        self._rebuild()

    def _filter(self, _=None):
        t = self._var.get().lower()
        f = [v for v in self._all if t in v.lower()]
        self._cb["values"] = f if f else self._all

    def _tab(self, _=None):
        t = self._var.get().lower()
        m = [v for v in self._all if v.lower().startswith(t)]
        if m:
            self._var.set(m[0])
        return "break"

    def _add(self, _=None):
        v = self._var.get().strip()
        if not v or v in self._sel:
            self._var.set(""); return
        if self._max and len(self._sel) >= self._max:
            self._var.set(""); return
        self._sel.append(v)
        if v not in self._all:
            self._all.append(v)
            self._all.sort()
            self._cb["values"] = self._all
        self._var.set("")
        self._rebuild()
        if self._change: self._change()

    def _remove(self, v):
        if v in self._sel: self._sel.remove(v)
        self._rebuild()
        if self._change: self._change()

    def _rebuild(self):
        for w in self._tags.winfo_children(): w.destroy()
        for v in self._sel:
            p = tk.Frame(self._tags, relief="solid", bd=1, bg="#2a3a2a")
            p.pack(side="left", padx=2, pady=1)
            tk.Label(p, text=v, bg="#2a3a2a", fg="#aaffaa",
                     font=("Arial", 8)).pack(side="left", padx=3)
            tk.Button(p, text="✕", bg="#2a3a2a", fg="#ff6666",
                      font=("Arial", 7), relief="flat",
                      command=lambda val=v: self._remove(val)).pack(side="left")


# ── ContentSelector ───────────────────────────────────────────────────────────

class ContentSelector(tk.Frame):
    """
    Dropdown to pick a content item (Effect/Cost/Condition/Trigger).
    Automatically shows:
      - Entry fields for each {X} variable
      - Dropdowns for each [a,b,c] option

    Stores result as:
        {
            "content_id":  "Draw",
            "var_values":  {"X": "3"},
            "opt_values":  {"0": "top"},
        }

    Calls on_change() whenever anything changes.
    Calls on_text_change(rendered_text) with the final display string.
    """

    def __init__(self, parent, content_ids: list, data_getter,
                 value: dict, on_change=None, on_text_change=None,
                 label: str = "Effect", bg="#1a1a1a", **kw):
        super().__init__(parent, bg=bg, **kw)
        self._ids          = content_ids
        self._get_item     = data_getter   # fn(id) -> item dict or None
        self._val          = value         # mutable dict stored in card
        self._on_change    = on_change
        self._on_text      = on_text_change
        self._label        = label
        self._bg           = bg
        self._build()

    def _build(self):
        row = tk.Frame(self, bg=self._bg)
        row.pack(fill="x")
        tk.Label(row, text=self._label + ":", bg=self._bg, fg="#ccc",
                 font=("Arial", 9, "bold")).pack(side="left", padx=4)

        self._id_var = tk.StringVar(value=self._val.get("content_id", ""))
        cb = ttk.Combobox(row, textvariable=self._id_var,
                          values=self._ids, width=20)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", self._on_id_change)
        cb.bind("<KeyRelease>",         self._filter)

        self._inputs_frame = tk.Frame(self, bg=self._bg)
        self._inputs_frame.pack(fill="x", padx=4, pady=2)
        self._rebuild_inputs()

    def _filter(self, _=None):
        t = self._id_var.get().lower()
        f = [i for i in self._ids if t in i.lower()]
        # update combobox values for filtering
        self._id_var.set(self._id_var.get())

    def _on_id_change(self, _=None):
        new_id = self._id_var.get()
        self._val["content_id"]  = new_id
        self._val["var_values"]  = {}
        self._val["opt_values"]  = {}
        self._rebuild_inputs()
        self._emit()

    def _rebuild_inputs(self):
        for w in self._inputs_frame.winfo_children():
            w.destroy()

        cid  = self._val.get("content_id", "")
        item = self._get_item(cid) if cid else None
        if not item:
            return

        variables = item.get("variables", {})
        options   = item.get("options", {})

        if not variables and not options:
            return

        var_vals = self._val.setdefault("var_values", {})
        opt_vals = self._val.setdefault("opt_values", {})

        # Variable inputs
        for vname in variables:
            row = tk.Frame(self._inputs_frame, bg=self._bg)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f"{{{vname}}}:", bg=self._bg, fg="#88aaff",
                     font=("Arial", 9, "bold"), width=8).pack(side="left")
            var = tk.StringVar(value=str(var_vals.get(vname, "")))
            def _tv(*_, n=vname, v=var):
                var_vals[n] = v.get()
                self._emit()
            var.trace_add("write", _tv)
            tk.Entry(row, textvariable=var, width=8,
                     bg="#2a2a2a", fg="white",
                     insertbackground="white").pack(side="left", padx=4)

        # Option dropdowns
        for opt_key, opt in options.items():
            choices = opt.get("choices", [])
            if not choices:
                continue
            row = tk.Frame(self._inputs_frame, bg=self._bg)
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f"OPT{opt_key}:", bg=self._bg, fg="#ffaa44",
                     font=("Arial", 9, "bold"), width=8).pack(side="left")
            var = tk.StringVar(value=opt_vals.get(opt_key, choices[0]))
            def _to(*_, k=opt_key, v=var):
                opt_vals[k] = v.get()
                self._emit()
            var.trace_add("write", _to)
            ttk.Combobox(row, textvariable=var, values=choices,
                         state="readonly", width=16).pack(side="left", padx=4)

    def _emit(self):
        """Render the content text and notify."""
        cid  = self._val.get("content_id", "")
        item = self._get_item(cid) if cid else None
        rendered = ""
        if item:
            from card_builder.CardTypes.base_card import _render_content
            rendered = _render_content(item, self._val)
        if self._on_text:
            self._on_text(rendered)
        if self._on_change:
            self._on_change()


def _render_content(item: dict, val: dict) -> str:
    """
    Render a content item's content_text by substituting var_values and opt_values.
    Falls back to effect_text for old-format items.
    Supports [if X=1]...[else]...[/if] syntax via template_parser if available.
    """
    template = item.get("content_text") or item.get("effect_text", "")
    var_vals = val.get("var_values", {})
    opt_vals = val.get("opt_values", {})

    try:
        from CardContent.template_parser import render_display_text
        return render_display_text(template, var_vals, opt_vals)
    except ImportError:
        pass

    # Fallback: simple substitution
    import re
    text = template
    for name, v in var_vals.items():
        text = text.replace(f"{{{name}}}", str(v) if v else name)
    opt_idx = 0
    def _repl(m):
        nonlocal opt_idx
        choice = opt_vals.get(str(opt_idx), m.group(1).split(",")[0].strip())
        opt_idx += 1
        return choice
    text = re.sub(r"\[([^\]]+)\]", _repl, text)
    return text


# ── BaseCardEditor ────────────────────────────────────────────────────────────

class BaseCardEditor(tk.Frame):
    """
    Base class for all card type editors.
    Provides:
      - Scrollable canvas layout
      - Common header: name, type badge, artwork picker
      - Helper methods: _lbl(), _sep(), _row()
    Subclasses implement _build_type_fields().
    """

    BG = "#1a1a1a"

    def __init__(self, parent, card: dict, on_change=None, **kw):
        super().__init__(parent, bg=self.BG, **kw)
        self.card      = card
        self.on_change = on_change
        self._setup_scroll()
        self._build_header()
        self._build_type_fields()

    # ── Scrollable inner frame ────────────────────────────────────────────────

    def _setup_scroll(self):
        vsb    = tk.Scrollbar(self, orient="vertical")
        vsb.pack(side="right", fill="y")
        canvas = tk.Canvas(self, bg=self.BG,
                           yscrollcommand=vsb.set,
                           highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        vsb.config(command=canvas.yview)

        self._f   = tk.Frame(canvas, bg=self.BG)
        self._win = canvas.create_window((0, 0), window=self._f, anchor="nw")
        self._f.bind("<Configure>",
                     lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(self._win, width=e.width))
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-e.delta/120), "units"))
        self._f.columnconfigure(0, weight=1)

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self):
        from card_builder.models import CARD_TYPE_PARENT
        from card_builder.constants import ELEMENTS

        ct  = self.card.get("card_type", "")
        cat = CARD_TYPE_PARENT.get(ct, "")

        # Name + type badge row
        row = tk.Frame(self._f, bg=self.BG)
        row.pack(fill="x", padx=8, pady=6)

        tk.Label(row, text="Name:", bg=self.BG, fg="#ccc",
                 font=("Arial", 9)).pack(side="left")
        self._name_var = tk.StringVar(value=self.card.get("name", ""))
        self._name_var.trace_add("write", self._name_changed)
        tk.Entry(row, textvariable=self._name_var, width=26,
                 bg="#2a2a2a", fg="white", insertbackground="white",
                 font=("Arial", 9)).pack(side="left", padx=(2, 12))

        # Element selector for Spells
        if ct == "Spells":
            tk.Label(row, text="Element:", bg=self.BG, fg="#ccc",
                     font=("Arial", 9)).pack(side="left")
            self._elem_var = tk.StringVar(value=self.card.get("element", "Fire"))
            self._elem_var.trace_add("write", self._elem_changed)
            ttk.Combobox(row, textvariable=self._elem_var,
                         values=ELEMENTS, width=10, state="readonly").pack(
                side="left", padx=2)

        tk.Label(row, text=f"[{cat} › {ct}]", bg=self.BG, fg="#555",
                 font=("Arial", 8, "italic")).pack(side="left", padx=8)

        # Artwork (not for Spells/Prowess)
        from card_builder.constants import BOX_CARD_TYPES
        if ct not in BOX_CARD_TYPES:
            art_row = tk.Frame(self._f, bg=self.BG)
            art_row.pack(fill="x", padx=8, pady=4)
            self._art = ArtworkPicker(art_row, self.card.get("artwork", ""),
                                      on_change=self._art_changed)
            self._art.pack(side="left")
        else:
            self._art = None

        self._sep()

    def _name_changed(self, *_):
        self.card["name"] = self._name_var.get()
        if self.on_change: self.on_change()

    def _elem_changed(self, *_):
        self.card["element"] = self._elem_var.get()
        if self.on_change: self.on_change()

    def _art_changed(self):
        if self._art:
            self.card["artwork"] = self._art.get()
        if self.on_change: self.on_change()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _sep(self):
        ttk.Separator(self._f, orient="horizontal").pack(
            fill="x", padx=8, pady=4)

    def _lbl(self, text, parent=None) -> tk.Label:
        p = parent or self._f
        return tk.Label(p, text=text, bg=self.BG, fg="#ccc", font=("Arial", 9))

    def _row(self) -> tk.Frame:
        f = tk.Frame(self._f, bg=self.BG)
        f.pack(fill="x", padx=8, pady=3)
        return f

    # ── To be implemented by subclasses ───────────────────────────────────────

    def _build_type_fields(self):
        raise NotImplementedError
