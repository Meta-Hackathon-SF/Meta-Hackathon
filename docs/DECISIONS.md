# Shared decisions
## D001: Feature boundary
Accepted by explicit user direction: existing web/ is a mock Facebook shell. Group Quests gets a separate UI/framework under web/src/features/group-quests/. Preserve existing routes and host layout; Will owns minimal entry integration.

## D002: Workstream ownership
Accepted from the latest team split: Rishi matching, Adam planning, Will voice interaction, Patrik privacy, Kai orchestration. All five own technical systems and their UI components.

## D003: Initial protocol
Foundation proposal: contract version 1.0.0 in contracts/. Each producer/consumer should ACK at H0. Runtime validators and implementations remain pending.

## D004: Server baseline
Proposed: FastAPI + PostgreSQL/Supabase; no server selected or installed by this foundation. Kai + Patrik confirm auth/database configuration, Adam confirms provider integration. Record any changed implementation choice here before parallel backend work.

## Change template
ID / UTC timestamp:
Decision and rationale:
Owner / affected producers and consumers:
Status (proposed or accepted):
ACK evidence:
Contract version / migration:
Verification:

## D005: Matching implementation baseline (Rishi)
ID / UTC timestamp: D005 / 2026-11-12
Decision and rationale: Rishi ACKs contract 1.0.0 (MatchInput, MatchResult, GroupProposal, MusePort) without changes. Matching is implemented in Python 3.10 stdlib under server/matching/ (compatible with the proposed FastAPI baseline in D004, no framework dependency) with runtime validators mirroring protocol.ts. MusePort is consumed through an injected port only; offline tests use a fake port labeled source "replay". The public MatchResult projection (no memberVersions/feasibleWindows) is offered as `public_projection()` for Patrik to adopt or replace with the shared DTO validator.
Owner / affected producers and consumers: Rishi; consumes Patrik (Candidate snapshots) and Adam (MusePort); produces for Adam/Kai (GroupProposal) and Will (matching card).
Status (proposed or accepted): Accepted for Rishi's ownership; non-breaking, no contract change.
ACK evidence: pending from Adam (rank_group task payload shape), Patrik (projection), Kai (route POST /communities/:id/matches registration).
Contract version / migration: 1.0.0, none.
Verification: tests/matching (offline, fake MusePort).

## D007: Session mechanism, privacy routes and snapshot semantics (Patrik)
ID / UTC timestamp: D007 / 2026-11-12T21:17Z. First drafted as D005, renumbered because Rishi's D005 merged to main first. Kai's branch uses D006 and Adam's branch also uses D005. Per Kai's D006, IDs get consolidated as each PR integrates.
Decision and rationale:
- Sessions: `POST /api/v1/session` mints a pseudonymous guest participant and an opaque 256-bit token, held in an HttpOnly/Secure/SameSite=Lax `gq_session` cookie. `Authorization: Bearer` is also accepted for multi-device tests. Only the SHA-256 hash is stored, with 7-day expiry, and `DELETE /session` revokes it. We have no confirmed Facebook or Supabase auth, and the mock shell's users aren't accounts. Synthetic profiles can't hold sessions. Identity is a server `Actor`; a `participantId` in a body is rejected.
- Storage: Postgres with RLS on all `privacy.*` tables. The API connects as a non-owner, non-bypass member of role `gq_api`, with transaction-local `gq.participant_id`. Cross-user reads go only through the `authorized_candidates` / `member_versions` SECURITY DEFINER functions. Privacy migrations run before `db/workflow/`.
- Additive routes beyond contracts/API.md: `POST /session`, `DELETE /session`, `GET /communities/:id/consent`, `POST /communities/:id/leave`, `GET /intents/me?communityId=`. `PUT /intents/me` and `PATCH /intents/me/availability` carry `communityId` in the body, since a participant can belong to more than one community.
- Snapshot semantics: `Candidate.intent.consentVersion` is the current consent revision that authorizes the snapshot. `publicInterests` is `[]` without public-interest consent. The requester must be eligible and is included.
- `Consent.revokedAt` is set on a revision that withdraws **participation** (matching or modelProcessing), and null otherwise. Hiding public interests doesn't set it, but it still emits a `consent_revoked` notice so projections refresh. (This was narrowed on 2026-11-12 because Will's shell treats `revokedAt !== null` as not consented.)
- Queued jobs: the workflow stores the enqueuing Actor's participantId. The worker calls `reauthorize_for_job`, which rechecks membership and consent before acting.
Owner / affected producers and consumers: Patrik (producer). Kai (server composition, jobs, workflow FKs), Rishi and Adam (Candidate consumers), Will (session/consent/intent UI calls).
Status: proposed. Implemented on role/patrik-privacy. No wire type in protocol.ts changed.
ACK evidence: pending from Kai, Rishi, Adam and Will.
Public projections (P2): `PublicGroupProposal` = `{proposalId, revision, members: PublicParticipant[3-5], sharedInterests, publicRationale, evidence}`. This is exactly the shape of Rishi's `matching.public_projection`, so no change is needed on his side. `PublicPlanCard` is QuestPlan minus `memberVersions`/`basedOnRevision`. Both are strict (unknown fields rejected). Before anything reaches a peer, Kai calls `server.privacy.projections.validate_public_proposal(dto, candidates)` / `project_plan(plan, candidates)`. These re-derive member profiles from the authorized snapshot (synthetic labels can't be altered) and reject public text that leaks a member's budget, goal fragment, unconsented interest or individual-constraint phrasing. Proposed to add both DTOs to protocol.ts once Rishi/Kai/Will ACK.
Integration update (2026-11-12, after Kai's D006 at 339ea63):
- Patrik ACKs Kai's registry convention.
- `server.privacy.registration.privacy_registration(service)` returns the `ServiceRegistration` (owner `privacy`, router, `actor_dependency`, a DB readiness probe). Kai's app must also call `install_privacy_error_handler(app)`; otherwise `PrivacyError` reaches the sanitizer and becomes 503 PROVIDER_UNAVAILABLE (reproduced).
- The privacy web client sends `Idempotency-Key` on every mutation.
- The actor is resolved once per request, shared between the router guard and route dependencies.
- Kai's `pyproject.toml` needs `psycopg[binary]>=3.2` and `psycopg-pool>=3.2`.
- `PrivacySlot` matches Will's `PrivacySlotProps`.
- `db/privacy/002_demo_communities.sql` seeds Will's demo community IDs/areas.
Patrik ACKs on other entries: Rishi D005, adopted `public_projection` shape with the privacy gate above. Adam D005 item 2: the draft carries no identity/consent and `PUT /intents/me` owns versioning; `get_consent(actor, communityId).wire()` is the consent input for the extract route. Adam item 3: no objection to `source: "fixture"`, and the privacy UI doesn't render evidence. Adam item 5: privacy now uses the `server.privacy` namespace import.
Contract version / migration: contract 1.0.0 unchanged; db/privacy/001_privacy_foundation.sql.
Verification: `server/.venv/bin/python -m pytest tests/privacy -q` -> 103 passed + 1 skipped on main; 108 passed with Kai's server/app (339ea63) on PYTHONPATH; local Postgres 17, synthetic fixtures only.
