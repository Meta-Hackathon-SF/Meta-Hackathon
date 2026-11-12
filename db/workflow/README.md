# Workflow persistence checkpoint

Apply `001_workflow.sql` once, with migration-owner credentials, after
`db/privacy/001_privacy_foundation.sql`. This migration creates the `workflow`
schema and the `workflow_worker` capability role. It is not a repeatable seed.
Production API and worker credentials must be non-owner, non-superuser,
non-BYPASSRLS logins. Grant the API login `gq_api` only; grant the separate worker
login both `gq_api` and `workflow_worker`. Keep both credentials server-side.

`WorkflowRepository` consumes the public privacy `Actor`, `Database` and
`PrivacyService` ports and `privacy.member_versions` SQL port. Supply approved
`proposal_projection` and `plan_projection` callables through the constructor;
artifact operations fail closed without them. A public projection export and
privacy-owner acknowledgment remain an integration dependency; this module does
not import privacy internals. Pass `worker_database` separately: worker operations fail closed when it is
absent. Fixture/replay mode is selected by trusted server construction, never an
HTTP body. Live mode rejects replay evidence and synthetic proposal members.

The P1 slice persists forming/proposed quests, immutable votes per participant and
revision, a unique finalization job at the third acceptance, leased worker claims,
one event/conversation per quest, an opener, event revisions and an outbox. A quest
row lock freezes the first quorum of three; late new votes fail stale. Operation
keys are bound to actor, route and canonical request hash. Reusing a key with a
different body fails; successful replays reuse identities and rebuild snapshots
from currently consented profiles. A voted plan revision cannot be overwritten.
Material finalizer changes produce a new proposed revision requiring fresh votes.
Publication side effects commit together or roll back together. Provider work
runs outside these transactions.

Public snapshots omit candidates, version vectors and private constraints. Read
projection checks use current authorized candidate data. Internal stored proposal
and plan artifacts retain version vectors and feasible windows for orchestration;
API credentials are backend-only and must never be given to peers. Jobs and event
revision ledgers have no direct API SELECT grant. Security-definer functions pin
their search paths and revoke default PUBLIC execution; leasing/publication
functions are granted only to `workflow_worker`.

This is a P2-entry checkpoint, not a production or P3 security certification.
Privacy reauthorization and public-text projection use separate transactions.
The in-publication version query detects a revocation already committed before
that query, but does not lock privacy membership/consent rows: a revoke may commit
between that query and workflow commit. Snapshot projection also cannot promise
atomic revocation across its separate privacy/workflow reads. Patrik must review
the schema, capability grants and an agreed atomic revocation mechanism before
merge or claims of race-proof revocation. Venue catalog, time, budget and location
feasibility remain the upstream planner/finalizer's responsibility; wire validity
and persistence alone do not establish them.

PostgreSQL integration tests require the real database roles and privacy migration.
No local PostgreSQL was available for this implementation checkpoint; report CI
results separately. Next work after feedback: bind the real planner/finalizer,
complete the revocation protocol, and exercise operational recovery/outbox
delivery. Failed jobs are terminal in this slice; lease reclamation is bounded
to five attempts and exhaustion recovery is deferred.
