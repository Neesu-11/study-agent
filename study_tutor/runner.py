"""Run a student's Python exercise in a short-lived local process."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from study_tutor.config import CODE_TIMEOUT_SECONDS

_SECRET_HINTS = ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")


@dataclass
class RunResult:
    ok: bool
    stdout: str
    stderr: str


def discover_python(override: str = "") -> str | None:
    """Find an interpreter that can execute lesson code.

    A packaged app is not itself a Python interpreter, so Run looks for a
    system Python when the tutor is frozen.
    """
    chosen = override.strip().strip('"')
    if chosen:
        return chosen
    if not getattr(sys, "frozen", False):
        return sys.executable
    attempts = (["py", "-3"], ["python"], ["python3"])
    for command in attempts:
        try:
            completed = subprocess.run(
                [*command, "-c", "import sys; print(sys.executable)"],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if completed.returncode != 0:
            continue
        lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        if lines:
            return lines[-1]
    return None


def run_user_code(source: str, interpreter: str, timeout: float = CODE_TIMEOUT_SECONDS) -> RunResult:
    if not interpreter:
        return RunResult(
            ok=False,
            stdout="",
            stderr="No Python interpreter was found. Install Python, or set its path in Settings. You can still ask the tutor to check the code.",
        )
    if len(source) > 50_000:
        return RunResult(ok=False, stdout="", stderr="That snippet is too long to run here.")
    with tempfile.TemporaryDirectory(prefix="mba-tutor-") as folder:
        script = Path(folder) / "exercise.py"
        script.write_text(source, encoding="utf-8")
        try:
            completed = subprocess.run(
                [interpreter, str(script)],
                cwd=folder,
                env=_scrubbed_env(),
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = _clip(exc.stdout)
            stderr = _clip(exc.stderr)
            return RunResult(False, stdout, (stderr + "\nTimed out after 5 seconds.").strip())
        except OSError as exc:
            return RunResult(False, "", f"Could not start Python: {exc}")
        return RunResult(completed.returncode == 0, _clip(completed.stdout), _clip(completed.stderr))


def _scrubbed_env() -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in os.environ.items():
        upper = key.upper()
        if any(hint in upper for hint in _SECRET_HINTS):
            continue
        cleaned[key] = value
    return cleaned


def _clip(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    if len(text) > 20_000:
        return text[:20_000] + "\n[output truncated]"
    return text
