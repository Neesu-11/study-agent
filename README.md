# MBA Study Tutor

A local Windows app for one student. You save a Gemini API key, import an MBA syllabus, edit the outline, and study one topic at a time. Progress, chat, and notes stay in a SQLite file on this PC. The API key stays in Windows Credential Manager.

This README is a map of the code: how the pieces fit, which Python ideas they use, and where to learn those ideas.

## Architecture

The program is split into four layers. The window never talks to SQLite or Gemini directly. It calls a small set of modules, and those modules do not know about buttons or text boxes.

```text
run_app.py / python -m study_tutor
        |
        v
study_tutor/ui          Tkinter screens. One job: show state and collect clicks.
        |
        v
study_tutor/*.py        Rules: outlines, prompts, grading, revision dates.
        |
        +--> db.py             SQLite
        +--> credentials.py    Windows Credential Manager
        +--> gemini_client.py  HTTPS calls to Gemini
        +--> runner.py         A short-lived Python process for exercises
```

A button click stays on the Tk thread only long enough to start work. Gemini and file parsing run on a background thread. The result is placed on a `queue.Queue`. The window polls that queue and then updates widgets. Tkinter is not thread-safe, so the worker thread never touches a widget.

### What happens when you study

1. `SetupView` checks the API key, then `credentials.py` stores it.
2. `ImportView` reads paste, PDF, or DOCX text through `syllabus.py`.
3. `GeminiClient.extract_syllabus` asks Gemini for JSON that matches a fixed schema. If that call fails, `parse_syllabus_locally` builds an outline with regular expressions.
4. `OutlineView` lets you edit that outline. `Database.create_subject` saves units and topics.
5. `StudyView` loads one topic. `prompts.py` builds the instructions. `GeminiClient` sends them. Messages and quiz scores go back through `db.py`.
6. `progress.py` turns a score into the next review date.

### Folder map

| Path | Role |
| --- | --- |
| `run_app.py` | Entry point PyInstaller freezes into the `.exe`. |
| `study_tutor/__main__.py` | `python -m study_tutor`. Parses `--self-check` with `argparse`. |
| `study_tutor/ui/app.py` | Main window, screen switching, background-job queue. |
| `study_tutor/ui/setup_view.py` | API key screen. |
| `study_tutor/ui/home_view.py` | Subject list. |
| `study_tutor/ui/import_view.py` | Paste or open a syllabus. |
| `study_tutor/ui/outline_view.py` | Editable unit and topic tree. |
| `study_tutor/ui/study_view.py` | Chat, practice, quiz, and revision. |
| `study_tutor/ui/dialogs.py` | Notes, textbooks, and settings windows. |
| `study_tutor/ui/widgets.py` | Scrolling text and the chat transcript. |
| `study_tutor/ui/theme.py` | Colours and fonts. |
| `study_tutor/db.py` | SQLite schema and queries. |
| `study_tutor/schemas.py` | Dataclasses for an outline, a quiz, and a practice task. |
| `study_tutor/syllabus.py` | PDF, DOCX, and plain-text reading. Local outline parser. |
| `study_tutor/prompts.py` | Text sent to Gemini. No network code here. |
| `study_tutor/gemini_client.py` | The only module that calls the Gemini API. |
| `study_tutor/grading.py` | Scores multiple-choice answers on this machine. |
| `study_tutor/progress.py` | Mastery and the next review date. |
| `study_tutor/materials.py` | Picks short excerpts from notes that match the topic. |
| `study_tutor/credentials.py` | Read and write the API key. |
| `study_tutor/runner.py` | Runs exercise code in a subprocess with a timeout. |
| `study_tutor/config.py` | App name, model name, and the database path. |
| `study_tutor/errors.py` | `TutorError`, the exception the window can show as a sentence. |
| `tests/` | Pytest checks that do not need a Gemini key. |
| `StudyTutor.spec` | PyInstaller build for `dist\MBAStudyTutor\MBAStudyTutor.exe`. |

### Data stored on this PC

`%LOCALAPPDATA%\MBAStudyTutor\study_tutor.db`

| Table | Holds |
| --- | --- |
| `subjects` | Course name, track, and the original syllabus text. |
| `units`, `topics` | The study path, plus mastery and the next review date on each topic. |
| `messages` | Chat for one topic. |
| `quiz_attempts` | Score, percent, and what was missed. |
| `materials` | Notes and textbook text. |
| `settings` | Chosen model and optional Python path. Not the API key. |

The key is stored with the `keyring` package, which uses Windows Credential Manager (`WinVaultKeyring`).

## Python concepts used here

Each idea below is used in this repo. The links are the official docs unless noted.

### Packages, modules, and `if __name__`

`study_tutor` is a package (a folder with `__init__.py`). `python -m study_tutor` runs `study_tutor/__main__.py`. `run_app.py` imports `main` so the frozen executable has a single script to start from. The `if __name__ == "__main__"` guard means importing the file does not launch the window.

- [Modules](https://docs.python.org/3/tutorial/modules.html)
- [The `import` system](https://docs.python.org/3/reference/import.html)

### Functions, classes, and methods

Screens are classes that inherit from `ttk.Frame`. `Database` and `GeminiClient` are classes whose methods group related behaviour. Small operations, such as `needs_revision` and `mcq_is_correct`, are plain functions because they do not need stored state.

- [Classes](https://docs.python.org/3/tutorial/classes.html)
- [tkinter](https://docs.python.org/3/library/tkinter.html)
- [TkDocs tutorial](https://tkdocs.com/tutorial/index.html) (clearer than the standard-library page for layout)

### Dataclasses

`Subject`, `Topic`, `SyllabusDraft`, and `Quiz` are `@dataclass` types. A dataclass writes `__init__` for you and keeps field names in one place. The UI and the database pass these objects around instead of raw tuples.

- [dataclasses](https://docs.python.org/3/library/dataclasses.html)

### Type hints

Signatures such as `def validate(self) -> str` and `list[str] | None` document what goes in and out. They are not required for the program to run. Pytest and the editor use them as a map.

- [Type hints](https://docs.python.org/3/library/typing.html)
- [typing cheat sheet](https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html) from mypy (the annotations, not a type-checker run in this project)

### Exceptions

`TutorError` and `ScannedDocumentError` are subclasses of `Exception`. Callers raise them with a sentence a student can read. A broad `except Exception` on the worker thread logs the traceback, then shows `str(exc)` on the window.

- [Errors and exceptions](https://docs.python.org/3/tutorial/errors.html)

### Context managers

`with self._lock` and `with self._conn` in `db.py` mean the lock is released and the transaction is committed even if a query fails. `runner.py` uses `tempfile.TemporaryDirectory` the same way: the folder is deleted when the block ends.

- [The `with` statement](https://docs.python.org/3/reference/compound_stmts.html#the-with-statement)

### `pathlib`, the environment, and files

`config.py` builds the database path from `LOCALAPPDATA` or an override in `STUDY_TUTOR_DB`. `syllabus.py` branches on the file suffix (`.pdf`, `.docx`, `.txt`). Tests pass `tmp_path` from pytest so they never write the real database.

- [pathlib](https://docs.python.org/3/library/pathlib.html)
- [os.environ](https://docs.python.org/3/library/os.html#os.environ)

### Regular expressions

`syllabus.py` uses the `re` module to find lines like `Unit I:` and bullet topics when Gemini is unavailable. `materials.py` uses it to split notes into paragraphs.

- [Regular expression HOWTO](https://docs.python.org/3/howto/regex.html)

### SQLite

`db.py` uses the standard-library `sqlite3` module. `PRAGMA foreign_keys = ON` makes deleting a subject delete its units, topics, messages, and notes. Rows are turned into dataclasses before they leave the module, so the rest of the app does not handle SQL strings.

- [sqlite3](https://docs.python.org/3/library/sqlite3.html)
- [SQL as understood by SQLite](https://www.sqlite.org/lang.html)

### Threads and queues

`App.run_async` starts a `threading.Thread`. The thread pushes `("ok", result)` or `("err", exception)` onto a `queue.Queue`. `App._drain_jobs` runs on the Tk thread via `after`, about ten times a second, and applies the result. That split is why a slow Gemini call does not freeze the window, and why an error still reaches the screen.

- [threading](https://docs.python.org/3/library/threading.html)
- [queue](https://docs.python.org/3/library/queue.html)

### Subprocesses

`runner.py` writes the exercise to a temp file and runs it with `subprocess.run`. A five-second `timeout` stops an infinite loop. The packaged app is not itself a Python interpreter, so Run looks for a system `python` or `py -3`.

- [subprocess](https://docs.python.org/3/library/subprocess.html)

### JSON and external APIs

`gemini_client.py` sends a JSON schema (`response_json_schema`) so syllabus, quiz, and practice replies have fixed fields. `_parse_json` still checks the text, because a network client should not trust a string blindly. `friendly_api_error` turns HTTP status codes into short messages and strips the API key if it appears in an error.

- [json](https://docs.python.org/3/library/json.html)
- [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [google-genai SDK](https://googleapis.github.io/python-genai/)

### Command-line arguments

`__main__.py` uses `argparse`. With no flags, the window opens. `--self-check` runs local checks and exits. That is how the packaged executable is tested without clicking through the UI.

- [argparse](https://docs.python.org/3/library/argparse.html)

### Virtual environments and third-party packages

`.venv` holds dependencies so they are not installed into the system Python. `requirements.txt` is what the app needs at runtime: `google-genai`, `pypdf`, `python-docx`, `keyring`, `pywin32`. `requirements-dev.txt` adds `pytest` and `pyinstaller`.

- [venv](https://docs.python.org/3/library/venv.html)
- [Installing packages](https://packaging.python.org/en/latest/tutorials/installing-packages/)

### Tests

`tests/` imports the same modules as the app and checks them with plain `assert`. `tmp_path` and `monkeypatch` are pytest fixtures. The UI smoke test builds a hidden Tk window, which is why it needs a desktop session.

- [pytest getting started](https://docs.pytest.org/en/stable/getting-started.html)

## A learning path through this repo

Read in this order if you are new to Python. Each step is enough to open the matching file and follow it.

1. The official [Python tutorial](https://docs.python.org/3/tutorial/) through chapter 8 (errors) and chapter 9 (classes). [Automate the Boring Stuff](https://automatetheboringstuff.com/) is a free practical companion for files, paths, and programs that do one job.
2. Modules, then open `study_tutor/__main__.py` and `run_app.py`.
3. Dataclasses and type hints, then open `study_tutor/schemas.py` and `study_tutor/progress.py`. `progress.py` has no UI and no network, so it is the easiest file to change and retest.
4. Exceptions and `with`, then open `study_tutor/errors.py` and the `create_subject` method in `study_tutor/db.py`.
5. `sqlite3`, then read the `CREATE TABLE` script in `db.py` next to `tests/test_db.py`.
6. `re` and `pathlib`, then `study_tutor/syllabus.py` next to `tests/test_syllabus.py`.
7. Tkinter via [TkDocs](https://tkdocs.com/tutorial/index.html), then `study_tutor/ui/home_view.py` (a short screen) before `study_view.py`.
8. `threading` and `queue`, then `run_async` and `_drain_jobs` in `study_tutor/ui/app.py`.
9. `subprocess`, then `study_tutor/runner.py`.
10. pytest, then run `python -m pytest` and read a failing assertion before changing production code.

## Run and test

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m study_tutor
```

```powershell
python -m pytest
python -m study_tutor --self-check
pyinstaller --noconfirm StudyTutor.spec
```

The executable is `dist\MBAStudyTutor\MBAStudyTutor.exe`. Tutoring needs internet. Running a Python exercise from the packaged app needs a Python interpreter on the machine. This version does not OCR scanned PDFs, open Power BI, or edit Excel files.
