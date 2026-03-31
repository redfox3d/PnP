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
        self.root.configure(bg="#1a1a1a")
        self._apply_style()
        self._current_panel = None
        from utils import enable_mousewheel_scroll
        enable_mousewheel_scroll(self.root)
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
                        fieldbackground="#2a2a2a",
                        background="#2a2a2a",
                        foreground="white",
                        selectbackground="#1a6e3c")

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
        self.root.geometry("360x430")
        self.root.resizable(False, False)

        # Center on screen
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"360x430+{(sw-360)//2}+{(sh-430)//2}")

        f = tk.Frame(self.root, bg="#1a1a1a")
        f.pack(fill="both", expand=True)

        tk.Label(f, text="✦  EMMA  ✦",
                 bg="#1a1a1a", fg="gold",
                 font=("Palatino Linotype", 22, "bold")).pack(pady=(28, 4))
        tk.Label(f, text="Game Tools",
                 bg="#1a1a1a", fg="#555",
                 font=("Arial", 9, "italic")).pack(pady=(0, 18))

        btn_kw = dict(width=22, font=("Arial", 11),
                      relief="flat", cursor="hand2")

        tk.Button(f, text="🃏  Card Builder",
                  bg="#1a3e8e", fg="white",
                  command=self.show_card_builder,
                  **btn_kw).pack(pady=5)

        tk.Button(f, text="📝  Content Editor",
                  bg="#553300", fg="white",
                  command=self.show_content_manager,
                  **btn_kw).pack(pady=5)

        tk.Button(f, text="🔮  AOE Designer",
                  bg="#3a1a5e", fg="white",
                  command=self.show_aoe_designer,
                  **btn_kw).pack(pady=5)

        tk.Button(f, text="🎲  Random Builder",
                  bg="#1a5e3a", fg="white",
                  command=self.show_random_builder,
                  **btn_kw).pack(pady=5)

        tk.Button(f, text="📦  Container Manager",
                  bg="#3a3a1a", fg="white",
                  command=self.show_container_manager,
                  **btn_kw).pack(pady=5)

    # ── Card Builder ──────────────────────────────────────────────────────────

    def show_card_builder(self):
        self._clear()
        self.root.title("Card Builder")
        self.root.geometry("1460x860")
        self.root.resizable(True, True)

        self._add_switch_bar("🃏 Card Builder", [
            ("📝 Content Editor",   self.show_content_manager),
            ("🔮 AOE Designer",     self.show_aoe_designer),
            ("🎲 Random Builder",   self.show_random_builder),
            ("📦 Container Manager",self.show_container_manager),
        ])

        from card_builder.app import CardBuilder
        container = tk.Frame(self.root, bg="#1a1a1a")
        container.pack(fill="both", expand=True)
        self._current_panel = CardBuilder(container_frame=container, root=self.root)

    # ── Content Manager ───────────────────────────────────────────────────────

    def show_content_manager(self):
        self._clear()
        self.root.title("Content Editor")
        self.root.geometry("1100x650")
        self.root.resizable(True, True)

        self._add_switch_bar("📝 Content Editor", [
            ("🃏 Card Builder",    self.show_card_builder),
            ("🔮 AOE Designer",    self.show_aoe_designer),
            ("🎲 Random Builder",  self.show_random_builder),
            ("📦 Container Mgr",   self.show_container_manager),
        ])

        # CardContent lives in a separate package next to card_builder
        content_dir = os.path.join(BASE_DIR, "CardContent")
        if content_dir not in sys.path:
            sys.path.insert(0, content_dir)

        from CardContent.content_manager import ContentManager
        container = tk.Frame(self.root, bg="#1a1a1a")
        container.pack(fill="both", expand=True)
        self._current_panel = ContentManager(root=container)

    # ── AOE Designer ──────────────────────────────────────────────────────────

    def show_aoe_designer(self):
        self._clear()
        self.root.title("AOE Designer")
        self.root.geometry("980x700")
        self.root.resizable(True, True)

        self._add_switch_bar("🔮 AOE Designer", [
            ("🃏 Card Builder",    self.show_card_builder),
            ("📝 Content Editor",  self.show_content_manager),
            ("🎲 Random Builder",  self.show_random_builder),
            ("📦 Container Mgr",   self.show_container_manager),
        ])

        from aoe_designer.app import AoEDesigner
        container = tk.Frame(self.root, bg="#1a1a1a")
        container.pack(fill="both", expand=True)
        self._current_panel = AoEDesigner(container)
        self._current_panel.pack(fill="both", expand=True)

    # ── Random Builder ────────────────────────────────────────────────────────

    def show_random_builder(self):
        self._clear()
        self.root.title("Random Builder")
        self.root.geometry("1300x800")
        self.root.resizable(True, True)

        self._add_switch_bar("🎲 Random Builder", [
            ("🃏 Card Builder",    self.show_card_builder),
            ("📝 Content Editor",  self.show_content_manager),
            ("🔮 AOE Designer",    self.show_aoe_designer),
            ("📦 Container Mgr",   self.show_container_manager),
        ])

        from random_builder.app import RandomBuilder
        container = tk.Frame(self.root, bg="#1a1a1a")
        container.pack(fill="both", expand=True)
        self._current_panel = RandomBuilder(container)
        self._current_panel.pack(fill="both", expand=True)

    # ── Container Manager ─────────────────────────────────────────────────────

    def show_container_manager(self):
        self._clear()
        self.root.title("Container Manager")
        self.root.geometry("900x600")
        self.root.resizable(True, True)

        self._add_switch_bar("📦 Container Manager", [
            ("🃏 Card Builder",    self.show_card_builder),
            ("📝 Content Editor",  self.show_content_manager),
            ("🎲 Random Builder",  self.show_random_builder),
        ])

        from container_manager.app import ContainerManager
        container = tk.Frame(self.root, bg="#1a1a1a")
        container.pack(fill="both", expand=True)
        self._current_panel = ContainerManager(container)
        self._current_panel.pack(fill="both", expand=True)

    # ── Shared switch bar ─────────────────────────────────────────────────────

    def _add_switch_bar(self, current: str, others: list):
        """Thin top bar: current tool label + buttons for all other tools."""
        bar = tk.Frame(self.root, bg="#0d0d0d", pady=3)
        bar.pack(fill="x", side="top")

        tk.Label(bar, text=current, bg="#0d0d0d", fg="#888",
                 font=("Arial", 8, "italic")).pack(side="left", padx=10)

        tk.Button(bar, text="⌂  Launcher",
                  command=self.show_launcher,
                  bg="#2a2a2a", fg="#aaaaaa",
                  font=("Arial", 8), relief="flat",
                  cursor="hand2").pack(side="right", padx=4)

        for label, cmd in reversed(others):
            tk.Button(bar, text=f"⇄  {label}",
                      command=cmd,
                      bg="#2a2a2a", fg="#aaaaaa",
                      font=("Arial", 8), relief="flat",
                      cursor="hand2").pack(side="right", padx=4)


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    App()
