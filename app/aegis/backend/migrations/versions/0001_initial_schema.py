"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-09-05

Baseline migration — mirrors ops/postgres/init/001_schema.sql exactly.
That file is kept for reference/documentation; this migration is now the
versioned source of truth for the schema. All future schema changes go
through new Alembic revisions, not hand edits to raw SQL.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.execute("""
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            full_name TEXT NOT NULL,
            msisdn TEXT UNIQUE NOT NULL,
            persona_tag TEXT,
            preferred_channel TEXT CHECK (preferred_channel IN ('WEB', 'USSD', 'BOTH')),
            typical_hour_start SMALLINT,
            typical_hour_end SMALLINT,
            typical_amount_avg NUMERIC(14,2),
            typical_amount_stddev NUMERIC(14,2),
            account_created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_active_at TIMESTAMPTZ
        )
    """)

    op.execute("""
        CREATE TABLE sessions (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID REFERENCES users(id),
            channel TEXT NOT NULL CHECK (channel IN ('WEB', 'USSD')),
            device_fingerprint TEXT,
            ip_address INET,
            ip_type TEXT CHECK (ip_type IN ('HOME_WIFI', 'MOBILE_DATA', 'VPN_PROXY', 'UNKNOWN')),
            geo_lat DOUBLE PRECISION,
            geo_lon DOUBLE PRECISION,
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            ended_at TIMESTAMPTZ
        )
    """)

    op.execute("""
        CREATE TABLE behavioral_events (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            session_id UUID NOT NULL REFERENCES sessions(id),
            event_type TEXT NOT NULL,
            key_dwell_ms INTEGER,
            key_flight_ms INTEGER,
            is_paste BOOLEAN DEFAULT FALSE,
            backspace_count INTEGER DEFAULT 0,
            nav_screen TEXT,
            cursor_smoothness_score REAL,
            call_active BOOLEAN DEFAULT FALSE,
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE ussd_events (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            session_id UUID NOT NULL REFERENCES sessions(id),
            menu_step TEXT NOT NULL,
            retry_count INTEGER DEFAULT 0,
            timeout_count INTEGER DEFAULT 0,
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE telco_state (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID NOT NULL REFERENCES users(id),
            imei TEXT NOT NULL,
            sim_device_paired BOOLEAN DEFAULT TRUE,
            last_sim_swap_at TIMESTAMPTZ,
            cell_region TEXT,
            otp_request_count_window INTEGER DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE transactions (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            session_id UUID NOT NULL REFERENCES sessions(id),
            user_id UUID NOT NULL REFERENCES users(id),
            beneficiary_account TEXT NOT NULL,
            beneficiary_is_novel BOOLEAN DEFAULT FALSE,
            amount NUMERIC(14,2) NOT NULL,
            requested_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE decisions (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            transaction_id UUID REFERENCES transactions(id),
            session_id UUID NOT NULL REFERENCES sessions(id),
            risk_score REAL,
            verdict TEXT NOT NULL CHECK (verdict IN ('ALLOW', 'CHALLENGE', 'BLOCK')),
            triggered_rules TEXT[],
            feature_contributions JSONB,
            explanation_customer TEXT,
            explanation_analyst TEXT,
            model_version TEXT,
            latency_ms REAL,
            decided_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE audit_log (
            id BIGSERIAL PRIMARY KEY,
            decision_id UUID REFERENCES decisions(id),
            row_data JSONB NOT NULL,
            prev_hash TEXT,
            row_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE correlation_edges (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            device_fingerprint TEXT,
            ip_address INET,
            user_id UUID NOT NULL REFERENCES users(id),
            first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE sensor_alerts (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            session_id UUID REFERENCES sessions(id),
            sensor TEXT NOT NULL CHECK (sensor IN ('SURICATA', 'ZEEK')),
            alert_tag TEXT NOT NULL,
            severity TEXT,
            raw_payload JSONB,
            recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("CREATE INDEX idx_sessions_user ON sessions(user_id)")
    op.execute("CREATE INDEX idx_behavioral_events_session ON behavioral_events(session_id)")
    op.execute("CREATE INDEX idx_ussd_events_session ON ussd_events(session_id)")
    op.execute("CREATE INDEX idx_transactions_user ON transactions(user_id)")
    op.execute("CREATE INDEX idx_decisions_session ON decisions(session_id)")
    op.execute("CREATE INDEX idx_correlation_device ON correlation_edges(device_fingerprint)")
    op.execute("CREATE INDEX idx_correlation_ip ON correlation_edges(ip_address)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sensor_alerts")
    op.execute("DROP TABLE IF EXISTS correlation_edges")
    op.execute("DROP TABLE IF EXISTS audit_log")
    op.execute("DROP TABLE IF EXISTS decisions")
    op.execute("DROP TABLE IF EXISTS transactions")
    op.execute("DROP TABLE IF EXISTS telco_state")
    op.execute("DROP TABLE IF EXISTS ussd_events")
    op.execute("DROP TABLE IF EXISTS behavioral_events")
    op.execute("DROP TABLE IF EXISTS sessions")
    op.execute("DROP TABLE IF EXISTS users")
