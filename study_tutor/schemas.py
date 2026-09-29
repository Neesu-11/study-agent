"""Structured tutor data and lenient parsers for Gemini JSON."""

from __future__ import annotations

from dataclasses import dataclass, field

from study_tutor.errors import TutorError

FOCUSES = ("python", "excel", "powerbi", "concept")
KINDS = ("python", "excel", "powerbi", "general")

FOCUS_LABELS = {
    "python": "Python",
    "excel": "Excel",
    "powerbi": "Power BI",
    "concept": "Concept",
}
KIND_LABELS = {
    "python": "Python",
    "excel": "Excel",
    "powerbi": "Power BI",
    "general": "General MBA",
}


@dataclass
class TopicDraft:
    title: str
    objective: str = ""
    focus: str = "concept"


@dataclass
class UnitDraft:
    title: str
    topics: list[TopicDraft] = field(default_factory=list)


@dataclass
class SyllabusDraft:
    subject_name: str
    kind: str
    units: list[UnitDraft]


@dataclass
class QuizQuestion:
    prompt: str
    kind: str
    choices: list[str]
    answer: str
    explanation: str


@dataclass
class Quiz:
    questions: list[QuizQuestion]


@dataclass
class PracticeTask:
    title: str
    briefing: str
    starter_code: str
    success_criteria: list[str]
    hint: str


@dataclass
class PracticeFeedback:
    percent: int
    feedback: str
    met_criteria: list[str]
    missing: list[str]
    model_answer: str


@dataclass
class ShortGrade:
    index: int
    correct: bool
    feedback: str


def _clean(value: object) -> str:
    return str(value or "").strip()


def detect_focus(*parts: str) -> str:
    text = " ".join(parts).lower()
    scores = {
        "powerbi": _keyword_score(text, ("power bi", "powerbi", "dax")),
        "excel": _keyword_score(text, ("excel", "spreadsheet", "pivot", "vlookup", "xlookup", "worksheet")),
        "python": _keyword_score(text, ("python", "pandas", "numpy", "jupyter", "dataframe")),
    }
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "concept"
    return best


def _keyword_score(text: str, phrases: tuple[str, ...]) -> int:
    return sum(text.count(phrase) for phrase in phrases)


def normalize_focus(value: object, hint: str = "") -> str:
    raw = _clean(value).lower().replace("_", " ").replace("-", " ")
    aliases = {
        "python": "python",
        "excel": "excel",
        "power bi": "powerbi",
        "powerbi": "powerbi",
        "concept": "concept",
        "general": "concept",
        "theory": "concept",
    }
    if raw in aliases:
        return aliases[raw]
    return detect_focus(f"{raw} {hint}")


def normalize_kind(value: object, units: list[UnitDraft]) -> str:
    raw = _clean(value).lower().replace("_", " ").replace("-", " ")
    aliases = {
        "python": "python",
        "excel": "excel",
        "power bi": "powerbi",
        "powerbi": "powerbi",
        "general": "general",
        "mba": "general",
        "concept": "general",
        "mixed": "general",
    }
    if raw in aliases:
        return aliases[raw]
    return infer_kind(units)


def infer_kind(units: list[UnitDraft]) -> str:
    counts: dict[str, int] = {}
    for unit in units:
        for topic in unit.topics:
            if topic.focus == "concept":
                continue
            counts[topic.focus] = counts.get(topic.focus, 0) + 1
    if len(counts) == 1:
        return next(iter(counts))
    return "general"


def syllabus_from_payload(payload: dict, fallback_name: str) -> SyllabusDraft:
    units: list[UnitDraft] = []
    for unit in payload.get("units") or []:
        if not isinstance(unit, dict):
            continue
        title = _clean(unit.get("title"))
        topics: list[TopicDraft] = []
        for topic in unit.get("topics") or []:
            if isinstance(topic, str):
                topic_title = _clean(topic)
                objective = ""
                focus_value = ""
            elif isinstance(topic, dict):
                topic_title = _clean(topic.get("title"))
                objective = _clean(topic.get("objective"))
                focus_value = topic.get("focus")
            else:
                continue
            if not topic_title:
                continue
            topics.append(
                TopicDraft(
                    title=topic_title[:160],
                    objective=objective[:400],
                    focus=normalize_focus(focus_value, topic_title),
                )
            )
        if title and topics:
            units.append(UnitDraft(title=title[:160], topics=topics))
    if not units:
        raise TutorError("The outline did not contain any units or topics.")
    name = _clean(payload.get("subject_name")) or fallback_name or "Subject"
    return SyllabusDraft(subject_name=name[:120], kind=normalize_kind(payload.get("kind"), units), units=units)


def quiz_from_payload(payload: dict, expected: int) -> Quiz:
    questions: list[QuizQuestion] = []
    for item in payload.get("questions") or []:
        if not isinstance(item, dict):
            continue
        prompt = _clean(item.get("prompt"))
        kind = _clean(item.get("kind")).lower()
        answer = _clean(item.get("answer"))
        explanation = _clean(item.get("explanation"))
        choices = [_clean(choice) for choice in item.get("choices") or [] if _clean(choice)]
        if not prompt or not answer:
            continue
        if kind not in {"mcq", "short"}:
            kind = "mcq" if len(choices) >= 2 else "short"
        if kind == "mcq" and len(choices) < 2:
            kind = "short"
            choices = []
        if kind == "short":
            choices = []
        questions.append(
            QuizQuestion(
                prompt=prompt,
                kind=kind,
                choices=choices[:6],
                answer=answer,
                explanation=explanation,
            )
        )
        if len(questions) >= expected:
            break
    if not questions:
        raise TutorError("Gemini did not return any quiz questions.")
    return Quiz(questions=questions)


def practice_from_payload(payload: dict) -> PracticeTask:
    criteria = [_clean(item) for item in payload.get("success_criteria") or [] if _clean(item)]
    briefing = _clean(payload.get("briefing"))
    if not briefing:
        raise TutorError("Gemini did not return a practice task.")
    return PracticeTask(
        title=_clean(payload.get("title")) or "Practice",
        briefing=briefing,
        starter_code=str(payload.get("starter_code") or "").strip("\n"),
        success_criteria=criteria[:6],
        hint=_clean(payload.get("hint")),
    )


def feedback_from_payload(payload: dict) -> PracticeFeedback:
    try:
        percent = int(payload.get("percent"))
    except (TypeError, ValueError):
        percent = 0
    return PracticeFeedback(
        percent=max(0, min(100, percent)),
        feedback=_clean(payload.get("feedback")) or "Review the criteria and try once more.",
        met_criteria=[_clean(item) for item in payload.get("met_criteria") or [] if _clean(item)],
        missing=[_clean(item) for item in payload.get("missing") or [] if _clean(item)],
        model_answer=_clean(payload.get("model_answer")),
    )


def short_grades_from_payload(payload: dict) -> list[ShortGrade]:
    grades: list[ShortGrade] = []
    for item in payload.get("results") or []:
        if not isinstance(item, dict):
            continue
        try:
            index = int(item.get("index"))
        except (TypeError, ValueError):
            continue
        grades.append(
            ShortGrade(
                index=index,
                correct=bool(item.get("correct")),
                feedback=_clean(item.get("feedback")),
            )
        )
    return grades
