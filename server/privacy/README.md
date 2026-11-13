# server/privacy (Patrik): verification, sessions, consent

Contract 2.0.0. Status: **implemented and tested offline** (role tasks 1-6: restore, sessions/consent v2/operator, private answer + guess store with TTL, M1 safety screening, OutputGuard, formationSnapshot lease + publish guard, block/report storage). Not yet mounted in Kai's composed app (server/app is not restored on main).

## Storage
SQLite from the Python standard library (`server/privacy/store.py`, schema `db/privacy/001_privacy.sql`). No database server, no container. `PrivacyStore(":memory:")` in tests; a file path via `CST_PRIVACY_DB` for the demo. Accepted in docs/DECISIONS.md D007 (Kai and Will ACKed; supersedes D002 for privacy storage only).

There is no database-level RLS. Every private query is keyed to `actor.player_id` from a verified session inside `service.py`; nothing else opens the store. Session tokens are stored only as SHA-256 hashes. Consent revisions are append-only.

## Ports (import from `server.privacy`)
| Port | Use |
| --- | --- |
| `PrivacyService.require_session(token) -> Actor` | `PrivacyPort.requireSession`. `Actor(player_id, session_id, community_id, is_operator)`; cannot be constructed outside the service. |
| `actor_dependency(service)` | FastAPI dependency for every authenticated route (cookie `cst_session` or `Authorization: Bearer`). |
| `PrivacyService.require_consent(actor)` | Raises `CONSENT_REQUIRED` unless matchAnswers, anonymousChat and isAdult are all on. Call at answer submit and again at commit for queued work. |
| `PrivacyService.require_operator(actor)` | Raises `FORBIDDEN` for non-operators. |
| `PrivacyService.add_listener(fn)` | `ChangeNotice(kind, player_id, community_id, consent_version, occurred_at)`; `consent_revoked` whenever the player is no longer fully consented. |
| `AnswerStore(store, service, answer_model=None, guess_model=None)` | Pass Will's `server.cycle.wire.DailyAnswer` / `PrevalenceGuess` as the models so reads come back as his camelCase types (privacy never imports them). Implements Will's `AnswerStore` port (server/cycle/ports.py): `get`, `list_for_player`, `save(answer, flag)`, `delete`, `save_guess`, `get_guess`, `purge_cycle`. Plus `mark_locked(cycleId, lockedAt)` (call on Saturday lock: refuses later writes with `CYCLE_LOCKED`, starts the 14-day clock), `purge_expired()`, `delete_my_data(playerId)`, `eligible_answers(cycleId)` (server-only: unflagged answers of fully consenting active members). `save` rejects a weight that is not the WEIGHTS rule and any player without full consent. Deleting removes the row and emits `answer_deleted`. |
| `OutputGuard()` | `check(text, againstAnswers) -> {"ok", "reasons"}` per protocol.ts, the strict mode for every Muse public text: `quote_5_words` (5+ consecutive words of any answer, or 4+ when that answer has at most 12 tokens), `sensitive_term` (health incl. mental health, sexuality, religion, finances, family trauma, home location, immigration status, substance use; optional plural `s`/`es`; single-word terms of 7+ letters also inside one space-free chunk such as `#depressionsquad`), `pii`, `contact_info`. Quote and term checks run on `textfold.fold`: NFKC, accents stripped, Cyrillic/Greek/IPA look-alikes folded, leet only inside mixed letter/digit tokens, `._-` to spaces, zero-width removed, spaced-out letters joined; quote tokens are also plural-stemmed. Terms that caused false positives in the safety eval are deliberately absent (high, straight, visa, dead, temple, closet, pills, sick, belt, mass). `check_chat(text, againstAnswers, revealed=bool)` for chat: quotes and PII always, contact info until a mutual reveal, no topic block (M1 handles distress). `text_guard()` is Will's `TextGuard` for M2 follow-ups. Deterministic, no model call. |
| `register_safety_task(registry)`, `SafetyScreener(muse)` | M1 = `PrivacyPort.screen`. `await screener.screen(text, "answer" | "chat_message") -> "none" | "distress" | "harm"`. A code pre-screen of explicit crisis/violence phrases runs first on folded text (catches `k1ll myself`, `k i l l myself`, homoglyphs, `kms` unless a number precedes it, `unalive`, `goodbye notes`, `enough pills`, `kill me now`, hope/wish-not-to-wake-up forms, `kys` as harm, and `end it` only after an intent lead-in at the end of a clause); a hit returns at once with no model call, and Muse can never downgrade it. Otherwise Muse M1 runs through Adam's adapter (random id + text only, schema-validated). The model's reason is discarded. Provider failure or `muse=None` raises retryable `PROVIDER_UNAVAILABLE`: answers return the error, chat holds the message. `sync_screen()` is Will's `SafetyScreen`. |
| `ActivityStore(store, approved_event_ids=...)` | D010 activity signals. `PUT /me/activity` drops (never stores) any `eventIds` outside the approved catalog. The default source is `server.planning.VenueCatalog.load().event_ids()` (D013), read per request; if the catalog or `event_ids()` is unavailable it fails closed and keeps no event ids. Tests inject a synthetic set. |
| `register_activity_task(registry)`, `ActivityTopics(muse)`, `ActivityClassifier(muse)` (`topics.py`) | **D014 M9, signed off by Patrik with conditions** (code redaction via `redact_for_model`: emails, links, phone/id numbers, street addresses, @mentions; 2,000-char cap; consent copy). Post/comment text is sent to Muse transiently for classification, never stored or logged; only allowlisted labels are kept. Batches of 8 under random per-call ids. Code rechecks every result: only sent ids, a duplicate id fails closed, a missing id gives nothing, enum recheck, at most 3 labels, `sensitive` drops the whole text, only positive/neutral kept. Provider failure keeps no topics (`muse_unavailable`), never keywords. `derive_topics` is the labeled offline fallback used only when no Muse port is configured (`keyword_fallback`). `PUT /me/activity` reports the path in `X-Topic-Source`. |
| `register_sensitivity_task(registry)`, `SensitivityScreen(muse)` (`sensitivity.py`) | **D014 M10, signed off by Patrik.** Second gate AFTER `OutputGuard.check` passes, for every public Muse text. `await allowed(texts) -> list[bool]` (batches of 40, random ids): allowed only if the id came back exactly once with `none`. Provider error or `muse=None` blocks everything. `sync_allowed()` for sync callers. |
| `PrivacyFormation(store, answers, moderation, activity=None, *, question_texts=None)` | Per Kai's CHANGE on #13. `lease = prepare_formation(cycleId, communityId)`: `lease.snapshot` is `{answers, idMap, blockedPairs}` (one random ref per player per lease, server weights, blocked pairs among snapshot players). **D014 (contract 2.2.0, signed off by Patrik):** each answer also carries its stored `questionId`, and with an injected `question_texts(cycleId, communityId) -> {questionId: text}` (stored DailyQuestions, never a new selection) the snapshot adds `questions: [{questionId, text}]` for the answered questions. Players with any flagged answer that cycle are excluded entirely. `LeasedSnapshot(lease)` is Rishi's `SnapshotSource`. `with publish_guard(cycleId, lease.revision, playerIds): commit()` holds privacy's write lock through the commit and raises `STALE_REVISION` if any consent, answer, edit, flag or block changed. Lock order: cycle guard, then privacy guard, then Kai's commit. Privacy calls inside the guard nest as savepoints. Single process; not a cross-store transaction. |
| `ModerationStore(store, service)` | `block(actor, playerId)` (silent no-op for self/unknown/other community), `blocked_by(playerId, communityId)`, `blocked_pairs(...)`, `report(actor, roomId, messageId, handle, reason)` (idempotent per reporter+message), `distinct_reporters(roomId, messageId)` (auto-hide at 2), `reported_message_ids(reporterId, roomId)` (hide for reporter now), `report_queue(operator)` (operator only). |
| `privacy_registration(service, answers=, moderation=, resolve_handle=)` | Kai's `ServiceRegistration`. Pass all three so `DELETE /me/data` and `POST /me/blocks` are mounted in the composed app (without them only join/session/consent are). |
| `build_router(service, answers=None, moderation=None, resolve_handle=None, activity=None, activity_muse=None)`, `install_privacy_error_handler(app)` | Routes below and the `ApiError` envelope for `PrivacyError`. |

## Routes (mounted under /api/v1)
| Route | Body | Result |
| --- | --- | --- |
| POST /communities/:id/join | `{displayName, matchAnswers, anonymousChat, isAdult}` | 201 `{player, consent, isOperator}` + `cst_session` cookie. All three toggles required (403 `CONSENT_REQUIRED`, nothing stored). With a valid session for that Group: 200, same state, no new cookie. |
| GET /session | - | `{player, consent, isOperator}` |
| DELETE /session | - | 204, session revoked, cookie cleared (privacy-owned addition) |
| DELETE /me/data | - | 202 `{status:"deleted"}`. Mounted when `answers` is passed. Deletes all of the player's answers and guesses now and emits `data_deleted` (Kai drops chat authorship links). Session and consent are kept. |
| POST /me/blocks | `{roomId, handle}` | Always 204 (no existence leak). Mounted when `moderation` and Kai's `resolve_handle(actor, roomId, handle) -> playerId | None` are passed. |
| PATCH /me/consent | `{expectedVersion, matchAnswers, anonymousChat, isAdult}` | `Consent`. 409 `STALE_REVISION` on version mismatch; same body retried returns the stored row. Withdrawing any toggle sets `revokedAt`; re-granting all three clears it. |

Cookie: HttpOnly, Secure (opt out only with `CST_COOKIE_INSECURE_DEV=1` for local http), SameSite=Lax, path `/api`, 7 days. Operator role is never granted over HTTP: `fixtures.grant_operator(store, playerId, communityId)` from a local setup script.

## Synthetic data
`fixtures.seed_synthetic_players(store)` loads the 8 `isSynthetic` players from `contracts/fixtures/week-sample.json`. Synthetic players can never hold a session.

## Run
```sh
server/.venv/bin/python -m pytest tests/privacy -q          # offline, no services
CST_COOKIE_INSECURE_DEV=1 server/.venv/bin/uvicorn server.privacy.devapp:app --port 8787   # local harness only
```

Schema: `db/privacy/001_privacy.sql` (players, communities, memberships, consents, sessions), `002_answers.sql` (answers, guesses, cycle_locks) and `003_blocks_reports.sql`. The store applies every `NNN_*.sql` in order.

## Not yet built (role task 7)
Consent screen, private support card and "delete my data" UI under `web/src/features/constellations/privacy/`.
