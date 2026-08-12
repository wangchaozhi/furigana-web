from app import db
from app.models import OverrideCreate, OverrideUpdate


def test_update_override(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "test.sqlite3")
    db.init_db()
    created = db.upsert_override(OverrideCreate(surface="明日", reading="あす", context="明日へ"))

    updated = db.update_override(
        created.id,
        OverrideUpdate(surface="明日", reading="あした", context="明日へ"),
    )

    assert updated is not None
    assert updated.reading == "あした"
    assert db.list_overrides() == [updated]
