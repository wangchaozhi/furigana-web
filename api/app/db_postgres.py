from __future__ import annotations

import json
import os
from datetime import date, datetime

import psycopg
from psycopg.rows import dict_row

from .models import AnnotatedLine, LayoutSettings, OverrideCreate, OverrideItem, OverrideUpdate, ProjectCreate, ProjectItem, ProjectSummary


def _connect() -> psycopg.Connection:
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row, prepare_threshold=None)


def _serialized(row: dict) -> dict:
    return {key: value.isoformat() if isinstance(value, (date, datetime)) else value for key, value in row.items()}


def init_db() -> None:
    with _connect() as conn, conn.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS app_users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL DEFAULT '',
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE TABLE IF NOT EXISTS projects (
                id BIGSERIAL PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                title TEXT NOT NULL DEFAULT '',
                artist TEXT NOT NULL DEFAULT '',
                year TEXT NOT NULL DEFAULT '',
                source_text TEXT NOT NULL,
                layout_json JSONB NOT NULL DEFAULT '{}'::jsonb,
                translation_language TEXT NOT NULL DEFAULT 'none',
                lines_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS projects_user_updated ON projects(user_id, updated_at DESC);
            CREATE TABLE IF NOT EXISTS ruby_overrides (
                id BIGSERIAL PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                surface TEXT NOT NULL,
                context TEXT NOT NULL DEFAULT '',
                reading TEXT NOT NULL,
                scope TEXT NOT NULL DEFAULT 'sentence' CHECK(scope IN ('sentence', 'project', 'global')),
                project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE UNIQUE INDEX IF NOT EXISTS ruby_overrides_identity
                ON ruby_overrides(user_id, surface, scope, COALESCE(project_id, -1), context);
            CREATE INDEX IF NOT EXISTS ruby_overrides_project_id ON ruby_overrides(project_id);
            ALTER TABLE app_users ENABLE ROW LEVEL SECURITY;
            ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
            ALTER TABLE ruby_overrides ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS deny_direct_client_access ON app_users;
            DROP POLICY IF EXISTS deny_direct_client_access ON projects;
            DROP POLICY IF EXISTS deny_direct_client_access ON ruby_overrides;
            CREATE POLICY deny_direct_client_access ON app_users
                FOR ALL TO anon, authenticated USING (false) WITH CHECK (false);
            CREATE POLICY deny_direct_client_access ON projects
                FOR ALL TO anon, authenticated USING (false) WITH CHECK (false);
            CREATE POLICY deny_direct_client_access ON ruby_overrides
                FOR ALL TO anon, authenticated USING (false) WITH CHECK (false);
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    REVOKE ALL ON TABLE app_users, projects, ruby_overrides FROM anon;
                    REVOKE ALL ON SEQUENCE projects_id_seq, ruby_overrides_id_seq FROM anon;
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    REVOKE ALL ON TABLE app_users, projects, ruby_overrides FROM authenticated;
                    REVOKE ALL ON SEQUENCE projects_id_seq, ruby_overrides_id_seq FROM authenticated;
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
                    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE app_users, projects, ruby_overrides TO service_role;
                    GRANT USAGE, SELECT ON SEQUENCE projects_id_seq, ruby_overrides_id_seq TO service_role;
                END IF;
            END
            $$;
            """
        )


def ensure_user(user_id: str, email: str = "") -> None:
    with _connect() as conn, conn.cursor() as cursor:
        cursor.execute(
            """INSERT INTO app_users(id, email) VALUES (%s, %s)
               ON CONFLICT (id) DO UPDATE SET email=EXCLUDED.email, updated_at=now()
               WHERE app_users.email IS DISTINCT FROM EXCLUDED.email""",
            (user_id, email),
        )


def list_overrides(user_id: str = "local") -> list[OverrideItem]:
    with _connect() as conn, conn.cursor() as cursor:
        cursor.execute(
            """SELECT id, surface, context, reading, scope, project_id, created_at
               FROM ruby_overrides WHERE user_id=%s
               ORDER BY surface, CASE scope WHEN 'sentence' THEN 1 WHEN 'project' THEN 2 ELSE 3 END, length(context) DESC""",
            (user_id,),
        )
        rows = cursor.fetchall()
    return [OverrideItem(**_serialized(row)) for row in rows]


def list_applicable_overrides(project_id: int | None, user_id: str = "local") -> list[OverrideItem]:
    with _connect() as conn, conn.cursor() as cursor:
        cursor.execute(
            """SELECT id, surface, context, reading, scope, project_id, created_at
               FROM ruby_overrides
               WHERE user_id=%s AND (scope IN ('sentence', 'global') OR (scope='project' AND project_id=%s))
               ORDER BY CASE scope WHEN 'sentence' THEN 1 WHEN 'project' THEN 2 ELSE 3 END, length(context) DESC""",
            (user_id, project_id),
        )
        rows = cursor.fetchall()
    return [OverrideItem(**_serialized(row)) for row in rows]


def upsert_override(item: OverrideCreate, user_id: str = "local") -> OverrideItem:
    context = item.context if item.scope == "sentence" else ""
    project_id = item.project_id if item.scope == "project" else None
    with _connect() as conn, conn.cursor() as cursor:
        if project_id is not None:
            cursor.execute("SELECT 1 FROM projects WHERE id=%s AND user_id=%s", (project_id, user_id))
            if cursor.fetchone() is None:
                raise ValueError("Project not found")
        cursor.execute(
            """INSERT INTO ruby_overrides(user_id, surface, context, reading, scope, project_id)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON CONFLICT (user_id, surface, scope, (COALESCE(project_id, -1)), context)
               DO UPDATE SET reading=EXCLUDED.reading
               RETURNING id, surface, context, reading, scope, project_id, created_at""",
            (user_id, item.surface, context, item.reading, item.scope, project_id),
        )
        row = cursor.fetchone()
    return OverrideItem(**_serialized(row))


def delete_override(override_id: int, user_id: str = "local") -> bool:
    with _connect() as conn, conn.cursor() as cursor:
        cursor.execute("DELETE FROM ruby_overrides WHERE id=%s AND user_id=%s", (override_id, user_id))
        return cursor.rowcount > 0


def update_override(override_id: int, item: OverrideUpdate, user_id: str = "local") -> OverrideItem | None:
    context = item.context if item.scope == "sentence" else ""
    project_id = item.project_id if item.scope == "project" else None
    with _connect() as conn, conn.cursor() as cursor:
        if project_id is not None:
            cursor.execute("SELECT 1 FROM projects WHERE id=%s AND user_id=%s", (project_id, user_id))
            if cursor.fetchone() is None:
                raise ValueError("Project not found")
        cursor.execute(
            """UPDATE ruby_overrides SET surface=%s, context=%s, reading=%s, scope=%s, project_id=%s
               WHERE id=%s AND user_id=%s
               RETURNING id, surface, context, reading, scope, project_id, created_at""",
            (item.surface, context, item.reading, item.scope, project_id, override_id, user_id),
        )
        row = cursor.fetchone()
    return OverrideItem(**_serialized(row)) if row else None


def save_project(item: ProjectCreate, user_id: str = "local") -> ProjectItem:
    with _connect() as conn, conn.cursor() as cursor:
        cursor.execute(
            """INSERT INTO projects(user_id, title, artist, year, source_text, layout_json, translation_language, lines_json)
               VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb) RETURNING *""",
            (user_id, item.title, item.artist, item.year, item.source_text, item.layout.model_dump_json(), item.translation_language,
             json.dumps([line.model_dump() for line in item.lines], ensure_ascii=False)),
        )
        row = cursor.fetchone()
    return _row_to_project(row)


def update_project(project_id: int, item: ProjectCreate, user_id: str = "local") -> ProjectItem | None:
    with _connect() as conn, conn.cursor() as cursor:
        cursor.execute(
            """UPDATE projects SET title=%s, artist=%s, year=%s, source_text=%s, layout_json=%s::jsonb,
               translation_language=%s, lines_json=%s::jsonb, updated_at=now()
               WHERE id=%s AND user_id=%s RETURNING *""",
            (item.title, item.artist, item.year, item.source_text, item.layout.model_dump_json(), item.translation_language,
             json.dumps([line.model_dump() for line in item.lines], ensure_ascii=False), project_id, user_id),
        )
        row = cursor.fetchone()
    return _row_to_project(row) if row else None


def list_projects(user_id: str = "local") -> list[ProjectSummary]:
    with _connect() as conn, conn.cursor() as cursor:
        cursor.execute(
            """SELECT id, title, artist, year, created_at, updated_at FROM projects
               WHERE user_id=%s ORDER BY updated_at DESC, id DESC""",
            (user_id,),
        )
        rows = cursor.fetchall()
    return [ProjectSummary(**_serialized(row)) for row in rows]


def get_project(project_id: int, user_id: str = "local") -> ProjectItem | None:
    with _connect() as conn, conn.cursor() as cursor:
        cursor.execute("SELECT * FROM projects WHERE id=%s AND user_id=%s", (project_id, user_id))
        row = cursor.fetchone()
    return _row_to_project(row) if row else None


def delete_project(project_id: int, user_id: str = "local") -> bool:
    with _connect() as conn, conn.cursor() as cursor:
        cursor.execute("DELETE FROM projects WHERE id=%s AND user_id=%s", (project_id, user_id))
        return cursor.rowcount > 0


def _row_to_project(row: dict) -> ProjectItem:
    data = _serialized(dict(row))
    data.pop("user_id", None)
    lines_raw = data.pop("lines_json")
    layout_raw = data.pop("layout_json", {}) or {}
    if isinstance(lines_raw, str):
        lines_raw = json.loads(lines_raw)
    if isinstance(layout_raw, str):
        layout_raw = json.loads(layout_raw)
    data["layout"] = LayoutSettings.model_validate(layout_raw)
    data["lines"] = [AnnotatedLine(**line) for line in lines_raw]
    return ProjectItem(**data)
