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
