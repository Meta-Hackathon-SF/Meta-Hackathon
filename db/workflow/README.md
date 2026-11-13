# Weekly workflow persistence foundation

Kai owns this schema. Task 1 restores the archived migration pattern with weekly
cycle jobs, idempotency and an outbox; retired product tables are removed.

Migration order: privacy's acknowledged 2.0.0 foundation first, then
`001_workflow.sql` and `002_runtime_state.sql`, in that order. These migrations
target a fresh PostgreSQL database; no deployment or legacy data migration is claimed.
The first migration's job/outbox tables have no API grants. The second adds the
private `workflow.runtime_state` row used by `PostgresWorkflowRepository` and a
server-only `workflow_runtime` NOLOGIN role with SELECT/INSERT/UPDATE policies.
The configured application LOGIN must inherit that role. PUBLIC has no grants,
and every workflow table enables and forces RLS. Never grant browser roles access
to private state, actor IDs, recipient lists or `workflow_runtime` membership.

The repository serializes short commits with SELECT FOR UPDATE on one private row,
validates every chat wire object and reference on reload, and atomically persists
messages, report/reveal state, replay deliveries, idempotency and metadata. It never
logs state/credentials, starts migrations implicitly or falls back to memory.
Raw answers, provider prompts/payloads and session tokens stay out of workflow metadata.

Callers must still acquire current cycle and privacy guards before the short commit,
and reauthorize reads and stream delivery. This is single-process integration with
privacy's separate SQLite store; it is not a distributed transaction. Never hold
the workflow transaction across a provider call.

Tests use a labeled TEST-ONLY serialized repository offline. Actual PostgreSQL
tests run only with explicit disposable `CONSTELLATIONS_TEST_ADMIN_DSN`; they create
and remove their own synthetic database. Local tests without that variable report
the PostgreSQL checks as skipped, not verified. See Kai's handoff for actual evidence.
