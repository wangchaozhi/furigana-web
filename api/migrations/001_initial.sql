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

-- The browser only uses Supabase Auth. Business data is accessed through the
-- FastAPI service, so deny direct Data API access to these public tables.
ALTER TABLE app_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE ruby_overrides ENABLE ROW LEVEL SECURITY;

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
END
$$;
