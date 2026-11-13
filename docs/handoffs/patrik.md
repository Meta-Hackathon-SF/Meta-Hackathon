# patrik handoff
Current step: 3 (Daily loop), see docs/PLAN.md. Role tasks 1-3 done offline (1-2 merged to main via PR #15); task 5 (OutputGuard) done offline; next is task 4 (M1 screening).
Status: implemented + tested offline (fixture/in-memory only). Not mounted in a composed app; no live journey.
Branch + commit: `role/patrik-privacy`, based on main `0ab9713`. See git log for the checkpoint commit.
Shared-file claims: docs/DECISIONS.md (ACKs for D005/D006, new D007).

## Completed tasks
1. Restored `server/privacy/*`, `tests/privacy/*` from `archive/group-quests-before-pivot` and reduced them to 2.0.0. Removed Group Quests intents, availability, candidates and projections. Replaced Postgres/psycopg with stdlib SQLite (`db/privacy/001_privacy.sql`, `server/privacy/store.py`), so no database server or Docker is needed.
2. Sessions + consent v2 (matchAnswers, anonymousChat, isAdult) + operator role. Join requires all three toggles. Sessions are Group-scoped and stored as SHA-256 hashes. Consent uses compare-and-set on `expectedVersion`. Synthetic players never hold sessions. Operator is granted only locally.

3. Private answer + guess store (`server/privacy/answers.py`, `db/privacy/002_answers.sql`) implementing Will's proposed `AnswerStore` port method-for-method, plus `mark_locked`, `purge_expired` (14 days after lock), `delete_my_data`, `eligible_answers` (unflagged, fully consenting, active members only; base for task 6). `DELETE /me/data` route. `fixtures.seed_players` = Will's proposed `SyntheticSeeder`.
5. OutputGuard (`server/privacy/guard.py`): protocol `check`, `check_chat(..., revealed)`, `text_guard()` for Will. 30-item sensitive red-team list, 5-word quote fuzz with disguises, PII/contact cases, and no false positives on all 44 question-bank questions and the fixture public texts.

## Changed interfaces and files
- Ports: `require_session(token) -> Actor(player_id, session_id, community_id, is_operator)`, `actor_dependency`, `require_consent`, `require_operator`, `add_listener(ChangeNotice)`, `build_router`, `install_privacy_error_handler`. Details in server/privacy/README.md.
- Routes: POST /communities/:id/join, GET/DELETE /session, PATCH /me/consent.
- Fixtures: `seed_synthetic_players` (week-sample.json players), `grant_operator`, `seed_community`.
- `server/privacy/registration.py` still targets the archived `server.app.registry.ServiceRegistration`. Re-check it once Kai restores server/app.

- `ChangeNotice` gained kinds `answer_deleted` (with `cycle_id`) and `data_deleted`; `consent_version` is now optional (None for non-consent kinds).

## Checks run + actual result
- Task 5 (2026-11-13): `tests/privacy/test_privacy_guard.py` 138 passed; full `pytest tests` **476 passed**. Mutation checks: no zero-width stripping, 6-word quote window, no sensitive check, contact blocked after reveal each fail the suite. Verified through Adam's `guard_allows` and Rishi's `sky._guard_ok` helpers.
- 2026-11-13 composition: `tests/privacy/test_privacy_cycle_composition.py` runs Will's real `CycleService` (main) with Patrik's real `AnswerStore` + `seed_players` and Adam's real `CycleQuestionPort`: submit, read back as Will's model, edit, guess, delete, revoked consent rejected, synthetic top-up, lock freezes writes, distress fixture excluded. Full `pytest tests` on merged main: **338 passed**. Found and fixed: reads returned privacy's snake_case model; Will's code needs his camelCase model, now injected by the composition root.
- Task 3 (2026-11-13): `pytest tests/privacy` **98 passed** offline. Combined privacy+matching+planning+providers **191 passed**. Mutation checks: flagged answers reaching formation, removed weight rule, removed lock check, removed consent check, wrong-scope delete-my-data each fail the suite.
- `server/.venv/bin/python -m pytest tests/privacy -q -p no:cacheprovider`: **68 passed** in 0.16 s, offline. Covers wire drift vs protocol.ts, forged playerId/isOperator/communityId, coercion, control-character names, consent gates, stale/retry, scoping between players, expiry (fake clock), sign-out, synthetic impersonation, cookie flags, no value echo, no-store.
- Mutation checks: an unscoped consent query fails 24 tests; removing the synthetic-session filter fails 1; removing the join consent gate fails 5.
- Not run: ruff (not installed in this venv), web checks (no UI change).

## Fixture versus live evidence
All evidence is offline (in-memory SQLite, synthetic names). No model call. No composed server.

## Requests answered
- 2026-11-13 Kai #13 (registry, session/consent, M1, OutputGuard, report/block store, publish gate): ACK registry; DELIVERED session/consent (#15), listeners, answer store (#24); planned OutputGuard -> M1 -> report/block -> formationSnapshot; CHANGE proposal `formation_snapshot` + `check_publish(cycleId, revision, playerIds)`. https://github.com/willapat/Meta-Hackathon/pull/13#issuecomment-6842159029
- PR opened: #24 (task 3).
- ACK D005 and D006 (producer shapes) recorded in docs/DECISIONS.md.

## Blocked on
- `@willapat` / `@beatopia`: wire `AnswerStore(store, privacy, answer_model=DailyAnswer, guess_model=PrevalenceGuess)` in place of the test-only adapter; call `mark_locked(cycleId, lockedAt)` on Saturday lock (or Kai's `on_locked` hook does). The store accepts his `DailyAnswer` model or a camelCase dict.
- `@beatopia` (Kai): ACK of D007 (SQLite storage vs D002) and restored `server/app` registry to mount `build_router` + `actor_dependency`. Independent work continues.
- `@willapat` (Will): ACK of the join/session response shape in D007.

## Next action
Consumers should swap their stand-ins for `server.privacy.OutputGuard` (Rishi `live_eval._AllowAll`, Adam planning guard, Will `guard=OutputGuard().text_guard()`, Kai chat `check_chat`). Then task 4: M1 safety screening (`PrivacyPort.screen`) via Adam's MusePort `safety_screen`, with a deterministic fail-closed fallback for chat and retryable error for answers. Task 5: OutputGuard (5-word quote, sensitive terms, PII, contact info). Both are independent of other owners.
