from app import db
from app.models import OverrideCreate, OverrideUpdate


def test_update_override(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "test.sqlite3")
    db.init_db()
    created = db.upsert_override(OverrideCreate(surface="明日", reading="あす", context="明日へ", scope="sentence"))

    updated = db.update_override(
        created.id,
        OverrideUpdate(surface="明日", reading="あした", context="明日へ", scope="sentence"),
    )

    assert updated is not None
    assert updated.reading == "あした"
    assert db.list_overrides() == [updated]


def test_rule_scopes_and_precedence(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "scopes.sqlite3")
    db.init_db()
    db.upsert_override(OverrideCreate(surface="明日", reading="あす", scope="global"))
    db.upsert_override(OverrideCreate(surface="明日", reading="みょうにち", scope="project", project_id=7))
    db.upsert_override(OverrideCreate(surface="明日", reading="あした", scope="sentence", context="でも明日"))

    project_rules = db.list_applicable_overrides(7)
    other_rules = db.list_applicable_overrides(8)

    assert [item.scope for item in project_rules] == ["sentence", "project", "global"]
    assert [item.scope for item in other_rules] == ["sentence", "global"]
