from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Iterable

from .models import AnnotatedLine, LayoutSettings, OverrideCreate, OverrideItem, OverrideUpdate, ProjectCreate, ProjectItem, ProjectSummary

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
        project_columns = {row[1] for row in conn.execute("PRAGMA table_info(projects)")}
        if "layout_json" not in project_columns:
            conn.execute("ALTER TABLE projects ADD COLUMN layout_json TEXT NOT NULL DEFAULT '{}'")
        if "translation_language" not in project_columns:
            conn.execute("ALTER TABLE projects ADD COLUMN translation_language TEXT NOT NULL DEFAULT 'none'")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(ruby_overrides)")}
        if columns and "scope" not in columns:
            conn.execute("ALTER TABLE ruby_overrides RENAME TO ruby_overrides_legacy")
            _create_override_table(conn)
            conn.execute(
                """
                INSERT INTO ruby_overrides(id, surface, context, reading, scope, project_id, created_at)
                SELECT id, surface, context, reading,
                       CASE WHEN context = '' THEN 'global' ELSE 'sentence' END,
                       NULL, created_at
                FROM ruby_overrides_legacy
                """
            )
            conn.execute("DROP TABLE ruby_overrides_legacy")
        elif not columns:
            _create_override_table(conn)


def _create_override_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE ruby_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            surface TEXT NOT NULL,
            context TEXT NOT NULL DEFAULT '',
            reading TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT 'sentence'
                CHECK(scope IN ('sentence', 'project', 'global')),
            project_id INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE UNIQUE INDEX ruby_overrides_identity
            ON ruby_overrides(surface, scope, COALESCE(project_id, -1), context);
        """
    )


def list_overrides() -> list[OverrideItem]:
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            """SELECT id, surface, context, reading, scope, project_id, created_at
               FROM ruby_overrides
               ORDER BY surface,
                 CASE scope WHEN 'sentence' THEN 1 WHEN 'project' THEN 2 ELSE 3 END,
                 length(context) DESC"""
        ).fetchall()
    return [OverrideItem(**dict(r)) for r in rows]


def list_applicable_overrides(project_id: int | None) -> list[OverrideItem]:
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            """SELECT id, surface, context, reading, scope, project_id, created_at
               FROM ruby_overrides
               WHERE scope IN ('sentence', 'global')
                  OR (scope = 'project' AND project_id = ?)
               ORDER BY CASE scope WHEN 'sentence' THEN 1 WHEN 'project' THEN 2 ELSE 3 END,
                        length(context) DESC""",
            (project_id,),
        ).fetchall()
    return [OverrideItem(**dict(r)) for r in rows]


def upsert_override(item: OverrideCreate) -> OverrideItem:
    context = item.context if item.scope == "sentence" else ""
    project_id = item.project_id if item.scope == "project" else None
    if item.scope == "project" and project_id is None:
        raise ValueError("Project rules require a project_id")
    with _LOCK, _connect() as conn:
        conn.execute(
            """
            INSERT INTO ruby_overrides(surface, context, reading, scope, project_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT DO UPDATE SET reading=excluded.reading
            """,
            (item.surface, context, item.reading, item.scope, project_id),
        )
        row = conn.execute(
            """SELECT id, surface, context, reading, scope, project_id, created_at
               FROM ruby_overrides
               WHERE surface=? AND scope=? AND COALESCE(project_id, -1)=COALESCE(?, -1) AND context=?""",
            (item.surface, item.scope, project_id, context),
        ).fetchone()
    return OverrideItem(**dict(row))


def delete_override(override_id: int) -> bool:
    with _LOCK, _connect() as conn:
        cur = conn.execute("DELETE FROM ruby_overrides WHERE id=?", (override_id,))
        return cur.rowcount > 0


def update_override(override_id: int, item: OverrideUpdate) -> OverrideItem | None:
    context = item.context if item.scope == "sentence" else ""
    project_id = item.project_id if item.scope == "project" else None
    if item.scope == "project" and project_id is None:
        raise ValueError("Project rules require a project_id")
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            "UPDATE ruby_overrides SET surface=?, context=?, reading=?, scope=?, project_id=? WHERE id=?",
            (item.surface, context, item.reading, item.scope, project_id, override_id),
        )
        if cur.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT id, surface, context, reading, scope, project_id, created_at FROM ruby_overrides WHERE id=?",
            (override_id,),
        ).fetchone()
    return OverrideItem(**dict(row))


def save_project(item: ProjectCreate) -> ProjectItem:
    payload = json.dumps([line.model_dump() for line in item.lines], ensure_ascii=False)
    layout = item.layout.model_dump_json()
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO projects(title, artist, year, source_text, layout_json, translation_language, lines_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (item.title, item.artist, item.year, item.source_text, layout, item.translation_language, payload),
        )
        project_id = int(cur.lastrowid)
        row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    return _row_to_project(row)


def update_project(project_id: int, item: ProjectCreate) -> ProjectItem | None:
    payload = json.dumps([line.model_dump() for line in item.lines], ensure_ascii=False)
    layout = item.layout.model_dump_json()
    with _LOCK, _connect() as conn:
        cur = conn.execute(
            """UPDATE projects
               SET title=?, artist=?, year=?, source_text=?, layout_json=?, translation_language=?, lines_json=?, updated_at=datetime('now')
               WHERE id=?""",
            (item.title, item.artist, item.year, item.source_text, layout, item.translation_language, payload, project_id),
        )
        if cur.rowcount == 0:
            return None
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
        if cur.rowcount:
            conn.execute("DELETE FROM ruby_overrides WHERE scope='project' AND project_id=?", (project_id,))
        return cur.rowcount > 0


def _row_to_project(row: sqlite3.Row) -> ProjectItem:
    data = dict(row)
    lines_raw = json.loads(data.pop("lines_json"))
    data["layout"] = LayoutSettings.model_validate_json(data.pop("layout_json", "{}") or "{}")
    data["lines"] = [AnnotatedLine(**line) for line in lines_raw]
    return ProjectItem(**data)
