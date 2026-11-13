# patrik handoff
Current step: 2 (Foundation), see docs/PLAN.md. Role tasks 1 and 2 done offline; next is task 3.
Status: implemented + tested offline (fixture/in-memory only). Not mounted in a composed app; no live journey.
Branch + commit: `role/patrik-privacy`, based on main `f99b533`. See git log for the checkpoint commit.
Shared-file claims: docs/DECISIONS.md (ACKs for D005/D006, new D007).

## Completed tasks
1. Restored `server/privacy/*`, `tests/privacy/*` from `archive/group-quests-before-pivot` and reduced them to 2.0.0. Removed Group Quests intents, availability, candidates and projections. Replaced Postgres/psycopg with stdlib SQLite (`db/privacy/001_privacy.sql`, `server/privacy/store.py`), so no database server or Docker is needed.
2. Sessions + consent v2 (matchAnswers, anonymousChat, isAdult) + operator role. Join requires all three toggles. Sessions are Group-scoped and stored as SHA-256 hashes. Consent uses compare-and-set on `expectedVersion`. Synthetic players never hold sessions. Operator is granted only locally.

## Changed interfaces and files
- Ports: `require_session(token) -> Actor(player_id, session_id, community_id, is_operator)`, `actor_dependency`, `require_consent`, `require_operator`, `add_listener(ChangeNotice)`, `build_router`, `install_privacy_error_handler`. Details in server/privacy/README.md.
- Routes: POST /communities/:id/join, GET/DELETE /session, PATCH /me/consent.
- Fixtures: `seed_synthetic_players` (week-sample.json players), `grant_operator`, `seed_community`.
- `server/privacy/registration.py` still targets the archived `server.app.registry.ServiceRegistration`. Re-check it once Kai restores server/app.

## Checks run + actual result
- `server/.venv/bin/python -m pytest tests/privacy -q -p no:cacheprovider`: **68 passed** in 0.16 s, offline. Covers wire drift vs protocol.ts, forged playerId/isOperator/communityId, coercion, control-character names, consent gates, stale/retry, scoping between players, expiry (fake clock), sign-out, synthetic impersonation, cookie flags, no value echo, no-store.
- Mutation checks: an unscoped consent query fails 24 tests; removing the synthetic-session filter fails 1; removing the join consent gate fails 5.
- Not run: ruff (not installed in this venv), web checks (no UI change).

## Fixture versus live evidence
All evidence is offline (in-memory SQLite, synthetic names). No model call. No composed server.

## Requests answered
- GitHub PR/issue tags could not be checked: the repo is private and Patrik's machine has no `gh` CLI or API auth. Remote handoffs of all four owners were inspected; none has a 2.0.0 request for Patrik (all predate the pivot).
- ACK D005 and D006 (producer shapes) recorded in docs/DECISIONS.md.

## Blocked on
- `@beatopia` (Kai): ACK of D007 (SQLite storage vs D002) and restored `server/app` registry to mount `build_router` + `actor_dependency`. Independent work continues.
- `@willapat` (Will): ACK of the join/session response shape in D007.

## Next action
Task 3: answer/guess store with author-only access, edit/delete, 14-day TTL with clock-injected test. Shapes come from Will's `DailyAnswer`/`PrevalenceGuess` in protocol.ts; the cycle/lock check stays Will's (`CyclePort`).
