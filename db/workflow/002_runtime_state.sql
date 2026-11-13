-- Kai-owned private persistence for the single-process weekly runtime.
-- Apply after 001_workflow.sql. Never give browsers membership in workflow_runtime.
BEGIN;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'workflow_runtime') THEN
        CREATE ROLE workflow_runtime NOLOGIN;
    END IF;
END $$;

CREATE TABLE workflow.runtime_state (
    state_key text PRIMARY KEY CHECK (char_length(state_key) BETWEEN 1 AND 128),
    revision bigint NOT NULL DEFAULT 0 CHECK (revision >= 0),
    body jsonb NOT NULL CHECK (jsonb_typeof(body) = 'object'),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE workflow.runtime_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow.runtime_state FORCE ROW LEVEL SECURITY;
REVOKE ALL ON workflow.runtime_state FROM PUBLIC;
GRANT USAGE ON SCHEMA workflow TO workflow_runtime;
GRANT SELECT, INSERT, UPDATE ON workflow.runtime_state TO workflow_runtime;
CREATE POLICY runtime_server_read ON workflow.runtime_state
    FOR SELECT TO workflow_runtime USING (true);
CREATE POLICY runtime_server_insert ON workflow.runtime_state
    FOR INSERT TO workflow_runtime WITH CHECK (true);
CREATE POLICY runtime_server_update ON workflow.runtime_state
    FOR UPDATE TO workflow_runtime USING (true) WITH CHECK (true);

INSERT INTO workflow.runtime_state (state_key, body) VALUES (
    'weekly',
    '{"schemaVersion":1,"seq":0,"rooms":{},"deliveries":[],"idempotency":[],"records":{}}'
);
COMMIT;
