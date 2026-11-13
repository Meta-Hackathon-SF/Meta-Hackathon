# Round lifecycle and orchestration: owned by kai
Read root AGENTS.md, docs/roles/kai.md and all shared contracts.
Assigned branch: `role/kai-orchestration`. Do not implement this area from another owner's branch without coordination.
This directory is reserved space only. No code exists here yet: the Group Quests server was removed from main (it survives only on branch `archive/group-quests-before-pivot` as reference) and Constellations is a fresh build.
Constellations: own the round lifecycle (open, locked, inducting, hunt levels, sky, closed), parallel Muse job orchestration, mutual idempotent passphrase/found-code confirm, SSE updates, Sky aggregates, ritual event + chat (P1), operator console API, synthetic top-up and reset. Contract: contracts/protocol.ts (1.0.0, pending D003 ACK).
Validate runtime data; do not duplicate private wire contracts. Coordination: before work check PRs/issues for tags, and when blocked on another owner stop and tag them using the exact block in [docs/COORDINATION.md](../../docs/COORDINATION.md) (sections 1 and 2).
