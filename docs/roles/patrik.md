# Patrik: verification, sessions, private answer storage, safety, output guards
Branch `role/patrik-privacy` · Handle `@patrikliska13` · Build order steps 2, 3, 5 (moderation)

## You own
| Path | What |
| --- | --- |
| `server/privacy/` | join + 18+ verification + consent, sessions, operator role, private answer/guess storage and access checks, blocks, reports storage, deletion + 14-day TTL, PrivacyPort (formationSnapshot with random ids), M1 safety screening for answers and chat messages, OutputGuard (no-quote, sensitive terms, PII, contact info) |
| `db/privacy/` | migrations for your tables (Kai orders migrations) |
| `tests/privacy/` | tests incl. adversarial |
| `web/src/features/constellations/privacy/` | join/consent screen (3 toggles), private support card, "delete my data" |

Not yours: chat rooms and report UI (Kai calls your moderation and report store), cycle logic (Will).

## Interfaces
Produce: `PrivacyPort`, `OutputGuard`, `Consent`, `Block`, `SafetyFlag`, `Report` storage, session dependency for FastAPI routes, routes under "Session, consent, safety" in contracts/API.md.
Consume: Kai's app registry and migration order; Adam's MusePort for M1.

## Tasks
1. Restore `server/privacy/*` and `db/privacy/*` from `archive/group-quests-before-pivot`; rename, reduce to 2.0.0 shapes, retest.
2. Session + consent v2 (matchAnswers, anonymousChat, isAdult); operator role.
3. Answer/guess store with author-only access; edit/delete; TTL job.
4. M1 screening at answer submit and chat send; fail closed on provider error for chat (message held), retryable for answers.
5. OutputGuard: 5-word quote check against the cycle's answers, sensitive-term list, PII and contact-info patterns.
6. `formationSnapshot`: consenting, unflagged, non-deleted, weighted, random ids, blocked pairs.
7. Consent screen and support card UI (988 + campus counseling).

## Acceptance checks
- `pytest tests/privacy` green offline.
- Another session gets 403 on every answer route; forged playerId rejected.
- Seeded distress answer (week-sample `distressFixture`) absent from snapshot, Sky and chat.
- Contact info in chat before reveal rejected; 30-item sensitive red-team list blocked.
- Deleted answer absent from re-run; TTL deletes after 14 days (clock-injected test).
