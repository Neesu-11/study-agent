"""Teach, ask, practice, quiz, and revision for one subject."""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from study_tutor.config import APP_NAME, QUIZ_QUESTIONS, REVISE_QUESTIONS
from study_tutor.db import Topic
from study_tutor.grading import mcq_is_correct, percent_correct, short_is_exact
from study_tutor.materials import Material, select_excerpts
from study_tutor.progress import apply_score, needs_revision, topic_badge
from study_tutor.prompts import (
    ask_request,
    format_outline,
    grade_short_request,
    practice_check_request,
    practice_request,
    quiz_request,
    revise_request,
    system_prompt,
    teach_request,
)
from study_tutor.runner import run_user_code
from study_tutor.schemas import FOCUS_LABELS, KIND_LABELS, PracticeTask, Quiz
from study_tutor.ui.dialogs import MaterialsDialog
from study_tutor.ui.theme import LINE, OK, WEAK
from study_tutor.ui.widgets import ScrolledText, Transcript

_LETTERS = "ABCDEFGHIJ"


class StudyView(ttk.Frame):
    def __init__(self, master: tk.Misc, app):
        super().__init__(master, padding=12)
        self.app = app
        self.subject_id: int | None = None
        self.topic_id: int | None = None
        self._loading = False
        self.quiz: Quiz | None = None
        self.quiz_kind = "quiz"
        self.quiz_answers: list[str] = []
        self.quiz_pos = 0
        self.task: PracticeTask | None = None
        self.last_run = ""

        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        paned = ttk.Panedwindow(self, orient=tk.HORIZONTAL)
        paned.grid(row=0, column=0, sticky="nsew")
        left = ttk.Frame(paned, padding=(0, 0, 8, 0))
        right = ttk.Frame(paned)
        paned.add(left, weight=1)
        paned.add(right, weight=4)
        self._paned = paned
        self._sash_set = False

        ttk.Label(left, text="Study path", style="Subhead.TLabel").pack(anchor="w")
        self.summary_var = tk.StringVar(value="")
        ttk.Label(left, textvariable=self.summary_var, style="Muted.TLabel", wraplength=240).pack(
            anchor="w", pady=(0, 6)
        )
        tree_wrap = ttk.Frame(left)
        tree_wrap.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(tree_wrap, show="tree", selectmode="browse")
        scroll = ttk.Scrollbar(tree_wrap, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.tag_configure("weak", foreground=WEAK)
        self.tree.tag_configure("ok", foreground=OK)
        self.tree.tag_configure("new", foreground="#5e6872")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        ttk.Button(left, text="Next topic", style="Quiet.TButton", command=self._next_topic).pack(
            anchor="w", pady=(8, 0)
        )

        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)
        header = ttk.Frame(right)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        header.columnconfigure(0, weight=1)
        self.subject_var = tk.StringVar(value="")
        ttk.Label(header, textvariable=self.subject_var, style="Eyebrow.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        nav = ttk.Frame(header)
        nav.grid(row=0, column=1, rowspan=2, sticky="ne")
        ttk.Button(nav, text="Materials", style="Quiet.TButton", command=self._materials).pack(side=tk.LEFT)
        ttk.Button(nav, text="Home", style="Quiet.TButton", command=lambda: self.app.show("home")).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        self.title_var = tk.StringVar(value="")
        ttk.Label(header, textvariable=self.title_var, style="Topic.TLabel", wraplength=560).grid(
            row=1, column=0, sticky="w"
        )
        self.detail_var = tk.StringVar(value="")
        ttk.Label(header, textvariable=self.detail_var, style="Muted.TLabel", wraplength=560).grid(
            row=2, column=0, sticky="w", pady=(2, 0)
        )

        modes = ttk.Frame(right)
        modes.grid(row=1, column=0, sticky="ew", pady=(8, 8))
        self.mode_buttons: list[ttk.Button] = []
        for label, command, style in (
            ("Teach me", self.on_teach, "Accent.TButton"),
            ("Practice", self.on_practice, "TButton"),
            ("Quiz me", self.on_quiz, "TButton"),
        ):
            button = ttk.Button(modes, text=label, style=style, command=command)
            button.pack(side=tk.LEFT, padx=(0, 6))
            self.mode_buttons.append(button)
        ttk.Separator(modes, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6, pady=2)
        revise = ttk.Button(modes, text="Revise", style="Quiet.TButton", command=self.on_revise)
        revise.pack(side=tk.LEFT)
        self.mode_buttons.append(revise)

        self.transcript = Transcript(right)
        self.transcript.grid(row=2, column=0, sticky="nsew")

        self.dock = ttk.Frame(right)
        self.dock.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        tk.Frame(self.dock, height=1, background=LINE).pack(fill=tk.X, pady=(0, 8))

        self.practice = ttk.LabelFrame(self.dock, text="Practice", padding=8)
        self.hint_var = tk.StringVar(value="")
        ttk.Label(self.practice, textvariable=self.hint_var, wraplength=640).pack(anchor="w")
        self.code_label = ttk.Label(self.practice, text="Your code")
        self.code_box = ScrolledText(self.practice, height=8, font=("Consolas", 10))
        self.output_label = ttk.Label(self.practice, text="Run output")
        self.output_box = ScrolledText(self.practice, height=4, font=("Consolas", 10), readonly=True)
        self.practice_buttons = ttk.Frame(self.practice)
        practice_buttons = self.practice_buttons
        self.hint_button = ttk.Button(practice_buttons, text="Hint", style="Quiet.TButton", command=self._show_hint)
        self.hint_button.pack(side=tk.LEFT)
        self.run_button = ttk.Button(practice_buttons, text="Run", command=self._run_code)
        self.run_button.pack(side=tk.LEFT, padx=6)
        self.check_button = ttk.Button(
            practice_buttons, text="Check my work", style="Accent.TButton", command=self._check_practice
        )
        self.check_button.pack(side=tk.LEFT)
        self.practice_note = ttk.Label(
            self.practice,
            text="Run executes this code on your computer, in a temporary folder, and stops it after 5 seconds.",
            style="Muted.TLabel",
            wraplength=640,
        )

        self.quiz_frame = ttk.LabelFrame(self.dock, text="Quiz", padding=8)
        self.quiz_prompt = tk.StringVar(value="")
        ttk.Label(self.quiz_frame, textvariable=self.quiz_prompt, wraplength=640, justify=tk.LEFT).pack(anchor="w")
        self.choice_frame = ttk.Frame(self.quiz_frame)
        self.answer_var = tk.StringVar(value="")
        self.short_box = ScrolledText(self.quiz_frame, height=3)
        self.quiz_buttons = ttk.Frame(self.quiz_frame)
        self.quiz_buttons.pack(fill=tk.X, pady=(8, 0))
        quiz_buttons = self.quiz_buttons
        ttk.Button(quiz_buttons, text="Back", style="Quiet.TButton", command=self._quiz_back).pack(side=tk.LEFT)
        self.quiz_next = ttk.Button(quiz_buttons, text="Next", style="Accent.TButton", command=self._quiz_next)
        self.quiz_next.pack(side=tk.LEFT, padx=6)
        ttk.Button(quiz_buttons, text="Leave quiz", style="Quiet.TButton", command=self._leave_quiz).pack(
            side=tk.RIGHT
        )

        self.composer = ttk.Frame(self.dock)
        self.composer.pack(fill=tk.X, pady=(8, 0))
        self.composer.columnconfigure(0, weight=1)
        ttk.Label(self.composer, text="Follow-up on this topic", style="Muted.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.question = ScrolledText(self.composer, height=3)
        self.question.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.question.text.bind("<Control-Return>", lambda _event: self.on_send())
        self.send_button = ttk.Button(self.composer, text="Send", style="Accent.TButton", command=self.on_send)
        self.send_button.grid(row=1, column=1, sticky="se", padx=(8, 0))
        ttk.Label(self.composer, text="Ctrl+Enter to send", style="Eyebrow.TLabel").grid(
            row=2, column=0, sticky="w", pady=(3, 0)
        )
        self.mode_buttons.append(self.send_button)
        self.mode_buttons.extend([self.hint_button, self.run_button, self.check_button, self.quiz_next])

    def on_show(self, subject_id: int | None = None, topic_id: int | None = None, **_kwargs) -> None:
        if subject_id is None:
            subject_id = self.subject_id
        subject = self.app.db.get_subject(subject_id) if subject_id else None
        if subject is None:
            self.app.show("home")
            return
        self.subject_id = subject.id
        self._place_sash()
        self._reload_tree(select=topic_id)

    def _place_sash(self) -> None:
        if self._sash_set:
            return
        self._sash_set = True
        self.after(60, lambda: self._paned.sashpos(0, 260))

    def set_busy(self, busy: bool) -> None:
        state = tk.DISABLED if busy else tk.NORMAL
        for button in self.mode_buttons:
            button.configure(state=state)

    def _reload_tree(self, select: int | None = None) -> None:
        assert self.subject_id is not None
        subject = self.app.db.get_subject(self.subject_id)
        topics = self.app.db.topics_for_subject(self.subject_id)
        today = date.today()
        weak = sum(1 for topic in topics if needs_revision(topic.review_state(), today))
        average = round(sum(topic.mastery for topic in topics) / len(topics), 0) if topics else 0
        track = KIND_LABELS.get(subject.kind, "") if subject else ""
        self.summary_var.set(f"{track} · mastery {average:.0f} · {weak} to revise")
        self._loading = True
        self.tree.delete(*self.tree.get_children())
        first_id = None
        for unit in self.app.db.units_for_subject(self.subject_id):
            unit_iid = self.tree.insert("", tk.END, text=unit.title, open=True)
            for topic in unit.topics:
                if first_id is None:
                    first_id = topic.id
                badge = topic_badge(topic.review_state(), today)
                if topic.last_reviewed is None:
                    tag = "new"
                elif needs_revision(topic.review_state(), today):
                    tag = "weak"
                else:
                    tag = "ok"
                self.tree.insert(unit_iid, tk.END, iid=f"t-{topic.id}", text=f"{topic.title}   {badge}", tags=(tag,))
        self._loading = False
        target = select or self.topic_id or first_id
        if target is not None:
            self._select_topic(target, force=True)

    def _on_tree_select(self, _event=None) -> None:
        if self._loading:
            return
        selected = self.tree.selection()
        if not selected or not str(selected[0]).startswith("t-"):
            return
        topic_id = int(str(selected[0])[2:])
        if topic_id == self.topic_id:
            return
        if self.quiz is not None and not self._confirm_leave_quiz():
            self._loading = True
            if self.topic_id is not None:
                self.tree.selection_set(f"t-{self.topic_id}")
            self._loading = False
            return
        self._load_topic(topic_id)

    def _select_topic(self, topic_id: int, force: bool = False) -> None:
        iid = f"t-{topic_id}"
        if not self.tree.exists(iid):
            return
        self._loading = True
        self.tree.selection_set(iid)
        self.tree.see(iid)
        self._loading = False
        if force or topic_id != self.topic_id:
            self._load_topic(topic_id)

    def _load_topic(self, topic_id: int) -> None:
        topic = self.app.db.get_topic(topic_id)
        if topic is None or self.subject_id is None:
            return
        self.topic_id = topic.id
        self.quiz = None
        self.task = None
        self.last_run = ""
        self._hide_practice()
        self._hide_quiz()
        subject = self.app.db.get_subject(self.subject_id)
        self.subject_var.set("" if subject is None else subject.name)
        self.title_var.set(topic.title)
        review = topic.next_review or "not scheduled"
        self.detail_var.set(
            f"{topic.unit_title}  ·  {FOCUS_LABELS.get(topic.focus, 'Concept')}  ·  next review {review}"
        )
        self.transcript.clear()
        messages = self.app.db.list_messages(topic.id)
        if messages:
            for message in messages:
                self.transcript.append(message.role, message.content)
        else:
            self.transcript.show_hint(
                "Teach me explains this topic. Practice sets one task. Quiz me records a score.\n"
                "Questions you type stay on this topic."
            )

    def _current_topic(self) -> Topic | None:
        if self.topic_id is None:
            messagebox.showinfo(APP_NAME, "Select a topic from the study path.")
            return None
        return self.app.db.get_topic(self.topic_id)

    def _history(self) -> list[tuple[str, str]]:
        if self.topic_id is None:
            return []
        messages = self.app.db.list_messages(self.topic_id)
        return [(message.role, message.content) for message in messages[-12:]]

    def _system(self) -> str:
        assert self.subject_id is not None and self.topic_id is not None
        subject = self.app.db.get_subject(self.subject_id)
        topic = self.app.db.get_topic(self.topic_id)
        if subject is None or topic is None:
            raise RuntimeError("That subject is no longer available.")
        materials = [
            Material(item.title, item.kind, item.content)
            for item in self.app.db.list_materials(self.subject_id)
        ]
        excerpt = select_excerpts(materials, topic.title, topic.unit_title, topic.objective)
        return system_prompt(
            subject_name=subject.name,
            kind=subject.kind,
            syllabus_text=subject.syllabus_text,
            outline=format_outline(self.app.db.outline_pairs(self.subject_id)),
            unit_title=topic.unit_title,
            topic_title=topic.title,
            objective=topic.objective,
            focus=topic.focus,
            materials_excerpt=excerpt,
        )

    def _record(self, role: str, content: str, mode: str) -> None:
        assert self.subject_id is not None and self.topic_id is not None
        self.app.db.add_message(self.subject_id, self.topic_id, mode, role, content)
        self.transcript.append(role, content)

    def _chat(self, mode: str, display: str, request: str, after=None) -> None:
        if self.app.busy or self._current_topic() is None:
            return
        if self.quiz is not None:
            messagebox.showinfo(APP_NAME, "Finish or leave the quiz before starting something else.")
            return
        topic_id = self.topic_id
        system = self._system()
        history = self._history()

        def work() -> str:
            return self.app.client().complete(system, history, request)

        def ok(text: str) -> None:
            if self.topic_id != topic_id:
                return
            self._record("user", display, mode)
            self._record("model", text, mode)
            if after is not None:
                after(text)

        self.app.run_async(work, ok)

    def on_teach(self) -> None:
        self._chat("teach", "Teach me this topic.", teach_request())

    def on_send(self) -> None:
        question = self.question.get_text().strip()
        if not question:
            return
        self.question.clear()
        self._chat("ask", question, ask_request(question))

    def on_practice(self) -> None:
        if self.app.busy or self._current_topic() is None:
            return
        if self.quiz is not None:
            messagebox.showinfo(APP_NAME, "Finish or leave the quiz before starting practice.")
            return
        topic_id = self.topic_id
        system = self._system()

        def work() -> PracticeTask:
            return self.app.client().practice(system, practice_request())

        def ok(task: PracticeTask) -> None:
            if self.topic_id != topic_id:
                return
            self.task = task
            body = f"# {task.title}\n\n{task.briefing}"
            if task.success_criteria:
                body += "\n\n# What good looks like\n" + "\n".join(f"- {item}" for item in task.success_criteria)
            self._record("user", "Give me a practice task.", "practice")
            self._record("model", body, "practice")
            self._open_practice(task)

        self.app.run_async(work, ok, status="Writing a practice task…")

    def _open_practice(self, task: PracticeTask) -> None:
        topic = self.app.db.get_topic(self.topic_id) if self.topic_id else None
        coding = bool(task.starter_code) or (topic is not None and topic.focus == "python")
        self.hint_var.set("" if coding else "Write your answer below, then check it.")
        self.last_run = ""
        self.output_box.set_text("")
        self.code_box.set_text(task.starter_code)
        for widget in (
            self.code_label,
            self.code_box,
            self.output_label,
            self.output_box,
            self.practice_buttons,
            self.practice_note,
        ):
            widget.pack_forget()
        if coding:
            self.code_label.pack(anchor="w", pady=(6, 0))
            self.code_box.pack(fill=tk.X, pady=(4, 0))
            self.output_label.pack(anchor="w", pady=(6, 0))
            self.output_box.pack(fill=tk.X)
            self.run_button.pack(side=tk.LEFT, padx=6)
        else:
            self.run_button.pack_forget()
        self.practice_buttons.pack(fill=tk.X, pady=(6, 0))
        if coding:
            self.practice_note.pack(anchor="w", pady=(6, 0))
        self.practice.pack(fill=tk.X, before=self.composer)

    def _hide_practice(self) -> None:
        self.practice.pack_forget()

    def _show_hint(self) -> None:
        if self.task and self.task.hint:
            self.hint_var.set(f"Hint: {self.task.hint}")
        else:
            self.hint_var.set("No hint was stored for this task.")

    def _run_code(self) -> None:
        if self.app.busy:
            return
        source = self.code_box.get_text()
        interpreter = self.app.python_interpreter()

        def work():
            return run_user_code(source, interpreter or "")

        def ok(result) -> None:
            text = result.stdout
            if result.stderr:
                text = (text + "\n" + result.stderr).strip()
            if not text:
                text = "The script finished with no output."
            self.last_run = text
            self.output_box.set_text(text)

        self.app.run_async(work, ok, status="Running your code…")

    def _check_practice(self) -> None:
        if self.app.busy or self.task is None or self._current_topic() is None:
            return
        topic = self.app.db.get_topic(self.topic_id) if self.topic_id else None
        coding = topic is not None and (topic.focus == "python" or bool(self.task.starter_code))
        answer = self.code_box.get_text().strip() if coding else self.question.get_text().strip()
        if not answer:
            messagebox.showinfo(APP_NAME, "Write an answer before checking it.")
            return
        topic_id = self.topic_id
        system = self._system()
        criteria = list(self.task.success_criteria)
        run_output = self.last_run if coding else ""

        def work():
            return self.app.client().grade_practice(
                system,
                practice_check_request(answer=answer, run_output=run_output, criteria=criteria),
            )

        def ok(feedback) -> None:
            if self.topic_id != topic_id:
                return
            lines = [f"# Practice check: {feedback.percent}%", "", feedback.feedback]
            if feedback.missing:
                lines.extend(["", "# Still open", *[f"- {item}" for item in feedback.missing]])
            if feedback.model_answer:
                lines.extend(["", "# One way to do it", feedback.model_answer])
            text = "\n".join(lines)
            self._record("user", "Check my work.", "practice")
            self._record("model", text, "practice")
            self._apply_percent(feedback.percent, "practice", feedback.missing, feedback.feedback)
            if not coding:
                self.question.clear()

        self.app.run_async(work, ok, status="Checking your answer…")

    def on_quiz(self) -> None:
        self._begin_quiz(QUIZ_QUESTIONS, "quiz")

    def on_revise(self) -> None:
        if self.app.busy or self.subject_id is None:
            return
        weak = self.app.db.weak_topics(self.subject_id)
        if not weak:
            messagebox.showinfo(
                APP_NAME,
                "Nothing is waiting for revision. Study a new topic, or take a quiz after you review one.",
            )
            return
        current = self.app.db.get_topic(self.topic_id) if self.topic_id else None
        target = current if current and any(item.id == current.id for item in weak) else weak[0]
        self._select_topic(target.id, force=True)
        topic = self.app.db.get_topic(target.id)
        if topic is None:
            return
        notes = self.app.db.recent_weak_points(topic.id)

        def after(_text: str) -> None:
            if messagebox.askyesno(APP_NAME, "Start a 3-question revision quiz?"):
                self._begin_quiz(REVISE_QUESTIONS, "revise")

        self._chat("revise", "Revise this topic.", revise_request(topic.mastery, notes), after)

    def _begin_quiz(self, count: int, kind: str) -> None:
        if self.app.busy or self._current_topic() is None:
            return
        if self.quiz is not None:
            messagebox.showinfo(APP_NAME, "A quiz is already open.")
            return
        topic_id = self.topic_id
        system = self._system()

        def work() -> Quiz:
            return self.app.client().quiz(system, quiz_request(count), count)

        def ok(quiz: Quiz) -> None:
            if self.topic_id != topic_id:
                return
            self.quiz = quiz
            self.quiz_kind = kind
            self.quiz_answers = [""] * len(quiz.questions)
            self.quiz_pos = 0
            self.quiz_frame.pack(fill=tk.X, before=self.composer)
            self.composer.pack_forget()
            self._render_quiz_question()

        self.app.run_async(work, ok, status="Writing quiz questions…")

    def _render_quiz_question(self) -> None:
        assert self.quiz is not None
        question = self.quiz.questions[self.quiz_pos]
        self.quiz_prompt.set(f"Question {self.quiz_pos + 1} of {len(self.quiz.questions)}\n\n{question.prompt}")
        for child in self.choice_frame.winfo_children():
            child.destroy()
        self.short_box.pack_forget()
        self.choice_frame.pack_forget()
        if question.kind == "mcq":
            self.choice_frame.pack(anchor="w", pady=(8, 0), before=self.quiz_buttons)
            stored = self.quiz_answers[self.quiz_pos]
            self.answer_var.set(stored)
            for index, choice in enumerate(question.choices):
                letter = _LETTERS[index] if index < len(_LETTERS) else str(index + 1)
                ttk.Radiobutton(
                    self.choice_frame,
                    text=f"{letter}. {choice}",
                    value=choice,
                    variable=self.answer_var,
                ).pack(anchor="w", pady=1)
        else:
            self.short_box.pack(fill=tk.X, pady=(8, 0), before=self.quiz_buttons)
            self.short_box.set_text(self.quiz_answers[self.quiz_pos])
        last = self.quiz_pos == len(self.quiz.questions) - 1
        self.quiz_next.configure(text="Submit" if last else "Next")

    def _store_quiz_answer(self) -> None:
        assert self.quiz is not None
        question = self.quiz.questions[self.quiz_pos]
        if question.kind == "mcq":
            self.quiz_answers[self.quiz_pos] = self.answer_var.get().strip()
        else:
            self.quiz_answers[self.quiz_pos] = self.short_box.get_text().strip()

    def _quiz_back(self) -> None:
        if self.quiz is None or self.quiz_pos == 0:
            return
        self._store_quiz_answer()
        self.quiz_pos -= 1
        self._render_quiz_question()

    def _quiz_next(self) -> None:
        if self.quiz is None:
            return
        self._store_quiz_answer()
        if self.quiz_pos < len(self.quiz.questions) - 1:
            self.quiz_pos += 1
            self._render_quiz_question()
            return
        self._submit_quiz()

    def _submit_quiz(self) -> None:
        assert self.quiz is not None
        flags: list[bool | None] = []
        pending: list[tuple[int, str, str, str]] = []
        for index, question in enumerate(self.quiz.questions):
            given = self.quiz_answers[index]
            if question.kind == "mcq":
                flags.append(mcq_is_correct(question, given))
            elif short_is_exact(question.answer, given):
                flags.append(True)
            else:
                flags.append(None)
                pending.append((index, question.prompt, question.answer, given))
        if not pending:
            self._finish_quiz(flags, {})
            return
        topic_id = self.topic_id
        system = self._system()
        quiz = self.quiz

        def work():
            return self.app.client().grade_short(system, grade_short_request(pending))

        def ok(grades) -> None:
            if self.topic_id != topic_id or self.quiz is not quiz:
                return
            by_index = {item.index: item for item in grades}
            extras = {item.index: item.feedback for item in grades}
            for index, flag in enumerate(flags):
                if flag is None:
                    flags[index] = bool(by_index.get(index) and by_index[index].correct)
            self._finish_quiz(flags, extras)

        self.app.run_async(work, ok, status="Marking short answers…")

    def _finish_quiz(self, flags: list[bool | None], extras: dict[int, str]) -> None:
        assert self.quiz is not None and self.topic_id is not None
        correct_flags = [bool(flag) for flag in flags]
        correct = sum(1 for flag in correct_flags if flag)
        total = len(self.quiz.questions)
        percent = percent_correct(correct, total)
        weak_points: list[str] = []
        lines = [f"# Quiz result: {correct}/{total} ({percent}%)", ""]
        for index, question in enumerate(self.quiz.questions):
            given = self.quiz_answers[index] or "[blank]"
            if correct_flags[index]:
                lines.append(f"{index + 1}. Correct. {question.explanation}")
            else:
                weak_points.append(question.prompt)
                extra = extras.get(index) or question.explanation
                lines.append(f"{index + 1}. Not yet. You said: {given}. {extra}")
        state = self._apply_percent(
            percent,
            self.quiz_kind,
            weak_points,
            "\n".join(lines),
            score=correct,
            total=total,
        )
        if state is not None:
            lines.extend(["", f"Next review: {state.next_review}."])
        self._record("user", "Quiz submitted.", self.quiz_kind)
        self._record("model", "\n".join(lines), self.quiz_kind)
        self._hide_quiz()
        self.quiz = None
        self._reload_tree(select=self.topic_id)

    def _apply_percent(
        self,
        percent: int,
        kind: str,
        weak_points: list[str],
        feedback: str,
        score: int | None = None,
        total: int | None = None,
    ):
        topic = self.app.db.get_topic(self.topic_id) if self.topic_id else None
        if topic is None:
            return None
        state = apply_score(topic.review_state(), percent, date.today())
        self.app.db.save_review(topic.id, state)
        if score is None or total is None:
            score, total = percent, 100
        self.app.db.add_attempt(topic.id, kind, score, total, percent, weak_points, feedback)
        self._refresh_badges()
        return state

    def _refresh_badges(self) -> None:
        if self.subject_id is None:
            return
        today = date.today()
        topics = self.app.db.topics_for_subject(self.subject_id)
        weak = sum(1 for topic in topics if needs_revision(topic.review_state(), today))
        average = round(sum(topic.mastery for topic in topics) / len(topics), 0) if topics else 0
        subject = self.app.db.get_subject(self.subject_id)
        track = KIND_LABELS.get(subject.kind, "") if subject else ""
        self.summary_var.set(f"{track} · mastery {average:.0f} · {weak} to revise")
        self._loading = True
        for topic in topics:
            iid = f"t-{topic.id}"
            if not self.tree.exists(iid):
                continue
            if topic.last_reviewed is None:
                tag = "new"
            elif needs_revision(topic.review_state(), today):
                tag = "weak"
            else:
                tag = "ok"
            badge = topic_badge(topic.review_state(), today)
            self.tree.item(iid, text=f"{topic.title}   {badge}", tags=(tag,))
        self._loading = False
        if self.topic_id is not None:
            current = self.app.db.get_topic(self.topic_id)
            if current is not None:
                review = current.next_review or "not scheduled"
                self.detail_var.set(
                    f"{current.unit_title} · {FOCUS_LABELS.get(current.focus, 'Concept')} · next review {review}"
                )

    def _hide_quiz(self) -> None:
        self.quiz_frame.pack_forget()
        if not self.composer.winfo_ismapped():
            self.composer.pack(fill=tk.X)

    def _confirm_leave_quiz(self) -> bool:
        return messagebox.askyesno(APP_NAME, "Leave this quiz without saving a score?")

    def _leave_quiz(self) -> None:
        if self.quiz is None:
            return
        if not self._confirm_leave_quiz():
            return
        self.quiz = None
        self._hide_quiz()

    def _next_topic(self) -> None:
        if self.subject_id is None:
            return
        nxt = self.app.db.next_new_topic(self.subject_id)
        if nxt is None:
            weak = self.app.db.weak_topics(self.subject_id)
            nxt = weak[0] if weak else None
        if nxt is None:
            messagebox.showinfo(APP_NAME, "Every topic has a score. Use Revise weak topics when one is due.")
            return
        if self.quiz is not None and not self._confirm_leave_quiz():
            return
        self.quiz = None
        self._select_topic(nxt.id, force=True)

    def _materials(self) -> None:
        if self.subject_id is None:
            return
        MaterialsDialog(self, self.app, self.subject_id)
