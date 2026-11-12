# Adaptive planning agent: owned by adam
Read root AGENTS.md, docs/roles/adam.md and all shared contracts.
Assigned branch: `role/adam-planning`. Do not implement this area from another owner's branch without coordination.
This directory is reserved implementation space, not a working module.
Build the stateful Muse propose/validate/revise loop. Own the single Muse adapter and intent extraction so other owners never invent provider APIs.
Follow contracts/protocol.ts and the relevant service boundary. Validate runtime data; do not duplicate private wire contracts.
