from app import db
from app.models import AnnotatedLine, OverrideCreate, OverrideUpdate, ProjectCreate, Segment


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


def test_update_project_in_place(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "projects.sqlite3")
    db.init_db()
    initial = ProjectCreate(
        title="旧标题",
        source_text="明日",
        lines=[AnnotatedLine(source="明日", segments=[Segment(text="明日", ruby="あす")])],
    )
    created = db.save_project(initial)
    changed = initial.model_copy(update={"title": "新标题"})

    updated = db.update_project(created.id, changed)

    assert updated is not None
    assert updated.id == created.id
    assert updated.title == "新标题"
    assert len(db.list_projects()) == 1


def test_project_preserves_translation_settings_and_lines(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "translations.sqlite3")
    db.init_db()
    project = db.save_project(
        ProjectCreate(
            title="双语",
            source_text="明日",
            translation_language="zh",
            lines=[
                AnnotatedLine(
                    source="明日",
                    translation="明天",
                    segments=[Segment(text="明日", ruby="あした")],
                )
            ],
        )
    )

    loaded = db.get_project(project.id)
    assert loaded is not None
    assert loaded.translation_language == "zh"
    assert loaded.lines[0].translation == "明天"


def test_delete_project_removes_its_scoped_rules(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "delete.sqlite3")
    db.init_db()
    project = db.save_project(ProjectCreate(title="测试", source_text="明日", lines=[]))
    db.upsert_override(
        OverrideCreate(surface="明日", reading="あした", scope="project", project_id=project.id)
    )

    assert db.delete_project(project.id)
    assert db.list_overrides() == []


def test_migrates_legacy_rules_to_scopes(tmp_path, monkeypatch):
    database = tmp_path / "legacy.sqlite3"
    monkeypatch.setattr(db, "_DB_PATH", database)
    with db._connect() as conn:
        conn.executescript(
            """
            CREATE TABLE ruby_overrides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                surface TEXT NOT NULL,
                context TEXT NOT NULL DEFAULT '',
                reading TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(surface, context)
            );
            INSERT INTO ruby_overrides(surface, context, reading)
            VALUES ('明日', 'でも明日', 'あした'), ('今日', '', 'きょう');
            """
        )

    db.init_db()

    rules = db.list_overrides()
    assert {(item.surface, item.scope) for item in rules} == {("明日", "sentence"), ("今日", "global")}
