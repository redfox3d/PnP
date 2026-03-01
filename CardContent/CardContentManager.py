import json
import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import re

COMMANDS_FILE = "manager/effect_commands.json"
COLUMNS_FILE = "manager/column_config.json"
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

class ContentManager:

    def __init__(self, root):
        self.root = root
        self.root.title("Card Content Manager")
        self.root.geometry("1000x600")

        self.data = {}
        self.load_all()

        # Load the Text Commands
        self.load_commands()

        # Determines which columns are shown
        self.load_column_config()

        self.update_command_registry()

        self.create_table()

        self.sort_history = []  # Track last 5 sorts
        self.sort_directions = {}  # Track direction für jede Spalte

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

        # Repariere kaputte Elemente
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
            self.column_config = {"visible_columns": []}

    def save_column_config(self):
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

        duration=1000

        self.root.after(duration, lambda: self._status_bar.destroy() if hasattr(self,
                                                                                "_status_bar") and self._status_bar else None)
        # Anstatt MessageBox -> grüne Bar
        self.show_status_bar("Alle Dateien und Befehle erfolgreich gespeichert!")

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
            textvariable=self.hidden_var
        )
        self.hidden_menu.pack(side="left", padx=10)
        self.hidden_menu.bind("<<ComboboxSelected>>", self.unhide_column)

        # ---------------- TABLE ----------------
        all_columns = self.get_all_columns()

        if not self.column_config["visible_columns"]:
            self.column_config["visible_columns"] = all_columns

        self.columns = [
            col for col in all_columns
            if col in self.column_config["visible_columns"]
        ]

        self.tree = ttk.Treeview(self.root, columns=self.columns, show="headings")

        self.tree.bind("<Button-1>", self.handle_header_click)
        self.tree.bind("<Button-3>", self.column_context_menu)

        for col in self.columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150)

        self.tree.pack(fill="both", expand=True)

        self.tree.bind("<Double-1>", self.open_detail_editor)

        self.apply_filters()



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
        column_name = self.columns[column_index]

        # Linksklick = Sortieren
        if event.num == 1:
            self.sort_directions[column_name] = not self.sort_directions.get(column_name, True)
            self.sort_history.insert(0, column_name)
            self.sort_history = list(dict.fromkeys(self.sort_history))[:5]
            self.apply_filters(sort_column=column_name)
            # Rechtsklick = Kontextmenü (Rename/Delete/Hide).num == 3:  # rechtsklick wird durch context menu gehandhabt, kein Rename hier
            pass

    def column_context_menu(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "heading":
            return

        column_id = self.tree.identify_column(event.x)
        column_index = int(column_id.replace("#", "")) - 1
        column_name = self.columns[column_index]

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Hide Column", command=lambda: self.hide_column(column_name))
        menu.add_command(label="Rename", command=lambda: self.rename_column(column_name))
        menu.add_command(label="Delete Column", command=lambda: self.delete_column(column_name))
        menu.post(event.x_root, event.y_root)

    def rename_column(self, old_name):
        new_name = tk.simpledialog.askstring("Rename Column", f"New name for '{old_name}':")
        if new_name and new_name != old_name:
            for items in self.data.values():
                for item in items:
                    if old_name in item:
                        item[new_name] = item.pop(old_name)
            if old_name in self.column_config["visible_columns"]:
                idx = self.column_config["visible_columns"].index(old_name)
                self.column_config["visible_columns"][idx] = new_name
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
                self.save_column_config()
            self.refresh_table()

    def hide_column(self, column_name):

        if column_name in self.column_config["visible_columns"]:
            self.column_config["visible_columns"].remove(column_name)

        self.save_column_config()
        self.refresh_table()

    def refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        self.columns = [col for col in self.get_all_columns() if col in self.column_config["visible_columns"]]
        self.populate_table()
        self.update_hidden_dropdown()

    def update_command_registry(self):

        found_commands = {}

        # Alle Effect Texte scannen
        for type_name, items in self.data.items():
            for item in items:
                text = item.get("effect_text", "")
                matches = extract_commands_from_text(text)

                for command_name, arg in matches:
                    found_commands.setdefault(command_name, 0)
                    found_commands[command_name] += 1

        # Registry vorbereiten
        registry = {c["name"]: c for c in self.commands_data["commands"]}

        # Neue Commands hinzufügen oder updaten
        for cmd_name, count in found_commands.items():

            if cmd_name in registry:
                registry[cmd_name]["usage_count"] = count
                registry[cmd_name]["active"] = True
            else:
                # Neuer Eintrag
                new_entry = {
                    "name": cmd_name,
                    "template": f"\\{cmd_name}{{x}}",
                    "usage_count": count,
                    "active": True,
                    "element_weights": {
                        "Fire": 0.5,
                        "Metal": 0,
                        "Ice": 0.2,
                        "Nature": 0.1,
                        "Blood": 0.1,
                        "Meta": 0.2,
                        "Potion": 0.2,
                        "Skills": 0.2
                    }
                }
                self.commands_data["commands"].append(new_entry)

        # Nicht mehr verwendete flaggen
        for cmd in self.commands_data["commands"]:
            if cmd["name"] not in found_commands:
                cmd["usage_count"] = 0
                cmd["active"] = False

        self.save_commands()

    # -------------------------
    # DETAIL EDITOR
    # -------------------------
    def open_detail_editor(self, event):
        selected = self.tree.focus()
        if not selected:
            return

        values = self.tree.item(selected)["values"]
        type_name, item_id = values[0], values[1]

        item = next(i for i in self.data[type_name] if i["id"] == item_id)

        editor = tk.Toplevel(self.root)
        editor.title(f"Edit {item_id}")

        tk.Label(editor, text="ID").grid(row=0, column=0)
        id_entry = tk.Entry(editor)
        id_entry.insert(0, item.get("id", ""))
        id_entry.grid(row=0, column=1)

        tk.Label(editor, text="Effect Text").grid(row=1, column=0)
        text_entry = tk.Entry(editor, width=50)
        text_entry.insert(0, item.get("effect_text", ""))
        text_entry.grid(row=1, column=1)

        tk.Label(editor, text="Reminder Text").grid(row=2, column=0)
        reminder_entry = tk.Entry(editor, width=50)
        reminder_entry.insert(0, item.get("reminder_text", ""))
        reminder_entry.grid(row=2, column=1)

        tk.Label(editor, text="Rarity").grid(row=3, column=0)
        rarity_entry = tk.Entry(editor)
        rarity_entry.insert(0, item.get("rarity", 0))
        rarity_entry.grid(row=3, column=1)

        # ---------------- Complexity Fields ----------------
        tk.Label(editor, text="Complexity Multiplier").grid(row=4, column=0)
        cm_entry = tk.Entry(editor)
        cm_entry.insert(0, item.get("complexity_multiplier", 1))
        cm_entry.grid(row=4, column=1)

        tk.Label(editor, text="Complexity Additive").grid(row=5, column=0)
        ca_entry = tk.Entry(editor)
        ca_entry.insert(0, item.get("complexity_additive", 0))
        ca_entry.grid(row=5, column=1)

        # Buttons for sub-editors
        tk.Button(
            editor,
            text="Edit Element Weights",
            command=lambda: self.open_weights_editor(item)
        ).grid(row=6, column=0, columnspan=2, pady=5)

        tk.Button(
            editor,
            text="Edit Conditions",
            command=lambda: self.open_conditions_editor(item)
        ).grid(row=7, column=0, columnspan=2, pady=5)

        def save_changes():
            item["id"] = id_entry.get()
            item["effect_text"] = text_entry.get()
            item["reminder_text"] = reminder_entry.get()
            item["rarity"] = int(rarity_entry.get())
            try:
                item["complexity_multiplier"] = float(cm_entry.get())
            except:
                item["complexity_multiplier"] = 1
            try:
                item["complexity_additive"] = float(ca_entry.get())
            except:
                item["complexity_additive"] = 0

            self.refresh_table()
            editor.destroy()

        tk.Button(editor, text="Save", command=save_changes).grid(row=8, column=0, columnspan=2)

    # -------------------------
    # ELEMENT WEIGHTS EDITOR
    # -------------------------
    def open_weights_editor(self, item):

        weights = item.setdefault("element_weights", {})

        win = tk.Toplevel(self.root)
        win.title("Element Weights")

        entries = {}

        row = 0

        # Nur feste ELEMENTS verwenden
        for element in ELEMENTS:
            value = weights.get(element, 0)

            tk.Label(win, text=element).grid(row=row, column=0)

            entry = tk.Entry(win)
            entry.insert(0, value)
            entry.grid(row=row, column=1)

            entries[element] = entry
            row += 1

        def save_weights():
            for element in ELEMENTS:
                try:
                    weights[element] = float(entries[element].get())
                except:
                    weights[element] = 0

            win.destroy()

        tk.Button(win, text="Save", command=save_weights).grid(row=row, column=0, columnspan=2)

    def apply_filters(self, sort_column=None):

        self.tree.delete(*self.tree.get_children())

        selected_type = self.type_filter.get()
        min_rarity = self.rarity_filter.get()
        search_text = self.search_filter.get().lower()

        try:
            min_rarity = int(min_rarity) if min_rarity else None
        except:
            min_rarity = None

        all_rows = []

        # ---------------- DATA COLLECT ----------------
        for type_name, items in self.data.items():

            if selected_type != "All" and type_name != selected_type:
                continue

            for item in items:

                rarity = item.get("rarity", 0)

                if min_rarity is not None and rarity < min_rarity:
                    continue

                # Search in all visible columns
                if search_text:
                    if not any(search_text in str(item.get(col, "")).lower()
                               for col in self.columns if col != "type"):
                        continue

                row = []
                for col in self.columns:
                    if col == "type":
                        row.append(type_name)
                    else:
                        row.append(item.get(col, ""))

                all_rows.append(row)

        # ---------------- SMART SORT ----------------
        def smart_value(val):
            try:
                return float(val)
            except (ValueError, TypeError):
                return str(val).lower()

        # ---------------- SORTING ----------------
        if sort_column and sort_column in self.columns:
            reverse = not self.sort_directions.get(sort_column, True)
            col_index = self.columns.index(sort_column)

            all_rows.sort(
                key=lambda row: smart_value(row[col_index]),
                reverse=reverse
            )

        # ---------------- INSERT ----------------
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

        tk.Label(win, text="Min Mana").grid(row=0, column=0)
        min_entry = tk.Entry(win)
        min_entry.insert(0, conditions.get("min_mana", ""))
        min_entry.grid(row=0, column=1)

        tk.Label(win, text="Max Mana").grid(row=1, column=0)
        max_entry = tk.Entry(win)
        max_entry.insert(0, conditions.get("max_mana", ""))
        max_entry.grid(row=1, column=1)

        def save_conditions():
            conditions["min_mana"] = int(min_entry.get())
            conditions["max_mana"] = int(max_entry.get())
            win.destroy()

        tk.Button(win, text="Save", command=save_conditions).grid(row=2, column=0, columnspan=2)

    # -------------------------
    # CREATE NEW Content
    # -------------------------
    def open_create_editor(self):

        editor = tk.Toplevel(self.root)
        editor.title("Create New Content")

        # ---------------- TYPE ----------------
        tk.Label(editor, text="Type").grid(row=0, column=0)
        type_box = ttk.Combobox(editor, values=list(FILES.keys()))
        type_box.grid(row=0, column=1)

        # ---------------- ID ----------------
        tk.Label(editor, text="ID").grid(row=1, column=0)
        id_entry = tk.Entry(editor)
        id_entry.grid(row=1, column=1)

        # ---------------- EFFECT TEXT ----------------
        tk.Label(editor, text="Effect Text").grid(row=2, column=0)
        text_entry = tk.Entry(editor, width=40)
        text_entry.grid(row=2, column=1)

        # ---------------- RARITY ----------------
        tk.Label(editor, text="Rarity").grid(row=3, column=0)
        rarity_entry = tk.Entry(editor)
        rarity_entry.insert(0, "10")  # Standardwert 10
        rarity_entry.grid(row=3, column=1)

        # ---------------- SAVE ----------------
        def create_content():

            type_name = type_box.get()
            item_id = id_entry.get()
            effect_text = text_entry.get()

            try:
                rarity = int(rarity_entry.get())
            except:
                messagebox.showerror("Error", "Rarity must be a number.")
                return

            if not type_name or not item_id:
                messagebox.showerror("Error", "Type and ID are required.")
                return

            # ID prüfen
            for item in self.data[type_name]:
                if item["id"] == item_id:
                    messagebox.showerror("Error", "ID already exists.")
                    return

            # ---------------- Standard Element-Weights ----------------
            element_weights = {
                element: 7 for element in ELEMENTS
            }

            new_item = {
                "id": item_id,
                "effect_text": effect_text,
                "rarity": rarity,
                "element_weights": element_weights,
                "conditions": {},
                "complexity_multiplier": 1,
                "complexity_additive": 0
            }

            # Alle zusätzlichen Spalten aus visible_columns hinzufügen
            for col in self.column_config["visible_columns"]:
                if col not in new_item:
                    new_item[col] = ""

            self.data[type_name].append(new_item)

            self.apply_filters()
            self.save_all()
            editor.destroy()

        tk.Button(editor, text="Create", command=create_content) \
            .grid(row=4, column=0, columnspan=2, pady=10)

    def save_commands(self):
        with open(COMMANDS_FILE, "w") as f:
            json.dump(self.commands_data, f, indent=4)

    def show_status_bar(self, message, duration=2000):
        """Zeigt eine kurze grüne Status-Bar mit Text an."""
        # Prüfen, ob schon eine Bar existiert und sie entfernen
        if hasattr(self, "_status_bar") and self._status_bar:
            self._status_bar.destroy()

        self._status_bar = tk.Label(
            self.root,
            text=message,
            bg="green",
            fg="white",
            font=("Arial", 12),
            anchor="center"
        )
        self._status_bar.pack(side="top", fill="x")

        # Bar nach `duration` Millisekunden automatisch entfernen
        self.root.after(duration, lambda: self._status_bar.destroy() if hasattr(self, "_status_bar") and self._status_bar else None)

    def add_column(self):

        new_column = simpledialog.askstring(
            "New Column",
            "Column name:"
        )

        if not new_column:
            return

        # Neue Spalte zu allen existierenden Items hinzufügen
        for items in self.data.values():
            for item in items:
                item.setdefault(new_column, "")

        # Neue Spalte direkt sichtbar machen
        if new_column not in self.column_config["visible_columns"]:
            self.column_config["visible_columns"].append(new_column)
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

        if column_name not in self.column_config["visible_columns"]:
            self.column_config["visible_columns"].append(column_name)

        self.save_column_config()
        self.refresh_table()


# -------------------------
# RUN
# -------------------------
root = tk.Tk()
app = ContentManager(root)
root.mainloop()