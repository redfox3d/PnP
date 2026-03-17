import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import re

COMMANDS_FILE = "manager/effect_commands.json"
COLUMNS_FILE = "manager/column_config.json"
WINDOW_POS_FILE = "manager/window_positions.json"
FILES = {
    "Effect": "effects.json",
    "Trigger": "triggers.json",
    "Condition": "conditions.json",
    "Cost": "costs.json"
}

ELEMENTS = [
    "Fire",
    "Metal",
    "Ice",
    "Nature",
    "Blood",
    "Meta",
    "Potion",
    "Skills"
]


# -------------------------
# COMMAND PARSER
# -------------------------
def extract_commands_from_text(text):
    r"""
    Sucht nach Befehlen im Format:
    \Command{argument}
    Beispiel:
    \Draw{2}
    \Discard{4}
    """
    pattern = r"\\(\w+)((\{[^}]*\})+)"
    matches = re.findall(pattern, text)
    results = []
    for name, arg_block, _ in matches:
        args = re.findall(r"\{([^}]*)\}", arg_block)
        results.append((name, args))
    return results


# -------------------------
# WINDOW POSITION HELPER
# -------------------------
class WindowMemory:
    """Saves and restores window geometry (position + size)."""

    def __init__(self, filepath=WINDOW_POS_FILE):
        self.filepath = filepath
        self._data = {}
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

    def restore(self, window, key, default_geometry="600x400"):
        """Apply saved geometry or default, then bind saving on close/move."""
        geometry = self._data.get(key, default_geometry)
        window.geometry(geometry)

        def on_configure(event):
            # Only save when the window itself changes (not child widgets)
            if event.widget == window:
                self._data[key] = window.geometry()
                self._save()

        window.bind("<Configure>", on_configure)


# Global instance
_window_memory = WindowMemory()


class ContentManager:

    def __init__(self, root):
        self.root = root
        self.root.title("Card Content Manager")

        # Restore main window position/size
        _window_memory.restore(self.root, "main", "1000x600")

        self.data = {}
        self.load_all()

        self.load_commands()
        self.load_column_config()
        self.update_command_registry()

        self.sort_history = []
        self.sort_directions = {}
        self.active_sort_column = None  # currently sorted column

        # Drag state for column reordering
        self._drag_col = None
        self._drag_col_index = None

        self.create_table()

    # -------------------------
    # LOAD ALL JSONS
    # -------------------------
    def load_all(self):
        for key, filename in FILES.items():
            if os.path.exists(filename):
                with open(filename, "r") as f:
                    self.data[key] = json.load(f).get(key, [])
            else:
                self.data[key] = []

        for items in self.data.values():
            for item in items:
                weights = item.setdefault("element_weights", {})
                for element in ELEMENTS:
                    weights.setdefault(element, 0)

    # -------------------------
    # LOAD Command Json
    # -------------------------
    def load_commands(self):
        if os.path.exists(COMMANDS_FILE):
            with open(COMMANDS_FILE, "r") as f:
                self.commands_data = json.load(f)
        else:
            self.commands_data = {"commands": []}

    def load_column_config(self):
        if os.path.exists(COLUMNS_FILE):
            with open(COLUMNS_FILE, "r") as f:
                self.column_config = json.load(f)
        else:
            self.column_config = {"visible_columns": [], "column_order": [], "column_widths": {}}

        # Ensure keys exist
        self.column_config.setdefault("column_order", [])
        self.column_config.setdefault("column_widths", {})

    def save_column_config(self):
        os.makedirs(os.path.dirname(COLUMNS_FILE), exist_ok=True)
        with open(COLUMNS_FILE, "w") as f:
            json.dump(self.column_config, f, indent=4)

    # -------------------------
    # SAVE
    # -------------------------
    def save_all(self):
        for key, filename in FILES.items():
            with open(filename, "w") as f:
                json.dump({key: self.data[key]}, f, indent=4)

        self.update_command_registry()

        self.show_status_bar("Alle Dateien und Befehle erfolgreich gespeichert!")

    # -------------------------
    # AUTO COLUMN WIDTH
    # -------------------------
    def compute_column_widths(self):
        """
        Berechnet Spaltenbreiten:
        1. Mindestens so breit wie der Spaltenname
        2. Dann so breit wie der längste Inhalt
        3. Min 60px, Max 400px
        """
        font_char_px = 7   # approximate px per character
        pad = 20           # extra padding

        widths = {}
        for col in self.columns:
            # Start with header width
            min_w = len(col) * font_char_px + pad
            max_content = min_w

            for type_name, items in self.data.items():
                for item in items:
                    val = type_name if col == "type" else str(item.get(col, ""))
                    w = len(val) * font_char_px + pad
                    if w > max_content:
                        max_content = w

            # Clamp
            widths[col] = max(60, min(400, max_content))

        return widths

    # -------------------------
    # TABLE
    # -------------------------
    def create_table(self):

        # ---------------- FILTER FRAME ----------------
        filter_frame = tk.Frame(self.root)
        filter_frame.pack(fill="x", padx=5, pady=5)

        tk.Label(filter_frame, text="Type").pack(side="left")
        self.type_filter = ttk.Combobox(
            filter_frame,
            values=["All"] + list(FILES.keys()),
            width=10
        )
        self.type_filter.set("All")
        self.type_filter.pack(side="left", padx=5)

        tk.Label(filter_frame, text="Min Rarity").pack(side="left")
        self.rarity_filter = tk.Entry(filter_frame, width=5)
        self.rarity_filter.pack(side="left", padx=5)

        tk.Label(filter_frame, text="Search").pack(side="left")
        self.search_filter = tk.Entry(filter_frame, width=20)
        self.search_filter.pack(side="left", padx=5)

        self.sort_var = tk.BooleanVar()
        tk.Checkbutton(
            filter_frame,
            text="Sort ID (A-Z)",
            variable=self.sort_var
        ).pack(side="left", padx=5)

        tk.Button(
            filter_frame,
            text="Apply",
            command=self.apply_filters
        ).pack(side="left", padx=5)

        # ---------------- BUTTON FRAME ----------------
        button_frame = tk.Frame(self.root)
        button_frame.pack(fill="x", pady=5)

        tk.Button(
            button_frame,
            text="New Content",
            command=self.open_create_editor
        ).pack(side="left", padx=10)

        tk.Button(
            button_frame,
            text="Add Column",
            command=self.add_column
        ).pack(side="left", padx=10)

        tk.Button(
            button_frame,
            text="Save All",
            command=self.save_all
        ).pack(side="right", padx=10)

        self.hidden_var = tk.StringVar()
        self.hidden_menu = ttk.Combobox(
            button_frame,
            textvariable=self.hidden_var,
            width=15
        )
        self.hidden_menu.pack(side="left", padx=10)
        self.hidden_menu.bind("<<ComboboxSelected>>", self.unhide_column)

        tk.Label(button_frame, text="↑ Unhide column").pack(side="left")

        # ---------------- TABLE ----------------
        all_columns = self.get_all_columns()

        if not self.column_config["visible_columns"]:
            self.column_config["visible_columns"] = all_columns

        # Apply saved column order if available
        saved_order = self.column_config.get("column_order", [])
        if saved_order:
            # Use saved order, but include any new columns not yet in saved order
            ordered = [c for c in saved_order if c in self.column_config["visible_columns"]]
            for c in self.column_config["visible_columns"]:
                if c not in ordered:
                    ordered.append(c)
            self.columns = ordered
        else:
            self.columns = [
                col for col in all_columns
                if col in self.column_config["visible_columns"]
            ]

        self.tree = ttk.Treeview(self.root, columns=self.columns, show="headings")

        # Compute and apply column widths
        col_widths = self.compute_column_widths()
        saved_widths = self.column_config.get("column_widths", {})

        for col in self.columns:
            self.tree.heading(col, text=col)
            # Saved width takes priority, then auto-computed
            w = saved_widths.get(col, col_widths.get(col, 150))
            self.tree.column(col, width=w, minwidth=40)

        # Scrollbar
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        # Bindings
        self.tree.bind("<Button-1>", self.handle_header_click)
        self.tree.bind("<Button-3>", self.column_context_menu)
        self.tree.bind("<Double-1>", self.open_detail_editor)

        # Column drag & drop for reordering
        self.tree.bind("<ButtonPress-1>", self._col_drag_start, add="+")
        self.tree.bind("<B1-Motion>", self._col_drag_motion, add="+")
        self.tree.bind("<ButtonRelease-1>", self._col_drag_release, add="+")

        # Save column widths when user resizes
        self.tree.bind("<ButtonRelease-1>", self._save_col_widths, add="+")

        self.apply_filters()
        self.update_hidden_dropdown()

    # -------------------------
    # COLUMN DRAG & DROP
    # -------------------------
    def _col_drag_start(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "heading":
            self._drag_col = None
            return
        col_id = self.tree.identify_column(event.x)
        self._drag_col_index = int(col_id.replace("#", "")) - 1
        self._drag_col = self.columns[self._drag_col_index]
        self._drag_start_x = event.x

    def _col_drag_motion(self, event):
        if self._drag_col is None:
            return
        # Visual feedback: change cursor
        self.tree.config(cursor="fleur")

    def _col_drag_release(self, event):
        if self._drag_col is None:
            return
        self.tree.config(cursor="")

        region = self.tree.identify_region(event.x, event.y)
        if region != "heading":
            self._drag_col = None
            return

        col_id = self.tree.identify_column(event.x)
        target_index = int(col_id.replace("#", "")) - 1

        if target_index != self._drag_col_index and 0 <= target_index < len(self.columns):
            # Reorder
            col = self.columns.pop(self._drag_col_index)
            self.columns.insert(target_index, col)

            # Rebuild treeview columns
            self.tree.config(columns=self.columns)
            col_widths = self.compute_column_widths()
            saved_widths = self.column_config.get("column_widths", {})
            for c in self.columns:
                self.tree.heading(c, text=c)
                w = saved_widths.get(c, col_widths.get(c, 150))
                self.tree.column(c, width=w, minwidth=40)

            # Save order
            self.column_config["column_order"] = list(self.columns)
            self.save_column_config()

            # Repopulate
            self.apply_filters()
            self._update_sort_headings()

        self._drag_col = None

    def _save_col_widths(self, event):
        """Save current column widths after user resize."""
        if not hasattr(self, "tree"):
            return
        widths = {}
        for col in self.columns:
            try:
                widths[col] = self.tree.column(col, "width")
            except Exception:
                pass
        self.column_config["column_widths"] = widths
        self.save_column_config()

    def populate_table(self):
        for type_name, items in self.data.items():
            for item in items:
                row = []
                for col in self.columns:
                    if col == "type":
                        row.append(type_name)
                    else:
                        row.append(item.get(col, ""))
                self.tree.insert("", "end", values=row)

    def handle_header_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "heading":
            return

        column_id = self.tree.identify_column(event.x)
        column_index = int(column_id.replace("#", "")) - 1
        if column_index >= len(self.columns):
            return
        column_name = self.columns[column_index]

        if event.num == 1:
            self.sort_directions[column_name] = not self.sort_directions.get(column_name, True)
            self.sort_history.insert(0, column_name)
            self.sort_history = list(dict.fromkeys(self.sort_history))[:5]
            self.active_sort_column = column_name
            self.apply_filters(sort_column=column_name)
            self._update_sort_headings()

    def _update_sort_headings(self):
        """
        Aktualisiert alle Spalten-Headings:
        - Aktive Sortierspalte: ▲ oder ▼ Pfeil im Text
        - Globaler ttk-Style wird für "aktiv sortierte" Spalte auf dunkleres
          Grau gesetzt. Da ttk keinen echten per-column Header-BG unterstützt,
          lösen wir das Header-Darkening über map() – wenn das Heading
          "pressed" ist, zeigt es den dunkleren Ton. Als visuellen Marker
          verwenden wir stattdessen das compound-image und einen kleinen
          farbigen Balken als linkes Bild.

        In der Praxis: Pfeil + kleines farbiges Quadrat links als Markierung.
        """
        if not hasattr(self, "_sort_img"):
            # Kleines blaues Quadrat als visuellen Marker für aktive Spalte
            self._sort_img = tk.PhotoImage(width=6, height=14)
            self._sort_img.put("#5a7fbf", to=(0, 0, 6, 14))
            self._nosort_img = tk.PhotoImage(width=6, height=14)
            self._nosort_img.put("#c8c8c8", to=(0, 0, 6, 14))

        for col in self.columns:
            if col == self.active_sort_column:
                arrow = " ▲" if self.sort_directions.get(col, True) else " ▼"
                self.tree.heading(
                    col,
                    text=col + arrow,
                    image=self._sort_img,
                    compound="left"
                )
            else:
                self.tree.heading(
                    col,
                    text=col,
                    image=self._nosort_img,
                    compound="left"
                )

    def column_context_menu(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "heading":
            return

        column_id = self.tree.identify_column(event.x)
        column_index = int(column_id.replace("#", "")) - 1
        if column_index >= len(self.columns):
            return
        column_name = self.columns[column_index]

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Hide Column", command=lambda: self.hide_column(column_name))
        menu.add_command(label="Rename", command=lambda: self.rename_column(column_name))
        menu.add_command(label="Delete Column", command=lambda: self.delete_column(column_name))
        menu.post(event.x_root, event.y_root)

    def rename_column(self, old_name):
        new_name = simpledialog.askstring("Rename Column", f"New name for '{old_name}':")
        if new_name and new_name != old_name:
            for items in self.data.values():
                for item in items:
                    if old_name in item:
                        item[new_name] = item.pop(old_name)
            if old_name in self.column_config["visible_columns"]:
                idx = self.column_config["visible_columns"].index(old_name)
                self.column_config["visible_columns"][idx] = new_name
            if old_name in self.column_config.get("column_order", []):
                idx = self.column_config["column_order"].index(old_name)
                self.column_config["column_order"][idx] = new_name
            self.save_column_config()
            self.refresh_table()

    def delete_column(self, column_name):
        if messagebox.askyesno("Delete Column", f"Are you sure you want to delete '{column_name}'?"):
            for items in self.data.values():
                for item in items:
                    if column_name in item:
                        del item[column_name]
            if column_name in self.column_config["visible_columns"]:
                self.column_config["visible_columns"].remove(column_name)
            if column_name in self.column_config.get("column_order", []):
                self.column_config["column_order"].remove(column_name)
            self.save_column_config()
            self.refresh_table()

    def hide_column(self, column_name):
        if column_name in self.column_config["visible_columns"]:
            self.column_config["visible_columns"].remove(column_name)
        self.save_column_config()
        self.refresh_table()

    def refresh_table(self):
        self.tree.delete(*self.tree.get_children())

        all_cols = self.get_all_columns()
        saved_order = self.column_config.get("column_order", [])

        if saved_order:
            ordered = [c for c in saved_order if c in self.column_config["visible_columns"]]
            for c in self.column_config["visible_columns"]:
                if c not in ordered:
                    ordered.append(c)
            self.columns = ordered
        else:
            self.columns = [c for c in all_cols if c in self.column_config["visible_columns"]]

        self.tree.config(columns=self.columns)
        col_widths = self.compute_column_widths()
        saved_widths = self.column_config.get("column_widths", {})
        for col in self.columns:
            self.tree.heading(col, text=col)
            w = saved_widths.get(col, col_widths.get(col, 150))
            self.tree.column(col, width=w, minwidth=40)

        self.populate_table()
        self.update_hidden_dropdown()
        self._update_sort_headings()

    # -------------------------
    # COMMAND REGISTRY
    # -------------------------
    def update_command_registry(self):
        found_commands = {}

        for type_name, items in self.data.items():
            for item in items:
                text = item.get("effect_text", "")
                matches = extract_commands_from_text(text)
                for command_name, arg in matches:
                    found_commands.setdefault(command_name, 0)
                    found_commands[command_name] += 1

        registry = {c["name"]: c for c in self.commands_data["commands"]}

        for cmd_name, count in found_commands.items():
            if cmd_name in registry:
                registry[cmd_name]["usage_count"] = count
                registry[cmd_name]["active"] = True
            else:
                new_entry = {
                    "name": cmd_name,
                    "template": f"\\{cmd_name}{{x}}",
                    "usage_count": count,
                    "active": True,
                    "element_weights": {
                        "Fire": 0.5, "Metal": 0, "Ice": 0.2,
                        "Nature": 0.1, "Blood": 0.1, "Meta": 0.2,
                        "Potion": 0.2, "Skills": 0.2
                    }
                }
                self.commands_data["commands"].append(new_entry)

        for cmd in self.commands_data["commands"]:
            if cmd["name"] not in found_commands:
                cmd["usage_count"] = 0
                cmd["active"] = False

        self.save_commands()

    # -------------------------
    # DETAIL EDITOR
    # -------------------------
    def open_detail_editor(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            return

        selected = self.tree.focus()
        if not selected:
            return

        values = self.tree.item(selected)["values"]
        if not values or len(values) < 2:
            return

        type_name, item_id = values[0], values[1]

        try:
            item = next(i for i in self.data[type_name] if i["id"] == item_id)
        except StopIteration:
            return

        editor = tk.Toplevel(self.root)
        editor.title(f"Edit {item_id}")
        _window_memory.restore(editor, "detail_editor", "500x350")

        tk.Label(editor, text="ID").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        id_entry = tk.Entry(editor, width=40)
        id_entry.insert(0, item.get("id", ""))
        id_entry.grid(row=0, column=1, padx=8, pady=4)

        tk.Label(editor, text="Effect Text").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        text_entry = tk.Entry(editor, width=50)
        text_entry.insert(0, item.get("effect_text", ""))
        text_entry.grid(row=1, column=1, padx=8, pady=4)

        tk.Label(editor, text="Reminder Text").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        reminder_entry = tk.Entry(editor, width=50)
        reminder_entry.insert(0, item.get("reminder_text", ""))
        reminder_entry.grid(row=2, column=1, padx=8, pady=4)

        tk.Label(editor, text="Rarity").grid(row=3, column=0, sticky="w", padx=8, pady=4)
        rarity_entry = tk.Entry(editor)
        rarity_entry.insert(0, item.get("rarity", 0))
        rarity_entry.grid(row=3, column=1, padx=8, pady=4)

        tk.Label(editor, text="Complexity Multiplier").grid(row=4, column=0, sticky="w", padx=8, pady=4)
        cm_entry = tk.Entry(editor)
        cm_entry.insert(0, item.get("complexity_multiplier", 1))
        cm_entry.grid(row=4, column=1, padx=8, pady=4)

        tk.Label(editor, text="Complexity Additive").grid(row=5, column=0, sticky="w", padx=8, pady=4)
        ca_entry = tk.Entry(editor)
        ca_entry.insert(0, item.get("complexity_additive", 0))
        ca_entry.grid(row=5, column=1, padx=8, pady=4)

        btn_frame = tk.Frame(editor)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=8)

        tk.Button(
            btn_frame,
            text="Edit Element Weights",
            command=lambda: self.open_weights_editor(item)
        ).pack(side="left", padx=8)

        tk.Button(
            btn_frame,
            text="Edit Conditions",
            command=lambda: self.open_conditions_editor(item)
        ).pack(side="left", padx=8)

        def save_changes():
            item["id"] = id_entry.get()
            item["effect_text"] = text_entry.get()
            item["reminder_text"] = reminder_entry.get()
            try:
                item["rarity"] = int(rarity_entry.get())
            except ValueError:
                pass
            try:
                item["complexity_multiplier"] = float(cm_entry.get())
            except ValueError:
                item["complexity_multiplier"] = 1
            try:
                item["complexity_additive"] = float(ca_entry.get())
            except ValueError:
                item["complexity_additive"] = 0

            self.refresh_table()
            editor.destroy()

        tk.Button(editor, text="Save", command=save_changes).grid(row=7, column=0, columnspan=2, pady=8)

    # -------------------------
    # ELEMENT WEIGHTS EDITOR
    # -------------------------
    def open_weights_editor(self, item):
        weights = item.setdefault("element_weights", {})

        win = tk.Toplevel(self.root)
        win.title("Element Weights")
        _window_memory.restore(win, "weights_editor", "250x300")

        entries = {}
        for row_idx, element in enumerate(ELEMENTS):
            value = weights.get(element, 0)
            tk.Label(win, text=element).grid(row=row_idx, column=0, sticky="w", padx=8, pady=2)
            entry = tk.Entry(win, width=10)
            entry.insert(0, value)
            entry.grid(row=row_idx, column=1, padx=8, pady=2)
            entries[element] = entry

        def save_weights():
            for element in ELEMENTS:
                try:
                    weights[element] = float(entries[element].get())
                except ValueError:
                    weights[element] = 0
            win.destroy()

        tk.Button(win, text="Save", command=save_weights).grid(
            row=len(ELEMENTS), column=0, columnspan=2, pady=8
        )

    def apply_filters(self, sort_column=None):
        self.tree.delete(*self.tree.get_children())

        selected_type = self.type_filter.get()
        min_rarity = self.rarity_filter.get()
        search_text = self.search_filter.get().lower()

        try:
            min_rarity = int(min_rarity) if min_rarity else None
        except ValueError:
            min_rarity = None

        all_rows = []

        for type_name, items in self.data.items():
            if selected_type != "All" and type_name != selected_type:
                continue

            for item in items:
                rarity = item.get("rarity", 0)
                if min_rarity is not None and rarity < min_rarity:
                    continue

                if search_text:
                    if not any(
                        search_text in str(item.get(col, "")).lower()
                        for col in self.columns if col != "type"
                    ):
                        continue

                row = []
                for col in self.columns:
                    if col == "type":
                        row.append(type_name)
                    else:
                        row.append(item.get(col, ""))
                all_rows.append(row)

        def smart_value(val):
            try:
                return (0, float(val))
            except (ValueError, TypeError):
                return (1, str(val).lower())

        if sort_column and sort_column in self.columns:
            reverse = not self.sort_directions.get(sort_column, True)
            col_index = self.columns.index(sort_column)
            all_rows.sort(key=lambda r: smart_value(r[col_index]), reverse=reverse)

        for row in all_rows:
            self.tree.insert("", "end", values=row)

    def reset_filters(self):
        self.type_filter.set("All")
        self.rarity_filter.delete(0, tk.END)
        self.search_filter.delete(0, tk.END)
        self.sort_var.set(False)
        self.apply_filters()

    def get_all_columns(self):
        columns = ["type", "id", "rarity", "effect_text", "reminder_text"]
        for items in self.data.values():
            for item in items:
                for k in item.keys():
                    if k not in columns:
                        columns.append(k)
        return columns

    # -------------------------
    # CONDITIONS EDITOR
    # -------------------------
    def open_conditions_editor(self, item):
        conditions = item.setdefault("conditions", {})

        win = tk.Toplevel(self.root)
        win.title("Conditions")
        _window_memory.restore(win, "conditions_editor", "250x130")

        tk.Label(win, text="Min Mana").grid(row=0, column=0, padx=8, pady=4, sticky="w")
        min_entry = tk.Entry(win)
        min_entry.insert(0, conditions.get("min_mana", ""))
        min_entry.grid(row=0, column=1, padx=8, pady=4)

        tk.Label(win, text="Max Mana").grid(row=1, column=0, padx=8, pady=4, sticky="w")
        max_entry = tk.Entry(win)
        max_entry.insert(0, conditions.get("max_mana", ""))
        max_entry.grid(row=1, column=1, padx=8, pady=4)

        def save_conditions():
            try:
                conditions["min_mana"] = int(min_entry.get())
            except ValueError:
                conditions["min_mana"] = 0
            try:
                conditions["max_mana"] = int(max_entry.get())
            except ValueError:
                conditions["max_mana"] = 0
            win.destroy()

        tk.Button(win, text="Save", command=save_conditions).grid(row=2, column=0, columnspan=2, pady=8)

    # -------------------------
    # CREATE NEW Content  (new layout)
    # -------------------------
    def open_create_editor(self):
        editor = tk.Toplevel(self.root)
        editor.title("Create New Content")
        _window_memory.restore(editor, "create_editor", "520x320")

        editor.columnconfigure(0, weight=0)
        editor.columnconfigure(1, weight=1)
        editor.columnconfigure(2, weight=0)
        editor.columnconfigure(3, weight=0)

        # ---- ROW 0: ID (left) + Type dropdown (right) ----
        tk.Label(editor, text="ID", font=("Arial", 10, "bold")).grid(
            row=0, column=0, sticky="w", padx=(10, 4), pady=(12, 4)
        )
        id_entry = tk.Entry(editor, width=28)
        id_entry.grid(row=0, column=1, sticky="we", padx=(0, 10), pady=(12, 4))

        tk.Label(editor, text="Type", font=("Arial", 10, "bold")).grid(
            row=0, column=2, sticky="w", padx=(4, 4), pady=(12, 4)
        )
        type_box = ttk.Combobox(editor, values=list(FILES.keys()), width=14, state="readonly")
        type_box.grid(row=0, column=3, sticky="w", padx=(0, 10), pady=(12, 4))
        if FILES:
            type_box.current(0)

        # ---- ROW 1: Effect Text ----
        tk.Label(editor, text="Effect Text").grid(
            row=1, column=0, sticky="w", padx=(10, 4), pady=4
        )
        text_entry = tk.Entry(editor, width=50)
        text_entry.grid(row=1, column=1, columnspan=3, sticky="we", padx=(0, 10), pady=4)

        # ---- ROW 2: Reminder Text ----
        tk.Label(editor, text="Reminder Text").grid(
            row=2, column=0, sticky="w", padx=(10, 4), pady=4
        )
        reminder_entry = tk.Entry(editor, width=50)
        reminder_entry.grid(row=2, column=1, columnspan=3, sticky="we", padx=(0, 10), pady=4)

        # ---- ROW 3: Rarity ----
        tk.Label(editor, text="Rarity").grid(
            row=3, column=0, sticky="w", padx=(10, 4), pady=4
        )
        rarity_entry = tk.Entry(editor, width=10)
        rarity_entry.insert(0, "10")
        rarity_entry.grid(row=3, column=1, sticky="w", pady=4)

        # ---- ROW 4: Complexity ----
        tk.Label(editor, text="Complexity Multiplier").grid(
            row=4, column=0, sticky="w", padx=(10, 4), pady=4
        )
        cm_entry = tk.Entry(editor, width=10)
        cm_entry.insert(0, "1")
        cm_entry.grid(row=4, column=1, sticky="w", pady=4)

        tk.Label(editor, text="Additive").grid(
            row=4, column=2, sticky="w", padx=(4, 4), pady=4
        )
        ca_entry = tk.Entry(editor, width=8)
        ca_entry.insert(0, "0")
        ca_entry.grid(row=4, column=3, sticky="w", padx=(0, 10), pady=4)

        # ---- ROW 5: Create button ----
        def create_content():
            type_name = type_box.get()
            item_id = id_entry.get().strip()
            effect_text = text_entry.get()
            reminder_text = reminder_entry.get()

            if not type_name or not item_id:
                messagebox.showerror("Error", "Type and ID are required.")
                return

            try:
                rarity = int(rarity_entry.get())
            except ValueError:
                messagebox.showerror("Error", "Rarity must be a number.")
                return

            try:
                complexity_multiplier = float(cm_entry.get())
            except ValueError:
                complexity_multiplier = 1

            try:
                complexity_additive = float(ca_entry.get())
            except ValueError:
                complexity_additive = 0

            for item in self.data.get(type_name, []):
                if item["id"] == item_id:
                    messagebox.showerror("Error", "ID already exists.")
                    return

            element_weights = {element: 7 for element in ELEMENTS}

            new_item = {
                "id": item_id,
                "effect_text": effect_text,
                "reminder_text": reminder_text,
                "rarity": rarity,
                "element_weights": element_weights,
                "conditions": {},
                "complexity_multiplier": complexity_multiplier,
                "complexity_additive": complexity_additive
            }

            for col in self.column_config["visible_columns"]:
                if col not in new_item:
                    new_item[col] = ""

            self.data[type_name].append(new_item)
            self.apply_filters()
            self.save_all()
            editor.destroy()

        tk.Button(
            editor,
            text="Create",
            width=16,
            command=create_content
        ).grid(row=5, column=0, columnspan=4, pady=16)

    def save_commands(self):
        os.makedirs(os.path.dirname(COMMANDS_FILE), exist_ok=True)
        with open(COMMANDS_FILE, "w") as f:
            json.dump(self.commands_data, f, indent=4)

    def show_status_bar(self, message, duration=2000):
        if hasattr(self, "_status_bar") and self._status_bar:
            try:
                self._status_bar.destroy()
            except Exception:
                pass

        self._status_bar = tk.Label(
            self.root,
            text=message,
            bg="green",
            fg="white",
            font=("Arial", 12),
            anchor="center"
        )
        self._status_bar.pack(side="top", fill="x")

        self.root.after(
            duration,
            lambda: self._status_bar.destroy()
            if hasattr(self, "_status_bar") and self._status_bar
            else None
        )

    def add_column(self):
        new_column = simpledialog.askstring("New Column", "Column name:")
        if not new_column:
            return

        for items in self.data.values():
            for item in items:
                item.setdefault(new_column, "")

        if new_column not in self.column_config["visible_columns"]:
            self.column_config["visible_columns"].append(new_column)

        if new_column not in self.column_config.get("column_order", []):
            self.column_config.setdefault("column_order", []).append(new_column)

        self.save_column_config()
        self.refresh_table()
        self.save_all()

    def update_hidden_dropdown(self):
        all_columns = self.get_all_columns()
        hidden = [
            col for col in all_columns
            if col not in self.column_config["visible_columns"]
        ]
        self.hidden_menu["values"] = hidden

    def unhide_column(self, event):
        column_name = self.hidden_var.get()
        if not column_name:
            return

        if column_name not in self.column_config["visible_columns"]:
            self.column_config["visible_columns"].append(column_name)

        if column_name not in self.column_config.get("column_order", []):
            self.column_config.setdefault("column_order", []).append(column_name)

        self.save_column_config()
        self.refresh_table()
        self.hidden_var.set("")


# -------------------------
# RUN
# -------------------------
root = tk.Tk()
app = ContentManager(root)
root.mainloop()