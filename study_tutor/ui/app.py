"""Main window and screen navigation."""

from __future__ import annotations

import logging
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from study_tutor import __version__
from study_tutor.config import APP_NAME, configure_logging, db_path
from study_tutor.credentials import get_api_key
from study_tutor.db import Database
from study_tutor.errors import TutorError
from study_tutor.gemini_client import GeminiClient
from study_tutor.runner import discover_python
from study_tutor.ui.home_view import HomeView
from study_tutor.ui.import_view import ImportView
from study_tutor.ui.outline_view import OutlineView
from study_tutor.ui.setup_view import SetupView
from study_tutor.ui.study_view import StudyView
from study_tutor.ui.theme import apply_theme

log = logging.getLogger(__name__)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        configure_logging()
        self.title(APP_NAME)
        self.geometry("1120x740")
        self.minsize(960, 640)
        apply_theme(self)
        self.db = Database(db_path())
        self.session: dict = {}
        self.busy = False
        self._jobs: queue.Queue = queue.Queue()
        self.status = tk.StringVar(value="Ready")
        self._build_menu()
        self.container = ttk.Frame(self)
        self.container.pack(fill=tk.BOTH, expand=True)
        self.views = {
            "setup": SetupView(self.container, self),
            "home": HomeView(self.container, self),
            "import": ImportView(self.container, self),
            "outline": OutlineView(self.container, self),
            "study": StudyView(self.container, self),
        }
        status = ttk.Frame(self, padding=(12, 6))
        status.pack(fill=tk.X)
        ttk.Label(status, textvariable=self.status).pack(side=tk.LEFT)
        self.progress = ttk.Progressbar(status, mode="indeterminate", length=140)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(50, self._route_start)
        self.after(100, self._drain_jobs)

    def _build_menu(self) -> None:
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=0)
        file_menu.add_command(label="Home", command=lambda: self.show("home"))
        file_menu.add_command(label="New subject", command=self._new_subject)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._close)
        settings = tk.Menu(menu, tearoff=0)
        settings.add_command(label="API key and model", command=self._open_settings)
        help_menu = tk.Menu(menu, tearoff=0)
        help_menu.add_command(label="About", command=self._about)
        menu.add_cascade(label="File", menu=file_menu)
        menu.add_cascade(label="Settings", menu=settings)
        menu.add_cascade(label="Help", menu=help_menu)
        self.configure(menu=menu)

    def _route_start(self) -> None:
        if not get_api_key():
            self.show("setup")
        elif not self.db.list_subjects():
            self.show("import")
        else:
            self.show("home")

    def show(self, name: str, **kwargs) -> None:
        if name != "setup" and name != "home" and not get_api_key():
            self.show("setup")
            return
        for view in self.views.values():
            view.pack_forget()
        view = self.views[name]
        view.on_show(**kwargs)
        view.pack(fill=tk.BOTH, expand=True)

    def require_key(self) -> bool:
        if get_api_key():
            return True
        messagebox.showinfo(APP_NAME, "Save a Gemini API key before continuing.")
        self.show("setup")
        return False

    def client(self) -> GeminiClient:
        key = get_api_key()
        if not key:
            raise TutorError("Save a Gemini API key before studying.")
        from study_tutor.config import DEFAULT_MODEL

        model = self.db.get_setting("gemini_model", DEFAULT_MODEL)
        return GeminiClient(key, model)

    def python_interpreter(self) -> str | None:
        return discover_python(self.db.get_setting("python_path", ""))

    def set_status(self, message: str) -> None:
        self.status.set(message)

    def run_async(self, work, on_ok, on_err=None, status: str = "Contacting Gemini…") -> None:
        if self.busy:
            return
        self._set_busy(True, status)

        def target() -> None:
            try:
                result = work()
            except Exception as exc:
                log.exception("background task failed")
                self._jobs.put(("err", exc, on_err))
            else:
                self._jobs.put(("ok", result, on_ok))

        threading.Thread(target=target, daemon=True).start()

    def _drain_jobs(self) -> None:
        try:
            while True:
                kind, payload, callback = self._jobs.get_nowait()
                if kind == "ok":
                    self._finish_ok(payload, callback)
                else:
                    self._finish_error(payload, callback)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(100, self._drain_jobs)

    def _finish_ok(self, result, on_ok) -> None:
        self._set_busy(False, "Ready")
        try:
            on_ok(result)
        except Exception as exc:
            log.exception("ui callback failed")
            messagebox.showerror(APP_NAME, str(exc) or exc.__class__.__name__)

    def _finish_error(self, exc: Exception, on_err) -> None:
        self._set_busy(False, "Ready")
        if on_err is not None:
            on_err(exc)
            return
        messagebox.showerror(APP_NAME, str(exc) or exc.__class__.__name__)

    def _set_busy(self, busy: bool, message: str) -> None:
        self.busy = busy
        self.status.set(message)
        if busy:
            self.progress.pack(side=tk.RIGHT)
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.pack_forget()
        for view in self.views.values():
            setter = getattr(view, "set_busy", None)
            if setter is not None:
                setter(busy)

    def _new_subject(self) -> None:
        if self.require_key():
            self.show("import")

    def _open_settings(self) -> None:
        from study_tutor.ui.dialogs import SettingsDialog

        SettingsDialog(self, self)

    def _about(self) -> None:
        messagebox.showinfo(
            APP_NAME,
            (
                f"{APP_NAME} {__version__}\n\n"
                "One local study path per subject. Explanations come from Gemini and stay "
                "inside the syllabus topic you select.\n\n"
                "The API key is kept in Windows Credential Manager. Progress, chat, and notes "
                "are stored in a SQLite file under your local app data.\n\n"
                "This version does not OCR scanned PDFs, connect to Power BI, or edit Excel files. "
                "Python exercises can be run locally when a Python interpreter is available."
            ),
        )

    def _close(self) -> None:
        try:
            self.db.close()
        finally:
            self.destroy()


def run() -> None:
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    app = App()
    app.mainloop()
