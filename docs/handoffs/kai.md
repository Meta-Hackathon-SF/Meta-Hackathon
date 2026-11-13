# Kai handoff
Current step: 2 foundation restored; task 2 production formation/reveal BLOCKED
Status: fixture-verified only; default app intentionally not ready; no deployment/live Muse
Branch + commit: role/kai-orchestration / ddb71c1 (foundation)
Contract: 2.0.0 unchanged; D005 and D006 ACK posted on PR #11
Updated: 2026-11-13T02:14:06Z

## Completed milestones
- Task 1: archived app/config/errors/middleware/registry, manifests, CI, workflow migration restored and adapted. Existing 2.0.0 AGENTS preserved. Retired workflow modules replaced with strict weekly boundaries and a port-only worker.
- Registry: ServiceRegistration(owner, router, authorize, ready); /api/v1 prefix; only privacy POST /communities/{id}/join bootstraps without the global verified-session dependency. Areas include privacy/cycle/voice/matching/planning/orchestration/chat. See server/app/README.md.
- Strict camelCase models match the shared contract (including rejecting extra isFallback), runtime errors and fixture tests. The formation worker validates partition and blocks; injected store must recheck current consent/deletions/cycle revision atomically.
- db/workflow migration installs only jobs/idempotency/outbox, forced RLS and no API grants. PostgreSQL execution is unverified locally; CI has a disposable PostgreSQL migration check. No production repository exists.

## Requests answered
- PR #11: ACK FormationPort consumption and fallback labeling; CHANGE: isFallback is internal metadata, not a wire field. Rishi's to_wire already omits it; a public fallback label remains needed in the guarded name rather than private sharedMeaning.
- D005/D006 Kai ACK: https://github.com/willapat/Meta-Hackathon/pull/11#issuecomment-6841714246
- Remote handoffs read for all owners. Adam/Will still describe pre-pivot work, not delivered 2.0.0 dependencies; Patrik has not started 2.0.0. Superseded pre-pivot requests are not implemented.

## Shared-file claims
Task-1-authorized pyproject.toml, .github/workflows/validation.yml and db/workflow/*. No contracts or other owner paths changed.

## Checks and evidence
- Python 3.13.7 isolated venv outside repo; pinned installed dependency versions in server/app/requirements-dev.lock.
- python -m pytest tests/orchestration tests/chat -q: 77 passed, one Starlette httpx deprecation warning. Initial boolean-day test failed, fixed and rerun green.
- ruff format applied; ruff check before formatting found one long test line (formatted); final lint pending next checkpoint.
- Fixture adapters live exclusively under tests/. No live model, real player data, complete prompts, credentials or raw request logs.
- Web acceptance and PostgreSQL execution not run at this checkpoint. PR remains draft.

## Blocked on
- Patrik: 2.0.0 session/consent dependency, OutputGuard, M1, private storage/report/block ports, atomic current-state gates and revocation/deletion hooks. PrivacyPort alone exposes no transactional publish gate or answer texts for OutputGuard.
- Will: acknowledged CyclePort/router and a current locked/reveal snapshot plus revision/timing gate so formation and Sunday publishing cannot race cycle changes.
- Rishi: FormationService exists on role branch/PR #11; wire result compatible. Fallback grouping label currently only private sharedMeaning/internal metadata. computeSky is not yet supplied.
- Router registration ACKs and readiness exports from owners. No fake auth or fixture route is mounted.

## Next consumer action
Owners ACK/CHANGE the registry and deliver approved public factories/dependencies, production transaction hooks and cycle gates. Kai can then replace test stores with approved adapters and verify integration. Until then only independent work behind labeled test adapters; tasks 2-5 are not declared live-complete.

## Independent chat milestone (PR #13)
- Pure authorized-transaction chat policies: anonymous handles, M1 + OutputGuard gate, rate limiting, actor/route/body idempotency helper, immediate report hiding, two distinct reporters auto-hide, room-local blocks, pending/mutual reveal, exact weekly expiry, 14-day text/outbox purge.
- Validated StreamEvent union, SSE encoder, Last-Event-ID parsing, seq replay filtering; historical messages recheck current moderation/block state and mutual identities are pair-only.
- TEST-ONLY transaction/privacy/session/clock driver is exclusively tests/chat/adapters.py. No production chat store, route, HTTP stream or fake auth installed. Canonical block/report persistence, current privacy gates and actual moderation remain blocked.
- Targeted tests/chat: 32 passed; Ruff clean. Fixture evidence only, no model call.
- Requests answered: #14 DELIVERED registry/cycle slot/deps; #12 DELIVERED registry, ACK store needs; #17 ACK nudge shape and scope cut; #15 ACK D007 privacy SQLite (no cross-store atomicity assumed); #16 ACK guarded public fallback fix. Responses posted in original threads.
- New remote state: privacy sessions/consent are now on main; Rishi fallback fix/Sky computation and Will cycle hooks/router are on branches. Next sync main before composition; update old blockers accordingly.
- Sites skill applies only as local repository UI workflow; no hosting registration or deployment requested.
