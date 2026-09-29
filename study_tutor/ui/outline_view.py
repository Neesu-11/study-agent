"""Editable unit and topic list before the study path is saved."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from study_tutor.config import APP_NAME
from study_tutor.schemas import FOCUS_LABELS, KIND_LABELS, SyllabusDraft, TopicDraft, UnitDraft
from study_tutor.ui.dialogs import TopicEditor, kind_label, kind_value


class OutlineView(ttk.Frame):
    def __init__(self, master: tk.Misc, app):
        super().__init__(master, padding=20)
        self.app = app
        self.nodes: dict[str, dict] = {}
        self._counter = 0
        ttk.Label(self, text="Review the outline", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            self,
            text="This order becomes the study path. Rename, delete, or move anything that does not belong.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 8))
        self.warning = ttk.Label(self, text="", wraplength=860, foreground="#8c2f2f")
        self.warning.pack(anchor="w", pady=(0, 8))
        form = ttk.Frame(self)
        form.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(form, text="Subject").grid(row=0, column=0, sticky="w")
        ttk.Label(form, text="Track").grid(row=0, column=1, sticky="w", padx=(12, 0))
        self.name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.name_var, width=48).grid(row=1, column=0, sticky="w")
        self.kind_var = tk.StringVar()
        ttk.Combobox(
            form,
            textvariable=self.kind_var,
            values=list(KIND_LABELS.values()),
            state="readonly",
            width=22,
        ).grid(row=1, column=1, sticky="w", padx=(12, 0))
        columns = ("focus", "objective")
        self.tree = ttk.Treeview(self, columns=columns, show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Unit / topic")
        self.tree.heading("focus", text="Style")
        self.tree.heading("objective", text="Objective")
        self.tree.column("#0", width=320, anchor="w")
        self.tree.column("focus", width=110, anchor="w")
        self.tree.column("objective", width=420, anchor="w")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Double-1>", lambda _event: self._edit())
        actions = ttk.Frame(self)
        actions.pack(fill=tk.X, pady=(8, 0))
        for label, command in (
            ("Add unit", self._add_unit),
            ("Add topic", self._add_topic),
            ("Edit", self._edit),
            ("Delete", self._delete),
            ("Move up", lambda: self._move(-1)),
            ("Move down", lambda: self._move(1)),
        ):
            ttk.Button(actions, text=label, command=command).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(actions, text="Back", command=lambda: self.app.show("import")).pack(side=tk.RIGHT, padx=(6, 0))
        self.save_button = ttk.Button(
            actions, text="Create study path", style="Accent.TButton", command=self._save
        )
        self.save_button.pack(side=tk.RIGHT)

    def on_show(self, **_kwargs) -> None:
        draft = self.app.session.get("draft")
        if draft is None:
            self.app.show("import")
            return
        self.name_var.set(draft.subject_name)
        self.kind_var.set(kind_label(draft.kind))
        warning = self.app.session.get("outline_warning") or ""
        self.warning.configure(text=warning)
        self._load(draft)

    def _new_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}{self._counter}"

    def _load(self, draft: SyllabusDraft) -> None:
        self.tree.delete(*self.tree.get_children())
        self.nodes.clear()
        for unit in draft.units:
            self._insert_unit(unit)

    def _insert_unit(self, unit: UnitDraft, index: int | None = None) -> str:
        iid = self._new_id("u")
        kwargs = {"text": unit.title, "values": ("", f"{len(unit.topics)} topics"), "open": True}
        if index is None:
            self.tree.insert("", tk.END, iid, **kwargs)
        else:
            self.tree.insert("", index, iid, **kwargs)
        self.nodes[iid] = {"type": "unit", "title": unit.title}
        for topic in unit.topics:
            self._insert_topic(iid, topic)
        return iid

    def _insert_topic(self, unit_iid: str, topic: TopicDraft, index: int | None = None) -> str:
        iid = self._new_id("t")
        values = (FOCUS_LABELS.get(topic.focus, "Concept"), topic.objective)
        if index is None:
            self.tree.insert(unit_iid, tk.END, iid, text=topic.title, values=values)
        else:
            self.tree.insert(unit_iid, index, iid, text=topic.title, values=values)
        self.nodes[iid] = {"type": "topic", "draft": topic}
        self._refresh_unit_count(unit_iid)
        return iid

    def _refresh_unit_count(self, unit_iid: str) -> None:
        count = len(self.tree.get_children(unit_iid))
        title = self.nodes[unit_iid]["title"]
        self.tree.item(unit_iid, text=title, values=("", f"{count} topics"))

    def _selected(self) -> str | None:
        selected = self.tree.selection()
        return selected[0] if selected else None

    def _add_unit(self) -> None:
        dialog = TopicEditor(self, title="", unit=True)
        self.wait_window(dialog)
        if not dialog.result:
            return
        unit = UnitDraft(title=dialog.result["title"], topics=[])
        iid = self._insert_unit(unit)
        self.tree.selection_set(iid)

    def _add_topic(self) -> None:
        selected = self._selected()
        if selected is None:
            messagebox.showinfo(APP_NAME, "Select a unit first.")
            return
        unit_iid = selected if self.nodes[selected]["type"] == "unit" else self.tree.parent(selected)
        dialog = TopicEditor(self, title="")
        self.wait_window(dialog)
        if not dialog.result:
            return
        topic = TopicDraft(
            title=dialog.result["title"],
            objective=dialog.result["objective"],
            focus=dialog.result["focus"],
        )
        iid = self._insert_topic(unit_iid, topic)
        self.tree.selection_set(iid)
        self.tree.item(unit_iid, open=True)

    def _edit(self) -> None:
        selected = self._selected()
        if selected is None:
            return
        node = self.nodes[selected]
        if node["type"] == "unit":
            dialog = TopicEditor(self, title=node["title"], unit=True)
            self.wait_window(dialog)
            if not dialog.result:
                return
            node["title"] = dialog.result["title"]
            self._refresh_unit_count(selected)
            return
        topic: TopicDraft = node["draft"]
        dialog = TopicEditor(self, title=topic.title, objective=topic.objective, focus=topic.focus)
        self.wait_window(dialog)
        if not dialog.result:
            return
        topic.title = dialog.result["title"]
        topic.objective = dialog.result["objective"]
        topic.focus = dialog.result["focus"]
        self.tree.item(
            selected,
            text=topic.title,
            values=(FOCUS_LABELS.get(topic.focus, "Concept"), topic.objective),
        )

    def _delete(self) -> None:
        selected = self._selected()
        if selected is None:
            return
        if self.nodes[selected]["type"] == "unit":
            for child in self.tree.get_children(selected):
                self.nodes.pop(child, None)
        parent = self.tree.parent(selected)
        self.nodes.pop(selected, None)
        self.tree.delete(selected)
        if parent:
            self._refresh_unit_count(parent)

    def _move(self, delta: int) -> None:
        selected = self._selected()
        if selected is None:
            return
        parent = self.tree.parent(selected)
        index = self.tree.index(selected)
        target = index + delta
        if target < 0 or target >= len(self.tree.get_children(parent)):
            return
        self.tree.move(selected, parent, target)

    def _save(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning(APP_NAME, "Name the subject before saving the study path.")
            return
        units: list[UnitDraft] = []
        for unit_iid in self.tree.get_children(""):
            topics: list[TopicDraft] = []
            for topic_iid in self.tree.get_children(unit_iid):
                topic = self.nodes[topic_iid]["draft"]
                if topic.title.strip():
                    topics.append(topic)
            if topics:
                units.append(UnitDraft(title=self.nodes[unit_iid]["title"].strip(), topics=topics))
        if not units:
            messagebox.showwarning(APP_NAME, "Add at least one topic.")
            return
        draft = SyllabusDraft(subject_name=name, kind=kind_value(self.kind_var.get()), units=units)
        syllabus_text = self.app.session.get("syllabus_text") or ""
        subject_id = self.app.db.create_subject(draft, syllabus_text)
        self.app.session.pop("draft", None)
        self.app.session.pop("outline_warning", None)
        self.app.show("study", subject_id=subject_id)
