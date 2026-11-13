# Confession capture: owned by will
Read root AGENTS.md, docs/roles/will.md and all shared contracts.
Assigned branch: `role/will-voice-ui`. Do not implement this area from another owner's branch without coordination.
This directory is reserved space only. No code exists here yet: the Group Quests server was removed from main (it survives only on branch `archive/group-quests-before-pivot` as reference) and Constellations is a fresh build.
Constellations: own confession capture by voice (transcribed) or text, 1-400 characters, with typed fallback that never loses the session. Will composes the join, confession, follow-up and guess flow. Contract: contracts/protocol.ts (1.0.0, pending D003 ACK).
Validate runtime data; do not duplicate private wire contracts. Coordination: before work check PRs/issues for tags, and when blocked on another owner stop and tag them using the exact block in [docs/COORDINATION.md](../../docs/COORDINATION.md) (sections 1 and 2).
