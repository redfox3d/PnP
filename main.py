import os
import sys
import tkinter as tk
from tkinter import ttk

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "card_builder"))

# ── ERST Pfade setzen ─────────────────────────────────────
from card_builder import data as _data, models as _models

_data.set_data_dir(BASE_DIR)

CARDS_FILE = os.path.join(BASE_DIR, "cc_builder", "manager_data", "cards.json")
print(f"[main] cards file → '{CARDS_FILE}'  exists={os.path.exists(CARDS_FILE)}")
_models.set_cards_file(CARDS_FILE)

# ── DANN erst CardBuilder importieren ─────────────────────
from card_builder.app import CardBuilder

root = tk.Tk()
style = ttk.Style(root)
try:
    style.theme_use("clam")
except Exception:
    pass

style.configure("TCombobox",
                fieldbackground="#2a2a2a",
                background="#2a2a2a",
                foreground="white",
                selectbackground="#1a6e3c")

root.configure(bg="#1a1a1a")
app = CardBuilder(root)
root.mainloop()