-- Jarvis 3.0 — schéma initial
-- pgvector activé pour stocker les embeddings ECAPA voix-print

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- Utilisateurs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username    TEXT NOT NULL UNIQUE,
    is_owner    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- Voix-print (embeddings ECAPA-TDNN 192-d, L2-normalisés)
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
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    text        TEXT NOT NULL,
    tags        TEXT[] DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS facts_user_id_idx ON facts(user_id);
CREATE INDEX IF NOT EXISTS facts_tags_idx ON facts USING GIN(tags);
