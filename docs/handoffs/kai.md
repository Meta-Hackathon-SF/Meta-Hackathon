# Kai handoff

- Updated: 2026-11-12T21:24Z
- Owner / branch: Kai / `role/kai-orchestration`
- Current phase: **P0 independent server baseline verified; coordination gate pending**.
- Next system phase: P1 durable workflow state, not implemented in this checkpoint.
- Contract: 1.0.0, unchanged.
- Implementation commits: `adb7dc6` (server baseline), `1a0e045` (privacy bootstrap alignment).
- Test/evidence checkpoint: the commit containing this handoff adds `tests/orchestration/test_app.py`.
- Integration checkpoint / shared-file claim (2026-11-12T21:32Z): latest human direction authorizes safe automatic squash merges. Kai is updating `AGENTS.md` with this standing policy and `PROJECT_KNOWLEDGE.md` with verified source/evidence. Current main was merged normally (`bdac27e`), preserving Rishi's D005 and Kai's D006; combined tests passed 144/144. The P0 phase and unimplemented event/persistence scope are unchanged.

## Completed deliverable

An executable FastAPI app with `/health`, `/health/ready`, development OpenAPI,
and explicit service composition. Default readiness is **503**, not a fabricated
working product: no business services, sessions, DB or provider are installed.

`create_app(..., registrations=[ServiceRegistration(...)])` mounts owner routers
under `/api/v1`, rejects duplicate owners/routes, requires a session guard, and
checks readiness with bounded owner probes. The sole unauthenticated bootstrap
exception is privacy-owned `POST /session`; GET/DELETE and all other handlers
remain guarded. Original route dependencies/lifespan are preserved.

All HTTP responses carry server-generated request IDs; API responses are
`no-store`. Runtime error envelopes match the shared camelCase wire contract.
Malformed requests and unexpected failures do not expose submitted values or
exception text. Explicit-origin credentialed CORS is configured for Vite;
production origins must be set and development docs are disabled in production.
Idempotency headers are validated, but **no durable ledger/replay is implemented**.

## Changed files and shared-file claims

Claims were recorded here before editing shared files. Kai coordinates root
`pyproject.toml`, root `.gitignore`, `server/app/requirements-dev.lock`, and the
new coordinator entry D006 in `docs/DECISIONS.md`. App code/run instructions are
under `server/app/`; test adapters are only under `tests/orchestration/`.

No changes to `contracts/`, teammates' implementations, the mock Facebook UI,
web dependencies, existing routing, or database schemas. No new services or
public deployments were created.

## Actual checks

- `.venv/Scripts/python.exe -m pytest tests/orchestration -q`: **42 passed**, no warnings.
- Repeated the documented pinned install in a separate fresh virtual environment
  at `.venv/reproducibility`; `pip check` passed and the same **42 tests passed**.
- `python -m ruff check server/app tests/orchestration`: passed.
- `python -m ruff format --check server/app tests/orchestration`: passed.
- Uvicorn started on loopback; real HTTP probes verified 200 liveness, 503
  unconfigured readiness, request-ID/error envelopes, and no implemented quest
  endpoint accepting a client-supplied identity. Server stopped after verification.
- Existing web `npm run lint` and `npm run build`: passed, no frontend code changes.

The 42 tests include missing/invalid guards, forged participant IDs, session
bootstrap isolation, bounded/missing/duplicate idempotency headers, readiness
timeouts/errors/non-bools, strict payload validation, redacted logs/errors,
credentialed CORS, duplicate dynamic routes, production configuration, and
protocol version/error-code drift.

## Fixture versus live evidence

All registered business routes/guards in these tests are explicitly synthetic
and exist only in the test module. Local socket probes prove HTTP startup, not
authentication or event persistence. No live Muse call, PostgreSQL integration,
real participant action, concurrency/event guarantee, or public deployment is
claimed. Privacy/matching/planning/onboarding were inspected on their remote
branches, not merged or executed in this checkout.

## Upstream review and acknowledgments

Reviewed handoffs and published APIs on:

- Patrik: `origin/role/patrik-privacy@b192050`.
- Adam: `origin/role/adam-planning@7298895`.
- Rishi: `origin/role/rishi-matching@dcfded2`.
- Will: `origin/role/will-voice-ui@45a6732`.

D006 records Kai's ACK of Postgres/privacy-first migration ordering, the public
privacy guards/job recheck hooks, Adam's Python adapter/PEP 420 namespace, Rishi's
matching job entry point, and Will's events-slot props. Three upstream branches
used D005 for different proposals; refer to owner/branch/commit, and consolidate
decision IDs at integration. No unacknowledged wire DTO/evidence-enum change was
adopted here.

## Exact next consumer actions

- **Patrik:** review D006 and `server/app/README.md`; use canonical
  `server.privacy` imports when composing from the repo root. Supply a DB-backed
  privacy registration with `build_router(service)`, `actor_dependency(service)`,
  its error handler, and a real readiness probe. Review the session-creation
  exception. Privacy migration runs before workflow; no workflow tables exist yet.
- **Adam:** ACK the registration convention; compose the process Muse adapter
  from public exports. Extraction should return synchronously under the current
  contract. Live evidence still needs the provider credentials/run owned by Adam.
- **Rishi:** supply the matching job wrapper using authorized candidates and
  the public projection; P1 orchestration will store proposal/version snapshots.
- **Will:** events-slot props are ACKed. `onAccepted` will fire only on a persisted
  server acknowledgment. No event component exists yet. Extraction/transcription
  remain synchronous unless an agreed contract change says otherwise; the job
  status DTO will be coordinated before P1 async routes are landed.

## Remaining work

P0 multi-owner composition/ACKs and a locally configured Postgres are pending.
The teammates' implementations are available on role branches; they are not
missing, but have not been integrated here. P1 will add workflow tables after
privacy, transactional acceptance/idempotency, durable jobs/outbox and unique
event identity, with restart/concurrency tests. Event UI follows the agreed slot
contract alongside that system. No teammate branch was merged and nothing was
pushed to main.
