# Privacy, consent and output guard: owned by patrik
Read root AGENTS.md, docs/roles/patrik.md and all shared contracts.
Assigned branch: `role/patrik-privacy`. Do not implement this area from another owner's branch without coordination.
This directory is reserved space only. No code exists here yet: the Group Quests server was removed from main (it survives only on branch `archive/group-quests-before-pivot` as reference) and Constellations is a fresh build.
Constellations: own ConsentV2 (3 toggles incl. 18+), answers readable only by author and server, blocks, M1 safety triage, the output guard (no-quote 5+ word checker, sensitive-term filter), Sky threshold (3 demo / 25 prod), deletion + 14-day TTL, and the prompt builder that strips all profile fields. Contract: contracts/protocol.ts (1.0.0, pending D003 ACK).
Validate runtime data; do not duplicate private wire contracts. Coordination: before work check PRs/issues for tags, and when blocked on another owner stop and tag them using the exact block in [docs/COORDINATION.md](../../docs/COORDINATION.md) (sections 1 and 2).
