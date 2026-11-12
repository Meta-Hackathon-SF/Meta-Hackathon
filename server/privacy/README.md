# Privacy and group-access system (Patrik)

Status: **P1 + P2 privacy pieces (projections, UI) implemented and verified locally with synthetic fixtures** against Postgres 17 in Docker. Not deployed, not integrated with Kai's server composition yet, no live participants. See `docs/handoffs/patrik.md` for current evidence.

## Run locally
```sh
python3 -m venv server/.venv && server/.venv/bin/pip install -r server/privacy/requirements.txt
db/privacy/dev-db.sh up                  # disposable Postgres on 127.0.0.1:54329
server/.venv/bin/python -m pytest tests/privacy -q
# optional HTTP harness (privacy routes only; NOT the Group Quests server)
GQ_DATABASE_URL=postgresql://gq_api_login@127.0.0.1:54329/postgres GQ_COOKIE_INSECURE_DEV=1 \
  server/.venv/bin/uvicorn server.privacy.devapp:app --port 8787
```

## Auth approach (decision D007)
- `POST /api/v1/session` creates a **pseudonymous guest participant** for this device and sets an opaque 256-bit session token in `gq_session` (HttpOnly, Secure, SameSite=Lax, path `/api`, 7-day expiry). `Authorization: Bearer <token>` is accepted for multi-device tests.
- Only the SHA-256 hash is stored. Synthetic profiles can never hold a session.
- Identity is the `Actor` returned by `PrivacyService.resolve(token)`. It cannot be built from a participantId. Request bodies never carry identity, and `participantId` in a body is rejected as an unknown field.
- This is **not** Facebook login. The mock shell's demo users are not accounts.

## Ports for other owners (import from `server.privacy`)
| Consumer | Call | Notes |
| --- | --- | --- |
| Kai (all routes) | `actor_dependency(service)` FastAPI dependency -> `Actor` | 401 `UNAUTHENTICATED` envelope on failure |
| Kai (composition) | `server.privacy.registration.privacy_registration(service)` in `create_app(registrations=[...])`, then `install_privacy_error_handler(app)` | without the handler, privacy errors become 503 under Kai's sanitizer. `install_error_handlers` is for the standalone dev harness only |
| Rishi / Adam via Kai's job | `service.authorized_candidates(actor, communityId) -> list[Candidate]` | validated `Candidate` wire objects for `MatchInput.candidates` / `PlanInput.participants` |
| Kai (enqueue guard) | `service.require_eligible(actor, communityId)` | raises `CONSENT_REQUIRED` |
| Kai (worker) | `service.reauthorize_for_job(enqueuedBy, communityId) -> Actor` | `enqueuedBy` = the verified actor stored at enqueue time; rechecks membership + consent now |
| Kai (before publish) | `service.check_member_versions(actor, communityId, memberVersions) -> VersionCheck` | `current`, `stale_participant_ids`, `ineligible_participant_ids` (Python, server-internal); actor must be in the set (max 5) |
| Kai (invalidation) | `service.add_listener(fn(ChangeNotice))` | kinds `consent_granted`, `consent_revoked`, `intent_updated`, `left_community`; ids + versions only, fired after commit |

Snapshot semantics:
- The requester must itself be eligible (`CONSENT_REQUIRED` otherwise) and is included in the result.
- Eligible means: an active member, current consent with `matching && modelProcessing`, and a confirmed intent in the same community.
- `publicProfile.publicInterests` is `[]` unless that member consented to public interests. `isSynthetic` is carried from the participant row.
- `intent.consentVersion` is the **current** consent revision that authorizes the snapshot, so `memberVersions` built from it can be rechecked later.

## HTTP routes (`/api/v1`)
| Route | Body | Result |
| --- | --- | --- |
| `POST /session` | none | `SessionView`, sets cookie |
| `GET /session` | none | `{participantId, expiresAt, memberships:[{communityId, displayName, consent, hasIntent, intentVersion}]}` |
| `DELETE /session` | none | 204, session revoked |
| `POST /communities/:id/join` | `{displayName, consent:{matching, modelProcessing, publicInterests}}` | `MembershipView`. Idempotent for an active member; consent changes go through PATCH |
| `GET /communities/:id/consent` | none | `Consent` |
| `PATCH /communities/:id/consent` | `{expectedVersion, matching, modelProcessing, publicInterests}` | `Consent` v+1. 409 `STALE_REVISION` on version mismatch; same-body retry returns the stored result |
| `POST /communities/:id/leave` | none | `Consent` (all false, `revokedAt` set). Private intent deleted |
| `GET /intents/me?communityId=` | none | own `PrivateIntent` or 404 |
| `PUT /intents/me` | `{communityId, expectedVersion (0=create), goal, interests, areaId, timeZone, availability, maxBudgetMinor, currency, maxDurationMinutes, groupPreference}` | `PrivateIntent` |
| `PATCH /intents/me/availability` | `{communityId, expectedVersion, availability}` | `PrivateIntent` v+1 and an `intent_updated` notice |

The server sets `participantId`, `intentVersion`, `consentVersion` and `confirmedAt`. `areaId` must belong to the community and `currency` must equal the community currency. Windows are RFC3339 UTC (`Z`), half-open, start < end, non-overlapping, 1-20 of them.

`Consent.revokedAt` is set on a revision that withdraws matching or model processing; otherwise `null`. Hiding public interests leaves it `null` but emits `consent_revoked`.

## Storage (`db/privacy/001_privacy_foundation.sql`)
- **Demo seed:** `002_demo_communities.sql` seeds `demo-campus` plus Will's shell communities (`hackathon-builders`, `meta-ai-explorers`, `xr-student-collective`), all `is_demo`.
- **Tables:** `privacy.participants`, `sessions`, `communities`, `memberships`, `consents` (append-only revisions) and `private_intents` (one current row; overwritten on update, deleted on leave).
- **Row-level security:** policies on all tables, scoped to the `gq_api` role. The API must connect as a non-owner, non-superuser, non-BYPASSRLS member of `gq_api`, and `Database` refuses to start otherwise.
- **Fail-closed identity:** `gq.participant_id` is set per transaction only from a verified session. If it's unset, every query returns nothing.
- **Cross-user access** goes only through the SECURITY DEFINER functions `authorized_candidates` and `member_versions`.
- **Migration order:** privacy runs first. `db/workflow/` (Kai) may reference `privacy.participants(participant_id)` and `privacy.communities(community_id)`.

## Public projections (`server/privacy/projections.py`)
- `project_proposal(groupProposal, candidates) -> PublicGroupProposal`: from Rishi's GroupProposal. Members are re-derived from the snapshot; a member outside it gives `FORBIDDEN`.
- `validate_public_proposal(dto, candidates)`: gate for an already-projected dict (e.g. `matching.public_projection`). Uses a strict shape, requires member profiles identical to the authorized ones (synthetic labels preserved), and leak-checks the text.
- `project_plan(questPlan, candidates) -> PublicPlanCard`: drops `memberVersions`/`basedOnRevision`. It leak-checks title, activity, collaborationTask, publicRationale and opener. The plan's own cost is an allowed public amount.
- `find_leaks(texts, candidates)` returns codes like `publicRationale:budget`, `:goal` (5-word overlap), `:unconsented_interest` and `:individual_constraint` (e.g. "Sam's budget", "can't afford", "only free after"). It never echoes the value.
- **Limits:** the check is heuristic (known facts and phrasing), not proof. Paraphrased disclosures can pass, so public text must still be built from approved facts.

## Privacy UI (`web/src/features/group-quests/privacy/`)
See its README. `PrivacyCenter` handles the whole flow (start session -> consent-first join -> consent panel -> what-others-see preview -> leave). The building blocks are also exported. `httpPrivacyClient('/api/v1')` is the live client; `fixturePrivacyClient()` shows a "Fixture mode" badge.

## Not done yet
These are planned, not implemented:
- Quest leave (`POST /quests/:id/leave`, with Kai) and subscription invalidation (P3).
- Invite scoping (P4).
- Privacy UI under `web/src/features/group-quests/privacy/`.
- Rate limiting on `POST /session`.
- Supabase-specific role mapping.
