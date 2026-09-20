-- AEGIS core schema
-- Division 1: Foundation & Schema
-- Every downstream division (data generator, feature engineering, ML, hard controls,
-- correlation engine, audit log) reads from or writes to these tables.
--
-- SUPERSEDED as the init mechanism: the schema is now owned by Alembic
-- (backend/migrations/versions/0001_initial_schema.py), which runs automatically
-- on backend container startup. This file is kept only as schema documentation —
-- it is no longer mounted into docker-entrypoint-initdb.d. Future schema changes
-- go through new Alembic revisions, not edits here.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- USERS: profile + historical behavioural baselines
-- ============================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name TEXT NOT NULL,
    msisdn TEXT UNIQUE NOT NULL,              -- phone number, used for USSD + telco fields
    persona_tag TEXT,                          -- links back to synthetic persona (Division 3)
    preferred_channel TEXT CHECK (preferred_channel IN ('WEB', 'USSD', 'BOTH')),
    typical_hour_start SMALLINT,                -- historical baseline window
    typical_hour_end SMALLINT,
    typical_amount_avg NUMERIC(14,2),
    typical_amount_stddev NUMERIC(14,2),
    account_created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active_at TIMESTAMPTZ
);

-- ============================================================
-- SESSIONS: one row per login/session, either channel
-- ============================================================
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    channel TEXT NOT NULL CHECK (channel IN ('WEB', 'USSD')),
    device_fingerprint TEXT,                    -- hash of UA + screen + timezone (WEB only)
    ip_address INET,
    ip_type TEXT CHECK (ip_type IN ('HOME_WIFI', 'MOBILE_DATA', 'VPN_PROXY', 'UNKNOWN')),
    geo_lat DOUBLE PRECISION,
    geo_lon DOUBLE PRECISION,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at TIMESTAMPTZ
);

-- ============================================================
-- BEHAVIORAL_EVENTS: WEB channel telemetry
-- ============================================================
CREATE TABLE behavioral_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id),
    event_type TEXT NOT NULL,                   -- KEYDOWN, KEYUP, PASTE, BACKSPACE, MOUSEMOVE, NAV, CALL_STATE
    key_dwell_ms INTEGER,
    key_flight_ms INTEGER,
    is_paste BOOLEAN DEFAULT FALSE,
    backspace_count INTEGER DEFAULT 0,
    nav_screen TEXT,
    cursor_smoothness_score REAL,               -- derived metric, 0 = robotic, 1 = natural
    call_active BOOLEAN DEFAULT FALSE,           -- simultaneous phone call flag
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- USSD_EVENTS: USSD channel telemetry (Division 2B)
-- ============================================================
CREATE TABLE ussd_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id),
    menu_step TEXT NOT NULL,                    -- accumulated 'text' value, e.g. '1*2*5000'
    retry_count INTEGER DEFAULT 0,
    timeout_count INTEGER DEFAULT 0,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- TELCO_STATE: simulated telco-side signals (Division 5B)
-- ============================================================
CREATE TABLE telco_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    imei TEXT NOT NULL,
    sim_device_paired BOOLEAN DEFAULT TRUE,
    last_sim_swap_at TIMESTAMPTZ,
    cell_region TEXT,
    otp_request_count_window INTEGER DEFAULT 0,  -- rolling count, refreshed by Redis in prod
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- TRANSACTIONS
-- ============================================================
CREATE TABLE transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id),
    user_id UUID NOT NULL REFERENCES users(id),
    beneficiary_account TEXT NOT NULL,
    beneficiary_is_novel BOOLEAN DEFAULT FALSE,
    amount NUMERIC(14,2) NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- DECISIONS: the core output of Division 4 (ML) + Division 5 (hard controls)
-- ============================================================
CREATE TABLE decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_id UUID REFERENCES transactions(id),
    session_id UUID NOT NULL REFERENCES sessions(id),
    risk_score REAL,                             -- 0-100, null if a hard rule short-circuited scoring
    verdict TEXT NOT NULL CHECK (verdict IN ('ALLOW', 'CHALLENGE', 'BLOCK')),
    triggered_rules TEXT[],                       -- e.g. {'SIM_SWAP_RECENT', 'OTP_REPLAY'}
    feature_contributions JSONB,                  -- SHAP output, Division 6A
    explanation_customer TEXT,                    -- Division 6B
    explanation_analyst TEXT,                     -- Division 6B
    model_version TEXT,                           -- e.g. 'aegis-xgb-v3'
    latency_ms REAL,
    decided_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- AUDIT_LOG: hash-chained, tamper-evident (Division 8E)
-- ============================================================
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    decision_id UUID REFERENCES decisions(id),
    row_data JSONB NOT NULL,
    prev_hash TEXT,
    row_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- CORRELATION_EDGES: identity correlation graph (Division 5C)
-- ============================================================
CREATE TABLE correlation_edges (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_fingerprint TEXT,
    ip_address INET,
    user_id UUID NOT NULL REFERENCES users(id),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- SENSOR_ALERTS: Suricata/Zeek ingestion (Division 8C)
-- ============================================================
CREATE TABLE sensor_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID REFERENCES sessions(id),
    sensor TEXT NOT NULL CHECK (sensor IN ('SURICATA', 'ZEEK')),
    alert_tag TEXT NOT NULL,
    severity TEXT,
    raw_payload JSONB,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Helpful indexes
-- ============================================================
CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_behavioral_events_session ON behavioral_events(session_id);
CREATE INDEX idx_ussd_events_session ON ussd_events(session_id);
CREATE INDEX idx_transactions_user ON transactions(user_id);
CREATE INDEX idx_decisions_session ON decisions(session_id);
CREATE INDEX idx_correlation_device ON correlation_edges(device_fingerprint);
CREATE INDEX idx_correlation_ip ON correlation_edges(ip_address);
