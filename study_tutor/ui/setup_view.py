"""First-launch API key screen."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from study_tutor.config import APP_NAME, DEFAULT_MODEL
from study_tutor.credentials import get_api_key, set_api_key
from study_tutor.errors import TutorError
from study_tutor.gemini_client import GeminiClient
class SetupView(ttk.Frame):
    def __init__(self, master: tk.Misc, app):
        super().__init__(master, padding=28)
        self.app = app
        self.replacing = False
        ttk.Label(self, text=APP_NAME, style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            self,
            text=(
                "Enter a Gemini API key to start. It is checked with a short request, "
                "then stored in Windows Credential Manager. Study replies need an internet connection."
            ),
            wraplength=640,
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(8, 18))
        form = ttk.Frame(self)
        form.pack(anchor="w", fill=tk.X)
        ttk.Label(form, text="Gemini API key").grid(row=0, column=0, sticky="w")
        self.key_var = tk.StringVar()
        self.entry = ttk.Entry(form, textvariable=self.key_var, width=56, show="*")
        self.entry.grid(row=1, column=0, sticky="w", pady=(0, 8))
        self.reveal = tk.BooleanVar(value=False)
        ttk.Checkbutton(form, text="Show key", variable=self.reveal, command=self._toggle).grid(row=2, column=0, sticky="w")
        ttk.Label(form, text="Model").grid(row=3, column=0, sticky="w", pady=(12, 0))
        self.model_var = tk.StringVar(value=DEFAULT_MODEL)
        ttk.Entry(form, textvariable=self.model_var, width=40).grid(row=4, column=0, sticky="w")
        self.notice = ttk.Label(self, text="", wraplength=640)
        self.notice.pack(anchor="w", pady=(16, 8))
        buttons = ttk.Frame(self)
        buttons.pack(anchor="w")
        self.save_button = ttk.Button(buttons, text="Check and save", style="Accent.TButton", command=self._save)
        self.save_button.pack(side=tk.LEFT)
        self.back_button = ttk.Button(buttons, text="Back", command=lambda: self.app.show("home"))
        self.back_button.pack(side=tk.LEFT, padx=8)

    def on_show(self, replacing: bool = False, **_kwargs) -> None:
        self.replacing = replacing
        self.key_var.set("")
        self.model_var.set(self.app.db.get_setting("gemini_model", DEFAULT_MODEL))
        self.notice.configure(text="")
        if replacing or get_api_key():
            self.back_button.pack(side=tk.LEFT, padx=8)
        else:
            self.back_button.pack_forget()
        self.entry.focus_set()

    def set_busy(self, busy: bool) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        self.save_button.configure(state=state)

    def _toggle(self) -> None:
        self.entry.configure(show="" if self.reveal.get() else "*")

    def _save(self) -> None:
        if self.app.busy:
            return
        key = self.key_var.get().strip()
        model = self.model_var.get().strip() or DEFAULT_MODEL
        try:
            if len(key) < 20:
                raise TutorError("Paste the full API key from Google AI Studio.")
        except TutorError as exc:
            self.notice.configure(text=str(exc))
            return

        def work() -> str:
            return GeminiClient(key, model).validate()

        def fail(exc: Exception) -> None:
            message = str(exc)
            self.notice.configure(text=message)
            self.app.set_status(message)

        def ok(used_model: str) -> None:
            try:
                set_api_key(key)
            except TutorError as exc:
                self.notice.configure(text=str(exc))
                return
            self.app.db.set_setting("gemini_model", used_model)
            self.key_var.set("")
            note = ""
            if used_model != model:
                note = f" Saved model {used_model} because {model} did not answer."
            self.app.set_status(f"API key saved.{note}")
            if self.app.db.list_subjects():
                self.app.show("home")
            else:
                self.app.show("import")

        self.notice.configure(text="Checking the key with Gemini…")
        self.app.run_async(work, ok, on_err=fail, status="Checking the Gemini API key…")
