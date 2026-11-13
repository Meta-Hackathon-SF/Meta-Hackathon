# Constellations 2.0.0 server foundation

Python 3.11+. From the repository root, create and activate a virtual environment:

```sh
python -m pip install -r server/app/requirements-dev.lock
python -m pip install --no-deps -e .
python -m uvicorn server.app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

No environment file loads automatically. See `.env.example` for public settings;
keep credentials outside Git. `/health` is liveness, while `/health/ready` returns
503 until all registered areas are genuinely ready. The default app mounts no
player routes and has no test adapter, fake session or provider fallback.

## Router registry for every owner

Import `create_app` from `server.app.main` and `ServiceRegistration` from
`server.app.registry`. Pass `registrations=[ServiceRegistration(owner, router,
authorize, ready)]`. Owners are `privacy`, `cycle`, `voice`, `matching`, `planning`,
`orchestration`, `chat`; combine an area's routes in one APIRouter.

- Router paths follow contracts/API.md without `/api/v1`; Kai adds that prefix.
- `authorize` is Patrik's server-verified session dependency, supplied explicitly.
  The owning handler must recheck resource membership and consent at commit/read.
  Only privacy's `POST /communities/{id}/join` skips the global session guard.
  Join still requires Idempotency-Key and Patrik's abuse/verification checks.
- `ready` is async and returns literal True only with actual dependencies ready.
  A false value, exception or 500ms timeout fails closed; never probe a paid model.
- Missing guards, duplicate owners/routes and unsupported routes fail startup.
  Owner routers and dependencies are preserved; do not import teammates' internals.

Reply ACK/CHANGE on Kai's PR with your router factory, guard and readiness export
before live wiring. This Python registry convention changes no shared contract.

## Safety and limitations

Error codes, camelCase envelope and runtime validation mirror protocol.ts 2.0.0.
Request errors expose no submitted values. Logs contain only generated requestId;
run with access logging disabled to keep query strings private. CORS is explicit;
production requires CONSTELLATIONS_ALLOWED_ORIGINS and disables docs/OpenAPI.

Mutations validate one bounded Idempotency-Key header. Actor/route/body binding
and replay must be implemented transactionally by each service; header validation
alone does not provide idempotency. Workflow schema has no API grants. Production
privacy transactions and cycle revision gates remain blocked on owner ACKs.
No fixture adapter is imported by server code. Ordinary tests make no model calls.

```sh
python -m pytest tests/orchestration tests/chat -q
python -m ruff check server/app server/orchestration server/chat tests/orchestration tests/chat
```

See docs/handoffs/kai.md for actual checks, blockers and fixture versus live status.

## Public composition and operator readers

`server.app.composition.compose(privacy=privacy_service, registrations=[...])`
mounts Patrik's published privacy registration and error handler, preserving Kai's
request/validation middleware. Caller configures the service and its lifespan;
Kai never opens or queries the privacy store.

`server.app.operator.operator_registration(session_dependency=...,
require_operator=privacy.require_operator, calls_source=..., reports_source=...)`
provides GET /operator/calls and /operator/reports under the orchestration area.
Sources are synchronous callbacks taking the verified Group-scoped Actor and
returning approved wire dictionaries. Scope the reader to that Group; do not pass
a multi-Group global log. Output is projected to MuseCallEvidence/Report fields
and runtime-validated. A missing source returns 503, never a fake empty queue.
Combine this router into the orchestration registration when adding formation
routes rather than registering the same area twice.
