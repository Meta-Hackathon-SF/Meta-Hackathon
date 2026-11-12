# patrik handoff
Updated: 2026-11-12T21:39Z
Current phase:
- P1 verified locally.
- P2 privacy-owned pieces are built and verified locally: public projections, leak guard and privacy UI.
- P2 live integration (Will's consent wiring, Kai's guards at routes and subscriptions) is not done.
Status: verified with synthetic fixtures against local Postgres plus a local browser run. Not integrated into Kai's server or Will's shell, not deployed, no live users.
Branch: role/patrik-privacy. P1 (b192050) and P2 (329078f) merged to main via PR #6 (616e543). This update is the integration-fixes commit on top of main.
Shared contract: 1.0.0, unchanged. The additive routes, DTOs and semantics are in docs/DECISIONS.md **D007**, renumbered from my D005 because Rishi and Adam also used D005. ACKs pending.

## Completed deliverables
- P0: auth approach and candidate signature documented (D007, server/privacy/README.md).
- P1:
  - sessions, membership, versioned consent and self-only intents
  - RLS migration
  - `authorized_candidates`, `require_eligible`, `reauthorize_for_job`, `check_member_versions` and change listeners
- P2 (privacy part):
  - `server/privacy/projections.py`: `PublicGroupProposal` (same shape as Rishi's `public_projection`), `PublicPlanCard`, `project_proposal`, `validate_public_proposal`, `project_plan`, and the `find_leaks` private-fact guard
  - `web/src/features/group-quests/privacy/`: `PrivacyCenter`, `JoinCommunityCard`, `ConsentPanel`, `PublicPreview`, `LeaveCommunity`, the HTTP and fixture clients, and `usePrivacySession`

## Changed interfaces and files
- Import path is now `server.privacy` (namespace style matching Rishi/Adam). Test files are renamed to `test_privacy_*.py` so a combined `pytest tests/` run doesn't collide on basenames.
- New: `server/privacy/projections.py`, `tests/privacy/test_privacy_projections.py`, `web/src/features/group-quests/privacy/*`.
- Shared files touched:
  - `.gitignore` (root)
  - `docs/DECISIONS.md` (D007, including ACK notes on Rishi D005 and Adam D005 items 2/3/5)
  - no changes to `web/src/App.tsx`, `vite.config.ts` or the shell

## Integration fixes after Kai/Will branches (this update)
These came from inspecting `origin/role/kai-orchestration@339ea63` and `origin/role/will-voice-ui@45a6732`:
- **Error handler:** `server/privacy/registration.py` provides `privacy_registration(service)` for Kai's `create_app`, plus `install_privacy_error_handler(app)`. Without the handler, privacy errors become 503 PROVIDER_UNAVAILABLE in Kai's app (reproduced).
- **Readiness:** a DB readiness probe that runs off the event loop.
- **Single resolve:** the actor is resolved once per request.
- **Idempotency:** the web client sends `Idempotency-Key` on every mutation, as Kai's registry requires.
- **Will's slot:** `PrivacySlot` matches Will's `PrivacySlotProps {communityId, mode, onConsentChange}`.
- **`revokedAt` narrowed** to matching/model withdrawal, so Will's `revokedAt === null` check is correct.
- **Communities:** `db/privacy/002_demo_communities.sql` seeds Will's demo communities.

## Checks run + actual result
- Integration fixes:
  - `pytest tests/privacy tests/matching` on this branch: 205 passed, 1 skipped (the Kai composition test skips until Kai merges)
  - `pytest tests/privacy` with Kai's `server/app` (339ea63, exported, not merged) on PYTHONPATH: 108 passed. This includes 5 composition tests: bootstrap needs a key but no session, protected routes give 401, privacy codes are preserved (409/404/400, not 500/503), Will's communities are joinable, readiness reports privacy ready.
  - Browser check: `PrivacySlot` → Vite proxy → Kai's `create_app` + privacy → Postgres. It reported `null` before joining and v1 granted after; hiding interests kept `revokedAt` null; a stale save from a second tab gave 409 and a reload; withdrawing matching set `revokedAt`; all 5 mutations carried `Idempotency-Key`. The temporary files and servers were removed afterwards.
  - `web`: tsc, oxlint and vite build ok.
- Earlier P1/P2 checks:
- `server/.venv/bin/python -m pytest tests/privacy -q`: 100 passed. That's 76 from P1 plus 24 projection tests:
  - allowlist drops memberVersions/feasibleWindows/private fields
  - synthetic label can't be altered
  - member outside the snapshot gives FORBIDDEN
  - 8 leak phrasings rejected, 4 group-level phrasings allowed
  - plan text fields all checked, and the plan's own cost is allowed
  - a prompt-injection string is treated as data
- `cd web && npx tsc -b`: ok. `npm run lint` (oxlint): ok, 0 warnings in privacy/. `npx vite build`: ok, though the privacy module isn't in the bundle until Will mounts it.
- Browser run: a temporary preview page (not committed), Playwright, the privacy dev server and Postgres. The flow passed:
  - signed out, then start
  - join with all toggles off by default, and join blocked without a name
  - join with matching + Muse, giving matchable v1
  - withdrawing shows the warning; save gives v2, not matchable
  - a second tab saves v3, then the first tab's stale save reloads to v3
  - leave, then back to the join card with a notice
  - fixture mode at 375px shows the badge, with no horizontal overflow
  - Only console error: the expected 409 from the deliberate stale save. Screenshots were reviewed locally, not committed.

## Fixture versus live evidence
- All evidence uses synthetic profiles ("(demo)", isSynthetic=true) and test guest sessions.
- The leak guard is heuristic: it catches known facts and phrasing, not paraphrases.
- No live participants, no Muse output was checked, no deployment.

## Next consumer + exact action
- Kai:
  - `create_app(registrations=[privacy_registration(service), ...])` then `install_privacy_error_handler(app)`
  - add `psycopg[binary]>=3.2` and `psycopg-pool>=3.2` to pyproject
  - `tests/privacy/test_privacy_kai_composition.py` runs automatically once server/app is on main
  - run the db/privacy migration first; FK to `privacy.participants` / `privacy.communities`
  - jobs store the enqueuing participantId, then `reauthorize_for_job` and `check_member_versions` before publishing
  - pass proposals and plans through `validate_public_proposal` / `project_plan` before any peer read, SSE or snapshot
  - register a `ChangeNotice` listener to invalidate jobs
  - ACK D007
- Will:
  - register `featureSlots = { privacy: PrivacySlot }` (one line in shell/slots.ts)
  - add a vite `/api` proxy
  - onboarding confirm step calls `PUT /intents/me` with `expectedVersion` (0 = create)
  - ACK D007
- Rishi: matching input = `authorized_candidates(actor, communityId)`. Keep `public_projection`; Kai gates it via `validate_public_proposal`.
- Adam:
  - planning input participants = the same snapshot
  - the extract route's consent input = `get_consent(actor, communityId).wire()`
  - your planner's public text goes through `project_plan`, which raises `INVALID_INPUT` with a leak code: retry or use a template

## Blocked on + owner
- Kai's server/app scaffold (live integration).
- Will's shell route (UI mount).
- D007 ACKs (all).
- Muse credentials (Adam), before the leak guard can be checked on live model text.

## Next independent task
- P3: `POST /quests/:id/leave` (needs Kai's quest tables) and subscription invalidation hook, i.e. a per-quest membership recheck function for SSE reconnect.
- Rate limit `POST /session`.
- Adversarial test: revoke during an in-flight model call, then the publish recheck blocks it (fixture job).
