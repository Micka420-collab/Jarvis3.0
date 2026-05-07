-- Jarvis 3.0 — schéma initial
-- pgvector activé pour stocker les embeddings ECAPA voix-print

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- Utilisateurs (profils familiaux)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username    TEXT NOT NULL UNIQUE,
    display_name TEXT,
    avatar_url  TEXT,
    is_owner    BOOLEAN NOT NULL DEFAULT FALSE,
    role        TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner','adult','teen','child','guest')),
    permissions JSONB NOT NULL DEFAULT '{}'::jsonb,
    voice_enrolled BOOLEAN NOT NULL DEFAULT FALSE,
    face_enrolled  BOOLEAN NOT NULL DEFAULT FALSE,
    push_subscriptions JSONB NOT NULL DEFAULT '[]'::jsonb,  -- VAPID
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Voix-print (ECAPA 192-d L2-normalisés) — multi-utilisateurs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS voiceprints (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    embedding   vector(192) NOT NULL,
    sample_count INT NOT NULL DEFAULT 1,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS voiceprints_user_id_idx ON voiceprints(user_id);
-- index ANN pour recherche rapide multi-users (HNSW)
CREATE INDEX IF NOT EXISTS voiceprints_embedding_idx
    ON voiceprints USING hnsw (embedding vector_cosine_ops);

-- ---------------------------------------------------------------------------
-- Audit auth
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS auth_events (
    id          BIGSERIAL PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id     UUID,
    session_id  TEXT,
    kind        TEXT NOT NULL,         -- voice_verify, jwt_issue, admin_command, ...
    similarity  REAL,
    accepted    BOOLEAN,
    metadata    JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS auth_events_ts_idx ON auth_events(ts DESC);

-- ---------------------------------------------------------------------------
-- Devices IoT (registre unifié MQTT/HA/série/Z2M)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS devices (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    transport   TEXT NOT NULL CHECK (transport IN ('mqtt','homeassistant','serial','zigbee2mqtt')),
    config      JSONB NOT NULL DEFAULT '{}'::jsonb,
    requires_admin BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Faits long-terme (résumé, accessibles aussi via Qdrant pour la recherche)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS facts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID REFERENCES users(id) ON DELETE SET NULL,
    text             TEXT NOT NULL,
    tags             TEXT[] DEFAULT '{}',
    -- Catégorie : preference (j'aime/je n'aime pas), fact (info objective),
    -- event (passé daté), conversation (extrait dialogue), skill_observation
    -- (apprentissage de routine), other.
    kind             TEXT NOT NULL DEFAULT 'fact',
    -- Importance subjective 0..1, pondère le scoring (par défaut 0.5)
    importance       REAL NOT NULL DEFAULT 0.5,
    -- Recherche full-text en français (BM25 via to_tsvector) pour hybrid search
    tsv              tsvector GENERATED ALWAYS AS (to_tsvector('french', coalesce(text, ''))) STORED,
    -- Compteur d'utilisation : un fact rappelé souvent est plus pertinent
    recall_count     INT NOT NULL DEFAULT 0,
    last_recalled_at TIMESTAMPTZ,
    -- Source : qui/quoi a inséré ce fait (orchestrator, user, learning_service...)
    source           TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS facts_user_id_idx     ON facts(user_id);
CREATE INDEX IF NOT EXISTS facts_tags_idx        ON facts USING GIN(tags);
CREATE INDEX IF NOT EXISTS facts_kind_idx        ON facts(kind);
CREATE INDEX IF NOT EXISTS facts_tsv_idx         ON facts USING GIN(tsv);
CREATE INDEX IF NOT EXISTS facts_recall_idx      ON facts(recall_count DESC, last_recalled_at DESC);

-- Trigger : maj automatique de updated_at sur tout UPDATE
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$ BEGIN NEW.updated_at = NOW(); RETURN NEW; END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS facts_set_updated_at ON facts;
CREATE TRIGGER facts_set_updated_at BEFORE UPDATE ON facts
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ALTER pour les bases existantes (idempotent)
ALTER TABLE facts ADD COLUMN IF NOT EXISTS kind             TEXT NOT NULL DEFAULT 'fact';
ALTER TABLE facts ADD COLUMN IF NOT EXISTS importance       REAL NOT NULL DEFAULT 0.5;
ALTER TABLE facts ADD COLUMN IF NOT EXISTS recall_count     INT  NOT NULL DEFAULT 0;
ALTER TABLE facts ADD COLUMN IF NOT EXISTS last_recalled_at TIMESTAMPTZ;
ALTER TABLE facts ADD COLUMN IF NOT EXISTS source           TEXT;
ALTER TABLE facts ADD COLUMN IF NOT EXISTS updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW();
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name='facts' AND column_name='tsv') THEN
        ALTER TABLE facts ADD COLUMN tsv tsvector
              GENERATED ALWAYS AS (to_tsvector('french', coalesce(text, ''))) STORED;
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Routines (apprises automatiquement ou créées manuellement)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS routines (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    trigger     JSONB NOT NULL,    -- {kind: 'time'|'event'|'voice', spec: {...}}
    actions     JSONB NOT NULL,    -- [{tool, args}]
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    learned     BOOLEAN NOT NULL DEFAULT FALSE,  -- true si proposée par learning service
    confidence  REAL DEFAULT 0,    -- score pattern detection
    created_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_run_at TIMESTAMPTZ
);

-- ---------------------------------------------------------------------------
-- Observations IoT (pour le pattern detection des routines apprises)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS observations (
    id          BIGSERIAL PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    kind        TEXT NOT NULL,   -- 'iot_command', 'voice_intent', 'presence', ...
    device_id   TEXT,
    action      TEXT,
    metadata    JSONB DEFAULT '{}'::jsonb,
    -- weekday/hour pré-calculés pour requêtes pattern rapides
    weekday     INT,
    hour        INT
);
CREATE INDEX IF NOT EXISTS observations_kind_idx ON observations(kind, ts DESC);
CREATE INDEX IF NOT EXISTS observations_pattern_idx ON observations(weekday, hour, device_id, action);

-- ---------------------------------------------------------------------------
-- Mode présence (away mode) — état global
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS presence_state (
    id          INT PRIMARY KEY DEFAULT 1 CHECK (id = 1),  -- singleton
    away        BOOLEAN NOT NULL DEFAULT FALSE,
    away_until  TIMESTAMPTZ,
    simulate_presence BOOLEAN NOT NULL DEFAULT FALSE,
    last_seen_owner_at TIMESTAMPTZ,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO presence_state (id) VALUES (1) ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- Trace de raisonnement (explainability)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reasoning_traces (
    id          BIGSERIAL PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_id  TEXT,
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    user_text   TEXT,
    intent      TEXT,
    tools_called JSONB DEFAULT '[]'::jsonb,
    memory_hits JSONB DEFAULT '[]'::jsonb,
    response    TEXT,
    duration_ms INT
);
CREATE INDEX IF NOT EXISTS reasoning_session_idx ON reasoning_traces(session_id, ts DESC);
