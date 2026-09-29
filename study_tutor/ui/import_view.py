"""Paste or import a syllabus before the outline is built."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, ttk

from study_tutor.errors import TutorError
from study_tutor.schemas import KIND_LABELS
from study_tutor.syllabus import SAMPLE_SYLLABUS, parse_syllabus_locally, read_document
from study_tutor.ui.dialogs import kind_value
from study_tutor.ui.widgets import ScrolledText

_TRACKS = ("Auto",) + tuple(KIND_LABELS.values())


class ImportView(ttk.Frame):
    def __init__(self, master: tk.Misc, app):
        super().__init__(master, padding=24)
        self.app = app
        ttk.Label(self, text="Import a syllabus", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            self,
            text=(
                "Paste a syllabus, or open a text-based PDF or DOCX. "
                "Gemini turns it into an outline you can edit. Scanned PDFs are not read in this version."
            ),
            style="Muted.TLabel",
            wraplength=760,
        ).pack(anchor="w", pady=(6, 12))
        form = ttk.Frame(self)
        form.pack(fill=tk.X)
        ttk.Label(form, text="Subject name (optional)").grid(row=0, column=0, sticky="w")
        ttk.Label(form, text="Track").grid(row=0, column=1, sticky="w", padx=(16, 0))
        self.name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.name_var, width=42).grid(row=1, column=0, sticky="w", pady=(0, 8))
        self.track_var = tk.StringVar(value="Auto")
        ttk.Combobox(form, textvariable=self.track_var, values=_TRACKS, state="readonly", width=22).grid(
            row=1, column=1, sticky="w", padx=(16, 0)
        )
        self.body = ScrolledText(self, height=18)
        self.body.pack(fill=tk.BOTH, expand=True, pady=(4, 8))
        self.file_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.file_var, style="Muted.TLabel").pack(anchor="w")
        buttons = ttk.Frame(self)
        buttons.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(buttons, text="Open file", command=self._open_file).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Sample syllabus", command=self._sample).pack(side=tk.LEFT, padx=8)
        ttk.Button(buttons, text="Back", command=lambda: self.app.show("home")).pack(side=tk.LEFT)
        self.extract_button = ttk.Button(
            buttons, text="Build outline", style="Accent.TButton", command=self._extract
        )
        self.extract_button.pack(side=tk.RIGHT)

    def on_show(self, **_kwargs) -> None:
        if not self.body.get_text().strip():
            self.file_var.set("")

    def set_busy(self, busy: bool) -> None:
        self.extract_button.configure(state=tk.DISABLED if busy else tk.NORMAL)

    def _sample(self) -> None:
        self.body.set_text(SAMPLE_SYLLABUS)
        self.file_var.set("Sample business analytics syllabus")
        if not self.name_var.get().strip():
            self.name_var.set("Business Analytics")

    def _open_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open a syllabus",
            filetypes=[
                ("Syllabus files", "*.pdf *.docx *.txt *.md"),
                ("PDF", "*.pdf"),
                ("Word", "*.docx"),
                ("Text", "*.txt *.md"),
            ],
        )
        if not path:
            return
        try:
            text = read_document(path)
        except TutorError as exc:
            from tkinter import messagebox

            messagebox.showerror("MBA Study Tutor", str(exc))
            return
        self.body.set_text(text)
        self.file_var.set(path)

    def _extract(self) -> None:
        if self.app.busy:
            return
        if not self.app.require_key():
            return
        text = self.body.get_text().strip()
        if len(text) < 40:
            from tkinter import messagebox

            messagebox.showwarning("MBA Study Tutor", "Paste a syllabus or open a file first.")
            return
        preferred_name = self.name_var.get().strip()
        track = self.track_var.get()

        def work():
            warning = ""
            try:
                draft = self.app.client().extract_syllabus(text, preferred_name)
            except TutorError as exc:
                draft = parse_syllabus_locally(text, preferred_name)
                warning = (
                    f"{exc} A local outline is ready instead. Edit it before you create the study path."
                )
            if preferred_name:
                draft.subject_name = preferred_name
            if track != "Auto":
                draft.kind = kind_value(track)
            return draft, warning

        def ok(result) -> None:
            draft, warning = result
            self.app.session["draft"] = draft
            self.app.session["syllabus_text"] = text
            self.app.session["outline_warning"] = warning
            self.app.show("outline")

        self.app.run_async(work, ok, status="Building the study outline…")
