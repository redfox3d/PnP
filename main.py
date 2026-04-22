"""
main.py – Entry point with launcher and in-process panel switching.

Panels:
    launcher        – start screen
    card_builder    – CardBuilder editor
    content_manager – CardContent manager
"""

import os
import sys
import tkinter as tk
from tkinter import ttk

# ── Colour palette ────────────────────────────────────────────────────────────
BG_ROOT     = "#0d1117"
BG_PANEL    = "#111827"
BG_CARD     = "#1a2035"
BG_INPUT    = "#1e2a3a"
BG_ROW_ALT  = "#161e2e"
BORDER      = "#2a3a50"
BORDER_LT   = "#1e2d42"
BTN_PRIMARY = "#1a3a6e"
BTN_SAVE    = "#1a5c3a"
BTN_DANGER  = "#5c1a1a"
BTN_NEUTRAL = "#1e2d42"
FG_TITLE    = "#e8f0ff"
FG_PRIMARY  = "#c8d4e8"
FG_MUTED    = "#6878a0"
FG_ACCENT   = "#5b9bd5"
SEL_BG      = "#1a4a7a"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# ── Set up paths before any card_builder imports ──────────────────────────────
from card_builder import data as _data, models as _models
from card_builder.materials import set_materials_dir

_data.set_data_dir(BASE_DIR)

CARDS_DIR = os.path.join(BASE_DIR, "cards")
_models.set_cards_dir(CARDS_DIR)
set_materials_dir(CARDS_DIR)

print(f"[main] BASE_DIR  → '{BASE_DIR}'")
print(f"[main] CARDS_DIR → '{CARDS_DIR}'")


# ── Central App controller ────────────────────────────────────────────────────

class App:
    """
    Owns the single Tk root window.
    Switches between launcher, card builder, and content manager
    by destroying the current panel and building the next one.
    """

    def __init__(self):
        self.root = tk.Tk()
        self.root.configure(bg=BG_ROOT)
        self._apply_style()
        self._current_panel = None
        self.show_launcher()
        self.root.mainloop()

    # ── Style ─────────────────────────────────────────────────────────────────

    def _apply_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TCombobox",
                        fieldbackground=BG_INPUT,
                        background=BG_INPUT,
                        foreground=FG_PRIMARY,
                        selectbackground=SEL_BG,
                        selectforeground=FG_PRIMARY,
                        arrowcolor=FG_ACCENT)
        style.map("TCombobox",
                  fieldbackground=[("readonly", BG_INPUT)],
                  foreground=[("readonly", FG_PRIMARY)])
        style.configure("TSeparator", background=BORDER)

    # ── Panel switching ───────────────────────────────────────────────────────

    def _clear(self):
        """Destroy all widgets in root."""
        for w in self.root.winfo_children():
            w.destroy()
        self._current_panel = None

    # ── Launcher ──────────────────────────────────────────────────────────────

    def show_launcher(self):
        self._clear()
        self.root.title("Emma – Game Tools")
        self.root.geometry("380x560")
        self.root.resizable(False, False)

        # Center on screen
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"380x560+{(sw-380)//2}+{(sh-560)//2}")

        f = tk.Frame(self.root, bg=BG_ROOT)
        f.pack(fill="both", expand=True, padx=20)

        tk.Label(f, text="✦ EMMA ✦",
                 bg=BG_ROOT, fg="gold",
                 font=("Palatino Linotype", 22, "bold")).pack(pady=(32, 4))
        tk.Label(f, text="Game Tools",
                 bg=BG_ROOT, fg=FG_MUTED,
                 font=("Segoe UI", 9, "italic")).pack(pady=(0, 22))

        btn_kw = dict(width=24, font=("Segoe UI", 10),
                      relief="flat", cursor="hand2", fg=FG_PRIMARY, pady=4)

        # ── Group 1: KARTEN (Card editing & generation) ──────────────────────
        tk.Label(f, text="━━━ KARTEN ━━━", bg=BG_ROOT, fg=FG_ACCENT,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(4, 2))

        tk.Button(f, text="🃏  Card Builder",
                  bg=BTN_PRIMARY,
                  command=self.show_card_builder,
                  **btn_kw).pack(pady=3, fill="x")

        tk.Button(f, text="🎲  Random Builder",
                  bg=BTN_PRIMARY,
                  command=self.show_random_builder,
                  **btn_kw).pack(pady=3, fill="x")

        # ── Group 2: TOOLS ────────────────────────────────────────────────────
        tk.Label(f, text="━━━ TOOLS ━━━", bg=BG_ROOT, fg=FG_ACCENT,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(8, 2))

        tk.Button(f, text="📦  Container Manager",
                  bg=BTN_NEUTRAL,
                  command=self.show_container_manager,
                  **btn_kw).pack(pady=3, fill="x")

        tk.Button(f, text="🔮  AOE Designer",
                  bg=BTN_NEUTRAL,
                  command=self.show_aoe_designer,
                  **btn_kw).pack(pady=3, fill="x")

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=12)

        # ── Group 3: CONTENT ──────────────────────────────────────────────────
        tk.Label(f, text="━━━ CONTENT ━━━", bg=BG_ROOT, fg=FG_ACCENT,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 2))

        tk.Button(f, text="📝  Content Editor",
                  bg=BTN_PRIMARY,
                  command=self.show_content_manager,
                  **btn_kw).pack(pady=3, fill="x")

        tk.Button(f, text="⚗️  Ingredient Editor",
                  bg=BTN_NEUTRAL,
                  command=self._open_ingredient_editor,
                  **btn_kw).pack(pady=3, fill="x")

        tk.Button(f, text="🎯  Effect Types",
                  bg=BTN_NEUTRAL,
                  command=self._open_effect_types,
                  **btn_kw).pack(pady=3, fill="x")

        tk.Button(f, text="🎲  Dice Settings",
                  bg=BTN_NEUTRAL,
                  command=self._open_dice_editor,
                  **btn_kw).pack(pady=3, fill="x")

    def _open_dice_editor(self):
        from random_builder.dice_models import load_dice_config, save_dice_config, die_avg
        import tkinter as tk
        from tkinter import messagebox

        cfg = load_dice_config()
        dlg = tk.Toplevel(self.root)
        dlg.title("Würfel Einstellungen")
        dlg.geometry("400x480")
        dlg.resizable(False, True)
        dlg.configure(bg="#1a1a2a")

        BG  = "#1a1a2a"
        BG2 = "#252535"
        FG  = "white"

        tk.Label(dlg, text="🎲  Würfel", bg=BG, fg="#ffdd88",
                 font=("Segoe UI", 13, "bold")).pack(pady=(12, 2))
        tk.Label(dlg,
                 text="ID = Würfelausdruck (z.B. D6, 2D4, D8).  Avg = Erwartungswert.\n"
                      "Generator wählt N×ID sodass N×Avg ≈ Zielwert → z.B. '4D4'.",
                 bg=BG, fg="#888", font=("Segoe UI", 8), justify="left").pack(padx=16)

        # ── Dice list ─────────────────────────────────────────────────────────
        list_frame = tk.Frame(dlg, bg=BG2, relief="groove", bd=1)
        list_frame.pack(fill="x", padx=16, pady=8)

        # Header
        hdr = tk.Frame(list_frame, bg=BG2)
        hdr.pack(fill="x", padx=6, pady=(4, 0))
        for txt, w in [("ID", 10), ("Avg", 8), ("Vorschau", 14)]:
            tk.Label(hdr, text=txt, width=w, bg=BG2, fg="#aaaacc",
                     font=("Segoe UI", 8, "bold"), anchor="w").pack(side="left")

        dice_rows  = []   # list of (id_var, avg_var)
        rows_frame = tk.Frame(list_frame, bg=BG2)
        rows_frame.pack(fill="x", padx=6, pady=4)

        def _preview(id_v, avg_v):
            """Show what the die produces for avg × 3 as a sample."""
            try:
                avg = float(avg_v.get())
                did = id_v.get().strip()
                n   = max(1, round(avg * 3 / avg))   # always 3 for preview
                return f"3×{avg:.1f} → {3}{did}" if n != 1 else did
            except Exception:
                return "?"

        preview_vars = []

        def _rebuild_rows():
            for w in rows_frame.winfo_children():
                w.destroy()
            preview_vars.clear()
            for i, (id_v, avg_v) in enumerate(dice_rows):
                row = tk.Frame(rows_frame, bg=BG2)
                row.pack(fill="x", pady=2)

                id_entry = tk.Entry(row, textvariable=id_v, width=10,
                                    bg="#2a2a3a", fg="#aaddff",
                                    insertbackground=FG, font=("Courier", 9))
                id_entry.pack(side="left", padx=2)

                avg_entry = tk.Entry(row, textvariable=avg_v, width=7,
                                     bg="#2a2a3a", fg="#ffdd88",
                                     insertbackground=FG, font=("Courier", 9))
                avg_entry.pack(side="left", padx=2)

                pv = tk.StringVar()
                preview_vars.append(pv)
                tk.Label(row, textvariable=pv, width=14, bg=BG2, fg="#88cc88",
                         font=("Courier", 8), anchor="w").pack(side="left", padx=4)

                def _upd_preview(*_, iv=id_v, av=avg_v, pvar=pv):
                    try:
                        avg = float(av.get())
                        did = iv.get().strip()
                        # show sample N=3 result
                        n3 = max(1, round(3 * avg / avg)) if avg else 1
                        pvar.set(f"z.B. 4×avg={4*avg:.1f} → 4{did}")
                    except Exception:
                        pvar.set("")
                id_v.trace_add("write", _upd_preview)
                avg_v.trace_add("write", _upd_preview)
                _upd_preview()

                idx = i
                tk.Button(row, text="✕", font=("Arial", 7), padx=3, pady=0,
                          bg="#3a1a1a", fg="#ff8888",
                          command=lambda i=idx: (_remove_row(i))
                          ).pack(side="left", padx=2)

        def _remove_row(idx):
            if 0 <= idx < len(dice_rows):
                dice_rows.pop(idx)
            _rebuild_rows()

        def _add_row():
            dice_rows.append((tk.StringVar(value="D6"), tk.StringVar(value="3.5")))
            _rebuild_rows()

        # Populate from config (migrate old 'value' entries automatically)
        for d in cfg.get("dice", []):
            avg_val = die_avg(d)
            dice_rows.append((tk.StringVar(value=d.get("id", "D6")),
                               tk.StringVar(value=str(avg_val))))
        _rebuild_rows()

        tk.Button(list_frame, text="+ Würfel hinzufügen", command=_add_row,
                  bg="#1a3a6e", fg=FG, font=("Segoe UI", 8),
                  relief="flat").pack(pady=(2, 8))

        # ── dice_can_chance ───────────────────────────────────────────────────
        sep_f = tk.Frame(dlg, bg=BG)
        sep_f.pack(fill="x", padx=16, pady=(0, 4))
        tk.Label(sep_f, text="Chance (0–1) dass 'dice_allowed'-Variablen Würfel benutzen:",
                 bg=BG, fg="#aaa", font=("Segoe UI", 8)).pack(anchor="w")
        chance_var = tk.StringVar(value=str(cfg.get("dice_can_chance", 0.5)))
        tk.Entry(sep_f, textvariable=chance_var, width=8,
                 bg="#2a2a3a", fg=FG, insertbackground=FG,
                 font=("Courier", 10)).pack(anchor="w", pady=(2, 0))

        # ── Save ──────────────────────────────────────────────────────────────
        def _save():
            new_dice = []
            for id_v, avg_v in dice_rows:
                did = id_v.get().strip()
                if not did:
                    continue
                try:
                    avg = float(avg_v.get())
                except ValueError:
                    messagebox.showwarning("Fehler",
                        f"Ungültiger Avg-Wert für '{did}'", parent=dlg)
                    return
                new_dice.append({"id": did, "avg": avg})
            new_dice.sort(key=lambda d: d["avg"])
            try:
                chance = max(0.0, min(1.0, float(chance_var.get())))
            except ValueError:
                messagebox.showwarning("Fehler", "Ungültige Wahrscheinlichkeit", parent=dlg)
                return
            save_dice_config({"dice": new_dice, "dice_can_chance": chance})
            dlg.destroy()

        tk.Button(dlg, text="💾  Speichern", command=_save,
                  bg="#1a6e3c", fg=FG, font=("Segoe UI", 10, "bold"),
                  width=24).pack(pady=10)

    def _open_effect_types(self):
        import json
        effects_path = os.path.join(BASE_DIR, "CardContent", "cc_data", "effects.json")
        try:
            with open(effects_path, encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"Effect": []}
        from CardContent.effect_type_panel import EffectTypePanel
        EffectTypePanel(self.root, data)

    def _open_ingredient_editor(self):
        from card_builder.ingredient_editor import IngredientEditor
        IngredientEditor(self.root)

    # ── Container Manager ─────────────────────────────────────────────────────

    def show_container_manager(self):
        self._clear()
        self.root.title("Container Manager")
        self.root.geometry("1200x750")
        self.root.resizable(True, True)

        self._add_switch_bar("📦 Container Manager", [
            ("🃏 Card Builder",   self.show_card_builder),
            ("📝 Content Editor", self.show_content_manager),
        ])

        from container_manager.app import ContainerManager
        container = tk.Frame(self.root, bg=BG_ROOT)
        container.pack(fill="both", expand=True)
        self._current_panel = ContainerManager(container)
        self._current_panel.pack(fill="both", expand=True)

    # ── Random Builder ────────────────────────────────────────────────────────

    def show_random_builder(self):
        self._clear()
        self.root.title("Random Builder")
        self.root.geometry("1500x860")
        self.root.resizable(True, True)

        self._add_switch_bar("🎲 Random Builder", [
            ("🃏 Card Builder",   self.show_card_builder),
            ("📝 Content Editor", self.show_content_manager),
        ])

        from random_builder.app import RandomBuilder
        container = tk.Frame(self.root, bg=BG_ROOT)
        container.pack(fill="both", expand=True)
        self._current_panel = RandomBuilder(container)
        self._current_panel.pack(fill="both", expand=True)

    # ── Card Builder ──────────────────────────────────────────────────────────

    def show_card_builder(self):
        self._clear()
        self.root.title("Card Builder")
        self.root.geometry("1460x860")
        self.root.resizable(True, True)

        self._add_switch_bar("🃏 Card Builder", [
            ("📝 Content Editor", self.show_content_manager),
            ("🔮 AOE Designer",   self.show_aoe_designer),
        ])

        from card_builder.app import CardBuilder
        container = tk.Frame(self.root, bg=BG_ROOT)
        container.pack(fill="both", expand=True)
        self._current_panel = CardBuilder(container_frame=container, root=self.root)

    # ── Content Manager ───────────────────────────────────────────────────────

    def show_content_manager(self):
        self._clear()
        self.root.title("Content Editor")
        self.root.geometry("1100x650")
        self.root.resizable(True, True)

        self._add_switch_bar("📝 Content Editor", [
            ("🃏 Card Builder",  self.show_card_builder),
            ("🔮 AOE Designer",  self.show_aoe_designer),
        ])

        # CardContent lives in a separate package next to card_builder
        content_dir = os.path.join(BASE_DIR, "CardContent")
        if content_dir not in sys.path:
            sys.path.insert(0, content_dir)

        from CardContent.content_manager import ContentManager
        container = tk.Frame(self.root, bg=BG_ROOT)
        container.pack(fill="both", expand=True)
        self._current_panel = ContentManager(root=container)

    # ── AOE Designer ──────────────────────────────────────────────────────────

    def show_aoe_designer(self):
        self._clear()
        self.root.title("AOE Designer")
        self.root.geometry("980x700")
        self.root.resizable(True, True)

        self._add_switch_bar("🔮 AOE Designer", [
            ("🃏 Card Builder",   self.show_card_builder),
            ("📝 Content Editor", self.show_content_manager),
        ])

        from aoe_designer.app import AoEDesigner
        container = tk.Frame(self.root, bg=BG_ROOT)
        container.pack(fill="both", expand=True)
        self._current_panel = AoEDesigner(container)
        self._current_panel.pack(fill="both", expand=True)

    # ── Shared switch bar ─────────────────────────────────────────────────────

    def _add_switch_bar(self, current: str, others: list):
        """Thin top bar: current tool label + buttons for all other tools."""
        bar = tk.Frame(self.root, bg=BG_ROOT, height=32)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        tk.Label(bar, text=current, bg=BG_ROOT, fg=FG_ACCENT,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=10)

        tk.Button(bar, text="⌂ Launcher",
                  command=self.show_launcher,
                  bg=BTN_NEUTRAL, fg=FG_PRIMARY,
                  font=("Segoe UI", 8), relief="flat",
                  cursor="hand2").pack(side="right", padx=4, pady=4)

        for label, cmd in reversed(others):
            tk.Button(bar, text=f"⇄  {label}",
                      command=cmd,
                      bg=BTN_NEUTRAL, fg=FG_PRIMARY,
                      font=("Segoe UI", 8), relief="flat",
                      cursor="hand2").pack(side="right", padx=4, pady=4)

        # 1px separator line at bottom of bar
        tk.Frame(self.root, bg=BG_CARD, height=1).pack(fill="x", side="top")


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    App()
