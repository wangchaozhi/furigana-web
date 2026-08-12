from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Iterable

from .models import AnnotatedLine, OverrideCreate, OverrideItem, ProjectCreate, ProjectItem, ProjectSummary

_DB_PATH = Path(os.getenv("DB_PATH", "/data/furigana.sqlite3"))
_LOCK = threading.RLock()


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with _LOCK, _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS ruby_overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                surface TEXT NOT NULL,
                context TEXT NOT NULL DEFAULT '',
                reading TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(surface, context)
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '',
                artist TEXT NOT NULL DEFAULT '',
                year TEXT NOT NULL DEFAULT '',
                source_text TEXT NOT NULL,
                lines_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )


def list_overrides() -> list[OverrideItem]:
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            "SELECT id, surface, context, reading, created_at FROM ruby_overrides ORDER BY surface, length(context) DESC"
        ).fetchall()
    return [OverrideItem(**dict(r)) for r in rows]


def upsert_override(item: OverrideCreate) -> OverrideItem:
    with _LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO ruby_overrides(surface, context, reading)
            VALUES (?, ?, ?)
            ON CONFLICT(surface, context) DO UPDATE SET reading=excluded.reading
            """,
            (item.surface, item.context, item.reading),
        )
        row = conn.execute(
            "SELECT id, surface, context, reading, created_at FROM ruby_overrides WHERE surface=? AND context=?",
            (item.surface, item.context),
        ).fetchone()
    return OverrideItem(**dict(row))


def delete_override(override_id: int) -> bool:
    with _LOCK, _connect() as conn:
        cur = conn.execute("DELETE FROM ruby_overrides WHERE id=?", (override_id,))
        return cur.rowcount > 0


def save_project(item: ProjectCreate) -> ProjectItem:
    payload = json.dumps([line.model_dump() for line in item.lines], ensure_ascii=False)
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO projects(title, artist, year, source_text, lines_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (item.title, item.artist, item.year, item.source_text, payload),
        )
        project_id = int(cur.lastrowid)
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    return _row_to_project(row)


def list_projects() -> list[ProjectSummary]:
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            "SELECT id, title, artist, year, created_at, updated_at FROM projects ORDER BY updated_at DESC, id DESC"
        ).fetchall()
    return [ProjectSummary(**dict(r)) for r in rows]


def get_project(project_id: int) -> ProjectItem | None:
    with _LOCK, _connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    return _row_to_project(row) if row else None


def delete_project(project_id: int) -> bool:
    with _LOCK, _connect() as conn:
        cur = conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
        return cur.rowcount > 0


def _row_to_project(row: sqlite3.Row) -> ProjectItem:
    data = dict(row)
    lines_raw = json.loads(data.pop("lines_json"))
    data["lines"] = [AnnotatedLine(**line) for line in lines_raw]
    return ProjectItem(**data)
