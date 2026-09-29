from study_tutor.grading import mcq_is_correct, percent_correct, short_is_exact
from study_tutor.schemas import QuizQuestion, quiz_from_payload, syllabus_from_payload


def test_multiple_choice_accepts_the_letter_or_the_text():
    question = QuizQuestion("Which one?", "mcq", ["Margin", "Markup"], "Markup", "Markup is on cost.")
    assert mcq_is_correct(question, "Markup")
    assert mcq_is_correct(question, "b")
    assert mcq_is_correct(question, "B.")
    assert mcq_is_correct(question, "Margin") is False
    assert mcq_is_correct(question, "") is False


def test_short_answer_ignores_case_and_spacing():
    assert short_is_exact("Net present value", " net   present value ")
    assert short_is_exact("Net present value", "NPV") is False


def test_percent_rounds_half_up_style():
    assert percent_correct(1, 3) == 33
    assert percent_correct(0, 0) == 0


def test_syllabus_payload_fills_missing_focus():
    draft = syllabus_from_payload(
        {
            "subject_name": "Accounting",
            "kind": "mba",
            "units": [
                {
                    "title": "Unit 1",
                    "topics": [{"title": "Pivot tables in Excel", "objective": "Build one."}],
                }
            ],
        },
        "Fallback",
    )
    assert draft.kind == "general"
    assert draft.units[0].topics[0].focus == "excel"


def test_quiz_payload_drops_broken_questions():
    quiz = quiz_from_payload(
        {
            "questions": [
                {"prompt": "", "kind": "short", "choices": [], "answer": "x", "explanation": ""},
                {
                    "prompt": "Name the statement.",
                    "kind": "short",
                    "choices": [],
                    "answer": "Balance sheet",
                    "explanation": "It lists position.",
                },
            ]
        },
        5,
    )
    assert len(quiz.questions) == 1
    assert quiz.questions[0].kind == "short"
