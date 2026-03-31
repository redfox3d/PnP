"""
utils.py – Application-wide utilities.

enable_mousewheel_scroll(root):
    Binds a single <MouseWheel> handler to the root window.
    When the user scrolls, it walks up the widget hierarchy from
    the widget currently under the mouse pointer and scrolls the
    first Canvas or Text widget it finds.
    Works on Windows (<MouseWheel>) and Linux (<Button-4/5>).
"""

import tkinter as tk


def _scroll_target(widget):
    """Walk up widget hierarchy; return first scrollable Canvas or Text."""
    w = widget
    seen = set()
    while w is not None:
        try:
            wid = str(w)
            if wid in seen:          # Endlosschleife verhindern (Root hat sich selbst als Parent)
                break
            seen.add(wid)
            cls = w.winfo_class()
        except Exception:
            break
        if cls in ("Canvas", "Text"):
            return w
        parent_name = w.winfo_parent()
        if not parent_name:          # Root hat keinen Parent
            break
        try:
            w = w.nametowidget(parent_name)
        except Exception:
            break
    return None


def _on_mousewheel(event):
    """Called for <MouseWheel> (Windows/macOS) events on root."""
    try:
        target = event.widget.winfo_containing(event.x_root, event.y_root)
    except Exception:
        return
    canvas = _scroll_target(target)
    if canvas is None:
        return
    # Windows: event.delta is ±120 multiples; Linux uses Button-4/5
    delta = int(-event.delta / 120)
    canvas.yview_scroll(delta, "units")


def _on_mousewheel_linux(event):
    """Called for <Button-4> / <Button-5> (Linux scroll) on root."""
    try:
        target = event.widget.winfo_containing(event.x_root, event.y_root)
    except Exception:
        return
    canvas = _scroll_target(target)
    if canvas is None:
        return
    direction = -1 if event.num == 4 else 1
    canvas.yview_scroll(direction, "units")


def enable_mousewheel_scroll(root: tk.Tk):
    """
    Call once after creating the root Tk window.
    Attaches hover-based mousewheel scrolling to every Canvas/Text
    in the entire application without modifying individual widgets.
    """
    root.bind_all("<MouseWheel>",  _on_mousewheel,        add="+")
    root.bind_all("<Button-4>",    _on_mousewheel_linux,  add="+")
    root.bind_all("<Button-5>",    _on_mousewheel_linux,  add="+")
