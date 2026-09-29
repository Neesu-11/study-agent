"""Paths, model choice, and other fixed settings."""

from __future__ import annotations

import logging
import os
from pathlib import Path

APP_NAME = "MBA Study Tutor"
CREDENTIAL_SERVICE = "MBAStudyTutor"
CREDENTIAL_ACCOUNT = "gemini-api-key"
DEFAULT_MODEL = "gemini-3.8-flash"
DATA_DIR_NAME = "MBAStudyTutor"

MAX_FILE_BYTES = 15 * 1024 * 1024
MAX_DOCUMENT_CHARS = 150_000
SYLLABUS_PROMPT_CHARS = 12_000
MATERIAL_PROMPT_CHARS = 7_000
HISTORY_MESSAGES = 12
QUIZ_QUESTIONS = 5
REVISE_QUESTIONS = 3
CODE_TIMEOUT_SECONDS = 5


def data_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(root) / DATA_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    override = os.environ.get("STUDY_TUTOR_DB")
    if override:
        path = Path(override)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    return data_dir() / "study_tutor.db"


def configure_logging() -> None:
    log_path = data_dir() / "app.log"
    root = logging.getLogger()
    if any(isinstance(handler, logging.FileHandler) for handler in root.handlers):
        return
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
