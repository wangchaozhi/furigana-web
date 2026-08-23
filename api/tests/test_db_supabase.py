from app import db_supabase
from app.models import AnnotatedLine, OverrideCreate, ProjectCreate, Segment


def test_new_secret_key_is_not_sent_as_bearer_token():
    headers = db_supabase._request_headers("sb_secret_example", "return=representation")

    assert headers["apikey"] == "sb_secret_example"
    assert "Authorization" not in headers


def test_legacy_service_role_jwt_keeps_bearer_header():
    legacy_key = "header.payload.signature"
    headers = db_supabase._request_headers(legacy_key, "return=minimal")

    assert headers["apikey"] == legacy_key
    assert headers["Authorization"] == f"Bearer {legacy_key}"


def test_ensure_user_uses_server_side_upsert(monkeypatch):
    calls = []
    monkeypatch.setattr(db_supabase, "_request", lambda *args, **kwargs: calls.append((args, kwargs)) or [])

    db_supabase.ensure_user("alice", "alice@example.com")

    args, kwargs = calls[0]
    assert args == ("POST", "app_users")
    assert kwargs["params"] == {"on_conflict": "id"}
    assert kwargs["body"]["id"] == "alice"
    assert kwargs["prefer"] == "resolution=merge-duplicates,return=minimal"


def test_applicable_overrides_are_filtered_and_sorted(monkeypatch):
    rows = [
        {"id": 1, "surface": "明日", "context": "", "reading": "あす", "scope": "global", "project_id": None, "created_at": "2026-01-01T00:00:00Z"},
        {"id": 2, "surface": "明日", "context": "でも明日", "reading": "あした", "scope": "sentence", "project_id": None, "created_at": "2026-01-01T00:00:00Z"},
        {"id": 3, "surface": "明日", "context": "", "reading": "みょうにち", "scope": "project", "project_id": 7, "created_at": "2026-01-01T00:00:00Z"},
        {"id": 4, "surface": "明日", "context": "", "reading": "みょうにち", "scope": "project", "project_id": 8, "created_at": "2026-01-01T00:00:00Z"},
    ]
    monkeypatch.setattr(db_supabase, "_request", lambda *args, **kwargs: list(rows))

    result = db_supabase.list_applicable_overrides(7, "alice")

    assert [item.id for item in result] == [2, 3, 1]


def test_project_payload_round_trip():
    item = ProjectCreate(
        title="测试",
        source_text="明日",
        lines=[AnnotatedLine(source="明日", segments=[Segment(text="明日", ruby="あす")])],
    )
    row = {
        "id": 5,
        **db_supabase._project_values(item, "alice"),
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }

    project = db_supabase._row_to_project(row)

    assert project.id == 5
    assert project.title == "测试"
    assert project.lines[0].segments[0].ruby == "あす"


def test_delete_project_always_filters_by_user(monkeypatch):
    calls = []
    monkeypatch.setattr(db_supabase, "_request", lambda *args, **kwargs: calls.append((args, kwargs)) or [{"id": 9}])

    assert db_supabase.delete_project(9, "alice")
    assert calls[0][1]["params"] == {"id": "eq.9", "user_id": "eq.alice"}
