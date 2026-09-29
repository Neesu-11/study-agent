"""Small Tkinter building blocks."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from study_tutor.ui.theme import CARD, INK, LINE, MUTED, TEAL


class ScrolledText(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        height: int = 8,
        font: tuple[str, int] | tuple[str, int, str] = ("Segoe UI", 10),
        readonly: bool = False,
    ):
        super().__init__(master)
        self._readonly = readonly
        self.text = tk.Text(
            self,
            height=height,
            wrap=tk.WORD,
            font=font,
            undo=not readonly,
            padx=10,
            pady=8,
            background=CARD,
            foreground=INK,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=LINE,
            highlightcolor=TEAL,
            insertbackground=INK,
        )
        scroll = ttk.Scrollbar(self, command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        if readonly:
            self.text.configure(state=tk.DISABLED)

    def get_text(self) -> str:
        return self.text.get("1.0", "end-1c")

    def set_text(self, value: str) -> None:
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", value)
        if self._readonly:
            self.text.configure(state=tk.DISABLED)

    def clear(self) -> None:
        self.set_text("")


class Transcript(ScrolledText):
    def __init__(self, master: tk.Misc):
        super().__init__(master, height=16, readonly=True)
        text = self.text
        text.configure(state=tk.NORMAL, padx=16, pady=12, spacing1=2)
        text.tag_configure("hint", foreground=MUTED, font=("Segoe UI", 11), spacing1=12, spacing3=8)
        text.tag_configure("meta_user", foreground=TEAL, font=("Segoe UI", 8, "bold"), lmargin1=96, spacing1=18)
        text.tag_configure(
            "user",
            foreground=INK,
            font=("Segoe UI", 11),
            lmargin1=96,
            lmargin2=96,
            rmargin=12,
            spacing3=2,
        )
        text.tag_configure("meta_tutor", foreground=MUTED, font=("Segoe UI", 8, "bold"), lmargin1=2, spacing1=18)
        text.tag_configure(
            "tutor",
            foreground=INK,
            font=("Segoe UI", 11),
            lmargin1=2,
            lmargin2=2,
            rmargin=64,
            spacing3=2,
        )
        text.tag_configure("heading", foreground=TEAL, font=("Segoe UI", 12, "bold"), spacing1=8, spacing3=2)
        text.tag_configure(
            "code",
            font=("Consolas", 10),
            background="#efeae2",
            foreground=INK,
            spacing1=6,
            spacing3=6,
        )
        text.tag_raise("heading")
        text.tag_raise("code")
        text.configure(state=tk.DISABLED)

    def show_hint(self, content: str) -> None:
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.insert("1.0", content, "hint")
        self.text.configure(state=tk.DISABLED)

    def append(self, role: str, content: str) -> None:
        self.text.configure(state=tk.NORMAL)
        if "hint" in self.text.tag_names("1.0"):
            self.text.delete("1.0", tk.END)
        user = role == "user"
        label = "You" if user else "Tutor"
        base = "user" if user else "tutor"
        meta = "meta_user" if user else "meta_tutor"
        if self.text.index("end-1c") != "1.0":
            self.text.insert(tk.END, "\n")
        self.text.insert(tk.END, label + "\n", meta)
        _insert_formatted(self.text, content, base)
        self.text.configure(state=tk.DISABLED)
        self.text.see(tk.END)


def _insert_formatted(widget: tk.Text, content: str, base_tag: str) -> None:
    parts = content.split("```")
    for index, part in enumerate(parts):
        if index % 2 == 1:
            code = part
            if "\n" in code:
                first, rest = code.split("\n", 1)
                if first.strip() and " " not in first.strip() and len(first.strip()) < 20:
                    code = rest
            widget.insert(tk.END, code.strip("\n") + "\n", (base_tag, "code"))
            continue
        lines = part.split("\n")
        for line_index, line in enumerate(lines):
            heading = line.startswith("# ")
            shown = line[2:] if heading else line
            suffix = "\n" if line_index < len(lines) - 1 or index < len(parts) - 1 else ""
            if not shown and not suffix:
                continue
            tags: tuple[str, ...] = (base_tag, "heading") if heading else (base_tag,)
            widget.insert(tk.END, shown + suffix, tags)
