# Single Muse adapter: owned by adam
Read root AGENTS.md, docs/roles/adam.md and all shared contracts.
Assigned branch: `role/adam-planning`. Do not implement this area from another owner's branch without coordination.
This directory is reserved space only. No code exists here yet: the Group Quests server was removed from main (it survives only on branch `archive/group-quests-before-pivot` as reference) and Constellations is a fresh build.
Constellations: the single Muse provider adapter (target model muse-spark-1.3) used by every Muse job M1-M8; strict JSON, one retry, labeled fallback, sanitized ModelEvidence with callType and latency. Never invent provider APIs. Contract: contracts/protocol.ts (1.0.0, pending D003 ACK).
Validate runtime data; do not duplicate private wire contracts. Coordination: before work check PRs/issues for tags, and when blocked on another owner stop and tag them using the exact block in [docs/COORDINATION.md](../../docs/COORDINATION.md) (sections 1 and 2).
