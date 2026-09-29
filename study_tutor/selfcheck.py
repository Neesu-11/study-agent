"""Startup checks used by tests and the packaged executable."""

from __future__ import annotations

from datetime import date
import tempfile
import traceback
from pathlib import Path

from study_tutor import __version__
from study_tutor.credentials import windows_keyring_name
from study_tutor.db import Database
from study_tutor.grading import mcq_is_correct
from study_tutor.progress import ReviewState, apply_score
from study_tutor.prompts import system_prompt
from study_tutor.runner import discover_python, run_user_code
from study_tutor.schemas import QuizQuestion
from study_tutor.syllabus import SAMPLE_SYLLABUS, parse_syllabus_locally


def run_self_check(result_path: Path | None = None) -> int:
    lines: list[str] = []
    try:
        lines.append(f"version {__version__}")
        draft = parse_syllabus_locally(SAMPLE_SYLLABUS, "")
        if len(draft.units) < 4:
            raise RuntimeError("sample syllabus did not produce four units")
        with tempfile.TemporaryDirectory(prefix="mba-selfcheck-") as folder:
            database = Database(Path(folder) / "check.db")
            subject_id = database.create_subject(draft, SAMPLE_SYLLABUS)
            topics = database.topics_for_subject(subject_id)
            if len(topics) < 8:
                raise RuntimeError("sample subject did not store its topics")
            database.close()
        updated = apply_score(ReviewState(), 40, date(2026, 9, 29))
        if updated.status != "weak":
            raise RuntimeError("a low score should schedule revision")
        question = QuizQuestion("Pick one", "mcq", ["Alpha", "Beta"], "Beta", "Because.")
        if not mcq_is_correct(question, "b"):
            raise RuntimeError("multiple choice grading failed")
        prompt = system_prompt(
            subject_name="Analytics",
            kind="general",
            syllabus_text="Unit I",
            outline="Unit I\n- Metrics",
            unit_title="Unit I",
            topic_title="Metrics",
            objective="Choose a metric",
            focus="concept",
            materials_excerpt="",
        )
        if "Metrics" not in prompt or "outside" not in prompt:
            raise RuntimeError("system prompt lost the topic boundary")
        interpreter = discover_python()
        if interpreter:
            ran = run_user_code("print(6 * 7)", interpreter)
            if not ran.ok or "42" not in ran.stdout:
                raise RuntimeError(ran.stderr or "python runner failed")
            lines.append("python runner ok")
        else:
            lines.append("python runner skipped")
        backend = windows_keyring_name()
        if "win" not in backend.lower():
            raise RuntimeError(f"unexpected credential backend: {backend}")
        lines.append(f"credentials {backend}")
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        tk.Label(root, text="ok")
        root.update_idletasks()
        root.destroy()
        lines.append("tkinter ok")
        lines.append("SELF_CHECK_OK")
        code = 0
    except Exception:
        lines.append("SELF_CHECK_FAIL")
        lines.append(traceback.format_exc())
        code = 1
    text = "\n".join(lines) + "\n"
    if result_path is not None:
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(text, encoding="utf-8")
    try:
        print(text, end="")
    except Exception:
        pass
    return code
