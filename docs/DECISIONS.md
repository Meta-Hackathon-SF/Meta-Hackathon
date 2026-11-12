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
