# server/privacy (Patrik): verification, sessions, consent

Contract 2.0.0. Status: **implemented and tested offline** (role tasks 1-3: restore, sessions/consent v2/operator, private answer + guess store with TTL). Not yet mounted in Kai's composed app (server/app is not restored on main).

## Storage
SQLite from the Python standard library (`server/privacy/store.py`, schema `db/privacy/001_privacy.sql`). No database server, no container. `PrivacyStore(":memory:")` in tests; a file path via `CST_PRIVACY_DB` for the demo. Proposed in docs/DECISIONS.md D007 (needs Kai's ACK because D002 named PostgreSQL).

There is no database-level RLS. Every private query is keyed to `actor.player_id` from a verified session inside `service.py`; nothing else opens the store. Session tokens are stored only as SHA-256 hashes. Consent revisions are append-only.

## Ports (import from `server.privacy`)
| Port | Use |
| --- | --- |
| `PrivacyService.require_session(token) -> Actor` | `PrivacyPort.requireSession`. `Actor(player_id, session_id, community_id, is_operator)`; cannot be constructed outside the service. |
| `actor_dependency(service)` | FastAPI dependency for every authenticated route (cookie `cst_session` or `Authorization: Bearer`). |
| `PrivacyService.require_consent(actor)` | Raises `CONSENT_REQUIRED` unless matchAnswers, anonymousChat and isAdult are all on. Call at answer submit and again at commit for queued work. |
| `PrivacyService.require_operator(actor)` | Raises `FORBIDDEN` for non-operators. |
| `PrivacyService.add_listener(fn)` | `ChangeNotice(kind, player_id, community_id, consent_version, occurred_at)`; `consent_revoked` whenever the player is no longer fully consented. |
| `AnswerStore(store, service)` | Implements Will's proposed `AnswerStore` port (server/cycle/ports.py): `get`, `list_for_player`, `save(answer, flag)`, `delete`, `save_guess`, `get_guess`, `purge_cycle`. Plus `mark_locked(cycleId, lockedAt)` (call on Saturday lock: refuses later writes with `CYCLE_LOCKED`, starts the 14-day clock), `purge_expired()`, `delete_my_data(playerId)`, `eligible_answers(cycleId)` (server-only: unflagged answers of fully consenting active members). `save` rejects a weight that is not the WEIGHTS rule and any player without full consent. Deleting removes the row and emits `answer_deleted`. |
| `build_router(service, answers=None)`, `install_privacy_error_handler(app)` | Routes below and the `ApiError` envelope for `PrivacyError`. |

## Routes (mounted under /api/v1)
| Route | Body | Result |
| --- | --- | --- |
| POST /communities/:id/join | `{displayName, matchAnswers, anonymousChat, isAdult}` | 201 `{player, consent, isOperator}` + `cst_session` cookie. All three toggles required (403 `CONSENT_REQUIRED`, nothing stored). With a valid session for that Group: 200, same state, no new cookie. |
| GET /session | - | `{player, consent, isOperator}` |
| DELETE /session | - | 204, session revoked, cookie cleared (privacy-owned addition) |
| DELETE /me/data | - | 202 `{status:"deleted"}`. Mounted when `answers` is passed. Deletes all of the player's answers and guesses now and emits `data_deleted` (Kai drops chat authorship links). Session and consent are kept. |
| PATCH /me/consent | `{expectedVersion, matchAnswers, anonymousChat, isAdult}` | `Consent`. 409 `STALE_REVISION` on version mismatch; same body retried returns the stored row. Withdrawing any toggle sets `revokedAt`; re-granting all three clears it. |

Cookie: HttpOnly, Secure (opt out only with `CST_COOKIE_INSECURE_DEV=1` for local http), SameSite=Lax, path `/api`, 7 days. Operator role is never granted over HTTP: `fixtures.grant_operator(store, playerId, communityId)` from a local setup script.

## Synthetic data
`fixtures.seed_synthetic_players(store)` loads the 8 `isSynthetic` players from `contracts/fixtures/week-sample.json`. Synthetic players can never hold a session.

## Run
```sh
server/.venv/bin/python -m pytest tests/privacy -q          # offline, no services
CST_COOKIE_INSECURE_DEV=1 server/.venv/bin/uvicorn server.privacy.devapp:app --port 8787   # local harness only
```

Schema: `db/privacy/001_privacy.sql` (players, communities, memberships, consents, sessions) and `002_answers.sql` (answers, guesses, cycle_locks). The store applies every `NNN_*.sql` in order.

## Not yet built (role tasks 4-7)
M1 safety screening, OutputGuard, `formationSnapshot` (built on `eligible_answers`), blocks/reports storage, consent screen and support card UI.
