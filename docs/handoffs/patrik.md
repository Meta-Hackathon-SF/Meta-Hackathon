# patrik handoff
Current phase: P1, done locally. P2 (public projections + privacy UI) is next.
Status: verified with synthetic fixtures against local Postgres. Not integrated with Kai's server, not deployed, no live users.
Branch + commit: role/patrik-privacy (see `git log`; the first privacy implementation commit is "feat(privacy): sessions, consent, private intents and authorized snapshots").
Shared contract: 1.0.0, unchanged. Additive routes and semantics are proposed in docs/DECISIONS.md D005 (ACK pending).

## Completed deliverables
- P0: auth approach and candidate service signature documented (D005, server/privacy/README.md).
- P1:
  - server/privacy/: guest sessions (hashed opaque token, cookie/Bearer), community membership, versioned consent (CAS + same-body retry), self-only PrivateIntent CRUD and availability updates, `authorized_candidates`, `require_eligible`, `reauthorize_for_job`, `check_member_versions`, and change listeners.
  - db/privacy/: RLS migration, dev DB script and synthetic fixtures.

## Changed interfaces and files
- New: `db/privacy/001_privacy_foundation.sql`, `db/privacy/dev-db.sh`, `server/privacy/{__init__,api,db,errors,fixtures,service,wire,devapp}.py`, `server/privacy/{README.md,requirements.txt}` and `tests/privacy/*`.
- Shared files touched:
  - root `.gitignore` (new: venv/pycache/.env)
  - `docs/DECISIONS.md` (D005 appended)
  - Kai may take over `.gitignore` and the server manifests.

## Checks run + actual result
- `db/privacy/dev-db.sh up && server/.venv/bin/python -m pytest tests/privacy -q`: 76 passed (Python 3.14.2, Postgres 17-alpine, FastAPI 0.162.5, Pydantic 2.14.3, psycopg 3.3.9).
- Coverage:
  - wire drift against protocol.ts
  - forged participantId, snake_case and coerced types
  - non-UTC or overlapping windows
  - RLS as a non-owner role: no actor sees nothing; cross-user read/update/delete/insert denied; sessions unreadable; internal function not executable
  - superuser connection refused
  - synthetic impersonation blocked
  - stale/concurrent consent (6 threads, 1 winner)
  - snapshot filtering by consent, leave and community
  - publication recheck detects stale/revoked members
  - job reauthorization after revoke/leave
  - HTTP 401 envelope with X-Request-Id; validation errors don't echo values
- Mutation check: loosening `intents_self` to `USING (true)` makes the direct policy tests fail (2 tests). Restored afterwards.
- HTTP smoke via `privacy.devapp` + curl: session, join, and 401 envelope.

## Fixture versus live evidence
All evidence uses synthetic profiles labeled "(demo)" with `isSynthetic=true`, plus guest sessions created by the tests. No live participants, provider calls, or deployed DB.

## Next consumer + exact action
- Kai:
  - mount `build_router(service)` at /api/v1 with `install_error_handlers`
  - use `actor_dependency` on every route
  - run `db/privacy` before `db/workflow`, with FKs to `privacy.participants` / `privacy.communities`
  - store the enqueuing actor's participantId on jobs and call `reauthorize_for_job` then `check_member_versions` before publishing
  - register a listener for invalidation
  - ACK D005
- Rishi: consume `authorized_candidates(actor, communityId)` as `MatchInput.candidates`. Never query privacy tables. ACK the D005 open question on PublicGroupProposal.
- Adam: use the same snapshot for `PlanInput.participants`, and only send minimum fields to Muse.
- Will: the onboarding flow calls `POST /session` -> `POST /communities/:id/join` (explicit toggles) -> `PUT /intents/me` with `expectedVersion`.

## Blocked on + owner
- Kai's server scaffold, for integration (the privacy dev harness covers local use until then).
- D005 ACKs from all.
- Public proposal DTO, from Rishi + Kai.

## Next independent task
- P2: allowlisted public projections (participant/proposal/event) with leak tests.
- Privacy UI in web/src/features/group-quests/privacy/: consent panel, leave control, and a "what others see" preview.
