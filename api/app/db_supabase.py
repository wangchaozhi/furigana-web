from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import AnnotatedLine, LayoutSettings, OverrideCreate, OverrideItem, OverrideUpdate, ProjectCreate, ProjectItem, ProjectSummary


def _request_headers(secret_key: str, prefer: str) -> dict[str, str]:
    headers = {
        "apikey": secret_key,
        "Content-Type": "application/json",
        "Prefer": prefer,
    }
    # New sb_secret_* keys are API keys, not JWTs, and Supabase rejects them
    # when sent as a Bearer token. Legacy service_role keys are JWT-shaped and
    # still require the Authorization header for backward compatibility.
    if len(secret_key.split(".")) == 3:
        headers["Authorization"] = f"Bearer {secret_key}"
    return headers


def _request(
    method: str,
    table: str,
    *,
    params: dict[str, str] | None = None,
    body: Any = None,
    prefer: str = "return=representation",
) -> list[dict]:
    base_url = os.environ["SUPABASE_URL"].rstrip("/")
    secret_key = os.environ["SUPABASE_SECRET_KEY"]
    query = f"?{urlencode(params)}" if params else ""
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = Request(
        f"{base_url}/rest/v1/{table}{query}",
        data=data,
        method=method,
        headers=_request_headers(secret_key, prefer),
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = response.read()
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Supabase Data API returned {error.code}: {detail}") from error
    return json.loads(payload) if payload else []


def init_db() -> None:
    """Schema changes are applied through versioned Supabase migrations."""


def ensure_user(user_id: str, email: str = "") -> None:
    _request(
        "POST",
        "app_users",
        params={"on_conflict": "id"},
        body={"id": user_id, "email": email, "updated_at": _now()},
        prefer="resolution=merge-duplicates,return=minimal",
    )


def list_overrides(user_id: str = "local") -> list[OverrideItem]:
    rows = _request("GET", "ruby_overrides", params={"user_id": f"eq.{user_id}", "select": "id,surface,context,reading,scope,project_id,created_at"})
    rows.sort(key=lambda row: (row["surface"], _scope_order(row["scope"]), -len(row.get("context") or "")))
    return [OverrideItem(**row) for row in rows]


def list_applicable_overrides(project_id: int | None, user_id: str = "local") -> list[OverrideItem]:
    rows = _request("GET", "ruby_overrides", params={"user_id": f"eq.{user_id}", "select": "id,surface,context,reading,scope,project_id,created_at"})
    rows = [row for row in rows if row["scope"] in {"sentence", "global"} or (row["scope"] == "project" and row["project_id"] == project_id)]
    rows.sort(key=lambda row: (_scope_order(row["scope"]), -len(row.get("context") or "")))
    return [OverrideItem(**row) for row in rows]


def upsert_override(item: OverrideCreate, user_id: str = "local") -> OverrideItem:
    context = item.context if item.scope == "sentence" else ""
    project_id = item.project_id if item.scope == "project" else None
    if project_id is not None and not _project_exists(project_id, user_id):
        raise ValueError("Project not found")
    filters = _override_filters(user_id, item.surface, item.scope, context, project_id)
    existing = _request("GET", "ruby_overrides", params={**filters, "select": "id"})
    values = {"user_id": user_id, "surface": item.surface, "context": context, "reading": item.reading, "scope": item.scope, "project_id": project_id}
    if existing:
        rows = _request("PATCH", "ruby_overrides", params={"id": f"eq.{existing[0]['id']}"}, body={"reading": item.reading})
    else:
        rows = _request("POST", "ruby_overrides", body=values)
    return OverrideItem(**rows[0])


def delete_override(override_id: int, user_id: str = "local") -> bool:
    rows = _request("DELETE", "ruby_overrides", params={"id": f"eq.{override_id}", "user_id": f"eq.{user_id}"})
    return bool(rows)


def update_override(override_id: int, item: OverrideUpdate, user_id: str = "local") -> OverrideItem | None:
    context = item.context if item.scope == "sentence" else ""
    project_id = item.project_id if item.scope == "project" else None
    if project_id is not None and not _project_exists(project_id, user_id):
        raise ValueError("Project not found")
    rows = _request(
        "PATCH",
        "ruby_overrides",
        params={"id": f"eq.{override_id}", "user_id": f"eq.{user_id}"},
        body={"surface": item.surface, "context": context, "reading": item.reading, "scope": item.scope, "project_id": project_id},
    )
    return OverrideItem(**rows[0]) if rows else None


def save_project(item: ProjectCreate, user_id: str = "local") -> ProjectItem:
    rows = _request("POST", "projects", body=_project_values(item, user_id))
    return _row_to_project(rows[0])


def update_project(project_id: int, item: ProjectCreate, user_id: str = "local") -> ProjectItem | None:
    values = _project_values(item, user_id)
    values.pop("user_id")
    values["updated_at"] = _now()
    rows = _request("PATCH", "projects", params={"id": f"eq.{project_id}", "user_id": f"eq.{user_id}"}, body=values)
    return _row_to_project(rows[0]) if rows else None


def list_projects(user_id: str = "local") -> list[ProjectSummary]:
    rows = _request(
        "GET",
        "projects",
        params={"user_id": f"eq.{user_id}", "select": "id,title,artist,year,created_at,updated_at", "order": "updated_at.desc,id.desc"},
    )
    return [ProjectSummary(**row) for row in rows]


def get_project(project_id: int, user_id: str = "local") -> ProjectItem | None:
    rows = _request("GET", "projects", params={"id": f"eq.{project_id}", "user_id": f"eq.{user_id}", "select": "*"})
    return _row_to_project(rows[0]) if rows else None


def delete_project(project_id: int, user_id: str = "local") -> bool:
    rows = _request("DELETE", "projects", params={"id": f"eq.{project_id}", "user_id": f"eq.{user_id}"})
    return bool(rows)


def _project_exists(project_id: int, user_id: str) -> bool:
    return bool(_request("GET", "projects", params={"id": f"eq.{project_id}", "user_id": f"eq.{user_id}", "select": "id"}))


def _override_filters(user_id: str, surface: str, scope: str, context: str, project_id: int | None) -> dict[str, str]:
    return {
        "user_id": f"eq.{user_id}",
        "surface": f"eq.{surface}",
        "scope": f"eq.{scope}",
        "context": f"eq.{context}",
        "project_id": "is.null" if project_id is None else f"eq.{project_id}",
    }


def _project_values(item: ProjectCreate, user_id: str) -> dict:
    return {
        "user_id": user_id,
        "title": item.title,
        "artist": item.artist,
        "year": item.year,
        "source_text": item.source_text,
        "layout_json": item.layout.model_dump(),
        "translation_language": item.translation_language,
        "lines_json": [line.model_dump() for line in item.lines],
    }


def _row_to_project(row: dict) -> ProjectItem:
    data = dict(row)
    data.pop("user_id", None)
    lines_raw = data.pop("lines_json")
    layout_raw = data.pop("layout_json", {}) or {}
    data["layout"] = LayoutSettings.model_validate(layout_raw)
    data["lines"] = [AnnotatedLine(**line) for line in lines_raw]
    return ProjectItem(**data)


def _scope_order(scope: str) -> int:
    return {"sentence": 1, "project": 2, "global": 3}[scope]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
