# Weekly workflow persistence foundation

Kai owns this schema. Task 1 restores the archived migration pattern with weekly
cycle jobs, idempotency and an outbox; retired product tables are removed.

Migration order: privacy's acknowledged 2.0.0 foundation first, then
`001_workflow.sql`, then a separately reviewed service-role integration migration.
This file runs on a fresh database; no existing deployment migration is claimed.
It installs no access grants or RLS policies: ordinary roles cannot read/write.
Do not grant direct browser access to jobs, actor IDs or recipient lists.

A production repository and transactional privacy rechecks remain BLOCKED on
Patrik's storage/session interface and Will's cycle revision/timing interface.
No SQL run or PostgreSQL-backed behavior is claimed until recorded in the handoff.
