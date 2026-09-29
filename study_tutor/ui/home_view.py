"""Subject list and progress summary."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from study_tutor.config import APP_NAME
from study_tutor.ui.dialogs import kind_label


class HomeView(ttk.Frame):
    def __init__(self, master: tk.Misc, app):
        super().__init__(master, padding=24)
        self.app = app
        header = ttk.Frame(self)
        header.pack(fill=tk.X)
        ttk.Label(header, text="Your subjects", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Button(header, text="New subject", style="Accent.TButton", command=self._new).pack(side=tk.RIGHT)
        ttk.Label(
            self,
            text="Progress stays in a local database on this PC.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(6, 12))
        columns = ("name", "track", "topics", "mastery", "weak")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("name", text="Subject")
        self.tree.heading("track", text="Track")
        self.tree.heading("topics", text="Topics")
        self.tree.heading("mastery", text="Mastery")
        self.tree.heading("weak", text="To revise")
        self.tree.column("name", width=280, anchor="w")
        self.tree.column("track", width=140, anchor="w")
        self.tree.column("topics", width=80, anchor="center")
        self.tree.column("mastery", width=100, anchor="center")
        self.tree.column("weak", width=100, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", lambda _event: self._open())
        buttons = ttk.Frame(self)
        buttons.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(buttons, text="Continue", style="Accent.TButton", command=self._open).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Delete", command=self._delete).pack(side=tk.LEFT, padx=8)
        self.empty = ttk.Label(self, text="", style="Muted.TLabel")
        self.empty.pack(anchor="w", pady=(8, 0))

    def on_show(self, **_kwargs) -> None:
        self.tree.delete(*self.tree.get_children())
        subjects = self.app.db.list_subjects()
        for subject in subjects:
            self.tree.insert(
                "",
                tk.END,
                iid=str(subject.id),
                values=(
                    subject.name,
                    kind_label(subject.kind),
                    subject.topic_count,
                    f"{subject.avg_mastery:.0f}",
                    subject.weak_count,
                ),
            )
        if subjects:
            self.empty.configure(text="")
            first = self.tree.get_children()
            if first:
                self.tree.selection_set(first[0])
        else:
            self.empty.configure(text="Import a syllabus to build your first study path.")

    def _selected_id(self) -> int | None:
        selected = self.tree.selection()
        if not selected:
            return None
        return int(selected[0])

    def _new(self) -> None:
        if not self.app.require_key():
            return
        self.app.show("import")

    def _open(self) -> None:
        subject_id = self._selected_id()
        if subject_id is None:
            messagebox.showinfo(APP_NAME, "Create a subject from a syllabus first.")
            return
        self.app.show("study", subject_id=subject_id)

    def _delete(self) -> None:
        subject_id = self._selected_id()
        if subject_id is None:
            return
        subject = self.app.db.get_subject(subject_id)
        name = subject.name if subject else "this subject"
        if not messagebox.askyesno(APP_NAME, f"Delete {name} and its saved progress?"):
            return
        self.app.db.delete_subject(subject_id)
        self.on_show()
