"""
CardContentManager.py – Entry point.
Run this file directly to open the Content Manager.

All logic has been split into CardContent/:
    CardContent/template_parser.py   – parse_template, render_content_text
    CardContent/window_memory.py     – WindowMemory singleton
    CardContent/content_editor.py    – ContentEditor, ElementWeightsEditor, ConditionsEditor
    CardContent/content_manager.py   – ContentManager (table, filter, CRUD)
"""

import tkinter as tk
from CardContent.content_manager import ContentManager

if __name__ == "__main__":
    root = tk.Tk()
    app  = ContentManager(root)
    root.mainloop()
