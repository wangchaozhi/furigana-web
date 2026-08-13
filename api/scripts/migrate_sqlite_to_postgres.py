from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import db_postgres  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Import one local SQLite workspace into a Vercel PostgreSQL user account.")
    parser.add_argument("sqlite", type=Path, help="Path to furigana.sqlite3")
    parser.add_argument("--user-id", required=True, help="Supabase auth user UUID")
    parser.add_argument("--email", default="", help="Supabase account email")
    args = parser.parse_args()
    if not os.getenv("DATABASE_URL"):
        parser.error("DATABASE_URL must point to the target PostgreSQL database")

    db_postgres.init_db()
    db_postgres.ensure_user(args.user_id, args.email)
    source = sqlite3.connect(args.sqlite)
    source.row_factory = sqlite3.Row
    project_map: dict[int, int] = {}

    with psycopg.connect(os.environ["DATABASE_URL"]) as target, target.cursor() as cursor:
        for row in source.execute("SELECT * FROM projects ORDER BY id"):
            values = dict(row)
            cursor.execute(
                """INSERT INTO projects(user_id, title, artist, year, source_text, layout_json,
                   translation_language, lines_json, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s) RETURNING id""",
                (
                    args.user_id,
                    values.get("title", ""), values.get("artist", ""), values.get("year", ""),
                    values["source_text"], values.get("layout_json") or "{}",
                    values.get("translation_language") or "none", values["lines_json"],
                    values["created_at"], values["updated_at"],
                ),
            )
            project_map[int(values["id"])] = int(cursor.fetchone()[0])

        for row in source.execute("SELECT * FROM ruby_overrides ORDER BY id"):
            values = dict(row)
            scope = values.get("scope") or ("global" if not values.get("context") else "sentence")
            project_id = project_map.get(values.get("project_id")) if scope == "project" else None
            if scope == "project" and project_id is None:
                continue
            cursor.execute(
                """INSERT INTO ruby_overrides(user_id, surface, context, reading, scope, project_id, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (user_id, surface, scope, (COALESCE(project_id, -1)), context)
                   DO UPDATE SET reading=EXCLUDED.reading""",
                (args.user_id, values["surface"], values.get("context", ""), values["reading"], scope, project_id, values["created_at"]),
            )

    source.close()
    print(json.dumps({"projects": len(project_map), "target_user": args.user_id}, ensure_ascii=False))


if __name__ == "__main__":
    main()
