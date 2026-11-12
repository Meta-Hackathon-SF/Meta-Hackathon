# Group Quests server baseline — Kai / P0

This is an executable FastAPI composition baseline. It does **not** implement
authentication, database persistence, matching, Muse calls, or event creation.
The default application registers no synthetic actors or provider adapters.
The existing Facebook shell is unchanged.

## Reproducible setup

From the repository root, with Python 3.11+ (verified using Python 3.13):

```sh
python -m venv .venv
```

Activate the virtual environment:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
```

```sh
# macOS/Linux
. .venv/bin/activate
```

Install the exact versions verified for this checkpoint, then the local package:

```sh
python -m pip install -r server/app/requirements-dev.lock
python -m pip install --no-deps -e .
python -m uvicorn server.app.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Use `.venv/Scripts/python.exe` on Windows if activation is unavailable. The app
does not load `.env` files implicitly; set process variables from the documented
examples in `.env.example`. Keep credentials outside Git.

Open `http://127.0.0.1:8000/health` for liveness and `/docs` for the development
OpenAPI view. `GET /health/ready` deliberately returns **503** until all five
service owners are registered and their readiness probes pass. A running HTTP
process is not evidence of a working Group Quests journey.

## Registration handoff

Kai coordinates root `pyproject.toml`, the dependency lock, this app factory, and
future migration ordering. Consumers should propose dependency additions to Kai
instead of independently creating conflicting manifests.

`create_app(settings=..., registrations=[...])` accepts
`ServiceRegistration(owner, router, authorize, ready)` from `server.app.registry`:

- `owner`: `privacy`, `matching`, `planning`, `orchestration`, or `voice`; one
  registration per owner. Combine that owner's handlers in one `APIRouter`.
- `router`: HTTP routes using paths from `contracts/API.md` **without** `/api/v1`.
  The factory adds that prefix. Duplicate methods/paths, including differently
  named dynamic parameters, fail during application construction.
- `authorize`: a required FastAPI dependency implementing server-side verified
  session/consent checks. Patrik owns its implementation. Supply the same public
  privacy dependency to every protected router; never infer identity from a
  client participant ID or the Facebook shell's localStorage. The sole bootstrap
  exception is privacy-owned `POST /session`, which still requires an idempotency
  key. `GET /session`, `DELETE /session`, and all other API routes keep the guard.
  Session creation behavior remains Patrik's implementation, never a fake actor
  supplied by this app. Resource membership
  and consent must also be rechecked by the owning handler/transaction/stream.
- `ready`: an async, bounded health probe returning a literal bool. Return true
  only when that service's real dependencies are ready. Missing, throwing,
  timing-out, and non-bool probes leave the server unready. No paid provider call
  should be made just to check readiness.

This coordinator-side registration proposal needs acknowledgment from the
service owners before live composition. It does not alter shared wire contracts
or claim a settled authentication mechanism. Test routers/guards exist only in
`tests/orchestration/`; there is no fixture-mode environment bypass in the app.

## Request/error conventions

- Responses carry a server-generated `X-Request-Id`. Caller-provided IDs are not
  used as trusted log metadata. API responses use `Cache-Control: no-store`.
- Runtime `ApiError` fields/error literals match `contracts/protocol.ts` 1.0.0;
  an offline compatibility test checks the version and error-code set.
- `ServiceError(code)` produces the approved status/message/retryability. Request
  validation errors return 400 without echoing submitted values, extra fields,
  tokens, private intents, or exception text.
- Unhandled pre-response service failures return a sanitized, retryable 503 and
  log only a generated request ID. The baseline disables access logging in its
  run command so query strings are not written to request logs.
- All registered mutations require exactly one `Idempotency-Key` (1–128 printable
  ASCII characters without spaces). This is **header validation only**; binding
  actor/route/body, conflict detection, persistence and replay are P1 work.
- Development CORS permits only the two explicit Vite origins by default.
  Production requires `GROUP_QUESTS_ALLOWED_ORIGINS`, comma separated, and disables
  OpenAPI/docs. CORS is not authentication.
- Pure ASGI middleware avoids buffering future SSE. Streaming owners must handle
  authorization/revocation and safe mid-stream errors; SSE is not implemented by
  the existence of this middleware.

## Checks

```sh
python -m ruff check server/app tests/orchestration
python -m ruff format --check server/app tests/orchestration
python -m pytest tests/orchestration -q
```

The tests use clearly synthetic, test-only adapters and make no paid calls.
They cover health/readiness, session-guard execution, forged participant IDs,
malformed requests, idempotency-header validation, sanitized logs/errors, CORS,
startup registration conflicts, and wire-error compatibility.

## Still pending

Remote role handoffs now provide privacy, extraction, matching, and onboarding
implementations. They are not merged into this branch or live-integrated here.
Kai has reviewed the published ports; see `docs/handoffs/kai.md` and the
coordinator entry in `docs/DECISIONS.md` for exact acknowledgments and mismatches.
Patrik: use the canonical `server.privacy` namespace, register `build_router` with
`actor_dependency`, and install the privacy error handler at composition time;
review session bootstrap, no-store/error behavior and database schema boundaries.
Adam/Rishi/Will: acknowledge registration and supply owner routers/readiness
probes. Kai's next system work is P1 transactions, durable jobs, idempotency and
event identity, with privacy migrations first. No PostgreSQL instance or public
deployment has been created or verified on this Windows checkout.
