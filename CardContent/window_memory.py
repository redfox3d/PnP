"""
window_memory.py – Saves and restores tkinter window geometry.
"""

import json
import os

_HERE           = os.path.dirname(os.path.abspath(__file__))
WINDOW_POS_FILE = os.path.join(_HERE, "manager_data", "window_positions.json")


class WindowMemory:
    """Persists window position + size across sessions."""

    def __init__(self, filepath: str = WINDOW_POS_FILE):
        self.filepath = filepath
        self._data: dict = {}
        self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def _save(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)
        with open(self.filepath, "w") as f:
            json.dump(self._data, f, indent=4)

    def restore(self, window, key: str, default: str = "600x400") -> None:
        """Apply saved geometry (or default), then auto-save on every resize/move."""
        window.geometry(self._data.get(key, default))

        def _on_cfg(event):
            if event.widget == window:
                self._data[key] = window.geometry()
                self._save()

        window.bind("<Configure>", _on_cfg)


# Module-level singleton – shared by all cc_builder windows
wm = WindowMemory()