# API composition and round orchestration: owned by kai
Read root AGENTS.md, docs/roles/kai.md and all shared contracts.
Assigned branch: `role/kai-orchestration`. Do not implement this area from another owner's branch without coordination.
This directory is reserved implementation space, not a working module.
Constellations: API composition for /api/v1 (session, rounds, induction, riddles, finds, sky, stream, operator routes) coordinated by Kai; reuses the merged registry and /health baseline. Target contract: contracts/constellations.ts (2.0.0-proposed, D009).
Follow contracts/protocol.ts and the relevant service boundary. Validate runtime data; do not duplicate private wire contracts.
