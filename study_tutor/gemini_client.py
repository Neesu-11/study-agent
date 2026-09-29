"""Gemini calls for outlines, tutoring, quizzes, and grading."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

from google import genai
from google.genai import types

from study_tutor.config import DEFAULT_MODEL
from study_tutor.errors import TutorError
from study_tutor.schemas import (
    PracticeFeedback,
    PracticeTask,
    Quiz,
    ShortGrade,
    SyllabusDraft,
    feedback_from_payload,
    practice_from_payload,
    quiz_from_payload,
    short_grades_from_payload,
    syllabus_from_payload,
)

log = logging.getLogger(__name__)

SYLLABUS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "subject_name": {"type": "string"},
        "kind": {"type": "string", "enum": ["python", "excel", "powerbi", "general"]},
        "units": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "topics": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "objective": {"type": "string"},
                                "focus": {
                                    "type": "string",
                                    "enum": ["python", "excel", "powerbi", "concept"],
                                },
                            },
                            "required": ["title", "objective", "focus"],
                        },
                    },
                },
                "required": ["title", "topics"],
            },
        },
    },
    "required": ["subject_name", "kind", "units"],
}

QUIZ_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "kind": {"type": "string", "enum": ["mcq", "short"]},
                    "choices": {"type": "array", "items": {"type": "string"}},
                    "answer": {"type": "string"},
                    "explanation": {"type": "string"},
                },
                "required": ["prompt", "kind", "choices", "answer", "explanation"],
            },
        }
    },
    "required": ["questions"],
}

PRACTICE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "briefing": {"type": "string"},
        "starter_code": {"type": "string"},
        "success_criteria": {"type": "array", "items": {"type": "string"}},
        "hint": {"type": "string"},
    },
    "required": ["title", "briefing", "starter_code", "success_criteria", "hint"],
}

FEEDBACK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "percent": {"type": "integer"},
        "feedback": {"type": "string"},
        "met_criteria": {"type": "array", "items": {"type": "string"}},
        "missing": {"type": "array", "items": {"type": "string"}},
        "model_answer": {"type": "string"},
    },
    "required": ["percent", "feedback", "met_criteria", "missing", "model_answer"],
}

SHORT_GRADE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "correct": {"type": "boolean"},
                    "feedback": {"type": "string"},
                },
                "required": ["index", "correct", "feedback"],
            },
        }
    },
    "required": ["results"],
}

_SKIP_MODEL_WORDS = ("tts", "image", "live", "embed", "audio", "imagen", "veo", "robot")


def friendly_api_error(exc: Exception, secret: str | None = None) -> str:
    text = str(exc)
    if secret:
        text = text.replace(secret, "[key]")
    lowered = text.lower()
    if "api_key_invalid" in lowered or "api key not valid" in lowered or " 401" in f" {lowered}":
        return "That API key was rejected. Create a Gemini API key in Google AI Studio and try again."
    if "429" in text or "resource_exhausted" in lowered:
        return "Gemini is rate-limiting this key. Wait a moment and try again."
    if "503" in text or "unavailable" in lowered or "high demand" in lowered:
        return "Gemini is busy right now. This model is under high demand. Wait a minute and try again."
    if "404" in text or "not_found" in lowered:
        return (
            "The selected Gemini model is not available for this key. "
            "Open Settings and try another model, and confirm the key can call the Gemini API."
        )
    if any(word in lowered for word in ("timed out", "timeout", "connection", "network", "unreachable")):
        return "Could not reach Gemini. Check your internet connection and try again."
    compact = " ".join(text.split())
    return f"Gemini request failed: {compact[:400]}"


def _thinking_config():
    thinking_cls = getattr(types, "ThinkingConfig", None)
    if thinking_cls is None:
        return None
    level = getattr(getattr(types, "ThinkingLevel", None), "LOW", "low")
    try:
        return thinking_cls(thinking_level=level, include_thoughts=False)
    except Exception:
        return None


class GeminiClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key.strip()
        self.model = model.strip() or DEFAULT_MODEL
        self._client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(timeout=45_000),
        )

    def validate(self) -> str:
        """Return the model name that accepted a short generation request."""
        try:
            self._generate(
                "Reply with the single word OK.",
                max_tokens=64,
                temperature=0,
                retry_transient=False,
            )
            return self.model
        except TutorError as exc:
            if not _should_switch_model(str(exc)):
                raise
            original = self.model
            try:
                fallback = self._pick_fallback_model(skip={original})
            except TutorError:
                raise exc
            if fallback.lower() == original.lower():
                raise exc
            self.model = fallback
            try:
                self._generate(
                    "Reply with the single word OK.",
                    max_tokens=64,
                    temperature=0,
                    retry_transient=False,
                )
            except TutorError:
                self.model = original
                raise exc
            return self.model

    def extract_syllabus(self, text: str, subject_name: str) -> SyllabusDraft:
        prompt = (
            "Extract a study outline from this MBA syllabus. "
            "Preserve the course order. Use the syllabus topic titles, cleaned lightly. "
            "Do not invent units that are not in the text. "
            "Each topic should be one sitting of about 10 to 30 minutes. "
            "If a unit lists more than 12 sub-bullets, keep the headings rather than every sub-bullet. "
            "objective is one sentence on what the student should be able to do. "
            "focus is python, excel, powerbi, or concept. "
            "kind is python, excel, powerbi, or general. Use general when the course mixes those or is a standard MBA subject.\n\n"
            f"Preferred subject name, if you cannot find a title: {subject_name or 'Subject'}\n\n"
            f"<syllabus>\n{text[:100000]}\n</syllabus>"
        )
        payload = self._generate_json(prompt, SYLLABUS_SCHEMA, temperature=0.2, max_tokens=8192)
        return syllabus_from_payload(payload, subject_name or "Subject")

    def complete(self, system: str, history: list[tuple[str, str]], user_text: str) -> str:
        contents = _contents(history, user_text)
        return self._generate(contents, system=system, temperature=0.6, max_tokens=2048)

    def quiz(self, system: str, user_text: str, count: int) -> Quiz:
        payload = self._generate_json(
            user_text,
            QUIZ_SCHEMA,
            system=system,
            temperature=0.4,
            max_tokens=4096,
        )
        return quiz_from_payload(payload, count)

    def practice(self, system: str, user_text: str) -> PracticeTask:
        payload = self._generate_json(
            user_text,
            PRACTICE_SCHEMA,
            system=system,
            temperature=0.5,
            max_tokens=2500,
        )
        return practice_from_payload(payload)

    def grade_short(self, system: str, user_text: str) -> list[ShortGrade]:
        payload = self._generate_json(
            user_text,
            SHORT_GRADE_SCHEMA,
            system=system,
            temperature=0,
            max_tokens=2048,
        )
        return short_grades_from_payload(payload)

    def grade_practice(self, system: str, user_text: str) -> PracticeFeedback:
        payload = self._generate_json(
            user_text,
            FEEDBACK_SCHEMA,
            system=system,
            temperature=0.2,
            max_tokens=2048,
        )
        return feedback_from_payload(payload)

    def _generate_json(
        self,
        contents: str,
        schema: dict[str, Any],
        *,
        system: str | None = None,
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        text = self._generate(
            contents,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            schema=schema,
        )
        return _parse_json(text)

    def _generate(
        self,
        contents: str | list[dict[str, Any]],
        *,
        system: str | None = None,
        temperature: float,
        max_tokens: int,
        schema: dict[str, Any] | None = None,
        retry_transient: bool = True,
    ) -> str:
        config_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        thinking = _thinking_config()
        if thinking is not None:
            config_kwargs["thinking_config"] = thinking
        if system:
            config_kwargs["system_instruction"] = system
        if schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            fields = getattr(types.GenerateContentConfig, "model_fields", {})
            if "response_json_schema" in fields:
                config_kwargs["response_json_schema"] = schema
            else:
                config_kwargs["response_schema"] = schema
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=contents,
                    config=types.GenerateContentConfig(**config_kwargs),
                )
                text = (response.text or "").strip()
                if not text:
                    raise TutorError("Gemini returned an empty response.")
                return text
            except TutorError:
                raise
            except Exception as exc:
                last_error = exc
                message = str(exc).lower()
                if attempt == 0 and ("thinking" in message or "thinking_level" in message):
                    config_kwargs.pop("thinking_config", None)
                    continue
                if (
                    retry_transient
                    and attempt == 0
                    and any(token in message for token in ("429", "503", "unavailable", "resource_exhausted"))
                ):
                    time.sleep(2)
                    continue
                log.info("gemini call failed: %s", friendly_api_error(exc, self.api_key))
                raise TutorError(friendly_api_error(exc, self.api_key)) from exc
        raise TutorError(friendly_api_error(last_error or Exception("unknown"), self.api_key))

    def _pick_fallback_model(self, skip: set[str] | None = None) -> str:
        skipped = {name.lower() for name in (skip or set())}
        try:
            names = []
            for model in self._client.models.list():
                raw = getattr(model, "name", "") or ""
                name = raw.split("/")[-1]
                lowered = name.lower()
                if lowered in skipped or not lowered.startswith("gemini"):
                    continue
                if any(word in lowered for word in _SKIP_MODEL_WORDS):
                    continue
                names.append(name)
        except Exception as exc:
            raise TutorError(friendly_api_error(exc, self.api_key)) from exc
        for preferred in names:
            if "flash" in preferred and "lite" not in preferred:
                return preferred
        for preferred in names:
            if "flash" in preferred:
                return preferred
        if names:
            return names[0]
        raise TutorError("This API key cannot see a Gemini text model.")


def _should_switch_model(message: str) -> bool:
    lowered = message.lower()
    return any(
        token in lowered
        for token in ("not available", "high demand", "unavailable", "503", "not found", "404")
    )


def _contents(history: list[tuple[str, str]], user_text: str) -> list[dict[str, Any]]:
    items: list[tuple[str, str]] = []
    for role, text in history[-12:]:
        mapped = "user" if role == "user" else "model"
        cleaned = text.strip()
        if not cleaned:
            continue
        if items and items[-1][0] == mapped:
            items[-1] = (mapped, items[-1][1] + "\n\n" + cleaned)
        else:
            items.append((mapped, cleaned))
    if items and items[-1][0] == "user":
        items[-1] = ("user", items[-1][1] + "\n\n" + user_text)
    else:
        items.append(("user", user_text))
    if items[0][0] != "user":
        items.insert(0, ("user", "Continue this tutoring session."))
    return [{"role": role, "parts": [{"text": text[:8000]}]} for role, text in items]


def _parse_json(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        if candidate.lower().startswith("json"):
            candidate = candidate[4:]
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            try:
                payload = json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                raise TutorError("Gemini returned JSON that could not be read.") from exc
        else:
            raise TutorError("Gemini returned JSON that could not be read.") from exc
    if not isinstance(payload, dict):
        raise TutorError("Gemini returned a JSON value that was not an object.")
    return payload
