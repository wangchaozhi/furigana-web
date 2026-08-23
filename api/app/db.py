from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path

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
            CREATE TABLE IF NOT EXISTS app_users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            INSERT OR IGNORE INTO app_users(id, email) VALUES ('local', 'local@furigana.invalid');
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL DEFAULT 'local' REFERENCES app_users(id) ON DELETE CASCADE,
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
        if "user_id" not in project_columns:
            conn.execute("ALTER TABLE projects ADD COLUMN user_id TEXT NOT NULL DEFAULT 'local'")
        if "layout_json" not in project_columns:
            conn.execute("ALTER TABLE projects ADD COLUMN layout_json TEXT NOT NULL DEFAULT '{}'")
        if "translation_language" not in project_columns:
            conn.execute("ALTER TABLE projects ADD COLUMN translation_language TEXT NOT NULL DEFAULT 'none'")

        columns = {row[1] for row in conn.execute("PRAGMA table_info(ruby_overrides)")}
        if columns and ("scope" not in columns or "user_id" not in columns):
            conn.execute("DROP INDEX IF EXISTS ruby_overrides_identity")
            conn.execute("ALTER TABLE ruby_overrides RENAME TO ruby_overrides_legacy")
            _create_override_table(conn)
            legacy_columns = {row[1] for row in conn.execute("PRAGMA table_info(ruby_overrides_legacy)")}
            scope_expr = "scope" if "scope" in legacy_columns else "CASE WHEN context = '' THEN 'global' ELSE 'sentence' END"
            project_expr = "project_id" if "project_id" in legacy_columns else "NULL"
            user_expr = "user_id" if "user_id" in legacy_columns else "'local'"
            conn.execute(
                f"""INSERT INTO ruby_overrides(id, user_id, surface, context, reading, scope, project_id, created_at)
                    SELECT id, {user_expr}, surface, context, reading, {scope_expr}, {project_expr}, created_at
                    FROM ruby_overrides_legacy"""
            )
            conn.execute("DROP TABLE ruby_overrides_legacy")
        elif not columns:
            _create_override_table(conn)
        conn.execute("CREATE INDEX IF NOT EXISTS projects_user_updated ON projects(user_id, updated_at DESC)")


def _create_override_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE ruby_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL DEFAULT 'local' REFERENCES app_users(id) ON DELETE CASCADE,
            surface TEXT NOT NULL,
            context TEXT NOT NULL DEFAULT '',
            reading TEXT NOT NULL,
            scope TEXT NOT NULL DEFAULT 'sentence' CHECK(scope IN ('sentence', 'project', 'global')),
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE UNIQUE INDEX ruby_overrides_identity
            ON ruby_overrides(user_id, surface, scope, COALESCE(project_id, -1), context);
        """
    )


def ensure_user(user_id: str, email: str = "") -> None:
    with _LOCK, _connect() as conn:
        conn.execute(
            """INSERT INTO app_users(id, email) VALUES (?, ?)
               ON CONFLICT(id) DO UPDATE SET email=excluded.email, updated_at=datetime('now')
               WHERE app_users.email IS NOT excluded.email""",
            (user_id, email),
        )


def list_overrides(user_id: str = "local") -> list[OverrideItem]:
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            """SELECT id, surface, context, reading, scope, project_id, created_at FROM ruby_overrides
               WHERE user_id=? ORDER BY surface,
               CASE scope WHEN 'sentence' THEN 1 WHEN 'project' THEN 2 ELSE 3 END, length(context) DESC""",
            (user_id,),
        ).fetchall()
    return [OverrideItem(**dict(row)) for row in rows]


def list_applicable_overrides(project_id: int | None, user_id: str = "local") -> list[OverrideItem]:
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            """SELECT id, surface, context, reading, scope, project_id, created_at FROM ruby_overrides
               WHERE user_id=? AND (scope IN ('sentence', 'global') OR (scope='project' AND project_id=?))
               ORDER BY CASE scope WHEN 'sentence' THEN 1 WHEN 'project' THEN 2 ELSE 3 END, length(context) DESC""",
            (user_id, project_id),
        ).fetchall()
    return [OverrideItem(**dict(row)) for row in rows]


def _validate_project(conn: sqlite3.Connection, project_id: int | None, user_id: str) -> None:
    if project_id is None:
        raise ValueError("Project rules require a project_id")
    if conn.execute("SELECT 1 FROM projects WHERE id=? AND user_id=?", (project_id, user_id)).fetchone() is None:
        raise ValueError("Project not found")


def upsert_override(item: OverrideCreate, user_id: str = "local") -> OverrideItem:
    context = item.context if item.scope == "sentence" else ""
    project_id = item.project_id if item.scope == "project" else None
    with _LOCK, _connect() as conn:
        if item.scope == "project":
            _validate_project(conn, project_id, user_id)
        conn.execute(
            """INSERT INTO ruby_overrides(user_id, surface, context, reading, scope, project_id)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT DO UPDATE SET reading=excluded.reading""",
            (user_id, item.surface, context, item.reading, item.scope, project_id),
        )
        row = conn.execute(
            """SELECT id, surface, context, reading, scope, project_id, created_at FROM ruby_overrides
               WHERE user_id=? AND surface=? AND scope=? AND COALESCE(project_id, -1)=COALESCE(?, -1) AND context=?""",
            (user_id, item.surface, item.scope, project_id, context),
        ).fetchone()
    return OverrideItem(**dict(row))


def delete_override(override_id: int, user_id: str = "local") -> bool:
    with _LOCK, _connect() as conn:
        cursor = conn.execute("DELETE FROM ruby_overrides WHERE id=? AND user_id=?", (override_id, user_id))
        return cursor.rowcount > 0


def update_override(override_id: int, item: OverrideUpdate, user_id: str = "local") -> OverrideItem | None:
    context = item.context if item.scope == "sentence" else ""
    project_id = item.project_id if item.scope == "project" else None
    with _LOCK, _connect() as conn:
        if item.scope == "project":
            _validate_project(conn, project_id, user_id)
        cursor = conn.execute(
            """UPDATE ruby_overrides SET surface=?, context=?, reading=?, scope=?, project_id=?
               WHERE id=? AND user_id=?""",
            (item.surface, context, item.reading, item.scope, project_id, override_id, user_id),
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute(
            "SELECT id, surface, context, reading, scope, project_id, created_at FROM ruby_overrides WHERE id=? AND user_id=?",
            (override_id, user_id),
        ).fetchone()
    return OverrideItem(**dict(row))


def save_project(item: ProjectCreate, user_id: str = "local") -> ProjectItem:
    payload = json.dumps([line.model_dump() for line in item.lines], ensure_ascii=False)
    with _LOCK, _connect() as conn:
        cursor = conn.execute(
            """INSERT INTO projects(user_id, title, artist, year, source_text, layout_json, translation_language, lines_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, item.title, item.artist, item.year, item.source_text, item.layout.model_dump_json(), item.translation_language, payload),
        )
        row = conn.execute("SELECT * FROM projects WHERE id=? AND user_id=?", (int(cursor.lastrowid), user_id)).fetchone()
    return _row_to_project(row)


def update_project(project_id: int, item: ProjectCreate, user_id: str = "local") -> ProjectItem | None:
    payload = json.dumps([line.model_dump() for line in item.lines], ensure_ascii=False)
    with _LOCK, _connect() as conn:
        cursor = conn.execute(
            """UPDATE projects SET title=?, artist=?, year=?, source_text=?, layout_json=?, translation_language=?,
               lines_json=?, updated_at=datetime('now') WHERE id=? AND user_id=?""",
            (item.title, item.artist, item.year, item.source_text, item.layout.model_dump_json(), item.translation_language,
             payload, project_id, user_id),
        )
        if cursor.rowcount == 0:
            return None
        row = conn.execute("SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, user_id)).fetchone()
    return _row_to_project(row)


def list_projects(user_id: str = "local") -> list[ProjectSummary]:
    with _LOCK, _connect() as conn:
        rows = conn.execute(
            """SELECT id, title, artist, year, created_at, updated_at FROM projects
               WHERE user_id=? ORDER BY updated_at DESC, id DESC""",
            (user_id,),
        ).fetchall()
    return [ProjectSummary(**dict(row)) for row in rows]


def get_project(project_id: int, user_id: str = "local") -> ProjectItem | None:
    with _LOCK, _connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id=? AND user_id=?", (project_id, user_id)).fetchone()
    return _row_to_project(row) if row else None


def delete_project(project_id: int, user_id: str = "local") -> bool:
    with _LOCK, _connect() as conn:
        cursor = conn.execute("DELETE FROM projects WHERE id=? AND user_id=?", (project_id, user_id))
        return cursor.rowcount > 0


def _row_to_project(row: sqlite3.Row) -> ProjectItem:
    data = dict(row)
    data.pop("user_id", None)
    lines_raw = json.loads(data.pop("lines_json"))
    data["layout"] = LayoutSettings.model_validate_json(data.pop("layout_json", "{}") or "{}")
    data["lines"] = [AnnotatedLine(**line) for line in lines_raw]
    return ProjectItem(**data)
