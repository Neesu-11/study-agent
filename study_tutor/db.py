"""SQLite storage for subjects, progress, chat, and course materials."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from study_tutor.progress import ReviewState, needs_revision
from study_tutor.schemas import SyllabusDraft


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat(timespec="seconds")


@dataclass
class Subject:
    id: int
    name: str
    kind: str
    syllabus_text: str
    created_at: str
    topic_count: int = 0
    avg_mastery: float = 0.0
    weak_count: int = 0


@dataclass
class Topic:
    id: int
    unit_id: int
    unit_title: str
    title: str
    position: int
    objective: str
    focus: str
    mastery: float
    ease: float
    interval_days: int
    repetitions: int
    lapses: int
    last_reviewed: str | None
    next_review: str | None
    status: str

    def review_state(self) -> ReviewState:
        return ReviewState(
            mastery=self.mastery,
            ease=self.ease,
            interval_days=self.interval_days,
            repetitions=self.repetitions,
            lapses=self.lapses,
            last_reviewed=self.last_reviewed,
            next_review=self.next_review,
            status=self.status,
        )


@dataclass
class Unit:
    id: int
    subject_id: int
    title: str
    position: int
    topics: list[Topic]


@dataclass
class Message:
    id: int
    role: str
    mode: str
    content: str
    created_at: str


@dataclass
class StoredMaterial:
    id: int
    title: str
    kind: str
    content: str
    created_at: str


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._create()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _create(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS subjects (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    syllabus_text TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS units (
                    id INTEGER PRIMARY KEY,
                    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    position INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS topics (
                    id INTEGER PRIMARY KEY,
                    unit_id INTEGER NOT NULL REFERENCES units(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    objective TEXT NOT NULL DEFAULT '',
                    focus TEXT NOT NULL DEFAULT 'concept',
                    mastery REAL NOT NULL DEFAULT 0,
                    ease REAL NOT NULL DEFAULT 2.5,
                    interval_days INTEGER NOT NULL DEFAULT 0,
                    repetitions INTEGER NOT NULL DEFAULT 0,
                    lapses INTEGER NOT NULL DEFAULT 0,
                    last_reviewed TEXT,
                    next_review TEXT,
                    status TEXT NOT NULL DEFAULT 'new'
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY,
                    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
                    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
                    mode TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS quiz_attempts (
                    id INTEGER PRIMARY KEY,
                    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    total INTEGER NOT NULL,
                    percent INTEGER NOT NULL,
                    weak_points TEXT NOT NULL DEFAULT '',
                    feedback TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS materials (
                    id INTEGER PRIMARY KEY,
                    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_units_subject ON units(subject_id, position);
                CREATE INDEX IF NOT EXISTS idx_topics_unit ON topics(unit_id, position);
                CREATE INDEX IF NOT EXISTS idx_messages_topic ON messages(topic_id, id);
                """
            )

    def get_setting(self, key: str, default: str) -> str:
        with self._lock:
            row = self._conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return default if row is None else str(row["value"])

    def set_setting(self, key: str, value: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def create_subject(self, draft: SyllabusDraft, syllabus_text: str) -> int:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "INSERT INTO subjects(name, kind, syllabus_text, created_at) VALUES(?, ?, ?, ?)",
                (draft.subject_name.strip(), draft.kind, syllabus_text, _now()),
            )
            subject_id = int(cursor.lastrowid)
            for unit_index, unit in enumerate(draft.units):
                unit_cursor = self._conn.execute(
                    "INSERT INTO units(subject_id, title, position) VALUES(?, ?, ?)",
                    (subject_id, unit.title.strip(), unit_index),
                )
                unit_id = int(unit_cursor.lastrowid)
                for topic_index, topic in enumerate(unit.topics):
                    self._conn.execute(
                        """
                        INSERT INTO topics(unit_id, title, position, objective, focus)
                        VALUES(?, ?, ?, ?, ?)
                        """,
                        (unit_id, topic.title.strip(), topic_index, topic.objective.strip(), topic.focus),
                    )
            return subject_id

    def list_subjects(self, today: date | None = None) -> list[Subject]:
        today = today or date.today()
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM subjects ORDER BY created_at DESC, id DESC"
            ).fetchall()
        subjects = [self._subject(row) for row in rows]
        for subject in subjects:
            topics = self.topics_for_subject(subject.id)
            subject.topic_count = len(topics)
            subject.avg_mastery = (
                round(sum(topic.mastery for topic in topics) / len(topics), 1) if topics else 0.0
            )
            subject.weak_count = sum(
                1 for topic in topics if needs_revision(topic.review_state(), today)
            )
        return subjects

    def get_subject(self, subject_id: int) -> Subject | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,)).fetchone()
        return None if row is None else self._subject(row)

    def delete_subject(self, subject_id: int) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))

    def units_for_subject(self, subject_id: int) -> list[Unit]:
        with self._lock:
            unit_rows = self._conn.execute(
                "SELECT * FROM units WHERE subject_id = ? ORDER BY position, id",
                (subject_id,),
            ).fetchall()
            topic_rows = self._conn.execute(
                """
                SELECT topics.*, units.title AS unit_title
                FROM topics
                JOIN units ON units.id = topics.unit_id
                WHERE units.subject_id = ?
                ORDER BY units.position, topics.position, topics.id
                """,
                (subject_id,),
            ).fetchall()
        grouped: dict[int, list[Topic]] = {}
        for row in topic_rows:
            grouped.setdefault(int(row["unit_id"]), []).append(self._topic(row))
        return [
            Unit(
                id=int(row["id"]),
                subject_id=int(row["subject_id"]),
                title=str(row["title"]),
                position=int(row["position"]),
                topics=grouped.get(int(row["id"]), []),
            )
            for row in unit_rows
        ]

    def topics_for_subject(self, subject_id: int) -> list[Topic]:
        return [topic for unit in self.units_for_subject(subject_id) for topic in unit.topics]

    def get_topic(self, topic_id: int) -> Topic | None:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT topics.*, units.title AS unit_title
                FROM topics JOIN units ON units.id = topics.unit_id
                WHERE topics.id = ?
                """,
                (topic_id,),
            ).fetchone()
        return None if row is None else self._topic(row)

    def outline_pairs(self, subject_id: int) -> list[tuple[str, list[str]]]:
        return [
            (unit.title, [topic.title for topic in unit.topics])
            for unit in self.units_for_subject(subject_id)
        ]

    def next_new_topic(self, subject_id: int) -> Topic | None:
        for topic in self.topics_for_subject(subject_id):
            if topic.last_reviewed is None:
                return topic
        return None

    def weak_topics(self, subject_id: int, today: date | None = None) -> list[Topic]:
        today = today or date.today()
        weak = [
            topic
            for topic in self.topics_for_subject(subject_id)
            if needs_revision(topic.review_state(), today)
        ]
        weak.sort(key=lambda topic: (topic.mastery, topic.next_review or ""))
        return weak

    def save_review(self, topic_id: int, state: ReviewState) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE topics
                SET mastery = ?, ease = ?, interval_days = ?, repetitions = ?, lapses = ?,
                    last_reviewed = ?, next_review = ?, status = ?
                WHERE id = ?
                """,
                (
                    state.mastery,
                    state.ease,
                    state.interval_days,
                    state.repetitions,
                    state.lapses,
                    state.last_reviewed,
                    state.next_review,
                    state.status,
                    topic_id,
                ),
            )

    def add_message(
        self,
        subject_id: int,
        topic_id: int | None,
        mode: str,
        role: str,
        content: str,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO messages(subject_id, topic_id, mode, role, content, created_at)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (subject_id, topic_id, mode, role, content[:20000], _now()),
            )

    def list_messages(self, topic_id: int) -> list[Message]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM messages WHERE topic_id = ? ORDER BY id",
                (topic_id,),
            ).fetchall()
        return [
            Message(
                id=int(row["id"]),
                role=str(row["role"]),
                mode=str(row["mode"]),
                content=str(row["content"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def add_attempt(
        self,
        topic_id: int,
        kind: str,
        score: int,
        total: int,
        percent: int,
        weak_points: list[str],
        feedback: str,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO quiz_attempts(
                    topic_id, kind, score, total, percent, weak_points, feedback, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    topic_id,
                    kind,
                    score,
                    total,
                    percent,
                    "\n".join(weak_points)[:4000],
                    feedback[:8000],
                    _now(),
                ),
            )

    def recent_weak_points(self, topic_id: int, limit: int = 3) -> str:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT weak_points FROM quiz_attempts
                WHERE topic_id = ? AND weak_points != ''
                ORDER BY id DESC LIMIT ?
                """,
                (topic_id, limit),
            ).fetchall()
        notes = [str(row["weak_points"]) for row in rows]
        return "\n".join(reversed(notes))

    def add_material(self, subject_id: int, title: str, kind: str, content: str) -> int:
        with self._lock, self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO materials(subject_id, title, kind, content, created_at)
                VALUES(?, ?, ?, ?, ?)
                """,
                (subject_id, title.strip()[:160], kind, content[:200000], _now()),
            )
            return int(cursor.lastrowid)

    def list_materials(self, subject_id: int) -> list[StoredMaterial]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM materials WHERE subject_id = ? ORDER BY id",
                (subject_id,),
            ).fetchall()
        return [
            StoredMaterial(
                id=int(row["id"]),
                title=str(row["title"]),
                kind=str(row["kind"]),
                content=str(row["content"]),
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def delete_material(self, material_id: int) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM materials WHERE id = ?", (material_id,))

    def _subject(self, row: sqlite3.Row) -> Subject:
        return Subject(
            id=int(row["id"]),
            name=str(row["name"]),
            kind=str(row["kind"]),
            syllabus_text=str(row["syllabus_text"]),
            created_at=str(row["created_at"]),
        )

    def _topic(self, row: sqlite3.Row) -> Topic:
        return Topic(
            id=int(row["id"]),
            unit_id=int(row["unit_id"]),
            unit_title=str(row["unit_title"]),
            title=str(row["title"]),
            position=int(row["position"]),
            objective=str(row["objective"]),
            focus=str(row["focus"]),
            mastery=float(row["mastery"]),
            ease=float(row["ease"]),
            interval_days=int(row["interval_days"]),
            repetitions=int(row["repetitions"]),
            lapses=int(row["lapses"]),
            last_reviewed=row["last_reviewed"],
            next_review=row["next_review"],
            status=str(row["status"]),
        )
