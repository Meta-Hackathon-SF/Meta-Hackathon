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
