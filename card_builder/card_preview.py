"""
card_builder/card_preview.py – Wiederverwendbares CardPreviewWidget.

Wird von card_builder/app.py UND random_builder/app.py genutzt.
Kapselt Canvas + SpellCardRenderer in einem eigenständigen Frame.
"""
import tkinter as tk

from .constants import CARD_W, CARD_H
from .CardTypes import get_renderer


class CardPreviewWidget(tk.Frame):
    """
    Eigenständiges Karten-Vorschau-Widget.

    Enthält:
      - Überschrift-Label
      - tk.Canvas in Kartengröße
      - Einen Renderer (SpellCardRenderer o.ä.) passend zum card_type

    Verwendung:
        preview = CardPreviewWidget(parent, label="Vorschau")
        preview.pack(...)
        preview.show(card_dict)   # Karte rendern
        preview.clear()           # Canvas leeren
    """

    def __init__(self, parent, label: str = "Vorschau", **kw):
        bg = kw.pop("bg", "#111")
        super().__init__(parent, bg=bg, **kw)

        tk.Label(self, text=label, bg=bg, fg="#aaa",
                 font=("Arial", 9, "bold")).pack(pady=(6, 2))

        self._canvas = tk.Canvas(
            self, width=CARD_W, height=CARD_H,
            bg="#000", highlightthickness=1,
            highlightbackground="#444")
        self._canvas.pack(pady=4, padx=8)

        self._renderer  = None
        self._card_type = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def show(self, card: dict) -> None:
        """Rendert eine Karte auf dem Canvas."""
        card_type = card.get("card_type", "Spells")
        # Renderer nur neu erstellen wenn sich der Kartentyp ändert
        if card_type != self._card_type or self._renderer is None:
            self._card_type = card_type
            self._renderer  = get_renderer(card_type)(self._canvas)
        self._renderer.render(card)

    def clear(self) -> None:
        """Löscht den Canvas und setzt den Renderer zurück."""
        self._canvas.delete("all")
        self._renderer  = None
        self._card_type = None

    # ── Interne Canvas-Referenz (für Abwärtskompatibilität) ────────────────────

    @property
    def canvas(self) -> tk.Canvas:
        return self._canvas
