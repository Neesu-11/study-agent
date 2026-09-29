"""Store the Gemini API key in Windows Credential Manager."""

from __future__ import annotations

import keyring
from keyring.errors import PasswordDeleteError

from study_tutor.config import CREDENTIAL_ACCOUNT, CREDENTIAL_SERVICE
from study_tutor.errors import TutorError


def windows_keyring_name() -> str:
    backend = keyring.get_keyring()
    return f"{type(backend).__module__}.{type(backend).__name__}"


def assert_windows_credential_store() -> None:
    name = windows_keyring_name().lower()
    if "win" not in name:
        raise TutorError(
            "Windows Credential Manager is not available "
            f"(keyring backend: {windows_keyring_name()})."
        )


def get_api_key() -> str | None:
    value = keyring.get_password(CREDENTIAL_SERVICE, CREDENTIAL_ACCOUNT)
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def set_api_key(api_key: str) -> None:
    cleaned = api_key.strip()
    if len(cleaned) < 20 or any(char.isspace() for char in cleaned):
        raise TutorError("Enter the API key as a single unbroken string.")
    assert_windows_credential_store()
    keyring.set_password(CREDENTIAL_SERVICE, CREDENTIAL_ACCOUNT, cleaned)


def clear_api_key() -> None:
    try:
        keyring.delete_password(CREDENTIAL_SERVICE, CREDENTIAL_ACCOUNT)
    except PasswordDeleteError:
        return
