import os
import time

import pytest

from study_tutor.errors import TutorError
from study_tutor.schemas import PracticeTask
from study_tutor.syllabus import SAMPLE_SYLLABUS, parse_syllabus_locally


@pytest.mark.skipif(os.environ.get("STUDY_TUTOR_SKIP_UI") == "1", reason="UI smoke test disabled")
def test_screens_build(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDY_TUTOR_DB", str(tmp_path / "ui.db"))
    from study_tutor.ui.app import App

    app = App()
    app.withdraw()
    try:
        app.show("home")
        app.show("import")
        draft = parse_syllabus_locally(SAMPLE_SYLLABUS, "Business Analytics")
        app.session["draft"] = draft
        app.session["syllabus_text"] = SAMPLE_SYLLABUS
        app.show("outline")
        subject_id = app.db.create_subject(draft, SAMPLE_SYLLABUS)
        app.show("study", subject_id=subject_id)
        app.views["study"]._open_practice(
            PracticeTask(
                title="Try a filter",
                briefing="Keep the rows with a missing price.",
                starter_code="rows = []\n",
                success_criteria=["The result lists only blank prices."],
                hint="Look for an empty string.",
            )
        )
        seen: list[str] = []

        def work():
            raise TutorError("Gemini is busy right now.")

        app.run_async(work, lambda _result: None, on_err=lambda exc: seen.append(str(exc)))
        deadline = time.monotonic() + 3
        while not seen and time.monotonic() < deadline:
            app.update()
            time.sleep(0.05)
        assert seen == ["Gemini is busy right now."]
        assert app.busy is False
        app.update_idletasks()
    finally:
        app.destroy()
