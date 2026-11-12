# Round lifecycle and orchestration: owned by kai
Read root AGENTS.md, docs/roles/kai.md and all shared contracts.
Assigned branch: `role/kai-orchestration`. Do not implement this area from another owner's branch without coordination.
This directory is reserved implementation space, not a working module.
Constellations: own the round lifecycle (open, locked, inducting, hunt levels, sky, closed), parallel Muse job orchestration, mutual idempotent passphrase/found-code confirm, SSE updates, Sky aggregates, ritual event + chat (P1), operator console API, synthetic top-up and reset. Adapts the merged workflow. Target contract: contracts/constellations.ts (2.0.0-proposed, D009).
Follow contracts/protocol.ts and the relevant service boundary. Validate runtime data; do not duplicate private wire contracts.
