# Shared decisions
## D001: Feature boundary
Accepted by explicit user direction: existing web/ is a mock Facebook shell. Group Quests gets a separate UI/framework under web/src/features/group-quests/. Preserve existing routes and host layout; Will owns minimal entry integration.

## D002: Workstream ownership
Accepted from the latest team split: Rishi matching, Adam planning, Will voice interaction, Patrik privacy, Kai orchestration. All five own technical systems and their UI components.

## D003: Initial protocol
Foundation proposal: contract version 1.0.0 in contracts/. Each producer/consumer should ACK at H0. Runtime validators and implementations remain pending.

## D004: Server baseline
Proposed: FastAPI + PostgreSQL/Supabase; no server selected or installed by this foundation. Kai + Patrik confirm auth/database configuration, Adam confirms provider integration. Record any changed implementation choice here before parallel backend work.

## D005: Muse provider configuration, extraction wire shape, fixture evidence label
ID / UTC timestamp: D005 / 2026-11-12 (Adam, role/adam-planning)
Decision and rationale:
1. Provider (informational, no contract change): Muse is reached through Meta's Meta Model API, OpenAI-compatible `POST https://api.meta.ai/v1/chat/completions`, `Authorization: Bearer`, default model `muse-spark-1.3`, structured output via `response_format.json_schema`. Verified from official dev.meta.ai docs on 2026-11-12; no live call verified yet. `-contributor` model variants are rejected because Meta may train on their prompts. See server/providers/README.md.
2. Additive wire shapes `IntentField`, `IntentDraft`, `ExtractionResult` for `POST /intents/extract` (protocol.ts "PROPOSED (D005)" section). The draft carries no identity/consent/version fields; `timeZone` and `currency` come from the community. Missing facts are listed with fixed server questions, never invented.
3. Additive proposal: allow `ModelEvidence.source = "fixture"` so scripted test doubles are not labeled replay. Interim (until ACK): fixtures use `source: "replay"` with a `model` prefixed `fixture:`; UIs should treat that prefix as fixture.
4. Python MusePort form: `await muse.generate(GenerateRequest(task, request_id, prompt_version, payload, deadline_s?, correction?)) -> GenerateResult(output, evidence, attempts)`; asyncio cancellation replaces AbortSignal. Each owner registers its own `TaskSpec` (instructions + output schema) for its task; the adapter executes only registered (task, promptVersion) pairs.
5. Packaging (Kai to confirm): planning/provider code is standard-library-only Python 3.11+, importable as `server.providers` / `server.planning` with `server/` as a PEP 420 namespace (no shared `server/__init__.py` added). Offline tests: `python3 -m unittest discover -s tests/planning -t .`.
Owner / affected producers and consumers: Adam (producer). Will (renders ExtractionResult), Patrik (persists confirmed intent; consent check input), Rishi (MusePort consumer; registers rank_group spec), Kai (route registration, server composition, manifests).
Status (proposed or accepted): proposed. Items 2-3 need Will + Patrik ACK; item 3 needs all UI owners; items 4-5 need Rishi + Kai ACK.
ACK evidence: pending.
Contract version / migration: additive; CONTRACT_VERSION stays 1.0.0 until ACK, then 1.1.0. No migration.
Verification: tests/planning (33 offline tests, fixture transport + local HTTP stub). Live: pending credentials (`python3 -m server.providers.smoke`).

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
ACK evidence: Kai ACKed the Postgres boundary, migration order and ports in D006 (merged to main, e687906). Pending from Rishi, Adam and Will.
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

## D006: Kai's server composition checkpoint and upstream acknowledgments
ID / UTC timestamp: D006 / 2026-11-12T21:24Z
Decision and rationale:
- FastAPI is now executable in `server/app/` on Kai's branch. Kai coordinates the root Python manifest, pinned dev/runtime dependencies, and composition entry point. This implements the HTTP baseline in D004; it does not claim database integration or a live product journey.
- Kai ACKs Patrik's proposed Postgres boundary and migration order: `db/privacy/001_privacy_foundation.sql` runs before future workflow migrations; planned workflow references use `privacy.participants(participant_id)` and `privacy.communities(community_id)`. This checkout has not run those migrations or verified Postgres.
- Kai ACKs the published `build_router(service)`, `actor_dependency(service)`, `reauthorize_for_job`, `check_member_versions`, and change-listener ports. `POST /session` must bootstrap without an existing session; only privacy may register this exception. All other routes retain the injected session guard. The existing route-level guards are preserved. Bootstrap still requires an idempotency header; durable request replay is P1, not implemented here. Full guest-session lifecycle/schema review and live mounting remain pending.
- Canonical Python imports are `server.<owner>` under a PEP 420 namespace. No shared `server/__init__.py` is added. This ACKs Adam's namespace/stdlib-adapter proposal. Patrik currently documents `privacy` with `--app-dir server`; use the canonical namespace when composing the root app, without importing private tables or creating a second implementation.
- Kai ACKs Adam's typed async Muse adapter form as an internal integration boundary, not as a vendor API. No live model call or endpoint evidence is claimed by Kai. Kai ACKs Rishi's matching job entry point and Will's events-slot props, with `onAccepted` firing only after server-acknowledged persistence. Async matching/planning work will follow the shared job contract; extraction/transcription remain synchronous unless an agreed API change is made.
- The three remote role branches independently used decision ID D005 for different proposals. Do not conflate or overwrite them. References below include owner, branch and commit. Consolidate IDs when their PRs are integrated. This entry does not adopt an unacknowledged extraction DTO, change the evidence enum, or bump protocol 1.0.0.
Owner / affected producers and consumers: Kai (server coordinator); Patrik (auth/database), Adam (provider/planning), Rishi (matching), Will (voice/UI).
Status: Kai's acknowledgments recorded; server registration convention and full multi-owner composition pending consumer review. No breaking wire change landed.
ACK evidence: reviewed `origin/role/patrik-privacy@b192050`, `origin/role/adam-planning@7298895`, `origin/role/rishi-matching@dcfded2`, and `origin/role/will-voice-ui@45a6732` handoffs and published public APIs. These branches were inspected, not merged into Kai's checkout.
Contract version / migration: 1.0.0 unchanged; no workflow tables or migration executed.
Verification: 42 offline server-boundary tests passed on Python 3.13.7; live local HTTP liveness/readiness/error checks passed; real provider/database integration is not verified.

## D008: Contract 1.1.0 proposal for preferences, Muse-created events, negotiation and challenges (Adam)
ID / UTC timestamp: D008 / 2026-11-12T23:10Z (Adam, role/adam-planning). D005 is taken by both Adam and Rishi, D006 by Kai, and D007 by Patrik, so this entry uses the next free number.
Decision and rationale: implements the README pivot at main `45a47e6`. Members share preferences instead of picking an activity. Muse creates an event when nothing fits, negotiates with simulated venues, and sets post-meetup challenges. Wire shapes are in `contracts/protocol.ts` under "PROPOSED (D008)". Python validators are in `server/planning/wire.py`, and the examples in `contracts/examples/1.1.0/` are produced by fixture runs and checked by `tests/planning/test_v11.py`.
1. **PreferenceProfile / PreferenceExtractionRequest / PreferenceExtractionResult** (`POST /preferences/extract`, proposed). The profile holds availability, a per-person `maxBudgetMinor` ceiling, `areaId`, interests, `avoid`, `energy`, `socialComfort` and `openToNew`. It carries no identity or consent. Every value needs a verbatim quote, as in D005. **At most one follow-up, enforced by structure:** code picks the field (availability, then budget, then area, then interests) and uses fixed server wording. A request that carries `followUp` always gets back `followUp: null` and `ready_to_confirm`. Fields still missing are left to Will's confirm-and-tap UI.
2. **PreferenceTraits on Candidate (Patrik-owned shape, proposed):** `Candidate.preferences?: {energy, socialComfort, avoid, openToNew}`. It is optional, so 1.0 snapshots stay valid. Because validators reject unknown fields, Patrik's and Rishi's validators must accept it before anyone sends it. `PrivateIntent` is unchanged. Recommended mapping on confirm: availability, budget and area go to the existing intent fields; interests go to `interests`/`publicInterests` per consent; `goal` becomes a fixed server string ("meet people in this community") until Patrik decides otherwise.
3. **Opportunity (Kai owns storage and the full union; Adam produces `source: "muse_created"`).** `EventCreator.create(CreateEventInput) -> CreateEventResult`. Code enumerates (approved public venue, slot) options where at least 3 same-area members are free and the venue is open, with per-option cost and duration caps that keep at least 3 members eligible. Muse picks one option and writes the activity. Code then re-derives eligibility at the chosen time and price and rejects the choice below 3. `avoid` terms may not appear in the public text. Muse sees only aggregates: public-interest counts, the union of avoid terms without attribution, energy and comfort mixes, and option counts.
4. **VenueBrief / VenueOffer / Counteroffer / NegotiationTurn / Deal / NegotiationResult.** The venue receives only `VenueBrief`: activity, groupSize, window, `totalBudgetMinor = groupSize x lowest member ceiling`, and currency. Code enforces four rules:
   - The group agent may accept only an offer within the limit, and may counter only downward and within the limit.
   - The simulated venue cannot go below its persona floor.
   - Before a Deal exists, the per-person price `ceil(total/size)` is checked against every member's ceiling.
   - A `Deal` is always `status: "awaiting_approval"` and `isSimulated: true`. Nothing is booked or paid.

   **Privacy note for Patrik:** `totalBudgetMinor / groupSize` reveals the lowest ceiling in the group, but not whose it is. Any equal-split total budget has this property, and the README requires sending the total.
5. **RewardOption / Reward / ChallengeInput / Challenge.** The goal metric is `sessions_together` (target 2-6, due in 7-60 days), which Kai can count from completed events. `progress` starts at 0 and Kai owns updates. A reward must come from the approved, simulated `rewardOptions`, and a venue-sponsored reward only from the event's own venue. Text may not claim attendance.
6. **MusePort task enum (additive):** `extract_preferences`, `create_event`, `negotiate`, `venue_persona`, `challenge`. These are allowlisted in `server/providers/port.py` and registered by `register_planning_tasks`.
7. **Provider facts (informational):** live calls on 2026-11-12 reported model `muse-spark-1.3` (Spark family). `extract_intent` took 23.8 s and `rank_group` 17.2 s at `reasoning_effort=low`. The default "high" effort timed out at 30 s on two attempts. Wonder and Ember are not available in the documented model list and were not tested. A journey that makes several sequential calls will not meet a 60 s target, so Kai should overlap jobs (for example, run event creation while the member confirms).
8. **Adam ACKs Rishi's D005** `rank_group` payload/output shape without changes. `server/providers/rank_port.py` registers `rank_group.v1` against it, and a live call through `rank_with_muse` validated. Matching's default `timeout_s=20` is too tight for live calls; use 60 s or more.
Owner / affected producers and consumers: Adam (producer). Will (preference UI, follow-up, pitch card, negotiation view, challenge UI), Patrik (PreferenceTraits snapshot, persistence of the confirmed profile, the venue-brief disclosure), Kai (Opportunity store and union, Deal approval transitions, challenge progress, `/preferences/extract` route, job overlap), Rishi (rank people against an Opportunity; accept `Candidate.preferences`).
Status: proposed. Implemented and offline-tested on role/adam-planning. Not integrated.
ACK evidence: pending. Will: items 1, 4 and 5 (UI shapes). Patrik: items 1, 2 and 4 (privacy). Kai: items 3, 4, 5 and 6 (storage, transitions, routes). Rishi: items 2 and 3 (ranking input).
Contract version / migration: additive; CONTRACT_VERSION stays 1.0.0 until ACK, then 1.1.0 together with the D005 shapes. Validators that reject unknown fields must add `Candidate.preferences` before producers send it. No database migration from Adam.
Verification: `python3 -m unittest discover -s tests/planning -t .` gives 97 OK. `pytest tests/matching tests/planning` gives 199 passed. Live: the two calls in item 7 only. The new 1.1.0 tasks have not been called live.
