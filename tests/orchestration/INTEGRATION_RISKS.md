# Workflow integration review — Kai P1 to P2 entry

This is a review checklist and evidence boundary, not a claim that all risks have
been eliminated. The tests use real PostgreSQL/non-bypass roles and authenticated
guest **test sessions**, but all people, preferences, proposals and provider
evidence are fixtures. No live Muse or three-human/device journey is certified.

## Required publication boundary

The accepted plan must remain the plan participants confirmed. Changed time,
venue, cost, members or activity requires a new proposed revision and a fresh
acceptance set. A row lock prevents competing workflow updates, but it does not
by itself make an external provider response current. The job must revalidate
stored quest/member versions and current eligibility before committing effects.

The suite checks explicit revocation and intent changes before publication. The
last-millisecond consent-revoke/commit race needs Patrik's review: public privacy
service checks may run in a different transaction from workflow publication.
The reviewed SQL `finish_job` locks workflow rows but does not itself lock or
recheck privacy consent rows. Workflow locks alone must not be advertised as
serializing privacy mutations.
A transaction-scoped public privacy guard or equivalent proven coordination is
needed before claiming full adversarial race coverage. This is a P2/P3 integration
gate, not permission to weaken consent or silently publish a stale plan.

## Database capability and RLS review

- Workflow tables must fail closed without `privacy.actor()` and restrict peer
  reads to current authorized quest members. Test the actual `gq_api` login, not a
  migration owner or service role that bypasses row-level security.
- A distinct `workflow_worker` role gates claim/complete/fail. API request
  credentials must not execute those functions, even by changing an actor setting.
- Any SECURITY DEFINER routine needs a fixed safe search path, explicit actor and
  membership/version checks, and PUBLIC execution revoked. Do not use recursive
  table policies or grant peers access to internal proposal versions/job payloads.
- Recheck authorization before idempotency replay and reads. An old response is
  not an access grant after a session, membership or consent has been revoked.
- Member public profiles should be projected using current consent; historical
  `publicInterests` must not survive withdrawal through a stale cached snapshot.

## Contract and demo boundaries

The wire contract is `contracts/protocol.ts` 1.0.0. Snapshot and event field
allowlists are asserted in the tests. Private proposal member versions, budgets,
intent goals, transcripts and worker internals must never enter public snapshots,
messages or error bodies. A persisted event is an in-app event, not a real
Facebook Event. No model-generated side effect is authorized by a prompt.

The parent owns the HTTP registration. Accept body is exactly `{revision, choice}`;
identity is the verified session and mode is server selected. Proposal creation
must consume an authoritative server proposal; the fixture plan import used by
these tests must never become an unrestricted client endpoint.

These milestone tests require three independent authenticated test actors, one
pending job, one persistent event identity, one assistant opener, and restoration
from PostgreSQL through a fresh client/process. This is storage/transaction and
HTTP evidence once the combined integration head passes PostgreSQL CI. Until then,
the assertions describe required behavior, not completed runtime verification.
Real Muse planning, approved venue catalog integration, UI stream
reconnect, external host invitations and P3–P6 behavior remain separate work.

## CI and resumption

Set `GQ_TEST_ADMIN_DSN` to a disposable Postgres 17 test service. The harness makes
a unique database plus separate API and worker login roles and removes them at
session teardown. Its destructive cleanup is scoped to that unique database.
Local absence of PostgreSQL is an explicit skip; CI must require a connection and
reject silently skipped **workflow** tests as well as privacy tests. Missing
implementation imports should fail collection, never be skipped as fake success.

Before merging: run the combined test suite on the exact integration head, obtain
Patrik's policy/capability review, and record fixture versus live evidence in the
handoff. Stop at a tested P2 entry point for feedback; do not expand into hosting,
full revision recovery or a new Campus product in this checkpoint.
