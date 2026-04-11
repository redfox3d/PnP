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

        # ── Group 1: KARTEN ───────────────────────────────────────────────────
        tk.Label(f, text="KARTEN", bg=BG_ROOT, fg=FG_MUTED,
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(4, 2))

        tk.Button(f, text="🃏  Card Builder",
                  bg=BTN_PRIMARY,
                  command=self.show_card_builder,
                  **btn_kw).pack(pady=3, fill="x")

        tk.Button(f, text="🔮  AOE Designer",
                  bg=BTN_NEUTRAL,
                  command=self.show_aoe_designer,
                  **btn_kw).pack(pady=3, fill="x")

        tk.Button(f, text="🎲  Random Builder",
                  bg=BTN_NEUTRAL,
                  command=self.show_random_builder,
                  **btn_kw).pack(pady=3, fill="x")

        tk.Button(f, text="📦  Container Manager",
                  bg=BTN_NEUTRAL,
                  command=self.show_container_manager,
                  **btn_kw).pack(pady=3, fill="x")

        ttk.Separator(f, orient="horizontal").pack(fill="x", pady=12)

        # ── Group 2: CONTENT ──────────────────────────────────────────────────
        tk.Label(f, text="CONTENT", bg=BG_ROOT, fg=FG_MUTED,
                 font=("Segoe UI", 7, "bold")).pack(anchor="w", pady=(0, 2))

        tk.Button(f, text="📝  Content Editor",
                  bg=BTN_PRIMARY,
                  command=self.show_content_manager,
                  **btn_kw).pack(pady=3, fill="x")

        tk.Button(f, text="⚗️  Material-Effekte",
                  bg=BTN_NEUTRAL,
                  command=self._open_material_effects,
                  **btn_kw).pack(pady=3, fill="x")

        tk.Button(f, text="🎯  Effekt Primärtypen",
                  bg=BTN_NEUTRAL,
                  command=self._open_effect_types,
                  **btn_kw).pack(pady=3, fill="x")

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

    def _open_material_effects(self):
        from card_builder.material_editor import MaterialEffectEditor
        MaterialEffectEditor(self.root)

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
