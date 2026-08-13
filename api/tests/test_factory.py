from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from app import db
from app.factory import create_app


def test_local_mode_exposes_authenticated_features(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "api.sqlite3")
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    with TestClient(create_app(db)) as client:
        assert client.get("/api/auth/config").json() == {"required": False}
        assert client.get("/api/auth/me").json()["id"] == "local"
        assert client.get("/api/projects").status_code == 200


def test_cloud_mode_rejects_missing_token(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "protected.sqlite3")
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    with TestClient(create_app(db)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/auth/config").json() == {"required": True}
        response = client.get("/api/projects")
        assert response.status_code == 401
        assert response.json()["detail"] == "Authentication required"


def test_cloud_mode_syncs_users_and_isolates_api_data(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "cloud.sqlite3")
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret-at-least-32-characters-long")

    def token(subject: str, email: str) -> str:
        return jwt.encode(
            {
                "sub": subject,
                "email": email,
                "aud": "authenticated",
                "iss": "https://example.supabase.co/auth/v1",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            },
            "test-secret-at-least-32-characters-long",
            algorithm="HS256",
        )

    alice = {"Authorization": f"Bearer {token('alice', 'alice@example.com')}"}
    bob = {"Authorization": f"Bearer {token('bob', 'bob@example.com')}"}
    payload = {"title": "私有项目", "source_text": "明日", "lines": []}
    with TestClient(create_app(db)) as client:
        assert client.get("/api/auth/me", headers=alice).json() == {"id": "alice", "email": "alice@example.com"}
        created = client.post("/api/projects", headers=alice, json=payload)
        assert created.status_code == 200
        assert len(client.get("/api/projects", headers=alice).json()) == 1
        assert client.get("/api/projects", headers=bob).json() == []
        assert client.get(f"/api/projects/{created.json()['id']}", headers=bob).status_code == 404
