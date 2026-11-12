# Keeper prompts and Muse jobs: owned by adam
Read root AGENTS.md, docs/roles/adam.md and all shared contracts.
Assigned branch: `role/adam-planning`. Do not implement this area from another owner's branch without coordination.
This directory is reserved implementation space, not a working module.
Constellations: own the single Muse adapter use and the Keeper voice/prompting rules, plus Muse jobs M2 clarify, M5 society identity, M6 riddle chains, M7 ritual quest and M8 Sky narration. Every output passes Patrik's output guard before release. Adapts the merged propose/validate loop. Target contract: contracts/constellations.ts (2.0.0-proposed, D009).
Follow contracts/protocol.ts and the relevant service boundary. Validate runtime data; do not duplicate private wire contracts.
