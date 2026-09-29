"""Modal editors for topics, notes, and settings."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from study_tutor.config import APP_NAME, DEFAULT_MODEL
from study_tutor.errors import TutorError
from study_tutor.schemas import FOCUS_LABELS, KIND_LABELS
from study_tutor.syllabus import read_document
from study_tutor.ui.theme import PAPER
from study_tutor.ui.widgets import ScrolledText


def kind_label(kind: str) -> str:
    return KIND_LABELS.get(kind, KIND_LABELS["general"])


def kind_value(label: str) -> str:
    for key, value in KIND_LABELS.items():
        if value == label:
            return key
    return "general"


def focus_value(label: str) -> str:
    for key, value in FOCUS_LABELS.items():
        if value == label:
            return key
    return "concept"


class TopicEditor(tk.Toplevel):
    def __init__(self, master: tk.Misc, *, title: str, objective: str = "", focus: str = "concept", unit: bool = False):
        super().__init__(master)
        self.result: dict[str, str] | None = None
        self.title("Edit unit" if unit else "Edit topic")
        self.configure(background=PAPER)
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Title").grid(row=0, column=0, sticky="w")
        self.title_var = tk.StringVar(value=title)
        ttk.Entry(frame, textvariable=self.title_var, width=52).grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.objective_var = tk.StringVar(value=objective)
        self.focus_var = tk.StringVar(value=FOCUS_LABELS.get(focus, "Concept"))
        if not unit:
            ttk.Label(frame, text="Objective").grid(row=2, column=0, sticky="w")
            ttk.Entry(frame, textvariable=self.objective_var, width=52).grid(row=3, column=0, sticky="ew", pady=(0, 8))
            ttk.Label(frame, text="Lesson style").grid(row=4, column=0, sticky="w")
            ttk.Combobox(
                frame,
                textvariable=self.focus_var,
                values=list(FOCUS_LABELS.values()),
                state="readonly",
                width=24,
            ).grid(row=5, column=0, sticky="w", pady=(0, 8))
        buttons = ttk.Frame(frame)
        buttons.grid(row=6, column=0, sticky="e")
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="Save", style="Accent.TButton", command=self._save).pack(side=tk.RIGHT, padx=(0, 8))
        self.bind("<Escape>", lambda _event: self.destroy())
        self.bind("<Return>", lambda _event: self._save())
        self.grab_set()
        self.title_var.trace_add("write", lambda *_args: None)
        self.after(50, self._focus)

    def _focus(self) -> None:
        for child in self.winfo_children():
            for entry in child.winfo_children():
                if isinstance(entry, ttk.Entry):
                    entry.focus_set()
                    return

    def _save(self) -> None:
        title = self.title_var.get().strip()
        if not title:
            messagebox.showwarning(APP_NAME, "Add a title.", parent=self)
            return
        self.result = {
            "title": title,
            "objective": self.objective_var.get().strip(),
            "focus": focus_value(self.focus_var.get()),
        }
        self.destroy()


class MaterialsDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, app, subject_id: int):
        super().__init__(master)
        self.app = app
        self.subject_id = subject_id
        self.title("Notes and textbooks")
        self.configure(background=PAPER)
        self.geometry("640x460")
        self.transient(master.winfo_toplevel())
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            frame,
            text="These stay on this computer. The tutor uses short excerpts when they match the topic.",
            style="Muted.TLabel",
            wraplength=580,
        ).pack(anchor="w", pady=(0, 8))
        self.list = tk.Listbox(frame, height=12, activestyle="dotbox", font=("Segoe UI", 10))
        self.list.pack(fill=tk.BOTH, expand=True)
        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(buttons, text="Add note", command=self._add_note).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Import file", command=self._import_file).pack(side=tk.LEFT, padx=8)
        ttk.Button(buttons, text="Remove", command=self._remove).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Close", command=self.destroy).pack(side=tk.RIGHT)
        self._ids: list[int] = []
        self._reload()
        self.grab_set()

    def _reload(self) -> None:
        self.list.delete(0, tk.END)
        self._ids = []
        for material in self.app.db.list_materials(self.subject_id):
            kind = "Note" if material.kind == "note" else "Textbook"
            self.list.insert(tk.END, f"{kind}: {material.title}")
            self._ids.append(material.id)

    def _add_note(self) -> None:
        dialog = NoteEditor(self)
        self.wait_window(dialog)
        if not dialog.result:
            return
        title, content = dialog.result
        self.app.db.add_material(self.subject_id, title, "note", content)
        self._reload()

    def _import_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Import notes or a textbook",
            filetypes=[
                ("Documents", "*.pdf *.docx *.txt *.md"),
                ("PDF", "*.pdf"),
                ("Word", "*.docx"),
                ("Text", "*.txt *.md"),
            ],
        )
        if not path:
            return
        try:
            content = read_document(path)
        except TutorError as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self)
            return
        title = path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
        self.app.db.add_material(self.subject_id, title, "textbook", content)
        self._reload()

    def _remove(self) -> None:
        selection = self.list.curselection()
        if not selection:
            return
        material_id = self._ids[selection[0]]
        self.app.db.delete_material(material_id)
        self._reload()


class NoteEditor(tk.Toplevel):
    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self.result: tuple[str, str] | None = None
        self.title("Add a note")
        self.configure(background=PAPER)
        self.geometry("560x420")
        self.transient(master.winfo_toplevel())
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Title").pack(anchor="w")
        self.title_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.title_var).pack(fill=tk.X, pady=(0, 8))
        ttk.Label(frame, text="Note").pack(anchor="w")
        self.body = ScrolledText(frame, height=12)
        self.body.pack(fill=tk.BOTH, expand=True)
        buttons = ttk.Frame(frame)
        buttons.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(buttons, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(buttons, text="Save", style="Accent.TButton", command=self._save).pack(side=tk.RIGHT, padx=(0, 8))
        self.grab_set()

    def _save(self) -> None:
        title = self.title_var.get().strip()
        content = self.body.get_text().strip()
        if not title or not content:
            messagebox.showwarning(APP_NAME, "Add a title and the note text.", parent=self)
            return
        self.result = (title, content)
        self.destroy()


class SettingsDialog(tk.Toplevel):
    def __init__(self, master: tk.Misc, app):
        super().__init__(master)
        self.app = app
        self.title("Settings")
        self.configure(background=PAPER)
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text="Gemini model").grid(row=0, column=0, sticky="w")
        self.model_var = tk.StringVar(value=app.db.get_setting("gemini_model", DEFAULT_MODEL))
        ttk.Entry(frame, textvariable=self.model_var, width=42).grid(row=1, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(frame, text="Python for coding exercises (optional)").grid(row=2, column=0, sticky="w")
        self.python_var = tk.StringVar(value=app.db.get_setting("python_path", ""))
        ttk.Entry(frame, textvariable=self.python_var, width=42).grid(row=3, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(
            frame,
            text="The packaged app uses this interpreter only when you press Run. Tutoring itself does not need a local Python.",
            style="Muted.TLabel",
            wraplength=420,
        ).grid(row=4, column=0, sticky="w", pady=(0, 12))
        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, sticky="ew")
        ttk.Button(buttons, text="Replace API key", command=self._replace_key).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Remove API key", command=self._remove_key).pack(side=tk.LEFT, padx=8)
        ttk.Button(buttons, text="Save", style="Accent.TButton", command=self._save).pack(side=tk.RIGHT)
        self.grab_set()

    def _save(self) -> None:
        model = self.model_var.get().strip() or DEFAULT_MODEL
        self.app.db.set_setting("gemini_model", model)
        self.app.db.set_setting("python_path", self.python_var.get().strip())
        self.destroy()

    def _replace_key(self) -> None:
        self.destroy()
        self.app.show("setup", replacing=True)

    def _remove_key(self) -> None:
        if not messagebox.askyesno(APP_NAME, "Remove the saved Gemini API key from Windows Credential Manager?", parent=self):
            return
        from study_tutor.credentials import clear_api_key

        clear_api_key()
        self.destroy()
        self.app.show("setup", replacing=False)
