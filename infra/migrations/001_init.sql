-- Aurora VIII · Migración 001 · Esquema inicial
-- Compatible con PostgreSQL 14+ y Supabase. Idempotente: puede ejecutarse varias veces.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Identidad de aplicación (vinculada al proveedor de autenticación por auth_subject)
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_subject  TEXT NOT NULL UNIQUE,
    email         TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended')),
    is_admin      BOOLEAN NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_users_email ON users (lower(email));

CREATE TABLE IF NOT EXISTS projects (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    problem      TEXT NOT NULL DEFAULT '',
    tags         JSONB NOT NULL DEFAULT '[]'::jsonb,
    owner_id     UUID NOT NULL REFERENCES users(id),
    status       TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_projects_owner ON projects (owner_id);

CREATE TABLE IF NOT EXISTS project_members (
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        TEXT NOT NULL CHECK (role IN ('lead','engineer','reviewer','reader')),
    added_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, user_id)
);
CREATE INDEX IF NOT EXISTS ix_members_user ON project_members (user_id);

CREATE TABLE IF NOT EXISTS datasets (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id     UUID REFERENCES projects(id) ON DELETE CASCADE,  -- NULL = dataset demo global
    name           TEXT NOT NULL,
    version        INTEGER NOT NULL DEFAULT 1,
    kind           TEXT NOT NULL CHECK (kind IN ('builtin','upload')),
    family_hint    TEXT NOT NULL DEFAULT 'feedforward',
    storage_key    TEXT,
    metadata_json  JSONB NOT NULL DEFAULT '{}'::jsonb,
    status         TEXT NOT NULL DEFAULT 'ready' CHECK (status IN ('ready','deleted')),
    created_by     UUID REFERENCES users(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_datasets_project ON datasets (project_id);

CREATE TABLE IF NOT EXISTS architectures (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id     UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    family         TEXT NOT NULL CHECK (family IN ('feedforward','rnn','cnn','gan')),
    justification  TEXT NOT NULL DEFAULT '',
    config_json    JSONB NOT NULL,
    summary_json   JSONB NOT NULL DEFAULT '{}'::jsonb,
    version        INTEGER NOT NULL DEFAULT 1,
    created_by     UUID REFERENCES users(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, name, version)
);
CREATE INDEX IF NOT EXISTS ix_arch_project ON architectures (project_id);

CREATE TABLE IF NOT EXISTS training_jobs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id        UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    architecture_id   UUID NOT NULL REFERENCES architectures(id),
    dataset_id        UUID NOT NULL REFERENCES datasets(id),
    status            TEXT NOT NULL DEFAULT 'QUEUED'
                      CHECK (status IN ('QUEUED','PREPARING','RUNNING','COMPLETED','FAILED','CANCELLED')),
    progress          REAL NOT NULL DEFAULT 0,
    current_epoch     INTEGER NOT NULL DEFAULT 0,
    total_epochs      INTEGER NOT NULL,
    params_json       JSONB NOT NULL,
    priority          INTEGER NOT NULL DEFAULT 0,
    attempt           INTEGER NOT NULL DEFAULT 0,
    max_attempts      INTEGER NOT NULL DEFAULT 2,
    cancel_requested  BOOLEAN NOT NULL DEFAULT false,
    cancel_reason     TEXT,
    error_message     TEXT,
    result_json       JSONB NOT NULL DEFAULT '{}'::jsonb,
    trace_json        JSONB NOT NULL DEFAULT '{}'::jsonb,
    worker_id         TEXT,
    heartbeat_at      TIMESTAMPTZ,
    created_by        UUID NOT NULL REFERENCES users(id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at        TIMESTAMPTZ,
    ended_at          TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_jobs_queue ON training_jobs (status, priority DESC, created_at);
CREATE INDEX IF NOT EXISTS ix_jobs_project ON training_jobs (project_id, created_at DESC);

CREATE TABLE IF NOT EXISTS training_metrics (
    id            BIGSERIAL PRIMARY KEY,
    job_id        UUID NOT NULL REFERENCES training_jobs(id) ON DELETE CASCADE,
    epoch         INTEGER NOT NULL,
    metric_name   TEXT NOT NULL,
    metric_value  DOUBLE PRECISION NOT NULL,
    recorded_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_metrics_job ON training_metrics (job_id, epoch);

-- Bitácora de eventos en tiempo real (fuente para SSE con reanudación por Last-Event-ID)
CREATE TABLE IF NOT EXISTS job_events (
    id           BIGSERIAL PRIMARY KEY,
    job_id       UUID NOT NULL REFERENCES training_jobs(id) ON DELETE CASCADE,
    event_type   TEXT NOT NULL,
    payload      JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_events_job ON job_events (job_id, id);

CREATE TABLE IF NOT EXISTS model_versions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id     UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    job_id         UUID NOT NULL UNIQUE REFERENCES training_jobs(id),
    version        INTEGER NOT NULL,
    storage_key    TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','reviewed','approved','retired')),
    checksum       TEXT NOT NULL,
    size_bytes     BIGINT NOT NULL DEFAULT 0,
    metrics_json   JSONB NOT NULL DEFAULT '{}'::jsonb,
    notes          TEXT NOT NULL DEFAULT '',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, version)
);

CREATE TABLE IF NOT EXISTS audit_events (
    id             BIGSERIAL PRIMARY KEY,
    actor_id       UUID REFERENCES users(id),
    project_id     UUID REFERENCES projects(id) ON DELETE SET NULL,
    action         TEXT NOT NULL,
    metadata_json  JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_audit_project ON audit_events (project_id, created_at DESC);

-- Límites de recursos configurables desde Administración
CREATE TABLE IF NOT EXISTS system_settings (
    key         TEXT PRIMARY KEY,
    value_json  JSONB NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Supabase expone el esquema public por PostgREST. El acceso a datos de Aurora VIII
-- se hace SOLO a través de la API (rol de servicio), así que activamos RLS sin políticas:
-- nadie con la anon key puede leer o escribir estas tablas directamente.
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['users','projects','project_members','datasets','architectures',
                           'training_jobs','training_metrics','job_events','model_versions',
                           'audit_events','system_settings','schema_migrations']
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;

INSERT INTO schema_migrations (version) VALUES ('001_init') ON CONFLICT DO NOTHING;
