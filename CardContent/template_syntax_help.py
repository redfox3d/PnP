"""
template_syntax_help.py – Syntax reference window.
"""

import tkinter as tk
from tkinter import ttk


HELP_TEXT = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CONTENT BOX  –  Template-Struktur
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{X}              Freie Variable (Zahl oder Text)
                 Wird im Karten-Editor ausgefüllt.
                 Beispiel:  Draw {X} Cards.

[a, b, c]        Dropdown-Auswahl
                 Wird im Karten-Editor als Dropdown angezeigt.
                 Beispiel:  Draw from the [top, random, bottom].

[, Apfel]        Leere erste Option = "kein Wert"
                 Beispiel:  Draw [, Apfel] Cards.
                 → Option 1: (leer)  Option 2: Apfel

[\Elements]      Alle Elemente als Auswahl (automatisch)
                 Expandiert zu [Fire, Metal, Ice, Nature, Blood, Quinta].
                 Jedes Element bekommt seine eigene Gewichtung.
                 Beispiel:  Deal [\Elements] damage.

[\AOE]           Alle gespeicherten AOE-Muster als Auswahl
                 Expandiert zu den IDs aus dem AOE Designer.
                 Beispiel:  Cast in pattern [\AOE].


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CONTENT TEXT / REMINDER TEXT  –  Bedingter Text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{X}              Wert der Variable einfügen
                 Beispiel:  Draw {X} Cards.

[if X=1]...[/if]
                 Einfache Bedingung

[if X=1]...[else]...[/if]
                 If / Else

[if X=1]...[elif X=2-5]...[else]...[/if]
                 If / Elif / Else


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  VERGLEICHSOPERATOREN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

X=1              gleich
X!=1             ungleich
X>1              größer als
X<1              kleiner als
X>=1             größer oder gleich
X<=1             kleiner oder gleich
X=1-5            Range (inkl. 1 und 5)


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  OPTIONEN  (OPT0, OPT1, ...)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OPT0             erste [a,b,c]-Auswahl in der Sigil
OPT1             zweite Auswahl, usw.

[if OPT0=top]from the top[/if]
                 Prüft ob Option 0 "top" ist

[if OPT0=]Draw Cards.[elif OPT0=Apfel]Draw Apfel Cards.[/if]
                 Leerer Wert = erste Option war leer ("")


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  VOLLSTÄNDIGES BEISPIEL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Sigil:
    Draw {X} cards from the [top, random, bottom].

Content Text:
    [if X=1]Draw a Card[else]Draw {X} Cards[/if]
    [if OPT0=top] from the top.[elif OPT0=random] randomly.[else] from the bottom.[/if]

Bei X=1, OPT0=top:
    → "Draw a Card from the top."

Bei X=3, OPT0=random:
    → "Draw 3 Cards randomly."


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  IDs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Content ID:      Draw
Variable X:      Draw.0  (automatisch generiert)
Choice "top":    Draw.1  (automatisch generiert)

Umbenennung "Draw" → "Discard":
    → Content ID wird "Discard"
    → Draw.0 wird Discard.0
    → Draw.1 wird Discard.1
    → Alle Conditions-Referenzen werden aktualisiert
"""


class SyntaxHelpWindow(tk.Toplevel):

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Syntax Referenz")
        self.geometry("560x640")
        self.resizable(True, True)
        self._build()

    def _build(self):
        frame = tk.Frame(self)
        frame.pack(fill="both", expand=True)

        vsb = tk.Scrollbar(frame, orient="vertical")
        vsb.pack(side="right", fill="y")

        txt = tk.Text(frame, wrap="word", yscrollcommand=vsb.set,
                      font=("Consolas", 10), bg="#1a1a1a", fg="#e0e0e0",
                      padx=12, pady=8, relief="flat", state="normal")
        txt.pack(fill="both", expand=True)
        vsb.config(command=txt.yview)

        # Configure tags for highlighting
        txt.tag_config("heading",  foreground="#f0c040", font=("Consolas", 10, "bold"))
        txt.tag_config("syntax",   foreground="#88ccff", font=("Consolas", 10))
        txt.tag_config("comment",  foreground="#888888", font=("Consolas", 10, "italic"))
        txt.tag_config("example",  foreground="#aaffaa", font=("Consolas", 10))

        for line in HELP_TEXT.split("\n"):
            if line.startswith("━"):
                txt.insert("end", line + "\n", "heading")
            elif line.strip().startswith("→"):
                txt.insert("end", line + "\n", "example")
            elif line.strip().startswith("#") or "Beispiel" in line:
                txt.insert("end", line + "\n", "comment")
            elif any(op in line for op in ["{", "[if", "[elif", "[else", "OPT", "Draw", "Discard"]):
                txt.insert("end", line + "\n", "syntax")
            else:
                txt.insert("end", line + "\n")

        txt.config(state="disabled")

        tk.Button(self, text="Schließen", command=self.destroy,
                  bg="#333", fg="white").pack(pady=6)
