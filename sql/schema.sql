CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS network;
CREATE SCHEMA IF NOT EXISTS monitoring;
CREATE SCHEMA IF NOT EXISTS dashboard;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        CREATE TYPE user_role AS ENUM ('ADMIN', 'NETWORK_OPERATOR', 'NETWORK_MANAGER');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ric_status') THEN
        CREATE TYPE ric_status AS ENUM ('HEALTHY', 'DEGRADED', 'CRITICAL', 'MAINTENANCE');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'slice_type') THEN
        CREATE TYPE slice_type AS ENUM ('eMBB', 'URLLC', 'mMTC', 'ERLLC', 'feMBB', 'umMTC', 'MBRLLC', 'mURLLC');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'risk_level') THEN
        CREATE TYPE risk_level AS ENUM ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS auth.users (
    id BIGSERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role user_role NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_auth_users_role ON auth.users(role);
CREATE INDEX IF NOT EXISTS ix_auth_users_is_active ON auth.users(is_active);

CREATE TABLE IF NOT EXISTS network.regions (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    ric_status ric_status NOT NULL,
    network_load NUMERIC(5, 2) NOT NULL CHECK (network_load >= 0 AND network_load <= 100),
    gnodeb_count INTEGER NOT NULL CHECK (gnodeb_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS network.sessions (
    id BIGSERIAL PRIMARY KEY,
    session_code VARCHAR(64) NOT NULL UNIQUE,
    region_id BIGINT NOT NULL REFERENCES network.regions(id) ON DELETE RESTRICT,
    slice_type slice_type NOT NULL,
    use_case_type VARCHAR(120) NOT NULL DEFAULT 'Smart City' CHECK (use_case_type <> ''),
    required_mobility BOOLEAN NOT NULL DEFAULT FALSE,
    required_connectivity BOOLEAN NOT NULL DEFAULT FALSE,
    slice_handover BOOLEAN NOT NULL DEFAULT FALSE,
    lte_5g_category INTEGER NOT NULL DEFAULT 10 CHECK (lte_5g_category >= 1 AND lte_5g_category <= 22),
    smartphone INTEGER NOT NULL DEFAULT 0 CHECK (smartphone IN (0, 1)),
    gbr INTEGER NOT NULL DEFAULT 0 CHECK (gbr IN (0, 1)),
    latency_ms NUMERIC(10, 2) NOT NULL CHECK (latency_ms >= 0),
    packet_loss NUMERIC(6, 3) NOT NULL CHECK (packet_loss >= 0),
    throughput_mbps NUMERIC(10, 2) NOT NULL CHECK (throughput_mbps >= 0),
    iot_devices INTEGER NOT NULL DEFAULT 0 CHECK (iot_devices IN (0, 1)),
    public_safety INTEGER NOT NULL DEFAULT 0 CHECK (public_safety IN (0, 1)),
    smart_city_home INTEGER NOT NULL DEFAULT 0 CHECK (smart_city_home IN (0, 1)),
    cpu_util_pct NUMERIC(5, 2) NOT NULL DEFAULT 0 CHECK (cpu_util_pct >= 0 AND cpu_util_pct <= 100),
    mem_util_pct NUMERIC(5, 2) NOT NULL DEFAULT 0 CHECK (mem_util_pct >= 0 AND mem_util_pct <= 100),
    bw_util_pct NUMERIC(5, 2) NOT NULL DEFAULT 0 CHECK (bw_util_pct >= 0 AND bw_util_pct <= 100),
    active_users INTEGER NOT NULL DEFAULT 0 CHECK (active_users >= 0),
    queue_len INTEGER NOT NULL DEFAULT 0 CHECK (queue_len >= 0),
    packet_loss_budget NUMERIC(10, 6) NOT NULL DEFAULT 0 CHECK (packet_loss_budget >= 0),
    latency_budget_ns BIGINT NOT NULL DEFAULT 0 CHECK (latency_budget_ns >= 0),
    jitter_budget_ns BIGINT NOT NULL DEFAULT 0 CHECK (jitter_budget_ns >= 0),
    data_rate_budget_gbps NUMERIC(10, 2) NOT NULL DEFAULT 0 CHECK (data_rate_budget_gbps >= 0),
    slice_available_transfer_rate_gbps NUMERIC(12, 3) NOT NULL DEFAULT 0 CHECK (slice_available_transfer_rate_gbps >= 0),
    slice_latency_ns BIGINT NOT NULL DEFAULT 0 CHECK (slice_latency_ns >= 0),
    slice_packet_loss NUMERIC(10, 6) NOT NULL DEFAULT 0 CHECK (slice_packet_loss >= 0),
    slice_jitter_ns BIGINT NOT NULL DEFAULT 0 CHECK (slice_jitter_ns >= 0),
    timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_network_sessions_region_id ON network.sessions(region_id);
CREATE INDEX IF NOT EXISTS ix_network_sessions_slice_type ON network.sessions(slice_type);
CREATE INDEX IF NOT EXISTS ix_network_sessions_region_timestamp ON network.sessions(region_id, timestamp);

CREATE TABLE IF NOT EXISTS monitoring.predictions (
    id BIGSERIAL PRIMARY KEY,
    session_id BIGINT NOT NULL REFERENCES network.sessions(id) ON DELETE CASCADE,
    sla_score NUMERIC(5, 4) NOT NULL CHECK (sla_score >= 0 AND sla_score <= 1),
    congestion_score NUMERIC(5, 4) NOT NULL CHECK (congestion_score >= 0 AND congestion_score <= 1),
    anomaly_score NUMERIC(5, 4) NOT NULL CHECK (anomaly_score >= 0 AND anomaly_score <= 1),
    risk_level risk_level NOT NULL,
    predicted_slice_type slice_type NOT NULL,
    slice_confidence NUMERIC(5, 4) NOT NULL CHECK (slice_confidence >= 0 AND slice_confidence <= 1),
    recommended_action TEXT NOT NULL,
    model_source VARCHAR(255) NOT NULL,
    predicted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_monitoring_predictions_session_predicted_at
    ON monitoring.predictions(session_id, predicted_at);
CREATE INDEX IF NOT EXISTS ix_monitoring_predictions_risk_level
    ON monitoring.predictions(risk_level);

CREATE TABLE IF NOT EXISTS dashboard.dashboard_snapshots (
    id BIGSERIAL PRIMARY KEY,
    region_id BIGINT REFERENCES network.regions(id) ON DELETE SET NULL,
    sla_percent NUMERIC(5, 2) NOT NULL CHECK (sla_percent >= 0 AND sla_percent <= 100),
    avg_latency_ms NUMERIC(10, 2) NOT NULL,
    congestion_rate NUMERIC(5, 2) NOT NULL CHECK (congestion_rate >= 0 AND congestion_rate <= 100),
    active_alerts_count INTEGER NOT NULL DEFAULT 0 CHECK (active_alerts_count >= 0),
    anomalies_count INTEGER NOT NULL DEFAULT 0 CHECK (anomalies_count >= 0),
    total_sessions INTEGER NOT NULL DEFAULT 0 CHECK (total_sessions >= 0),
    generated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_dashboard_snapshots_region_generated_at
    ON dashboard.dashboard_snapshots(region_id, generated_at);
