-- Kai-owned weekly job foundation, adapted from the archived workflow migration.
-- Fresh 2.0.0 schema only: no pre-pivot data migration is authorized.
-- This migration deliberately grants NO browser/API access. Privacy integration,
-- service-role grants and foreign keys require Patrik's acknowledged 2.0.0 port.
BEGIN;
CREATE SCHEMA workflow;
REVOKE ALL ON SCHEMA workflow FROM PUBLIC;
CREATE TABLE workflow.jobs (
    job_id text PRIMARY KEY,
    cycle_id text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('formation', 'reveal', 'expiry')),
    status text NOT NULL DEFAULT 'pending'
      CHECK (status IN ('pending', 'running', 'succeeded', 'failed')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 3),
    lease_owner text,
    lease_expires_at timestamptz,
    revision bigint NOT NULL CHECK (revision > 0),
    failure_code text,
    available_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (cycle_id, kind, revision),
    CHECK ((lease_owner IS NULL) = (lease_expires_at IS NULL))
);
CREATE TABLE workflow.idempotency (
    actor_id text NOT NULL,
    route text NOT NULL,
    key text NOT NULL CHECK (char_length(key) BETWEEN 1 AND 128),
    body_hash text NOT NULL,
    result jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (actor_id, route, key)
);
-- Outbox contains only already-validated StreamEvent. Identity events require
-- exactly the two recipients. Per-player revocation/membership is rechecked on read.
CREATE TABLE workflow.outbox (
    seq bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    cycle_id text NOT NULL,
    recipients text[] NOT NULL CHECK (cardinality(recipients) > 0),
    body jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE workflow.jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.jobs FORCE ROW LEVEL SECURITY;
ALTER TABLE workflow.idempotency ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.idempotency FORCE ROW LEVEL SECURITY;
ALTER TABLE workflow.outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.outbox FORCE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA workflow FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA workflow FROM PUBLIC;
COMMIT;
